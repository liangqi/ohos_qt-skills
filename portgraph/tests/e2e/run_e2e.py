#!/usr/bin/env python3
"""portgraph E2E 依赖对账 harness（真实 GitHub 项目 × README 依赖描述）。

对 corpus.json 中每个真实 Qt 项目执行：
  clone（复用已有克隆）→ 私有 DB 副本（与主库隔离，可并行）→ scan
  → analyze → fetch-deps --dry-run → README/INSTALL 依赖 oracle 提取
  → 直接依赖(depth-1) 对账 → 差异自动归因（构建文件 grep 取证）
  → 人可读报告(.report.md) + agent 可读报告(.report.json)

用法:
    python tests/e2e/run_e2e.py list
    python tests/e2e/run_e2e.py run --project tdesktop [--fresh-db] [--skip-scan] [--no-clone]
    python tests/e2e/run_e2e.py run --all

产物:
    tests/e2e/reports/<app>.report.md     人可读依赖分析报告（中文）
    tests/e2e/reports/<app>.report.json   agent 可读结构化报告
    tests/e2e/oracle/<app>.json           依赖 oracle（首次运行自动提取；
                                          agent 复核修正后置 reviewed=true）
    tests/e2e/overrides/<app>.json        归因修正规则（agent 编辑后重跑生效）
    workspace/e2e/db/<app>.sqlite         私有 DB 副本（gitignore 区）

差异归因类（by_design=true 为预期行为，不计 bug）:
    matched / matched-optional      oracle 与 portgraph 一致
    missed-dep           ★ bug候选  README 声明且构建文件引用，portgraph 未检出
    resolution-gap       ★ bug候选  扫描出 pkg-unknown 幽灵节点，且库里其实
                                    存在同库异名的已知鸿蒙包（真解析缺口）
    false-positive       ★ bug候选  portgraph 检出但构建文件无引用
    readme-stale                    README 声明但构建文件不引用（README 过时）
    readme-omitted                  构建文件引用但 README 未列（portgraph 正确）
    qt-granularity                  Qt/KF 模块粒度折叠（README 只写 "Qt"）
    build-only                      构建工具（fetch-deps 不收 build 依赖）
    optional-not-built              可选依赖，默认构建不含
    vendored                        README 声明但为 .gitmodules 自带子模块
                                    （随项目编译，不作为外部包获取）
    unknown-ok                      幽灵节点无任何形近已知包：真实外部依赖、
                                    无鸿蒙包，need_port 为正确结论
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from port_graph import (DB_PATH, WORKSPACE, cloner, db, deps_fetch,  # noqa: E402
                        engine, kb_seed, project_scanner, qt_scanner)

E2E_DIR = Path(__file__).resolve().parent
ORACLE_DIR = E2E_DIR / "oracle"
OVERRIDES_DIR = E2E_DIR / "overrides"
REPORTS_DIR = E2E_DIR / "reports"
CORPUS_FILE = E2E_DIR / "corpus.json"
E2E_DB_DIR = WORKSPACE / "e2e" / "db"
DRYRUN_OUT = WORKSPACE / "e2e" / "ohos-libs-dryrun"

BUG_CLASSES = {"missed-dep", "resolution-gap", "false-positive"}
BY_DESIGN_CLASSES = {"matched", "matched-optional", "readme-stale",
                     "readme-omitted", "qt-granularity", "build-only",
                     "optional-not-built", "unknown-ok", "vendored",
                     "unclassified"}

# ---------------------------------------------------------------- 常量表

# README 依赖段标题提示词（小写子串匹配）
SECTION_HINTS = ("dependenc", "requirement", "依赖", "prerequisite",
                 "third-party", "third party", "third‑party", "libraries",
                 "构建所需", "需要安装")

# 构建工具/测试框架（目标侧不需要，fetch-deps 口径不收）
BUILD_TOOLS = {
    "cmake", "ninja", "ninja-build", "make", "gmake", "gcc", "g++", "clang",
    "clang++", "llvm", "lld", "python", "python3", "python2", "perl", "ruby",
    "node", "nodejs", "git", "subversion", "svn", "pkg-config", "pkgconf",
    "autoconf", "automake", "libtool", "m4", "nasm", "yasm", "patch", "flex",
    "bison", "gperf", "extra-cmake-modules", "ecm", "doxygen", "graphviz",
    "sphinx", "meson", "qt-tools", "qtbase-dev", "lrelease", "moc",
    "gettext", "po4a", "appstream", "desktop-file-utils", "shared-mime-info",
    "gtest", "googletest", "gmock", "catch2", "catch", "libunity", "mock",
}

# README 侧名字别名 → 规范名（与 kb_seed.ALIASES 互补，方向相反）
README_ALIASES = {
    "qt": "qt", "qt5": "qt", "qt6": "qt", "qtbase": "qt", "qt-base": "qt",
    "qt5-base": "qt", "qt6-base": "qt", "qt-framework": "qt",
    "kf5": "kf", "kf6": "kf", "kf": "kf", "kde-frameworks": "kf",
    "kde-framework": "kf",
    "libssl": "openssl", "libcrypto": "openssl", "openssl-dev": "openssl",
    "libssl-dev": "openssl", "openssl-3": "openssl",
    "boost-libs": "boost", "boost-libraries": "boost", "libboost": "boost",
    "boost-dev": "boost",
    "zlib1g": "zlib", "zlib1g-dev": "zlib", "zlib-dev": "zlib",
    "libz": "zlib",
    "libtorrent": "libtorrent-rasterbar",
    "taglib-dev": "taglib", "libtag": "taglib",
    "libbotan": "botan", "botan-2": "botan", "botan-3": "botan",
    "libsodium-dev": "libsodium", "libgcrypt": "libgcrypt",
    "libxkb": "libxkbcommon", "xkbcommon": "libxkbcommon",
    "qt5-webengine": "qt", "qt6-webengine": "qt",
    "qt5-quickcontrols2": "qt", "qt6-quickcontrols2": "qt",
    # 同库异名（e2e tdesktop 复核确认）：nayuki QR-Code-generator
    # = cmd-pkgs libqrcodegen（版本序列同源，1.8.0）
    "qr-code-generator": "libqrcodegen",
}

_VERSION_TOK_RE = re.compile(r"^[\d<>=~^]|^v?\d+(\.\d+)*\+?$")
_STOP_WORDS = {"and", "or", "with", "higher", "later", "newer", "above",
               "greater", "以上", "及以上", "or", "newer.", "later."}


# ---------------------------------------------------------------- 工具

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_corpus() -> List[Dict]:
    data = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
    return data["projects"]


def fresh_db_copy(dst: Path) -> None:
    """用 sqlite3 backup API 把主库复制为项目私有 DB（WAL 安全）。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    src = sqlite3.connect(str(DB_PATH))
    out = sqlite3.connect(str(dst))
    with out:
        src.backup(out)
    src.close()
    out.close()


