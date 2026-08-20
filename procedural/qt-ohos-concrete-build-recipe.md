---
id: procedural-qt-ohos-concrete-build-recipe
type: procedural
domain: workflow
tags: [workflow, qt, harmonyos, ohos, build, cmake, hvigorw, ohos-toolchain, porting, migration]
created: 2026-07-04
updated: 2026-08-03
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-build-run-workflow, semantic-qt-harmonyos-build]
summary: >
  Qt→OHOS 迁移的落地编译配方（Playbook A/B）：OhosExampleApp/CMakeLists.txt 构建 libOhos<Slug>.so
  + main.cpp (extern "C" int main, QPA dlsym 入口) + HarmonyOS 模板 → hvigorw assembleHap → 未签名 HAP；
  或 ohos-build/CMakeLists.txt + ohos.toolchain.cmake → 静态库 .a。100 应用批量验证（69/100 成功）。
  本页是 [[qt-app-harmonyos-migration]] 8 步工作流的"阶段三编译"落地版。
---

# Qt→OHOS 落地编译配方（Playbook A / B）

> 本页是 [[qt-app-harmonyos-migration]] 的阶段三（编译验证）落地配方。8 步工作流讲"改什么"，本页讲"怎么编出来"。
> 2026-07-04 在 xlsx rows 400-499 共 100 个 Qt 开源应用上批量验证：**69 成功**（17 HAP + 52 库），2 失败，29 延期。

---

## 参考实现

`${PROJECTS_ROOT}/260702/qView/` 是首个完整迁移并构建成功的 HAP 项目，本页所有模式均来自该实现 + 100 应用批量的复现。

## 环境固定路径

| 项 | 路径 |
|----|------|
| Qt 5.15 OHOS SDK | `${QT5_15_OHOS_SDK}`（CMAKE_PREFIX_PATH） |
| 鸿蒙胶水模板 | `${OHOS_TEMPLATE_SRC}`（5.15 / 5.12 源码树内均有） |
| OHOS cmake | `…/sdk/default/openharmony/native/build-tools/cmake/bin/cmake.exe` |
| OHOS ninja | `…/native/build-tools/cmake/bin/ninja.exe` |
| OHOS toolchain | `…/native/build/cmake/ohos.toolchain.cmake` |
| hvigorw | `C:/Program Files/Huawei/DevEco Studio/tools/hvigor/bin/hvigorw.js` |
| node | `C:/Program Files/nodejs/node` |
| jbr (java) | `C:/Program Files/Huawei/DevEco Studio/jbr/bin` |
| libqohosstyle.so | `${QT5_15_OHOS_SDK}/plugins/styles/libqohosstyle.so` |
| QPA 插件 | `${QT5_15_OHOS_SDK}/plugins/platforms/libqohos.so`（构建时由 CMake 链接，无需手拷） |

目标 ABI：**arm64-v8a**（仅此一种）。本节路径为 Qt5.15.16 SDK；Qt6-only 项目走 §Qt6 变体（Qt6 6.12 superbuild，见 [[qt6-ohos-windows-cli-deploy]]；部署前仍必做 `patch_needed.py` + main 可见性，非直接判不可行）。

## Slug 命名

- `<Slug>` = PascalCase、仅字母数字，从项目名派生（去连字符/下划线/点）：`Qt-AES`→`QtAes`、`qt-json`→`QtJson`、`Qt-Advanced-Docking-System`→`QtAdvancedDockingSystem`。
- `add_library(Ohos<Slug> SHARED …)` → 产物 `libOhos<Slug>.so`。
- `bundleName` = `com.example.<slug-lower-no-hyphens>`。

---

## Playbook A — 应用 / 示例（有 `int main()`）→ 未签名 HAP

### A1. `OhosExampleApp/CMakeLists.txt`

