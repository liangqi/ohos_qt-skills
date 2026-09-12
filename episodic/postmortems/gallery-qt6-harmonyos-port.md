---
id: episodic-projects-gallery-qt6-harmonyos-port
type: episodic
domain: project
tags: [gallery, qt6, harmonyos, ohos, porting, cmake, harmonydeployqt, additional-packages]
created: 2026-09-12
updated: 2026-09-12
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-qt6-status, semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-project-structure]
summary: >
  Qt Widgets gallery 示例（qmake/Qt5）用 Qt 6.12.0 预构建鸿蒙 kit 移植到 HarmonyOS arm64-v8a：
  qt_add_executable 的 finalizer 自动产出 MODULE 库 + ${target}_make_hap 目标，
  Qt5 时代手工套模板/配 APP_LIBRARY_NAME/手动拷 libqohosstyle.so 全部自动化。
  三条关键结论：additional-packages 的 10 个运行时 .so 必须用 QT_HARMONYOS_EXTRA_LIBS 显式补
  （ICU 还要版本化/非版本化双名字）；Qt6 的平台宏是 Q_OS_HARMONY 不是 Qt5 的 Q_OS_OHOS；
  签名是最后一公里（未签名 HAP 装不上机）。编译/打包/依赖闭包已验证，真机运行未验证。
---

# gallery（Qt Widgets 示例）Qt 6.12 鸿蒙化 — 经验总结

## 项目概览

| 字段 | 内容 |
|------|------|
| 时间 | 2026-09-12 |
| 源工程 | `qtbase/examples/widgets/gallery`（Qt 5 时代，qmake，`QT += widgets`） |
| 目标 | HarmonyOS arm64-v8a |
| Qt | **6.12.0 预构建安装器 kit**（`<QtSDK>/6.12.0/harmonyos_arm64_v8a` + host `macos`） |
| host | macOS arm64 |
| 产物 | `entry-default-unsigned.hap` 103 MB / 签名后 `entry-default-signed.hap` 104 MB |
| 移植代价 | 新增 1 个 CMakeLists.txt + 改 20 行源码 |

## 预检结论

| 预检项 | 结果 |
|--------|------|
| Qt 版本（按代码判定） | Qt 5 代码（`QString::splitRef`、`AA_EnableHighDpiScaling`），需 Qt5→Qt6 改造 |
| 模块依赖 | Core / Gui / Widgets — 预构建 kit 全有 |
| 项目类型 | 有 `int main()` → application（Playbook A），产物 HAP |
| 平台绑定 | 无 X11 / Win32 / D-Bus / Cocoa |
| `foreach` / 三方库 | 均无 |

**可行性：低风险。**

---

## 关键发现

### 1. Qt 6.12 kit 自带鸿蒙工程模板与 CMake finalizer，Qt5 时代的手工步骤全部作废

kit 内 `src/harmonyos/templates/` 就是完整的 DevEco 工程模板（ArkTS 胶水、`QAbility.ets`、
`build-profile.json5`…），`harmonydeployqt` 会自动取用——**不需要再手工复制模板目录**。

`qt_add_executable()` 在 OHOS 上：
- 用 `add_library(MODULE)` 产出 `libgallery.so`，并把可见性设为 `default`，
  使 `main` 保持 `GLOBAL DEFAULT`（ArkTS 侧 `dlsym("main")` 取入口）——实测符号表确认；
- 注册 `_qt_internal_harmonyos_executable_finalizer`，生成
  `<build>/gallery-harmony-deployment-settings.json` 与 **`gallery_make_hap`** 目标，
  该目标调用 `harmonydeployqt`（+ hvigor）一步出 HAP。

实测**自动完成**的事（对照 [[qt-harmonyos-project-structure]] 里 Qt5 的手工清单）：

