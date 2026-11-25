"""configure / build / install for the Qt OHOS SDK (variant parameterised).

Python replacement of compile-qt-sdk.sh - with the Windows gap closed:
the bash script could not run the build on Windows at all; here mingw32-make
is spawned directly with the SHELL=cmd.exe override, which is safe from any
host shell (see semantic/qt-harmonyos-build.md "incremental build & install").

Variant axes:  Qt 5.12 / 5.15   x   release / debug   x   gl (desktop) / gles

Directory layout (compile-qt-sdk.sh conventions):
    <build_root>/build-<SDK_NAME>/     shadow build dir
    <sdk_root>/<SDK_NAME>/             installed SDK (CMAKE_PREFIX_PATH)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import envcheck
from .state import ForgeState

# ---------------------------------------------------------------- variants

# Skip lists transcribed from semantic/qt-harmonyos-build.md.
SKIP_5_12 = [
    "qt3d", "qtactiveqt", "qtandroidextras", "qtcanvas3d", "qtconnectivity",
    "qtdatavis3d", "qtdoc", "qtlocation", "qtmacextras", "qtnetworkauth",
    "qtpim", "qtpurchasing", "qtqa", "qtremoteobjects", "qtrepotools",
    "qtscript", "qtscxml", "qtsensors", "qtserialbus", "qtserialport",
    "qtspeech", "qtsystems", "qttools", "qttranslations",
    "qtvirtualkeyboard", "qtwayland", "qtwebchannel", "qtwebengine",
    "qtwebglplugin", "qtwebsockets", "qtwebview", "qtwinextras",
    "qtx11extras", "doc",
]
SKIP_5_15 = [
    "doc", "qtactiveqt", "qtandroidextras", "qtcanvas3d", "qtdoc",
    "qtfeedback", "qtgamepad", "qtlocation", "qtmacextras", "qtnetworkauth",
    "qtpim", "qtpurchasing", "qtqa", "qtremoteobjects", "qtrepotools",
    "qtscript", "qtsystems", "qttools", "qtwayland", "qtwebchannel",
    "qtwebengine", "qtwebglplugin", "qtwinextras", "qtx11extras",
    "qtopcua", "qtknx", "qtconnectivity", "coap",
]


def resolve_skip_list(qt_version, skip_extra=None, with_modules=None):
    """Default skip list for the version, minus with_modules, plus
    skip_extra. Returns (skip_list, ignored_with) - with entries not in
    the default list are ignored (reported, not applied)."""
    skip = list(QT_VERSIONS[qt_version][1])
    ignored_with = []
    for mod in with_modules or []:
        if mod in skip:
            skip.remove(mod)
        else:
            ignored_with.append(mod)
    for mod in skip_extra or []:
        if mod not in skip:
            skip.append(mod)
    return skip, ignored_with


QT_VERSIONS = {"5.12": ("Qt5.12.12-arm64-v8a", SKIP_5_12),
               "5.15": ("Qt5.15.16-arm64-v8a", SKIP_5_15)}

DEFAULT_TIMEOUTS = {"configure": 1800.0, "build": 14400.0, "install": 3600.0}


def sdk_dir_name(qt_version: str, render: str, build_type: str) -> str:
    """Installed SDK directory name (compile-qt-sdk.sh convention)."""
    if qt_version not in QT_VERSIONS:
        raise ValueError("unsupported Qt version %r (source-buildable: %s); "
                         "6.12 ships prebuilt - register it, do not compile"
                         % (qt_version, ", ".join(QT_VERSIONS)))
    name = QT_VERSIONS[qt_version][0]
    if render == "gles":
        name += "-gles"
    elif render == "gles3":
        name += "-gles3"
    if build_type == "debug":
        name += "-debug"
    return name


# ---------------------------------------------------------------- variants
# The build context is multi-slot: one slot per configured variant
# (qt_version x render x build_type), with an `active` pointer that
# build/install/verify/release operate on. This allows maintaining e.g.
# 5.15-gl-release and 5.12-gles-debug side by side in one forge home.

def variant_key(qt_version: str, render: str, build_type: str) -> str:
    return "%s-%s-%s" % (qt_version, render, build_type)


def ensure_variants(st: ForgeState) -> None:
    """Migrate legacy single-slot build section (qt_version at top level)
    into the multi-variant slot structure, in place."""
    build = st.section("build")
    if "variants" in build:
        return
    legacy = dict(build)
    build.clear()
    build["variants"] = {}
    if legacy.get("qt_version"):
        key = variant_key(str(legacy["qt_version"]),
                          str(legacy.get("render") or "gl"),
                          str(legacy.get("build_type") or "release"))
        build["variants"][key] = legacy
        build["active"] = key


def build_ctx(st: ForgeState) -> Dict:
    """Return the active variant slot (live reference inside state.data;
    callers mutating it must `st.save()` afterwards)."""
    ensure_variants(st)
    build = st.section("build")
    key = build.get("active")
    variants = build.get("variants") or {}
    if not key or key not in variants:
        raise RuntimeError(
            "no configured build context - run `configure` first "
            "(available variants: %s)" % (", ".join(variants) or "none"))
    return variants[key]


def set_active_variant(st: ForgeState, qt_version: str, render: str,
                       build_type: str) -> Dict:
    """Switch the active variant slot (must already be configured)."""
    ensure_variants(st)
    build = st.section("build")
    key = variant_key(qt_version, render, build_type)
    variants = build.get("variants") or {}
    if key not in variants:
        raise RuntimeError(
            "variant %r not configured (available: %s) - run `configure "
            "--qt %s --render %s --build-type %s` first"
            % (key, ", ".join(variants) or "none",
               qt_version, render, build_type))
    build["active"] = key
    st.save()
    return variants[key]


def variant_paths(st: ForgeState, qt_version: str, render: str,
                  build_type: str) -> Dict[str, Path]:
    cfg = st.env()
    build_root = Path(cfg.get("build_root") or
                      (st.home / "build")).resolve()
    sdk_root = Path(cfg.get("sdk_root") or
                    (st.home / "sdk")).resolve()
    name = sdk_dir_name(qt_version, render, build_type)
    return {"build_dir": build_root / ("build-" + name),
            "sdk_dir": sdk_root / name}


# ---------------------------------------------------------------- env

def _ensure_python_shim(st: ForgeState) -> Optional[Path]:
    """qtdeclarative's qmake scripts invoke `python` (not `python3`), but
    most Linux distros ship only python3 - the build dies at QtQml with
    `sh: 1: python: not found` (QOH038). Provide a forge-local shim dir
    with a `python` symlink instead of touching the host system."""
    if os.name == "nt":
        return None
    shim = st.state_dir / "pyshim"
    shim.mkdir(parents=True, exist_ok=True)
    link = shim / "python"
    target = Path(sys.executable or "/usr/bin/python3")
    if not link.exists():
        try:
            link.symlink_to(target)
        except OSError:
            return None
    return shim


def build_env(st: ForgeState) -> Dict[str, str]:
    """Cross-compile environment for configure/make (envcheck resolution)."""
    cfg = st.env()
    values = envcheck.default_paths()
    native = cfg.get("ohos_sdk_native") or values["ohos_sdk_native"]
    if not native:
        raise RuntimeError("ohos_sdk_native not configured "
                           "(`config set ohos_sdk_native <path>`)")
    env = dict(os.environ)
    env["NATIVE_OHOS_SDK"] = str(native)
    env["OHOS_SDK_SYSROOT"] = str(Path(native) / "sysroot")
    env["LLVM_INSTALL_DIR"] = str(Path(native) / "llvm")
    # put MinGW / Perl first on PATH (Windows)
    for key in ("mingw_root", "perl_root"):
        base = cfg.get(key) or values.get(key)
        if base:
            bin_dir = Path(base)
            bin_dir = bin_dir / "bin" if (bin_dir / "bin").is_dir() else bin_dir
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    # forge-local `python` -> python3 shim (QOH038, POSIX only)
    shim = _ensure_python_shim(st)
    if shim:
        env["PATH"] = str(shim) + os.pathsep + env.get("PATH", "")
    return env


def _sdk_version(native: Path) -> str:
    """Version string from the SDK's oh-uni-package.json ("" if unknown)."""
    try:
        text = (native / "oh-uni-package.json").read_text(
            encoding="utf-8", errors="replace")
        m = re.search(r'"version"\s*:\s*"([^"]+)"', text)
        return m.group(1) if m else ""
    except OSError:
        return ""