```cmake
cmake_minimum_required(VERSION 3.16)
project(Ohos<Slug> LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)
# .ui 与 .cpp 分目录（forms/ vs src/）时 AUTOUIC 不会自动按 .ui 目录搜，
# #include "ui_*.h" 会报 "could not be found" → 须显式列 .ui 目录（promoted widget 头目录也一并列）
# list(APPEND CMAKE_AUTOUIC_SEARCH_PATHS ${APP_SRC_DIR}/<forms-or-ui-dir> <src-dir>)  # 见 [build-fail-autouic-ui-not-found]

# 交叉编译 find_package 修复（关键）
if(CMAKE_CROSSCOMPILING)
    set(_saved "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
    set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()
find_package(Qt5 5.15 REQUIRED COMPONENTS <Core Gui Widgets Network …>)  # 仅用到的模块
if(CMAKE_CROSSCOMPILING)
    set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "${_saved}")
endif()

set(APP_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../<srcsubdir>")
include_directories(${APP_SRC_DIR} ${CMAKE_CURRENT_SOURCE_DIR})

set(APP_SOURCES   ${APP_SRC_DIR}/<file1>.cpp ${APP_SRC_DIR}/<file2>.cpp …)  # 从 .pro SOURCES，排除 *win32*/*x11*/*cocoa*/*osx*/*android*
set(APP_HEADERS   ${APP_SRC_DIR}/<file1>.h …)
set(APP_FORMS     ${APP_SRC_DIR}/<file>.ui …)        # 如有
set(APP_RESOURCES ${APP_SRC_DIR}/<file>.qrc)          # 如有

add_library(Ohos<Slug> SHARED main.cpp ${APP_SOURCES} ${APP_HEADERS} ${APP_FORMS} ${APP_RESOURCES})

target_compile_definitions(Ohos<Slug> PRIVATE
    QT_DEPRECATED_WARNINGS
    # QT_NO_FOREACH   ← 仅当确认项目不用 Qt foreach 宏时才定义！否则 OMIT
    NO_X11
    # 应用自有 DEFINES
)

target_link_libraries(Ohos<Slug> PRIVATE
    Qt5::Core Qt5::Gui Qt5::Widgets   # 仅用到的模块
    Qt5::QOhosPlatformIntegrationPlugin
)
```

### A2. `OhosExampleApp/main.cpp`（OHOS 入口 shim）

QPA 插件通过 `dlsym("main")` 查找入口点，故共享库**必须**导出 `extern "C" int main`：

```cpp
#include <QApplication>
#include "<mainwindow header>"
extern "C" int main(int argc, char *argv[])
{
#if QT_VERSION < QT_VERSION_CHECK(6, 0, 0)
    QCoreApplication::setAttribute(Qt::AA_EnableHighDpiScaling);
#endif
    QApplication app(argc, argv);
    QCoreApplication::setOrganizationName("<Name>");
    QCoreApplication::setApplicationName("<Name>");
    MainWindow w;   // 改为项目的主窗口类
    w.show();
    return app.exec();
}
```

> 从项目原始 `main.cpp` 改造：保留 org/app name、高 DPI、命令行解析等逻辑；把 `int main` 改成 `extern "C" int main`；**排除原始 main.cpp 不进 APP_SOURCES**（用 shim 替代，避免重复符号）。

### A3. 从模板创建 HarmonyOS/

```bash
mkdir -p "${PROJECTS_ROOT}/<batch>/<Name>/HarmonyOS"
cp -r "${OHOS_TEMPLATE_SRC}/." "<…>/HarmonyOS/"
```

**无 Qt 源码时**：
```bash
bash skills/kb-init/scripts/download-template.sh --dest=workspace/templates
cp -r "workspace/templates/." "<…>/HarmonyOS/"
```

### A4. 配置 7 个文件（`HarmonyOS/` 下）

1. **`entry/build-profile.json5`** `externalNativeOptions`：
   - `"path": "<绝对路径>/OhosExampleApp/CMakeLists.txt"`（正斜杠）
   - `"arguments": "-DCMAKE_PREFIX_PATH=${QT5_15_OHOS_SDK}"`
   - `"abiFilters": ["arm64-v8a"]`（删掉 `x86_64`）
