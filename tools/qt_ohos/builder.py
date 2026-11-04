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
  compatible_sdk  build-profile compatibleSdkVersion it must match (optional)
  package_command / package_dir  hvigor(or devecocli) packaging command
"""

from __future__ import annotations

import glob as globmod
import re
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


VERSIONED_SO_RE = re.compile(r"\.so(\.\d+)+$")
LIBS_ALLOWED_SUFFIX = (".so", ".a")


def preflight_package(state):
    """打包前检查 entry/libs/ 与 build-profile.json5 —— 这两处错都只在设备上炸。

    1. **版本化 .so**：`libfoo.so.1` 放进 `entry/libs/arm64-v8a/` 会被原样打进 HAP，
       但加载器按 soname 找 `libfoo.so`，结果装机后 dlopen 失败。打包前改名成 `.so`
       （或同时放一个符号链接同名文件）。
    2. **非 .so 文件**：hvigor 只搬 `.so`（另有 `.a` 静态库不进包），其它后缀会被静默
       忽略，表现为"我明明放进去 libruntime.so.1.2"。
    3. **compatibleSdkVersion**：与 CLI 记录的 `compatible_sdk` 不一致时，装机可能直接
       被系统拒绝（版本低于设备要求）或用了高版本 API 在旧设备上崩。

    返回 (errors, warnings)，都是人读字符串。
    """
    env = env_of(state)
    root = Path(state.project_root)
    errors, warns = [], []

    for arch_dir in sorted(root.glob("entry/libs/*")):
        if not arch_dir.is_dir():
            continue
        for path in sorted(arch_dir.iterdir()):
            if not path.is_file():
                continue
            if VERSIONED_SO_RE.search(path.name):
                plain = path.name.split(".so")[0] + ".so"
                if (arch_dir / plain).exists():
                    continue          # soname 由同名副本满足，不是错误
                errors.append(
                    "entry/libs/%s/%s 是版本化 .so：加载器按 soname 找不到它，"
                    "请改名为 .so（或同时提供同名副本 %s）"
                    % (arch_dir.name, path.name, plain))
            elif not path.name.endswith(LIBS_ALLOWED_SUFFIX):
                warns.append(
                    "entry/libs/%s/%s 不是 .so，打包时会被忽略"
                    % (arch_dir.name, path.name))

    profile = root / "build-profile.json5"
    declared = None
    if profile.is_file():
        text = profile.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'"compatibleSdkVersion"\s*:\s*"([^"]+)"', text)
        if match:
            declared = match.group(1)
    wanted = env.get("compatible_sdk")
    if wanted and declared and str(wanted) != str(declared):
        errors.append(
            "build-profile.json5 compatibleSdkVersion=%s 与 env.json "
            "compatible_sdk=%s 不一致（装机可能被拒或用到设备没有的 API）"
            % (declared, wanted))
    elif declared:
        warns.append("compatibleSdkVersion=%s（未配置 env.json compatible_sdk，"
                     "未做一致性校验）" % declared)

    return errors, warns


def package_hap(state, timeout: float = 1800.0):
    env = env_of(state)
    build_json = state.read_json("build.json", default={}) or {}
    errors, warns = preflight_package(state)
    build_json["package_preflight"] = {"errors": errors, "warnings": warns}
    if errors:
        # 这些错在打包后才发现就只能到设备上猜，前置拦下并给出可执行的修法。
        # 记录必须是 FAIL：落成 SKIP 会让 `status` 和门禁对不上（SKIP 表示"没测"，
        # 这里明确是"测了、不合格"）。
        result = state.fail_cmd("package", "; ".join(errors))
        result.stderr = "\n".join(errors)
        build_json["package"] = result.to_dict()
        state.write_json("build.json", build_json)
        return result
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
    """Capture device log for N seconds after launch and look for crashes.

    三个诚实性约束（缺一个就会把"没跑起来"读成"没崩溃"）：

    1. **上游状态向下传播**：install / launch 不是 PASS 时，"崩溃窗口"没有意义，
       这里直接记 SKIP 并说明原因，绝不记 PASS。
    2. **日志必须按本应用过滤**：`hilog` 是全设备缓冲，别的进程崩溃会被算到本应用
       头上（既可能假阳性，也可能把本应用的崩溃淹没）。过滤词取 `bundle_name`
       与 `process_name`（缺省取 bundle 最后一段，鸿蒙进程名常常就长这样）——
       只认 bundle 全名时，日志里只写进程名的行会被全部丢掉，反而变成"没证据"。
    3. **过滤后没有任何本应用日志 → 判 NOT_RUN**：空证据不等于"无崩溃"。
    """
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    bundle = env.get("bundle_name")

    for step in ("install", "launch"):
        status = str((runtime.get(step) or {}).get("status", "NOT_RUN"))
        if status != "PASS":
            result = state.skip_cmd(
                "crash_check",
                "upstream %s is %s - crash window is meaningless without a "
                "running app" % (step, status))
            result.stderr = "SKIP: upstream %s=%s; not a PASS" % (step, status)
            runtime["crash_check"] = result.to_dict()
            runtime["crash_markers_found"] = []
            state.write_json("runtime.json", runtime)
            return result

    hdc = env.get("hdc", "hdc")
    wait_sec = float(env.get("crash_wait_sec", 8))
    timeout = timeout or (wait_sec + 30)

    result = state.run_cmd([hdc, "shell", "timeout", str(int(wait_sec)),
                            "hilog"], label="hilog-crash-window",
                           timeout=timeout)
    raw = result.stdout + "\n" + result.stderr
    lines = raw.splitlines()
    process = env.get("process_name") or (bundle.rsplit(".", 1)[-1] if bundle else "")
    terms = [t for t in {bundle or "", process} if t]
    scoped = ([ln for ln in lines if any(t.lower() in ln.lower() for t in terms)]
              if terms else lines)
    if terms and not scoped and bundle:
        # 日志里的进程名常与 bundle 不同（缩写/连写），先用较宽的词再找一轮：
        # 直接判"没证据"会把真的跑起来的应用读成没测。
        wide = [seg for seg in bundle.split(".") if len(seg) >= 4]
        wide_scoped = [ln for ln in lines
                       if any(t.lower() in ln.lower() for t in wide)]
        if wide_scoped:
            terms, scoped = wide, wide_scoped
    text = "\n".join(scoped).lower()
    crash_markers = ["cppcrash", "jscrash", "appfreeze", "sigsegv", "sigabrt",
                     "faultlog", "process died", "dlopen failed"]
    found = [m for m in crash_markers if m in text]
    result.exit_code = 0  # hilog capture exit code is not meaningful
    if result.status == "PASS" and terms and not scoped:
        # 抓到了窗口，但没有一行属于本应用：不能据此宣称"无崩溃"
        result.status = "NOT_RUN"
        result.stderr = ("no log line matched %s in %ss window - inconclusive, "
                         "not a PASS（可 config set process_name 换过滤词）"
                         % ("/".join(terms), int(wait_sec)))
    elif result.status == "PASS":
        result.status = "FAIL" if found else "PASS"
        result.stderr = ("crash markers found: %s" % ", ".join(found)) if found else \
            ("no crash markers in %ss window (%d line(s)%s)" % (
                int(wait_sec), len(scoped),
                ", filtered by %s" % "/".join(terms) if terms else ", unfiltered"))
    else:
        result.stderr = "crash window capture failed: %s" % result.stderr.strip()[:200]
    runtime["crash_check"] = result.to_dict()
    runtime["crash_check"]["bundle_filtered"] = bool(terms)
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
