"""Migration plan generation + conservative, fully-tracked auto fixes.

Auto-fix policy (IMPORTANT):
- Q_OS_OHOS implies Q_OS_LINUX in Qt for HarmonyOS, so `#ifdef Q_OS_LINUX`
  branches ARE compiled on-device; they must be reviewed, never blindly
  widened. Such spots become manual plan steps with file:line refs.
- Only whitelisted, semantics-preserving fixes are applied automatically.
  Every applied fix is tracked by patch.ChangeTracker (changes.json +
  patches/), so the diff can always be reviewed or rolled back.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

# qmake `unix:!android:!macx` scope without `:!ohos` (golden rule B9):
# ohos also matches the unix scope and would compile wrong Linux code paths.
_UNIX_SCOPE_RE = re.compile(r"unix(:![A-Za-z_]+)*:(?!.*!ohos)")
_QT_MODULES_KB = "semantic/qt-harmonyos-modules.md"

# Fallback sets, used ONLY when knowledge/adaptation/modules.yaml is missing.
# Single source of truth: knowledge/adaptation/modules.yaml (project of
# semantic/qt-harmonyos-modules.md) - consumed via assessor.module_status.
UNSUPPORTED_MODULES = {"webengine", "webkit", "webenginecore", "webenginewidgets",
                       "dbus", "remoteobjects", "serialbus", "multimedia",
                       "multimediawidgets"}
RESTRICTED_MODULES = {"serialport", "bluetooth", "nfc", "location",
                      "positioning", "charts", "datavis3d"}


def _module_status(kb_root, module: str, version_key: str):
    """(status, ref, note) for a scanner-style module name; matrix-driven."""
    from . import assessor
    matrix = None
    if kb_root:
        matrix = assessor.load_adaptation(kb_root).get("modules")
    if matrix and matrix.get("modules"):
        status, entry = assessor.module_status(matrix, module, version_key)
        if status is not None:
            return status, (entry.get("ref") or _QT_MODULES_KB), \
                (entry.get("substitute") or "")
    if module in UNSUPPORTED_MODULES:
        return "out-of-scope", _QT_MODULES_KB, ""
    if module in RESTRICTED_MODULES:
        return "restricted", _QT_MODULES_KB, ""
    return None, _QT_MODULES_KB, ""


def build_plan(scan_info: Dict, risk_report: Dict, deps: List[Dict],
               kb_root=None) -> Dict:
    steps: List[Dict] = []
    sid = 0

    def add(title, action, refs=None, detail="", severity="medium", targets=None):
        nonlocal sid
        sid += 1
        steps.append({"id": "S%03d" % sid, "title": title, "action": action,
                      "severity": severity, "detail": detail,
                      "refs": refs or [], "targets": targets or []})

    # 1. HarmonyOS project creation
    add("Create HarmonyOS shell project (entry module + CMake glue)",
        "assisted", ["semantic/qt-harmonyos-project-structure.md",
                     "procedural/qt-app-harmonyos-migration.md"],
        "use Qt source template at OHOS_TEMPLATE_SRC "
        "(qtbase/src/harmonyos/templates) or templates/qt-ohos-app in this KB",
        severity="high")

    # 2. unsupported / restricted Qt modules
    #    (knowledge/adaptation/modules.yaml is the single source of truth)
    version_key = "qt6_12" if str(scan_info.get("qt_version_hint") or "") \
        .startswith("6") else "qt5_15"
    for mod in scan_info.get("qt_modules", []):
        status, ref, substitute = _module_status(kb_root, mod, version_key)
        if status == "out-of-scope":
            refs = [ref]
            if substitute or mod.startswith("webengine") or mod == "webkit":
                refs.append("procedural/qt-cef-ohos-dev-guide.md")
                add("Replace Qt module '%s' (%s)" % (
                        mod, substitute or "CEF is the OHOS substitute"),
                    "manual", refs, severity="critical")
            elif mod == "dbus":
                refs.append("problems/runtime-fail-libqtdbus-missing.md")
                add("Remove/replace Qt module 'dbus' (no DBus on HarmonyOS)",
                    "manual", refs, severity="critical")
            else:
                add("Remove/replace unsupported Qt module '%s'" % mod,
                    "manual", refs, severity="critical")
        elif status == "restricted":
            add("Review restricted Qt module '%s' availability on OHOS" % mod,
                "manual", [ref], severity="high")

    # 3. risk findings -> steps (critical/high become explicit steps)
    seen = set()
    for finding in risk_report.get("findings", []):
        if finding["severity"] not in ("critical", "high"):
            continue
        key = (finding["rule"], finding.get("category"))
        if key in seen:
            continue
        seen.add(key)
        add("Resolve %s risk %s (%s)" % (finding["severity"], finding["rule"],
                                         finding.get("name")),
            "manual", finding.get("kb") or [],
            "golden rules: %s; first hit: %s:%s" % (
                ",".join(finding.get("golden_rules") or []) or "-",
                finding.get("file"), finding.get("line")),
            severity=finding["severity"],
            targets=[finding.get("file")] if finding.get("file") else [])

    # 4. third-party dependencies
    for dep in deps:
        add("Provide OHOS build of third-party dependency '%s'" % dep["name"],
            "manual", ["semantic/qt-harmonyos-third-party-libs.md"],
            "status: %s" % dep.get("status", "unknown"), severity="high")

    # 5. build wiring (golden rules B1/B2/B10)
    add("Wire CMake for OHOS cross build (B1 find-root-path, B2 QPA plugin link)",
        "auto", ["semantic/qt-harmonyos-golden-rules.md",
                 "semantic/qt-harmonyos-project-structure.md"],
        severity="high")
    if scan_info.get("qrc_files") and scan_info.get("build_system") in (
            "cmake", "cmake+qmake"):
        add("Enable CMAKE_AUTORCC for qrc resources (B10)", "auto",
            ["semantic/qt-harmonyos-golden-rules.md"], severity="high")
    if scan_info.get("pro_files"):
        add("Add :!ohos to unix qmake scopes (B9)", "auto",
            ["semantic/qt-harmonyos-golden-rules.md",
             "semantic/qt-harmonyos-code-patterns.md"], severity="high")

    # 6. packaging / runtime
    add("Package HAP + sign + install + launch", "assisted",
        ["semantic/qt-harmonyos-build-run-workflow.md"], severity="high")
    add("Runtime smoke test + hilog crash check", "assisted",
        ["problems/_lookup.md"], severity="medium")

    return {
        "project": scan_info.get("name"),
        "steps": steps,
        "counts": {
            "total": len(steps),
            "auto": sum(1 for s in steps if s["action"] == "auto"),
            "assisted": sum(1 for s in steps if s["action"] == "assisted"),
            "manual": sum(1 for s in steps if s["action"] == "manual"),
        },
    }


# --------------------------------------------------------------- auto fixes

def apply_auto_fixes(scan_info: Dict, project_root, tracker) -> List[Dict]:
    """Apply whitelisted automatic fixes. Returns list of applied fix records."""
    root = Path(project_root).resolve()
    applied = []

    # FIX-B9: qmake unix scopes need :!ohos
    for rel in scan_info.get("pro_files", []):
        path = root / rel
        original = path.read_text(encoding="utf-8", errors="replace")
        fixed = _fix_unix_scope(original)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8")
            tracker.track(rel, original, fixed, "fix-b9-unix-scope",
                          "append :!ohos to unix qmake scopes (golden rule B9)")
            applied.append({"fix": "fix-b9-unix-scope", "file": rel,
                            "golden_rule": "B9"})

    # FIX-B10: CMAKE_AUTORCC for qrc resources
    if scan_info.get("qrc_files"):
        for rel in scan_info.get("cmake_files", []):
            path = root / rel
            original = path.read_text(encoding="utf-8", errors="replace")
            fixed = _fix_autorcc(original)
            if fixed != original:
                path.write_text(fixed, encoding="utf-8")
                tracker.track(rel, original, fixed, "fix-b10-autorcc",
                              "enable CMAKE_AUTORCC (golden rule B10)")
                applied.append({"fix": "fix-b10-autorcc", "file": rel,
                                "golden_rule": "B10"})
    return applied


def _fix_unix_scope(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            lines.append(line)
            continue
        # only touch condition lines that use the unix scope
        if re.search(r"(^|[\s\(\)\{\}])(unix)([:!\w]*)\s*[:{]", line):
            def repl(match):
                scope = match.group(0)
                if "!ohos" in scope:
                    return scope
                # insert :!ohos right after the unix scope chain
                return re.sub(r"(unix(?::!\w+)*)", r"\1:!ohos", scope, count=1)
            new_line = re.sub(r"unix(?::!\w+)*", repl, line)
            lines.append(new_line)
        else:
            lines.append(line)
    return "".join(lines)


def _fix_autorcc(text: str) -> str:
    if re.search(r"CMAKE_AUTORCC\s+ON", text):
        return text
    if not re.search(r"\.qrc|qt5?_add_resources|qt_add_resources", text, re.I):
        # no qrc reference in this CMake file; still enable if AUTORCC sibling exists
        if not re.search(r"CMAKE_AUTOMOC\s+ON", text):
            return text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.search(r"CMAKE_AUTOMOC\s+ON", line):
            lines.insert(i + 1, "set(CMAKE_AUTORCC ON)\n")
            return "".join(lines)
    match = re.search(r"^\s*project\s*\(", text, re.M)
    if match:
        insert_at = text.find("\n", match.end())
        if insert_at != -1:
            return (text[:insert_at + 1] +
                    "\nset(CMAKE_AUTORCC ON)  # qt-ohos-run: golden rule B10\n" +
                    text[insert_at + 1:])
    return text
