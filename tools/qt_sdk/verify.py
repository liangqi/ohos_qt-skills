"""SV0..SV8 verification gates - the only success criterion for the forge.

    SV0  environment ready (source tree / OHOS SDK native / build tools)
    SV1  source state known (branch+commit+submodules registered, working
         tree changes == registered patch stack)
    SV2  configure PASS evidence
    SV3  build PASS evidence (TIMEOUT is never PASS)
    SV4  install propagation (key libs fresh in the SDK)
    SV5  SDK integrity (qmake / lib / include / mkspecs)
    SV6  traceability (manifest patch set == real git diff, version p<N>
         == applied patch count)
    SV7  smoke (optional; manual mark or qt-ohos-run evidence)
    SV8  release archived (manifest + ENV.local.md switched)

Result: PASS (SV0-SV6 + SV8; SV7 optional for test builds),
PARTIAL (compiled+installed but unsmoked), FAIL otherwise.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

from . import building, envcheck, patching, releasing, srctree
from .state import ForgeState

REQUIRED_FOR_PASS = ["SV0", "SV1", "SV2", "SV3", "SV4", "SV5", "SV6", "SV8"]


def run(st: ForgeState) -> Dict:
    gates: List[Dict] = []
    st.begin_stage("verify")

    gates.append(_sv0(st))
    gates.append(_sv1(st))
    gates.append(_sv2(st))
    gates.append(_sv3(st))
    gates.append(_sv4(st))
    gates.append(_sv5(st))
    gates.append(_sv6(st))
    gates.append(_sv7(st))
    gates.append(_sv8(st))

    table = {g["gate"]: g for g in gates}
    failed = [g["gate"] for g in gates
              if g["status"] == "FAIL" and g["gate"] in REQUIRED_FOR_PASS]
    smoke_missing = table["SV7"]["status"] == "SKIP"
    if failed:
        result = "FAIL"
    elif smoke_missing:
        result = "PARTIAL"
    else:
        result = "PASS"

    st.section("gates").update({g["gate"]: g["status"] for g in gates})
    st.section("gates")["result"] = result
    st.section("gates")["verified_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if result != "FAIL":
        st.complete_stage("verify", next_action="release")
    else:
        st.fail_stage("verify", "failed: %s" % failed, next_action="verify")
    return {"result": result, "failed": failed, "gates": gates}


def mark_smoke(st: ForgeState, result: str, note: str = "") -> Dict:
    if result not in ("pass", "fail"):
        raise ValueError("result must be pass|fail")
    st.section("gates")["SV7"] = "PASS" if result == "pass" else "FAIL"
    st.section("smoke").update({"result": result, "note": note,
                                "recorded": time.strftime(
                                    "%Y-%m-%d %H:%M:%S")})
    st.save()
    return {"ok": True, "SV7": st.section("gates")["SV7"]}


# ---------------------------------------------------------------- gates

def _sv0(st: ForgeState) -> Dict:
    cfg = st.env()
    report = envcheck.check(qt_src=cfg.get("qt_src", ""),
                            ohos_sdk_native=cfg.get("ohos_sdk_native", ""))
    fails = [c for c in report["checks"] if not c["ok"]]
    return {"gate": "SV0", "name": "environment ready",
            "status": "PASS" if report["ok"] else "FAIL",
            "detail": "; ".join("%s: %s" % (c["name"], c["detail"])
                                for c in fails) or "all checks ok"}


def _sv1(st: ForgeState) -> Dict:
    cfg = st.env()
    src = Path(cfg.get("qt_src") or "")
    if not (src / "qtbase").is_dir():
        return {"gate": "SV1", "name": "source state known", "status": "FAIL",
                "detail": "qt_src not configured"}
    info = srctree.inspect(src)
    if info.get("uninitialised_submodules"):
        return {"gate": "SV1", "name": "source state known", "status": "FAIL",
                "detail": "uninitialised submodules: %s"
                % info["uninitialised_submodules"][:5]}
    dirty = set(info.get("qtbase_dirty", []))
    registered = set(patching.applied_files(st))
    unregistered = sorted(dirty - registered)
    if unregistered:
        return {"gate": "SV1", "name": "source state known", "status": "FAIL",
                "detail": "unregistered working-tree changes: %s"
                % unregistered[:10]}
    missing = sorted(registered - dirty)
    if missing:
        return {"gate": "SV1", "name": "source state known", "status": "FAIL",
                "detail": "registered but not present in tree: %s"
                % missing[:10]}
    st.section("src").update({"path": str(src), "branch": info.get("branch"),
                              "commit": info.get("commit"),
                              "qtbase_commit": info.get("qtbase_commit")})
    return {"gate": "SV1", "name": "source state known", "status": "PASS",
            "detail": "%s @ %s, %d patched files"
            % (info.get("branch"), str(info.get("qtbase_commit"))[:10],
               len(registered))}


def _last_cmd(st: ForgeState, label_prefix: str) -> Dict:
    for cmd in reversed(st.data.get("commands", [])):
        if str(cmd.get("label", "")).startswith(label_prefix):
            return cmd
    return {}


def _sv2(st: ForgeState) -> Dict:
    cmd = _last_cmd(st, "configure")
    if not cmd:
        return {"gate": "SV2", "name": "configure", "status": "FAIL",
                "detail": "no configure evidence - run `configure`"}
    return {"gate": "SV2", "name": "configure",
            "status": cmd.get("status", "FAIL"),
            "detail": cmd.get("evidence", "")}


def _sv3(st: ForgeState) -> Dict:
    cmd = _last_cmd(st, "build")
    if not cmd:
        return {"gate": "SV3", "name": "build", "status": "FAIL",
                "detail": "no build evidence - run `build`"}
    return {"gate": "SV3", "name": "build",
            "status": cmd.get("status", "FAIL"),
            "detail": "%s (%s lines, %ss)"
            % (cmd.get("evidence", ""), cmd.get("log_lines"),
               cmd.get("duration"))}


def _active_ctx(st: ForgeState) -> Dict:
    try:
        return building.build_ctx(st)
    except RuntimeError as exc:
        return {"_error": str(exc)}


def _sv4(st: ForgeState) -> Dict:
    ctx = _active_ctx(st)
    if ctx.get("_error"):
        return {"gate": "SV4", "name": "install propagation", "status": "FAIL",
                "detail": ctx["_error"]}
    sdk_dir = Path(ctx.get("sdk_dir") or "")
    started = ctx.get("install_started")
    if not sdk_dir.is_dir() or not started:
        return {"gate": "SV4", "name": "install propagation", "status": "FAIL",
                "detail": "no install evidence - run `install`"}
    ts = time.mktime(time.strptime(started, "%Y-%m-%d %H:%M:%S"))
    libs = building.sdk_key_libs(sdk_dir)
    if not libs:
        return {"gate": "SV4", "name": "install propagation", "status": "FAIL",
                "detail": "no key libs found under %s" % sdk_dir}
    stale = [str(l.relative_to(sdk_dir)) for l in libs
             if l.stat().st_mtime < ts]
    if stale:
        return {"gate": "SV4", "name": "install propagation", "status": "FAIL",
                "detail": "stale libs (not refreshed by install): %s"
                % stale}
    return {"gate": "SV4", "name": "install propagation", "status": "PASS",
            "detail": "%d key libs fresh since %s" % (len(libs), started)}


def _sv5(st: ForgeState) -> Dict:
    ctx = _active_ctx(st)
    if ctx.get("_error"):
        return {"gate": "SV5", "name": "SDK integrity", "status": "FAIL",
                "detail": ctx["_error"]}
    sdk_dir = Path(ctx.get("sdk_dir") or "")
    if not sdk_dir.is_dir():
        return {"gate": "SV5", "name": "SDK integrity", "status": "FAIL",
                "detail": "SDK dir missing: %s" % sdk_dir}
    missing = [name for name in ("lib", "include", "mkspecs")
               if not (sdk_dir / name).is_dir()]
    qmake = (sdk_dir / "bin" / "qmake.exe").exists() or \
        (sdk_dir / "bin" / "qmake").exists()
    if missing or not qmake:
        return {"gate": "SV5", "name": "SDK integrity", "status": "FAIL",
                "detail": "missing: %s%s" % (
                    ", ".join(missing) or "-",
                    "" if qmake else " + bin/qmake")}
    return {"gate": "SV5", "name": "SDK integrity", "status": "PASS",
            "detail": str(sdk_dir)}


def _sv6(st: ForgeState) -> Dict:
    ctx = st.section("build")
    release = st.section("release")
    ver = release.get("version")
    if not ver:
        return {"gate": "SV6", "name": "traceability", "status": "FAIL",
                "detail": "no release cut - run `release`"}
    applied = patching.applied_entries(st)
    try:
        parsed = releasing.parse_version(ver)
    except ValueError as exc:
        return {"gate": "SV6", "name": "traceability", "status": "FAIL",
                "detail": str(exc)}
    if parsed["patches"] != len(applied):
        return {"gate": "SV6", "name": "traceability", "status": "FAIL",
                "detail": "version says p%d but %d patches applied"
                % (parsed["patches"], len(applied))}
    return {"gate": "SV6", "name": "traceability", "status": "PASS",
            "detail": "%s == %d patches (%s)"
            % (ver, len(applied),
               ",".join(e["id"] for e in applied) or "none")}


def _sv7(st: ForgeState) -> Dict:
    status = st.section("gates").get("SV7")
    smoke = st.section("smoke")
    if status == "PASS":
        return {"gate": "SV7", "name": "smoke (optional)",
                "status": "PASS", "detail": smoke.get("note", "")}
    if status == "FAIL":
        return {"gate": "SV7", "name": "smoke (optional)",
                "status": "FAIL", "detail": smoke.get("note", "")}
    return {"gate": "SV7", "name": "smoke (optional)", "status": "SKIP",
            "detail": "mark with `smoke-mark --result pass|fail` (or use "
                      "qt-ohos-run build/smoke against the new SDK)"}


def _sv8(st: ForgeState) -> Dict:
    release = st.section("release")
    env_sync = st.section("env_sync")
    ver = release.get("version")
    if not ver:
        return {"gate": "SV8", "name": "release archived", "status": "FAIL",
                "detail": "no release cut"}
    if not env_sync.get("version"):
        return {"gate": "SV8", "name": "release archived", "status": "FAIL",
                "detail": "ENV.local.md not switched - run `use %s`" % ver}
    return {"gate": "SV8", "name": "release archived", "status": "PASS",
            "detail": "%s -> %s" % (ver, env_sync.get("env_var"))}
