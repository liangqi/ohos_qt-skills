"""应用依赖鸿蒙产物一键获取（agent 工具，见 docs/fetch-deps.md）。

    python portgraph.py fetch-deps <app> [--out DIR] [--force] [--dry-run] [--json]

依赖闭包口径：沿 runtime / uses-module 边递归（与可移植性判定引擎一致），
跳过 platform_cond=macos 的条件依赖。与判定引擎的关键差异：已鸿蒙化
（ported）的包也继续下钻其 runtime 依赖——bottle 不捆绑依赖，目标侧
链接/运行仍需要其依赖的产物（.so / 头文件 / pkg-config）。

build/test 依赖是主机构建工具（cmake/nasm 等在构建机运行），
不属于目标侧产物需求，不下载。

节点分类（manifest 中的 status）：
  downloaded    本次下载并解压成功
  already_local 本地已就绪（artifact_local 或 out/<name>/<version>/ 已存在）
  covered       同名包产物已由另一数据源节点获取（hb:/cmdpkgs: 去重）
  provided      Qt 模块 / 平台 API，由 Qt SDK / 鸿蒙框架本身提供
  cmd_only      无直链但有获取命令（多为 formula 缺版本号无法构造 bottle URL）
  need_port     无产物，需自行交叉编译（附源码链接）
  failed        下载失败（404 / 网络错误 / sha256 不匹配）
  target        应用节点自身
"""

from __future__ import annotations

import json
import re
import tarfile
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import db, engine, harmonybrew

RECURSE_TYPES = ("runtime", "uses-module")
SKIP_PLATFORM_CONDS = ("macos",)
PROVIDED_KINDS = ("qt-module", "platform-api")

# cmd-pkgs 产物 URL 尾部 .../<name>-<version>-ohos-aarch64.tar.gz
_URL_VER_RE = re.compile(r"-(.+?)-ohos-aarch64\.tar\.gz$")


def dependency_closure(conn, app_id: str) -> List[Dict]:
    """BFS 收集应用依赖闭包（含 app 自身），按发现序返回节点列表。

    provided 节点（Qt 模块）不展开——其依赖由 Qt SDK 自带。
    """
    result: List[Dict] = []
    visited = {app_id}
    queue = [app_id]
    while queue:
        nid = queue.pop(0)
        node = db.get_node(conn, nid)
        if node is None:
            continue
        result.append(node)
        if node["kind"] in PROVIDED_KINDS:
            continue
        for e in db.out_edges(conn, nid, RECURSE_TYPES):
            if e.get("platform_cond") in SKIP_PLATFORM_CONDS:
                continue
            if e["dst"] not in visited:
                visited.add(e["dst"])
                queue.append(e["dst"])
    return result


def _ver_from_url(url: str) -> Optional[str]:
    m = _URL_VER_RE.search(url)
    return m.group(1) if m else None


def _list_libs(installed: Path) -> List[str]:
    lib_dir = installed / "lib"
    if not lib_dir.is_dir():
        return []
    return sorted(p.stem[3:] for p in lib_dir.glob("lib*.so"))


def _hints(installed: Path, libs: List[str]) -> Dict:
    return {
        "cmake": (
            "cmake -S . -B build_ohos \\\n"
            "  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \\\n"
            "  -DOHOS_ARCH=arm64-v8a \\\n"
            "  -DCMAKE_PREFIX_PATH=%s \\\n"
            "  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH" % installed),
        "qmake": ("LIBS += -L%s/lib %s" % (
            installed, " ".join("-l%s" % l for l in libs))),
        "deploy": "部署 .so 到 entry/libs/arm64-v8a/ 后才能在设备运行",
    }


def _locate_root(target: Path) -> Path:
    """定位安装根：扁平包（cmd-pkgs，lib/include 在 target 下）取 target；
    带顶层目录的包取其下唯一含 lib/include/bin 的子目录。"""
    if any((target / d).is_dir() for d in ("lib", "include", "bin")):
        return target
    cands = [c for c in sorted(target.iterdir()) if c.is_dir() and
             any((c / d).is_dir() for d in ("lib", "include", "bin"))]
    return cands[0] if cands else target


