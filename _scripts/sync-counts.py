#!/usr/bin/env python3
"""Sync "derived numbers" from the source of truth into the human-facing docs (README / TESTING).

Why it exists: README and TESTING state **derived facts** such as page counts and test counts.
These numbers used to be edited by hand and have demonstrably drifted: README said "engine
self-tests 12 cases" when the real number was 75; TESTING said "48 cases" when it was 109.
Once numbers drift, the promise "the counts in the docs are guarded by tests" becomes a one-off slogan.

Now it works like this: source of truth (filesystem / AST counts) -> this script -> docs. Every
replacement has an exact anchor; if an anchor doesn't match, the script exits with an error
(meaning someone changed that line of text), so nothing is silently missed.

Usage:
    python _scripts/sync-counts.py            # sync in place
    python _scripts/sync-counts.py --check    # check only; exit 1 if stale (for CI)
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


# (file, regex, function that rebuilds from the groups) -- each must match exactly once
RULES: List[Tuple[str, str, Callable[[re.Match, Dict[str, int]], str]]] = [
    ("README.md", r"(knowledge%20pages-)(\d+)(-orange)",
     lambda m, c: "%s%d%s" % (m.group(1), c["pages"], m.group(3))),
    ("README.md", r"(\d+)( QOH error patterns machine-matched \+ )(\d+)( real-world pitfall pages)",
     lambda m, c: "%d%s%d%s" % (c["qoh"], m.group(2), c["problems"], m.group(4))),
    ("README.md", r"(knowledge/errors\()(\d+)( QOH\) · rules\()(\d+)( R\))",
     lambda m, c: "%s%d%s%d%s" % (m.group(1), c["qoh"], m.group(3),
                                  c["rules"], m.group(5))),
    ("README.md", r"(qt-ohos-run\.py` \()(\d+)( subcommands\))",
     lambda m, c: "%s%d%s" % (m.group(1), _subcommands("tools/qt-ohos-run.py"),
                              m.group(3))),
    ("README.md", r"(\| )(\d+)( QOH error patterns auto-matched)",
     lambda m, c: "%s%d%s" % (m.group(1), c["qoh"], m.group(3))),
    ("README.md",
     r"(\d+)( pages \(Qt side )(\d+)( \+ embedded platform )(\d+)(\), )(\d+)( iron rules, 13 API mapping categories, )(\d+)( real-world pitfalls)",
     lambda m, c: "%d%s%d%s%d%s%d%s%d%s" % (
         c["pages"], m.group(2), c["qt"], m.group(4), c["common"], m.group(6),
         c["iron"], m.group(8), c["problems"], m.group(10))),
    ("README.md", r"(engine self-tests )(\d+)( cases \+ consistency )(\d+)( cases \+ C\+\+20 scan )(\d+)( cases)",
     lambda m, c: "%s%d%s%d%s%d%s" % (m.group(1), c["engine"], m.group(3),
                                      c["consistency"], m.group(5),
                                      c["scanner"], m.group(7))),
    ("README.md", r"(\| Numbers \| Consistency cases \()(\d+)(\))",
     lambda m, c: "%s%d%s" % (m.group(1), c["consistency"], m.group(3))),
    ("README.md",
     r"(engine )(\d+)( \+ consistency )(\d+)( \+ scan )(\d+)( = )(\d+)( cases, plus )(\d+)( graph unit tests)",
     lambda m, c: "%s%d%s%d%s%d%s%d%s%d%s" % (
         m.group(1), c["engine"], m.group(3), c["consistency"], m.group(5),
         c["scanner"], m.group(7), c["tests"], m.group(9), c["graph_total"],
         m.group(11))),
    ("README.md", r"(pre-scan \+ risk report from )(\d+)( rules)",
     lambda m, c: "%s%d%s" % (m.group(1), c["rules"], m.group(3))),
    ("README.md", r"(scan \()(\d+)( pre-scan rules produce a risk report\))",
     lambda m, c: "%s%d%s" % (m.group(1), c["rules"], m.group(3))),
    ("README.md", r"(# Embedded general HarmonyOS platform knowledge \()(\d+)( pages)",
     lambda m, c: "%s%d%s" % (m.group(1), c["common"], m.group(3))),
    ("README.md", r"(; )(\d+)( task types in total)",
     lambda m, c: "%s%d%s" % (m.group(1), c["routes"], m.group(3))),
    ("README.md", r"(└── skills/ +) # (\d+)( Agent Skills?)",
     lambda m, c: "%s # %d%s" % (m.group(1), c["skills"], m.group(3))),
    ("README.md", r"(- Version numbers follow.*$)", lambda m, c: m.group(1)),
    ("TESTING.md", r"(# consistency \+ engine \+ scan \()(\d+)( cases\))",
     lambda m, c: "%s%d%s" % (m.group(1), c["tests"], m.group(3))),
    ("TESTING.md",
     r"(\*\*OK \()(\d+)( tests\)\*\* \| engine )(\d+)( \+ consistency )(\d+)( \+ cpp20 scan )(\d+)( = )(\d+)( \(plus )(\d+)( portgraph unit tests: graph )(\d+)( \+ prefetch )(\d+)",
     lambda m, c: "%s%d%s%d%s%d%s%d%s%d%s%d%s%d%s%d" % (
         m.group(1), c["tests"], m.group(3), c["engine"], m.group(5),
         c["consistency"], m.group(7), c["scanner"], m.group(9), c["tests"],
         m.group(11), c["graph_total"], m.group(13), c["graph"],
         m.group(15), c["prefetch"])),
    ("TESTING.md", r"(# expect \"CI: all passed\" \()(\d+)( cases\))",
     lambda m, c: "%s%d%s" % (m.group(1), c["tests"], m.group(3))),
    ("TESTING.md", r"(gen-manifest: counts consistent \()(\d+)( pages / )(\d+)( cases\))",
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
            problems.append("%s: anchor %r matched %d times (should be exactly once)"
                            % (rel, pattern[:48], len(matches)))
            continue
        match = matches[0]
        text = text[:match.start()] + builder(match, counts) + text[match.end():]
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sync the derived numbers in the docs")
    parser.add_argument("--check", action="store_true", help="check only; exit 1 if stale")
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
    summary = ("%d pages / QOH %d / R %d / problems %d / iron rules %d / cases %d (engine %d + consistency %d + scan %d)"
               % (counts["pages"], counts["qoh"], counts["rules"],
                  counts["problems"], counts["iron"], counts["tests"],
                  counts["engine"], counts["consistency"], counts["scanner"]))
    if args.check:
        if changed:
            print("sync-counts: doc numbers are stale: %s; run python _scripts/sync-counts.py"
                  % ", ".join(changed))
            return 1
        print("sync-counts: consistent (%s)" % summary)
        return 0
    print("sync-counts: synced %s (%s)"
          % (", ".join(changed) if changed else "no changes", summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