def norm_name(s: str) -> str:
    """依赖名规范化：小写、去 markdown 修饰、去版本 token、分隔符统一。"""
    s = s.strip().lower()
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("`", "").replace("**", "").replace("*", "")
    toks = []
    for t in s.split():
        tl = t.strip("()[]{}:;,.")
        if not tl:
            continue
        if _VERSION_TOK_RE.match(tl):
            break
        if tl in _STOP_WORDS:
            break
        toks.append(tl)
        if len(toks) >= 4:
            break
    s = " ".join(toks)
    s = re.sub(r"[^a-z0-9@+]+", "-", s).strip("-")
    return s


def canon_of(s: str) -> str:
    """进一步折叠：别名表 + @变体剥离。"""
    n = norm_name(s)
    n = README_ALIASES.get(n, n)
    if "@" in n and not n.startswith("openssl@"):
        n = n.split("@", 1)[0]
    return n


def pg_canon(node: Dict) -> str:
    """portgraph 依赖节点 → 规范名（qt-module 折叠为 qt，KF 折叠为 kf）。

    分隔符归一与 oracle 侧 norm_name 对齐（_ / 空格 → -）：否则
    json_schema_validator（require_dep 下划线名）永远匹配不上
    oracle 的 json-schema-validator，两侧对称归一后才可比。"""
    if node["kind"] == "qt-module":
        return "qt"
    if node["kind"] == "framework":
        return "kf"
    name = (node["name"] or "").lower()
    if "@" in name and not name.startswith("openssl@"):
        name = name.split("@", 1)[0]
    name = re.sub(r"[^a-z0-9@+]+", "-", name).strip("-")
    return name or node["id"].split(":", 1)[-1].lower()


def names_match(oracle_name: str, pg_name: str, pg_node: Dict) -> bool:
    """oracle 名 ↔ portgraph 节点名匹配（精确 → 别名 → kb_seed.ALIASES → 包含）。"""
    oc = canon_of(oracle_name)
    pc = pg_canon(pg_node)
    if not oc or not pc:
        return False
    if oc == pc:
        return True
    # kb_seed.ALIASES: openssl → [openssl@3, openssl]
    for cand in kb_seed.ALIASES.get(oc, []):
        if cand == pc or cand == (pg_node["name"] or "").lower():
            return True
    if len(oc) >= 5 and len(pc) >= 5 and (oc in pc or pc in oc):
        return True
    return False


def _fold_pkg_name(n: str) -> str:
    """包名折叠：小写、去 @变体、去 lib 前缀、分隔符归一。"""
    n = (n or "").lower().strip()
    at = n.find("@")
    if at > 0:
        n = n[:at]
    if n.startswith("lib") and len(n) > 3:
        n = n[3:]
    return n.replace("_", "-").strip("-")


def ghost_plausible_package(conn, ghost_name: str) -> Optional[Dict]:
    """幽灵节点名是否存在"本应解析到"的已知鸿蒙包。

    判据（任一命中即存在）：
    - kb_seed.PKG_ALIASES 指向的目标包在库里存在
    - 已入库 hb/cmd-pkgs 包名折叠后相等，或互为子串且共享完整分隔分量
      （openal ⊂ openal-soft；udev ⊄ uudeview——无分量交集）
    返回 {id, name} 或 None。None → 幽灵是正确检出（unknown-ok）。
    """
    raw = (ghost_name or "").strip()
    g = _fold_pkg_name(raw)
    if not g or len(g) < 3:
        return None
    alias = kb_seed.PKG_ALIASES.get(raw.lower())
    if isinstance(alias, str):
        node = kb_seed.resolve_package(conn, alias)
        if node:
            return {"id": node["id"], "name": node["name"]}
    g_parts = set(p for p in g.split("-") if p)
    try:
        rows = conn.execute(
            "SELECT id, name FROM nodes WHERE kind='package' "
            "AND (id LIKE 'hb:%' OR id LIKE 'cmdpkgs:%')").fetchall()
    except sqlite3.Error:
        return None
    for r in rows:
        p = _fold_pkg_name(r["name"] or "")
        if not p:
            continue
        if p == g:
            return {"id": r["id"], "name": r["name"]}
        p_parts = set(x for x in p.split("-") if x)
        if (g in p or p in g) and (g_parts & p_parts):
            return {"id": r["id"], "name": r["name"]}
    return None


