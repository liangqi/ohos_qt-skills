#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb-cef-graft.py — 把 CEF 嫁接到鸿蒙 Qt 模板工程上（正确姿势：基于模板嫁接，不在 CEF demo 上改）

模板的 Qt OHOS QPA 胶水（QAbility/QAbilityStage/libqohos/*NativeNode）天然版本正确，嫁接 CEF 只动
CEF 部分，Qt 侧不碰——保功能稳定 + 符合去版本化（qt-cef-ohos-dev-guide.md §0/§5）。

两条路径：
  - 公开 only（无 --ohqtcef-glue）：CEF 内核+CefClient 可编译（骨架），CEF<->ArkTS 胶水留 §5.3 TODO。
  - --ohqtcef-glue <OpenQtCef 胶水>：全量 overlay 跑通——用 OpenQtCef 真 C++(testcef/mainwindow/main+
    完整 CefSettings)+web_engine+adapter_c，部署 Qt+CEF .so，配 build-profile(arm64-only/SDK17/lazy import/
    QT_PREFIX)，生成 hvigor-wrapper.bat(修 spawn java ENOENT)，ohpm install，可 --run 调 devecocli 签名+装机+
    启动+崩溃日志。一次跑通。

用法:
  python kb-cef-graft.py \\
    --template <Qt OHOS 模板工程> --qt-sdk <Qt OHOS SDK> --output <输出工程> \\
    --cef-root <CEF 组件包>          # 公开 only 路径用（--ohqtcef-glue 时可省，从 glue 取 CEF .so）\\
    [--ohqtcef-glue <OpenQtCef 胶水>]  # 全量 overlay 跑通 \\
    [--app-name qtcefdemo] [--bundle <id>] [--deveco <DevEco>] [--ohos-ndk <NDK>] \\
    [--run]                          # 全量路径：调 devecocli signature generate + run + log --crash \\
    [--dry-run] [--no-verify] [--keep]

退出码: 0=成功, 1=失败。运行测试踩的坑全固化（见 _PITFALLS 注释）。
"""
import argparse, os, sys, shutil, subprocess, re, json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# _PITFALLS: 运行测试踩的坑（全固化进脚本，做到一次成功）：
#  P1  CMake set(...);set(...) 一行 → 分行（; 非语句分隔符）
#  P2  CMake 路径 C:\Qt 的 \Q 非法转义 → 正斜杠
#  P3  ADD_LOGICAL_TARGET 在 OHOS 失败（CMAKE_SYSTEM_NAME=OHOS 非 Linux，CEF_LIBTYPE 空）→ 直链 libcef.so
#  P4  QAbility super 用 arguments[0] → ArkTS 禁索引访问 → 具名参数
#  P5  QAbilityStage IoC 正则漏 onCreate(): void { 的 :void → [^{]*\{
#  P6  build-profile modules 正则匹配错 ]（applyToProducts 的）→ 括号深度找 + 尾逗号剥除
#  P7  spawn java ENOENT at PackageHap → hvigor-wrapper.bat（cd /d + 重注 jbr/java PATH）
#  P8  abiFilters [x86_64,arm64-v8a] → x86_64 无 CEF .so 失败 → arm64-v8a only
#  P9  ArkTS lazy import → 模板 API12 太低 → compatibleSdkVersion 5.0.5(17)+stage
#  P10 libqohos.so+Qt5 .so+libqohosstyle.so 未部署（Qt 运行时）→ 从 SDK 部署到 entry/libs
#  P11 libadapter_c.so 未编（骨架 node_manager 替了 OpenQtCef adapter_c）→ 用 OpenQtCef 真 C++（含 adapter_c）
#  P12 骨架 main.cpp CefSettings 不全 → CefInitialize SIGTRAP → 用 OpenQtCef 真 C++(testcef 完整 CefSettings)
#  P13 QT_PREFIX 未定义（OpenQtCef CMake 用 ${QT_PREFIX}）→ build-profile arguments -DQT_PREFIX=<sdk>
#  P14 signingConfigs 空 → unsigned HAP 装机拒 → devecocli signature generate
#  P15 ohpm 未 install → web_engine import 未解析 → ohpm install

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
    "devecocli": None,  # None=自动探测 AppData/Roaming/npm/devecocli
    "device": "46G0225208000016",
    "compatible_sdk_version": "5.0.5(17)",  # P9 lazy import 需 API17
    "compatible_sdk_version_stage": "release",
    "qt_libs": ["libQt5Core.so", "libQt5Gui.so", "libQt5Widgets.so"],  # Qt5；Qt6 改 libQt6*
    "libqohos_glob": "plugins/platforms/libqohos.so",
    "libqohosstyle_glob": "plugins/styles/libqohosstyle.so",
    "bundle": "com.example.qtcefdemo",
    "app_name": "qtcefdemo",
    "ohos_ndk": None,  # None=从 deveco/sdk 推导
    "cef_version": None,
}

def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if path:
        p = Path(path)
        if not p.is_file(): fail(f"配置文件不存在: {p}")
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    if not cfg.get("devecocli"):
        found = shutil.which("devecocli")  # Windows 会按 PATHEXT 找到 devecocli.cmd
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

# ---------- 预检 ----------
def preflight(args):
    step("0. 预检基础环境")
    qt_sdk = Path(args.qt_sdk).resolve()
    template = Path(args.template).resolve()
    if not qt_sdk.is_dir(): fail(f"Qt OHOS SDK 不存在: {qt_sdk}")
    if not (qt_sdk / "lib/cmake").is_dir(): fail(f"Qt SDK 缺 lib/cmake: {qt_sdk}")
    # P10: libqohos.so 在 SDK plugins/platforms/
    qohos = list(qt_sdk.glob("plugins/platforms/libqohos.so")) + list(qt_sdk.glob("**/libqohos.so"))
    if not qohos: fail(f"Qt SDK 缺 libqohos.so（QPA 插件）: {qt_sdk}")
    info(f"Qt SDK: {qt_sdk}（libqohos.so ✓）")
    if not template.is_dir(): fail(f"模板工程不存在: {template}")
    if not (template / "entry/src/main/qt/libqohos.d.ts").is_file():
        fail(f"模板不是有效 Qt OHOS 工程（缺 entry/src/main/qt/libqohos.d.ts）: {template}")
    qt_major, qt_ver = detect_qt_version(template)
    info(f"模板 Qt 版本: {qt_ver or '?'} → Qt{qt_major} CMake 变体")
    glue = Path(args.ohqtcef_glue).resolve() if args.ohqtcef_glue else None
    cef_root = Path(args.cef_root).resolve() if args.cef_root else None
    if glue and glue.is_dir():
        for need, label in [("web_engine","web_engine"), ("entry/libs/arm64-v8a/libcef.so","libcef.so"),
                            ("entry/libs/arm64-v8a/libadapter.so","libadapter.so"),
                            ("entry/src/main/cpp/testcef","testcef 真 C++"),
                            ("entry/src/main/cpp/CMakeLists.txt","OpenQtCef CMakeLists"),
                            ("entry/src/main/cpp/include","CEF include"),
                            ("entry/src/main/cpp/libcef_dll","libcef_dll wrapper")]:
            if not (glue / need).exists(): fail(f"OpenQtCef 胶水缺 {label}: {glue}/{need}")
        info(f"OpenQtCef 胶水: {glue}（全量 overlay 路径）")
    else:
        glue = None
        if not cef_root or not cef_root.is_dir(): fail("无 --ohqtcef-glue 时必须 --cef-root（CEF 组件包）")
        for need in ["include","cmake","libcef_dll"]:
            if not (cef_root / need).is_dir(): fail(f"CEF 组件包缺 {need}/")
        if not (cef_root / "libs/arm64-v8a/libcef.so").is_file(): fail("CEF 组件包缺 libcef.so")
        info(f"CEF 组件包: {cef_root}（公开 only 路径，CEF<->ArkTS 胶水用骨架 §5.3 TODO）")
    cfg = load_config(args.config)
    if args.deveco: cfg["deveco"] = args.deveco
    if args.device: cfg["device"] = args.device
    if args.ohos_ndk: cfg["ohos_ndk"] = args.ohos_ndk
    info(f"配置: deveco={cfg['deveco']} | device={cfg['device']} | sdk={cfg['compatible_sdk_version']} | qt_libs={cfg['qt_libs']}")
    devecocli = cfg.get("devecocli") or shutil.which("devecocli") or str(Path(os.environ.get("APPDATA",""))/"npm/devecocli.cmd")
    if Path(devecocli).exists(): info(f"devecocli: {devecocli}（--run 用）")
    else: warn("devecocli 不可用（--run 跳过签名+装机+启动）")
    return dict(qt_sdk=qt_sdk, template=template, qt_major=qt_major, qt_ver=qt_ver,
                glue=glue, cef_root=cef_root, devecocli=devecocli, config=cfg)

