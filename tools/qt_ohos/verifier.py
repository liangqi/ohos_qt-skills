"""Verification Gates G0-G13.

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
    G13 Loadable      every strong UND symbol is provided by the HAP or sysroot

Overall: PASS only if G0-G8 all PASS; PARTIAL if G3-G5 PASS; else FAIL.
STALE is not a verdict of its own: a record whose HAP/device fingerprint no
longer matches the current state is reported as STALE and never counts as PASS.
"""

from __future__ import annotations

import datetime
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .builder import env_of
from .elf import ElfInfo, describe_mismatch, read_elf, read_elf_bytes

GATE_ORDER = ["G%d" % i for i in range(14)]
CORE_GATES = ["G%d" % i for i in range(9)]        # verdict scope: G0-G8
GATE_TITLES = {
    "G0": "Environment", "G1": "Project", "G2": "Compatibility",
    "G3": "Compile", "G4": "Link/Artifact", "G5": "Package",
    "G6": "Install", "G7": "Launch", "G8": "Crash",
    "G9": "UI", "G10": "Smoke", "G11": "Feature", "G12": "Regression",
    "G13": "Loadable",
}
PASS = "PASS"
FAIL = "FAIL"
PARTIAL = "PARTIAL"
NOT_RUN = "NOT_RUN"
SKIP = "SKIP"
# Record does not match the current HAP/device: neither "passed" nor "failed this time"
STALE = "STALE"


def _cmd_status(section: Dict, key: str) -> str:
    record = (section or {}).get(key) or {}
    return str(record.get("status", NOT_RUN))


# --- Artifact content checks (G4/G5) ---------------------------------------
# "File exists and is non-empty" is the weakest criterion: copying an x86 .so under an aarch64 name, or a HAP
# missing one DT_NEEDED library, both turn an "existence is enough" gate green. Here we read the ELF header
# and dynamic section, so the criterion becomes "can this file be dlopen'ed on the target".

# sonames provided by the OHOS runtime that don't go into the HAP (prefix match). Deliberately excludes libssl/libcrypto:
# an imported OpenSSL that isn't packaged is exactly the defect we want to catch.
SYSTEM_SONAMES = (
    "libc.so", "libm.so", "libdl.so", "libz.so", "libpthread.so", "librt.so",
    "libstdc++.so", "libc++.so", "libc++_shared.so", "libunwind.so",
    "libclang_rt.", "libhilog", "libhitrace", "libhisysevent", "libipc",
    "libsamgr", "libeventhandler", "libability", "libwant", "libbundle",
    "libappkit", "libappexecfwk", "libace", "libnapi", "libnative", "libutils",
    "libcjson", "libEGL", "libGLESv2", "libvulkan", "libpulse", "libOpenSLES",
    "libicu", "libskia", "libresource", "libmultimedia", "libimage",
    "libwindow", "libdisplay", "libui", "libpixelmap", "librawfile",
    "libsecurity", "libnode", "libuv", "libqos", "libclang",
)


def _expected_abi(state) -> str:
    env = env_of(state) if state is not None else {}
    return str(env.get("ohos_arch") or env.get("target_abi") or "arm64-v8a")


def _is_system_soname(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in SYSTEM_SONAMES)


def _artifact_problems(path: Path, expected_abi: str
                       ) -> Tuple[Optional[ElfInfo], List[str]]:
    """(info, problems) for one built artifact. Empty problems == loadable."""
    if path.suffix.lower() == ".a":
        with path.open("rb") as handle:
            magic = handle.read(8)
        return None, ([] if magic.startswith(b"!<arch>")
                      else ["not an ar archive"])
    try:
        info = read_elf(path)
    except (ValueError, OSError) as exc:
        return None, [str(exc)]
    problem = describe_mismatch(info, expected_abi)
    return info, ([problem] if problem else [])


def _identity(info: Optional[ElfInfo]) -> str:
    if info is None:
        return "static archive"
    return "ELF%d/%s/%s" % (info.elf_class, info.machine_name, info.type_name)


def _hap_lib_names(project_root: Path, build_json: Dict) -> set:
    """File names under libs/<abi>/ in the HAP, used to decide whether a DT_NEEDED ships with the package."""
    hap = build_json.get("hap")
    if not hap:
        return set()
    path = Path(hap)
    if not path.is_absolute():
        path = project_root / path
    if not path.is_file():
        return set()
    try:
        with zipfile.ZipFile(path) as archive:
            return {name.split("/")[-1] for name in archive.namelist()
                    if "/libs/" in name and re.search(r"\.so(\.\d+)*$",
                                                      name.split("/")[-1])}
    except (zipfile.BadZipFile, OSError):
        return set()