2. **`AppScope/app.json5`**：`"bundleName": "com.example.<slug-lower>"`
3. **`entry/src/main/ets/common/QtAppConstants.ets`**：`APP_LIBRARY_NAME = 'libOhos<Slug>.so';`、`LOG_TAG = '<Name>';`
4. **`AppScope/resources/base/element/string.json`**：`app_name` value → `<Name>`
5. **`entry/src/main/resources/{base,en_US,zh_CN}/element/string.json`**：`QAbility_label` value → `<Name>`（三个语言都改）
6. **`build-profile.json5`（根）** 覆盖为**未签名**配置（模板自带的 `signingConfig:"default"` 是无效的，必须改）：
   ```json5
   {
     "app": {
       "signingConfigs": [],
       "products": [
         { "name": "default", "compatibleSdkVersion": "5.0.0(12)", "compatibleSdkVersionStage": "beta3", "runtimeOS": "HarmonyOS" }
       ],
       "buildModeSet": [ { "name": "debug" }, { "name": "release" } ]
     },
     "modules": [
       { "name": "entry", "srcPath": "./entry", "targets": [ { "name": "default", "applyToProducts": ["default"] } ] },
       { "name": "qEmbeddedUiExtensionHost", "srcPath": "./qEmbeddedUiExtensionHost", "targets": [ { "name": "default", "applyToProducts": ["default"] } ] }
     ]
   }
   ```
7. **`local.properties`**：`sdk.dir=C:\\Program Files\\Huawei\\DevEco Studio\\sdk`

### A5. 拷贝 Qt 样式插件

```bash
mkdir -p "<…>/HarmonyOS/entry/libs/arm64-v8a/styles"
cp "${QT5_15_OHOS_SDK}/plugins/styles/libqohosstyle.so" "<…>/HarmonyOS/entry/libs/arm64-v8a/styles/"
```

> 其余 Qt 运行时 .so（libQt5Core.so、libqohos.so QPA 等）由 CMake/hvigorw 在构建时从 SDK 自动链接打包，**无需手拷**（qView 实测 libs/ 只有 styles/libqohosstyle.so，HAP 仍完整）。

### A6. 构建

```bash
export PATH="/c/Program Files/Huawei/DevEco Studio/jbr/bin:/c/Program Files/Huawei/DevEco Studio/tools/node:$PATH"
export DEVECO_SDK_HOME='C:\Program Files\Huawei\DevEco Studio\sdk'
cd "<…>/HarmonyOS"
node "C:/Program Files/Huawei/DevEco Studio/tools/hvigor/bin/hvigorw.js" assembleHap \
  --mode module -p product=default -p buildMode=debug --no-daemon
```

**成功标志**：`entry/build/default/outputs/default/entry-default-unsigned.hap` 存在 + `BUILD SUCCESSFUL`。

> 编译验证目标 = 未签名 HAP（不配签名）。签名是独立后续步骤，不阻塞编译。详见 [[qt-harmonyos-build-run-workflow]] 与 [signhap-bundlename-mismatch]。

---

## Playbook B — 库 / 插件 / header-only → .a/.so

库不产出 HAP，用独立 CMake + OHOS toolchain 交叉编译。

### B1. `ohos-build/CMakeLists.txt`