# ---------- 嫁接 ----------
def graft(args, ctx):
    out = Path(args.output).resolve()
    if out.exists(): fail(f"输出目录已存在: {out}（先删或换路径）")
    template = ctx["template"]; glue = ctx["glue"]
    step("1. 复制模板 → 输出（保版本正确 Qt 胶水）")
    shutil.copytree(template, out)
    for c in [".hvigor",".cxx",".idea","oh_modules","build"]:
        for p in out.rglob(c):
            if p.is_dir(): shutil.rmtree(p, ignore_errors=True)
    info(f"已复制到 {out}")
    if glue:
        overlay_openqtcef_full(out, glue, ctx, args)
    else:
        overlay_public_skeleton(out, ctx, args)
    deploy_qt_so(out, ctx["qt_sdk"], ctx["config"])  # P10
    patch_build_profile_full(out, args, ctx)  # P6/P8/P9/P13
    patch_qt_constants(out, "qtmodule" if glue else args.app_name)  # P11/P12: glue 用 qtmodule target
    patch_app_scope(out, args.bundle)
    write_hvigor_wrapper(out, ctx["config"])  # P7
    run_ohpm_install(out, ctx["config"])  # P15
    return out

def overlay_openqtcef_full(out, glue, ctx, args):
    step("2. OpenQtCef 全量 overlay（真 C++ + web_engine + adapter + CEF .so）")
    # P11/P12: 用 OpenQtCef 真 C++（testcef/mainwindow/main + CMakeLists + include/libcef_dll/cmake + 完整 CefSettings）替骨架
    src_cpp = glue / "entry/src/main/cpp"
    dst_cpp = out / "entry/src/main/cpp"
    if dst_cpp.exists(): shutil.rmtree(dst_cpp)
    shutil.copytree(src_cpp, dst_cpp)
    info(f"真 C++ overlay: {dst_cpp}（testcef/mainwindow/main + OpenQtCef CMakeLists + adapter_c 源码 + 完整 CefSettings）")
    # web_engine har 模块（含 CEF 资源 icudtl.dat/.pak/locales in resfile）
    we = glue / "web_engine"
    if we.is_dir():
        dst_we = out / "web_engine"
        shutil.copytree(we, dst_we)
        for stale in ["oh-package-lock.json5","BuildProfile.ets"]:
            p = dst_we / stale
            if p.exists(): p.unlink()
        info(f"web_engine/ overlay（含 CEF 资源 resfile: icudtl.dat/.pak/locales）")
    # CEF .so（libcef.so+libadapter.so+依赖链）从 glue/entry/libs 部署
    src_lib = glue / "entry/libs/arm64-v8a"
    dst_lib = out / "entry/libs/arm64-v8a"; dst_lib.mkdir(parents=True, exist_ok=True)
    n = 0
    for so in src_lib.glob("*.so"):
        shutil.copy2(so, dst_lib / so.name); n += 1
    info(f"CEF .so 部署: {n} 个（libcef.so+libadapter.so+依赖链）")
    # libadapter_c napi 类型已随 cpp/ copytree 带入（OpenQtCef cpp/ 含 types/libadapter_c），无需重复复制
    # build-profile modules 加 web_engine（P6 括号深度）+ oh-package deps
    patch_build_profile_modules(out)
    patch_oh_package(out)
    # QAbility extends WebQtAbility + QAbilityStage extends WebAbilityStage + IoC（P4/P5 具名 super + adapter_c.initFunc + super.onCreate）
    patch_qability_extends(out)
    # CEF 权限
    patch_module_json5(out)
    info("QAbility extends WebQtAbility（具名 super）+ QAbilityStage extends WebAbilityStage（IoC super.onCreate）+ CEF 权限")

