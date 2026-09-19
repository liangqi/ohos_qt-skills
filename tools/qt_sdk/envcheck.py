"""SV0 environment check + ENV.local.md bridge.

Python replacement of detect-env.sh / verify-env.sh (build-related part).
Reads KB_ROOT/ENV.local.md (product of skills/kb-init) and checks:

- Qt source tree (qtbase/ + qtohosextras/ submodules)
- OHOS SDK native toolchain (llvm/bin)
- build tools: git, cmake; on Windows also mingw32-make + perl
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

KB_ROOT = Path(__file__).resolve().parent.parent.parent

ENV_LOCAL = KB_ROOT / "ENV.local.md"

# ENV.local.md table row: | `KEY` | `value` |
_ENV_ROW_RE = re.compile(r"\|\s*`([A-Z0-9_]+)`\s*\|\s*`([^`]*)`\s*\|")

# path variables this CLI understands (first existing wins per group)
SRC_VARS = ["QT5_15_SRC", "QT5_12_SRC", "QT6_DEV_SRC"]
SDK_VARS = ["QT5_15_OHOS_SDK", "QT5_12_OHOS_SDK", "QT6_OHOS_SDK"]


def parse_env_local() -> Dict[str, str]:
    """Extract | `VAR` | `value` | pairs from ENV.local.md."""
    if not ENV_LOCAL.is_file():
        return {}
    values: Dict[str, str] = {}
    for match in _ENV_ROW_RE.finditer(
            ENV_LOCAL.read_text(encoding="utf-8", errors="replace")):
        key, val = match.group(1), match.group(2).strip()
        if val:
            values[key] = val
    return values


def _first_existing(values: Dict[str, str], keys: List[str]) -> str:
    for key in keys:
        val = values.get(key, "")
        if val and Path(val).exists():
            return val
    for key in keys:                      # fall back to first non-empty
        if values.get(key):
            return values[key]
    return ""


def default_paths() -> Dict[str, str]:
    """Bridge ENV.local.md into the forge env (source of truth for paths)."""
    values = parse_env_local()
    return {
        "qt_src": _first_existing(values, SRC_VARS),
        "sdk_root": _first_existing(values, SDK_VARS),
        "ohos_sdk_native": values.get("OHOS_SDK_NATIVE", ""),
        "mingw_root": values.get("MINGW_ROOT", ""),
        "perl_root": values.get("PERL_ROOT", ""),
    }


def _tool(name: str, extra_dirs: List[str] = None) -> str:
    """Resolve a tool, also looking into extra dirs (MINGW_ROOT/PERL_ROOT)."""
    found = shutil.which(name)
    if found:
        return found
    for base in extra_dirs or []:
        for sub in ("bin", ""):
            cand = Path(base) / sub / (name + (".exe" if os.name == "nt"
                                               else ""))
            if cand.is_file():
                return str(cand)
    return ""


def check(qt_src: str = "", ohos_sdk_native: str = "") -> Dict:
    """Run the SV0 checks. Returns a dict with `checks` list + `ok` flag."""
    values = default_paths()
    qt_src = qt_src or values["qt_src"]
    native = ohos_sdk_native or values["ohos_sdk_native"]
    extra = [d for d in (values["mingw_root"], values["perl_root"]) if d]

    checks: List[Dict] = []

    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "ok": ok, "detail": detail})

    # 1. Qt source tree
    src = Path(qt_src) if qt_src else None
    if src and (src / "qtbase").is_dir():
        extras_ok = (src / "qtohosextras").is_dir()
        add("qt_source", True, str(src))
        add("qt_submodules", extras_ok,
            "qtohosextras/ present" if extras_ok else
            "missing qtohosextras/ - run: git submodule update --init --recursive")
    else:
        add("qt_source", False,
            "no Qt source tree (set via `config set qt_src <path>`; "
            "acquire with `src-clone`)")

    # 2. OHOS SDK native
    native_path = Path(native) if native else None
    llvm_bin = native_path / "llvm" / "bin" if native_path else None
    clang = None
    if llvm_bin and llvm_bin.is_dir():
        clang = _tool("clang", [str(native_path / "llvm")])
    add("ohos_sdk_native", bool(llvm_bin and llvm_bin.is_dir()),
        str(native) if native else "OHOS_SDK_NATIVE not set in ENV.local.md")

    # 3. build tools
    add("git", bool(_tool("git")), _tool("git"))
    add("cmake", bool(_tool("cmake")), _tool("cmake"))
    if os.name == "nt":
        mingw = _tool("mingw32-make", extra)
        perl = _tool("perl", extra)
        add("mingw32_make", bool(mingw), mingw or
            "install llvm-mingw / set MINGW_ROOT in ENV.local.md")
        add("perl", bool(perl), perl or
            "install Strawberry Perl / set PERL_ROOT in ENV.local.md")
    else:
        make = _tool("make") or _tool("gmake")
        add("make", bool(make), make)
        # qtdeclarative invokes `python` (not `python3`) from its qmake
        # scripts (QOH038). The forge CLI auto-shims python -> python3 in
        # build_env (tools/qt_sdk/building.py), so only python3 itself is
        # a hard requirement here.
        py3 = _tool("python3") or _tool("python")
        py_alias = _tool("python")
        add("python3", bool(py3), py3 or
            "install python3 - qtdeclarative cannot build without it")
        add("python_alias", True,
            py_alias or
            "`python` alias not found - the CLI will auto-shim it "
            "(.qtsdk/pyshim) or: ln -s /usr/bin/python3 /usr/local/bin/python")

    return {"checks": checks,
            "ok": all(c["ok"] for c in checks),
            "resolved": {"qt_src": qt_src, "ohos_sdk_native": native,
                         "clang": clang or ""}}


def git_available() -> bool:
    return bool(_tool("git"))


def run_git(args, cwd) -> subprocess.CompletedProcess:
    """Small helper for read-only git queries (never raises)."""
    return subprocess.run(["git"] + args, cwd=str(cwd),
                          capture_output=True, text=True,
                          errors="replace")