```cmake
cmake_minimum_required(VERSION 3.16)
project(Ohos<Slug> LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

if(CMAKE_CROSSCOMPILING)
    set(_saved "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
    set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()
find_package(Qt5 5.15 REQUIRED COMPONENTS <Core Gui Widgets …>)
if(CMAKE_CROSSCOMPILING)
    set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "${_saved}")
endif()

set(LIB_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../<srcsubdir>")
include_directories(${LIB_SRC_DIR})

add_library(Ohos<Slug> STATIC ${LIB_SRC_DIR}/<file1>.cpp ${LIB_SRC_DIR}/<file2>.cpp …)
# 插件用 MODULE；header-only 库加一个 test_main.cpp (int main(){return 0;}) #include 头文件来验证

target_link_libraries(Ohos<Slug> PRIVATE Qt5::Core Qt5::Gui Qt5::Widgets)  # 库不需要 QPA 插件
target_compile_definitions(Ohos<Slug> PRIVATE QT_DEPRECATED_WARNINGS NO_X11)
```

> 优先**写全新极简 CMakeLists 直接列源码**，不要 `add_subdirectory(原始)`——原始 CMake 常含 Qt6 find_package、install/export、CPack 等会污染交叉编译的规则。

### B2. 构建

```bash
OHOS_NATIVE="C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/native"
CMAKE="$OHOS_NATIVE/build-tools/cmake/bin/cmake.exe"
NINJA="$OHOS_NATIVE/build-tools/cmake/bin/ninja.exe"
cd "<…>/ohos-build"
"$CMAKE" -S . -B build -G Ninja \
  -DCMAKE_MAKE_PROGRAM="$NINJA" \
  -DCMAKE_TOOLCHAIN_FILE="$OHOS_NATIVE/build/cmake/ohos.toolchain.cmake" \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_PREFIX_PATH="${QT5_15_OHOS_SDK}" \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH
"$CMAKE" --build build
```

**成功标志**：`build/libOhos<Slug>.a`（或 `.so`）存在。

### B3. Playbook B → Demo 验证（可选）

静态库无法直接安装到真机，需编写 Playbook A 风格的 demo 应用完成端到端验证。

**适用场景**：需要验证库在 OHOS 真机上的运行时行为（如 qhttp HTTP 通信、QSqlMigrator 数据库迁移）。

**Demo 工程结构**：

```
ProjectRoot/
├── OhosExampleApp/          ← 新建（Playbook A 风格）
│   ├── CMakeLists.txt       ← 编译库源码 + demo main.cpp → SHARED lib
│   └── main.cpp             ← QWidget demo，展示库核心功能
├── HarmonyOS/               ← 从已有 Playbook A 项目复制
└── src/ (或 lib/)           ← 原始库源码
```

**CMakeLists.txt 要点**：

```cmake
# 直接编译库源码（非链接 .a），与 demo main.cpp 一起打成 SHARED lib
set(LIB_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../src)
include_directories(${LIB_SRC_DIR})

add_library(Ohos<Slug>Demo SHARED
    main.cpp
    ${LIB_SOURCES}    # 库的 .cpp 文件
)

# 必加 DBus（复用 RedisView 经验）
target_link_libraries(Ohos<Slug>Demo PRIVATE
    Qt5::Core Qt5::Gui Qt5::Widgets
    Qt5::DBus                              # ← 必加
    Qt5::QOhosPlatformIntegrationPlugin
)
```

**main.cpp 设计原则**：
- QWidget UI：提供可交互按钮/输入框，展示库的核心功能
- 日志输出：用 QTextEdit 显示操作结果，便于验证
- 沙箱安全：文件操作使用 `QStandardPaths::writableLocation()`
- `extern "C" int main()`：OHOS entry shim 标准格式

**已验证案例**：

| 项目 | 库类型 | Demo 功能 | 构建时间 | 真机验证 |
|------|--------|----------|---------|---------|
| qhttp | HTTP 库 | Server 启停 + Client GET + 日志 | 23s | ✅ 进程稳定 |
| QSqlMigrator | 数据库迁移库 | DB 打开/关闭 + 迁移 + CRUD + 日志 | 24s | ✅ 进程稳定 |

> 详细运行测试流程见 [[qt-ohos-run-test]] §7。

---

## 批量验证得到的关键经验

