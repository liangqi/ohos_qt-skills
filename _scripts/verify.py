#!/usr/bin/env python3
"""ohos-qt-skills 仓库自检（契约 / 结构 / 知识页 / 卫生）。

用法：
    python3 _scripts/verify.py            # 全量检查
    python3 _scripts/verify.py --quiet    # 只输出问题
    python3 _scripts/verify.py --json      # 机读输出

退出码：0 = PASS（可有 WARN）｜1 = FAIL（有 ERROR）

设计原则：零第三方依赖（纯标准库），可在 Windows / macOS / Linux 一致运行；
只做"机器能判定的事实"（存在性 / 一致性 / 可解析性），不做主观质量评分。
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- 结果收集

ERRORS: list[str] = []
WARNS: list[str] = []
INFOS: list[str] = []


def error(code: str, msg: str) -> None:
    ERRORS.append(f"[{code}] {msg}")


def warn(code: str, msg: str) -> None:
    WARNS.append(f"[{code}] {msg}")


def info(msg: str) -> None:
    INFOS.append(msg)


# ---------------------------------------------------------------- 工具函数

SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", "outputs", ".venv"}
ARTIFACT_DIRS = {".cxx", ".hvigor", ".idea", ".gradle", ".deveco"}
TEXT_EXTS = {
    ".md", ".py", ".sh", ".json", ".json5", ".yaml", ".yml", ".toml", ".txt",
    ".ets", ".ts", ".cpp", ".h", ".hpp", ".cmake", ".cfg", ".ini", ".prf", ".pro",
}
MAX_SCAN_BYTES = 2 * 1024 * 1024
# 常见占位符用户名不算泄露（文档示例用）
PLACEHOLDER_USERS = {"you", "yourname", "username", "currentuser", "user", "example", "me"}
LOCAL_PATH_RE = re.compile(r"/Users/([A-Za-z0-9._-]+)/")
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\\\?[Uu]sers\\\\?([A-Za-z0-9._-]+)")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else None


def fm_field(fm: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip() if m else None


_GIT_VISIBLE: set[str] | None = None
_GIT_PROBED = False
INCLUDE_IGNORED = False


def _git_visible_files() -> set[str] | None:
    """本仓被 git 跟踪或未忽略的文件集合；非 git 环境返回 None。

    卫生检查必须只看"会被提交的东西"：本地 `workspace/` 的 Qt 构建树、
    `ENV.local.md` 里的本机绝对路径都是 gitignore 的，扫进来会产生成百条
    与提交无关的噪声，把真错误淹没（Windows 现场实测 134 条）。
    """
    global _GIT_VISIBLE, _GIT_PROBED
    if _GIT_PROBED:
        return _GIT_VISIBLE
    _GIT_PROBED = True
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        _GIT_VISIBLE = None
        return None
    if proc.returncode != 0:
        _GIT_VISIBLE = None
        return None
    raw = proc.stdout.decode("utf-8", errors="replace")
    _GIT_VISIBLE = {item for item in raw.split("\0") if item}
    return _GIT_VISIBLE


def walk_files(root: Path):
    visible = None if INCLUDE_IGNORED else _git_visible_files()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if visible is not None:
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    rel = path.as_posix()
                if rel not in visible:
                    continue
            yield path


# ---------------------------------------------------------------- 契约检查

CONTRACT_KEYS = [
    "schema_version", "id", "kind", "entrypoint", "map", "verify",
    "tooling_contract_version", "default_audience",
]


def load_contract() -> dict:
    path = ROOT / "kb.yaml"
    if not path.exists():
        error("C1", "缺少仓库契约 kb.yaml")
        return {}
    contract: dict = {}
    current_list: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - ") and current_list:
            contract.setdefault(current_list, []).append(raw[4:].strip())
            continue
        m = re.match(r"^([A-Za-z0-9_]+):[ \t]*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value:
            contract[key] = value
            current_list = None
        else:
            current_list = key
            contract.setdefault(key, [])
    for key in CONTRACT_KEYS:
        if not contract.get(key):
            error("C1", f"kb.yaml 缺少必填键 {key}")
    return contract


def check_paths(contract: dict) -> None:
    for rel in contract.get("required_paths", []):
        if not (ROOT / rel).exists():
            error("C2", f"契约要求的路径不存在：{rel}")
    for rel in contract.get("optional_paths", []):
        if not (ROOT / rel).exists():
            info(f"可选路径缺失（不失败）：{rel}")
    entry = contract.get("entrypoint")
    if entry and not (ROOT / entry).exists():
        error("C2", f"入口文件不存在：{entry}")
    idx = contract.get("map")
    if idx and not (ROOT / idx).exists():
        error("C2", f"知识地图不存在：{idx}")


def check_entrypoints() -> None:
    agents = ROOT / "AGENTS.md"
    claude = ROOT / "CLAUDE.md"
    if not agents.exists():
        error("C3", "缺少 AGENTS.md")
        return
    if not claude.exists():
        warn("C3", "缺少 CLAUDE.md（Claude Code 用户需手工复制 AGENTS.md）")
        return
    if agents.read_text(encoding="utf-8") != claude.read_text(encoding="utf-8"):
        error("C3", "AGENTS.md 与 CLAUDE.md 内容不一致（CLAUDE.md 应为 AGENTS.md 的副本）")


# ---------------------------------------------------------------- 知识页检查

# 各域必填字段（保留各域既有 schema 差异，逐步收敛）
DOMAIN_RULES = {
    "semantic": ["id", "type", "summary", "status", "audience"],
    "procedural": ["id", "type", "summary", "status", "audience"],
    "episodic": ["id", "type", "summary", "status", "audience"],
    "problems": ["id", "type", "summary", "status", "audience"],
    "ohos-common-kb-public": ["id", "summary", "status", "audience"],
}

PAGE_GLOBS = [
    ("semantic", "semantic/*.md"),
    ("procedural", "procedural/*.md"),
    ("episodic", "episodic/postmortems/*.md"),
    ("problems", "problems/*.md"),
    ("ohos-common-kb-public", "ohos-common-kb-public/*/*.md"),
]


def collect_pages() -> tuple[list[tuple[str, Path, str]], dict[str, str]]:
    pages: list[tuple[str, Path, str]] = []
    ids: dict[str, str] = {}
    for domain, pattern in PAGE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.name.startswith("_"):
                continue
            text = read_text(path)
            fm = frontmatter(text)
            rel = str(path.relative_to(ROOT))
            if fm is None:
                error("C4", f"{rel} 缺少 frontmatter")
                continue
            pages.append((domain, path, fm))
            for field in DOMAIN_RULES.get(domain, ["id", "summary", "status", "audience"]):
                if not fm_field(fm, field):
                    error("C4", f"{rel} 缺少 frontmatter 字段 {field}")
            pid = fm_field(fm, "id")
            if pid:
                if pid in ids:
                    error("C5", f"重复 id：{pid}（{ids[pid]} 与 {rel}）")
                ids[pid] = rel
            audience = fm_field(fm, "audience")
            if audience and audience != "public":
                error("C6", f"{rel} 的 audience={audience}（公开仓只允许 public）")
    return pages, ids


def head_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def tracked_files() -> list[str]:
    """入库文件清单：优先 git ls-files（权威），否则退回文件系统遍历。"""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout:
            return [x for x in out.stdout.split("\0") if x]
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(str(p.relative_to(ROOT)) for p in walk_files(ROOT))


def content_tree_sha256() -> str:
    """sha256 over sorted("<relpath>\\0<sha256(file)>\\n")，排除 manifest 自身。"""
    h = hashlib.sha256()
    for rel in sorted(tracked_files()):
        if rel == "RELEASE-MANIFEST.yaml":
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        h.update(rel.encode("utf-8") + b"\0")
        h.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return h.hexdigest()


def count_tests() -> int:
    def count(*rels: str) -> int:
        total = 0
        for rel in rels:
            try:
                tree = ast.parse(read_text(ROOT / rel))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                    total += sum(1 for item in node.body
                                 if isinstance(item, ast.FunctionDef)
                                 and item.name.startswith("test_"))
        return total
    return (count("tests/test_qt_ohos.py", "tests/test_kb_consistency.py",
                  "tests/test_cpp20_gap_scan.py")
            + count("portgraph/tests/test_port_graph.py",
                    "portgraph/tests/test_prefetch.py"))


def _yaml_value(raw: str) -> str:
    """取标量值：去掉行尾注释与引号（引号内不切）。"""
    v = raw.strip()
    if v[:1] in ('"', "'"):
        quote = v[0]
        end = v.find(quote, 1)
        return v[1:end] if end != -1 else v.strip(quote)
    idx = v.find(" #")
    return (v[:idx] if idx != -1 else v).strip()


def _yaml_scalars(text: str) -> dict:
    """只取顶层 `key: value` 与一层缩进 `  key: value`，够 manifest 用。"""
    flat: dict = {}
    section = ""
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^  ([A-Za-z0-9_]+):[ \t]*(.*)$", raw)
        if m and section:
            flat[f"{section}.{m.group(1)}"] = _yaml_value(m.group(2))
            continue
        m = re.match(r"^([A-Za-z0-9_]+):[ \t]*(.*)$", raw)
        if m:
            value = _yaml_value(m.group(2))
            if value:
                flat[m.group(1)] = value
                section = ""
            else:
                section = m.group(1)
    return flat


def check_manifest(pages: list[tuple[str, Path, str]]) -> None:
    """发版清单（RELEASE-MANIFEST.yaml）的字段必须与仓库实际一致。

    trunk-candidate 阶段只校验结构性事实（页面数 / skills / 用例数 / 枚举值）；
    一旦 status=released，内容树摘要与 root_commit 也必须对得上——否则"可对账"
    只是一句话。
    """
    path = ROOT / "RELEASE-MANIFEST.yaml"
    if not path.exists():
        warn("M1", "缺少 RELEASE-MANIFEST.yaml（发版清单；trunk 起应常驻）")
        return
    fm = _yaml_scalars(read_text(path))

    version = fm.get("release_version", "")
    if not re.match(r"^v\d+\.\d+\.\d+$", version):
        error("M1", f"release_version 格式不合法：{version!r}（应形如 v3.0.0）")
    status = fm.get("status", "")
    if status not in ("trunk-candidate", "released", "retired"):
        error("M1", f"status 取值不合法：{status!r}（trunk-candidate / released / retired）")

    common = sum(1 for d, _, _ in pages if d == "ohos-common-kb-public")
    qt_side = len(pages) - common
    for key, actual in (("common_pages_count", common), ("qt_pages_count", qt_side)):
        claimed = fm.get(key, "")
        if not claimed.isdigit():
            error("M1", f"{key} 缺失或非整数：{claimed!r}")
        elif int(claimed) != actual:
            error("M1", f"{key}={claimed}，实际 {actual}（页面数变了就更新清单）")

    skills = re.findall(r'"([^"]+)"', fm.get("skills", ""))
    actual_skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))
    if sorted(skills) != actual_skills:
        error("M1", f"skills 清单与 skills/ 目录不符：清单 {sorted(skills)}，实际 {actual_skills}")

    claimed_tests = fm.get("validation.unittests", "")
    actual_tests = count_tests()
    if not claimed_tests.isdigit():
        error("M1", f"validation.unittests 缺失或非整数：{claimed_tests!r}")
    elif int(claimed_tests) != actual_tests:
        error("M1", f"validation.unittests={claimed_tests}，实际 {actual_tests}")

    digest = fm.get("content_tree_sha256", "")
    if not re.match(r"^[0-9a-f]{64}$", digest):
        error("M1", "content_tree_sha256 缺失或不是 64 位小写十六进制")
        return
    actual_digest = content_tree_sha256()
    if status == "released":
        root_commit = fm.get("root_commit", "")
        if not re.match(r"^[0-9a-f]{40}$", root_commit):
            error("M1", "status=released 但 root_commit 未回填（40 位 SHA）")
            return
        # 只有站在发版提交上才强制摘要一致；发版之后的正常提交不算错（树已前进）
        if head_commit() == root_commit and digest != actual_digest:
            error("M1", "在发版提交上，content_tree_sha256 与树不符"
                        "（清单被改过或提交被篡改）")
        elif head_commit() != root_commit:
            info("发版 %s 已归档在 %s…，当前树在此之后" % (version[:12], root_commit[:12]))
    elif digest != actual_digest:
        info("发版清单为 %s 快照（%s…），与当前树不同——发版时运行 "
             "_scripts/gen-manifest.py 刷新" % (version, digest[:12]))


def _strip_inline_code(line: str) -> str:
    """把行内代码段替换成空白，避免示例写法被当成真链接。"""
    return re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def check_relative_links() -> None:
    """Markdown 相对 .md 链接必须指向存在的文件（C8）。

    C7 只查 `[[wikilink]]`；`](path.md)` 这类相对链接一直没人管，实测已有一处
    根相对写法（从子目录解析必然断），渲染与 Obsidian 都打不开。
    """
    for path in walk_files(ROOT):
        if path.suffix != ".md":
            continue
        rel = path.relative_to(ROOT).as_posix()
        in_fence = False
        for line in read_text(path).splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # 行内代码里的 `](x.md)` 是示例，不是链接
            for match in re.finditer(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)",
                                     _strip_inline_code(line)):
                target = match.group(1)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if not (path.parent / target).exists():
                    error("C8", f"相对链接指向不存在的文件：{rel} -> {target}")


INDEX_ENTRY_FILES = (
    "_index/_map.md", "_index/_tags.md", "_index/_task-routing.md",
    "_index/_dashboard.md", "problems/_lookup.md",
    "ohos-common-kb-public/_index.md",
)


def check_page_reachability(pages: list) -> None:
    """每个知识页至少要在一个索引里出现（C9）。

    132 页里曾只有 45 页进 `_map`，其余靠全库搜索；页写好了但没人能按图索骥，
    等于 Agent 看不见。索引入口可以是 _map/_tags/_task-routing/_lookup/内嵌库索引。
    """
    texts = []
    for rel in INDEX_ENTRY_FILES:
        path = ROOT / rel
        if path.exists():
            texts.append(read_text(path))
    orphan = []
    for dirname, path, _aud in pages:
        if path.name.startswith("_"):
            continue
        if not any(path.name in text for text in texts):
            orphan.append(path.relative_to(ROOT).as_posix())
    for rel in orphan:
        error("C9", f"页面未进任何索引（Agent 按图索骥看不到）：{rel}")


def check_wikilinks(ids: dict[str, str]) -> None:
    names = {p.stem for p in ROOT.rglob("*.md") if ".git" not in p.parts}
    broken: dict[str, int] = {}
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        in_fence = False
        for line in read_text(path).splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in re.finditer(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]", line):
                target = m.group(1).split("#")[0].strip()
                if not target:
                    continue
                base = Path(target).stem
                if base in names or target in ids:
                    continue
                broken[target] = broken.get(target, 0) + 1
    for target, count in sorted(broken.items(), key=lambda kv: -kv[1]):
        error("C7", f"wikilink 无法解析：[[{target}]]（{count} 处）")


def check_index_consistency(pages: list[tuple[str, Path, str]]) -> None:
    dash = ROOT / "_index/_dashboard.md"
    if not dash.exists():
        warn("C8", "缺少 _index/_dashboard.md")
        return
    fm = frontmatter(read_text(dash)) or ""
    claimed = fm_field(fm, "total_pages")
    if not claimed:
        return
    try:
        claimed_n = int(claimed)
    except ValueError:
        warn("C8", f"_dashboard.md 的 total_pages 不是整数：{claimed}")
        return
    # 口径与 _dashboard 一致：只统计 semantic/procedural/episodic/preference，
    # problems 与内嵌 common-KB 单独计数（见 problems/_lookup 与 manifest）。
    scoped = [p for p in pages if p[0] in ("semantic", "procedural", "episodic")]
    archived = sum(1 for _, _, page_fm in scoped
                   if (fm_field(page_fm, "status") or "") == "archived")
    actual = len(scoped) - archived
    if claimed_n != actual:
        warn("C8", f"_dashboard.md 声称 {claimed_n} 活跃页，实际 {actual}（含 {archived} 归档）")


# ---------------------------------------------------------------- 卫生检查

def check_hygiene() -> None:
    artifacts: dict[str, int] = {}
    leaks: list[str] = []
    if not INCLUDE_IGNORED and _git_visible_files() is None:
        # 没有 git 就没有"哪些文件会被提交"的依据：此时噪声必然存在，
        # 必须明说，否则用户会以为这堆 H2 是真的泄漏。
        warn("H1", "未检测到 git（或不在工作树内）：卫生检查无法跳过 gitignore 的"
                   "本地文件，H2 噪声属预期；可用 --include-ignored 显式复现")
    for path in walk_files(ROOT):
        rel = path.relative_to(ROOT)
        parts = set(rel.parts[:-1])
        if path.name == ".DS_Store" or path.suffix == ".pyc" or path.name == "__pycache__":
            key = path.name if path.name != "__pycache__" else "__pycache__"
            artifacts[key] = artifacts.get(key, 0) + 1
            continue
        hit = parts & ARTIFACT_DIRS
        if hit:
            key = "/".join(sorted(hit))
            artifacts[key] = artifacts.get(key, 0) + 1
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
        except OSError:
            continue
        text = read_text(path)
        if not text:
            continue
        hit = None
        for m in LOCAL_PATH_RE.finditer(text):
            if m.group(1).lower() not in PLACEHOLDER_USERS:
                hit = m.group(0)
                break
        if hit is None:
            for m in WIN_PATH_RE.finditer(text):
                if m.group(1).lower() not in PLACEHOLDER_USERS:
                    hit = m.group(0)
                    break
        if hit:
            leaks.append(f"{rel}: {hit}")
    for key, count in sorted(artifacts.items()):
        warn("H1", f"提交树内存在构建/系统产物目录 {key}（{count} 个文件）")
    for leak in leaks:
        error("H2", f"文件含本机绝对路径：{leak}")


# ---------------------------------------------------------------- 主流程

def main() -> int:
    parser = argparse.ArgumentParser(description="ohos-qt-skills 仓库自检")
    parser.add_argument("--quiet", action="store_true", help="只输出 ERROR/WARN")
    parser.add_argument("--json", action="store_true", help="机读输出")
    parser.add_argument("--include-ignored", action="store_true",
                        help="连 gitignore 的本地文件一起扫（默认只看会被提交的文件）")
    args = parser.parse_args()
    global INCLUDE_IGNORED
    INCLUDE_IGNORED = args.include_ignored

    contract = load_contract()
    check_paths(contract)
    check_entrypoints()
    pages, ids = collect_pages()
    check_wikilinks(ids)
    check_relative_links()
    check_page_reachability(pages)
    check_index_consistency(pages)
    check_manifest(pages)
    check_hygiene()

    ok = not ERRORS
    if args.json:
        print(json.dumps(
            {"ok": ok, "errors": ERRORS, "warnings": WARNS, "info": INFOS,
             "pages": len(pages)},
            ensure_ascii=False, indent=2))
    else:
        if not args.quiet:
            contract_id = contract.get("id", "?")
            print(f"ohos-qt-skills verify — 契约 {contract_id} v{contract.get('schema_version', '?')}"
                  f"（tooling v{contract.get('tooling_contract_version', '?')}）")
            print(f"内容页：{len(pages)} ｜ id：{len(ids)}")
            for line in INFOS:
                print(f"  INFO  {line}")
        for line in WARNS:
            print(f"  WARN  {line}")
        for line in ERRORS:
            print(f"  ERROR {line}")
        print(f"RESULT: {'PASS' if ok else 'FAIL'}"
              f"（{len(ERRORS)} errors, {len(WARNS)} warnings）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