def _hap_allowed_libs(env: Dict) -> Tuple[List[str], List[str]]:
    """(usable prefixes, rejected ones).

    `hap_allowed_libs` may be a list, or a comma-separated string written by `config set`.
    Earlier code iterated the string into characters, so "l" let every lib* through -- the allowlist was useless.
    Normalize it here, and reject prefixes shorter than 4 characters (a prefix like "lib" lets half the system through).
    """
    raw = (env or {}).get("hap_allowed_libs") or []
    if isinstance(raw, str):
        items = re.split(r"[,;\s]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        items = [str(item) for item in raw]
    else:
        items = [str(raw)]
    usable: List[str] = []
    rejected: List[str] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        (usable if len(item) >= 4 else rejected).append(item)
    return usable, rejected


def _hap_dependency_report(hap: Path, expected_abi: str,
                           allowed_extra: List[str]) -> Dict:
    """Read the HAP's libs/<abi>/*.so and close their DT_NEEDED graph.

    Any DT_NEEDED that is neither packed, nor a known OHOS system soname, nor
    listed in `env.hap_allowed_libs` makes the app fail at load time — that is a
    broken HAP no matter how "packaged successfully" looked, so it is reported as a defect.
    """
    report: Dict = {"packed": 0, "deps": 0, "abi_dirs": [],
                    "missing": [], "definite": [], "unreadable": [],
                    "sonames": []}
    try:
        archive = zipfile.ZipFile(hap)
    except (zipfile.BadZipFile, OSError) as exc:
        report["error"] = "hap is not a valid zip (unsigned or corrupted: %s)" % exc
        return report
    with archive:
        # Versioned library names (libQt6Core.so.6 / libssl.so.3) must count too, otherwise
        # "libssl.so.3 is right there" gets read as "not packaged".
        entries = [n for n in archive.namelist()
                   if re.search(r"\.so(\.\d+)*$", n)]
        libs: Dict[str, ElfInfo] = {}
        for name in entries:
            parts = name.split("/")
            if len(parts) < 3 or parts[-3] != "libs":
                continue                 # only the libs/<abi>/<name>.so layout counts
            abi_dir, base = parts[-2], parts[-1]
            if abi_dir not in report["abi_dirs"]:
                report["abi_dirs"].append(abi_dir)
            try:
                libs[base] = read_elf_bytes(archive.read(name))
            except (ValueError, KeyError) as exc:
                report["unreadable"].append("%s (%s)" % (base, exc))
            report["packed"] = len(libs) + len(report["unreadable"])
    report["sonames"] = sorted(libs)

    for abi_dir in report["abi_dirs"]:
        if expected_abi and abi_dir != expected_abi:
            report["definite"].append(
                "HAP packs %s, target is %s" % (abi_dir, expected_abi))

    packed = set(libs)
    extra = tuple(str(name).strip() for name in (allowed_extra or [])
                  if len(str(name).strip()) >= 4)
    missing: List[str] = []
    for base, info in libs.items():
        for dep in info.needed:
            report["deps"] += 1
            if dep in packed or _is_system_soname(dep):
                continue
            if any(name.startswith(dep + ".") for name in packed):
                continue
            if extra and any(dep.startswith(prefix) for prefix in extra):
                continue
            missing.append("%s (needed by %s)" % (dep, base))
    report["missing"] = sorted(set(missing))
    report["definite"] = sorted(set(list(report["definite"]) + missing))
    return report


# --- Record fingerprints (D-03) ---------------------------------------------
# When a gate record holds only a status, "yesterday's PASS from installing HAP-A" is inherited directly by
# today's verify of HAP-B: the report then shows self-contradictory combos like G6 FAIL alongside G7/G9 PASS.
# Fingerprints don't change the criteria; they only answer "was this PASS produced by this tree and this device".

def file_fingerprint(path: Path) -> Dict:
    """(sha256, size, mtime_ns); sha is computed for large files only when necessary."""
    import hashlib
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns}