# ---------------------------------------------------------------- oracle 提取

def _parse_oracle_dep(raw: str) -> Optional[Dict]:
    """单条 README 依赖文本 → {name, type, raw}；无法解析返回 None。"""
    s = raw.strip()
    if not s or len(s) > 120:
        return None
    s_disp = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)   # 保留原文展示
    low = s.lower()
    typ = "runtime"
    if ("optional" in low or "可选" in low or "if available" in low
            or "not required" in low):
        typ = "optional"
    if (("(build" in low and ")" in low) or "build only" in low
            or "构建" in low or "编译" in low or "compile" in low
            or "toolchain" in low):
        typ = "build"
    name = norm_name(s)
    if not name or len(name) > 60:
        return None
    if canon_of(name) in BUILD_TOOLS or name in BUILD_TOOLS:
        typ = "build"
    if typ == "runtime" and name in BUILD_TOOLS:
        typ = "build"
    # 多词散文行（4 token 且以句号结尾）丢弃
    if s.endswith(".") and len(s.split()) > 6:
        return None
    return {"name": name, "display": s_disp.strip(), "type": typ, "raw": s}


def extract_oracle_from_doc(text: str) -> List[Dict]:
    """从 README/INSTALL 文本提取依赖段条目（bullet/编号/表格行）。"""
    lines = text.splitlines()
    deps: List[Dict] = []
    seen = set()
    level = None
    in_sec = False
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl, title = len(m.group(1)), m.group(2).lower()
            if any(h in title for h in SECTION_HINTS):
                in_sec, level = True, lvl
                continue
            if in_sec and lvl <= (level or 9):
                in_sec = False
            continue
        if not in_sec:
            continue
        item = None
        mb = re.match(r"^\s*[-*+•]\s+(.+)$", ln)
        mn = re.match(r"^\s*\d+[.)]\s+(.+)$", ln)
        mt = re.match(r"^\s*\|(.+)\|\s*$", ln)
        if mb:
            item = mb.group(1)
        elif mn:
            item = mn.group(1)
        elif mt:
            cells = [c.strip() for c in mt.group(1).split("|")]
            if all(re.match(r"^[-: ]*$", c) for c in cells if c):
                continue
            item = next((c for c in cells if c), None)
        if not item:
            continue
        d = _parse_oracle_dep(item)
        if d and d["name"] not in seen:
            seen.add(d["name"])
            deps.append(d)
    return deps


def load_oracle(proj: Dict, repo_path: Path) -> Dict:
    """加载 oracle：人工复核文件优先，否则自动提取并落盘（reviewed=false）。"""
    app = proj["name"]
    of = ORACLE_DIR / ("%s.json" % app)
    if of.exists():
        data = json.loads(of.read_text(encoding="utf-8"))
        data.setdefault("app", app)
        data.setdefault("reviewed", False)
        return data
    extracted: List[Dict] = []
    source = None
    for fname in proj.get("oracle_files", ["README.md"]):
        f = repo_path / fname
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        got = extract_oracle_from_doc(text)
        if got:
            source, extracted = fname, got
            break
    data = {"app": app, "source": source,
            "source_note": "自动提取（heuristic），待 agent 复核" if source
            else "未找到依赖段，待 agent 手工编写",
            "reviewed": False, "deps": extracted}
    ORACLE_DIR.mkdir(parents=True, exist_ok=True)
    of.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                  encoding="utf-8")
    return data


# ---------------------------------------------------------------- 构建文件取证

BUILD_FILE_NAMES = {"CMakeLists.txt", "meson.build", "vcpkg.json",
                    "conanfile.py", "conanfile.txt", "configure.ac"}
BUILD_FILE_SUFFIXES = (".cmake", ".pro", ".pri", ".prf")
LOOSE_ONLY_NAMES = {"vcpkg.json", "conanfile.py", "conanfile.txt"}
LOOSE_ONLY_SUFFIXES = (".pro", ".pri")
SKIP_DIRS = {".git", "node_modules"}


def _collect_build_files(repo: Path, max_files: int = 4000) -> List[Path]:
    out: List[Path] = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if (fn in BUILD_FILE_NAMES or fn.endswith(BUILD_FILE_SUFFIXES)
                    or fn.endswith(".cmake")):
                out.append(Path(root) / fn)
                if len(out) >= max_files:
                    return out
    return out


def _word_guard(e: str) -> str:
    """词界保护：字母数字之外均算边界（_:.-@ 等分隔符也算）。

    \b 无法命中 external_openal / lib_zlib / ns::openal 这类下划线/
    冒号连写形式（e2e tdesktop 复核：external_* 前缀目标名曾被漏判），
    改用环视断言实现分隔符敏感的边界。
    """
    return r"(?<![A-Za-z0-9])" + e + r"(?![A-Za-z0-9])"