| 经验 | 说明 | 反例项目 |
|------|------|---------|
| **QT_NO_FOREACH 慎用** | 仅在 grep 确认项目**不**使用 Qt `foreach` 宏时才定义；否则 OMIT（定义会编译失败） | QRCodeGenerator/mainwindow.cpp、qt-json/json.cpp、QtWebApp（共 10 处 foreach） |
| **x86 内联禁用** | arm64 不支持 AESNI/SSE/AVX；不定义 `USE_INTEL_AES_IF_AVAILABLE` 等 | Qt-AES |
| **全新 CMakeLists 优先** | 不 add_subdirectory 原始 CMake（Qt6 find_package / 硬编码路径 / install 规则会坏事） | simple-mail、Qt-AES、SARibbon |
| **Qt5+Qt6 "both" 优先 Qt5** | `find_package(Qt5 5.15 …)`（现成 SDK 无补丁）；Qt6-only 项目走「Qt6 变体」 | "both" 项目走 Qt5；Qt6-only 走 Qt6 |
| **Qt6-only 不再不可行** | Qt6 6.12 superbuild 可编译（2026-07-13 验证），无需源码补丁；部署前仍必做两道运行时检查：NEEDED 改裸名（`patch_needed.py`）+ `main` 加 `visibility("default")`；否则设备 dlopen/dlsym 失败 | qcoro/qlementine/libQuotient 等 8 个延期项 un-blocked（见 §「Qt6 变体」）|
| **OHOS Qt Network 无 OpenSSL** | SDK 的 Qt Network 编译时 `QT_NO_SSL`；SSL 分支需 `#ifndef QT_NO_SSL` 守卫 | simple-mail（SslConnection/TlsConnection case 标签移入守卫） |
| **clang 严格执行 C++ 标准** | MSVC 允许的 `QPixmap icon = ""`（双重用户定义隐式转换）clang 拒绝，需显式改写 | FdogInstantMessaging/query.h |
| **OHOS Qt5 SDK 模块缺口** | 不提供 Qt5QuickControls2 / Qt5Quick3D / Qt5WebSockets / Qt5UiTools / Qt5PrintSupport（部分）| Open-Typer、bppgrid、canonic |
| **OHOS clang 15 不支持 C++23** | 不支持 P0847 deducing-this（`this auto& self`），即使 `-std=c++2b` | creeper-qt |
| **hvigorw ArkTS WARN 非错误** | 模板层 deprecated NODE/getShared、napi verification、SDK 5.0.5 on 5.0.0(12)——构建仍成功 | 全部 HAP 项目 |

## 不可行判据（直接 defer，不进入编译批次）

- **Qt6-only 不再不可行** ✅：Qt6 6.12 superbuild 在 Windows **可编译**（2026-07-13 验证，gallery demo 真机运行通过），无需源码补丁；部署前必做 `patch_needed.py`（DT_NEEDED）+ main 可见性。见 [[qt6-ohos-windows-cli-deploy]] + [[qt-harmonyos-qt6-status]]。Qt6-only 项目（qcoro、qlementine、libQuotient、qml-niri、nodegui、libONVIF、QSvgStyle、unofficial-discord-client 等）改走 **Qt6 路径**（见下方「Qt6 变体」），非 defer。
- **核心功能绑 X11/Win32/D-Bus**：QHotkey（X11+Win32 全局热键）、qxtglobalshortcut、QtGlobalEvent（Win32 钩子）、QGnomePlatform（D-Bus/GTK）、telepathy-morse（D-Bus）、Qt-Nice-Frameless-Window（Win32/Cocoa）。
- **专有/重型原生引擎**：VLC、Ultralight、CEF（NewBingClient）、i2pd、google-breakpad（qBreakpad）、Vulkan WSI（LearnVulkan）、Firebase、Skia（QtSkia——需 Linux GN 交叉编译 libskia.a）。
- **网络抓包/系统级**：Network-capture（WinPcap/Winsock2）。

## Qt6 变体（A/B 均可配 Qt6）