| Qt5 手工步骤（golden-rules） | Qt 6.12 预构建 kit |
|------|------|
| B2 链接 `QOhosPlatformIntegrationPlugin` | 不用写，`libqohos.so` 自动进 `entry/libs/arm64-v8a/` |
| B3 手配 `QtAppConstants.ets` 的 `APP_LIBRARY_NAME` | 自动生成 `export const APP_LIBRARY_NAME = 'libgallery.so';` |
| B7 手拷 `libqohosstyle.so` → `libs/<abi>/styles/` | 自动，含 `imageformats/`、`generic/` 插件子目录 |
| §1.4 手改 `string.json` 的 `app_name` / `QAbility_label` | 由 `QT_HARMONYOS_APP_NAME` / `_APP_LABEL` / `_APP_BUNDLE_NAME` 目标属性生成 |

命令形态（本次实际使用）：

```bash
<QT6_OHOS_SDK>/bin/qt-cmake -S . -B <build> -DCMAKE_BUILD_TYPE=Release \
  -DHARMONYOS_HVIGOR=/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw
cmake --build <build> --target gallery_make_hap
```

> `HARMONYOS_HVIGOR`（或环境变量 `QT_HARMONYOS_HVIGOR`）在 **configure 时**读取；不给的话
> `harmonydeployqt` 会尝试在生成的工程里找 hvigorw，而模板里没有该 wrapper。
> 另注：kit 里烘焙的 OHOS SDK 路径是 `/opt/harmonyos/command-line-tools/sdk/...`
> （configure 输出可见），与 DevEco Studio 自带的那份 SDK 是两码事。

### 2. additional-packages 的 10 个运行时 .so 必须显式补，ICU 要双名字

`harmonydeployqt` 只带 Qt 自己的库。首次打出的 HAP 31.8 MB，用依赖闭包脚本查出 **10 个未解析依赖**：

```
libQt6Core.so → libicui18n.so.78  libicuuc.so.78  libicudata.so.78
libQt6Gui.so  → libfontconfig.so  libfreetype.so  libpng16.so
libfontconfig → libexpat.so ;  libqjpeg.so → libjpeg.so
ICU 自身的 NEEDED 又是无版本后缀的 libicuuc.so / libicudata.so
```

正规做法不是写脚本手拷，而是 kit 支持的 **`QT_HARMONYOS_EXTRA_LIBS`** 目标属性
（对标 Android 的 `QT_ANDROID_EXTRA_LIBS`，取绝对路径或 CMake target）：

```cmake
if(OHOS)
    # 7 个按原名
    foreach(_lib libexpat.so libfontconfig.so libfreetype.so libicudata.so
                 libicuuc.so libjpeg.so libpng16.so)
        list(APPEND _ohos_extra_libs "${OHOS_ADDITIONAL_PACKAGES}/lib/${_lib}")
    endforeach()
    # 3 个 ICU 版本化别名：kit 链接 libicu*.so.78，而 additional-packages 的
    # SONAME 无版本后缀（符号后缀 _78 对得上）；鸿蒙沙箱不能用 symlink，只能改名复制
    foreach(_alias libicui18n libicuuc libicudata)
        file(COPY_FILE "${OHOS_ADDITIONAL_PACKAGES}/lib/${_alias}.so"
                       "${_extra_dir}/${_alias}.so.78" ONLY_IF_DIFFERENT)
        list(APPEND _ohos_extra_libs "${_extra_dir}/${_alias}.so.78")
    endforeach()
    set_property(TARGET gallery APPEND PROPERTY QT_HARMONYOS_EXTRA_LIBS ${_ohos_extra_libs})
endif()
```

**版本化与非版本化两个名字都要在场**（Qt 认 `.so.78`，ICU 之间认无后缀名）。
实测 hvigor 能正常打包 `*.so.78` 这种文件名（`unzip -l` 确认在 `libs/arm64-v8a/` 内）。
代价：`libicudata.so` 33 MB 打了两份，HAP 从 31.8 MB 涨到 103 MB。
瘦身思路（未实施）：把 `libQt6Core.so` 的 `DT_NEEDED` 字符串原地截短为无后缀名
（新串更短可安全原地改），只留一份 ICU。