def _extract_tarball(tar_path: Path, target: Path) -> List[str]:
    """解压通用鸿蒙产物 tar.gz 到 target，返回补建的 .so 链接列表。

    先解压到 staging 再原子落位：中途失败（网络外的磁盘/锁错误）不留
    半成品，重跑不会把残缺产物误判为已就绪。NTFS 建不了符号链接：
    包内相对链接改为拷贝目标文件，使 -lfoo 能被交叉链接器解析。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".staging")
    if staging.exists():
        harmonybrew._rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    fixed: List[str] = []
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            pending = []
            for m in tar.getmembers():
                if m.isdir():
                    (staging / m.name).mkdir(parents=True, exist_ok=True)
                elif m.isreg():
                    harmonybrew._extract_with_retry(tar, m, staging)
                elif m.issym():
                    pending.append(m)
            for m in pending:
                link_path = staging / m.name
                src = None
                if not m.linkname.startswith("/"):
                    src = (link_path.parent / m.linkname).resolve()
                if src and src.is_file() and not link_path.exists():
                    shutil.copy2(src, link_path)
                    fixed.append(m.name)
    except Exception:
        harmonybrew._rmtree(staging)
        raise
    if target.exists():       # 覆盖旧产物（可能含 brew 只读文件）
        harmonybrew._rmtree(target)
    staging.rename(target)
    return fixed


def _fetch_generic(node: Dict, out_dir: Path, force: bool) -> Dict:
    """下载非 bottle 域的鸿蒙产物（cmd-pkgs tar.gz 等），解压到
    out/<name>/<version>/。无库内 sha256（cmd-pkgs 源未提供摘要）。"""
    url = node["artifact_url"]
    name = node["name"]
    version = node.get("version") or _ver_from_url(url) or "unknown"
    target = out_dir / name / version
    if target.exists() and any(target.iterdir()) and not force:
        return {"status": "already_local", "artifact_url": url,
                "installed": str(target)}
    cache = out_dir / ".cache"
    cache.mkdir(exist_ok=True)
    tar_path = cache / url.rsplit("/", 1)[-1]
    harmonybrew._download(url, tar_path, node.get("bottle_sha256"))
    fixed = _extract_tarball(tar_path, target)
    tar_path.unlink(missing_ok=True)
    installed = _locate_root(target)
    libs = _list_libs(installed)
    return {"status": "downloaded", "artifact_url": url,
            "sha256": "verified" if node.get("bottle_sha256") else "n/a",
            "installed": str(installed), "libs": libs,
            "symlinks_fixed": fixed[:10], "hints": _hints(installed, libs)}


def _fetch_one(conn, node: Dict, out_dir: Path, force: bool) -> Dict:
    """按产物 URL 域分派下载：bottle 域走 fetch_bottle（sha256 校验），
    其余走通用 tar.gz 提取。失败不抛出，返回 failed 条目。"""
    url = node["artifact_url"]
    try:
        if url.startswith(harmonybrew.BOTTLE_DOMAIN):
            r = harmonybrew.fetch_bottle(conn, node["name"], out_dir,
                                         force=force)
            # 跳过路径（已存在）不含 sha256/libs/hints 键，用 .get
            return {"status": "already_local" if r.get("skipped")
                    else "downloaded",
                    "artifact_url": r["bottle_url"],
                    "sha256": r.get("sha256"),
                    "installed": r["installed"],
                    "libs": r.get("libs"), "hints": r.get("hints")}
        return _fetch_generic(node, out_dir, force)
    except Exception as exc:
        return {"status": "failed", "artifact_url": url, "error": str(exc)}


def _mark_local(conn, name: str, installed: str) -> None:
    """把已就绪产物路径回写同名节点（hb:/cmdpkgs:），供 Web 详情展示。

    已有指向真实存在的路径时保留；指向失效目录（如项目搬迁前的旧
    绝对路径）时用新路径覆盖。
    """
    for nid in ("hb:%s" % name, "cmdpkgs:%s" % name):
        node = db.get_node(conn, nid)
        if node is None:
            continue
        old = node.get("artifact_local")
        if old and Path(old).is_dir():
            continue
        conn.execute("UPDATE nodes SET artifact_local=? WHERE id=?",
                     (installed, nid))
    conn.commit()


def fetch_app_deps(conn, app_id: str, out_dir: Path,
                   force: bool = False, dry_run: bool = False,
                   progress: Optional[Callable[[Dict], None]] = None) -> Dict:
    """下载应用依赖闭包内全部可获取的鸿蒙产物，返回 manifest。

    dry_run=True 只分类不下载不写盘；progress 为每个节点处理完的回调。
    """
    app = db.get_node(conn, app_id)
    if app is None:
        raise ValueError("app node not found: %s" % app_id)
    out_dir = Path(out_dir)
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    nodes = dependency_closure(conn, app_id)

    # 预扫描：同名包任一节点有产物直链即视为可下载（hb/cmdpkgs 跨源互补）
    downloadable = {}
    for n in nodes:
        if n.get("artifact_url"):
            downloadable.setdefault(n["name"].lower(), n)

    entries: List[Dict] = []
    installed_by_name: Dict[str, str] = {}
    for node in nodes:
        name = node["name"]
        art = engine.artifact_info(node)
        entry = {"id": node["id"], "name": name, "kind": node["kind"],
                 "version": node.get("version"),
                 "port_status": node.get("port_status")}
        if node["id"] == app_id:
            entry["status"] = "target"
        elif node["kind"] in PROVIDED_KINDS:
            entry["status"] = "provided"
            entry["note"] = "由 Qt SDK / 鸿蒙框架提供，随 Qt for HarmonyOS 部署"
        elif name.lower() in installed_by_name:
            entry["status"] = "covered"
            entry["installed"] = installed_by_name[name.lower()]
        elif name.lower() in downloadable:
            src = downloadable[name.lower()]
            entry["version"] = src.get("version") or entry["version"]
            if dry_run:
                entry["status"] = "would_download"
                entry["artifact_url"] = src["artifact_url"]
                # 预填目标路径，使同名节点在 dry-run 下也能正确标记 covered
                installed_by_name[name.lower()] = str(
                    out_dir / src["name"] / (src.get("version") or "unknown"))
            else:
                entry.update(_fetch_one(conn, src, out_dir, force))
                if entry.get("installed"):
                    installed_by_name[name.lower()] = entry["installed"]
                    if entry["status"] in ("downloaded", "already_local"):
                        _mark_local(conn, name, entry["installed"])
        elif art.get("artifact_local") and Path(art["artifact_local"]).is_dir():
            entry["status"] = "already_local"
            entry["installed"] = art["artifact_local"]
            installed_by_name[name.lower()] = art["artifact_local"]
        elif art.get("artifact_cmd"):
            entry["status"] = "cmd_only"
            entry["artifact_cmd"] = art["artifact_cmd"]
            entry["note"] = ("无直链（formula 未能解析版本号）："
                             "在鸿蒙设备执行该命令，或补版本号构造 bottle URL")
        else:
            entry["status"] = "need_port"
            entry["source_url"] = art.get("source_url")
            entry["repo_url"] = art.get("repo_url")
            entry["homepage"] = art.get("homepage")
        entries.append(entry)
        if progress:
            progress(entry)

    installed_dirs = sorted({e["installed"] for e in entries
                             if e.get("installed")})
    manifest = {
        "app": {"id": app_id, "name": app["name"]},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "closure_size": len(nodes),
        "summary": dict(Counter(e["status"] for e in entries)),
        "deps": entries,
        "toolchain": {
            "cmake_prefix_path": ";".join(installed_dirs),
            "cmake": (
                "cmake -S . -B build_ohos \\\n"
                "  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \\\n"
                "  -DOHOS_ARCH=arm64-v8a \\\n"
                "  -DCMAKE_PREFIX_PATH=%s \\\n"
                "  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH"
                % ";".join(installed_dirs)),
            "note": "NATIVE_OHOS_SDK 为本机 HarmonyOS SDK native 路径；"
                    "所有 .so 需部署到 entry/libs/arm64-v8a/ 才能在设备运行",
        },
    }
    if not dry_run:
        slug = re.sub(r"[^\w.-]+", "_", app["name"]) or app_id
        mpath = out_dir / ("manifest-%s.json" % slug)
        mpath.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1),
            encoding="utf-8")
        manifest["manifest_path"] = str(mpath)
    return manifest
