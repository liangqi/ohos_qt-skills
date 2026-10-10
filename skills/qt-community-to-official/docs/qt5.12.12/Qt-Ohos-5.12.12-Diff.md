# Qt for HarmonyOS (OHOS) 版本差异分析文档

## Qt 5.12.12 (qt-harmonyos-src) vs Qt 5.15.12 (tqtc-qt5-5.15)

> **用途**: 开发者和 `qt-community-to-official` skill 可根据本文档实现 Qt 5.12.12 与 Qt 5.15.12 鸿蒙化版本之间的切换。

---

## 目录

1. [差异总览](#1-差异总览)
2. [qtohosextras 模块（公开 API）](#2-qtohosextras-模块公开-api)
3. [QPA 平台插件差异](#3-qpa-平台插件差异)
4. [NAPI 构建系统重构（最关键变化）](#4-napi-构建系统重构最关键变化)
5. [qohosdeviceinfo 文件迁移](#5-qohosdeviceinfo-文件迁移)
6. [qohospointerstyle.h 移除](#6-qohospointerstyleh-移除)
7. [QPA 插件源码差异（qohosplugincore / qohosplatformintegration / qohosplatformtheme）](#7-qpa-插件源码差异qohosplugincore--qohosplatformintegration--qohosplatformtheme)
8. [mkspecs 与编译配置差异](#8-mkspecs-与编译配置差异)
9. [各子模块 OHOS 插件差异](#9-各子模块-ohos-插件差异)
10. [权限配置（module.json5）](#10-权限配置modulejson5)
11. [DevEco 应用模板](#11-deveco-应用模板)
12. [头文件清单与类名索引](#12-头文件清单与类名索引)
13. [行尾格式差异](#13-行尾格式差异)
14. [版本切换迁移指南](#14-版本切换迁移指南)

---

## 1. 差异总览

| 维度 | 5.12.12 (社区/开源版基线) | 5.15.12 (tqtc 商业版) | 差异级别 |
|---|---|---|---|
| **qtohosextras 公开 API** | 17 个公开头文件 | 完全相同 (41 文件逐一对比) | **无差异** |
| **QPA 平台插件源码** | 214 个 .h/.cpp 文件 | 214 个文件内容完全相同 | **无差异** |
| **NAPI 构建方式** | `include(node-addon-api.pri)` + `-lace_napi.z` | `CONFIG += qnapi` (新 qnapi.prf) | **全局重构** |
| **qohosdeviceinfo 位置** | `corelib/kernel/` | `plugins/platforms/ohos/` | **文件迁移** |
| **qohospointerstyle.h** | 存在于 QPA 插件 | 已移除 | **文件移除** |
| **qohosplugincore.h/.cpp** | 原始版本 | 新增 NAPI 模块、枚举重构、API 变更 | **有差异** |
| **qohosplatformintegration** | 原始版本 | 新增设置缓存、PC 模式窗口能力 | **有差异** |
| **qohosplatformtheme.cpp** | QPixmap::loadFromData | QImageReader + setScaledSize | **有差异** |
| **qmake.conf 警告** | `-Wno-error` | `-Werror` | **配置变更** |
| **权限 (module.json5)** | 17 项权限 | 完全相同 | **无差异** |
| **DevEco 模板** | 完整模板 | 完全相同 | **无差异** |
| **各模块插件源码** | 原始版本 | 少量增强（HEIC、超分辨率等） | **少量差异** |
| **行尾格式** | LF (Unix) | CRLF (Windows) | **格式差异** |

**核心结论**: 两版本的鸿蒙化 **公开 API 完全一致**，差异集中在 **构建系统重构**（NAPI 依赖方式）、**内部文件组织**（qohosdeviceinfo 迁移）、以及少量 **QPA 插件内部实现增强**。

---

## 2. qtohosextras 模块（公开 API）

### 2.1 完全相同的部分

以下内容在两个版本中 **逐文件、逐字节完全相同**（共 41 个源文件 + 头文件 + .pro）：

**公开头文件 (17 个)**:

| 头文件 | 类/功能 |
|---|---|
| `qohosabilitycontext.h` | `QOhosAbilityContext` — Ability 上下文 |
| `qohosuiabilitycontext.h` | `QOhosUiAbilityContext` — UIAbility 上下文 |
| `qohosappcontext.h` | `QOhosAppContext` — 应用上下文 |
| `qohosappbundleinfo.h` | `QOhosAppBundleInfo` — Bundle 信息 |
| `qohosapppermissions.h` | `QOhosAppPermissions` — 应用权限 |
| `qohosbundlemanager.h` | `QOhosBundleManager` — Bundle 管理器 |
| `qohosenums.h` | OHOS 枚举定义 |
| `qohosfileshare.h` | `QOhosFileShare` — 文件分享 |
| `qohosfileutils.h` | `QOhosFileUtils` — 文件工具 |
| `qohosmultimediautils.h` | `QOhosMultimediaUtils` — 多媒体工具 |
| `qohosoperationstatus.h` | `QOhosOperationStatus` — 操作状态 |
| `qohospasteboard.h` | `QOhosPasteboard` — 剪贴板 |
| `qohossharekit.h` | `QOhosShareKit` — 分享工具包 |
| `qohosstartoptions.h` | `QOhosStartOptions` — 启动选项 |
| `qohosstartrequest.h` | `QOhosStartRequest` — 启动请求 |
| `qohoswant.h` | `QOhosWant` — Want 跨组件通信 |
| `qohoswindowutils.h` | `QOhosWindowUtils` — 窗口工具 |
| `qtohosextrasglobal.h` | 全局宏定义 |

**私有头文件 (7 个)**:
- `qohosappbundleinfo_p.h`, `qohosapppermissionsutils_p.h`, `qohosoperationstatus_p.h`
- `qohossharekit_p.h`, `qohosstartoptions_p.h`, `qohosstartrequest_p.h`, `qohoswantutils_p.h`

**构建文件**:
- `qtohosextras.pro`, `src/src.pro`, `src/ohosextras/ohosextras.pro`
- `.qmake.conf`, `sync.profile`

**所有 .cpp 实现文件**: 15 个，逐一对比完全相同。

### 2.2 迁移影响

> **开发者无需修改任何 qtohosextras API 调用代码**。所有公开类名、方法签名、枚举值、命名空间在两个版本中完全一致。

---

## 3. QPA 平台插件差异

### 3.1 源文件清单对比

QPA 平台插件 (`qtbase/src/plugins/platforms/ohos/`) 共 214 个 .h/.cpp 源文件，**内容完全相同**。

仅存在以下文件级差异:

| 文件 | 5.12.12 | 5.15.12 | 说明 |
|---|---|---|---|
| `qohospointerstyle.h` | ✅ 存在 | ❌ 移除 | 指针样式枚举头文件 |
| `qohosdeviceinfo_p.h` | ❌ 不在此目录 | ✅ 新增 | 从 corelib 迁移至此 |
| `qohosdeviceinfo.cpp` | ❌ 不在此目录 | ✅ 新增 | 从 corelib 迁移至此 |

### 3.2 ohos.pro 差异（QPA 插件构建文件）

```diff
--- 5.12.12 ohos.pro
+++ 5.15.12 ohos.pro

 # HEADERS 部分:
-    $$PWD/qohospointerstyle.h \           # 移除: 指针样式头文件
+    $$PWD/qohosdeviceinfo_p.h \            # 新增: 设备信息头文件（从 corelib 迁入）

 # SOURCES 部分:
+    $$PWD/qohosdeviceinfo.cpp \            # 新增: 设备信息源文件（从 corelib 迁入）

 # LIBS 部分:
-    -lace_napi.z \                        # 移除: NAPI 库直接链接
     -lace_ndk.z \                         # 保留

 # 底部:
-include($$PWD/../../../3rdparty/node-addon-api.pri)   # 移除: 直接包含 NAPI pri
+CONFIG += qnapi                                        # 新增: 使用 qnapi 特性
+
+include($$PWD/../../../3rdparty/optional-lite.pri)    # 新增: optional-lite 依赖
```

### 3.3 QPA 插件源码差异详情

以下 4 个 QPA 插件内部源文件存在内容差异（非公开 API，开发者通常不直接调用）:

| 文件 | 变更行数 | 变更类型 |
|---|---|---|
| `qohosplugincore.h` | ~20 行 | 枚举重构、新方法、类型变更 |
| `qohosplugincore.cpp` | ~50 行 | 新 NAPI 模块、代码风格、API 变更 |
| `qohosplatformintegration.h` | ~3 行 | 新增成员变量 |
| `qohosplatformintegration.cpp` | ~16 行 | 设置缓存、PC 模式窗口能力 |
| `qohosplatformtheme.cpp` | ~30 行 | 文件图标渲染改进 |

详见 [第 7 节](#7-qpa-插件源码差异qohosplugincore--qohosplatformintegration--qohosplatformtheme)。

---

## 4. NAPI 构建系统重构（最关键变化）

### 4.1 变更概述

5.15.12 引入了全新的 **`qnapi.prf`** qmake 特性文件，统一管理 NAPI (node-addon-api) 的头文件包含和库链接。所有原先直接 `include(node-addon-api.pri)` + `-lace_napi.z` 的模块，统一改为 `CONFIG += qnapi`。

### 4.2 新增文件: qnapi.prf

**路径**: `qtbase/mkspecs/features/ohos/qnapi.prf`（仅 5.15.12 存在）

```qmake
# Build dependency for using QtCore's QNapi helpers (kernel/qnapi_p.h).
#
# Enable from any qtbase or sibling-submodule .pro/.pri with:
#
#     CONFIG += qnapi
#
# Provides everything a consumer of qnapi_p.h needs:
#   - the bundled node-addon-api headers (include path + NAPI defines), and
#   - the OHOS NAPI runtime library (-lace_napi.z).
include($$clean_path($$PWD/../../../src/3rdparty/node-addon-api.pri))
LIBS_PRIVATE += -lace_napi.z
```

### 4.3 受影响的 .pro/.pri 文件（完整清单）

以下文件全部从旧方式迁移到新方式:

| 模块 | 文件路径 | 5.12.12 (旧) | 5.15.12 (新) |
|---|---|---|---|
| QPA 平台插件 | `qtbase/src/plugins/platforms/ohos/ohos.pro` | `include(node-addon-api.pri)` + `-lace_napi.z` | `CONFIG += qnapi` + `include(optional-lite.pri)` |
| QtCore 内核 | `qtbase/src/corelib/kernel/kernel.pri` | `LIBS_PRIVATE += -lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 网络承载 | `qtbase/src/plugins/bearer/ohos/src/src.pro` | `LIBS_PRIVATE += -lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 打印支持 | `qtbase/src/plugins/printsupport/ohos/ohos.pro` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 字体数据库 | `qtbase/src/platformsupport/fontdatabases/ohos/openharmony.pri` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 多媒体 | `qtmultimedia/src/plugins/ohos/src/src.pro` | `-lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 音频 | `qtmultimedia/src/plugins/ohos-audio/src/src.pro` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 传感器 | `qtsensors/src/plugins/sensors/ohos/ohos.pro` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 语音合成 | `qtspeech/src/plugins/tts/ohos/ohos.pro` | `LIBS += -lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| WebView | `qtwebview/src/plugins/ohos/ohos.pro` | `-lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| 定位 | `qtlocation/src/plugins/position/ohos/ohos.pro` | `-lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |

### 4.4 迁移影响

> **迁移到 5.15.12 时**: 如果开发者有自定义的 .pro 文件引用了 NAPI，需要将:
> ```qmake
> # 旧方式 (5.12.12)
> LIBS += -lace_napi.z
> include($$PWD/path/to/node-addon-api.pri)
> ```
> 替换为:
> ```qmake
> # 新方式 (5.15.12)
> CONFIG += qnapi
> ```
>
> **反向迁移到 5.12.12 时**: 将 `CONFIG += qnapi` 替换回直接引用。

---

## 5. qohosdeviceinfo 文件迁移

### 5.1 位置变更

| 版本 | 头文件路径 | 源文件路径 | 引用位置 |
|---|---|---|---|
| 5.12.12 | `qtbase/src/corelib/kernel/qohosdeviceinfo_p.h` | `qtbase/src/corelib/kernel/qohosdeviceinfo.cpp` | `corelib/kernel/kernel.pri` |
| 5.15.12 | `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo_p.h` | `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo.cpp` | `plugins/platforms/ohos/ohos.pro` |

### 5.2 内容差异

头文件内容 **几乎相同**，唯一差异是导出宏:

```diff
--- 5.12.12 (corelib 版，有 Q_CORE_EXPORT)
+++ 5.15.12 (QPA 插件版，无导出宏)

-Q_CORE_EXPORT void init(QMap<Type, QVariant> devinfo);
-Q_CORE_EXPORT QVariant getProperty(Type prop);
+void init(QMap<Type, QVariant> devinfo);
+QVariant getProperty(Type prop);

-Q_CORE_EXPORT QOhosOptional<RecognizedDeviceType> tryGetRecognizedDeviceType();
-Q_CORE_EXPORT bool isTablet();
-Q_CORE_EXPORT bool is2in1();
-Q_CORE_EXPORT bool isPhone();
-Q_CORE_EXPORT int sdkApiVersion();
-Q_CORE_EXPORT bool isCurrentDeviceSupported();
+QOhosOptional<RecognizedDeviceType> tryGetRecognizedDeviceType();
+bool isTablet();
+bool is2in1();
+bool isPhone();
+int sdkApiVersion();
+bool isCurrentDeviceSupported();
```

> **原因**: 从 QtCore 库迁移到 QPA 插件后，不再需要 `Q_CORE_EXPORT` 导出宏（插件内部使用，不跨库导出）。

### 5.3 API 不变

`QOhosDeviceInfo` 命名空间提供的 API 完全相同:

- `Type` 枚举: `deviceType`, `manufacture`, `brand`, `marketName`, ... `udid`, `distributionOSName`, ...
- `RecognizedDeviceType` 枚举: `_2in1`, `tablet`, `phone`
- 函数: `init()`, `getProperty()`, `tryGetRecognizedDeviceType()`, `isTablet()`, `is2in1()`, `isPhone()`, `sdkApiVersion()`, `isCurrentDeviceSupported()`

### 5.4 迁移影响

> **对开发者无直接影响**。`qohosdeviceinfo` 是内部私有头文件 (`_p.h`)，不属于公开 API。
>
> 如果开发者直接引用了 `QtCore/private/qohosdeviceinfo_p.h`，在 5.15.12 中需要改为从 QPA 插件目录引用。

---

## 6. qohospointerstyle.h 移除

### 6.1 变更说明

5.12.12 的 QPA 插件中包含 `qohospointerstyle.h`，定义了 `QOhosPointerStyle` 枚举（44 个指针样式值）及其 `OhosEnumMeta` 模板特化。5.15.12 中此文件已被移除。

### 6.2 移除原因

枚举定义可能已迁移到 `qohosenums.h` 统一管理（5.15.12 的 `qohosplugincore.h` 新增了 `#include <qohosenums.h>`，且将 `QOhosAbilityOnContinueResult` 从自定义枚举改为引用 `enums::ohos::app::ability::AbilityConstant::OnContinueResult`）。

### 6.3 迁移影响

> **对开发者无直接影响**。`qohospointerstyle.h` 是 QPA 插件内部头文件，不属于公开 API。

---

## 7. QPA 插件源码差异（qohosplugincore / qohosplatformintegration / qohosplatformtheme）

### 7.1 qohosplugincore.h 差异

```diff
--- 5.12.12
+++ 5.15.12

 // 头文件包含变更
-#include <array>
+#include <qohosenums.h>

 // 新增虚函数
+virtual void forceResolveQWindowDestroyPromiseIfPresent(Napi::Env env) = 0;

 // 枚举重构: QOhosAbilityOnContinueResult
-enum class QOhosAbilityOnContinueResult
-{
-    AGREE,
-    REJECT,
-    MISMATCH,
-};
+using QOhosAbilityOnContinueResult = enums::ohos::app::ability::AbilityConstant::OnContinueResult;

 // 移除 OhosEnumMeta 模板特化
-template<>
-struct OhosEnumMeta<QOhosAbilityOnContinueResult>
-{
-    static constexpr const char *fullTypeName = "@ohos.app.ability.AbilityConstant.OnContinueResult";
-    static constexpr std::array<std::pair<QOhosAbilityOnContinueResult, const char *>, 3> enumeratorsNames = {{ ... }};
-};

 // 超时参数类型变更
-Q_REQUIRED_RESULT bool tryInvokeInQtThreadAndTryWaitForContinue(
-    std::function<void(std::function<void()>)> &&task,
-    std::chrono::milliseconds timeout);
+Q_REQUIRED_RESULT bool tryInvokeInQtThreadAndTryWaitForContinue(
+    std::function<void(std::function<void()>)> &&task,
+    std::chrono::nanoseconds timeout);
```

### 7.2 qohosplugincore.cpp 差异

**新增 NAPI 模块注册**:
```diff
+    "@ohos.data.distributedDataObject",    // 分布式数据对象
+    "@ohos.net.connection",                // 网络连接管理
```

**新增虚函数实现**:
```diff
+void DummyQAbilityPeer::forceResolveQWindowDestroyPromiseIfPresent(Napi::Env)
+{
+}
```

**API 变更**:
- `hasValue()` → `has_value()` (optional-lite API 升级)
- `std::chrono::milliseconds timeout` → `std::chrono::nanoseconds timeout`

**代码风格变更**: 移除了大量单行 if 语句的花括号（不影响逻辑）。

### 7.3 qohosplatformintegration.h 差异

```diff
 private:
+    std::shared_ptr<void> m_settingsCacheHandle;    // 新增: 设置缓存句柄
+
     std::shared_ptr<void> m_eglDisplayHandle;
```

### 7.4 qohosplatformintegration.cpp 差异

**新增设置缓存初始化**:
```diff
+#include <qohossettings.h>

 // 构造函数中新增:
+m_settingsCacheHandle = QOhosSettings::instance().installSettingsCache();
```

**窗口能力变更 (NonFullScreenWindows)**:
```diff
         case MultipleWindows: return true;
-        case WindowManagement: return true;
+        case WindowManagement:
+        case NonFullScreenWindows:
+            return QOhosSettings::instance().isWindowPcModeEnabled();
```

> **说明**: 5.15.12 中 `WindowManagement` 不再无条件返回 `true`，而是根据 `QOhosSettings::isWindowPcModeEnabled()` 判断。新增了 `NonFullScreenWindows` 能力支持，同样依赖 PC 模式设置。

### 7.5 qohosplatformtheme.cpp 差异

**新增头文件**:
```diff
+#include <QtCore/qbuffer.h>
+#include <QtGui/qimagereader.h>
```

**文件图标渲染改进**:

5.12.12 使用 `QPixmap::loadFromData` 加载后用 `scaled()` 缩放:
```cpp
// 5.12.12: 简单加载 + 后缩放
QPixmap pixmap;
pixmap.loadFromData(resourceContentBuffer.Data(), resourceContentBuffer.ByteLength());
return pixmap.scaled(size, Qt::KeepAspectRatio, Qt::SmoothTransformation);
```

5.15.12 改用 `QImageReader` + `setScaledSize` 实现高效按需缩放:
```cpp
// 5.15.12: QImageReader 按需缩放，避免加载全尺寸图后再缩放
QBuffer svgResourceBuffer(&svgResourceContent);
QImageReader imageReader(&svgResourceBuffer);
const auto sourceSize = imageReader.size();
const auto targetSize = sourceSize.scaled(requestedSize, Qt::KeepAspectRatio);
imageReader.setScaledSize(targetSize);
const auto image = imageReader.read();
return QPixmap::fromImage(image);
```

**函数签名变更**:
```diff
-QOhosOptional<QPixmap> tryGetFilePixmapByResourceObject(
-    QtOhos::JsState &jsState, QNapi::Object resource)
+QOhosOptional<QPixmap> tryGetFilePixmapByResourceObject(
+    QtOhos::JsState &jsState, QNapi::Object resource, const QSize &requestedSize)

-QOhosOptional<QPixmap> tryGetFilePixmapByFilenameExtension(
-    QtOhos::JsState &jsState, const std::string &filenameExtension)
+QOhosOptional<QPixmap> tryGetFilePixmapByFilenameExtension(
+    QtOhos::JsState &jsState, const std::string &filenameExtension, const QSize &requestedSize)
```

> **说明**: 这些是 QPA 插件内部函数，不影响公开 API。改进了文件图标的渲染效率，特别是 SVG 图标。

### 7.6 迁移影响

> 这些差异全部在 QPA 插件内部实现中，**不影响开发者使用的公开 API**。但以下行为变化值得注意:
>
> 1. **窗口管理**: 5.15.12 中 `WindowManagement` 和 `NonFullScreenWindows` 能力受 PC 模式设置控制，开发者需确保 `QOhosSettings::isWindowPcModeEnabled()` 在目标设备上返回预期值。
> 2. **超时精度**: `tryInvokeInQtThreadAndTryWaitForContinue` 的超时参数从毫秒改为纳秒，精度提升 100 万倍。如果开发者直接调用了此内部函数，需调整超时值。
> 3. **分布式数据对象**: 5.15.12 新增了 `@ohos.data.distributedDataObject` NAPI 模块支持。

---

## 8. mkspecs 与编译配置差异

### 8.1 qmake.conf 差异

**路径**: `qtbase/mkspecs/ohos-clang/qmake.conf`

```diff
--- 5.12.12
+++ 5.15.12

     -Wformat \
-    -Wno-error
-
-QMAKE_CXXFLAGS_WARN_ON += -Wno-error
-QMAKE_CFLAGS_WARN_ON += -Wno-error
+    -Werror
```

> **影响**: 5.15.12 将警告视为错误 (`-Werror`)。迁移时需确保代码无编译警告，否则构建会失败。可在需要时临时添加 `-Wno-error` 恢复旧行为。

### 8.2 openharmonydeployqt.pro 差异

```diff
--- 5.12.12
+++ 5.15.12

     shellcommandoutputstream.cpp
+
+DEFINES -= QT_NO_JAVA_STYLE_ITERATORS
```

> **影响**: 部署工具在 5.15.12 中启用了 Java 风格迭代器支持。

### 8.3 其他不变的构建配置

以下配置文件在两版本中 **完全相同**:

| 文件 | 说明 |
|---|---|
| `ohos-clang/qplatformdefs.h` | 平台定义 |
| `features/ohos/ohos_deployment.prf` | 部署特性 |
| `configure.json` | 配置检测 |
| `platformheaders/ohosfunctions/qohosfunctions.h` | 平台函数头 |
| `platformheaders/ohosfunctions/ohosfunctions.pri` | 平台函数 pri |
| `tools/openharmonydeployqt/main.cpp` | 部署工具主程序 |

---

## 9. 各子模块 OHOS 插件差异

### 9.1 .pro 文件差异（全部为 NAPI 重构）

所有子模块的 .pro 文件差异 **仅为 NAPI 构建方式变更**（见 [第 4 节](#4-napi-构建系统重构最关键变化)），无其他配置差异。

### 9.2 源码内容差异

以下 OHOS 插件源文件存在少量内容差异（均为功能增强或 API 适配）:

#### 多媒体 (qtmultimedia)

| 文件 | 差异 | 说明 |
|---|---|---|
| `camera/qohoscameracommon.cpp` | +3 行 | 新增 `CAMERA_FORMAT_HEIC` 格式支持 |
| `camera/qohosimagecommon.cpp` | 少量 | 图像通用代码适配 |
| `mediaplayer/mediaplayer.pri` | 少量 | pri 文件调整 |
| `mediaplayer/qohosavplayer.cpp` | +9 行 | 新增 `AV_ERR_SUPER_RESOLUTION_UNSUPPORTED`、`AV_ERR_SUPER_RESOLUTION_NOT_ENABLED`、`AV_ERR_IO_CLEARTEXT_NOT_PERMITTED` 错误码处理 |

#### 传感器 (qtsensors)

| 文件 | 差异 | 说明 |
|---|---|---|
| `ohossensorbackendbase.h` | 1 行 | `std::numeric_limits<qreal>::min()` → `lowest()`（修正最小值语义） |
| `ohosmagnetometerbackend.cpp` | 少量 | 磁力计后端适配 |
| `ohossensorsmanager.cpp` | 少量 | 传感器管理器适配 |
| `ohossensorutils.cpp` | 少量 | 传感器工具适配 |

#### 语音合成 (qtspeech)

| 文件 | 差异 | 说明 |
|---|---|---|
| `qtexttospeech_ohos.cpp` | ~17 行 | `QSet::toList()` → `values()`、代码风格变更 |
| `corespeechkit/texttospeechproxy.cpp` | 少量 | TTS 代理适配 |
| `qohosexpected_p.h` | 少量 | expected 辅助头文件适配 |

#### WebView (qtwebview)

| 文件 | 差异 | 说明 |
|---|---|---|
| `qohoswebview.cpp` | +12 行 | 新增 `httpUserAgent()` / `setHttpUserAgent()` 方法（空实现 stub） |

#### 定位 (qtlocation)

| 文件 | 差异 | 说明 |
|---|---|---|
| `geoservices/ohosmapkit/qpoicategoryohosmapkit.cpp` | 少量 | POI 分类适配 |

### 9.3 完全相同的子模块

以下子模块的 OHOS 插件源码在两版本中 **完全相同**（无任何内容差异）:

- **蓝牙** (`qtconnectivity/src/bluetooth/ohos/`): 17 个文件全部相同
- **打印支持** (`qtbase/src/plugins/printsupport/ohos/`): 11 个文件全部相同
- **样式** (`qtbase/src/plugins/styles/ohos/`): 5 个文件全部相同
- **网络承载** (`qtbase/src/plugins/bearer/ohos/`): 19 个文件全部相同
- **字体数据库** (`qtbase/src/platformsupport/fontdatabases/ohos/`): 3 个文件全部相同
- **部署工具** (`qtbase/src/tools/openharmonydeployqt/`): 4 个文件全部相同
- **串口** (`qtserialport/src/serialport/ohos/`): 7 个文件全部相同

### 9.4 迁移影响

> 子模块差异均为 **内部功能增强**，不影响公开 API。开发者无需修改应用代码。多媒体的 HEIC 格式和超分辨率错误码是系统 SDK 升级带来的自然演进。

---

## 10. 权限配置（module.json5）

### 10.1 完全相同

权限配置文件 `qtbase/src/harmonyos/templates/entry/src/main/module.json5` 在两版本中 **完全相同**。

### 10.2 权限清单（17 项）

| 权限 | 用途 |
|---|---|
| `ohos.permission.SYSTEM_FLOAT_WINDOW` | 悬浮窗 |
| `ohos.permission.FILE_ACCESS_PERSIST` | 持久文件访问 |
| `ohos.permission.PRINT` | 打印 |
| `ohos.permission.PREPARE_APP_TERMINATE` | 应用终止准备 |
| `ohos.permission.STORE_PERSISTENT_DATA` | 持久数据存储 |
| `ohos.permission.INTERNET` | 网络 |
| `ohos.permission.READ_PASTEBOARD` | 读取剪贴板 |
| `ohos.permission.CAMERA` | 相机 |
| `ohos.permission.MICROPHONE` | 麦克风 |
| `ohos.permission.CUSTOM_SCREEN_CAPTURE` | 自定义截屏 |
| `ohos.permission.ACCELEROMETER` | 加速度计 |
| `ohos.permission.GYROSCOPE` | 陀螺仪 |
| `ohos.permission.APPROXIMATELY_LOCATION` | 大致位置 |
| `ohos.permission.LOCATION` | 精确位置 |
| `ohos.permission.GET_WIFI_INFO` | WiFi 信息 |
| `ohos.permission.ACCESS_BLUETOOTH` | 蓝牙 |
| `ohos.permission.GET_FILE_ICON` | 文件图标 |

### 10.3 Ability 声明

- `QAbility`: 主入口 Ability (launchType=specified, continuable)
- `QEmbeddedUiExtensionAbility`: 嵌入式 UI 扩展
- `QBundledEmbeddedUiExtensionAbility`: 打包嵌入式 UI 扩展

---

## 11. DevEco 应用模板

### 11.1 完全相同

DevEco Studio 应用模板 (`qtbase/src/harmonyos/templates/`) 的所有核心配置文件在两版本中 **完全相同**:

| 文件 | 说明 |
|---|---|
| `build-profile.json5` | 构建配置 (runtimeOS: HarmonyOS, compatibleSdkVersion: 5.0.0(12)) |
| `AppScope/app.json5` | 应用配置 (bundleName: com.ohos.ohosqttemplate) |
| `oh-package.json5` | 包配置 |
| `entry/src/main/module.json5` | 模块清单（含权限） |
| `entry/src/main/cpp/CMakeLists.txt` | CMake 构建 |
| `entry/src/main/ets/qability/QAbility.ets` | ArkTS Ability |
| `README.md` | 模板说明 |

### 11.2 构建产物差异

5.12.12 的模板目录中包含构建缓存文件（`.hvigor/`, `.idea/`, `entry/.cxx/`, `oh_modules/`），这些是构建产物而非源码。5.15.12 的模板目录中这些缓存已被清理。

> **迁移影响**: 无。构建产物不应纳入版本控制，清理是正确的做法。

---

## 12. 头文件清单与类名索引

### 12.1 qtohosextras 公开头文件（两版本完全相同）

```
QtOhosExtras/
├── qohosabilitycontext.h        → QOhosAbilityContext
├── qohosappbundleinfo.h         → QOhosAppBundleInfo
├── qohosappcontext.h            → QOhosAppContext
├── qohosapppermissions.h        → QOhosAppPermissions
├── qohosbundlemanager.h         → QOhosBundleManager
├── qohosenums.h                 → OHOS 枚举定义
├── qohosfileshare.h             → QOhosFileShare
├── qohosfileutils.h             → QOhosFileUtils
├── qohosmultimediautils.h       → QOhosMultimediaUtils
├── qohosoperationstatus.h       → QOhosOperationStatus
├── qohospasteboard.h            → QOhosPasteboard
├── qohossharekit.h              → QOhosShareKit
├── qohosstartoptions.h          → QOhosStartOptions
├── qohosstartrequest.h          → QOhosStartRequest
├── qohosuiabilitycontext.h      → QOhosUiAbilityContext
├── qohoswant.h                  → QOhosWant
├── qohoswindowutils.h           → QOhosWindowUtils
├── qtohosextrasglobal.h         → 全局宏
└── qtohosextrasversion.h        → 版本头
```

### 12.2 QPA 平台插件内部头文件（非公开）

以下头文件在 QPA 插件中，开发者通常不直接引用:

| 头文件 | 5.12.12 | 5.15.12 | 说明 |
|---|---|---|---|
| `qohosplugincore.h` | ✅ | ✅ (有变更) | 插件核心 |
| `qohosplatformintegration.h` | ✅ | ✅ (有变更) | 平台集成 |
| `qohosplatformtheme.h` | ✅ | ✅ | 平台主题 |
| `qohosplatformwindow.h` | ✅ | ✅ | 平台窗口 |
| `qohosplatformscreen.h` | ✅ | ✅ | 平台屏幕 |
| `qohosplatformclipboard.h` | ✅ | ✅ | 剪贴板 |
| `qohosplatformcursor.h` | ✅ | ✅ | 光标 |
| `qohosplatformdrag.h` | ✅ | ✅ | 拖放 |
| `qohoseventdispatcher.h` | ✅ | ✅ | 事件分发 |
| `qohosinputcontext.h` | ✅ | ✅ | 输入法 |
| `qohossettings.h` | ✅ | ✅ | 设置 |
| `qohospointerstyle.h` | ✅ | ❌ (移除) | 指针样式 |
| `qohosdeviceinfo_p.h` | ✅ (corelib) | ✅ (QPA) | 设备信息 |
| `qohosenums.h` | ✅ | ✅ | 枚举 |
| ... (共 100+ 内部头文件) | | | |

### 12.3 无障碍 (Accessibility) 头文件

无障碍模块 (`qtbase/src/plugins/platforms/ohos/accessibility/`) 的所有头文件在两版本中 **完全相同**:

- `qohosplatformaccessibility.h` — 平台无障碍实现
- `qohosaccessibilitytree.h` — 无障碍树
- `qohosaccessibilityprovider.h` — 无障碍提供者
- `qohosaccessibilityarkuihelpers.h` — ArkUI 无障碍辅助
- `qohosaccessibilityeventhandler.h` — 无障碍事件处理
- `qohosaccessibilitymenuactions.h` — 无障碍菜单动作
- `qohosaccessibilitynodehelpers.h` — 无障碍节点辅助
- `qohossafeqaccessibleinterfacewrapper.h` — 安全接口包装

---

## 13. 行尾格式差异

| 版本 | 行尾格式 | 说明 |
|---|---|---|
| 5.12.12 | LF (Unix) | 标准 Unix 行尾 |
| 5.15.12 | CRLF (Windows) | Windows 行尾 |

> **影响**: 对 qmake 构建无影响。但如果使用 `diff` 工具对比文件，可能因行尾差异导致误报。建议使用 `diff --strip-trailing-cr` 或归一化后比较。
>
> **注意**: macOS 的 `diff` 命令在处理 CRLF 文件时可能不显示实际内容差异（即使文件内容不同也返回 exit code 0）。建议使用 Python `difflib` 或先 `sed 's/\r$//'` 归一化后再比较。

---

## 14. 版本切换迁移指南

### 14.1 从 5.12.12 迁移到 5.15.12

#### 步骤 1: 更新 SDK

将 Qt SDK 替换为 5.15.12 (tqtc) 版本的编译产物。

#### 步骤 2: 更新 NAPI 构建引用

检查所有 `.pro` / `.pri` 文件中的 NAPI 引用:

```qmake
# 查找旧引用
rg -n 'node-addon-api\.pri|lace_napi\.z' --type qmake

# 替换为:
# 旧: LIBS += -lace_napi.z
# 旧: include($$PWD/.../node-addon-api.pri)
# 新: CONFIG += qnapi
```

#### 步骤 3: 处理 -Werror

5.15.12 默认将警告视为错误。如果代码有编译警告:

```qmake
# 方案 A: 修复所有警告（推荐）
# 方案 B: 在 .pro 中临时禁用
QMAKE_CXXFLAGS_WARN_ON += -Wno-error
QMAKE_CFLAGS_WARN_ON += -Wno-error
```

#### 步骤 4: 检查 qohosdeviceinfo 引用

如果代码直接引用了 `QtCore/private/qohosdeviceinfo_p.h`:

```cpp
// 5.12.12: 从 corelib 引用
#include <QtCore/private/qohosdeviceinfo_p.h>
// 函数有 Q_CORE_EXPORT 导出

// 5.15.12: 从 QPA 插件引用（路径变化，无导出宏）
// 需调整 include 路径
```

#### 步骤 5: 检查窗口能力

如果代码依赖 `WindowManagement` 能力始终返回 `true`:

```cpp
// 5.12.12: WindowManagement 始终返回 true
// 5.15.12: WindowManagement 返回 QOhosSettings::isWindowPcModeEnabled()
// 需确保 PC 模式已启用，或调整窗口管理逻辑
```

#### 步骤 6: 验证构建

```bash
# 使用 hvigorw 构建
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

### 14.2 从 5.15.12 迁移到 5.12.12

#### 步骤 1: 更新 SDK

将 Qt SDK 替换为 5.12.12 版本的编译产物。

#### 步骤 2: 回退 NAPI 构建引用

```qmake
# 查找新引用
rg -n 'CONFIG \+= qnapi' --type qmake

# 替换为:
# 新: CONFIG += qnapi
# 旧: LIBS += -lace_napi.z
#     include($$PWD/.../node-addon-api.pri)
```

#### 步骤 3: 处理 qohosdeviceinfo

如果代码引用了 QPA 插件中的 `qohosdeviceinfo`:

```cpp
// 5.15.12: 从 QPA 插件引用（无导出宏）
// 5.12.12: 从 corelib 引用（有 Q_CORE_EXPORT 导出）
#include <QtCore/private/qohosdeviceinfo_p.h>
// 函数有 Q_CORE_EXPORT，可跨库调用
```

#### 步骤 4: 恢复 -Wno-error

```qmake
# 5.12.12 默认 -Wno-error，无需特殊处理
# 如果从 5.15.12 迁移了 -Werror 设置，需改回 -Wno-error
```

#### 步骤 5: 验证构建

同 14.1 步骤 6。

### 14.3 与社区版 (qtohextras) 的关系

本文档对比的两个版本均使用 **商业版** (`qtohosextras` / `QtOhosExtras`) 鸿蒙化代码。如果需要从 **社区版** (`qtohextras` / `QtOhExtras`) 迁移到商业版，请参考 `qt-community-to-official` skill 的 `docs/` 目录中的迁移文档。

社区版与商业版的主要差异（不在本文档范围内）:

| 维度 | 社区版 (qtohextras) | 商业版 (qtohosextras) |
|---|---|---|
| 模块名 | `QtOhExtras` | `QtOhosExtras` |
| qmake 引用 | `QT += ohextras` | `QT += ohosextras` |
| 命名空间 | `QtOh` | `QtOhosExtras` |
| 上下文类 | `QOhAppContext` | `QOhosAbilityContext` |
| 权限 API | 同步 (`checkPermission`) | 异步 (signal-slot) |
| 文件分享 | `QOhFileShare::shareFile()` | `QOhosAbilityContext::shareDataWithShareKit()` |
| 平台参数 | `-platform openharmony` | `-platform ohos` |

### 14.4 快速检查清单

迁移时使用以下检查清单确保不遗漏:

- [ ] NAPI 构建引用 (`CONFIG += qnapi` ↔ `include(node-addon-api.pri)` + `-lace_napi.z`)
- [ ] 警告级别 (`-Werror` ↔ `-Wno-error`)
- [ ] qohosdeviceinfo include 路径 (corelib ↔ QPA 插件)
- [ ] qohospointerstyle.h 是否被引用（5.15.12 已移除）
- [ ] 窗口管理能力依赖 (`isWindowPcModeEnabled()` 行为变化)
- [ ] 行尾格式 (LF ↔ CRLF)
- [ ] qtohosextras 公开 API（无需修改，两版本完全相同）
- [ ] 权限配置 module.json5（无需修改，两版本完全相同）
- [ ] DevEco 模板（无需修改，两版本完全相同）

---

## 附录 A: 差异文件完整清单

### A.1 内容不同的文件（OHOS 相关）

| # | 文件路径 | 差异类型 |
|---|---|---|
| 1 | `qtbase/src/plugins/platforms/ohos/ohos.pro` | NAPI 重构 + 文件迁移 |
| 2 | `qtbase/src/plugins/platforms/ohos/qohosplugincore.h` | 枚举重构 + 新方法 + 类型变更 |
| 3 | `qtbase/src/plugins/platforms/ohos/qohosplugincore.cpp` | 新 NAPI 模块 + API 变更 |
| 4 | `qtbase/src/plugins/platforms/ohos/qohosplatformintegration.h` | 新增成员变量 |
| 5 | `qtbase/src/plugins/platforms/ohos/qohosplatformintegration.cpp` | 设置缓存 + PC 模式 |
| 6 | `qtbase/src/plugins/platforms/ohos/qohosplatformtheme.cpp` | 文件图标渲染改进 |
| 7 | `qtbase/src/corelib/kernel/kernel.pri` | NAPI 重构 + qohosdeviceinfo 移除 |
| 8 | `qtbase/mkspecs/ohos-clang/qmake.conf` | 警告级别变更 |
| 9 | `qtbase/src/plugins/bearer/ohos/src/src.pro` | NAPI 重构 |
| 10 | `qtbase/src/plugins/printsupport/ohos/ohos.pro` | NAPI 重构 |
| 11 | `qtbase/src/platformsupport/fontdatabases/ohos/openharmony.pri` | NAPI 重构 |
| 12 | `qtbase/src/tools/openharmonydeployqt/openharmonydeployqt.pro` | 新增 DEFINES |
| 13 | `qtmultimedia/src/plugins/ohos/src/src.pro` | NAPI 重构 |
| 14 | `qtmultimedia/src/plugins/ohos-audio/src/src.pro` | NAPI 重构 |
| 15 | `qtmultimedia/src/plugins/ohos/src/camera/qohoscameracommon.cpp` | HEIC 格式 |
| 16 | `qtmultimedia/src/plugins/ohos/src/camera/qohosimagecommon.cpp` | 图像适配 |
| 17 | `qtmultimedia/src/plugins/ohos/src/mediaplayer/mediaplayer.pri` | pri 调整 |
| 18 | `qtmultimedia/src/plugins/ohos/src/mediaplayer/qohosavplayer.cpp` | 超分辨率错误码 |
| 19 | `qtmultimedia/src/plugins/ohos/src/mediaplayer/qohosvideorenderercontrol.cpp` | 渲染适配 |
| 20 | `qtsensors/src/plugins/sensors/ohos/ohos.pro` | NAPI 重构 |
| 21 | `qtsensors/src/plugins/sensors/ohos/ohossensorbackendbase.h` | min→lowest |
| 22 | `qtsensors/src/plugins/sensors/ohos/ohosmagnetometerbackend.cpp` | 适配 |
| 23 | `qtsensors/src/plugins/sensors/ohos/ohossensorsmanager.cpp` | 适配 |
| 24 | `qtsensors/src/plugins/sensors/ohos/ohossensorutils.cpp` | 适配 |
| 25 | `qtspeech/src/plugins/tts/ohos/ohos.pro` | NAPI 重构 |
| 26 | `qtspeech/src/plugins/tts/ohos/qtexttospeech_ohos.cpp` | QSet API + 风格 |
| 27 | `qtspeech/src/plugins/tts/ohos/corespeechkit/texttospeechproxy.cpp` | 适配 |
| 28 | `qtspeech/src/plugins/tts/ohos/qohosexpected_p.h` | 适配 |
| 29 | `qtwebview/src/plugins/ohos/ohos.pro` | NAPI 重构 |
| 30 | `qtwebview/src/plugins/ohos/qohoswebview.cpp` | 新增 userAgent stub |
| 31 | `qtlocation/src/plugins/position/ohos/ohos.pro` | NAPI 重构 |
| 32 | `qtlocation/src/plugins/geoservices/ohosmapkit/qpoicategoryohosmapkit.cpp` | POI 适配 |

### A.2 仅在 5.12.12 中存在的文件

| 文件路径 | 说明 |
|---|---|
| `qtbase/src/plugins/platforms/ohos/qohospointerstyle.h` | 指针样式枚举（5.15.12 已移除） |
| `qtbase/src/corelib/kernel/qohosdeviceinfo_p.h` | 设备信息头（5.15.12 迁至 QPA 插件） |
| `qtbase/src/corelib/kernel/qohosdeviceinfo.cpp` | 设备信息源（5.15.12 迁至 QPA 插件） |

### A.3 仅在 5.15.12 中存在的文件

| 文件路径 | 说明 |
|---|---|
| `qtbase/mkspecs/features/ohos/qnapi.prf` | NAPI 构建特性（新增） |
| `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo_p.h` | 设备信息头（从 corelib 迁入） |
| `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo.cpp` | 设备信息源（从 corelib 迁入） |

### A.4 完全相同的 OHOS 模块（无任何差异）

| 模块 | 文件数 | 说明 |
|---|---|---|
| qtohosextras | 41 | 公开 API 模块，完全相同 |
| 蓝牙 (bluetooth) | 17 | 蓝牙后端，完全相同 |
| 打印 (printsupport) | 11 | 打印支持，完全相同 |
| 样式 (styles) | 5 | 样式插件，完全相同 |
| 网络承载 (bearer) | 19 | 网络引擎，完全相同 |
| 字体数据库 (fontdb) | 3 | 字体数据库，完全相同 |
| 部署工具 (deploytool) | 4 | 部署工具，完全相同 |
| 串口 (serialport) | 7 | 串口后端，完全相同 |
| 地图服务 (ohosmapkit) | 30 | 地图服务（.pro 有 NAPI 变更，源码 1 文件有差异） |
| 无障碍 (accessibility) | 34 | 无障碍模块，完全相同 |
| ArkUI 集成 (qarkui) | 21 | ArkUI 交互层，完全相同 |
| 渲染层 (render) | 37 | 渲染与输入处理，完全相同 |

---

## 附录 B: qtohosextras API 速查表（两版本通用）

### B.1 应用上下文

```cpp
#include <QtOhosExtras/QOhosAbilityContext>

// 获取 Ability 上下文实例
auto ctx = QOhosAbilityContext::instance();

// 权限请求（异步信号槽）
QObject::connect(ctx, &QOhosAbilityContext::namedPermissionRequestResponseReceived,
    [](QString permName, AppPermissions::PermissionResult result) { /* ... */ });
ctx->requestPermissionFromUserIfNeeded("ohos.permission.CAMERA");

// 文件分享
auto record = QSharedPointer<ShareKit::QOhosSharedRecord>::create();
record->setTitle("title");
record->addImage(QUrl("file:///data/image.png"));
auto options = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();
QObject::connect(ctx.data(), &QOhosAbilityContext::shareKitCompleted,
    [](QByteArray, QSharedPointer<ShareKit::QOhosShareOperationResult> result) { /* ... */ });
ctx->shareDataWithShareKit({record}, options);
```

### B.2 Want 跨组件通信

```cpp
#include <QtOhosExtras/QOhosWant>
#include <QtOhosExtras/QOhosStartOptions>
#include <QtOhosExtras/QOhosStartRequest>

QOhosWant want;
want.setAction("ohos.want.action.viewData");
want.addEntity("entity.system.browsable");
want.setUri(QUrl("https://example.com"));
```

### B.3 窗口工具

```cpp
#include <QtOhosExtras/QOhosWindowUtils>

// 圆角窗口
QOhosWindowUtils::setWindowCornerRadius(window, 20.0);
// 隐私模式
QOhosWindowUtils::setWindowPrivacyMode(window, true);
// 保持屏幕常亮
QOhosWindowUtils::setWindowKeepScreenOn(window, true);
```

### B.4 主题

```cpp
#include <QtOhosExtras/QOhosPlatformIntegration>

// 设置深色主题
QOhosPlatformIntegration::setDarkThemeEnabled(true);
```

### B.5 剪贴板

```cpp
#include <QtOhosExtras/QOhosPasteboard>

QOhosPasteboard::setText("text to copy");
QString text = QOhosPasteboard::text();
```

### B.6 .pro 配置

```qmake
QT += ohosextras core gui widgets
CONFIG += ohos
```

---

*本文档基于逐文件 Python difflib 归一化对比生成，已排除 CRLF/LF 行尾差异和构建产物干扰。*
