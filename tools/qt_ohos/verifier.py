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
    # 没跑过 risk_scan 就没有任何风险数据：此时"没有 critical 风险"是
    # "没检查"，不是"检查通过"。空证据只能判 NOT_RUN。
    risk = scan.get("risk") or {}
    findings = risk.get("findings")
    open_critical = [f for f in (findings or []) if f.get("severity") == "critical"]
    addressed = state.data.get("addressed_critical", [])
    unresolved = [f for f in open_critical
                  if f.get("rule") not in addressed]
    if findings is None:
        gate("G2", NOT_RUN, "risk scan not run (no scan.json risk section)")
    elif not open_critical:
        gate("G2", PASS, "no critical risks detected (%d findings scanned)"
             % len(findings))
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
    # 整包链路很长，库级进展单独记（`libcheck`），否则"这个库已经能编能链"
    # 这种事实在门禁里完全不可见，移植到一半就只能看总失败。
    libs = state.read_json("libs.json", default={}) or {}
    lib_records = libs.get("libraries") or []
    probed = sum(1 for item in lib_records if item.get("level") == "probed")
    built = sum(1 for item in lib_records if item.get("level") == "built")
    lib_note = (" | libs: %d built, %d probed" % (built, probed)) if lib_records else ""
    artifacts = build_json.get("artifacts") or []
    if status == PASS:
        gate("G4", PASS if artifacts else PARTIAL,
             "%d native artifact(s) found%s" % (len(artifacts), lib_note))
    else:
        gate("G4", NOT_RUN, "compile not PASS%s" % lib_note)

    # G5 package ---------------------------------------------------------
    pkg_status = _cmd_status(build_json, "package")
    hap = build_json.get("hap")
    if pkg_status == PASS and hap:
        g5, g5_detail = PASS, "hap: %s" % hap
    elif pkg_status == PASS:
        # 打包命令自称成功却没有产物：不能算打过包
        g5, g5_detail = FAIL, "package reported PASS but no .hap artifact found"
    else:
        g5, g5_detail = _map_cmd(pkg_status), "hap: %s" % (hap or "-")
    gate("G5", g5, g5_detail,
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
    # 只有"应用真的装上并起来了"才谈得上崩溃窗口：install/launch 不是 PASS 时
    # 一律 SKIP（旧实现会拿全设备 hilog 灌一个 PASS 出来，把"没跑起来"读成"没崩溃"）。
    crash_status = _cmd_status(runtime, "crash_check")
    markers = runtime.get("crash_markers_found") or []
    if inst_status != PASS or launch_status != PASS:
        gate("G8", SKIP,
             "install=%s launch=%s - crash window not applicable"
             % (_map_cmd(inst_status), _map_cmd(launch_status)))
    elif crash_status == "PASS" and markers:
        gate("G8", FAIL, "crash markers: %s" % ", ".join(markers),
             (runtime.get("crash_check") or {}).get("evidence", ""))
    else:
        filtered = bool((runtime.get("crash_check") or {}).get("bundle_filtered"))
        marker_note = ", ".join(markers) if markers else "none"
        if _map_cmd(crash_status) == PASS and not filtered:
            # 没配 bundle_name 时抓的是全设备缓冲，别的进程的崩溃/日志都会混进来
            gate("G8", PARTIAL,
                 "crash markers: %s (no bundle_name configured - device-wide "
                 "buffer, evidence is weak)" % marker_note,
                 (runtime.get("crash_check") or {}).get("evidence", ""))
        else:
            gate("G8", _map_cmd(crash_status),
                 "crash markers: %s%s" % (marker_note,
                                          "" if filtered else " (unfiltered)"),
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
