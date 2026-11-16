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
      guard:                    # 文件级断言：命中 glob 的文件必须满足 require
        files: ["platform_*.h"] # glob
        when: ["Q_OS_OHOS"]     # 可选：文件里出现这些片段才检查
        require: ["Q_OS_A"]     # 这些片段必须全部出现
        require_any: ["Q_OS_B"] # 这些片段至少出现一个
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
SEVERITY_DOWN = {"critical": "high", "high": "medium", "medium": "low", "low": "low"}
MAX_MATCHES_PER_RULE = 50

# 这些路径里的代码在鸿蒙目标上根本不参与编译（第三方源码树按平台裁剪、
# 或平台专属目录）。把它们算成 critical 会让风险面虚高（实测 tdesktop
# ThirdParty/fcitx5-qt 的 DBus 头被算成 critical），G2 也就失去判别力。
# 只收"按平台裁剪的第三方源码树"这类约定名。`vendor/`、`external/`、`contrib/`
# 在别的工程里常被真实编译进目标（AOSP 的 external/ 就是），自动降级会漏掉
# 会炸的真风险，因此这些目录要靠规则自己写 `exclude`。
THIRD_PARTY_HINTS = ("/thirdparty/", "/third_party/", "/3rdparty/", "/3rd-party/")
PLATFORM_EXCLUDED_HINTS = ("/platform/win/", "/platform/windows/", "/windows/",
                           "/win32/", "/winrt/", "/platform/macos/", "/macos/",
                           "/osx/", "/platform/apple/", "/darwin/",
                           "/platform/android/", "/platform/ios/")


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

            excludes = [str(g) for g in _as_list(match.get("exclude"))]
            for pattern in _as_list(match.get("source")):
                rx = _compile(pattern)
                if rx is None:
                    continue
                count = 0
                for src in scan_info.get("sources", []):
                    if src["ext"] not in TEXT_SCAN_EXTS:
                        continue
                    rel = src["path"]
                    if excludes and any(fnmatch.fnmatch(rel, g) for g in excludes):
                        continue
                    if rel not in sources_text:
                        try:
                            sources_text[rel] = (root / rel).read_text(
                                encoding="utf-8", errors="replace")
                        except OSError:
                            sources_text[rel] = ""
                    for lineno, line in enumerate(sources_text[rel].splitlines(), 1):
                        if rx.search(line):
                            findings.append(_scoped_finding(
                                rule, rel, lineno, line.strip()[:120]))
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
                    if excludes and any(fnmatch.fnmatch(rel, g) for g in excludes):
                        continue
                    if fnmatch.fnmatch(rel, str(pattern)):
                        findings.append(_scoped_finding(rule, rel, 0, "file present"))

            # guard：命中 glob 的文件必须**同时**包含 require 里全部片段，
            # 且（若给了 require_any）至少包含其中之一。`when` 用来把断言限定在
            # "已经写了某个片段"的文件上——比如"写了 Q_OS_OHOS 就必须也写
            # Q_OS_HARMONY"，没写任何 OHOS 宏的文件归审计工具管，不归这条规则。
            # 单看 files 只能报"文件存在"，看不出守卫写错在哪。
            guard = match.get("guard")
            if isinstance(guard, dict):
                globs = [str(g) for g in _as_list(guard.get("files"))]
                when = [(_compile(r), r) for r in _as_list(guard.get("when"))]
                when = [(rx, raw) for rx, raw in when if rx is not None]
                required = [(_compile(r), r) for r in _as_list(guard.get("require"))]
                required = [(rx, raw) for rx, raw in required if rx is not None]
                any_of = [(_compile(r), r) for r in _as_list(guard.get("require_any"))]
                any_of = [(rx, raw) for rx, raw in any_of if rx is not None]
                if globs and (required or any_of):
                    for rel in _all_rel_paths(root):
                        if not any(fnmatch.fnmatch(rel, g) for g in globs):
                            continue
                        try:
                            text = (root / rel).read_text(encoding="utf-8",
                                                          errors="replace")
                        except OSError:
                            continue
                        if when and not any(rx.search(text) for rx, _ in when):
                            continue
                        problems = []
                        missing = [raw for rx, raw in required if not rx.search(text)]
                        if missing:
                            problems.append("missing: %s" % ", ".join(
                                str(m) for m in missing))
                        if any_of and not any(rx.search(text) for rx, _ in any_of):
                            problems.append("missing one of: %s" % ", ".join(
                                str(raw) for _, raw in any_of))
                        if problems:
                            # 行号取守卫所在行：`文件:0` 没法点进去看
                            line = 1
                            for idx, row in enumerate(text.splitlines(), 1):
                                if re.search(r"#\s*(?:el)?if(?:def)?\b.*Q_OS_", row):
                                    line = idx
                                    break
                            else:
                                for idx, row in enumerate(text.splitlines(), 1):
                                    if re.search(r"Q_OS_[A-Z_]+", row):
                                        line = idx
                                        break
                            findings.append(_scoped_finding(
                                rule, rel, line, "; ".join(problems)))

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


def _path_scope(rel: str) -> str:
    """路径是不是"鸿蒙目标不编译"的代码：third-party / 平台专属目录。"""
    norm = "/" + rel.replace("\\", "/").lower().strip("/") + "/"
    if any(hint in norm for hint in THIRD_PARTY_HINTS):
        return "third-party"
    if any(hint in norm for hint in PLATFORM_EXCLUDED_HINTS):
        return "platform-excluded"
    return ""


def _scoped_finding(rule: Dict, rel: str, line: int, snippet: str) -> Dict:
    """按文件作用域降级：不参与 OHOS 编译的代码不该按 critical 阻塞 G2。

    规则可以用 `scope: keep` 关掉降级（确实需要在第三方目录里报问题的场景）。
    """
    finding = _finding(rule, rel, line, snippet)
    scope = _path_scope(rel)
    if scope and str(rule.get("scope", "")).lower() != "keep":
        finding["severity"] = SEVERITY_DOWN.get(finding["severity"],
                                                finding["severity"])
        finding["scope"] = scope
    return finding


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
        "scope": "",
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
