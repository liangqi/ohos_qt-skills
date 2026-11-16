#!/usr/bin/env python3
"""把"派生数字"从真源同步进面向人的文档（README / TESTING）。

为什么需要它：README 与 TESTING 里写着页数、用例数这类**派生事实**。以前这些数字靠手改，
实测已经漂移过：README 说"引擎自测 12 用例"，真实 75；TESTING 说"48 用例"，真实 109。
数字一漂，"文档里的数量由用例守着"这条承诺就变成一次性口号。

现在改成：真源（文件系统 / AST 计数）→ 本脚本 → 文档。每条替换都有精确锚点，锚点匹配不到
就报错退出（说明有人改了那行文字），不会静默漏改。

用法：
    python _scripts/sync-counts.py            # 原地同步
    python _scripts/sync-counts.py --check    # 只检查，过期退出 1（CI 用）
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "_scripts"


def _load_manifest_module():
    spec = importlib.util.spec_from_file_location(
        "gen_manifest", SCRIPTS / "gen-manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # type: ignore[union-attr]
    return module


def _entry_count(rel: str, key: str) -> int:
    text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    match = re.search(rf"^{key}:\s*(\d+)", text, re.M)
    return int(match.group(1)) if match else 0


def _iron_rules() -> int:
    text = (ROOT / "semantic" / "qt-harmonyos-golden-rules.md").read_text(
        encoding="utf-8", errors="replace")
    return len(re.findall(r"^\|\s*[A-Z]?\d+\s*\|", text, re.M)) or len(
        re.findall(r"^### ", text, re.M))


def _routes() -> int:
    text = (ROOT / "_index" / "_task-routing.md").read_text(
        encoding="utf-8", errors="replace")
    return len(re.findall(r"^### \[[A-Z]\]", text, re.M))


def _test_cases(rel: str) -> int:
    try:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError):
        return 0
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            total += sum(1 for item in node.body
                         if isinstance(item, ast.FunctionDef)
                         and item.name.startswith("test_"))
    return total


def compute() -> Dict[str, int]:
    manifest = _load_manifest_module()
    common, qt_side, _detail = manifest.page_counts()
    engine = _test_cases("tests/test_qt_ohos.py")
    consistency = _test_cases("tests/test_kb_consistency.py")
    scanner = _test_cases("tests/test_cpp20_gap_scan.py")
    graph = _test_cases("portgraph/tests/test_port_graph.py")
    prefetch = _test_cases("portgraph/tests/test_prefetch.py")
    problems = len([p for p in (ROOT / "problems").glob("*.md")
                    if not p.name.startswith("_")])
    return {
        "pages": common + qt_side,
        "qt": qt_side,
        "common": common,
        "qoh": _entry_count("knowledge/errors/index.yaml", "entry_count"),
        "rules": _entry_count("knowledge/rules/index.yaml", "rule_count"),
        "problems": problems,
        "iron": _iron_rules(),
        "engine": engine,
        "consistency": consistency,
        "scanner": scanner,
        "tests": engine + consistency + scanner,
        "graph": graph,
        "prefetch": prefetch,
        "graph_total": graph + prefetch,
        "skills": len(list((ROOT / "skills").glob("*/SKILL.md"))),
        "routes": _routes(),
    }


# (文件, 正则, 用分组重建的函数) —— 每条必须恰好命中一次
RULES: List[Tuple[str, str, Callable[[re.Match, Dict[str, int]], str]]] = [
    ("README.md", r"(知识页-)(\d+)(-orange)",
     lambda m, c: "%s%d%s" % (m.group(1), c["pages"], m.group(3))),
    ("README.md", r"(\d+)( 条 QOH 错误模式机器匹配 \+ )(\d+)( 个实战踩坑页)",
     lambda m, c: "%d%s%d%s" % (c["qoh"], m.group(2), c["problems"], m.group(4))),
    ("README.md", r"(knowledge/errors\()(\d+)( 条 QOH\) · rules\()(\d+)( 条 R\))",
     lambda m, c: "%s%d%s%d%s" % (m.group(1), c["qoh"], m.group(3),
                                  c["rules"], m.group(5))),
    ("README.md", r"(qt-ohos-run\.py`（)(\d+)( 个子命令）)",
     lambda m, c: "%s%d%s" % (m.group(1), _subcommands("tools/qt-ohos-run.py"),
                              m.group(3))),
    ("README.md", r"(\| )(\d+)( 条 QOH 错误模式自动匹配)",
     lambda m, c: "%s%d%s" % (m.group(1), c["qoh"], m.group(3))),
    ("README.md",
     r"(\d+)( 页（Qt 侧 )(\d+)( \+ 内嵌平台 )(\d+)(），)(\d+)( 条铁律，13 类 API 映射，)(\d+)( 个实战踩坑)",
     lambda m, c: "%d%s%d%s%d%s%d%s%d%s" % (
         c["pages"], m.group(2), c["qt"], m.group(4), c["common"], m.group(6),
         c["iron"], m.group(8), c["problems"], m.group(10))),
    ("README.md", r"(引擎自测 )(\d+)( 用例 \+ 一致性 )(\d+)( 用例 \+ C\+\+20 扫描 )(\d+)( 用例)",
     lambda m, c: "%s%d%s%d%s%d%s" % (m.group(1), c["engine"], m.group(3),
                                      c["consistency"], m.group(5),
                                      c["scanner"], m.group(7))),
    ("README.md", r"(\| 数字 \| 一致性用例（)(\d+)( 个）)",
     lambda m, c: "%s%d%s" % (m.group(1), c["consistency"], m.group(3))),
    ("README.md",
     r"(引擎 )(\d+)( \+ 一致性 )(\d+)( \+ 扫描 )(\d+)( = )(\d+)( 用例，另有图谱 )(\d+)( 单测)",
     lambda m, c: "%s%d%s%d%s%d%s%d%s%d%s" % (
         m.group(1), c["engine"], m.group(3), c["consistency"], m.group(5),
         c["scanner"], m.group(7), c["tests"], m.group(9), c["graph_total"],
         m.group(11))),
    ("README.md", r"(预扫描 \+ )(\d+)( 条规则风险报告)",
     lambda m, c: "%s%d%s" % (m.group(1), c["rules"], m.group(3))),
    ("README.md", r"(扫描（)(\d+)( 条预扫描规则出风险报告）)",
     lambda m, c: "%s%d%s" % (m.group(1), c["rules"], m.group(3))),
    ("README.md", r"(# 内嵌 HarmonyOS 平台通用知识（)(\d+)( 页)",
     lambda m, c: "%s%d%s" % (m.group(1), c["common"], m.group(3))),
    ("README.md", r"(共 )(\d+)( 类任务)",
     lambda m, c: "%s%d%s" % (m.group(1), c["routes"], m.group(3))),
    ("README.md", r"(└── skills/ +) # (\d+)( 个 Agent Skill)",
     lambda m, c: "%s # %d%s" % (m.group(1), c["skills"], m.group(3))),
    ("README.md", r"(- 版本号遵循.*$)", lambda m, c: m.group(1)),
    ("TESTING.md", r"(# 一致性 \+ 引擎 \+ 扫描（)(\d+)( 用例）)",
     lambda m, c: "%s%d%s" % (m.group(1), c["tests"], m.group(3))),
    ("TESTING.md",
     r"(\*\*OK（)(\d+)( tests）\*\* \| 引擎 )(\d+)( \+ 一致性 )(\d+)( \+ cpp20 扫描 )(\d+)( = )(\d+)(（另有 portgraph )(\d+)( 单测：图谱 )(\d+)( \+ 预取 )(\d+)",
     lambda m, c: "%s%d%s%d%s%d%s%d%s%d%s%d%s%d%s%d" % (
         m.group(1), c["tests"], m.group(3), c["engine"], m.group(5),
         c["consistency"], m.group(7), c["scanner"], m.group(9), c["tests"],
         m.group(11), c["graph_total"], m.group(13), c["graph"],
         m.group(15), c["prefetch"])),
    ("TESTING.md", r"(# 期望「CI: 全部通过」（)(\d+)( 用例）)",
     lambda m, c: "%s%d%s" % (m.group(1), c["tests"], m.group(3))),
    ("TESTING.md", r"(gen-manifest: 计数一致（)(\d+)( 页 / )(\d+)( 用例）)",
     lambda m, c: "%s%d%s%d%s" % (m.group(1), c["pages"], m.group(3),
                                  c["tests"], m.group(5))),
]


def _subcommands(script: str) -> int:
    import subprocess
    proc = subprocess.run([sys.executable, str(ROOT / script), "--help"],
                          capture_output=True, text=True, timeout=120,
                          cwd=str(ROOT))
    block = re.search(r"\{([a-z0-9,\-_]+)\}", proc.stdout or "")
    return len(block.group(1).split(",")) if block else 0


def apply(text: str, path: str, counts: Dict[str, int],
          problems: List[str]) -> str:
    for rel, pattern, builder in RULES:
        if rel != path:
            continue
        matches = list(re.finditer(pattern, text, re.M))
        if len(matches) != 1:
            problems.append("%s: 锚点 %r 命中 %d 次（应恰好 1 次）"
                            % (rel, pattern[:48], len(matches)))
            continue
        match = matches[0]
        text = text[:match.start()] + builder(match, counts) + text[match.end():]
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步文档里的派生数字")
    parser.add_argument("--check", action="store_true", help="只检查，过期退出 1")
    args = parser.parse_args(argv)
    counts = compute()
    problems: List[str] = []
    changed: List[str] = []
    for path in sorted({rel for rel, _p, _b in RULES}):
        target = ROOT / path
        original = target.read_text(encoding="utf-8")
        updated = apply(original, path, counts, problems)
        if updated != original:
            changed.append(path)
            if not args.check:
                target.write_text(updated, encoding="utf-8")
    if problems:
        for item in problems:
            print("sync-counts: " + item, file=sys.stderr)
        return 2
    summary = ("%d 页 / QOH %d / R %d / problems %d / 铁律 %d / 用例 %d（引擎 %d + 一致性 %d + 扫描 %d）"
               % (counts["pages"], counts["qoh"], counts["rules"],
                  counts["problems"], counts["iron"], counts["tests"],
                  counts["engine"], counts["consistency"], counts["scanner"]))
    if args.check:
        if changed:
            print("sync-counts: 文档数字过期：%s，运行 python _scripts/sync-counts.py"
                  % ", ".join(changed))
            return 1
        print("sync-counts: 一致（%s）" % summary)
        return 0
    print("sync-counts: 已同步 %s（%s）"
          % (", ".join(changed) if changed else "无变化", summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
