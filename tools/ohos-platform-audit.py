#!/usr/bin/env python3
"""Platform-layer porting audit - answers "what is this application's platform abstraction still missing".

    python tools/ohos-platform-audit.py <app>/SourceFiles/platform
    python tools/ohos-platform-audit.py <app>/SourceFiles/platform --json
    python tools/ohos-platform-audit.py <dir> --undefined undef.txt

Why it is needed: a desktop application's platform layer has **two dispatch mechanisms**;
watching only one covers at most half.

  1. **Header dispatch**: `platform_*.h` ends in an `#ifdef` chain whose trailing `#else`
     falls through to the Linux implementation. A guard that only names `Q_OS_OHOS` is
     **never true** on a Qt 6.x kit (6.x only defines `Q_OS_HARMONY`), so it silently
     picks up the D-Bus/X11 implementation.
  2. **Source dispatch**: `platform_*.h` has no `#ifdef` at all; the build picks the `.cpp`
     by path. Such headers need no changes; it is enough that `ohos/xxx_ohos.cpp` is
     selected by the build.

Exit codes: 0 = every header-dispatch file accepts both OHOS macros; 1 = some file only
accepts one macro; 2 = usage/path error. In `--undefined` mode, 0 = no symbol was found
that "nobody implements at all".

Implementation constraints: standard library only, no third-party dependencies, identical
on Windows/macOS/Linux.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADER_PREFIX = "platform_"
OHOS_MACROS = ("Q_OS_OHOS", "Q_OS_HARMONY", "__OHOS__")
# A header-dispatch guard must hold on both kinds of kit: Qt 5.15 provides Q_OS_OHOS +
# Q_OS_HARMONY, Qt 6.12+ provides only Q_OS_HARMONY. `__OHOS__` is a compiler-predefined
# macro present in both generations, so "using it" also counts as complete.
# Header-dispatch detection: any #if/#ifdef/#elif line mentions a Q_OS_* macro, or an
# include of a per-platform implementation directory. The old criterion required "at least
# two distinct Q_OS_ macros", so files that only wrote `#ifdef Q_OS_OHOS` (exactly the kind
# we want to catch) were classified as source dispatch and the audit simply PASSed - the
# criterion must not be stricter than the thing being checked.
# `__OHOS__` is a compiler macro defined by both Qt 5 and 6; guards using it are header dispatch too.
OS_BRANCH_RE = re.compile(
    r"^\s*#\s*(?:el)?if(?:def)?\s+.*\b(?:Q_OS_[A-Z_]+|__OHOS__)", re.M)
ALT_DIR_RE = re.compile(r'#\s*include\s*[<"][^">]*\b(?:linux|windows|macos|darwin|win32)/')
UNDEF_RE = re.compile(r"undefined (?:symbol|reference)[: ]+[`'\"]?([A-Za-z_][\w:~<>]*)")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def classify(text: str) -> str:
    """header = the header is selected by an #ifdef chain; source = the build selects the .cpp by path.

    Criterion: as soon as there is Q_OS_* conditional compilation, or an include of a
    per-platform implementation directory, this header performs platform dispatch - even if
    it only accepts one macro (which is exactly the defect to report).
    """
    if OS_BRANCH_RE.search(text):
        return "header"
    if ALT_DIR_RE.search(text):
        return "header"
    return "source"


def audit(root: Path, strict: bool = False) -> dict:
    headers = sorted(p for p in root.glob(HEADER_PREFIX + "*.h") if p.is_file())
    header_dispatch, source_dispatch, missing, no_ohos = [], [], [], []
    for path in headers:
        text = read_text(path)
        kind = classify(text)
        present = [m for m in OHOS_MACROS if m in text]
        # Complete = accepts the macro names of both kit generations. Q_OS_OHOS alone is dead
        # code on Qt 6, Q_OS_HARMONY alone is dead code on a Qt 5.15 kit; report both.
        has_all = "__OHOS__" in present or (
            "Q_OS_OHOS" in present and "Q_OS_HARMONY" in present)
        if kind == "header":
            header_dispatch.append({"file": path.name, "ok": has_all,
                                    "macros": present})
            if not present:
                # a dispatch chain that never mentions OHOS: not "one macro short" but "one branch short"
                no_ohos.append(path.name)
            elif not has_all:
                missing.append(path.name)
        else:
            source_dispatch.append(path.name)

    ohos_dir = root / "ohos"
    ohos_files = sorted(p.name for p in ohos_dir.iterdir() if p.is_file()) \
        if ohos_dir.is_dir() else []

    # Source-dispatch files: the header has no branch to change; the implementation must be
    # selected by path by the build, so assert that `ohos/` really has a matching implementation
    # (matched on the core name with the platform_ prefix stripped).
    unimplemented = []
    if strict:
        blob = "\n".join(ohos_files).lower()
        for name in source_dispatch:
            core = name[len(HEADER_PREFIX):-len(".h")].lower()
            if core and core not in blob:
                unimplemented.append(name)

    return {
        "root": str(root),
        "header_dispatch": header_dispatch,
        "source_dispatch": source_dispatch,
        "missing_both_macros": missing,
        "no_ohos_branch": no_ohos,
        "ohos_implementations": ohos_files,
        "ohos_dir_exists": ohos_dir.is_dir(),
        "source_dispatch_unimplemented": unimplemented,
    }


def symcheck(root: Path, undefined_file: Path) -> dict:
    """Infer "which platform symbols nobody implements yet" from the link-time undefined symbol list.

    The criterion is deliberately conservative: a symbol name (with parameters and qualifiers
    stripped) that appears in any implementation file under `ohos/` counts as "owned";
    otherwise it is listed as possibly missing. It does not replace the linker; it only
    automates narrowing down "which of the one or two hundred undefined symbols belong to the
    platform layer".
    """
    text = read_text(undefined_file)
    symbols = sorted(set(UNDEF_RE.findall(text)))
    ohos_dir = root / "ohos"
    blob = "\n".join(read_text(p) for p in ohos_dir.iterdir()
                     if p.is_file()) if ohos_dir.is_dir() else ""
    platform_level = []
    for sym in symbols:
        base = sym.split("(")[0].split("::")[-1].strip()
        if not base:
            continue
        if base in blob:
            continue
        platform_level.append(sym)
    return {
        "undefined_total": len(symbols),
        "platform_level_missing": platform_level,
        "ohos_dir": str(ohos_dir),
    }


def render(report: dict) -> str:
    lines = []
    hd = report["header_dispatch"]
    lines.append("header dispatch (%d), all must name Q_OS_OHOS + Q_OS_HARMONY "
                 "(or __OHOS__):" % len(hd))
    for item in hd:
        lines.append("  %-42s %s" % (item["file"],
                                     "OK" if item["ok"] else "MISSING"))
    lines.append("")
    lines.append("source dispatch (%d), no #ifdef chain by design:" %
                 len(report["source_dispatch"]))
    for name in report["source_dispatch"]:
        lines.append("  %s" % name)
    lines.append("")
    if report["ohos_dir_exists"]:
        lines.append("ohos/ implementations (%d):" %
                     len(report["ohos_implementations"]))
    else:
        lines.append("ohos/ directory does not exist")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Platform-layer porting audit: header/source dispatch classification + dual OHOS macro assertion")
    parser.add_argument("platform_dir", help="the application's platform directory (e.g. SourceFiles/platform)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--undefined", metavar="FILE",
                        help="link log file: infer platform symbols still missing an implementation")
    parser.add_argument("--strict", action="store_true",
                        help="source-dispatch files must also have a matching implementation under ohos/, otherwise fail")
    args = parser.parse_args()

    root = Path(args.platform_dir)
    if not root.is_dir():
        print("not a directory: %s" % root, file=sys.stderr)
        return 2

    report = audit(root, strict=args.strict)
    exit_code = 1 if (report["missing_both_macros"]
                      or report["source_dispatch_unimplemented"]) else 0
    if args.strict and report["no_ohos_branch"]:
        exit_code = 1

    undef_report = None
    if args.undefined:
        undef_file = Path(args.undefined)
        if not undef_file.is_file():
            print("not a file: %s" % undef_file, file=sys.stderr)
            return 2
        undef_report = symcheck(root, undef_file)
        report["undefined"] = undef_report
        if undef_report["platform_level_missing"]:
            exit_code = 1

    if args.strict and not report["ohos_dir_exists"]:
        report["source_dispatch_unimplemented"] = list(report["source_dispatch"])
        exit_code = 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
        if undef_report is not None:
            lines = report["header_dispatch"]
            print("")
            print("undefined symbols: %d total, %d with no ohos/ implementation"
                  % (undef_report["undefined_total"],
                     len(undef_report["platform_level_missing"])))
            for sym in undef_report["platform_level_missing"][:40]:
                print("  missing: %s" % sym)
        print("")
        if report["source_dispatch_unimplemented"]:
            print("FAIL: %d source-dispatch header(s) have no ohos/ implementation:"
                  % len(report["source_dispatch_unimplemented"]))
            for name in report["source_dispatch_unimplemented"]:
                print("  %s" % name)
        if report["no_ohos_branch"]:
            print("WARN: %d header-dispatch file(s) never mention OHOS "
                  "(add an OHOS branch, or confirm they are source-dispatched):"
                  % len(report["no_ohos_branch"]))
            for name in report["no_ohos_branch"]:
                print("  %s" % name)
        if report["missing_both_macros"]:
            print("FAIL: %d header(s) do not accept both OHOS macros:"
                  % len(report["missing_both_macros"]))
            for name in report["missing_both_macros"]:
                print("  %s" % name)
        else:
            print("PASS: every header-dispatch platform file accepts both OHOS macros")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
