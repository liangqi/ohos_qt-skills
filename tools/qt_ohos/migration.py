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


KIT_MODULE_RE = re.compile(r"^Qt6([A-Za-z][A-Za-z0-9]*)$")


def kit_modules(env: Dict) -> set:
    """Which Qt modules are actually installed in the kit (`<kit>/lib/cmake/Qt6<Module>/`).

    No-op "provide module X" steps in the plan all came from never asking what the kit actually provides.
    """
    prefix = (env or {}).get("qt_sdk_prefix")
    if not prefix:
        return set()
    base = Path(prefix).expanduser() / "lib" / "cmake"
    if not base.is_dir():
        return set()
    names = set()
    for entry in base.iterdir():
        match = KIT_MODULE_RE.match(entry.name)
        if match:
            names.add(match.group(1).lower())
    return names


def build_plan(scan_info: Dict, risk_report: Dict, deps: List[Dict],
               kb_root=None, env: Optional[Dict] = None) -> Dict:
    """Turn scan results into an executable step table.

    Ordered by the bottlenecks observed in practice: environment (kit / SDK / hvigor / signing)
    first, module replacement in the middle, packaging and installation last. Early versions put
    "review Charts" and "replace CEF with webengine" first, while what actually got stuck was the
    toolchain and hvigor - those two steps were no-ops.
    """
    steps: List[Dict] = []
    sid = 0
    env = env or {}
    available = kit_modules(env)
    required_map = scan_info.get("qt_module_required") or {}

    def add(title, action, refs=None, detail="", severity="medium", targets=None):
        nonlocal sid
        sid += 1
        steps.append({"id": "S%03d" % sid, "title": title, "action": action,
                      "severity": severity, "detail": detail,
                      "refs": refs or [], "targets": targets or []})

    # 1. environment first: without toolchain / hvigor / signing, none of the later steps can run
    add("Run environment doctor (kit / SDK / hvigor / device)", "auto",
        ["procedural/qt6-ohos-windows-cli-deploy.md",
         "semantic/qt-harmonyos-build-run-workflow.md"],
        "`qt-ohos-run doctor`: every failure comes with a config set fix; Qt6 needs a host kit"
        " (qt_host_sdk) + the OHOS native SDK (ohos_sdk_native)",
        severity="critical")
    add("Align SDK/toolchain and hvigor five-piece set", "auto",
        ["procedural/qt6-ohos-windows-cli-deploy.md",
         "procedural/qt6-ohos-manual-deploy.md"],
        "QT_HARMONYOS_HVIGOR absolute path, JAVA_HOME, DEVECO_SDK_HOME, "
        "HVIGOR_USER_HOME, npm_config_cache; align compatibleSdkVersion with the SDK",
        severity="critical")
    add("Prepare signing materials and device chain", "assisted",
        ["procedural/qt6-ohos-windows-cli-deploy.md",
         "semantic/qt-harmonyos-third-party-libs.md"],
        "`qt-ohos-run sign` (devecocli) or manual six-piece-set configuration; "
        "`hdc list targets` must list the device",
        severity="high")

    # 2. HarmonyOS project creation
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
        if not required_map.get(mod, True):
            continue          # no steps for soft dependencies, otherwise the plan is full of no-ops
        status, ref, substitute = _module_status(kb_root, mod, version_key)
        if status == "out-of-scope":
            if mod in available and mod not in ("webengine", "webenginecore",
                                                "webenginewidgets", "webkit"):
                continue      # the kit already has this module; no "provide it" step
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
        if dep.get("name", "").lower() in available:
            continue          # third-party libraries bundled with the kit need not be provided separately
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
    add("Package HAP via Qt6 _make_hap / harmonydeployqt6 (not a bare command)",
        "auto", ["procedural/qt6-ohos-windows-cli-deploy.md"],
        "`package` has two built-in paths; `package_command` is only an escape hatch",
        severity="high")
    add("Package HAP + sign + install + launch", "assisted",
        ["semantic/qt-harmonyos-build-run-workflow.md"], severity="high")
    add("Runtime smoke test + hilog crash check", "assisted",
        ["problems/_lookup.md"], severity="medium")

    return {
        "project": scan_info.get("name"),
        "qt_kit_modules": sorted(available),
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


# Candidate fix list: auto-fix only covers the two "allowlisted + confident" items (B9 unix
# scope, B10 AUTORCC), so pure-CMake / no-qrc projects often get no change at all. In that case
# emit **candidates** (file + line + why) and let a human/agent decide - "not confident enough to
# auto-change" must not mean saying nothing (tdesktop in practice: the patch phase only printed
# no automatic fixes applicable, while what really needed changing was a few places in CMake).
_FIX_CANDIDATES = [
    {
        "id": "cand-shared-lib",
        "rule": "B1",
        "why": "Qt HarmonyOS apps must be built as SHARED: the QPA plugin needs main after dlopen",
        # qt_add_executable excluded: Qt6 maps it to SHARED on HarmonyOS, reporting it would only mislead
        "pattern": re.compile(
            r"\badd_executable\s*\(|\badd_library\s*\([^)]*\bSTATIC\b"),
        "fix": "change to add_library(<tgt> SHARED ...); projects using qt_add_executable"
               " are already in the right form, just confirm the output is lib*.so",
    },
    {
        "id": "cand-no-undefined",
        "rule": "B2",
        "why": "the toolchain enforces -Wl,--no-undefined; unresolved symbols SIGSEGV on the device "
               "in the find_sym2 phase",
        "pattern": re.compile(
            r"\badd_link_options\s*\(|\btarget_link_options\s*\(|"
            r"-Wl,--no-undefined|--allow-shlib-undefined"),
        "fix": "add target_link_options(<tgt> PRIVATE -Wl,--no-undefined); "
               "--allow-shlib-undefined has no effect on the HarmonyOS toolchain",
        "evidence": "use verify's G13 to check for unresolved symbols",
    },
    {
        "id": "cand-xcb-dbus",
        "rule": "R003/R001",
        "why": "X11(xcb)/DBus are not provided on HarmonyOS; needs a platform-layer replacement or exclusion via conditional compilation",
        "pattern": re.compile(
            r"find_package\s*\(\s*(X11|xcb|XCB|DBus|Qt6?\s+COMPONENTS[^)]*\b"
            r"(dbus|xcb))|pkg_check_modules\s*\([^)]*\b(xcb|dbus)",
            re.I),
        "fix": "move these dependencies into an `if(NOT OHOS)` branch, or switch to Qt's own "
               "QtDBus/QtNetwork equivalents",
    },
    {
        "id": "cand-qt-host-tools",
        "rule": "K-4",
        "why": "cross-compiling requires running moc/rcc/uic on the host; without a usable host kit, configure "
               "fails at Qt6::moc",
        "pattern": re.compile(r"QT_HOST_PATH|qt.toolchain.cmake|CMAKE_TOOLCHAIN_FILE"),
        "fix": "config set qt_host_sdk <host kit>; the builder then passes "
               "QT_HOST_PATH and QT_CHAINLOAD_TOOLCHAIN_FILE automatically",
    },
    {
        "id": "cand-rcc-write",
        "rule": "K-3",
        "why": "on some Windows environments the host rcc.exe cannot write its output file (build output directory permissions/"
               "path too long)",
        "pattern": re.compile(r"CMP0071|qt_add_resources|\.qrc", re.I),
        "fix": "move the qrc output directory to a short path inside the project, or use qt-ohos-run build "
               "--record-only to register externally built artifacts",
    },
    {
        "id": "cand-cxx20",
        "rule": "K-6",
        "why": "HarmonyOS libc++ 15 lacks std::ranges algorithms, <=>, jthread, stop_token, "
               "atomic_ref, make_unique_for_overwrite",
        "pattern": re.compile(
            r"CXX_STANDARD\s+2[03]|std::ranges|std::jthread|std::stop_token|"
            r"std::atomic_ref|std::make_unique_for_overwrite|<=>"),
        "fix": "lower the C++ standard to 17, or add compatibility headers to the project (see problems/"
               "build-clang15-libcpp15-cpp20-gaps.md)",
    },
]


def fix_candidates(scan_info: Dict, project_root) -> List[Dict]:
    """Options beyond auto-fix: scan file by file and report "where + why + how to change".

    **Read-only** scan, no files are modified; hits are grouped per file, at most the first 3 each.
    """
    root = Path(project_root).resolve()
    out: List[Dict] = []
    files = list(scan_info.get("cmake_files") or [])
    files += [f for f in (scan_info.get("pro_files") or [])
              if f not in files]
    for cand in _FIX_CANDIDATES:
        hits: List[Dict] = []
        for rel in files:
            path = root / rel
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if cand["pattern"].search(line):
                    hits.append({"file": rel, "line": i,
                                 "snippet": line.strip()[:120]})
                    break
            if len(hits) >= 3:
                break
        if hits:
            item = {"id": cand["id"], "rule": cand["rule"],
                    "why": cand["why"], "fix": cand["fix"], "hits": hits}
            if cand.get("evidence"):
                item["evidence"] = cand["evidence"]
            out.append(item)
    return out


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