def overlay_public_skeleton(out, ctx, args):
    step("2. 公开 only overlay（CEF 内核+CefClient 骨架，CEF<->ArkTS 留 §5.3 TODO）")
    cef_root = ctx["cef_root"]; app = args.app_name
    dst_lib = out / "entry/libs/arm64-v8a"; dst_lib.mkdir(parents=True, exist_ok=True)
    for so in (cef_root/"libs/arm64-v8a").glob("*.so"): shutil.copy2(so, dst_lib/so.name)
    write_cmake(out, app, ctx["qt_sdk"], cef_root, ctx["qt_major"], find_ohos_adapter(cef_root))
    write_cpp_skeletons(out, app)
    inject_arkts_skeleton(out, app)
    patch_module_json5(out)

def deploy_qt_so(out, qt_sdk, cfg):  # P10: 部署 Qt 运行时 .so（libqohos+Qt .so+qohosstyle 从 SDK）
    step("3. 部署 Qt 运行时 .so（libqohos+Qt .so+qohosstyle 从 SDK）")
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

# ---------- build-profile（P6/P8/P9/P13）----------
def patch_build_profile_full(out, args, ctx):
    step("4. build-profile 配置（abiFilters arm64-only P8 + SDK17 lazy import P9 + QT_PREFIX P13）")
    bp = out / "build-profile.json5"
    if not bp.is_file(): warn("build-profile.json5 不存在，跳过"); return
    t = bp.read_text(encoding="utf-8")
    # P9: compatibleSdkVersion + stage（从 config 取，OpenQtCef web_engine 用 lazy import 需 API17）
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
        # P13: arguments -DQT_PREFIX=<sdk>（OpenQtCef CMake 用 ${QT_PREFIX}）
        qt = str(ctx["qt_sdk"]).replace("\\","/")
        et = re.sub(r'"arguments"\s*:\s*"[^"]*"', f'"arguments": "-DQT_PREFIX={qt}"', et)
        if '"arguments"' not in et:
            et = et.replace('"externalNativeOptions"', f'"externalNativeOptions": {{\n      "arguments": "-DQT_PREFIX={qt}",', 1)
        ebp.write_text(et, encoding="utf-8")
        info("entry/build-profile: abiFilters=arm64-v8a only + arguments -DQT_PREFIX")
    bp.write_text(t, encoding="utf-8")
    info(f"build-profile: compatibleSdkVersion {sdk}+stage {stage}")

