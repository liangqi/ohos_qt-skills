"""Third-party dependency resolution.

Design (per the porting plan): do NOT re-implement the whole third-party
build ecosystem here. `build_in_harmonyos` already owns library builds;
this module detects dependencies, reports their status, and can delegate
to an external resolver when configured:

    set OHC_RUN=python /path/to/build_in_harmonyos/tools/ohc-run.py

Without a resolver, every detected dependency is reported as
`requires-build` with a pointer to semantic/qt-harmonyos-third-party-libs.md.
"""

from __future__ import annotations

import os
from typing import Dict, List

from .scanner import THIRD_PARTY_HINTS

# deps that the OHOS system / Qt SDK typically already provides
SYSTEM_PROVIDED = {"icu", "sqlite", "zlib"}

KB_REF = "semantic/qt-harmonyos-third-party-libs.md"


def analyze_dependencies(scan_info: Dict, state=None) -> List[Dict]:
    deps: List[Dict] = []
    for hint in scan_info.get("third_party_hints", []):
        name = hint["name"]
        if name in SYSTEM_PROVIDED:
            status, note = "likely-available", (
                "usually provided by OHOS system or Qt SDK - verify ABI/arch")
        else:
            status, note = "requires-build", (
                "cross-compile for aarch64 OHOS required (musl libc, no glibc)")
        deps.append({
            "name": name,
            "evidence": hint.get("evidence", []),
            "status": status,
            "note": note,
            "kb": KB_REF,
        })

    resolver = os.environ.get("OHC_RUN")
    if resolver and state is not None:
        for dep in deps:
            result = state.run_cmd(
                "%s resolve-deps %s" % (resolver, dep["name"]),
                label="resolve-dep-%s" % dep["name"], timeout=120)
            if result.status == "PASS":
                dep["external_resolver"] = "ok"
                if "available" in result.stdout.lower():
                    dep["status"] = "available"
            else:
                dep["external_resolver"] = "unavailable (%s)" % result.status
    elif resolver is None:
        for dep in deps:
            dep["external_resolver"] = "not configured (set OHC_RUN to the " \
                "build_in_harmonyos ohc-run.py for artifact reuse)"
    return deps