### 3. Qt 6 的鸿蒙平台宏是 `Q_OS_HARMONY`，不是 Qt 5 的 `Q_OS_OHOS`

`qsystemdetection.h`：`#elif defined(__OHOS__)` → `#define Q_OS_HARMONY` + `Q_OS_LINUX`。
**写成 `#ifdef Q_OS_OHOS` 的平台适配在 Qt 6 里是死代码，编译不报错、行为静默错误。**
（同一应用的另一次移植尝试正是栽在这里：沙箱路径适配整段没生效。）
`Q_OS_LINUX` 仍被隐含定义，golden-rules G1 的"检查所有 `Q_OS_LINUX` 分支"照旧成立。

### 4. Qt5 → Qt6 源码改造只有两处

| 文件 | 改动 | 原因 |
|------|------|------|
| `widgetgallery.cpp` | `QString::splitRef()` → `split()` | Qt 6 已删除；**全工程唯一的编译错误** |
| `main.cpp` | `AA_UseHighDpiPixmaps` / `AA_EnableHighDpiScaling` / `AA_DisableHighDpiScaling` 用 `QT_VERSION < 6.0` 包住 | Qt 6 高 DPI 恒开，三者是废弃 no-op（3 条 deprecated 警告） |

鸿蒙适配另加一处：`QFileSystemModel` 根路径在 `Q_OS_HARMONY` 下由 `QDir::rootPath()`（`/`）
改为 `QStandardPaths::AppDataLocation` 并 `setRootIndex()`——沙箱里 `/` 不可读，否则 Tree View 是空的。

窗口**无需**改动：`WidgetGallery` 虽是无 parent 的 `QDialog`，但它是首个顶层窗口，
按 First Window Rule（W2）自动绑定系统主窗口，不触发 W3。

### 5. 签名是最后一公里

`harmonydeployqt` 支持六件套签名参数（或同名 `QT_HARMONYOS_SIGNING_*` 环境变量）：
`--signing-cert-path` / `--signing-profile` / `--signing-store-file` / `--signing-key-alias` /
`--signing-key-password` / `--signing-store-password`（口令必须是 hvigor 加密后的 blob），
**六个缺一就整体跳过签名**，加 `--install` 可直接经 hdc 装机。

本次卡点：`~/.ohos/config/` 里 DevEco 自动生成的调试证书 `.cer/.p7b/.p12` 绑定的 bundle-name
是别的应用（profile 内 `"bundle-name"` 字段可用 `strings` 直接看），且 DevEco 26 把自动签名
口令留在 IDE 会话里、工程 `build-profile.json5` 的 `signingConfigs` 是空数组，
命令行无从复用 → 只能先用 DevEco Studio 打开生成的工程勾一次自动签名。

**实际走通的路径**：用 DevEco Studio 打开 `<build>/harmonyos-build`，勾 *Automatically generate
signature* —— DevEco 会为本工程的 bundleName 新签一套 `.cer/.p7b/.p12` 放进 `~/.ohos/config/`，
并把 `material`（含 hvigor 加密后的 `keyPassword`/`storePassword`）写进**生成工程的**
`build-profile.json5`。此后：

```bash
cd <build>/harmonyos-build
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:/Applications/DevEco-Studio.app/Contents/tools/node/bin:$PATH"
<DevEco>/Contents/tools/hvigor/bin/hvigorw assembleHap --no-daemon   # → entry-default-signed.hap
```

> ⚠️ **不要再跑 `<target>_make_hap`**：`harmonydeployqt` 会重新生成工程、覆盖
> `build-profile.json5`，刚配好的 `signingConfigs` 就没了。要让签名进 CMake 流程，
> 得把那六个值以 `QT_HARMONYOS_SIGNING_*` 环境变量喂给 `harmonydeployqt`（口令用
> `build-profile.json5` 里已加密的 blob 原样传）。

---

## 验证状态