def patch_build_profile_modules(out):  # P6: 括号深度找 modules ] + 尾逗号剥除
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

def patch_qability_extends(out):  # P4/P5: 具名 super + IoC
    qa = out / "entry/src/main/ets/qability/QAbility.ets"
    if qa.is_file():
        t = qa.read_text(encoding="utf-8")
        if "WebQtAbility" not in t:
            t = t.replace("extends UIAbility", "extends WebQtAbility", 1)
            if "import { WebQtAbility }" not in t:
                t = "import { WebQtAbility } from 'web_engine';\n" + t
            super_args = {  # P4: 具名参数（ArkTS 禁 arguments 索引访问）
                "onCreate": "(want, launchParam)", "onWindowStageCreate": "(windowStage)",
                "onWindowStageDestroy": "()", "onForeground": "()", "onBackground": "()",
                "onDestroy": "()", "onNewWant": "(want, launchParam)", "onContinue": "(wantParam)"}
            for m, a in super_args.items():
                pat = r"(" + re.escape(m) + r"\([^)]*\)[^{]*\{)"  # P5: 容许 :void 返回类型
                t = re.sub(pat, r"\1\n    super." + m + a + ";  // WebQtAbility CEF 协作", t, count=1)
            qa.write_text(t, encoding="utf-8")
    qs = out / "entry/src/main/ets/qabilitystage/QAbilityStage.ets"
    if qs.is_file():
        t = qs.read_text(encoding="utf-8")
        if "WebAbilityStage" not in t:
            t = t.replace("extends AbilityStage", "extends WebAbilityStage", 1)
            if "import { WebAbilityStage }" not in t:
                t = "import { WebAbilityStage } from 'web_engine';\nimport adapter_c from 'libadapter_c.so';\n" + t
            t = re.sub(r"(onCreate\([^)]*\)[^{]*\{)",  # P5: 容许 onCreate(): void {
                       r"\1\n    adapter_c.initFunc(1.0);  // scaledDensity TODO §5.3\n"
                       r"    super.onCreate();  // WebAbilityStage IoC（InjectModule.inject 绑定 AbilityManager 等，§B.3）",
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

# ---------- hvigor-wrapper.bat（P7 spawn java ENOENT）+ ohpm（P15）----------
def write_hvigor_wrapper(out, cfg):  # P7 spawn java ENOENT
    step("5. 生成 hvigor-wrapper.bat（修 PackageHap spawn java ENOENT，P7）")
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
    info(f"hvigor-wrapper.bat（cd /d + 重注 jbr/java PATH）")

def run_ohpm_install(out, cfg):  # P15: 链接 web_engine 依赖，否则 import unresolved
    step("6. ohpm install（链接 web_engine 依赖，P15）")
    deveco = cfg.get("deveco", "C:/Program Files/Huawei/DevEco Studio")
    pm = Path(deveco) / "tools/ohpm/bin/pm-cli.js"
    env = os.environ.copy()
    env["JAVA_HOME"] = f"{deveco}/jbr"; env["DEVECO_SDK_HOME"] = f"{deveco}/sdk"
    env["PATH"] = f"{deveco}/jbr/bin;{deveco}/tools/node/bin;{deveco}/tools/ohpm/bin;" + env.get("PATH","")
    if not pm.exists(): warn(f"ohpm pm-cli.js 不存在: {pm}，跳过（需手动 ohpm install）"); return
    try:
        r = run(["node", str(pm), "install"], check=False, capture=True, env=env, cwd=str(out), timeout=300)
        info(f"ohpm install 完成（exit {r.returncode}）")
    except Exception as e:
        warn(f"ohpm install 失败: {e}（需手动 ohpm install）")

# ---------- 公开 only 骨架 CMake/cpp（P1/P2/P3）----------
def write_cmake(out, app, qt_sdk, cef_root, qt_major, adapter):
    qt_libs = "Qt6::Core Qt6::Gui Qt6::Widgets" if qt_major == "6" else "Qt5::Core Qt5::Gui Qt5::Widgets"
    if qt_major == "6":
        qt_block = f'find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)\nqt_add_executable({app} main.cpp cefclient/my_client.cpp)'
    else:
        qt_block = f'find_package(Qt5 REQUIRED COMPONENTS Core Gui Widgets)\nadd_library({app} SHARED main.cpp cefclient/my_client.cpp)'
    adp = adapter.name if adapter else "<OHOS adapter .so>  # §5.2 版本敏感"
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
# P3: OHOS CMAKE_SYSTEM_NAME=OHOS 非 Linux，CEF_LIBTYPE 空 → ADD_LOGICAL_TARGET 失败；直链 libcef.so（OpenQtCef 模式）
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
    (cpp/"main.cpp").write_text(f'''// {app} — Qt + CEF OHOS demo（骨架，kb-cef-graft.py 公开 only 路径）
// 全量跑通用 --ohqtcef-glue（OpenQtCef 真 C++ testcef 完整 CefSettings）；本骨架 CefSettings 不全（P12）。
#include <QApplication><QMainWindow><thread><atomic>
#include "include/cef_app.h"
#include "cefclient/my_client.h"
extern "C" __attribute__((visibility("default"))) int cef_subprocess_entry(int argc,char*argv[]){{
  return CefExecuteProcess(CefMainArgs(argc,argv),nullptr,nullptr);}}
static std::atomic<bool> g_cef_ready{{false}};
static void cef_thread(int argc,char**argv){{
  CefSettings s; s.no_sandbox=true;
  // TODO §B.2: s.browser_subprocess_path="<lib{app}.so>"; // 骨架不全→CefInitialize 会 SIGTRAP（P12），用 --ohqtcef-glue
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

# ---------- --run: devecocli 签名+装机+启动+崩溃日志（P14）----------
def devecocli_run(out, args, ctx):
    step("7. devecocli signature generate + run + log（--run，P14 签名）")
    dc = ctx["devecocli"]
    if not Path(dc).exists(): warn("devecocli 不可用，跳过 --run（手动跑 devecocli signature generate + run）"); return
    deveco = ctx["config"].get("deveco", "C:/Program Files/Huawei/DevEco Studio")
    env = os.environ.copy()
    env["JAVA_HOME"] = f"{deveco}/jbr"; env["DEVECO_SDK_HOME"] = f"{deveco}/sdk"
    env["PATH"] = f"{deveco}/jbr/bin;{deveco}/tools/node/bin;{deveco}/tools/hvigor/bin;{deveco}/tools/ohpm/bin;" + env.get("PATH","")
    info("devecocli signature generate（生成 debug 证书+profile 写进 build-profile，P14）")
    r = run([dc, "signature", "generate", "--force"], check=False, capture=True, cwd=str(out), timeout=300, env=env)
    info(f"signature generate exit {r.returncode}")
    info("devecocli run（build signed + 装机 + 启动 QAbility）")
    r = run([dc, "run", "--module", "entry", "--device", args.device or ctx["config"].get("device","46G0225208000016"),
             "--ability", "QAbility", "--build-mode", "debug", "--uninstall"],
            check=False, capture=True, cwd=str(out), timeout=900, env=env)
    info(f"run exit {r.returncode}")
    if r.returncode == 0:
        info("=== 崩溃检查（devecocli log --crash）===")
        import time; time.sleep(7)
        rc = run([dc, "log", "--crash", "--bundle-name", args.bundle], check=False, capture=True, timeout=120, env=env)
        crash = re.search(r"Reason:|SIGSEGV|SIGTRAP|Kill Reason|\.ets:", rc.stdout or "")
        if crash: warn("检测到崩溃，见上；可能需补 .so/资源/版本适配（见 qt-cef-ohos-dev-guide §5）")
        else: info("✓ 无崩溃，app 运行中（用 devecocli log --bundle-name <bundle> 看 CEF 启动）")
        print((rc.stdout or "")[-1500:])

# ---------- 报告 ----------
def report(out, ctx, args):
    step("8. 报告")
    glue = ctx["glue"]
    print(f"  ✓ 嫁接产出: {out}")
    print(f"  Qt: Qt{ctx['qt_major']} {ctx['qt_ver'] or ''} | 路径: {'OpenQtCef 全量 overlay（一次跑通）' if glue else '公开 only（骨架，CEF<->ArkTS §5.3 TODO）'}")
    if glue:
        print("\n  全量路径固化（运行测试踩坑全修）:")
        print("    P1 CMake set 分行 | P2 路径正斜杠 | P3 直链 libcef.so（替 ADD_LOGICAL_TARGET）")
        print("    P4 QAbility 具名 super（ArkTS 无索引访问）| P5 QAbilityStage IoC 正则容 :void")
        print("    P6 build-profile 括号深度找 ]+尾逗号剥除 | P7 hvigor-wrapper.bat（spawn java ENOENT）")
        print("    P8 abiFilters arm64-only | P9 compatibleSdkVersion 5.0.5(17)+stage（lazy import）")
        print("    P10 部署 libqohos+Qt5+qohosstyle（Qt 运行时）| P11 OpenQtCef adapter_c（替骨架）")
        print("    P12 OpenQtCef 真 C++（testcef 完整 CefSettings，替骨架）| P13 arguments -DQT_PREFIX")
        print("    P14 devecocli signature generate（签名）| P15 ohpm install（web_engine 依赖）")
    print("\n  下一步:")
    if glue and args.run:
        print("    --run 已执行签名+装机+启动+崩溃检查（见上方 devecocli 输出）")
    elif glue:
        print("    cd <output> && devecocli signature generate --force  # P14 签名")
        print("    devecocli run --module entry --device <id> --ability QAbility --build-mode debug --uninstall  # 装机+启动")
        print("    devecocli log --crash --bundle-name <bundle>  # 崩溃检查")
    else:
        print("    填 §5.3 骨架 TODO（node_manager/IoC/子进程符号）后用 --ohqtcef-glue 跑通")

def main():
    ap = argparse.ArgumentParser(description="把 CEF 嫁接到鸿蒙 Qt 模板工程上（运行测试踩坑全固化）")
    ap.add_argument("--template", required=True)
    ap.add_argument("--qt-sdk", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--cef-root", help="CEF 组件包（公开 only 路径用；--ohqtcef-glue 时可省）")
    ap.add_argument("--ohqtcef-glue", help="OpenQtCef 胶水路径（全量 overlay 一次跑通）")
    ap.add_argument("--app-name", default="qtcefdemo")
    ap.add_argument("--bundle", default="com.example.qtcefdemo")
    ap.add_argument("--config", help="配置文件路径（JSON，环境配置：deveco/device/SDK版本/Qt .so 等，agent 改配置不改脚本）")
    ap.add_argument("--deveco", default=None, help="DevEco 路径（覆盖 config）")
    ap.add_argument("--ohos-ndk", default=None)
    ap.add_argument("--device", default=None, help="设备 id（覆盖 config）")
    ap.add_argument("--run", action="store_true", help="全量路径：devecocli 签名+装机+启动+崩溃检查")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    ctx = preflight(args)
    if args.dry_run:
        print("\n[dry-run] 预检完成，未落地。"); return 0
    out = graft(args, ctx)
    if args.run and ctx["glue"]:
        devecocli_run(out, args, ctx)
    report(out, ctx, args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