def _opengl_desktop_check(render: str, env: Dict[str, str]) -> Optional[str]:
    """Desktop GL needs the patched libGLv4.so in the sysroot (build.md).
    Returns a warning string when missing, None when ok/irrelevant."""
    if render != "gl":
        return None
    lib = (Path(env["OHOS_SDK_SYSROOT"]) / "usr" / "lib"
           / "aarch64-linux-ohos" / "libGLv4.so")
    if lib.exists():
        return None
    return ("desktop GL build: patched libGLv4.so missing in sysroot "
            "(expected %s) - get it from gitee.com/inkuu/opengl "
            "(mesa_headers_all) and place it in "
            "<sysroot>/usr/lib/aarch64-linux-ohos/ - see "
            "semantic/qt-harmonyos-build.md OpenGL section" % lib)


def _config_fingerprint(args: List[str], env: Dict[str, str]) -> str:
    """Fingerprint of everything that shapes the build dir: configure args
    plus the OHOS SDK identity (path + package version). Swapping the SDK
    behind the CLI's back (e.g. API 15 -> API 23) with a reused build dir
    leaves stale generated files behind (QOH040: qt_lib_dbus.pri kept ibus
    alive after -no-dbus)."""
    native = env.get("NATIVE_OHOS_SDK", "")
    seed = " ".join(args) + "|sdk=%s@%s" % (
        native, _sdk_version(Path(native)) if native else "?")
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _make_program() -> List[str]:
    """Make invocation; on Windows mingw32-make must get SHELL=cmd.exe
    (bash shells eat backslash paths - build.md common pitfalls)."""
    if os.name == "nt":
        return ["mingw32-make.exe", "SHELL=cmd.exe"]
    return ["make"]


