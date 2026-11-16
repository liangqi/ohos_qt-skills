"""Build / package / device orchestration.

All commands come from .qt-ohos/env.json (see `qt-ohos-run config`) so the
pipeline stays reproducible. Every command runs through state.run_cmd,
therefore every step has a timeout, an exit code and a log artifact, and
TIMEOUT is never reported as PASS.

env.json keys (all optional; missing pieces make the corresponding stage
SKIP instead of guessing):

    cmake           cmake executable              (default: cmake)
    build_dir       cmake build directory         (default: build-ohos)
    build_cwd       dir holding CMakeLists.txt    (default: project root;
                    CMake 工程常在子目录，例如 fincept-qt/，-S 要用它)
    cmake_args      extra configure args (list)
    build_command   full custom build command (overrides default cmake flow)
    qt_host_sdk     host Qt kit (QT_HOST_PATH)    Qt6 交叉编译必填
    ohos_sdk_native <OHOS SDK>/native             Qt6 交叉编译必填
    ohos_arch       target ABI                    (default: arm64-v8a)
    generator       CMake generator               (default: MinGW Makefiles on
                    Windows when mingw32-make exists, else Ninja/Unix Makefiles)
    make_program    CMAKE_MAKE_PROGRAM            (optional)
    package_target  explicit <target>_make_hap    (default: discovered from
                    *-harmony-deployment-settings.json)
    harmonyos_build hvigor 工程输出目录            (default: <build_dir>/harmonyos-build)
    hvigor          hvigorw(.bat) 绝对路径         (env QT_HARMONYOS_HVIGOR)
    java_home       JAVA_HOME（hvigor 的 node worker 要 java）
    deveco_sdk_home DEVECO_SDK_HOME
    hvigor_home     HVIGOR_USER_HOME              (default: .qt-ohos/hvigor-home)
    npm_cache       npm_config_cache              (default: .qt-ohos/npm-cache)
    device_sdk      compatibleSdkVersion 目标值    (default: 从 SDK 的
                    oh-uni-package.json 读，读不到就不改)
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
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from .state import CommandResult, native_path, find_hdc


def env_of(state) -> Dict:
    return state.read_json("env.json", default={}) or {}


QT6_TOOLCHAIN_REL = os.path.join("lib", "cmake", "Qt6", "qt.toolchain.cmake")
DEPLOY_SETTINGS_GLOB = "**/*-harmony-deployment-settings.json"


def qt6_toolchain(qt_prefix) -> Optional[Path]:
    """`<kit>/lib/cmake/Qt6/qt.toolchain.cmake` —— Qt6 交叉编译的唯一入口。

    预构建 kit 不是"给个 CMAKE_PREFIX_PATH 就能用"的普通 SDK：编译器、sysroot、
    OPENSSL_* 全在 toolchain 文件里。只给 prefix，cmake 会用宿主编译器编出一个
    能在 CI 机器上跑、在设备上 dlopen 失败的 .so——"编译通过"于是彻底失真。
    """
    if not qt_prefix:
        return None
    candidate = Path(str(qt_prefix)) / QT6_TOOLCHAIN_REL
    return candidate if candidate.is_file() else None


def default_generator(env: Dict) -> str:
    """Windows 上 NMake/Ninja 各有各的坑；MinGW Makefiles 是 CLI 场景最稳的。"""
    if env.get("generator"):
        return str(env["generator"])
    if os.name == "nt":
        if env.get("make_program") or shutil.which("mingw32-make"):
            return "MinGW Makefiles"
        return "Ninja" if shutil.which("ninja") else "NMake Makefiles"
    return "Ninja" if shutil.which("ninja") else "Unix Makefiles"


def qt6_configure_problems(env: Dict) -> list:
    """Qt6 kit 缺哪几项，缺的项让 cmake 报出一堆无关错误，这里先讲人话。"""
    problems = []
    host = env.get("qt_host_sdk")
    if not host:
        problems.append("qt_host_sdk 未配置（宿主 kit，QT_HOST_PATH；交叉编译的 moc/rcc 要用它）")
    elif not (Path(host) / "bin").is_dir():
        problems.append("qt_host_sdk=%s 不存在或不含 bin/" % host)
    native = env.get("ohos_sdk_native")
    if not native:
        problems.append("ohos_sdk_native 未配置（<OHOS SDK>/native）")
    elif not (Path(native) / "build" / "cmake" / "ohos.toolchain.cmake").is_file():
        problems.append("ohos_sdk_native=%s 下没有 build/cmake/ohos.toolchain.cmake"
                        % native)
    return problems


def qt6_configure_args(env: Dict) -> list:
    """Qt6 预构建 kit 的 configure 参数（顺序不重要，值是绝对路径）。"""
    args = ["-DCMAKE_TOOLCHAIN_FILE=%s" % qt6_toolchain(env.get("qt_sdk_prefix"))]
    if env.get("qt_host_sdk"):
        args.append("-DQT_HOST_PATH=%s" % env["qt_host_sdk"])
    native = env.get("ohos_sdk_native")
    if native:
        args.append("-DOHOS_SDK_NATIVE=%s" % native)
        chainload = Path(native) / "build" / "cmake" / "ohos.toolchain.cmake"
        args.append("-DQT_CHAINLOAD_TOOLCHAIN_FILE=%s" % chainload)
    args.append("-DOHOS_ARCH=%s" % (env.get("ohos_arch") or "arm64-v8a"))
    if env.get("make_program"):
        args.append("-DCMAKE_MAKE_PROGRAM=%s" % env["make_program"])
    return args


def configure_and_build(state, timeout: float = 1800.0):
    """G3 compile orchestration. Returns the decisive CommandResult."""
    env = env_of(state)
    build_json = state.read_json("build.json", default={}) or {}
    root = Path(state.project_root)
    build_dir = env.get("build_dir", "build-ohos")
    build_abs = Path(native_path(build_dir, root))
    source_abs = Path(native_path(env.get("build_cwd") or ".", root))

    custom = env.get("build_command")
    toolchain = qt6_toolchain(env.get("qt_sdk_prefix"))
    if custom:
        result = state.run_cmd(custom, label="build-custom", timeout=timeout)
        build_json["mode"] = "custom"
    elif toolchain:
        problems = qt6_configure_problems(env)
        if problems:
            # 直接判 FAIL 并给出 config set 的确切键名：让 cmake 去报
            # "Could not find a package configuration file" 只会把人带偏。
            result = state.fail_cmd("compile", "; ".join(problems))
            result.stderr = "\n".join(problems)
            build_json["mode"] = "qt6"
            build_json["qt6_problems"] = problems
            build_json["compile"] = result.to_dict()
            state.write_json("build.json", build_json)
            return result
        cmake = env.get("cmake", "cmake")
        generator = default_generator(env)
        configure = ([cmake, "-S", str(source_abs), "-B", str(build_abs),
                      "-G", generator, "-DCMAKE_BUILD_TYPE=Release"]
                     + qt6_configure_args(env)
                     + _cmake_args(env.get("cmake_args")))
        result = state.run_cmd(configure, label="cmake-configure",
                               timeout=min(timeout, 900), cwd=root)
        build_json["mode"] = "qt6"
        build_json["generator"] = generator
        build_json["source_dir"] = str(source_abs)
        if result.status == "PASS":
            result = state.run_cmd([cmake, "--build", str(build_abs),
                                    "--parallel"],
                                   label="cmake-build", timeout=timeout, cwd=root)
    else:
        # 只有 prefix、没有 toolchain：要么是 Qt5 SDK，要么是照抄了 Qt6 教程。
        # 两种情况都保留旧路径（Qt5 的 qmake/cmake 集成确实这么用），但要记下来。
        cmake = env.get("cmake", "cmake")
        cmake_args = _cmake_args(env.get("cmake_args"))
        qt_prefix = env.get("qt_sdk_prefix")
        if qt_prefix:
            cmake_args = cmake_args + ["-DCMAKE_PREFIX_PATH=%s" % qt_prefix]
        generator = default_generator(env)
        configure = ([cmake, "-S", str(source_abs), "-B", str(build_abs),
                      "-DCMAKE_BUILD_TYPE=Release"]
                     + (["-G", generator] if env.get("generator") else [])
                     + cmake_args)
        result = state.run_cmd(configure, label="cmake-configure",
                               timeout=min(timeout, 600), cwd=root)
        build_json["mode"] = "cmake"
        if result.status == "PASS":
            result = state.run_cmd([cmake, "--build", str(build_abs), "--parallel"],
                                   label="cmake-build", timeout=timeout, cwd=root)
    build_json["compile"] = result.to_dict()
    if result.status == "PASS":
        build_json["artifacts"] = _find_artifacts(state.project_root, build_dir)
    state.write_json("build.json", build_json)
    return result


VERSIONED_SO_RE = re.compile(r"\.so(\.\d+)+$")
LIBS_ALLOWED_SUFFIX = (".so", ".a")


def _cmake_args(raw) -> list:
    """env.json 的 cmake_args 允许两种写法：JSON 数组，或一条命令行字符串。

    字符串写法是 `config set cmake_args "-G Ninja ..."` 的自然结果；旧实现直接
    当列表用，`str + list` 抛 TypeError，把"换生成器"这个最普通的诉求变成崩溃。
    """
    if not raw:
        return []
    if isinstance(raw, str):
        import shlex
        return shlex.split(raw, posix=(os.name != "nt"))
    return [str(item) for item in raw]


def _sdk_key(value) -> tuple:
    """把 "5.0.5(17)" / "5.0.5（17）" / "17" / 17 归一成 (版本串, API 号)。"""
    if value is None:
        return ("", 0)
    text = str(value).strip().replace("（", "(").replace("）", ")")
    api = 0
    match = re.search(r"\((\d+)\)", text)
    if match:
        api = int(match.group(1))
        text = text[:match.start()].strip()
    elif text.isdigit():
        api, text = int(text), ""
    return (text, api)


def _sdk_equal(left, right) -> bool:
    left_key, right_key = _sdk_key(left), _sdk_key(right)
    if not left_key[1] or not right_key[1]:
        return left_key[0] == right_key[0] and left_key[1] == right_key[1]
    # 都有 API 号：API 号是硬约束；版本串只在两边都写了时才需要一致
    if left_key[1] != right_key[1]:
        return False
    return not (left_key[0] and right_key[0]) or left_key[0] == right_key[0]


def _package_dirs(state, env: Dict) -> list:
    """打包产物的落点，按优先级：显式配置 → Qt6 部署目录 → 工程根。

    旧实现只看工程根下的 `entry/libs` 与 `build-profile.json5`，那是 Qt5 壳工程的
    布局；Qt6 的 `_make_hap` / `harmonydeployqt6` 输出在
    `<build_dir>/harmonyos-build/`，同一套检查在根目录永远"什么都没找到"，
    于是 preflight 形同虚设。
    """
    root = Path(state.project_root)
    candidates = []
    for raw in (env.get("package_dir"), env.get("harmonyos_build")):
        if raw:
            candidates.append((root / raw).resolve())
    candidates.append((root / (env.get("build_dir") or "build-ohos")
                       / "harmonyos-build").resolve())
    candidates.append(root.resolve())
    seen, dirs = set(), []
    for path in candidates:
        if str(path) in seen:
            continue
        seen.add(str(path))
        if path.is_dir():
            dirs.append(path)
    return dirs


def _sdk_from_sdk_home(env: Dict) -> Optional[str]:
    """从 SDK 安装目录读真实版本（`"6.0.2(22)"` 形式）。

    Qt6 模板里的 `compatibleSdkVersion` 写死在 `src/harmonyos/templates/
    build-profile.json5`（实测是 `6.1.0(23)`），本机 SDK 不是这个版本时 hvigor 直接
    `00303082 Unable to find the compatibleSdkVersion ... in SDK Manager`。
    唯一可靠的来源是 SDK 自己的 `oh-uni-package.json`。
    """
    candidates = []
    for key in ("deveco_sdk_home", "deveco_path", "ohos_sdk_native"):
        raw = env.get(key)
        if not raw:
            continue
        base = Path(raw)
        candidates += [base / "default" / "openharmony" / "oh-uni-package.json",
                       base / "oh-uni-package.json",
                       base / ".." / "oh-uni-package.json"]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8",
                                                  errors="replace"))
        except ValueError:
            continue
        version = str(data.get("version") or "").strip()
        api = data.get("apiVersion") or data.get("api_version")
        if version and api:
            # version 可能是 6.0.2.1 这种四段，compatibleSdkVersion 用三段
            parts = version.split(".")
            short = ".".join(parts[:3]) if len(parts) >= 3 else version
            return "%s(%s)" % (short, api)
        if api:
            return str(api)
    return None


def _strip_json5(text: str) -> str:
    """去掉 JSON5 的注释与尾逗号，够用于读 build-profile.json5 / module.json5。"""
    out, i, n = [], 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = n if close < 0 else close + 2
            continue
        out.append(ch)
        i += 1
    stripped = "".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", stripped)


def read_json5(path) -> Optional[dict]:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for candidate in (text, _strip_json5(text)):
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def align_sdk_profile(state, env: Dict) -> list:
    """把打包目录里 `build-profile.json5` 的 compatibleSdkVersion 对齐到真 SDK。

    返回值是人读的改动说明（空列表 = 没动）。这是**唯一**该改这个字段的地方：
    铁律 B4 禁止在源码/模板里设 compileSdkVersion / targetSdkVersion，而
    compatibleSdkVersion 必须等于 SDK 里实际安装的版本，否则 hvigor 报 00303082。
    """
    wanted = env.get("compatible_sdk") or _sdk_from_sdk_home(env)
    if not wanted:
        return []
    changes = []
    for directory in _package_dirs(state, env):
        profile = directory / "build-profile.json5"
        if not profile.is_file():
            continue
        text = profile.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'("compatibleSdkVersion"\s*:\s*)'
                          r'(?:"([^"]*)"|(\d+))', text)
        if not match:
            continue
        current = match.group(2) or match.group(3)
        if _sdk_equal(current, wanted):
            continue
        replacement = '%s"%s"' % (match.group(1), wanted)
        profile.write_text(text[:match.start()] + replacement + text[match.end():],
                           encoding="utf-8")
        changes.append("%s: compatibleSdkVersion %s -> %s"
                       % (profile.as_posix(), current, wanted))
    return changes


def _sdk_problems(state, env: Dict) -> list:
    """compatibleSdkVersion 与 SDK 版本不一致时给可执行的修法。"""
    want = _sdk_from_sdk_home(env)
    declared = None
    for directory in _package_dirs(state, env):
        profile = directory / "build-profile.json5"
        if not profile.is_file():
            continue
        match = re.search(r'"compatibleSdkVersion"\s*:\s*'
                          r'(?:"([^"]+)"|(\d+))',
                          profile.read_text(encoding="utf-8", errors="replace"))
        if match:
            declared = match.group(1) or match.group(2)
            break
    if want and declared and not _sdk_equal(declared, want):
        return ["build-profile.json5 compatibleSdkVersion=%s 与本机 SDK=%s 不一致"
                "（hvigor 会报 00303082）；本工具会自动对齐，"
                "也可 `qt-ohos-run config set compatible_sdk %s`"
                % (declared, want, want)]
    return []


def preflight_package(state):
    """打包前检查 libs 落点、非 .so 文件、compatibleSdkVersion 与 SDK 版本。

    1. **版本化 .so**：`libfoo.so.1` 放进 `entry/libs/<abi>/` 会被原样打进 HAP，
       但加载器按 soname 找 `libfoo.so`，装机后 dlopen 失败。
    2. **非 .so 文件**：hvigor 只搬 `.so`（`.a` 静态库不进包），其它后缀被静默忽略，
       表现为"我明明放进去 libruntime.so.1.2"。
    3. **compatibleSdkVersion**：与 SDK 实际版本不一致时 hvigor 直接拒绝打包。

    返回 (errors, warnings)，都是人读字符串。
    """
    env = env_of(state)
    errors, warns = [], []
    dirs = _package_dirs(state, env)
    if not dirs:
        warns.append("找不到打包目录（已试 package_dir / <build_dir>/harmonyos-build / "
                     "工程根）——跳过 libs 与 SDK 版本检查")

    for directory in dirs:
        for arch_dir in sorted(directory.glob("**/entry/libs/*")):
            if not arch_dir.is_dir():
                continue
            for path in sorted(arch_dir.iterdir()):
                if not path.is_file():
                    continue
                if VERSIONED_SO_RE.search(path.name):
                    plain = path.name.split(".so")[0] + ".so"
                    if (arch_dir / plain).exists():
                        continue      # soname 由同名副本满足，不是错误
                    errors.append(
                        "%s 是版本化 .so：加载器按 soname 找不到它，"
                        "请改名为 .so（或同时提供同名副本 %s）"
                        % (path.as_posix(), plain))
                elif not path.name.endswith(LIBS_ALLOWED_SUFFIX):
                    warns.append("%s 不是 .so，打包时会被忽略"
                                 % path.as_posix())

    declared = None
    for directory in dirs:
        profile = directory / "build-profile.json5"
        if not profile.is_file():
            continue
        match = re.search(r'"compatibleSdkVersion"\s*:\s*'
                          r'(?:"([^"]+)"|(\d+))',
                          profile.read_text(encoding="utf-8", errors="replace"))
        if match:
            declared = match.group(1) or match.group(2)
            if '"runtimeOS"' in profile.read_text(encoding="utf-8",
                                                  errors="replace"):
                runtime_os = re.search(r'"runtimeOS"\s*:\s*"([^"]+)"',
                                       profile.read_text(encoding="utf-8",
                                                         errors="replace"))
                if runtime_os and runtime_os.group(1) != "HarmonyOS":
                    warns.append("%s runtimeOS=%s（Qt 应用需 HarmonyOS）"
                                 % (profile.as_posix(), runtime_os.group(1)))
            break

    wanted = env.get("compatible_sdk")
    if wanted and declared and not _sdk_equal(wanted, declared):
        errors.append(
            "build-profile.json5 compatibleSdkVersion=%s 与 env.json "
            "compatible_sdk=%s 不一致（装机可能被拒或用到设备没有的 API）"
            % (declared, wanted))
    else:
        errors.extend(_sdk_problems(state, env))

    return errors, warns


def find_hvigor(env: Dict) -> Optional[str]:
    """定位 hvigorw。缺它时 hvigor 只打印 warned 并**返回 0**——典型的假成功。"""
    raw = env.get("hvigor")
    candidates = []
    if raw:
        candidates.append(Path(raw))
    for key in ("deveco_path", "deveco_studio", "deveco_sdk_home"):
        base = env.get(key)
        if base:
            candidates.append(Path(base) / "tools" / "hvigor" / "bin"
                              / ("hvigorw.bat" if os.name == "nt" else "hvigorw"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    for name in ("hvigorw.bat", "hvigorw"):
        found = shutil.which(name)
        if found:
            return found
    return None


def hvigor_env(state, env: Dict, create: bool = True) -> Dict:
    """hvigor 跑起来需要的五件事，缺一个就在签名/构建阶段炸。

    1. `QT_HARMONYOS_HVIGOR`：绝对路径；不给时 `_make_hap` 只打印
       "No hvigor path specified, skipping build" 且**返回 0**。
    2. `JAVA_HOME`：DevEco 自带 jbr。
    3. `DEVECO_SDK_HOME`：CLI 的 sdk 根。
    4. `HVIGOR_USER_HOME`：必须是绝对可写路径，否则 EPERM mkdir；
       相对路径会被静默回退（并提示 Invalid custom userhome hvigor data dir）。
    5. `npm_config_cache`：必须在可写盘，否则 npm EPERM。
    """
    extra: Dict[str, str] = {}
    root = Path(state.project_root)
    hvigor = find_hvigor(env)
    if hvigor:
        extra["QT_HARMONYOS_HVIGOR"] = hvigor
    java_home = env.get("java_home")
    if not java_home:
        for key in ("deveco_path", "deveco_studio"):
            base = env.get(key)
            if base and (Path(base) / "jbr").is_dir():
                java_home = str(Path(base) / "jbr")
                break
    if java_home:
        extra["JAVA_HOME"] = str(Path(java_home).resolve())
    sdk_home = env.get("deveco_sdk_home") or env.get("deveco_path")
    if sdk_home:
        candidate = Path(sdk_home)
        if (candidate / "sdk").is_dir():
            candidate = candidate / "sdk"
        extra["DEVECO_SDK_HOME"] = str(candidate.resolve())
    hvigor_home = env.get("hvigor_home") or (root / ".qt-ohos" / "hvigor-home")
    npm_cache = env.get("npm_cache") or (root / ".qt-ohos" / "npm-cache")
    if create:
        # 打/装包时才落目录；doctor 这类只读体检不该在别人工程里建东西。
        Path(hvigor_home).mkdir(parents=True, exist_ok=True)
        Path(npm_cache).mkdir(parents=True, exist_ok=True)
    extra["HVIGOR_USER_HOME"] = str(Path(hvigor_home).resolve())
    extra["npm_config_cache"] = str(Path(npm_cache).resolve())
    return extra


HVIGOR_DIAGNOSTICS = [
    (r"No hvigor path specified",
     "hvigor 没被调用（它返回 0 但什么都没做）：config set hvigor <绝对路径>/hvigorw.bat"),
    (r"EPERM: operation not permitted, symlink",
     "hvigor 要建 junction 但当前不是管理员：用 `mklink /J` 预建 "
     "node_modules/@ohos/hvigor 与 hvigor-ohos-plugin 两个链接"),
    (r"EPERM: operation not permitted, mkdir.*\.hvigor",
     "HVIGOR_USER_HOME 不可写：config set hvigor_home <绝对可写路径>"),
    (r"npm ERR! code EPERM",
     "npm 缓存在不可写盘：config set npm_cache <绝对可写路径>"),
    (r"00303082|Unable to find the compatibleSdkVersion",
     "compatibleSdkVersion 与本机 SDK 不一致：config set compatible_sdk \"<ver>(<api>)\" "
     "（值见 SDK 的 oh-uni-package.json）"),
    (r"Failed to start hvigorw",
     "hvigorw 用了相对路径：QT_HARMONYOS_HVIGOR 必须是绝对路径"),
]


def hvigor_diagnostics(text: str) -> list:
    low = (text or "").lower()
    return [fix for pattern, fix in HVIGOR_DIAGNOSTICS
            if re.search(pattern.lower(), low)]


def deployment_settings(state, env: Dict) -> list:
    """Qt6 的 `_make_hap` 依赖 `<target>-harmony-deployment-settings.json`。"""
    root = Path(state.project_root)
    build_dir = (root / (env.get("build_dir") or "build-ohos")).resolve()
    found = sorted(build_dir.glob("**/*-harmony-deployment-settings.json"))
    return [p for p in found if "/.qt-ohos/" not in p.as_posix()]


def auto_package(state, env: Dict, timeout: float):
    """内置 Qt6 打包两条路；都不可用时明确 SKIP，而不是假装跑过。

    路 1：`cmake --build <bld> --target <target>_make_hap`
           （`Qt6HarmonyOSMacros.cmake:663-667` 定义的一键目标）
    路 2：`harmonydeployqt6 --input <settings> --output <dir> --hvigor <abs>`
    用户自备的 `package_command` 仍然是第一优先级（见 `package_hap`）。
    """
    root = Path(state.project_root)
    build_dir = (root / (env.get("build_dir") or "build-ohos")).resolve()
    settings = deployment_settings(state, env)
    target = env.get("package_target")
    if not target and settings:
        stem = settings[0].name[:-len("-harmony-deployment-settings.json")]
        target = stem + "_make_hap"
    extra = hvigor_env(state, env)
    notes = []
    if "QT_HARMONYOS_HVIGOR" not in extra:
        notes.append("未找到 hvigorw（找不到时会打印 No hvigor path specified 并"
                     "返回 0）：config set hvigor <绝对路径>/hvigorw.bat")

    if target and shutil.which("cmake"):
        result = state.run_cmd([env.get("cmake", "cmake"), "--build",
                                str(build_dir), "--target", target],
                               label="package-make-hap", timeout=timeout,
                               cwd=root, extra_env=extra)
        if result.status == "PASS":
            result.stderr += ("\n[qt-ohos-run] 假成功守卫：hvigor 未被调用"
                              if re.search(r"No hvigor path specified",
                                           result.stdout + result.stderr)
                              else "")
            if "No hvigor path specified" in (result.stdout + result.stderr):
                result.status = "FAIL"
        fixes = hvigor_diagnostics(result.stdout + "\n" + result.stderr)
        if fixes:
            notes.extend(fixes)
            if result.status == "PASS":
                result.status = "FAIL"
    else:
        hdq = None
        for name in ("harmonydeployqt6", "harmonydeployqt6.exe"):
            candidate = shutil.which(name)
            if candidate:
                hdq = candidate
                break
            if env.get("qt_host_sdk"):
                path = Path(env["qt_host_sdk"]) / "bin" / name
                if path.is_file():
                    hdq = str(path)
                    break
        if hdq and settings:
            out_dir = (root / (env.get("harmonyos_build") or "")
                       ) if env.get("harmonyos_build") else build_dir / "harmonyos-build"
            args = [hdq, "--input", str(settings[0]), "--output", str(out_dir)]
            if "QT_HARMONYOS_HVIGOR" in extra:
                args += ["--hvigor", extra["QT_HARMONYOS_HVIGOR"]]
            result = state.run_cmd(args, label="harmonydeployqt6", timeout=timeout,
                                   cwd=root, extra_env=extra)
            fixes = hvigor_diagnostics(result.stdout + "\n" + result.stderr)
            if fixes:
                notes.extend(fixes)
                if result.status == "PASS":
                    result.status = "FAIL"
        else:
            reason = ("既没有 <target>-harmony-deployment-settings.json，也没有 "
                      "harmonydeployqt6：先 `build` 成功一次（Qt6 的部署文件由构建"
                      "产物生成），或用 `package --record-only --hap <file>` 登记"
                      "外部打包结果")
            if notes:
                reason += "；" + "；".join(notes)
            result = state.skip_cmd("package", reason)
    if notes:
        result.stderr = (result.stderr + "\n[qt-ohos-run] " + "\n[qt-ohos-run] ".join(notes)).strip()
    return result


def package_hap(state, timeout: float = 1800.0):
    env = env_of(state)
    build_json = state.read_json("build.json", default={}) or {}
    aligned = align_sdk_profile(state, env)
    errors, warns = preflight_package(state)
    build_json["package_preflight"] = {"errors": errors, "warnings": warns,
                                       "sdk_aligned": aligned}
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
    if command:
        result = state.run_cmd(command, label="package-hap", timeout=timeout,
                               cwd=env.get("package_dir") or None,
                               extra_env=hvigor_env(state, env))
        fixes = hvigor_diagnostics(result.stdout + "\n" + result.stderr)
        if fixes:
            result.stderr += "\n[qt-ohos-run] " + "\n[qt-ohos-run] ".join(fixes)
            if result.status == "PASS":
                result.status = "FAIL"
    else:
        result = auto_package(state, env, timeout)
    build_json["package"] = result.to_dict()
    if result.status == "PASS":
        hap = find_hap(state.project_root, env.get("hap_glob"))
        build_json["hap"] = hap
        if not hap:
            result.status = "FAIL"
            result.stderr += "\n[qt-ohos-run] build succeeded but no .hap found"
            build_json["package"] = result.to_dict()
        else:
            ability = detect_ability(state, env)
            if ability and not env.get("ability_name"):
                env["ability_name"] = ability
                state.data.setdefault("env", {}).update(env)
                state.save()
    state.write_json("build.json", build_json)
    return result


def find_hap(project_root, hap_glob: Optional[str] = None) -> Optional[str]:
    """找 HAP 产物：签名版优先，且**只认真实存在的文件**。

    两个实测坑：①`signed/` 与 `unsigned/` 同名产物并存时，`sorted(glob)` 的
    顺序会让 install 随机挑到 unsigned（装不上）；②产物被手工删掉后，旧路径
    仍留在 build.json 里，install 反复失败却看不出原因。
    """
    root = Path(project_root)
    patterns = hap_glob.split(",") if hap_glob else [
        "**/build/**/*.hap", "**/*.hap"]
    found = []
    for pattern in patterns:
        for path in sorted(globmod.glob(str(root / pattern), recursive=True)):
            if "/.qt-ohos/" in path.replace("\\", "/"):
                continue
            if not Path(path).is_file() or Path(path).stat().st_size == 0:
                continue
            found.append(path)
    if not found:
        return None
    found.sort(key=lambda item: (0 if "-signed" in Path(item).name else 1,
                                 Path(item).as_posix()))
    return str(Path(found[0]).relative_to(root).as_posix())


def detect_ability(state, env: Dict) -> Optional[str]:
    """从 module.json5 读 mainElement/abilities，替代写死的 `EntryAbility`。

    Qt6 模板的 ability 叫 `QAbility`（`entry/src/main/ets/qability/QAbility.ets`），
    而 Qt5 壳工程叫 `EntryAbility`。默认值猜错时 `aa start` 报的是
    "ability not found"，看起来像应用没起来。
    """
    root = Path(state.project_root)
    modules = []
    for base in _package_dirs(state, env) or [root]:
        modules += sorted(base.glob("**/module.json5"))
    modules = [m for m in modules if "/.qt-ohos/" not in m.as_posix()]
    for path in modules:
        data = read_json5(path)
        if not isinstance(data, dict):
            continue
        module = data.get("module") if isinstance(data.get("module"), dict) else data
        abilities = module.get("abilities") or []
        names = [a.get("name") for a in abilities if isinstance(a, dict) and a.get("name")]
        main = module.get("mainElement")
        if main and main in names:
            return main
        if names:
            return names[0]
    return None


def install_hap(state, timeout: float = 300.0):
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    build_json = state.read_json("build.json", default={}) or {}
    root = Path(state.project_root)
    hap = build_json.get("hap")
    hdc = env.get("hdc") or find_hdc()
    if not hap:
        result = state.skip_cmd("install", "no HAP artifact recorded")
    else:
        path = Path(hap)
        if not path.is_absolute():
            path = root / hap
        if not path.is_file():
            # 缓存里的路径可能已被删除：重新找一次，再决定 FAIL
            fresh = find_hap(root, env.get("hap_glob"))
            if fresh:
                path = root / fresh
                build_json["hap"] = fresh
                state.write_json("build.json", build_json)
        if not path.is_file():
            result = state.fail_cmd(
                "install", "HAP 不存在：%s（重新 package 或 package --record-only --hap）"
                % path)
        else:
            # hdc 在 Windows 上不认 POSIX 相对路径，报的错是
            # "Error opening file: no such file or directory, path:C:\...\C:/Users/..."
            result = state.run_cmd([hdc, "install", "-r", native_path(path)],
                                   label="hdc-install", timeout=timeout)
            if result.status == "PASS" and "fail" in (
                    result.stdout + result.stderr).lower():
                result.status = "FAIL"
    runtime["install"] = result.to_dict()
    state.write_json("runtime.json", runtime)
    return result


def launch_app(state, timeout: float = 120.0):
    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    hdc = env.get("hdc") or find_hdc()
    bundle = env.get("bundle_name")
    ability = env.get("ability_name") or detect_ability(state, env)
    if not bundle:
        result = state.skip_cmd("launch", "env.json: bundle_name not set")
    elif not ability:
        result = state.fail_cmd(
            "launch",
            "没找到 ability 名：env.json 无 ability_name，且打包目录里没有可解析的 "
            "module.json5（Qt6 模板是 QAbility，Qt5 是 EntryAbility）")
    else:
        result = state.run_cmd(
            [hdc, "shell", "aa", "start", "-b", bundle, "-a", ability],
            label="aa-start", timeout=timeout)
        combined = (result.stdout + result.stderr).lower()
        if result.status == "PASS" and ("error" in combined or "fail" in combined):
            result.status = "FAIL"
            result.stderr += ("\n[qt-ohos-run] 用到的 ability=%s；若报 ability not found，"
                              "用 `aa dump -a` 或 module.json5 核对后 "
                              "`config set ability_name <name>`" % ability)
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


def find_devecocli(env: Dict) -> Optional[str]:
    raw = env.get("devecocli")
    if raw and Path(raw).is_file():
        return str(Path(raw).resolve())
    return shutil.which("devecocli")


def _shot_devecocli(state, cli: str, target: Path, timeout: float):
    return state.run_cmd([cli, "ui", "screenshot", "--path", str(target)],
                         label="ui-screenshot-" + target.stem, timeout=timeout)


def _shot_hdc(state, env: Dict, target: Path, timeout: float):
    """hdc 兜底：设备侧截图 + 拉回（`hdc file recv` 会返回 0 而不落文件）。"""
    hdc = env.get("hdc") or find_hdc()
    remote = "/data/local/tmp/qt_ohos_shot_%s.jpeg" % target.stem
    shot = state.run_cmd([hdc, "shell", "snapshot_display", "-f", remote],
                         label="snapshot-display-" + target.stem, timeout=timeout)
    if shot.status != "PASS":
        return shot
    ok, channel, detail = state.hdc_pull(remote, target, timeout=timeout, hdc=hdc)
    state.run_cmd([hdc, "shell", "rm", "-f", remote],
                  label="snapshot-cleanup", timeout=30)
    shot.stderr = (shot.stderr + "\n[qt-ohos-run] pull=%s %s"
                   % (channel, detail)).strip()
    if not ok:
        shot.status = "FAIL"
    return shot


def _tap_point(state, env: Dict, cli: Optional[str], image, timeout: float):
    """优先按布局树里第一个可点节点取中心；否则退到屏幕中心。"""
    if cli:
        dump = state.run_cmd([cli, "ui", "layout", "--format", "json"],
                             label="ui-layout", timeout=timeout)
        if dump.status == "PASS":
            point = _bounds_center(dump.stdout)
            if point:
                return point, "layout-clickable"
    return (image.width // 2, image.height // 2), "screen-center"


def _bounds_center(text: str):
    match = re.search(r'"bounds"\s*:\s*"\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', text or "")
    if not match:
        return None
    x1, y1, x2, y2 = (int(match.group(i)) for i in range(1, 5))
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def smoke_interact(state, timeout: float = 180.0):
    """G10 的机器取证：截图 → 交互 → 截图，量化"界面确实变了"。

    G10 的裁决权仍在人（`mark-gate G10`），这里只生产可审阅的证据：
    两张截图、像素差、颜色数、进程存活、布局树点击点。任何一步取不到证据就
    如实降级（PARTIAL/FAIL），绝不因为"截图命令返回 0"就宣称界面对了——
    `hdc file recv` 返回 0 却不落文件是这类假成功最常见的来源。
    """
    from . import png as png_mod

    env = env_of(state)
    runtime = state.read_json("runtime.json", default={}) or {}
    bundle = env.get("bundle_name")
    shots = Path(state.project_root) / ".qt-ohos" / "shots"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = shots / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence = {"dir": str(out_dir.relative_to(Path(state.project_root))),
                "bundle": bundle}

    if not bundle:
        result = state.skip_cmd("smoke_interact", "env.json: bundle_name not set")
        runtime["smoke_interact"] = result.to_dict()
        state.write_json("runtime.json", runtime)
        return result

    cli = find_devecocli(env)
    shot_a, shot_b = out_dir / "before.png", out_dir / "after.png"
    first = (_shot_devecocli(state, cli, shot_a, timeout) if cli
             else _shot_hdc(state, env, shot_a, timeout))
    if first.status != "PASS" or not shot_a.is_file():
        result = state.fail_cmd("smoke_interact",
                               "截图失败：%s" % (first.stderr or "").strip()[:300])
        runtime["smoke_interact"] = result.to_dict()
        state.write_json("runtime.json", runtime)
        return result

    image_a = png_mod.read_png(shot_a)
    if image_a is None:
        result = state.fail_cmd("smoke_interact",
                               "截图不是可解析的 PNG：%s（hdc 兜底可能是 JPEG）"
                               % shot_a)
        runtime["smoke_interact"] = result.to_dict()
        state.write_json("runtime.json", runtime)
        return result

    point, point_source = _tap_point(state, env, cli, image_a, timeout)
    if cli:
        tap = state.run_cmd([cli, "ui", "click", str(point[0]), str(point[1])],
                            label="ui-click", timeout=timeout)
    else:
        hdc = env.get("hdc") or find_hdc()
        tap = state.run_cmd([hdc, "shell", "uitest", "uiInput", "click",
                             str(point[0]), str(point[1])],
                            label="uiInput-click", timeout=timeout)
    time.sleep(1.5)

    second = (_shot_devecocli(state, cli, shot_b, timeout) if cli
              else _shot_hdc(state, env, shot_b, timeout))
    image_b = png_mod.read_png(shot_b) if second.status == "PASS" else None
    ratio = png_mod.diff_ratio(image_a, image_b) if image_b else None
    colors_a = png_mod.distinct_colors(image_a)
    colors_b = png_mod.distinct_colors(image_b) if image_b else None

    hdc = env.get("hdc") or find_hdc()
    alive = state.run_cmd([hdc, "shell", "pidof", bundle],
                          label="pidof", timeout=60)
    pid = (alive.stdout or "").strip()
    evidence.update({
        "tap": {"x": point[0], "y": point[1], "source": point_source,
                "status": tap.status},
        "shot_before": str(shot_a.relative_to(Path(state.project_root))),
        "shot_after": (str(shot_b.relative_to(Path(state.project_root)))
                       if image_b else None),
        "diff_ratio": ratio,
        "distinct_colors_before": colors_a,
        "distinct_colors_after": colors_b,
        "pid": pid or None,
        "devecocli": bool(cli),
    })
    runtime["smoke_interact"] = evidence
    state.write_json("runtime.json", runtime)

    problems = []
    if not cli:
        problems.append("用 hdc 兜底截图，交互走 uitest（devecocli 不可用时结果更脆）")
    if colors_a < 3:
        problems.append("截图只有 %d 种颜色，几乎肯定是黑屏/空白" % colors_a)
    if image_b is None:
        problems.append("交互后截图不可解析")
    elif ratio is not None and ratio < 0.005:
        problems.append("交互前后像素差 %.3f%%，界面没有可观察的变化" % (ratio * 100))
    if not pid:
        problems.append("交互后进程不在（pidof %s 为空）——可能已崩溃" % bundle)

    detail = ("shots=%s diff=%s colors=%s/%s pid=%s tap=%s"
              % (evidence["dir"],
                 "%.2f%%" % (ratio * 100) if ratio is not None else "n/a",
                 colors_a, colors_b, pid or "-",
                 "%d,%d(%s)" % (point[0], point[1], point_source)))
    status = "PASS" if not problems else ("PARTIAL" if image_b else "FAIL")
    result = CommandResult(command="", label="smoke-interact", status=status,
                           start_time=time.strftime("%Y-%m-%dT%H:%M:%S"),
                           stdout=detail, evidence=evidence["dir"],
                           stderr=("\n".join(problems) if problems
                                   else "机器取证通过（G10 仍需人工裁决）"))
    state.data.setdefault("commands", []).append(result.to_dict())
    state.save()
    runtime["smoke_interact"]["result"] = result.to_dict()
    state.write_json("runtime.json", runtime)
    return result
