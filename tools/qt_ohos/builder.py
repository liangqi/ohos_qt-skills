"""Build / package / device orchestration.

All commands come from .qt-ohos/env.json (see `qt-ohos-run config`) so the
pipeline stays reproducible. Every command runs through state.run_cmd,
therefore every step has a timeout, an exit code and a log artifact, and
TIMEOUT is never reported as PASS.

env.json keys (all optional; missing pieces make the corresponding stage
SKIP instead of guessing):

    cmake           cmake executable              (default: cmake)
    build_dir       cmake build directory         (default: build-ohos)
    cmake_args      extra configure args (list)
    build_command   full custom build command (overrides default cmake flow)
    package_command command producing the HAP     (e.g. node hvigorw.js assembleHap)
    package_dir     cwd for package_command
    hap_glob        glob to locate produced HAP   (default: **/*-signed.hap,**/*.hap)
    hdc             hdc executable                (default: hdc)
    bundle_name     application bundleName
    ability_name    main ability name             (default: EntryAbility)
    crash_wait_sec  seconds to watch hilog after launch (default: 8)
"""

from __future__ import annotations

import glob as globmod
from pathlib import Path
from typing import Dict, Optional


def env_of(state) -> Dict:
    return state.read_json("env.json", default={}) or {}


def configure_and_build(state, timeout: float = 1800.0):
    """G3 compile orchestration. Returns the decisive CommandResult."""
    env = env_of(state)
    build_json = state.read_json("build.json", default={}) or {}

    custom = env.get("build_command")
    if custom:
        result = state.run_cmd(custom, label="build-custom", timeout=timeout)
        build_json["mode"] = "custom"
    else:
        cmake = env.get("cmake", "cmake")
        build_dir = env.get("build_dir", "build-ohos")
        cmake_args = env.get("cmake_args") or []
        qt_prefix = env.get("qt_sdk_prefix")
        if qt_prefix:
            cmake_args = cmake_args + ["-DCMAKE_PREFIX_PATH=%s" % qt_prefix]
        configure = [cmake, "-S", ".", "-B", build_dir,
                     "-DCMAKE_BUILD_TYPE=Release"] + cmake_args
        result = state.run_cmd(configure, label="cmake-configure",
                               timeout=min(timeout, 600))
        build_json["mode"] = "cmake"
        if result.status == "PASS":
            result = state.run_cmd([cmake, "--build", build_dir, "--parallel"],
                                   label="cmake-build", timeout=timeout)
    build_json["compile"] = result.to_dict()
    if result.status == "PASS":
        build_json["artifacts"] = _find_artifacts(state.project_root,
                                                  env.get("build_dir", "build-ohos"))
    state.write_json("build.json", build_json)
    return result


def package_hap(state, timeout: float = 1800.0):
    env = env_of(state)
    build_json = state.read_json("build.json", default={}) or {}
    command = env.get("package_command")
    if not command:
        result = state.skip_cmd("package", "env.json: package_command not set")
    else:
        result = state.run_cmd(command, label="package-hap", timeout=timeout,
                               cwd=env.get("package_dir") or None)
    build_json["package"] = result.to_dict()
    if result.status == "PASS":
        hap = find_hap(state.project_root, env.get("hap_glob"))
        build_json["hap"] = hap
        if not hap:
            result.status = "FAIL"
            result.stderr += "\n[qt-ohos-run] build succeeded but no .hap found"
            build_json["package"] = result.to_dict()
    state.write_json("build.json", build_json)
    return result


def find_hap(project_root, hap_glob: Optional[str] = None) -> Optional[str]:
    root = Path(project_root)
    patterns = hap_glob.split(",") if hap_glob else [
        "**/build/**/*.hap", "**/*.hap"]
    for pattern in patterns:
        for path in sorted(globmod.glob(str(root / pattern), recursive=True)):
            if "/.qt-ohos/" not in path.replace("\\", "/"):
                return str(Path(path).relative_to(root).as_posix())
    return None