def grep_dep_refs(repo: Path, name_variants: List[str],
                  max_hits: int = 5) -> Dict:
    """在克隆仓库构建文件中搜索依赖引用，返回强/弱证据。

    强证据：find_package/pkg_check_modules/find_library/target_link_libraries
    弱证据：vcpkg/conan/qmake 文件中的裸名出现
    """
    variants = []
    for v in name_variants:
        if v and len(v) >= 3 and v not in variants:
            variants.append(v)
    if not variants:
        return {"strong": 0, "weak": 0, "hits": []}
    strict, loose = [], []
    for v in variants:
        e = re.escape(v)
        b = _word_guard(e)
        strict.append(re.compile(r"(?i)find_package\s*\(\s*%s" % b))
        strict.append(re.compile(r"(?i)pkg_check_modules\s*\([^)]*%s" % b))
        strict.append(re.compile(r"(?i)find_library\s*\([^)]*%s" % b))
        strict.append(re.compile(r"(?is)target_link_libraries\s*\([^)]*?%s"
                                 % b))
        loose.append(re.compile(r"(?i)%s" % b))
    hits: List[Dict] = []
    n_strong = n_weak = 0
    try:
        files = _collect_build_files(repo)
    except OSError:
        files = []
    for f in files:
        is_loose_only = (f.name in LOOSE_ONLY_NAMES
                         or f.name.endswith(LOOSE_ONLY_SUFFIXES))
        try:
            if f.stat().st_size > 2_000_000:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(repo)).replace("\\", "/")
        # 强证据：全文本匹配（CMake 命令常跨多行——tdesktop 的
        # target_link_libraries 每个链接项独占一行，逐行匹配会漏证据）
        for pat in strict:
            for m in pat.finditer(text):
                n_strong += 1
                line_no = text.count("\n", 0, m.end()) + 1
                if len(hits) < max_hits:
                    snippet = text[m.start():m.end()]
                    snippet = snippet[snippet.rfind("\n") + 1:][:120]
                    hits.append({"file": rel, "line": line_no,
                                 "strong": True, "text": snippet})
        if is_loose_only:
            for i, line in enumerate(text.splitlines(), 1):
                if any(p.search(line) for p in loose):
                    n_weak += 1
                    if len(hits) < max_hits and not any(
                            h["file"] == rel and h["line"] == i
                            for h in hits):
                        hits.append({"file": rel, "line": i, "strong": False,
                                     "text": line.strip()[:120]})
    return {"strong": n_strong, "weak": n_weak, "hits": hits}


def name_variants(disp_or_name: str, node: Optional[Dict] = None) -> List[str]:
    """oracle 原文名 / pg 节点名 → grep 变体列表。"""
    out = []
    raw = (disp_or_name or "").strip()
    if raw:
        out.append(raw)
        out.append(raw.lower())
    n = norm_name(raw) if raw else ""
    if n:
        out.append(n)
        out.append(n.replace("-", ""))
    if node is not None:
        nm = (node["name"] or "").strip()
        if nm:
            out.append(nm)
            out.append(nm.lower())
        # 节点名含 @version（openssl@3）时追加剥离变体：否则 grep 不到
        # find_package(OpenSSL) 这类原始声明（e2e qbittorrent 复盘确认）
        if "@" in nm:
            out.append(nm.split("@", 1)[0])
        nid = node["id"]
        if ":" in nid:
            tail = nid.split(":", 1)[1]
            out.append(tail)
            if "@" in tail:
                out.append(tail.split("@", 1)[0])
        # 反向别名：构建文件里用的是别名形态（find_package(X11) /
        # pkg_check_modules(xkbcommon)），而扫描期已归并到目标包节点
        # （libx11 / libxkbcommon）——把别名原名也加入 grep 变体
        node_nm = (node["name"] or "").lower()
        for alias_key, alias_target in kb_seed.PKG_ALIASES.items():
            if alias_target.lower() == node_nm:
                out.append(alias_key)
    return list(dict.fromkeys(v for v in out if v and len(v) >= 3))