def _default_jobs() -> int:
    return max(2, (os.cpu_count() or 4))


# ---------------------------------------------------------------- steps

def configure(st: ForgeState, qt_version: str, render: str = "gl",
              build_type: str = "release",
              timeout: Optional[float] = None,
              skip_extra: Optional[List[str]] = None,
              with_modules: Optional[List[str]] = None) -> Dict:
    """Full (re)configure of a shadow build dir for the given variant."""
    cfg = st.env()
    src = cfg.get("qt_src") or envcheck.default_paths()["qt_src"]
    if not src or not (Path(src) / "qtbase").is_dir():
        return {"ok": False, "error": "qt_src not configured or invalid"}
    src = Path(src)

    paths = variant_paths(st, qt_version, render, build_type)
    build_dir, sdk_dir = paths["build_dir"], paths["sdk_dir"]
    build_dir.mkdir(parents=True, exist_ok=True)
    sdk_dir.parent.mkdir(parents=True, exist_ok=True)

    env = build_env(st)
    args: List[str] = [
        "-xplatform", "ohos-clang",
        "-prefix", str(sdk_dir),
        "-opensource", "-confirm-license",
        "-debug" if build_type == "debug" else "-release",
    ]
    if render == "gl":
        args += ["-opengl", "desktop"]
    elif render == "gles":
        args += ["-opengl", "es2"]
    else:  # gles3: ES 2 + explicit -opengles3 (needs qtbase c5de1b3d+)
        args += ["-opengl", "es2", "-opengles3"]
    gl_warn = _opengl_desktop_check(render, env)
    if gl_warn:
        print("[qt-sdk-run] WARN: %s" % gl_warn)
    args += ["-no-use-gold-linker", "-no-gcc-sysroot", "-no-dbus",
             "-ohos-arch", "arm64-v8a",
             "-c++std", "c++14",
             "-nomake", "examples", "-nomake", "tests"]
    if os.name == "nt":
        args += ["-device-option",
                 "CROSS_COMPILE=%s" % (Path(env["LLVM_INSTALL_DIR"]) / "bin")]
    skip_list, ignored_with = resolve_skip_list(qt_version, skip_extra,
                                                with_modules)
    if skip_extra or with_modules:
        enabled = [m for m in (with_modules or [])
                   if m not in ignored_with]
        print("[qt-sdk-run] module set: skip=%d (default %d), enabled=%s, "
              "ignored --with=%s"
              % (len(skip_list), len(QT_VERSIONS[qt_version][1]),
                 ",".join(enabled) or "-",
                 ",".join(ignored_with) or "-"))
    for mod in skip_list:
        args += ["-skip", mod]

    if os.name == "nt":
        cmd = ["cmd.exe", "/c", str(src / "configure.bat")] + args
    else:
        cmd = ["sh", str(src / "configure")] + args

    # ---- stale-build-state guard (QOH040) --------------------------------
    # Reusing a build dir that was configured with different args or a
    # different OHOS SDK leaves stale generated files behind (classic:
    # qt_lib_dbus.pri survives a -no-dbus reconfigure, so qtHaveModule(dbus)
    # stays true and the ibus plugin still builds). Wipe and reconfigure.
    key = variant_key(qt_version, render, build_type)
    fp = _config_fingerprint(args, env)
    ensure_variants(st)
    prev = st.section("build")["variants"].get(key) or {}
    if build_dir.exists() and any(build_dir.iterdir()):
        prev_fp = prev.get("fingerprint")
        if prev_fp != fp:
            reason = ("configure fingerprint changed (args or OHOS SDK %s)"
                      % (_sdk_version(Path(env["NATIVE_OHOS_SDK"])) or "?")) \
                if prev_fp else \
                ("build dir has no recorded configure (previous run crashed?)")
            shutil.rmtree(build_dir)
            build_dir.mkdir(parents=True, exist_ok=True)
            print("[qt-sdk-run] wiped stale build dir (%s) - clean "
                  "reconfigure, see QOH040" % reason)

    st.begin_stage("configure")
    res = st.run_cmd(cmd, "configure-%s" % qt_version,
                     timeout=timeout or DEFAULT_TIMEOUTS["configure"],
                     cwd=build_dir, extra_env=env)
    # snapshot config.summary as build evidence
    summary = build_dir / "config.summary"
    if summary.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = st.state_dir / "builds" / ("%s-config.summary"
                                          % stamp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary, dest)

    if res.status == "PASS":
        ensure_variants(st)
        st.section("build")["variants"][key] = {
            "qt_version": qt_version, "render": render,
            "build_type": build_type, "sdk_dir": str(sdk_dir),
            "build_dir": str(build_dir), "configured": _now(),
            "fingerprint": fp}
        st.section("build")["active"] = key
        st.complete_stage("configure", next_action="build")
    else:
        st.fail_stage("configure",
                      "%s (see %s)" % (res.status, res.evidence),
                      next_action="configure")
    return {"ok": res.status == "PASS", "result": res,
            "build_dir": str(build_dir), "sdk_dir": str(sdk_dir),
            "variant": key}