def _current_device_serial(env: Dict) -> Optional[str]:
    """The first currently connected device; None if unavailable (no conclusion is drawn from it)."""
    import subprocess
    from .state import find_hdc
    hdc = env.get("hdc") or find_hdc()
    try:
        completed = subprocess.run([hdc, "list", "targets"],
                                   capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    text = completed.stdout.decode("utf-8", "replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or "empty" in line.lower():
            continue
        # Looks like "3XB0124726000062\tdevice"; the first column is enough
        return line.split()[0]
    return None


def stale_reasons(state, build_json: Dict, runtime: Dict) -> List[str]:
    """Why the historical records can't represent the current state (empty list = they can be trusted)."""
    reasons: List[str] = []
    hap = build_json.get("hap")
    recorded = build_json.get("hap_fingerprint") or {}
    if hap and recorded:
        path = Path(hap)
        if not path.is_absolute():
            path = Path(getattr(state, "project_root", ".") or ".") / hap
        if path.is_file():
            stat = path.stat()
            same_file = (stat.st_size == recorded.get("size")
                         and stat.st_mtime_ns == recorded.get("mtime_ns"))
            if not same_file:
                now = file_fingerprint(path)
                if now["sha256"] != recorded.get("sha256"):
                    reasons.append("HAP content changed (recorded %s... now %s...)" % (
                        str(recorded.get("sha256"))[:12], now["sha256"][:12]))
    current_sha = (build_json.get("hap_fingerprint") or {}).get("sha256")
    for step in ("install", "launch"):
        record = runtime.get(step) or {}
        if not record:
            continue
        recorded_hap = record.get("hap_sha256")
        if recorded_hap and current_sha and recorded_hap != current_sha:
            reasons.append("%s record belongs to another HAP" % step)
        recorded_serial = record.get("device_serial")
        if recorded_serial:
            now_serial = _current_device_serial(env_of(state))
            if now_serial and now_serial != recorded_serial:
                reasons.append("%s record came from device %s, current is %s"
                               % (step, recorded_serial, now_serial))
    return reasons


def _sysroot_exports(state, env: Dict) -> Tuple[Optional[Path], set]:
    """Set of symbols exported by all system libraries in the sysroot.

    Returns (None, set()) when there is no sysroot: G13 then SKIPs, never failing because "it couldn't read"
    -- that would create a batch of false failures on machines without ohos_sdk_native configured.
    """
    native = env.get("ohos_sdk_native")
    if not native:
        return None, set()
    root = Path(native) / "sysroot" / "usr" / "lib"
    if not root.is_dir():
        return None, set()
    abi = _expected_abi(state)
    dirs = [item for item in root.iterdir() if item.is_dir()]
    preferred = [item for item in dirs if abi.replace("-", "_") in item.name
                 or abi in item.name]
    chosen = preferred or dirs
    exports: set = set()
    for directory in chosen:
        for lib in sorted(directory.glob("*.so")):
            try:
                info = read_elf(lib, want_symbols=True)
            except (ValueError, OSError):
                continue
            exports.update(info.exports)
    return chosen[0] if chosen else None, exports


def _hap_symbol_report(hap: Path, expected_abi: str, allowed: List[str],
                       sysroot_exports: set) -> Dict:
    """Whether every DSO's "strong undefined symbols" in the HAP can be resolved."""
    report: Dict = {"libs": 0, "undefined": 0, "unresolved": [],
                    "unreadable": [], "error": ""}
    try:
        archive = zipfile.ZipFile(hap)
    except (zipfile.BadZipFile, OSError) as exc:
        report["error"] = "hap is not a valid zip (%s)" % exc
        return report
    with archive:
        infos = {}
        for name in archive.namelist():
            parts = name.split("/")
            if len(parts) < 3 or parts[-3] != "libs":
                continue
            if not re.search(r"\.so(\.\d+)*$", parts[-1]):
                continue
            if expected_abi and parts[-2] != expected_abi:
                continue
            try:
                infos[parts[-1]] = read_elf_bytes(archive.read(name),
                                                  want_symbols=True)
            except (ValueError, KeyError) as exc:
                report["unreadable"].append("%s (%s)" % (parts[-1], exc))
    packed_exports: set = set()
    for info in infos.values():
        packed_exports.update(info.exports)
    allowed_prefixes = tuple(item for item in allowed if len(item) >= 4)
    for base, info in sorted(infos.items()):
        report["libs"] += 1
        for sym in info.undefined:
            report["undefined"] += 1
            if sym in packed_exports or sym in sysroot_exports:
                continue
            if allowed_prefixes and sym.startswith(allowed_prefixes):
                continue
            # Weak-convention symbols injected by the compiler/toolchain don't need resolving
            if sym in ("_init", "_fini", "_edata", "_end", "__bss_start"):
                continue
            report["unresolved"].append("%s (needed by %s)" % (sym, base))
    report["unresolved"] = sorted(set(report["unresolved"]))
    return report


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
        # Cross-compile machines often install cmake outside PATH: give an actionable fix here,
        # rather than just reporting "not on PATH"
        missing.append("cmake not on PATH (config set cmake <absolute path>)")
    gate("G0", FAIL if missing else PASS,
         "missing: %s" % ", ".join(missing) if missing else "environment configured",
         "env.json")

    # G1 project ---------------------------------------------------------
    has_build_files = bool(scan.get("cmake_files") or scan.get("pro_files"))
    gate("G1", PASS if has_build_files and plan else FAIL,
         "build files: %s, plan: %s" % (has_build_files, bool(plan)), "scan.json")

    # G2 compatibility ---------------------------------------------------
    # Without a risk_scan run there is no risk data at all: "no critical risks" then means
    # "not checked", not "check passed". Empty evidence can only be NOT_RUN.
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
            # Marked but without evidence: equivalent to "waved through", doesn't count as addressed
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
             "%s (add evidence with mark-risk --rule <id> --evidence <change location/how verified>)"
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
    # The whole-package chain is long, so per-library progress is recorded separately (`libcheck`); otherwise facts like "this library
    # already compiles and links" are invisible in the gates, and halfway through a port you only see the overall failure.
    libs = state.read_json("libs.json", default={}) or {}
    lib_records = libs.get("libraries") or []
    probed = sum(1 for item in lib_records if item.get("level") == "probed")
    built = sum(1 for item in lib_records if item.get("level") == "built")
    lib_note = (" | libs: %d built, %d probed" % (built, probed)) if lib_records else ""
    artifacts = build_json.get("artifacts") or []
    project_root = Path(getattr(state, "project_root", ".") or ".")
    expected_abi = _expected_abi(state)
    present, absent = [], []
    for item in artifacts:
        raw = item.get("path") if isinstance(item, dict) else str(item)
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        # Hand-written/stale artifact paths shouldn't count as "has artifacts"
        if path.is_file() and path.stat().st_size > 0:
            present.append((raw, path))
        else:
            absent.append(raw)
    # sonames already in the HAP (or provided by the device) shouldn't be reported by G4 as "unresolved":
    # Qt's runtime libraries ship with the package, so naturally they're not in the artifact dir.
    hap_lib_names = _hap_lib_names(project_root, build_json)
    content_problems: List[str] = []
    identities: List[str] = []
    unresolved: List[str] = []
    present_names = {path.name for _raw, path in present}
    for raw, path in present:
        info, problems = _artifact_problems(path, expected_abi)
        identities.append(_identity(info))
        content_problems.extend("%s: %s" % (raw, why) for why in problems)
        if info is None:
            continue
        for dep in info.needed:
            if dep in present_names or dep in hap_lib_names or _is_system_soname(dep):
                continue
            sibling = path.parent / dep
            if sibling.is_file():
                continue
            unresolved.append("%s (needed by %s)" % (dep, path.name))
    ident_note = ""
    if identities:
        # A batch of artifacts should share one identity; if there are two, spell them out instead of just a count
        uniq = sorted(set(identities))
        ident_note = " | " + (uniq[0] if len(uniq) == 1 else ", ".join(uniq))
    if unresolved:
        ident_note += " | not resolved in artifact dir: %s" % ", ".join(
            sorted(set(unresolved))[:3])
    if status != PASS:
        gate("G4", NOT_RUN, "compile not PASS%s" % lib_note)
    elif content_problems:
        # File present, name right, but the content can't run (wrong arch / not a shared object / not ELF)
        gate("G4", FAIL, "%d of %d artifact(s) not loadable on %s: %s%s" % (
            len(content_problems), len(present), expected_abi,
            "; ".join(content_problems[:3]), ident_note))
    elif present:
        detail = "%d native artifact(s) on disk%s%s" % (
            len(present), ident_note, lib_note)
        if absent:
            detail += " | %d listed but missing: %s" % (
                len(absent), ", ".join(absent[:3]))
        gate("G4", PASS if not absent else PARTIAL, detail)
    elif artifacts:
        gate("G4", FAIL,
             "%d artifact(s) listed in build.json but none exists on disk "
             "(stale or hand-written paths)%s" % (len(artifacts), lib_note))
    else:
        gate("G4", PARTIAL, "no artifact recorded - compile PASS without "
                            "any .so/.a path%s" % lib_note)

    # G5 package ---------------------------------------------------------
    pkg_status = _cmd_status(build_json, "package")
    hap = build_json.get("hap")
    hap_path: Optional[Path] = None
    if hap:
        hap_path = Path(hap)
        if not hap_path.is_absolute():
            hap_path = project_root / hap_path
    allowed_libs, rejected_libs = _hap_allowed_libs(env)
    allowed_note = (" | ignored too-short allowlist prefixes: %s" % ", ".join(rejected_libs)
                    if rejected_libs else "")
    if pkg_status == PASS and hap and hap_path is not None:
        report = _hap_dependency_report(
            hap_path, expected_abi, allowed_libs) if hap_path.is_file() else {}
        if report.get("error"):
            g5, g5_detail = FAIL, "hap: %s | %s" % (hap, report["error"])
        elif report.get("definite"):
            g5 = FAIL
            g5_detail = "hap: %s | dependency closure broken: %s" % (
                hap, "; ".join(report["definite"][:3]))
        else:
            g5 = PASS
            g5_detail = "hap: %s | libs: %d packed, %d DT_NEEDED, closure complete" % (
                hap, report.get("packed", 0), report.get("deps", 0))
            if report.get("unreadable"):
                g5_detail += " | unparsable: %s" % ", ".join(
                    report["unreadable"][:2])
        g5_detail += allowed_note
    elif pkg_status == PASS:
        # The package command claims success but there is no artifact: doesn't count as packaged
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
    # A crash window only makes sense if "the app really got installed and started": when install/launch is not PASS
    # always SKIP (the old implementation would fill a PASS from device-wide hilog, reading "didn't start" as "didn't crash").
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
            # Without bundle_name configured this captures the device-wide buffer; other processes' crashes/logs get mixed in
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

    # G13 loadable --------------------------------------------------------
    # G4 asserts "is this an AArch64 shared object", but a library with the right architecture can still carry
    # symbols nobody can resolve: cross-linking defaults to `--allow-shlib-undefined`, and on the board musl
    # dereferences NULL in find_sym2 and crashes. This only checks "can the strong undefined symbols be closed".
    native = env.get("ohos_sdk_native")
    if pkg_status != PASS or not hap or hap_path is None or not hap_path.is_file():
        gate("G13", NOT_RUN, "package not PASS, no HAP to inspect")
    elif not native or not (Path(native) / "sysroot" / "usr" / "lib").is_dir():
        gate("G13", SKIP,
             "missing ohos_sdk_native/sysroot, cannot judge symbol closure"
             " (`config set ohos_sdk_native <SDK>/native`)")
    else:
        _sysroot_dir, sysroot_exports = _sysroot_exports(state, env)
        sym_report = _hap_symbol_report(hap_path, expected_abi,
                                        allowed_libs, sysroot_exports)
        strict = str(env.get("undefined_gate", "advisory")).lower() == "strict"
        if sym_report.get("error"):
            gate("G13", SKIP, sym_report["error"])
        elif sym_report.get("unresolved"):
            unresolved = sym_report["unresolved"]
            detail = ("%d strong undefined symbol(s) exist in neither packaged libs nor sysroot: %s"
                      " (may SIGSEGV in find_sym2 on the board)" % (
                          len(unresolved), ", ".join(unresolved[:5])))
            gate("G13", FAIL if strict else PARTIAL, detail,
                 "undefined_gate=%s" % ("strict" if strict else "advisory"))
        else:
            gate("G13", PASS,
                 "%d lib(s), %d UND, all resolvable from packaged libs or sysroot" % (
                     sym_report.get("libs", 0), sym_report.get("undefined", 0)))

    # G10-G12 manual gates --------------------------------------------------
    # recorded via `smoke --result` (G10) or `mark-gate G10|G11|G12` (all three)
    smoke = runtime.get("smoke")
    manual = state.data.get("manual_gates") or {}
    # G10 can only be a manual record (`smoke --result` or mark-gate). State manual in the detail,
    # otherwise readers can't tell "machine-tested" from "someone says they clicked through".
    if smoke:
        g10_note = "manual record (%s)" % (smoke.get("note") or "smoke --result")
        gate("G10", _map_cmd(str(smoke.get("status", NOT_RUN))), g10_note)
    elif manual.get("G10"):
        rec = manual.get("G10") or {}
        gate("G10", _map_cmd(str(rec.get("status", NOT_RUN))),
             rec.get("note") or "basic interaction test (manual)")
    else:
        # With no human verdict, present the `smoke-interact` machine evidence honestly downgraded:
        # the machine can prove "the UI changed and the process is alive", but not "the interaction is correct",
        # so it tops out at PARTIAL; PASS must always come from a human.
        evidence = runtime.get("smoke_interact") or {}
        inner = evidence.get("result") or {}
        status = str(inner.get("status") or NOT_RUN)
        detail = inner.get("stdout") or "smoke-interact not run (qt-ohos-run smoke-interact)"
        if status == PASS:
            gate("G10", PARTIAL,
                 "machine evidence passed, awaiting human verdict: " + detail, inner.get("evidence"))
        elif status in (FAIL, PARTIAL):
            gate("G10", _map_cmd(status), "machine evidence failed: " + detail,
                 inner.get("evidence"))
        else:
            gate("G10", NOT_RUN, detail)
    for gid in ("G11", "G12"):
        rec = manual.get(gid) or {}
        gate(gid, _map_cmd(str(rec.get("status", NOT_RUN))),
             rec.get("note") or GATE_TITLES[gid].lower() + " (manual)")

    # Fingerprint check: historical records can't stand in for this run's result -----
    reasons = stale_reasons(state, build_json, runtime)
    if reasons:
        stamp = "; ".join(reasons)
        for gid in ("G6", "G7", "G8", "G9"):
            if gates[gid]["status"] in (PASS, PARTIAL):
                gates[gid] = dict(gates[gid], status=STALE,
                                  detail="record stale: %s (re-run install/launch)" % stamp,
                                  evidence="")
    overall = _overall(gates)
    return gates, overall


def _map_cmd(status: str) -> str:
    return {
        "PASS": PASS, "FAIL": FAIL, "TIMEOUT": FAIL,
        "SKIP": SKIP, "NOT_RUN": NOT_RUN,
    }.get(status, NOT_RUN)


def _overall(gates: Dict[str, Dict]) -> str:
    """Three levels: PASS / PARTIAL / FAIL.

    PARTIAL exists because cross-compiling can reach "compiles + links" while packaging/installing hasn't started.
    Judging that FAIL would make every port that only reached the compile stage read as "failed",
    just as distorted as "compiles == port succeeded". So:
      - compile PASS and artifacts present (G3/G4), and packaging not judged failed (G5 in PASS/PARTIAL/NOT_RUN/SKIP)
          -> PARTIAL (interim result, not a deliverable state)
      - packaging really failed (G5 FAIL) or compile did not pass -> FAIL
    """
    core = [gates[g]["status"] for g in CORE_GATES]     # G0..G8
    if any(status == STALE for status in core):
        # With stale records, "all PASS" is an illusion: the conclusion was not produced by this tree
        return FAIL
    if all(status == PASS for status in core):
        return PASS
    compiled = gates["G3"]["status"] == PASS and gates["G4"]["status"] in (PASS, PARTIAL)
    package_not_failed = gates["G5"]["status"] in (PASS, PARTIAL, NOT_RUN, SKIP)
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
    # The verdict scope must be stated next to the conclusion, otherwise "Result: PASS" shown alongside G10 PARTIAL /
    # G11-G12 NOT_RUN in the table leaves readers guessing what PASS covers.
    lines.append("Result: %s (verdict scope G0-G8; G9-G13 are supplementary evidence, not part of the verdict)" % overall)
    if overall == PARTIAL:
        lines.append("NOTE: PARTIAL = compile/link passed; packaging/install/launch not done or not verified; "
                     "this is not a deliverable state.")
    if any(gates[gid]["status"] == STALE for gid in GATE_ORDER):
        lines.append("NOTE: STALE = this record comes from another HAP or another device, "
                     "not this run's result; re-running install / launch clears it.")
    if overall != PASS:
        lines.append("NOTE: tool verdict only - an LLM must not report migration "
                     "success when this result is not PASS.")
    return "\n".join(lines)


def addressed_critical_records(state) -> Dict[str, Dict]:
    """Read the "addressed critical" records, compatible with the historical plain id list.

    The historical format (`addressed_critical: ["R001"]`) has no evidence and is read as "no evidence";
    G2 judges it FAIL and prompts for evidence -- otherwise a single `mark-risk --rule R001` could clear
    437 critical risks, and the gate would be meaningless.
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