def vendored_submodule_match(repo_path: Path,
                             oracle_names: List[str]) -> Optional[Dict]:
    """oracle 依赖名（name/display 均尝试）是否是 .gitmodules 自带子模块
    （vendored，随项目编译）。

    匹配：折叠名（去分隔符/大小写）与子模块 name/path 末段/url 末段相等，
    或互为子串（≥5 字符）。返回 {path, url} 或 None。
    """
    try:
        submodules = qt_scanner._detect_gitmodules(repo_path)
    except OSError:
        return None
    if not submodules:
        return None

    def fold(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

    wants = []
    for nm in oracle_names:
        w = fold(canon_of(nm))
        if w and len(w) >= 3 and w not in wants:
            wants.append(w)
    if not wants:
        return None
    for gm in submodules:
        url = (gm.get("url") or "").rstrip("/")
        url_last = url.rsplit("/", 1)[-1]
        if url_last.endswith(".git"):
            url_last = url_last[:-4]
        cands = [gm.get("name") or "",
                 (gm.get("path") or "").rsplit("/", 1)[-1],
                 url_last]
        for c in cands:
            f = fold(c)
            if not f or len(f) < 3:
                continue
            for want in wants:
                if f == want or (len(want) >= 5 and
                                 (want in f or f in want)):
                    return {"path": gm.get("path"), "url": gm.get("url")}
    return None


# ---------------------------------------------------------------- 主流程

def bfs_depths(conn, app_id: str) -> Dict[str, int]:
    depths = {app_id: 0}
    queue = [app_id]
    while queue:
        nid = queue.pop(0)
        for e in db.out_edges(conn, nid, ("runtime", "uses-module")):
            if e.get("platform_cond") in ("macos",):
                continue
            if e["dst"] not in depths:
                depths[e["dst"]] = depths[nid] + 1
                queue.append(e["dst"])
    return depths


def run_project(proj: Dict, args) -> Dict:
    app_key = proj["name"]
    print("[e2e] ==== %s (tier %s) ====" % (app_key, proj.get("tier", "?")))

    # 1. clone（复用已有克隆）
    if args.no_clone:
        repo_path = WORKSPACE / app_key
    else:
        info = cloner.clone_repo(proj["url"], app_key)
        repo_path = Path(info["path"])
        print("[e2e] clone: %s (%s)" % (
            repo_path, "已存在复用" if not info["cloned"] else "新克隆"))

    # 2. 私有 DB 副本
    db_file = E2E_DB_DIR / ("%s.sqlite" % app_key)
    if args.fresh_db or not db_file.exists():
        fresh_db_copy(db_file)
        print("[e2e] 私有 DB: %s (从主库新复制)" % db_file.name)
    conn = db.connect(db_file)

    try:
        # 3. scan
        if args.skip_scan:
            row = conn.execute(
                "SELECT id FROM nodes WHERE kind='app' AND id LIKE ?",
                ("app:%" + app_key.lower() + "%",)).fetchone()
            if not row:
                print("[e2e] --skip-scan 但私有 DB 无该 app，回退扫描")
                args.skip_scan = False
            else:
                app_id = row["id"]
                scan = {"app_id": app_id, "name": app_key,
                        "build_system": "?", "sources": "?"}
        if not args.skip_scan:
            print("[e2e] scanning %s ..." % repo_path.name)
            scan = project_scanner.scan_project(conn, repo_path)
            app_id = scan["app_id"]
            print("[e2e] scan: app_id=%s build=%s sources=%s "
                  "qt_modules=%d deps_linked=%d deps_unknown=%d" % (
                      app_id, scan["build_system"], scan["sources"],
                      len(scan["modules_linked"]), len(scan["deps_linked"]),
                      len(scan["deps_unknown"])))

        # 4. analyze
        analysis = engine.analyze(conn, app_id)
        print("[e2e] analyze: verdict=%s blockers=%d unknowns=%d" % (
            analysis["verdict"], len(analysis["blockers"]),
            len(analysis["unknowns"])))

        # 5. fetch-deps dry-run（不下载不写盘）
        manifest = deps_fetch.fetch_app_deps(conn, app_id, DRYRUN_OUT,
                                             dry_run=True)
        print("[e2e] fetch-deps(dry-run): closure=%d %s" % (
            manifest["closure_size"],
            " ".join("%s=%d" % kv for kv in sorted(
                manifest["summary"].items()))))

        # 6. 直接依赖 + 闭包深度
        depths = bfs_depths(conn, app_id)
        direct = []
        for e in db.out_edges(conn, app_id, ("runtime", "uses-module")):
            if e.get("platform_cond") in ("macos",):
                continue
            nd = db.get_node(conn, e["dst"])
            if nd is None:
                continue
            direct.append({"id": nd["id"], "name": nd["name"],
                           "kind": nd["kind"], "edge": e["type"],
                           "port_status": nd["port_status"],
                           "depth": depths.get(e["dst"], -1)})
        direct.sort(key=lambda d: (d["kind"], d["name"].lower()))

        # 7. oracle
        oracle = load_oracle(proj, repo_path)
        print("[e2e] oracle: source=%s reviewed=%s deps=%d" % (
            oracle.get("source"), oracle.get("reviewed"),
            len(oracle.get("deps", []))))

        # 8. 对账 + 归因
        diffs, matched_pg_ids = reconcile(conn, oracle, direct, repo_path,
                                          manifest, app_id)

        # 9. overrides
        notes = []
        ov_file = OVERRIDES_DIR / ("%s.json" % app_key)
        if ov_file.exists():
            ov = json.loads(ov_file.read_text(encoding="utf-8"))
            notes = apply_overrides(diffs, ov)

        # 10. 指标
        metrics = compute_metrics(oracle, diffs)

        # 11. 报告
        result = assemble_result(proj, app_id, scan, analysis, manifest,
                                 direct, oracle, diffs, metrics, notes,
                                 repo_path)
        write_reports(result, diffs)
        print("[e2e] %s 指标: recall=%s precision=%s bug_candidates=%d" % (
            app_key, metrics["recall"], metrics["precision"],
            metrics["bug_candidates"]))
        for d in diffs:
            if d["class"] in BUG_CLASSES:
                note = d.get("agent_note") or (
                    d["evidence"]["note"] if d.get("evidence") else "")
                print("      ★ [%s] %s ← %s" % (
                    d["class"], d.get("oracle_name") or d.get("pg_name"),
                    note))
        print("[e2e] 报告: %s / %s" % (
            REPORTS_DIR / ("%s.report.md" % app_key),
            REPORTS_DIR / ("%s.report.json" % app_key)))
        return result
    finally:
        conn.close()


def reconcile(conn, oracle: Dict, direct: List[Dict], repo_path: Path,
              manifest: Dict, app_id: str) -> tuple:
    """对账主体：oracle × 直接依赖 → 归因差异列表 + 已匹配 pg 节点 id 集合。"""
    diffs: List[Dict] = []
    matched_pg_ids: set = set()
    odeps = oracle.get("deps", [])

    # --- pass 1: oracle 条目 ---
    for o in odeps:
        odisp = o.get("display") or o.get("name")
        hit = next((d for d in direct
                    if d["id"] not in matched_pg_ids
                    and names_match(odisp, d["name"], d)), None)
        if hit:
            matched_pg_ids.add(hit["id"])
            cls = ("matched-optional" if o.get("type") == "optional"
                   else "matched")
            ev = None
            if hit["id"].startswith("pkg-unknown:"):
                cand = ghost_plausible_package(conn, hit["name"])
                ev = ({"note": "⚠ 匹配到幽灵节点：库里存在形近已知包 %s（%s）"
                       "→ 名字解析缺口，需复核" % (cand["name"], cand["id"])}
                      if cand else
                      {"note": "匹配到幽灵节点：真实外部依赖且无已知鸿蒙包"
                       "（fetch-deps 报 need_port/需源码移植，检出正确）"})
            diffs.append({"class": cls, "side": "oracle", "by_design": True,
                          "oracle_name": o.get("name"),
                          "oracle_type": o.get("type"),
                          "pg_id": hit["id"], "pg_name": hit["name"],
                          "pg_kind": hit["kind"], "pg_status": hit["port_status"],
                          "depth": hit["depth"], "evidence": ev,
                          "agent_note": None})
            continue
        if o.get("type") == "build":
            diffs.append({"class": "build-only", "side": "oracle",
                          "by_design": True, "oracle_name": o.get("name"),
                          "oracle_type": "build", "pg_id": None,
                          "pg_name": None, "pg_kind": None, "pg_status": None,
                          "depth": None,
                          "evidence": {"note": "构建工具，fetch-deps 不收 build 边"},
                          "agent_note": None})
            continue
        if o.get("type") == "optional":
            diffs.append({"class": "optional-not-built", "side": "oracle",
                          "by_design": True, "oracle_name": o.get("name"),
                          "oracle_type": "optional", "pg_id": None,
                          "pg_name": None, "pg_kind": None, "pg_status": None,
                          "depth": None,
                          "evidence": {"note": "可选依赖，默认构建未启用"},
                          "agent_note": None})
            continue
        # runtime 且未匹配 → 取证：是否 vendored 子模块（随项目编译，
        # 不作为外部包获取），否则构建文件是否引用
        vend = vendored_submodule_match(
            repo_path, [odisp, o.get("name") or ""])
        if vend:
            diffs.append({"class": "vendored", "side": "oracle",
                          "by_design": True, "oracle_name": o.get("name"),
                          "oracle_type": "runtime", "pg_id": None,
                          "pg_name": None, "pg_kind": None,
                          "pg_status": None, "depth": None,
                          "evidence": {"note": " .gitmodules 自带子模块"
                            "（%s → %s）：随项目源码一起编译，不作为外部包"
                            "获取/检测" % (vend["path"], vend["url"])},
                          "agent_note": None})
            continue
        ev = grep_dep_refs(repo_path, name_variants(odisp))
        if ev["strong"] or ev["weak"]:
            cls, note = "missed-dep", (
                "README 声明且构建文件引用（strong=%d weak=%d），"
                "portgraph 未检出 → 扫描器漏检候选"
                % (ev["strong"], ev["weak"]))
        else:
            cls, note = "readme-stale", (
                "README 声明但构建文件无引用 → 疑似 README 过时/笔误")
        diffs.append({"class": cls, "side": "oracle",
                      "by_design": cls not in BUG_CLASSES,
                      "oracle_name": o.get("name"), "oracle_type": "runtime",
                      "pg_id": None, "pg_name": None, "pg_kind": None,
                      "pg_status": None, "depth": None,
                      "evidence": {"note": note, "grep": ev["hits"]},
                      "agent_note": None})

    # --- pass 2: portgraph 直接依赖 ---
    for d in direct:
        if d["id"] in matched_pg_ids:
            continue
        base = {"class": "", "side": "pg", "by_design": True,
                "oracle_name": None, "oracle_type": None,
                "pg_id": d["id"], "pg_name": d["name"], "pg_kind": d["kind"],
                "pg_status": d["port_status"], "depth": d["depth"],
                "evidence": None, "agent_note": None}
        if d["kind"] == "qt-module":
            base["class"] = "qt-granularity"
            base["evidence"] = {"note": "Qt 模块粒度：README 通常只写 'Qt'"}
            diffs.append(base)
            continue
        if d["kind"] == "framework":
            base["class"] = "qt-granularity"
            base["evidence"] = {"note": "KDE Frameworks 组件粒度："
                              "README 通常只写 'KDE Frameworks'"}
            diffs.append(base)
            continue
        if d["id"].startswith("pkg-unknown:"):
            cand = ghost_plausible_package(conn, d["name"])
            if cand:
                base["class"] = "resolution-gap"
                base["by_design"] = False
                base["evidence"] = {"note": "pkg-unknown 幽灵节点："
                                  "库里存在同库异名的已知鸿蒙包 %s（%s）→ "
                                  "名字解析缺口（ALIASES 缺条目）"
                                  % (cand["name"], cand["id"])}
            else:
                base["class"] = "unknown-ok"
                base["evidence"] = {"note": "未匹配到已知鸿蒙包：真实外部"
                                  "依赖，幽灵节点为正确检出"
                                  "（fetch-deps 报 need_port/需源码移植）"}
            diffs.append(base)
            continue
        ev = grep_dep_refs(repo_path, name_variants(None, d))
        if ev["strong"] or ev["weak"]:
            base["class"] = "readme-omitted"
            base["evidence"] = {"note": "构建文件引用但 README 未列 → "
                                "README 不完整（portgraph 正确）",
                                "grep": ev["hits"]}
        else:
            base["class"] = "false-positive"
            base["by_design"] = False
            base["evidence"] = {"note": "portgraph 检出但构建文件无引用 → "
                                "扫描误报候选（include 启发式/名字巧合）",
                                "grep": ev["hits"]}
        diffs.append(base)
    return diffs, matched_pg_ids


def apply_overrides(diffs: List[Dict], ov: Dict) -> List[str]:
    for rule in ov.get("reclassify", []):
        for d in diffs:
            if rule.get("dep") is not None:
                if d.get("pg_id") != rule["dep"] and (
                        (d.get("pg_name") or "").lower() != rule["dep"].lower()):
                    continue
            if rule.get("oracle") is not None:
                if (d.get("oracle_name") or "").lower() != rule["oracle"].lower():
                    continue
            if rule.get("from") and d["class"] != rule["from"]:
                continue
            d["class"] = rule["to"]
            d["by_design"] = rule["to"] not in BUG_CLASSES
            d["agent_note"] = rule.get("reason", "")
    return ov.get("notes", [])


def compute_metrics(oracle: Dict, diffs: List[Dict]) -> Dict:
    odeps = oracle.get("deps", [])
    o_runtime = [d for d in odeps if d.get("type") == "runtime"]
    o_optional = [d for d in odeps if d.get("type") == "optional"]
    matched = [d for d in diffs if d["class"] == "matched"]
    matched_opt = [d for d in diffs if d["class"] == "matched-optional"]
    pg_eff = [d for d in diffs if d["side"] == "pg"
              and d["class"] in ("readme-omitted", "false-positive")] + \
             [d for d in diffs if d["side"] == "oracle"
              and d["class"] in ("matched", "matched-optional")]
    pg_match = [d for d in diffs if d["class"] in ("matched",
                                                   "matched-optional")]
    bug = [d for d in diffs if d["class"] in BUG_CLASSES]
    recall = ("%.0f%%" % (100.0 * len(matched) / len(o_runtime))
              if o_runtime else "n/a")
    precision = ("%.0f%%" % (100.0 * len(pg_match) / len(pg_eff))
                 if pg_eff else "n/a")
    return {
        "oracle_runtime": len(o_runtime), "oracle_optional": len(o_optional),
        "matched": len(matched), "matched_optional": len(matched_opt),
        "recall": recall, "precision": precision,
        "bug_candidates": len(bug),
        "bug_by_class": {c: sum(1 for d in bug if d["class"] == c)
                         for c in sorted(BUG_CLASSES)},
        "class_counts": {c: sum(1 for d in diffs if d["class"] == c)
                         for c in sorted({d["class"] for d in diffs})},
    }


# ---------------------------------------------------------------- 报告

def assemble_result(proj, app_id, scan, analysis, manifest, direct, oracle,
                    diffs, metrics, notes, repo_path) -> Dict:
    return {
        "schema": "portgraph-e2e-report/1",
        "app": {"key": proj["name"], "app_id": app_id,
                "name": scan.get("name"), "url": proj["url"],
                "tier": proj.get("tier"),
                "build_system": scan.get("build_system"),
                "sources": scan.get("sources"),
                "repo_path": str(repo_path)},
        "generated_at": now_iso(),
        "verdict": analysis["verdict"],
        "blockers": [{"kind": b["kind"], "node": b["node"],
                      "reason": b["reason"]} for b in analysis["blockers"]],
        "unknowns": [{"kind": u["kind"], "node": u["node"],
                      "reason": u["reason"]} for u in analysis["unknowns"]],
        "platform_excluded": analysis.get("platform_excluded", []),
        "closure": {
            "size": manifest["closure_size"],
            "summary": manifest["summary"],
            "need_port": [{"id": e["id"], "name": e["name"],
                           "version": e.get("version"),
                           "source_url": e.get("source_url"),
                           "repo_url": e.get("repo_url")}
                          for e in manifest["deps"]
                          if e["status"] == "need_port"],
            "cmd_only": [{"id": e["id"], "name": e["name"],
                          "artifact_cmd": e.get("artifact_cmd")}
                         for e in manifest["deps"]
                         if e["status"] == "cmd_only"],
            "would_download": [e["name"] for e in manifest["deps"]
                               if e["status"] == "would_download"],
        },
        "direct_deps": direct,
        "oracle": oracle,
        "diffs": diffs,
        "metrics": metrics,
        "agent_notes": notes,
    }


_CLASS_LABEL = {
    "matched": "一致", "matched-optional": "一致(可选)",
    "missed-dep": "★漏检", "resolution-gap": "★解析缺口",
    "false-positive": "★误报", "readme-stale": "README过时",
    "readme-omitted": "README漏列", "qt-granularity": "粒度折叠",
    "build-only": "构建工具", "optional-not-built": "可选未启用",
    "unknown-ok": "未知包(正常)", "vendored": "自带子模块",
    "unclassified": "未归类",
}


def _md_escape(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_md_report(r: Dict, path: Path) -> None:
    m = r["metrics"]
    lines: List[str] = []
    a = lines.append
    a("# %s 依赖对账报告（portgraph E2E）" % r["app"]["name"])
    a("")
    a("> 生成时间: %s | 语料: corpus.json#%s | 构建系统: %s | 源文件: %s"
      % (r["generated_at"], r["app"]["key"], r["app"]["build_system"],
         r["app"]["sources"]))
    a("> Oracle: %s（复核: %s，%d 条；来源: %s）" % (
        r["oracle"].get("source") or "无",
        "已复核" if r["oracle"].get("reviewed") else "**未复核**",
        len(r["oracle"].get("deps", [])),
        r["oracle"].get("source_note", "")))
    a("")
    a("## 1. 结论速览")
    a("")
    a("| 指标 | 值 |")
    a("|---|---|")
    a("| 可移植性 verdict | **%s**（阻塞 %d / 未知 %d / 平台排除 %d） |" % (
        r["verdict"], len(r["blockers"]), len(r["unknowns"]),
        len(r["platform_excluded"])))
    a("| 检出召回率 | %s（%d/%d README 运行时依赖） |" % (
        m["recall"], m["matched"], m["oracle_runtime"]))
    a("| 检出精确率 | %s |" % m["precision"])
    a("| Bug 候选 | **%d**（%s） |" % (
        m["bug_candidates"],
        ", ".join("%s=%d" % kv for kv in m["bug_by_class"].items()
                  if kv[1]) or "无"))
    a("| 依赖闭包 | %d 项（%s） |" % (
        r["closure"]["size"],
        ", ".join("%s %d" % kv for kv in
                  sorted(r["closure"]["summary"].items()))))
    a("")
    if r["agent_notes"]:
        a("**Agent 复核说明**：")
        a("")
        for n in r["agent_notes"]:
            a("- %s" % n)
        a("")
    a("## 2. 可移植性判定（analyze）")
    a("")
    if r["blockers"]:
        a("| 阻塞类型 | 节点 | 原因 |")
        a("|---|---|---|")
        for b in r["blockers"][:30]:
            a("| %s | %s | %s |" % (_md_escape(b["kind"]),
                                    _md_escape(b["node"]),
                                    _md_escape(b["reason"])[:160]))
    else:
        a("（无硬阻塞）")
    if r["unknowns"]:
        a("")
        a("未确认项 %d 个：" % len(r["unknowns"]))
        for u in r["unknowns"][:15]:
            a("- [%s] %s: %s" % (u["kind"], u["node"], u["reason"][:120]))
    a("")
    a("## 3. 差异归因明细（oracle × portgraph 直接依赖）")
    a("")
    a("| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |")
    a("|---|---|---|---|---|")
    order = ["missed-dep", "resolution-gap", "false-positive",
             "readme-stale", "readme-omitted", "optional-not-built",
             "build-only", "qt-granularity", "matched", "matched-optional"]
    def sort_key(d):
        c = d["class"]
        return order.index(c) if c in order else len(order)
    for d in sorted(r["diffs"], key=sort_key):
        note = d["evidence"]["note"] if d.get("evidence") else ""
        if d.get("agent_note"):
            note = "%s 【agent: %s】" % (note, d["agent_note"])
        a("| %s | %s | %s | %s%s | %s |" % (
            _CLASS_LABEL.get(d["class"], d["class"]),
            _md_escape(d.get("oracle_name") or "—"),
            _md_escape(d.get("pg_name") or "—"),
            d.get("pg_kind") or d.get("oracle_type") or "",
            " d%d" % d["depth"] if d.get("depth") else "",
            _md_escape(note)[:200]))
    a("")
    a("归类统计：%s" % "，".join(
        "%s×%d" % (_CLASS_LABEL.get(c, c), n)
        for c, n in m["class_counts"].items()))
    a("")
    a("## 4. 依赖闭包概览（fetch-deps --dry-run）")
    a("")
    c = r["closure"]
    a("- 闭包总数 %d 项：%s" % (
        c["size"], "，".join("%s %d" % kv
                             for kv in sorted(c["summary"].items()))))
    if c["would_download"]:
        a("- 可直下 bottle：%s" % "、".join(c["would_download"][:40]))
    if c["cmd_only"]:
        a("- 仅命令获取（cmd_only）：%s" % "、".join(
            e["name"] for e in c["cmd_only"][:20]))
    if c["need_port"]:
        a("- 需自行移植（need_port）：%s" % "、".join(
            e["name"] for e in c["need_port"][:20]))
        for e in c["need_port"][:10]:
            src = e.get("source_url") or e.get("repo_url") or "?"
            a("  - %s: %s" % (e["name"], src))
    a("")
    a("## 5. 直接依赖全量清单（portgraph depth-1）")
    a("")
    a("| 节点 | 类型 | 边 | port_status | 深度 |")
    a("|---|---|---|---|---|")
    for d in r["direct_deps"]:
        a("| %s | %s | %s | %s | %s |" % (
            _md_escape(d["name"]), d["kind"], d["edge"],
            d["port_status"], d["depth"]))
    a("")
    a("## 6. 方法说明")
    a("")
    a("- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；"
      "闭包仅做产物概览。")
    a("- 归因证据：对未匹配项自动 grep 克隆仓库构建文件"
      "（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。")
    a("- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，"
      "需人工确认；其余为预期差异。")
    a("- agent 可读报告：`%s`" % (
        REPORTS_DIR / ("%s.report.json" % r["app"]["key"])))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(result: Dict, diffs: List[Dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    key = result["app"]["key"]
    write_md_report(result, REPORTS_DIR / ("%s.report.md" % key))
    (REPORTS_DIR / ("%s.report.json" % key)).write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="run_e2e.py",
        description="portgraph E2E 依赖对账 harness（真实项目 × README）")
    sub = ap.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run", help="对单个/全部语料项目执行对账")
    p_run.add_argument("--project", help="corpus 中的项目名")
    p_run.add_argument("--all", action="store_true", help="顺序执行全部")
    p_run.add_argument("--fresh-db", action="store_true",
                       help="强制从主库重新复制私有 DB")
    p_run.add_argument("--skip-scan", action="store_true",
                       help="跳过重扫（私有 DB 已有该 app 时）")
    p_run.add_argument("--no-clone", action="store_true",
                       help="不调用 clone（目录必须已存在）")
    sub.add_parser("list", help="列出语料项目")
    args = ap.parse_args()

    if args.cmd == "list" or not args.cmd:
        for p in load_corpus():
            print("%-12s tier %-2s %s  oracle: %s" % (
                p["name"], p.get("tier", "?"), p["url"],
                ",".join(p.get("oracle_files", []))))
        return

    corpus = load_corpus()
    if args.all:
        for p in corpus:
            run_project(p, args)
        return
    if not args.project:
        ap.error("需要 --project <name> 或 --all（可用项目见 list）")
    proj = next((p for p in corpus if p["name"] == args.project), None)
    if proj is None:
        ap.error("语料中无此项目: %s（可用见 list）" % args.project)
    run_project(proj, args)


if __name__ == "__main__":
    main()