def install_hap(state, timeout: float = 300.0):
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    build_json = state.read_json("build.json", default={}) or {}
    hap = build_json.get("hap")
    hdc = env.get("hdc", "hdc")
    if not hap:
        result = state.skip_cmd("install", "no HAP artifact recorded")
    else:
        result = state.run_cmd([hdc, "install", "-r", hap],
                               label="hdc-install", timeout=timeout)
        if result.status == "PASS" and "fail" in (result.stdout + result.stderr).lower():
            # hdc may return rc=0 while reporting failure in text
            result.status = "FAIL"
    runtime["install"] = result.to_dict()
    state.write_json("runtime.json", runtime)
    return result


def launch_app(state, timeout: float = 120.0):
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    hdc = env.get("hdc", "hdc")
    bundle = env.get("bundle_name")
    ability = env.get("ability_name", "EntryAbility")
    if not bundle:
        result = state.skip_cmd("launch", "env.json: bundle_name not set")
    else:
        result = state.run_cmd(
            [hdc, "shell", "aa", "start", "-b", bundle, "-a", ability],
            label="aa-start", timeout=timeout)
        combined = (result.stdout + result.stderr).lower()
        if result.status == "PASS" and ("error" in combined or "fail" in combined):
            result.status = "FAIL"
    runtime["launch"] = result.to_dict()
    state.write_json("runtime.json", runtime)
    return result


def crash_check(state, timeout: Optional[float] = None):
    """Capture device log for N seconds after launch and look for crashes."""
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    hdc = env.get("hdc", "hdc")
    wait_sec = float(env.get("crash_wait_sec", 8))
    timeout = timeout or (wait_sec + 30)

    result = state.run_cmd([hdc, "shell", "timeout", str(int(wait_sec)),
                            "hilog"], label="hilog-crash-window",
                           timeout=timeout)
    text = (result.stdout + "\n" + result.stderr).lower()
    crash_markers = ["cppcrash", "jscrash", "appfreeze", "sigsegv", "sigabrt",
                     "faultlog", "process died", "dlopen failed"]
    found = [m for m in crash_markers if m in text]
    result.exit_code = 0  # hilog capture exit code is not meaningful
    # only a successfully captured window can prove "no crash markers";
    # a failed/missing hdc run must not be reported as PASS
    if result.status == "PASS":
        result.status = "FAIL" if found else "PASS"
    result.stderr = ("crash markers found: %s" % ", ".join(found)) if found else \
        ("no crash markers in %ss window" % int(wait_sec)
         if result.status == "PASS" else
         "crash window capture failed: %s" % result.stderr.strip()[:200])
    runtime["crash_check"] = result.to_dict()
    runtime["crash_markers_found"] = found
    state.write_json("runtime.json", runtime)
    return result


def check_ui_window(state, timeout: float = 60.0):
    """G9 evidence: dump the layout tree of the launched bundle via uitest.

    Writes runtime['ui_window_seen'] (True/False). A successful dump means the
    app window exists; failures fall back to PARTIAL + manual `mark-ui`.
    """
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    hdc = env.get("hdc", "hdc")
    bundle = env.get("bundle_name")
    if not bundle:
        result = state.skip_cmd("ui_window", "env.json: bundle_name not set")
    else:
        result = state.run_cmd(
            [hdc, "shell", "uitest", "dumpLayout", "-b", bundle],
            label="uitest-dump-layout", timeout=timeout)
        combined = (result.stdout + "\n" + result.stderr).lower()
        if result.status == "PASS" and ("error" in combined or "fail" in combined):
            result.status = "FAIL"
            result.stderr += "\n[qt-ohos-run] uitest dumpLayout reported failure"
    runtime["ui_window"] = result.to_dict()
    runtime["ui_window_seen"] = (result.status == "PASS")
    state.write_json("runtime.json", runtime)
    return result


def _find_artifacts(project_root, build_dir: str):
    root = Path(project_root)
    artifacts = []
    search_dir = root / build_dir
    dirs = [search_dir] if search_dir.is_dir() else [root]
    for base in dirs:
        for pattern in ("**/*.so",):
            for path in globmod.glob(str(base / pattern), recursive=True):
                rel = Path(path).relative_to(root).as_posix()
                if ".qt-ohos" not in rel:
                    artifacts.append(rel)
        if artifacts:
            break
    return artifacts[:50]
