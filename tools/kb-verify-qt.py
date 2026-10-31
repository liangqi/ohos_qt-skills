#!/usr/bin/env python3
"""kb-verify-qt.py - verify KB Qt claims against the local Qt OHOS SDKs.

Cross-checks the machine layer and knowledge pages against real SDK contents
(see plan task T37 / optimization point 7):

  1. modules.yaml availability matrix vs actual libQt5*/libQt6* .so files
     (available -> must exist, out-of-scope/self-compile -> must not exist)
  2. QtOhosExtras API spot-check vs the Qt5 SDK headers
  3. knowledge/errors QOH refs -> problems/ pages exist

Paths come from ENV.local.md (both Windows drive-letter and /mnt/<drive>
forms are understood; paths are converted for the current OS).

Usage:  python tools/kb-verify-qt.py [--json]
Exit:   0 = all checks pass, 1 = mismatches found
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_ohos import yaml_lite  # noqa: E402

KB_ROOT = Path(__file__).resolve().parent.parent

# module-name -> Qt library class part (libQt5<Part>.so)
_LIB_NAME = {
    "opengl": "OpenGL", "openglextensions": "OpenGLExtensions",
    "ohosextras": "OhosExtras", "quickcontrols2": "QuickControls2",
    "quicktest": "QuickTest", "quicktimeline": "QuickTimeline",
    "docgallery": "DocGallery", "core5compat": "Core5Compat",
    "multimediawidgets": "MultimediaWidgets",
    "datavisualization": "DataVisualization",
    "webenginewidgets": "WebEngineWidgets", "webenginecore": "WebEngineCore",
    "multimedia": "Multimedia", "uitools": "UiTools", "serialbus": "SerialBus",
    "serialport": "SerialPort", "printsupport": "PrintSupport",
    "positioning": "Positioning", "remoteobjects": "RemoteObjects",
    "quickwidgets": "QuickWidgets", "network": "Network", "widgets": "Widgets",
}

EXTRAS_APIS = ["startAppProcess", "getCloseEventRootCause",
               "startAbilityForResult", "setWindowCornerRadius",
               "setShowWindowAsFloatWindowHint", "setWindowPrivacyMode",
               "setBundledAbilityAndQWindowBindingKeyForQWindow",
               "QOhosStartOptions"]


def _norm_path(raw: str) -> str:
    """Accept both /mnt/<drive>/... (WSL) and <drive>:\\... (Windows) forms."""
    raw = raw.strip()
    m = re.match(r"^/mnt/([a-zA-Z])/(.*)$", raw)
    if m:
        return "%s:/%s" % (m.group(1).upper(), m.group(2))
    return raw


def _env_local_paths() -> dict:
    path = KB_ROOT / "ENV.local.md"
    if not path.is_file():
        return {}
    values = {}
    for m in re.finditer(r"\|\s*`([A-Z0-9_]+)`\s*\|\s*`([^`]*)`\s*\|",
                         path.read_text(encoding="utf-8", errors="replace")):
        values[m.group(1)] = _norm_path(m.group(2))
    return values


def _lib_name(module: str, qt_major: int) -> str:
    part = _LIB_NAME.get(module)
    if part is None:
        part = "".join(w.capitalize() for w in module.split("_"))
    return "libQt%d%s.so" % (qt_major, part)


def check_modules(matrix: dict, sdk: Path, version_key: str, qt_major: int):
    """Yield (status, module, detail) mismatches for one SDK."""
    results = []
    lib_dir = sdk / "lib"
    modules = (matrix.get("modules") or {}) if isinstance(matrix, dict) else {}
    aliases = matrix.get("aliases") or {}
    seen_libs = {p.name for p in lib_dir.glob("libQt%d*.so" % qt_major)} \
        if lib_dir.is_dir() else set()
    for mod, entry in sorted(modules.items()):
        if not isinstance(entry, dict):
            continue
        status = entry.get(version_key)
        if status is None:
            continue
        lib = _lib_name(mod, qt_major)
        exists = lib in seen_libs
        if status == "available" and not exists:
            results.append(("MISMATCH", mod,
                            "matrix=available but %s/lib/%s missing" %
                            (sdk.name, lib)))
        elif status == "out-of-scope" and exists:
            results.append(("MISMATCH", mod,
                            "matrix=out-of-scope but %s/lib/%s EXISTS" %
                            (sdk.name, lib)))
        elif status == "self-compile" and exists:
            # SDK variants (e.g. Qt-full builds) may include extra modules;
            # the matrix documents the official SDK - informational only.
            results.append(("INFO", mod,
                            "matrix=self-compile but %s has %s (full build?)" %
                            (sdk.name, lib)))
    # reverse check: libs present in SDK but unknown to the matrix
    for lib in sorted(seen_libs):
        m = re.match(r"libQt\d(.+)\.so$", lib)
        if not m:
            continue
        for mod, entry in modules.items():
            if not isinstance(entry, dict):
                continue
            if _lib_name(mod, qt_major) == lib:
                break
        else:
            results.append(("INFO", lib,
                            "present in %s but not in modules.yaml" % sdk.name))
    return results


def check_extras(qt5_sdk: Path):
    results = []
    inc = qt5_sdk / "include" / "QtOhosExtras"
    if not inc.is_dir():
        return [("SKIP", "extras", "no include/QtOhosExtras in %s" % qt5_sdk)]
    text = ""
    for header in inc.glob("*.h"):
        text += header.read_text(encoding="utf-8", errors="replace")
    for api in EXTRAS_APIS:
        if api not in text:
            results.append(("MISMATCH", api,
                            "claimed in qt-ohos-extras.md but not in headers"))
    return results


def check_qoh_refs():
    results = []
    errors_dir = KB_ROOT / "knowledge" / "errors"
    for yaml_path in sorted(errors_dir.glob("QOH*.yaml")):
        try:
            data = yaml_lite.parse(yaml_path.read_text(encoding="utf-8"))
        except yaml_lite.YamlLiteError as exc:
            results.append(("MISMATCH", yaml_path.name, "parse error: %s" % exc))
            continue
        refs = (data or {}).get("refs") or {}
        for ref in refs.get("problems") or []:
            if not (KB_ROOT / ref).is_file():
                results.append(("MISMATCH", yaml_path.name,
                                "refs.problems target missing: %s" % ref))
    return results


def main(argv=None):
    emit_json = "--json" in (argv or [])
    paths = _env_local_paths()
    matrix_path = KB_ROOT / "knowledge" / "adaptation" / "modules.yaml"
    matrix = {}
    if matrix_path.is_file():
        matrix = yaml_lite.parse(matrix_path.read_text(encoding="utf-8")) or {}

    checks = []          # (status, subject, detail)
    sdk_map = []
    for env_key, version_key, major in (("QT5_15_OHOS_SDK", "qt5_15", 5),
                                        ("QT5_12_OHOS_SDK", "qt5_12", 5),
                                        ("QT6_OHOS_SDK", "qt6_12", 6)):
        raw = paths.get(env_key)
        if not raw:
            continue
        sdk = Path(raw)
        if not sdk.is_dir():
            checks.append(("SKIP", env_key, "path not found: %s" % raw))
            continue
        sdk_map.append((sdk, version_key, major))

    if not sdk_map:
        checks.append(("SKIP", "modules",
                       "no Qt OHOS SDK configured in ENV.local.md"))
    for sdk, version_key, major in sdk_map:
        checks.extend(check_modules(matrix, sdk, version_key, major))
        if major == 5:
            checks.extend(check_extras(sdk))
    checks.extend(check_qoh_refs())

    mismatches = [c for c in checks if c[0] == "MISMATCH"]
    infos = [c for c in checks if c[0] == "INFO"]
    skips = [c for c in checks if c[0] == "SKIP"]

    if emit_json:
        print(json.dumps({"mismatches": mismatches, "info": infos,
                          "skip": skips}, ensure_ascii=False, indent=2))
    else:
        print("Qt claim verification (vs local SDKs)")
        print("======================================")
        for status, subject, detail in checks:
            print("  %-9s %-28s %s" % (status, subject[:28], detail))
        print()
        print("mismatch=%d info=%d skip=%d" %
              (len(mismatches), len(infos), len(skips)))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