A/B 与 Qt5/Qt6 正交：A/B 选产物形态（HAP/.a），Qt5/Qt6 选 SDK。选 Qt6 时，在 A/B 之上加：

1. **SDK**：Qt6 6.12 superbuild 产物（host + target），非现成 Qt5.15.16 SDK。构建步骤见 [[qt6-ohos-windows-cli-deploy]]（MinGW g++ host + API 23，无需源码补丁）。
2. **CMake**：`find_package(Qt6 REQUIRED COMPONENTS ...)`（非 Qt5），`qt_add_executable`/`qt_add_resources`（去版本号前缀）。`CMAKE_PREFIX_PATH` 指向 Qt6 dev 构建目录。
3. **DT_NEEDED 改裸名**（运行时必须）：Qt6 `.so` 无 SONAME + Windows 交叉编译 → NEEDED 含绝对 Windows 路径（如 `<Qt6-build-dir>/lib*.so`）→ 设备 dlopen 失败。用 `patch_needed.py` 把所有 `.so`（业务库 + Qt 库自身）NEEDED 改裸名，`llvm-readelf -d` 验证无绝对路径（见 [runtime-fail-absolute-needed-path]）。
4. **`main` 可见性**（运行时必须）：给 `main` 加 `__attribute__((visibility("default")))`，`llvm-readelf --dyn-syms` 验证为 `GLOBAL DEFAULT`（见 [runtime-fail-main-symbol-hidden]）。
5. **资源部署**：`share/xxx` 运行时数据放 `entry/src/main/resources/resfile/share/xxx`，应用经 `QOhosAppContext::resourceDir()+"/share/xxx"` 定位。
6. **模块剪枝**：D-Bus/OpenSSL/WebEngine/MCP/QML Designer 在 Qt6 OHOS 不可用，`FEATURE_dbus=OFF`/`INPUT_openssl=no`/跳过相关子目录。

> Qt5→Qt6 API 差异（关闭事件私有化、QStandardPaths 映射变更、CMake API）详见 [[qt-harmonyos-qt6-status]]。

## 何时用哪条 Playbook

| 项目特征 | Playbook | 产物 |
|----------|----------|------|
| 有 `int main()`（application / example） | A | `entry-default-unsigned.hap` |
| 库 / 插件 / header-only（无 main） | B | `libOhos<Slug>.a` / `.so` |
| 不确定 | grep `int main(`；有则 A，无则 B | — |

## 供应链

详见 [[qt-app-harmonyos-migration]] 供应链章节。本配方是其中的"阶段三编译"环节。

## 相关上下文

- [[qt-app-harmonyos-migration]] — 8 步迁移工作流（本页是其阶段三落地版）
- [[qt-harmonyos-project-structure]] — 工程结构 / 模板 / CMake 四项关键配置
- [[qt-harmonyos-build-run-workflow]] — DevEco MCP / hvigorw / 构建失败排查四步法
- [[qt-harmonyos-build]] — Qt OHOS 构建环境搭建
- 批次复盘：qt-opensource-apps-batch-port-400-499（episodic）
- 相关问题：[build-fail-qtnetwork-no-ssl]、[build-fail-qtquickcontrols2-missing-ohos]、[build-fail-clang-strict-msvc-implicit-conversion]、[build-fail-cpp23-deducing-this]

## 内容来源

| 来源 | 说明 |
|------|------|
| 🛠️ 工作经验 | 100 应用批量迁移（xlsx rows 400-499，2026-07-04）+ qView 参考实现（260702 批次）——Playbook A/B 均在该批次实证 |
| 🔍 框架源码 | Qt 5.15.16 OHOS SDK 目录结构（lib/、plugins/platforms/libqohos.so、plugins/styles/libqohosstyle.so）、qtbase 源码内置胶水模板 |
| 📖 华为官方文档 | DevEco Studio / hvigorw / OHOS native toolchain 路径与用法 |
