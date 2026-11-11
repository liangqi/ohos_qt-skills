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

import datetime
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
    cmake = env.get("cmake", "cmake")
    if shutil.which(cmake) is None and not env.get("build_command"):
        # 交叉编译机常把 cmake 装在非 PATH 位置：这里给出可执行的修法，
        # 而不是只报一句 "not on PATH"
        missing.append("cmake not on PATH (config set cmake <绝对路径>)")
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
    records = addressed_critical_records(state)
    unresolved, no_evidence = [], []
    for item in open_critical:
        rid = str(item.get("rule"))
        rec = records.get(rid)
        if rec is None:
            unresolved.append(item)
        elif not str(rec.get("evidence") or "").strip():
            # 标记过但没有证据：等价于"标过去了"，不能算已处理
            no_evidence.append(rid)
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
    elif no_evidence:
        gate("G2", FAIL, "%d critical risk(s) marked addressed without evidence: "
             "%s（用 mark-risk --rule <id> --evidence <改动位置/验证方式> 补证据）"
             % (len(no_evidence), ", ".join(sorted(set(no_evidence)))),
             ".qt-ohos/state.json")
    else:
        gate("G2", PASS, "all critical risks addressed (with evidence)",
             ".qt-ohos/state.json")

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
    project_root = Path(getattr(state, "project_root", ".") or ".")
    present, absent = [], []
    for item in artifacts:
        raw = item.get("path") if isinstance(item, dict) else str(item)
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        # 手写/过期的产物路径不该被当成"有产物"
        if path.is_file() and path.stat().st_size > 0:
            present.append(raw)
        else:
            absent.append(raw)
    if status != PASS:
        gate("G4", NOT_RUN, "compile not PASS%s" % lib_note)
    elif present:
        detail = "%d native artifact(s) on disk%s" % (len(present), lib_note)
        if absent:
            detail += " | %d listed but missing: %s" % (
                len(absent), ", ".join(absent[:3]))
        gate("G4", PASS if not absent else PARTIAL, detail)
    elif artifacts:
        gate("G4", FAIL,
             "%d artifact(s) listed in build.json but none exists on disk "
             "(过期或手写的路径)%s" % (len(artifacts), lib_note))
    else:
        gate("G4", PARTIAL, "no artifact recorded - compile PASS without "
                            "any .so/.a path%s" % lib_note)

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
    # G10 只能是人工记录（`smoke --result` 或 mark-gate）。明细里写明 manual，
    # 否则读报告的人分不清"机器测过"和"人说我点过了"。
    if smoke:
        g10_note = "manual record (%s)" % (smoke.get("note") or "smoke --result")
        gate("G10", _map_cmd(str(smoke.get("status", NOT_RUN))), g10_note)
    else:
        rec = manual.get("G10") or {}
        gate("G10", _map_cmd(str(rec.get("status", NOT_RUN))),
             rec.get("note") or "basic interaction test (manual)")
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
    """PASS / PARTIAL / FAIL 三档。

    PARTIAL 存在的意义：交叉编译能做到"编过 + 链过"，而打包/装机还没开始。
    这种情况如果判 FAIL，所有只做到编译阶段的迁移都会被读成"失败"，
    与"编译通过 ≠ 迁移成功"同样失真。所以：
      - 编译 PASS 且产物在（G3/G4），且打包没被判失败（G5 ∈ PASS/PARTIAL/NOT_RUN/SKIP）
        → PARTIAL（阶段性成果，不是可交付状态）
      - 打包真的失败（G5 FAIL）或编译没通过 → FAIL
    """
    statuses = [gates[g]["status"] for g in GATE_ORDER]
    core = statuses[0:9]          # G0..G8
    if all(s == PASS for s in core):
        return PASS
    compiled = statuses[3] == PASS and statuses[4] in (PASS, PARTIAL)
    package_not_failed = statuses[5] in (PASS, PARTIAL, NOT_RUN, SKIP)
    if compiled and package_not_failed:
        return PARTIAL
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
    if overall == PARTIAL:
        lines.append("NOTE: PARTIAL = 编译/链接已通过，打包·装机·启动未完成或未验证；"
                     "这不是可交付状态。")
    if overall != PASS:
        lines.append("NOTE: tool verdict only - an LLM must not report migration "
                     "success when this result is not PASS.")
    return "\n".join(lines)


def addressed_critical_records(state) -> Dict[str, Dict]:
    """读取"已处理 critical"记录，兼容历史的纯 id 列表。

    历史格式（`addressed_critical: ["R001"]`）没有证据，读出来也当"没证据"，
    由 G2 判 FAIL 并提示补证据——否则一次 `mark-risk --rule R001` 就能把
    437 条 critical 清零，门禁等于没有。
    """
    raw = state.data.get("addressed_critical") or []
    records: Dict[str, Dict] = {}
    if isinstance(raw, dict):
        for rid, rec in raw.items():
            records[str(rid)] = rec if isinstance(rec, dict) else {}
    else:
        for item in raw:
            if isinstance(item, dict):
                rid = str(item.get("rule") or "")
                if rid:
                    records[rid] = item
            else:
                records[str(item)] = {}
    return records


def mark_critical_addressed(state, rule_ids: List[str], evidence: str = "",
                            note: str = "") -> None:
    records = addressed_critical_records(state)
    for rid in rule_ids:
        records[str(rid)] = {
            "evidence": (evidence or "").strip(),
            "note": (note or "").strip(),
            "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    state.data["addressed_critical"] = records
    state.save()
