#!/usr/bin/env python3
"""刷新 RELEASE-MANIFEST.yaml 的可计算字段（零第三方依赖）。

为什么需要它：清单里写着"可复现、可对账"，但内容树摘要、页面数、用例数
以前都是手填的，改完代码就过期。本脚本把它们重算一遍原地写回，发版流程
（tag 前）跑一次即可。

用法：
    python3 _scripts/gen-manifest.py            # 刷新哈希/计数/时间，保持 status 不变
    python3 _scripts/gen-manifest.py --check    # 只比对，不改文件；不一致退出 1
    python3 _scripts/gen-manifest.py --release  # 置 status=released、回填 root_commit

退出码：0 = 一致/已刷新；1 = --check 发现不一致或环境不满足。
"""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "RELEASE-MANIFEST.yaml"

PAGE_GLOBS = [
    ("semantic", "semantic/*.md"),
    ("procedural", "procedural/*.md"),
    ("episodic", "episodic/postmortems/*.md"),
    ("problems", "problems/*.md"),
    ("ohos-common-kb-public", "ohos-common-kb-public/*/*.md"),
]


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        print("gen-manifest: 需要 git（入库文件清单以 git ls-files 为准）")
        sys.exit(1)
    return [x for x in out.stdout.split("\0") if x]


def content_tree_sha256() -> str:
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


def page_counts() -> tuple[int, int, str]:
    counts: dict[str, int] = {}
    for domain, pattern in PAGE_GLOBS:
        counts[domain] = sum(
            1 for p in sorted(ROOT.glob(pattern)) if not p.name.startswith("_"))
    common = counts.get("ohos-common-kb-public", 0)
    qt_side = sum(v for k, v in counts.items() if k != "ohos-common-kb-public")
    detail = " + ".join(f"{k} {v}" for k, v in counts.items()
                        if k != "ohos-common-kb-public")
    return common, qt_side, detail


def test_count() -> int:
    def count(*rels: str) -> int:
        total = 0
        for rel in rels:
            try:
                tree = ast.parse((ROOT / rel).read_text(encoding="utf-8-sig"))
            except (OSError, SyntaxError):
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


def current_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, timeout=30)
    return out.stdout.strip() if out.returncode == 0 else ""


def set_scalar(text: str, key: str, value: str, indent: str = "",
               comment: str | None = None) -> str:
    """改一行 `key: value`。comment=None 保留原行尾注释，否则替换为给定注释。"""
    pattern = re.compile(rf"^({re.escape(indent)}{re.escape(key)}:[ \t]*)([^\n#]*?)([ \t]*#[^\n]*)?$",
                         re.M)
    m = pattern.search(text)
    if not m:
        print(f"gen-manifest: manifest 里找不到字段 {key}")
        sys.exit(1)
    tail = ("             # " + comment) if comment is not None else (m.group(3) or "")
    return text[:m.start()] + m.group(1) + value + tail + text[m.end():]


def main() -> int:
    parser = argparse.ArgumentParser(description="刷新发版清单的可计算字段")
    parser.add_argument("--check", action="store_true", help="只比对，不写文件")
    parser.add_argument("--release", action="store_true",
                        help="置 status=released 并回填 root_commit/released_at")
    args = parser.parse_args()

    original = MANIFEST.read_text(encoding="utf-8")
    text = original

    common, qt_side, detail = page_counts()
    digest = content_tree_sha256()
    tests = test_count()
    now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

    text = set_scalar(text, "content_tree_sha256", digest)
    text = set_scalar(text, "built_at", f'"{now}"')
    text = set_scalar(text, "common_pages_count", str(common))
    text = set_scalar(text, "qt_pages_count", str(qt_side),
                      comment=f"{detail}（不含 _index/_lookup）")
    text = set_scalar(text, "unittests", str(tests),
                      indent="  ")
    if args.release:
        commit = current_commit()
        text = set_scalar(text, "root_commit", f'"{commit}"')
        text = set_scalar(text, "status", "released")
        text = set_scalar(text, "released_at", f'"{now[:10]}"')

    if args.check:
        if text != original:
            print("gen-manifest: 清单与仓库实际不一致（运行 _scripts/gen-manifest.py 刷新）")
            for line in text.splitlines():
                if line not in original.splitlines() and line.strip():
                    print("  → " + line.strip())
            return 1
        print(f"gen-manifest: 一致（{common + qt_side} 页 / {tests} 用例 / {digest[:12]}…）")
        return 0

    MANIFEST.write_text(text, encoding="utf-8")
    print(f"gen-manifest: 已刷新（Qt {qt_side} + 平台 {common} = {qt_side + common} 页，"
          f"{tests} 用例，{digest[:12]}…）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
