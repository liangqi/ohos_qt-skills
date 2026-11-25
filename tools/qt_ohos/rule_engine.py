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
      guard:                    # file-level assertion: files matching the glob must satisfy require
        files: ["platform_*.h"] # glob
        when: ["Q_OS_OHOS"]     # optional: only check files containing these fragments
        require: ["Q_OS_A"]     # all of these fragments must appear
        require_any: ["Q_OS_B"] # at least one of these fragments must appear
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

# Code under these paths is never compiled for the HarmonyOS target (third-party source trees
# trimmed per platform, or platform-specific directories). Counting it as critical inflates the
# risk surface (observed: tdesktop ThirdParty/fcitx5-qt DBus headers counted as critical), and G2
# loses its discriminating power.
# Only conventional names for "third-party source trees trimmed per platform" are included.
# `vendor/`, `external/`, `contrib/` are often really compiled into the target in other projects
# (AOSP's external/ is), so auto-downgrading them would miss real risks that blow up; for those
# directories the rule must write its own `exclude`.
THIRD_PARTY_HINTS = ("/thirdparty/", "/third_party/", "/3rdparty/", "/3rd-party/")
PLATFORM_EXCLUDED_HINTS = ("/platform/win/", "/platform/windows/", "/windows/",
                           "/win32/", "/winrt/", "/platform/macos/", "/macos/",
                           "/osx/", "/platform/apple/", "/darwin/",
                           "/platform/android/", "/platform/ios/")

# Platform-specific **files** (independent of directory): files like Cocoa's foo_mac.mm or
# Win32's bar_win.cpp never become compilation units in a HarmonyOS build; when scattered in
# ordinary directories, a directory-based check misses them (observed: 113 of 114 critical
# findings came from such files). Suffixes are matched exactly as `_suffix` on the file stem to
# avoid false hits on `window.cpp`/`machine.cpp`.
PLATFORM_EXCLUDED_SUFFIXES = (
    "win", "win32", "win64", "windows", "winrt",
    "mac", "macos", "osx", "cocoa", "darwin", "apple", "ios",
    "android", "xcb", "wayland", "haiku",
)
_OBJC_EXTS = (".mm", ".m")

# If any of these tokens appears in the file name, the whole file serves only that platform
# (wherever xcb appears in `base_linux_xcb_library.cpp`, it is not a HarmonyOS compilation unit).
PLATFORM_EXCLUDED_TOKENS = ("xcb", "win32", "win64", "winrt", "cocoa", "objc",
                            "mfc", "atl")
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")

# Conditional blocks that hold only for these macros = not compiled on HarmonyOS (code inside
# should not count as risk). Once the condition also mentions LINUX/UNIX/OHOS/HARMONY,
# HarmonyOS enters that branch too.
_NON_OHOS_MACROS = ("Q_OS_WIN", "Q_OS_WIN32", "Q_OS_WIN64", "Q_OS_WINRT",
                    "Q_OS_MAC", "Q_OS_MACOS", "Q_OS_OSX", "Q_OS_DARWIN",
                    "Q_OS_APPLE", "Q_OS_IOS", "Q_OS_TVOS", "Q_OS_WATCHOS",
                    "Q_OS_ANDROID", "Q_OS_FREEBSD", "Q_OS_HAIKU",
                    "_WIN32", "_WIN64", "__APPLE__", "__MINGW32__",
                    "__MINGW64__", "TARGET_OS_MAC")
# Note: Q_OS_ANDROID belongs only to "non-HarmonyOS" - also listing it here would mean Android
# branches are never downgraded (`_excluded()` checks this constant first and returns False on a hit).
_OHOS_MACROS = ("Q_OS_LINUX", "Q_OS_UNIX", "Q_OS_OHOS", "Q_OS_HARMONY",
                "__OHOS__")
