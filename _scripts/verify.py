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
import json
import os
import re
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


def walk_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


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
    args = parser.parse_args()

    contract = load_contract()
    check_paths(contract)
    check_entrypoints()
    pages, ids = collect_pages()
    check_wikilinks(ids)
    check_index_consistency(pages)
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