def _fail_detail(out: Dict) -> str:
    """Human-readable failure detail from a _make() result."""
    res = out.get("result")
    if res:
        return "%s (see %s)" % (res.status, res.evidence)
    return str(out.get("error", "unknown error"))


def _make(st: ForgeState, targets: List[str], label: str,
          timeout: float) -> Dict:
    ctx = build_ctx(st)
    build_dir = Path(ctx["build_dir"])
    if not build_dir.is_dir():
        return {"ok": False, "error": "build dir missing: %s" % build_dir}
    env = build_env(st)
    jobs = st.env().get("jobs") or _default_jobs()
    cmd = _make_program() + ["-j%s" % int(jobs)] + targets
    res = st.run_cmd(cmd, label, timeout=timeout, cwd=build_dir,
                     extra_env=env)
    return {"ok": res.status == "PASS", "result": res,
            "build_dir": str(build_dir)}


def build(st: ForgeState, timeout: Optional[float] = None) -> Dict:
    """Incremental compile (no install target - see pitfall #1: `install`
    must follow or the SDK keeps the old libs)."""
    st.begin_stage("build")
    out = _make(st, [], "build", timeout or DEFAULT_TIMEOUTS["build"])
    if out["ok"]:
        st.complete_stage("build", next_action="install")
    else:
        st.fail_stage("build", _fail_detail(out), next_action="build")
    out["hint"] = ("compile only - run `install` to propagate libs into the "
                   "SDK (pitfall: make without install changes nothing)")
    return out


def install(st: ForgeState, timeout: Optional[float] = None) -> Dict:
    """make install: propagate built libs (incl. libqohos.so) into the SDK."""
    st.begin_stage("install")
    started = time.time()
    out = _make(st, ["install"], "install",
                timeout or DEFAULT_TIMEOUTS["install"])
    try:
        ctx = build_ctx(st)
    except RuntimeError:
        ctx = {}
    if out["ok"] and ctx:
        ctx["install_started"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(started))
        ctx["install_finished"] = _now()
        st.save()
        st.complete_stage("install", next_action="verify")
    else:
        st.fail_stage("install", _fail_detail(out), next_action="install")
    out["hint"] = ("demo apps must be rebuilt (hvigorw assembleHap) to link "
                   "the updated libqohos.so (pitfall #3)")
    return out


# ---------------------------------------------------------------- checks

def sdk_key_libs(sdk_dir: Path) -> List[Path]:
    """Libs whose freshness proves install propagation (SV4)."""
    candidates = [
        sdk_dir / "lib" / "libQt5Core.so",
        sdk_dir / "lib" / "libQt5Core.so.5",
    ]
    # QPA plugin (libqohos) location varies: plugins/platforms/
    plat = sdk_dir / "plugins" / "platforms"
    if plat.is_dir():
        candidates += [p for p in plat.glob("libqohos*.so")]
    return [c for c in candidates if c.exists()]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
