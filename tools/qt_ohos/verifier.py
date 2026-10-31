"""Verification Gates G0-G12.

Core principle: success is decided by the tool, not by the LLM.
"Compiled successfully" is NOT "migration succeeded".

    success = compile==PASS && package==PASS && install==PASS
              && launch==PASS && crash_check==PASS

Gate table:

    G0  Environment   SDK / clang / Qt SDK / DevEco configured
    G1  Project       build files + migration plan exist
    G2  Compatibility critical risks addressed (no open critical findings)
    G3  Compile       C++ compile PASS
    G4  Link/Artifact build artifacts (.so) present
    G5  Package       HAP produced
    G6  Install       hdc install PASS
    G7  Launch        ability start PASS
    G8  Crash         no crash markers within N seconds
    G9  UI            window creation evidence in device log
    G10 Smoke         basic interaction (manual/assisted)
    G11 Feature       core feature tests (manual)
    G12 Regression    baseline comparison (manual)

Overall: PASS only if G0-G8 all PASS; PARTIAL if G3-G5 PASS; else FAIL.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from .builder import env_of

GATE_ORDER = ["G%d" % i for i in range(13)]
GATE_TITLES = {
    "G0": "Environment", "G1": "Project", "G2": "Compatibility",
    "G3": "Compile", "G4": "Link/Artifact", "G5": "Package",
    "G6": "Install", "G7": "Launch", "G8": "Crash",
    "G9": "UI", "G10": "Smoke", "G11": "Feature", "G12": "Regression",
}
PASS = "PASS"
FAIL = "FAIL"
PARTIAL = "PARTIAL"
NOT_RUN = "NOT_RUN"
SKIP = "SKIP"


def _cmd_status(section: Dict, key: str) -> str:
    record = (section or {}).get(key) or {}
    return str(record.get("status", NOT_RUN))


def evaluate(state) -> Tuple[Dict[str, Dict], str]:
    gates: Dict[str, Dict] = {}

    def gate(gid: str, status: str, detail: str = "", evidence: str = ""):
        gates[gid] = {"status": status, "title": GATE_TITLES[gid],
                      "detail": detail, "evidence": evidence}

    env = env_of(state)
    scan = state.read_json("scan.json", default={}) or {}
    plan = state.read_json("migration-plan.json", default=None)
    build_json = state.read_json("build.json", default={}) or {}
    runtime = state.read_json("runtime.json", default={}) or {}

    # G0 environment ---------------------------------------------------
    missing = []
    if not env.get("qt_sdk_prefix") and not env.get("build_command"):
        missing.append("qt_sdk_prefix or build_command")
    if env.get("qt_sdk_prefix") and not Path(env["qt_sdk_prefix"]).exists():
        missing.append("qt_sdk_prefix path does not exist")
    if shutil.which(env.get("cmake", "cmake")) is None and not env.get("build_command"):
        missing.append("cmake not on PATH")
    gate("G0", FAIL if missing else PASS,
         "missing: %s" % ", ".join(missing) if missing else "environment configured",
         "env.json")

    # G1 project ---------------------------------------------------------
    has_build_files = bool(scan.get("cmake_files") or scan.get("pro_files"))
    gate("G1", PASS if has_build_files and plan else FAIL,
         "build files: %s, plan: %s" % (has_build_files, bool(plan)), "scan.json")

    # G2 compatibility ---------------------------------------------------
    risk = scan.get("risk") or {}
    open_critical = [f for f in risk.get("findings", [])
                     if f.get("severity") == "critical"]
    addressed = state.data.get("addressed_critical", [])
    unresolved = [f for f in open_critical
                  if f.get("rule") not in addressed]
    if not open_critical:
        gate("G2", PASS, "no critical risks detected")
    elif unresolved:
        gate("G2", FAIL, "%d unresolved critical risks: %s" % (
            len(unresolved),
            ", ".join(sorted({str(u.get("rule")) for u in unresolved}))),
            "scan.json")
    else:
        gate("G2", PASS, "all critical risks addressed")

    # G3 compile ---------------------------------------------------------
    status = _cmd_status(build_json, "compile")
    gate("G3", _map_cmd(status), "compile: %s" % status,
         (build_json.get("compile") or {}).get("evidence", ""))

    # G4 artifacts -------------------------------------------------------
    artifacts = build_json.get("artifacts") or []
    if status == PASS:
        gate("G4", PASS if artifacts else PARTIAL,
             "%d native artifact(s) found" % len(artifacts))
    else:
        gate("G4", NOT_RUN, "compile not PASS")

    # G5 package ---------------------------------------------------------
    pkg_status = _cmd_status(build_json, "package")
    hap = build_json.get("hap")
    gate("G5", PASS if (pkg_status == PASS and hap) else _map_cmd(pkg_status),
         "hap: %s" % (hap or "-"),
         (build_json.get("package") or {}).get("evidence", ""))

    # G6 install ---------------------------------------------------------
    inst_status = _cmd_status(runtime, "install")
    gate("G6", _map_cmd(inst_status), "hdc install: %s" % inst_status,
         (runtime.get("install") or {}).get("evidence", ""))

    # G7 launch ----------------------------------------------------------
    launch_status = _cmd_status(runtime, "launch")
    gate("G7", _map_cmd(launch_status), "aa start: %s" % launch_status,
         (runtime.get("launch") or {}).get("evidence", ""))

    # G8 crash -----------------------------------------------------------
    crash_status = _cmd_status(runtime, "crash_check")
    markers = runtime.get("crash_markers_found") or []
    gate("G8", _map_cmd(crash_status),
         "crash markers: %s" % (", ".join(markers) if markers else "none"),
         (runtime.get("crash_check") or {}).get("evidence", ""))

    # G9 UI ----------------------------------------------------------------
    hilog_log = (runtime.get("crash_check") or {}).get("evidence", "")
    ui_seen = runtime.get("ui_window_seen", False)
    if launch_status != PASS:
        gate("G9", NOT_RUN, "launch not PASS")
    elif ui_seen:
        gate("G9", PASS, "window creation marker seen in device log", hilog_log)
    else:
        gate("G9", PARTIAL,
             "no explicit window marker captured; verify visually", hilog_log)

    # G10-G12 manual gates --------------------------------------------------
    # recorded via `smoke --result` (G10) or `mark-gate G10|G11|G12` (all three)
    smoke = runtime.get("smoke")
    manual = state.data.get("manual_gates") or {}
    gate("G10", _map_cmd(str((smoke or {}).get("status", NOT_RUN)))
         if smoke else _map_cmd(str((manual.get("G10") or {}).get("status", NOT_RUN))),
         (manual.get("G10") or {}).get("note") or "basic interaction test")
    for gid in ("G11", "G12"):
        rec = manual.get(gid) or {}
        gate(gid, _map_cmd(str(rec.get("status", NOT_RUN))),
             rec.get("note") or GATE_TITLES[gid].lower() + " (manual)")

    overall = _overall(gates)
    return gates, overall


def _map_cmd(status: str) -> str:
    return {
        "PASS": PASS, "FAIL": FAIL, "TIMEOUT": FAIL,
        "SKIP": SKIP, "NOT_RUN": NOT_RUN,
    }.get(status, NOT_RUN)


def _overall(gates: Dict[str, Dict]) -> str:
    statuses = [gates[g]["status"] for g in GATE_ORDER]
    core = statuses[0:9]          # G0..G8
    if all(s == PASS for s in core):
        return PASS
    if statuses[3] == PASS and statuses[5] in (PASS, PARTIAL):
        return PARTIAL            # compiled (+ packaged) but not fully verified
    return FAIL


def render(gates: Dict[str, Dict], overall: str) -> str:
    lines = ["Gate  Title             Status     Detail",
             "----  ----------------  ---------  --------------------------"]
    for gid in GATE_ORDER:
        info = gates[gid]
        lines.append("%-5s %-17s %-10s %s" % (
            gid, info["title"], info["status"], info["detail"][:60]))
    lines.append("")
    lines.append("Result: %s" % overall)
    if overall != PASS:
        lines.append("NOTE: tool verdict only - an LLM must not report migration "
                     "success when this result is not PASS.")
    return "\n".join(lines)


def mark_critical_addressed(state, rule_ids: List[str]) -> None:
    addressed = set(state.data.get("addressed_critical", []))
    addressed.update(rule_ids)
    state.data["addressed_critical"] = sorted(addressed)
    state.save()
