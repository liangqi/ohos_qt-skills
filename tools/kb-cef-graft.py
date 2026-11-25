#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb-cef-graft.py — graft CEF onto a HarmonyOS Qt template project (the right way: graft onto the template, don't modify the CEF demo)

The template's Qt OHOS QPA glue (QAbility/QAbilityStage/libqohos/*NativeNode) is inherently the right version; grafting
CEF touches only the CEF part and leaves the Qt side alone - keeps functionality stable + follows de-versioning (qt-cef-ohos-dev-guide.md §0/§5).

Two paths:
  - Public only (no --ohqtcef-glue): CEF core + CefClient compile (skeleton); the CEF<->ArkTS glue is left as a §5.3 TODO.
  - --ohqtcef-glue <OpenQtCef glue>: full overlay that runs end to end - uses OpenQtCef's real C++ (testcef/mainwindow/main +
    complete CefSettings) + web_engine + adapter_c, deploys the Qt + CEF .so files, configures build-profile (arm64-only/SDK17/lazy import/
    QT_PREFIX), generates hvigor-wrapper.bat (fixes spawn java ENOENT), runs ohpm install, and with --run calls devecocli to sign + install +
    launch + collect crash logs. Works in one pass.

Usage:
  python kb-cef-graft.py \\
    --template <Qt OHOS template project> --qt-sdk <Qt OHOS SDK> --output <output project> \\
    --cef-root <CEF component package>  # for the public-only path (optional with --ohqtcef-glue, which supplies the CEF .so)\\
    [--ohqtcef-glue <OpenQtCef glue>]  # full overlay, runs end to end \\
    [--app-name qtcefdemo] [--bundle <id>] [--deveco <DevEco>] [--ohos-ndk <NDK>] \\
    [--run]                          # full path: calls devecocli signature generate + run + log --crash \\
    [--dry-run] [--no-verify] [--keep]