| 检查项 | 结果 |
|--------|------|
| configure | ✅ Clang 15.0.4，EGL / GLESv3 正常识别 |
| 交叉编译 | ✅ 修掉 `splitRef` 后一次通过 |
| `main` 为 `GLOBAL DEFAULT` | ✅ |
| 打 HAP | ✅ `BUILD SUCCESSFUL`，`entry-default-unsigned.hap` 103 MB |
| 运行时依赖闭包 | ✅ 补 10 个 .so 后无未解析项（脚本递归比对 NEEDED × sysroot × HAP libs） |
| macOS host 构建 | ✅ 同一份源码/CMakeLists 桌面侧照常编译（改动跨平台安全） |
| **真机运行** | ✅ **通过**（2026-09-12，HUAWEI 设备 / HarmonyOS）——见下节 |

## 真机验证（2026-09-12）

```bash
hdc install -r <...>/entry-default-signed.hap          # install bundle successfully
hdc shell aa start -a QAbility -b org.qtproject.example.gallery -m entry
```

hilog 里 Qt 胶水链路完整，**无任何缺库**（说明 §2 的 10 个 .so 补对了）：

```
setupQtApplication() - sharedLibraryName: libgallery.so
opened library '/data/storage/el1/bundle/libs/arm64/libgallery.so' with main function
calling 'main' function ... argv[0]='/data/storage/el1/bundle/libs/arm64/libgallery.so'
```

> 最后一行是铁律 L2（`argv[0]` 是**库路径**不是可执行文件路径）的直接实证。

截图确认渲染正常：标题 `Widget Gallery Qt 6.12.0`，Style 下拉为 **`ohos`**（说明
`styles/libqohosstyle.so` 自动部署生效），按钮 / 单选 / 三态复选框 / 密码框 / SpinBox /
日期时间 / 滑块 / Dial / 富文本全部正常，深色模式跟随系统，进度条动画在走，
窗口带鸿蒙原生标题栏与最大/最小/关闭按钮。关闭后进程正常退出
（`AbilityStage::onDestroy: calling _Exit(0)`），无崩溃。

**观察 1：`AppDataLocation` 在沙箱里落在空的 `preferences/`，Tree View 因此是空的。**
§4 的沙箱适配防住了"读 `/` 什么也没有"，但换到的目录本身也没内容——
设备上 `/data/app/el2/100/base/<bundle>/` 下是 `cache` / `files` / `haps` /
`preferences` / `temp` 五个子目录，而 Qt6 的 `AppDataLocation` 映射到 `preferences/`（空）。
要让文件树有东西看，应改用 `QDir::homePath()`（沙箱根）或 `files/`。
这条同时是 [[qt-harmonyos-qt6-status]] 「`AppLocalDataLocation` 在 Qt6 改映射到 preferencesDir」
的运行时实证。

**观察 2：关闭窗口时有两条非致命报错**（不影响退出，根因未定位）：

```
E OHOS plugin: got error from hideAbility(): name='Error',
  message='The StartOptions check failed.', code='16000067'
D OHOS plugin: Error: xComponent 0x... does not have any assigned receiver
```

发生在 `QDialog` 关闭走鸿蒙 hide 路径时（对应铁律 W5「主窗口 `hide()` 回退为最小化」的实现路径）。
单次观察、未复现验证，**暂不入 problems/**；如后续在别的应用上复现，再按错误码 `16000067` 立页。

## 可复用产出

- **CMakeLists 模式**：`qt_add_executable` + `QT_HARMONYOS_APP_*` + `QT_HARMONYOS_EXTRA_LIBS`，
  additional-packages 路径以 `OHOS_ADDITIONAL_PACKAGES` 环境变量/cache 变量注入并在缺失时 `FATAL_ERROR`。
- **依赖闭包自查脚本**：以 HAP 的 `entry/libs/<abi>/` 为根，递归取 `llvm-readelf -d` 的 NEEDED，
  逐个在「HAP libs / OHOS sysroot / additional-packages」三处找，找不到即 UNRESOLVED。
  打包后跑一遍，比装机后看 hilog 里的 `dlopen` 失败便宜得多。