_GUARD_LINE_RE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")


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
        guarded_lines: Dict[str, set] = {}

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
                    if rel not in guarded_lines:
                        guarded = set()
                        for rng in _guarded_ranges(sources_text[rel]):
                            guarded.update(rng)
                        guarded_lines[rel] = guarded
                    for lineno, line in enumerate(sources_text[rel].splitlines(), 1):
                        if rx.search(line):
                            finding = _scoped_finding(
                                rule, rel, lineno, line.strip()[:120])
                            if (lineno in guarded_lines[rel]
                                    and not finding["scope"]
                                    and str(rule.get("scope", "")).lower()
                                    != "keep"):
                                # inside a conditional block: HarmonyOS never compiles this code
                                finding["severity"] = SEVERITY_DOWN.get(
                                    finding["severity"], finding["severity"])
                                finding["scope"] = "platform-guarded"
                            findings.append(finding)
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

            # guard: files matching the glob must contain **all** fragments in require,
            # and (if require_any is given) at least one of those. `when` restricts the assertion
            # to files that "already contain some fragment" - e.g. "if Q_OS_OHOS is written,
            # Q_OS_HARMONY must be too"; files with no OHOS macro at all belong to the audit tool,
            # not to this rule. Looking at files alone can only report "file present", not where
            # the guard is wrong.
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
                            # use the guard's line number: `file:0` cannot be clicked through
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
    """Whether the path is code "not compiled for the HarmonyOS target": third-party / platform-specific directory or file."""
    norm = "/" + rel.replace("\\", "/").lower().strip("/") + "/"
    if any(hint in norm for hint in THIRD_PARTY_HINTS):
        return "third-party"
    if any(hint in norm for hint in PLATFORM_EXCLUDED_HINTS):
        return "platform-excluded"
    if _file_scope(norm.strip("/")):
        return "platform-excluded"
    return ""


def _file_scope(rel: str) -> bool:
    """Whether the file itself belongs only to non-HarmonyOS platforms.

    - the file name ends with a platform token (`foo_win.cpp`, `bar_mac.mm`, `baz_xcb.cpp`)
    - Objective-C / Objective-C++ (`.m` / `.mm`): the HarmonyOS toolchain does not compile
      these; in Qt projects they only take effect on Apple platforms
    """
    name = rel.rsplit("/", 1)[-1].lower()
    if name.endswith(_OBJC_EXTS):
        return True
    stem = name.rsplit(".", 1)[0]
    tokens = [t for t in _TOKEN_SPLIT_RE.split(stem) if t]
    if any(t in PLATFORM_EXCLUDED_TOKENS for t in tokens):
        return True
    for token in PLATFORM_EXCLUDED_SUFFIXES:
        if stem.endswith("_" + token) or stem.endswith("-" + token):
            return True
    # Forms without a separator such as `win32app.cpp`: only hit when the file stem starts with
    # the token and is clearly longer than it, to avoid `wine.cpp` / `machine.cpp`
    for token in ("win32", "win64", "winrt"):
        if stem.startswith(token) and len(stem) > len(token):
            return True
    return False


def _guarded_ranges(text: str) -> List[range]:
    """Conditional blocks that hold only for non-HarmonyOS platforms (1-based line ranges).

    Code inside `#ifdef Q_OS_WIN` / `#if defined(_WIN32)` blocks does not exist in a HarmonyOS
    build; reporting it as critical just drowns out the real risks (observed: 80 of one rule's
    87 hits were inside `#ifdef Q_OS_WIN`). Counting resumes after `#else`/`#elif` - that is
    another branch.
    """
    ranges: List[range] = []
    stack: List[int] = []          # per level: #if start line; non-zero means inside an excluded section
    def _excluded(cond: str) -> bool:
        if not cond.strip():
            return False       # the #ifdef macro name is in group(2), see below
        up = cond
        if any(m in up for m in _OHOS_MACROS):
            return False
        return any(re.search(r"\b%s\b" % re.escape(m), up)
                   for m in _NON_OHOS_MACROS)

    for lineno, line in enumerate(text.splitlines(), 1):
        m = _GUARD_LINE_RE.match(line)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        if kind in ("if", "ifdef", "ifndef"):
            if kind == "if":
                cond = rest
            else:
                # the macro name of `#ifdef Q_OS_WIN` is right in rest
                name = rest.strip().split()[0] if rest.strip() else ""
                cond = ("" if kind == "ifndef" else " %s " % name)
            stack.append(lineno if _excluded(cond) else 0)
        elif kind in ("else", "elif"):
            if stack:
                # The previous branch ends here: close any open excluded section first,
                # otherwise the first branch's line numbers in
                # `#ifdef Q_OS_WIN … #elif … #endif` get overwritten and the whole block misses the downgrade.
                start = stack[-1]
                if start:
                    ranges.append(range(start, lineno))
                if kind == "elif":
                    stack[-1] = lineno if _excluded(rest) else 0
                else:
                    stack[-1] = 0
        elif kind == "endif":
            if stack:
                start = stack.pop()
                if start:
                    ranges.append(range(start, lineno + 1))
    for start in stack:                 # unclosed: count to end of file
        if start:
            ranges.append(range(start, len(text.splitlines()) + 2))
    return ranges


def _scoped_finding(rule: Dict, rel: str, line: int, snippet: str) -> Dict:
    """Downgrade by file scope: code that is not part of the OHOS build should not block G2 as critical.

    A rule can disable the downgrade with `scope: keep` (for cases that really need to report
    problems inside third-party directories).
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