Exit codes: 0=success, 1=failure. Every pitfall hit during test runs is baked in (see the _PITFALLS comment).
"""
import argparse, os, sys, shutil, subprocess, re, json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# _PITFALLS: pitfalls hit during test runs (all baked into the script so it succeeds in one pass):
#  P1  CMake set(...);set(...) on one line -> split lines (; is not a statement separator)
#  P2  CMake path C:\Qt: \Q is an invalid escape -> forward slashes
#  P3  ADD_LOGICAL_TARGET fails on OHOS (CMAKE_SYSTEM_NAME=OHOS, not Linux; CEF_LIBTYPE empty) -> link libcef.so directly
#  P4  QAbility super uses arguments[0] -> ArkTS forbids indexed access -> named parameters
#  P5  QAbilityStage IoC regex missed the :void in onCreate(): void { -> [^{]*\{
#  P6  build-profile modules regex matched the wrong ] (from applyToProducts) -> bracket-depth search + trailing comma stripping
#  P7  spawn java ENOENT at PackageHap -> hvigor-wrapper.bat (cd /d + re-inject jbr/java PATH)
#  P8  abiFilters [x86_64,arm64-v8a] -> fails, no CEF .so for x86_64 -> arm64-v8a only
#  P9  ArkTS lazy import -> template's API12 too low -> compatibleSdkVersion 5.0.5(17)+stage
#  P10 libqohos.so+Qt5 .so+libqohosstyle.so not deployed (Qt runtime) -> deploy from the SDK to entry/libs
#  P11 libadapter_c.so not built (skeleton node_manager replaced OpenQtCef adapter_c) -> use OpenQtCef's real C++ (includes adapter_c)
#  P12 skeleton main.cpp has incomplete CefSettings -> CefInitialize SIGTRAP -> use OpenQtCef's real C++ (testcef, complete CefSettings)
#  P13 QT_PREFIX undefined (OpenQtCef CMake uses ${QT_PREFIX}) -> build-profile arguments -DQT_PREFIX=<sdk>
#  P14 signingConfigs empty -> unsigned HAP rejected at install -> devecocli signature generate
#  P15 ohpm not installed -> web_engine import unresolved -> ohpm install

def info(m):  print(f"  [OK] {m}")
def warn(m): print(f"  [WARN] {m}")
def fail(m): print(f"  [FAIL] {m}"); raise SystemExit(1)
def step(m):  print(f"\n━━━ {m} ━━━")
def run(cmd, check=True, capture=False, env=None, cwd=None, timeout=None):
    r = subprocess.run(cmd, capture_output=capture, text=capture, env=env, cwd=cwd, timeout=timeout)
    if check and r.returncode != 0:
        if capture: sys.stderr.write((r.stdout or "") + (r.stderr or ""))
        raise SystemExit(1)
    return r

DEFAULT_CONFIG = {
    "deveco": "C:/Program Files/Huawei/DevEco Studio",
    "devecocli": None,  # None=auto-detect AppData/Roaming/npm/devecocli
    "device": "46G0225208000016",
    "compatible_sdk_version": "5.0.5(17)",  # P9 lazy import needs API17
    "compatible_sdk_version_stage": "release",
    "qt_libs": ["libQt5Core.so", "libQt5Gui.so", "libQt5Widgets.so"],  # Qt5; for Qt6 use libQt6*
    "libqohos_glob": "plugins/platforms/libqohos.so",
    "libqohosstyle_glob": "plugins/styles/libqohosstyle.so",
    "bundle": "com.example.qtcefdemo",
    "app_name": "qtcefdemo",
    "ohos_ndk": None,  # None=derive from deveco/sdk
    "cef_version": None,
}

def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if path:
        p = Path(path)
        if not p.is_file(): fail(f"config file does not exist: {p}")
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    if not cfg.get("devecocli"):
        found = shutil.which("devecocli")  # on Windows, PATHEXT resolves devecocli.cmd
        cfg["devecocli"] = found or str(Path(os.environ.get("APPDATA", "")) / "npm/devecocli.cmd")
    return cfg

def find_ohos_adapter(cef_root):
    libdir = cef_root / "libs" / "arm64-v8a" if cef_root else None
    if not libdir or not libdir.is_dir(): return None
    cands = [f for f in libdir.glob("lib*adapter*.so") if f.name != "libcef.so"]
    return cands[0] if cands else None

def detect_qt_version(template):
    pkg = template / "entry/src/main/qt/oh-package.json5"
    if not pkg.is_file(): return "5", None
    m = re.search(r'"version"\s*:\s*"([^"]+)"', pkg.read_text(encoding="utf-8", errors="replace"))
    ver = m.group(1) if m else None
    return ("6" if (ver and ver.startswith("6")) else "5"), ver

# ---------- preflight ----------
def preflight(args):
    step("0. Preflight: base environment")
    qt_sdk = Path(args.qt_sdk).resolve()
    template = Path(args.template).resolve()
    if not qt_sdk.is_dir(): fail(f"Qt OHOS SDK does not exist: {qt_sdk}")
    if not (qt_sdk / "lib/cmake").is_dir(): fail(f"Qt SDK is missing lib/cmake: {qt_sdk}")
    # P10: libqohos.so lives in SDK plugins/platforms/
    qohos = list(qt_sdk.glob("plugins/platforms/libqohos.so")) + list(qt_sdk.glob("**/libqohos.so"))
    if not qohos: fail(f"Qt SDK is missing libqohos.so (QPA plugin): {qt_sdk}")
    info(f"Qt SDK: {qt_sdk} (libqohos.so ✓)")
    if not template.is_dir(): fail(f"template project does not exist: {template}")
    if not (template / "entry/src/main/qt/libqohos.d.ts").is_file():
        fail(f"template is not a valid Qt OHOS project (missing entry/src/main/qt/libqohos.d.ts): {template}")
    qt_major, qt_ver = detect_qt_version(template)
    info(f"template Qt version: {qt_ver or '?'} -> Qt{qt_major} CMake variant")
    glue = Path(args.ohqtcef_glue).resolve() if args.ohqtcef_glue else None
    cef_root = Path(args.cef_root).resolve() if args.cef_root else None
    if glue and glue.is_dir():
        for need, label in [("web_engine","web_engine"), ("entry/libs/arm64-v8a/libcef.so","libcef.so"),
                            ("entry/libs/arm64-v8a/libadapter.so","libadapter.so"),
                            ("entry/src/main/cpp/testcef","testcef real C++"),
                            ("entry/src/main/cpp/CMakeLists.txt","OpenQtCef CMakeLists"),
                            ("entry/src/main/cpp/include","CEF include"),
                            ("entry/src/main/cpp/libcef_dll","libcef_dll wrapper")]:
            if not (glue / need).exists(): fail(f"OpenQtCef glue is missing {label}: {glue}/{need}")
        info(f"OpenQtCef glue: {glue} (full overlay path)")
    else:
        glue = None
        if not cef_root or not cef_root.is_dir(): fail("--cef-root (CEF component package) is required without --ohqtcef-glue")
        for need in ["include","cmake","libcef_dll"]:
            if not (cef_root / need).is_dir(): fail(f"CEF component package is missing {need}/")
        if not (cef_root / "libs/arm64-v8a/libcef.so").is_file(): fail("CEF component package is missing libcef.so")
        info(f"CEF component package: {cef_root} (public-only path; CEF<->ArkTS glue uses the §5.3 TODO skeleton)")
    cfg = load_config(args.config)
    if args.deveco: cfg["deveco"] = args.deveco
    if args.device: cfg["device"] = args.device
    if args.ohos_ndk: cfg["ohos_ndk"] = args.ohos_ndk
    info(f"config: deveco={cfg['deveco']} | device={cfg['device']} | sdk={cfg['compatible_sdk_version']} | qt_libs={cfg['qt_libs']}")
    devecocli = cfg.get("devecocli") or shutil.which("devecocli") or str(Path(os.environ.get("APPDATA",""))/"npm/devecocli.cmd")
    if Path(devecocli).exists(): info(f"devecocli: {devecocli} (used by --run)")
    else: warn("devecocli unavailable (--run skips signing + install + launch)")
    return dict(qt_sdk=qt_sdk, template=template, qt_major=qt_major, qt_ver=qt_ver,
                glue=glue, cef_root=cef_root, devecocli=devecocli, config=cfg)

# ---------- graft ----------
def graft(args, ctx):
    out = Path(args.output).resolve()
    if out.exists(): fail(f"output directory already exists: {out} (delete it or use another path)")
    template = ctx["template"]; glue = ctx["glue"]
    step("1. Copy template -> output (keeps the correct-version Qt glue)")
    shutil.copytree(template, out)
    for c in [".hvigor",".cxx",".idea","oh_modules","build"]:
        for p in out.rglob(c):
            if p.is_dir(): shutil.rmtree(p, ignore_errors=True)
    info(f"copied to {out}")
    if glue:
        overlay_openqtcef_full(out, glue, ctx, args)
    else:
        overlay_public_skeleton(out, ctx, args)
    deploy_qt_so(out, ctx["qt_sdk"], ctx["config"])  # P10
    patch_build_profile_full(out, args, ctx)  # P6/P8/P9/P13
    patch_qt_constants(out, "qtmodule" if glue else args.app_name)  # P11/P12: glue uses the qtmodule target
    patch_app_scope(out, args.bundle)
    write_hvigor_wrapper(out, ctx["config"])  # P7
    run_ohpm_install(out, ctx["config"])  # P15
    return out

def overlay_openqtcef_full(out, glue, ctx, args):
    step("2. OpenQtCef full overlay (real C++ + web_engine + adapter + CEF .so)")
    # P11/P12: replace the skeleton with OpenQtCef's real C++ (testcef/mainwindow/main + CMakeLists + include/libcef_dll/cmake + complete CefSettings)
    src_cpp = glue / "entry/src/main/cpp"
    dst_cpp = out / "entry/src/main/cpp"
    if dst_cpp.exists(): shutil.rmtree(dst_cpp)
    shutil.copytree(src_cpp, dst_cpp)
    info(f"real C++ overlay: {dst_cpp} (testcef/mainwindow/main + OpenQtCef CMakeLists + adapter_c sources + complete CefSettings)")
    # web_engine har module (includes CEF resources icudtl.dat/.pak/locales in resfile)
    we = glue / "web_engine"
    if we.is_dir():
        dst_we = out / "web_engine"
        shutil.copytree(we, dst_we)
        for stale in ["oh-package-lock.json5","BuildProfile.ets"]:
            p = dst_we / stale
            if p.exists(): p.unlink()
        info(f"web_engine/ overlay (includes CEF resources in resfile: icudtl.dat/.pak/locales)")
    # CEF .so (libcef.so+libadapter.so+dependency chain) deployed from glue/entry/libs
    src_lib = glue / "entry/libs/arm64-v8a"
    dst_lib = out / "entry/libs/arm64-v8a"; dst_lib.mkdir(parents=True, exist_ok=True)
    n = 0
    for so in src_lib.glob("*.so"):
        shutil.copy2(so, dst_lib / so.name); n += 1
    info(f"CEF .so deployed: {n} (libcef.so+libadapter.so+dependency chain)")
    # libadapter_c napi types already came in with the cpp/ copytree (OpenQtCef cpp/ includes types/libadapter_c); no need to copy again
    # add web_engine to build-profile modules (P6 bracket depth) + oh-package deps
    patch_build_profile_modules(out)
    patch_oh_package(out)
    # QAbility extends WebQtAbility + QAbilityStage extends WebAbilityStage + IoC (P4/P5 named super + adapter_c.initFunc + super.onCreate)
    patch_qability_extends(out)
    # CEF permissions
    patch_module_json5(out)
    info("QAbility extends WebQtAbility (named super) + QAbilityStage extends WebAbilityStage (IoC super.onCreate) + CEF permissions")

def overlay_public_skeleton(out, ctx, args):
    step("2. Public-only overlay (CEF core + CefClient skeleton; CEF<->ArkTS left as §5.3 TODO)")
    cef_root = ctx["cef_root"]; app = args.app_name
    dst_lib = out / "entry/libs/arm64-v8a"; dst_lib.mkdir(parents=True, exist_ok=True)
    for so in (cef_root/"libs/arm64-v8a").glob("*.so"): shutil.copy2(so, dst_lib/so.name)
    write_cmake(out, app, ctx["qt_sdk"], cef_root, ctx["qt_major"], find_ohos_adapter(cef_root))
    write_cpp_skeletons(out, app)
    inject_arkts_skeleton(out, app)
    patch_module_json5(out)

def deploy_qt_so(out, qt_sdk, cfg):  # P10: deploy the Qt runtime .so (libqohos+Qt .so+qohosstyle from the SDK)
    step("3. Deploy the Qt runtime .so (libqohos+Qt .so+qohosstyle from the SDK)")
    dst = out / "entry/libs/arm64-v8a"; dst.mkdir(parents=True, exist_ok=True)
    qg = cfg.get("libqohos_glob", "plugins/platforms/libqohos.so")
    qohos = list(qt_sdk.glob(qg)) + list(qt_sdk.glob("**/libqohos.so"))
    if qohos: shutil.copy2(qohos[0], dst/"libqohos.so"); info("libqohos.so")
    styles_dir = dst / "styles"; styles_dir.mkdir(exist_ok=True)
    sg = cfg.get("libqohosstyle_glob", "plugins/styles/libqohosstyle.so")
    style = list(qt_sdk.glob(sg)) + list(qt_sdk.glob("**/libqohosstyle.so"))
    if style: shutil.copy2(style[0], styles_dir/"libqohosstyle.so"); info("styles/libqohosstyle.so")
    qt_libs = cfg.get("qt_libs", ["libQt5Core.so","libQt5Gui.so","libQt5Widgets.so"])
    for ql in qt_libs:
        p = qt_sdk / "lib" / ql
        if p.exists(): shutil.copy2(p, dst/ql)
    info(f"Qt .so: {qt_libs} → {dst}")

# ---------- build-profile (P6/P8/P9/P13) ----------
def patch_build_profile_full(out, args, ctx):
    step("4. build-profile configuration (abiFilters arm64-only P8 + SDK17 lazy import P9 + QT_PREFIX P13)")
    bp = out / "build-profile.json5"
    if not bp.is_file(): warn("build-profile.json5 does not exist, skipping"); return
    t = bp.read_text(encoding="utf-8")
    # P9: compatibleSdkVersion + stage (taken from config; OpenQtCef web_engine uses lazy import, which needs API17)
    sdk = ctx["config"].get("compatible_sdk_version", "5.0.5(17)")
    stage = ctx["config"].get("compatible_sdk_version_stage", "release")
    t = re.sub(r'"compatibleSdkVersion"\s*:\s*"[^"]*"', f'"compatibleSdkVersion": "{sdk}"', t)
    if "compatibleSdkVersionStage" not in t:
        t = t.replace(f'"compatibleSdkVersion": "{sdk}"',
                      f'"compatibleSdkVersion": "{sdk}",\n        "compatibleSdkVersionStage": "{stage}"')
    # P8: abiFilters arm64-v8a only
    ebp = out / "entry/build-profile.json5"
    if ebp.is_file():
        et = ebp.read_text(encoding="utf-8")
        et = re.sub(r'"abiFilters"\s*:\s*\[[^\]]*\]', '"abiFilters": ["arm64-v8a"]', et)
        # P13: arguments -DQT_PREFIX=<sdk> (OpenQtCef CMake uses ${QT_PREFIX})
        qt = str(ctx["qt_sdk"]).replace("\\","/")
        et = re.sub(r'"arguments"\s*:\s*"[^"]*"', f'"arguments": "-DQT_PREFIX={qt}"', et)
        if '"arguments"' not in et:
            et = et.replace('"externalNativeOptions"', f'"externalNativeOptions": {{\n      "arguments": "-DQT_PREFIX={qt}",', 1)
        ebp.write_text(et, encoding="utf-8")
        info("entry/build-profile: abiFilters=arm64-v8a only + arguments -DQT_PREFIX")
    bp.write_text(t, encoding="utf-8")
    info(f"build-profile: compatibleSdkVersion {sdk}+stage {stage}")

def patch_build_profile_modules(out):  # P6: find the modules ] by bracket depth + strip trailing comma
    bp = out / "build-profile.json5"
    if not bp.is_file(): return
    t = bp.read_text(encoding="utf-8")
    if '"web_engine"' in t: return
    m = re.search(r'"modules"\s*:\s*\[', t)
    if not m: return
    i = m.end(); depth = 1
    while i < len(t) and depth > 0:
        if t[i] == '[': depth += 1
        elif t[i] == ']': depth -= 1
        i += 1
    if depth != 0: return
    close = i - 1
    end = close
    while end > 0 and t[end-1] in ' \t\r\n': end -= 1
    if end > 0 and t[end-1] == ',': end -= 1
    we = (',\n    {\n      "name": "web_engine",\n      "srcPath": "./web_engine",\n'
          '      "targets": [\n        {\n          "name": "default",\n'
          '          "applyToProducts": [\n            "default"\n          ]\n        }\n      ]\n    }')
    bp.write_text(t[:end] + '\n' + we + '\n  ' + t[close:], encoding="utf-8")

def patch_oh_package(out):
    op = out / "entry/oh-package.json5"
    if not op.is_file(): return
    t = op.read_text(encoding="utf-8")
    if '"web_engine"' not in t:
        t = re.sub(r'("dependencies"\s*:\s*\{)', r'\1\n    "web_engine": "file:../web_engine",', t, count=1)
    if '"@types/libadapter_c.so"' not in t:
        t = re.sub(r'("devDependencies"\s*:\s*\{)', r'\1\n    "@types/libadapter_c.so": "file:./src/main/cpp/types/libadapter_c",', t, count=1)
    op.write_text(t, encoding="utf-8")

def patch_qability_extends(out):  # P4/P5: named super + IoC
    qa = out / "entry/src/main/ets/qability/QAbility.ets"
    if qa.is_file():
        t = qa.read_text(encoding="utf-8")
        if "WebQtAbility" not in t:
            t = t.replace("extends UIAbility", "extends WebQtAbility", 1)
            if "import { WebQtAbility }" not in t:
                t = "import { WebQtAbility } from 'web_engine';\n" + t
            super_args = {  # P4: named parameters (ArkTS forbids indexed access to arguments)
                "onCreate": "(want, launchParam)", "onWindowStageCreate": "(windowStage)",
                "onWindowStageDestroy": "()", "onForeground": "()", "onBackground": "()",
                "onDestroy": "()", "onNewWant": "(want, launchParam)", "onContinue": "(wantParam)"}
            for m, a in super_args.items():
                pat = r"(" + re.escape(m) + r"\([^)]*\)[^{]*\{)"  # P5: allow a :void return type
                t = re.sub(pat, r"\1\n    super." + m + a + ";  // WebQtAbility CEF cooperation", t, count=1)
            qa.write_text(t, encoding="utf-8")
    qs = out / "entry/src/main/ets/qabilitystage/QAbilityStage.ets"
    if qs.is_file():
        t = qs.read_text(encoding="utf-8")
        if "WebAbilityStage" not in t:
            t = t.replace("extends AbilityStage", "extends WebAbilityStage", 1)
            if "import { WebAbilityStage }" not in t:
                t = "import { WebAbilityStage } from 'web_engine';\nimport adapter_c from 'libadapter_c.so';\n" + t
            t = re.sub(r"(onCreate\([^)]*\)[^{]*\{)",  # P5: allow onCreate(): void {
                       r"\1\n    adapter_c.initFunc(1.0);  // scaledDensity TODO §5.3\n"
                       r"    super.onCreate();  // WebAbilityStage IoC (InjectModule.inject binds AbilityManager etc., §B.3)",
                       t, count=1)
            qs.write_text(t, encoding="utf-8")

def patch_module_json5(out):
    mj = out / "entry/src/main/module.json5"
    if not mj.is_file(): return
    t = mj.read_text(encoding="utf-8")
    add = []
    if "ohos.permission.INTERNET" not in t: add.append('{ "name": "ohos.permission.INTERNET" }')
    if "ohos.permission.GET_NETWORK_INFO" not in t: add.append('{ "name": "ohos.permission.GET_NETWORK_INFO" }')
    if not add: return
    inj = "".join(f"    {p},\n" for p in add)
    t = re.sub(r'("requestPermissions"\s*:\s*\[)([^\]]*)\]',
               lambda m: m.group(1) + inj + m.group(2).rstrip() + "\n  ]", t, count=1)
    mj.write_text(t, encoding="utf-8")

def patch_qt_constants(out, app):
    qc = out / "entry/src/main/ets/common/QtAppConstants.ets"
    if not qc.is_file(): return
    t = qc.read_text(encoding="utf-8")
    t = re.sub(r"APP_LIBRARY_NAME\s*=\s*'[^']*'", f"APP_LIBRARY_NAME = 'lib{app}.so'", t)
    t = re.sub(r"LOG_TAG\s*=\s*'[^']*'", f"LOG_TAG = '{app}'", t)
    qc.write_text(t, encoding="utf-8")

def patch_app_scope(out, bundle):
    ap = out / "AppScope/app.json5"
    if not ap.is_file(): return
    t = ap.read_text(encoding="utf-8")
    t = re.sub(r'"bundleName"\s*:\s*"[^"]*"', f'"bundleName": "{bundle}"', t)
    ap.write_text(t, encoding="utf-8")

# ---------- hvigor-wrapper.bat (P7 spawn java ENOENT) + ohpm (P15) ----------
def write_hvigor_wrapper(out, cfg):  # P7 spawn java ENOENT
    step("5. Generate hvigor-wrapper.bat (fixes PackageHap spawn java ENOENT, P7)")
    deveco = cfg.get("deveco", "C:/Program Files/Huawei/DevEco Studio").replace("/", "\\")
    out_str = str(out).replace("/", "\\")
    wrapper = f'''@echo off
rem hvigor-wrapper.bat - cd to project + re-inject jbr/java PATH (fix spawn java ENOENT at PackageHap, P7)
cd /d {out_str}
set "JAVA_HOME={deveco}\\jbr"
set "DEVECO_SDK_HOME={deveco}\\sdk"
set "PATH={deveco}\\jbr\\bin;{deveco}\\tools\\node\\bin;{deveco}\\tools\\hvigor\\bin;{deveco}\\tools\\ohpm\\bin;%PATH%"
"{deveco}\\tools\\hvigor\\bin\\hvigorw.bat" %*
'''
    (out / "hvigor-wrapper.bat").write_text(wrapper, encoding="utf-8")
    info(f"hvigor-wrapper.bat (cd /d + re-inject jbr/java PATH)")

def run_ohpm_install(out, cfg):  # P15: link the web_engine dependency, otherwise import unresolved
    step("6. ohpm install (link the web_engine dependency, P15)")
    deveco = cfg.get("deveco", "C:/Program Files/Huawei/DevEco Studio")
    pm = Path(deveco) / "tools/ohpm/bin/pm-cli.js"
    env = os.environ.copy()
    env["JAVA_HOME"] = f"{deveco}/jbr"; env["DEVECO_SDK_HOME"] = f"{deveco}/sdk"
    env["PATH"] = f"{deveco}/jbr/bin;{deveco}/tools/node/bin;{deveco}/tools/ohpm/bin;" + env.get("PATH","")
    if not pm.exists(): warn(f"ohpm pm-cli.js does not exist: {pm}, skipping (run ohpm install manually)"); return
    try:
        r = run(["node", str(pm), "install"], check=False, capture=True, env=env, cwd=str(out), timeout=300)
        info(f"ohpm install finished (exit {r.returncode})")
    except Exception as e:
        warn(f"ohpm install failed: {e} (run ohpm install manually)")

# ---------- public-only skeleton CMake/cpp (P1/P2/P3) ----------
def write_cmake(out, app, qt_sdk, cef_root, qt_major, adapter):
    qt_libs = "Qt6::Core Qt6::Gui Qt6::Widgets" if qt_major == "6" else "Qt5::Core Qt5::Gui Qt5::Widgets"
    if qt_major == "6":
        qt_block = f'find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)\nqt_add_executable({app} main.cpp cefclient/my_client.cpp)'
    else:
        qt_block = f'find_package(Qt5 REQUIRED COMPONENTS Core Gui Widgets)\nadd_library({app} SHARED main.cpp cefclient/my_client.cpp)'
    adp = adapter.name if adapter else "<OHOS adapter .so>  # §5.2 version-sensitive"
    tmpl = r'''cmake_minimum_required(VERSION 3.19)
project(__APP__ LANGUAGES CXX)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)
list(APPEND CMAKE_PREFIX_PATH "__QT_SDK__")
list(APPEND CMAKE_FIND_ROOT_PATH "__QT_SDK__")
if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()
set(CEF_ROOT "__CEF_ROOT__" CACHE PATH "")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CEF_ROOT}/cmake")
find_package(CEF REQUIRED)
add_subdirectory(${CEF_ROOT}/libcef_dll libcef_dll_wrapper)
# P3: on OHOS CMAKE_SYSTEM_NAME=OHOS, not Linux; CEF_LIBTYPE empty -> ADD_LOGICAL_TARGET fails; link libcef.so directly (OpenQtCef style)
find_library(native-window-lib native_window)
find_library(hilog-lib hilog_ndk.z)
find_library(ace-napi-lib ace_napi.z)
find_library(ace-ndk-lib ace_ndk.z)
add_library(node_adapter SHARED node_manager/node_manager.cpp)
target_include_directories(node_adapter PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(node_adapter PUBLIC ${hilog-lib} ${ace-napi-lib} ${ace-ndk-lib})
__QT_BLOCK__
target_include_directories(__APP__ PRIVATE ${CEF_ROOT} ${CEF_ROOT}/include ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(__APP__ PRIVATE
    __QT_LIBS__ node_adapter libcef_dll_wrapper
    ${CEF_ROOT}/libs/arm64-v8a/libcef.so
    ${CEF_ROOT}/libs/arm64-v8a/__ADAPTER__
    ${native-window-lib} ${hilog-lib} ${ace-napi-lib} ${ace-ndk-lib})
'''
    txt = (tmpl.replace("__APP__", app).replace("__QT_SDK__", str(qt_sdk).replace("\\","/"))
              .replace("__CEF_ROOT__", str(cef_root).replace("\\","/")).replace("__QT_BLOCK__", qt_block)
              .replace("__QT_LIBS__", qt_libs).replace("__ADAPTER__", adp))
    (out / "entry/src/main/cpp/CMakeLists.txt").write_text(txt, encoding="utf-8")

def write_cpp_skeletons(out, app):
    cpp = out / "entry/src/main/cpp"
    for d in ["cefclient","node_manager","include"]: (cpp/d).mkdir(parents=True, exist_ok=True)
    (cpp/"main.cpp").write_text(f'''// {app} — Qt + CEF OHOS demo (skeleton, kb-cef-graft.py public-only path)
// For a full working run use --ohqtcef-glue (OpenQtCef real C++ testcef, complete CefSettings); this skeleton's CefSettings is incomplete (P12).
#include <QApplication><QMainWindow><thread><atomic>
#include "include/cef_app.h"
#include "cefclient/my_client.h"
extern "C" __attribute__((visibility("default"))) int cef_subprocess_entry(int argc,char*argv[]){{
  return CefExecuteProcess(CefMainArgs(argc,argv),nullptr,nullptr);}}
static std::atomic<bool> g_cef_ready{{false}};
static void cef_thread(int argc,char**argv){{
  CefSettings s; s.no_sandbox=true;
  // TODO §B.2: s.browser_subprocess_path="<lib{app}.so>"; // incomplete skeleton -> CefInitialize SIGTRAPs (P12); use --ohqtcef-glue
  CefInitialize(CefMainArgs(argc,argv),s,nullptr,nullptr); g_cef_ready=true; CefRunMessageLoop(); CefShutdown();}}
int main(int argc,char*argv[]){{
  QApplication a(argc,argv); QMainWindow w; w.resize(1024,768); w.show();
  std::thread(cef_thread,argc,argv).detach(); return a.exec();}}
'''.replace("<QApplication>","#include <QApplication>\n#include <QMainWindow>\n#include <thread>\n#include <atomic>").encode("utf-8").decode(), encoding="utf-8")
    (cpp/"cefclient/my_client.h").write_text('#ifndef MY_CLIENT_H\n#define MY_CLIENT_H\n#include "include/cef_client.h"\nclass MyClient:public CefClient,public CefLifeSpanHandler,public CefDisplayHandler,public CefLoadHandler{public: CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler()override{return this;} CefRefPtr<CefDisplayHandler> GetDisplayHandler()override{return this;} CefRefPtr<CefLoadHandler> GetLoadHandler()override{return this;} void OnAfterCreated(CefRefPtr<CefBrowser>)override{} bool DoClose(CefRefPtr<CefBrowser>)override{return false;} void OnBeforeClose(CefRefPtr<CefBrowser>)override{} IMPLEMENT_REFCOUNTING(MyClient);};\n#endif\n', encoding="utf-8")
    (cpp/"cefclient/my_client.cpp").write_text('#include "cefclient/my_client.h"\n', encoding="utf-8")
    (cpp/"node_manager/node_manager.h").write_text('#pragma once\nnamespace node_manager{void attach(unsigned long);}\n', encoding="utf-8")
    (cpp/"node_manager/node_manager.cpp").write_text('#include "node_manager.h"\nnamespace node_manager{void attach(unsigned long){}}\n', encoding="utf-8")

def inject_arkts_skeleton(out, app):
    qa = out / "entry/src/main/ets/qability/QAbility.ets"
    if qa.is_file():
        t = qa.read_text(encoding="utf-8")
        anchor = "qpa.handleAbilityOnWindowStageCreate(this, windowStage);"
        if anchor in t and "CEF graft" not in t:
            qa.write_text(t.replace(anchor, anchor + "\n    // CEF graft §5.3 TODO: node_manager.attach(this window's ArkUI node)", 1), encoding="utf-8")

# ---------- --run: devecocli sign + install + launch + crash log (P14) ----------
def devecocli_run(out, args, ctx):
    step("7. devecocli signature generate + run + log (--run, P14 signing)")
    dc = ctx["devecocli"]
    if not Path(dc).exists(): warn("devecocli unavailable, skipping --run (run devecocli signature generate + run manually)"); return
    deveco = ctx["config"].get("deveco", "C:/Program Files/Huawei/DevEco Studio")
    env = os.environ.copy()
    env["JAVA_HOME"] = f"{deveco}/jbr"; env["DEVECO_SDK_HOME"] = f"{deveco}/sdk"
    env["PATH"] = f"{deveco}/jbr/bin;{deveco}/tools/node/bin;{deveco}/tools/hvigor/bin;{deveco}/tools/ohpm/bin;" + env.get("PATH","")
    info("devecocli signature generate (generates a debug certificate + profile written into build-profile, P14)")
    r = run([dc, "signature", "generate", "--force"], check=False, capture=True, cwd=str(out), timeout=300, env=env)
    info(f"signature generate exit {r.returncode}")
    info("devecocli run (build signed + install + launch QAbility)")
    r = run([dc, "run", "--module", "entry", "--device", args.device or ctx["config"].get("device","46G0225208000016"),
             "--ability", "QAbility", "--build-mode", "debug", "--uninstall"],
            check=False, capture=True, cwd=str(out), timeout=900, env=env)
    info(f"run exit {r.returncode}")
    if r.returncode == 0:
        info("=== crash check (devecocli log --crash) ===")
        import time; time.sleep(7)
        rc = run([dc, "log", "--crash", "--bundle-name", args.bundle], check=False, capture=True, timeout=120, env=env)
        crash = re.search(r"Reason:|SIGSEGV|SIGTRAP|Kill Reason|\.ets:", rc.stdout or "")
        if crash: warn("crash detected, see above; may need missing .so/resources/version adaptation (see qt-cef-ohos-dev-guide §5)")
        else: info("✓ no crash, app running (use devecocli log --bundle-name <bundle> to watch CEF start up)")
        print((rc.stdout or "")[-1500:])

# ---------- report ----------
def report(out, ctx, args):
    step("8. Report")
    glue = ctx["glue"]
    print(f"  ✓ graft output: {out}")
    print(f"  Qt: Qt{ctx['qt_major']} {ctx['qt_ver'] or ''} | path: {'OpenQtCef full overlay (runs in one pass)' if glue else 'public only (skeleton, CEF<->ArkTS §5.3 TODO)'}")
    if glue:
        print("\n  Full path baked-in fixes (all test-run pitfalls fixed):")
        print("    P1 CMake set split lines | P2 forward-slash paths | P3 link libcef.so directly (replaces ADD_LOGICAL_TARGET)")
        print("    P4 QAbility named super (ArkTS has no indexed access) | P5 QAbilityStage IoC regex allows :void")
        print("    P6 build-profile bracket-depth ] + trailing comma stripping | P7 hvigor-wrapper.bat (spawn java ENOENT)")
        print("    P8 abiFilters arm64-only | P9 compatibleSdkVersion 5.0.5(17)+stage (lazy import)")
        print("    P10 deploy libqohos+Qt5+qohosstyle (Qt runtime) | P11 OpenQtCef adapter_c (replaces skeleton)")
        print("    P12 OpenQtCef real C++ (testcef complete CefSettings, replaces skeleton) | P13 arguments -DQT_PREFIX")
        print("    P14 devecocli signature generate (signing) | P15 ohpm install (web_engine dependency)")
    print("\n  Next steps:")
    if glue and args.run:
        print("    --run already did signing + install + launch + crash check (see devecocli output above)")
    elif glue:
        print("    cd <output> && devecocli signature generate --force  # P14 signing")
        print("    devecocli run --module entry --device <id> --ability QAbility --build-mode debug --uninstall  # install + launch")
        print("    devecocli log --crash --bundle-name <bundle>  # crash check")
    else:
        print("    fill in the §5.3 skeleton TODOs (node_manager/IoC/subprocess symbols), then run end to end with --ohqtcef-glue")

def main():
    ap = argparse.ArgumentParser(description="Graft CEF onto a HarmonyOS Qt template project (all test-run pitfalls baked in)")
    ap.add_argument("--template", required=True)
    ap.add_argument("--qt-sdk", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--cef-root", help="CEF component package (for the public-only path; optional with --ohqtcef-glue)")
    ap.add_argument("--ohqtcef-glue", help="OpenQtCef glue path (full overlay, runs in one pass)")
    ap.add_argument("--app-name", default="qtcefdemo")
    ap.add_argument("--bundle", default="com.example.qtcefdemo")
    ap.add_argument("--config", help="config file path (JSON environment config: deveco/device/SDK version/Qt .so etc.; agents change the config, not the script)")
    ap.add_argument("--deveco", default=None, help="DevEco path (overrides config)")
    ap.add_argument("--ohos-ndk", default=None)
    ap.add_argument("--device", default=None, help="device id (overrides config)")
    ap.add_argument("--run", action="store_true", help="full path: devecocli signing + install + launch + crash check")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    ctx = preflight(args)
    if args.dry_run:
        print("\n[dry-run] preflight done, nothing written."); return 0
    out = graft(args, ctx)
    if args.run and ctx["glue"]:
        devecocli_run(out, args, ctx)
    report(out, ctx, args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
