"""Machine-executable risk rules engine.

Loads knowledge/rules/R*.yaml and matches them against a scanned project.
This upgrades the human-readable golden-rules into rules a tool can run:

    qt-ohos-run scan <project>

Rule schema (see knowledge/rules/index.yaml):

    id: R017
    name: linux_process_api
    category: process
    severity: critical          # critical / high / medium / low
    platform:
      harmonyos: unsupported    # unsupported / restricted / workaround / review
    match:
      source: ["fork\\(", ...]   # regexes against C/C++/QML source text
      pro:    [...]             # regexes against .pro/.pri contents
      cmake:  [...]             # regexes against CMakeLists.txt contents
      modules: [dbus]           # matched against detected Qt module list
      files:  ["*.so"]          # glob against project files
    golden_rules: [B9]          # cross-ref semantic/qt-harmonyos-golden-rules.md
    kb: [semantic/qt-harmonyos-platform-limits.md]
    solution: >
      ...
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, List

from . import yaml_lite
from .scanner import TEXT_SCAN_EXTS

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
MAX_MATCHES_PER_RULE = 50


def load_rules(kb_root) -> List[Dict]:
    rules_dir = Path(kb_root) / "knowledge" / "rules"
    rules = []
    if not rules_dir.is_dir():
        return rules
    for path in sorted(rules_dir.glob("R*.yaml")):
        try:
            rule = yaml_lite.parse(path.read_text(encoding="utf-8"))
        except yaml_lite.YamlLiteError as exc:
            raise ValueError("bad rule file %s: %s" % (path.name, exc))
        if isinstance(rule, dict) and rule.get("id"):
            rule["_file"] = path.name
            rules.append(rule)
    rules.sort(key=lambda r: str(r.get("id", "")))
    return rules


class RuleEngine:
    def __init__(self, kb_root):
        self.rules = load_rules(kb_root)

    def scan(self, scan_info: Dict, project_root) -> Dict:
        root = Path(project_root).resolve()
        findings: List[Dict] = []
        sources_text: Dict[str, str] = {}

        for rule in self.rules:
            match = rule.get("match") or {}

            for pattern in _as_list(match.get("modules")):
                if str(pattern).lower() in scan_info.get("qt_modules", []):
                    findings.append(_finding(rule, "qt-module:%s" % pattern,
                                             0, "Qt module '%s'" % pattern))

            for pattern in _as_list(match.get("source")):
                rx = _compile(pattern)
                if rx is None:
                    continue
                count = 0
                for src in scan_info.get("sources", []):
                    if src["ext"] not in TEXT_SCAN_EXTS:
                        continue
                    rel = src["path"]
                    if rel not in sources_text:
                        try:
                            sources_text[rel] = (root / rel).read_text(
                                encoding="utf-8", errors="replace")
                        except OSError:
                            sources_text[rel] = ""
                    for lineno, line in enumerate(sources_text[rel].splitlines(), 1):
                        if rx.search(line):
                            findings.append(_finding(rule, rel, lineno,
                                                     line.strip()[:120]))
                            count += 1
                            if count >= MAX_MATCHES_PER_RULE:
                                break
                    if count >= MAX_MATCHES_PER_RULE:
                        break

            for key, files in (("pro", scan_info.get("pro_files", [])),
                               ("cmake", scan_info.get("cmake_files", []))):
                for pattern in _as_list(match.get(key)):
                    rx = _compile(pattern)
                    if rx is None:
                        continue
                    for rel in files:
                        try:
                            text = (root / rel).read_text(encoding="utf-8",
                                                          errors="replace")
                        except OSError:
                            continue
                        for lineno, line in enumerate(text.splitlines(), 1):
                            if rx.search(line):
                                findings.append(_finding(rule, rel, lineno,
                                                         line.strip()[:120]))

            for pattern in _as_list(match.get("files")):
                for rel in _all_rel_paths(root):
                    if fnmatch.fnmatch(rel, str(pattern)):
                        findings.append(_finding(rule, rel, 0, "file present"))

        return self.report(findings)

    def report(self, findings: List[Dict]) -> Dict:
        by_sev: Dict[str, List[Dict]] = {}
        for item in findings:
            by_sev.setdefault(item["severity"], []).append(item)
        summary = {sev: len(items) for sev, items in by_sev.items()}
        ordered = sorted(findings, key=lambda f: (
            SEVERITY_ORDER.get(f["severity"], 9), f["rule"], f["file"], f["line"]))
        return {
            "summary": summary,
            "findings": ordered,
            "rules_loaded": len(self.rules),
        }


def _finding(rule: Dict, rel: str, line: int, snippet: str) -> Dict:
    return {
        "rule": rule.get("id"),
        "name": rule.get("name"),
        "severity": str(rule.get("severity", "medium")).lower(),
        "category": rule.get("category"),
        "file": rel,
        "line": line,
        "snippet": snippet,
        "platform": (rule.get("platform") or {}).get("harmonyos"),
        "golden_rules": _as_list(rule.get("golden_rules")),
        "kb": _as_list(rule.get("kb")),
        "solution": rule.get("solution"),
    }


def _as_list(value) -> List:
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v is not None]
    return [value]


def _compile(pattern: str):
    try:
        return re.compile(str(pattern))
    except re.error:
        return None


def _all_rel_paths(root: Path):
    for path in root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if not rel.startswith(".git/") and "/.qt-ohos/" not in rel:
                yield rel
