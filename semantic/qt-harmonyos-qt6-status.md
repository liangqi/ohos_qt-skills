---
id: semantic-qt-harmonyos-qt6-status
type: semantic
domain: tech
tags: [qt, qt6, harmonyos, ohos, status, cmake]
created: 2026-06-03
updated: 2026-06-03
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-build, semantic-qt-harmonyos-modules, semantic-qt-harmonyos-platform-limits, semantic-qt-ohos-project-analyzer-workflow]
summary: >
  Qt 6 鸿蒙化状态：qtbase dev 已合并 HarmonyOS 支持（Gerrit 733351），
  最低 SDK API 20（HarmonyOS 6.0.0），CMake 构建系统。
  从 Qt6 源码验证：QStandardPaths 映射（4 枚举已确认）、QPA 插件 API 变更
  （关闭事件私有化、枚举值改变）、QtOhosExtras 功能内联到 QPA 插件。
  Qt5→Qt6 关键差异（QStandardPaths、CMake API、QML、QPA API）。
---

# Qt 6 for HarmonyOS 状态

> **一句话**：Qt 6 鸿蒙化已在 qtbase dev 主干分支落地，当前处于早期阶段（仅 qtbase），其余模块尚未适配。

## 当前状态

| 项目 | 内容 |
|------|------|
| **合并状态** | ✅ Gerrit change [733351](https://codereview.qt-project.org/c/qt/qtbase/+/733351) 已合并到 qtbase dev |
| **最低 SDK** | HarmonyOS SDK **API 20**（HarmonyOS 6.0.0） |
| **目标架构** | arm64-v8a |
| **已完成模块** | 仅 **qtbase**（QtCore、QtGui、QtWidgets、QtNetwork、QtQml、QtQuick 等基础模块） |
| **未开始模块** | Qt Multimedia、Qt 3D、Qt Charts 等非 qtbase 模块尚无鸿蒙适配计划 |
| **构建系统** | **CMake**（Qt 6 全面使用 CMake，不再使用 qmake/configure） |

## 源码获取

```bash
# Qt 6 主干（dev 分支）
# 本地路径：<LOCAL_PATH>
git clone https://code.qt.io/qt/qtbase.git
cd qtbase
# dev 分支已包含 HarmonyOS 支持
```

## 构建方式

Qt 6 构建与 Qt 5 有根本性差异：

| 维度 | Qt 5 for OHOS | Qt 6 for OHOS |
|------|---------------|---------------|
| 构建系统 | `configure` + `make` | **CMake** |
| 编译命令 | `../configure -xplatform ohos-clang ...` | `cmake -GNinja -DQT_HOST_PATH=... -DCMAKE_TOOLCHAIN_FILE=...` |
| 模块管理 | qmake `.pro` 文件 | CMake `qt_add_executable` / `qt_add_qml_modules` |
| QML 导入 | `import QtQuick 2.x` | `import QtQuick`（无版本号） |
| C++ 标准 | C++14 | **C++17**（最低要求） |

详细构建步骤：参见 [Building Qt6 for HarmonyOS](https://wiki.qt.io/Building_Qt6_for_HarmonyOS)

## Qt 5 vs Qt 6 关键差异（鸿蒙化相关）

### QStandardPaths 新枚举

Qt 6 新增了若干 `QStandardPaths::StandardLocation` 枚举值，以下映射已从 Qt6 qtbase 源码（`qstandardpaths_ohos.cpp`）验证：

| Qt 6 枚举 | OHOS 映射 | Qt 5 状态 |
|-----------|----------|-----------|
| `PublicShareLocation` | ❌ **NOT SUPPORTED**（返回空字符串） | ❌ 不存在 |
| `TemplatesLocation` | ❌ **NOT SUPPORTED**（返回空字符串） | ❌ 不存在 |
| `StateLocation` | ✅ 映射到 `filesDir` | ❌ 不存在 |
| `GenericStateLocation` | ✅ 映射到 `filesDir` | ❌ 不存在 |

> ⚠️ **行为变更**：`AppLocalDataLocation` 在 Qt 5 for OHOS 上映射到 `filesDir`，但在 Qt 6 中映射到 **`preferencesDir`**。迁移时需注意路径差异。

### CMake API 变更

| Qt 5 | Qt 6 | 说明 |
|------|------|------|
| `find_package(Qt5 ...)` | `find_package(Qt6 ...)` | 包名变更 |
| `qt5_add_resources()` | `qt_add_resources()` | 去掉版本号前缀 |
| 无 | `qt_add_qml_modules()` | Qt 6 QML 模块声明 |
| `add_executable()` | `qt_add_executable()` | Qt 6 推荐使用 |

### QML 变更

| Qt 5 | Qt 6 | 说明 |
|------|------|------|
| `import QtQuick 2.15` | `import QtQuick` | 无版本号导入 |
| `import QtQuick.Controls 2.15` | `import QtQuick.Controls` | 同上 |
| `QtQuick.Controls` 模块在 OHOS SDK 中缺失 | ✅ 已确认：不在 qtbase 中，属于独立模块（qtdeclarative/qtquickcontrols2），需单独适配 |

### 其他变更

| 变更 | 影响 |
|------|------|
| `QFuture::then()` / `QPromise` | Qt 6 新增并发 API，Qt 5 需用 `QtConcurrent::run()` 替代 |
| `core5compat` 模块 | Qt 6 提供的 Qt 5 兼容层，部分 API 可通过此模块过渡 |
| 构建产物路径 | Qt 6 CMake 输出路径可能与 Qt 5 不同，影响 `QtAppConstants.ets` 中的 `APP_LIBRARY_NAME` |

### QPA 插件 API 变更（从源码验证）

Qt 6 将原 QtOhosExtras 模块的大部分功能**内联到了 QPA 插件中**（`src/plugins/platforms/ohos/`，196 个文件）。以下是关键 API 差异：

#### 关闭事件 API — 重大变更

| 维度 | Qt 5（QtOhosExtras） | Qt 6（QPA 内部） |
|------|---------------------|-----------------|
| 枚举名 | `CloseEventRootCause` | `CloseRootCause`（**private** `_p.h`） |
| `InternalClose` | ✅ 存在 | ❌ 移除（替换为 `NotSpecified`） |
| `AbilityClose` | ✅ 存在 | ⚠️ 更名为 `OnPrepareToTerminate` |
| `WindowStageClose` | ✅ 存在 | ✅ 存在（同名） |
| `SubWindowClose` | ❌ 不存在 | ✅ **新增** |
| 获取函数 | `getCloseEventRootCause(QCloseEvent*)` 公开 API | `getCloseRootCauseForEventOrDefault(QEvent*)` **私有 API** |

> ⚠️ **关键差异**：Qt 6 的关闭事件 API 目前是**私有内部 API**（`_p.h` 头文件），尚无公开接口。这意味着 Qt 5 中使用 `QtOhosExtras::getCloseEventRootCause()` 的代码在 Qt 6 中**无法直接迁移**，需要等待公开 API 或通过 QtOhosExtras Qt 6 版本提供。

#### 窗口标记 API — 保持一致

| API | Qt 5 | Qt 6 |
|-----|------|------|
| `tagWindowOrWidgetAsSubWindowOf` | `QOhosFunctions` (public) | `QPlatformNativeInterface` (internal) ✅ |
| `tagWindowOrWidgetAsMainWindow` | `QOhosFunctions` (public) | `QPlatformNativeInterface` (internal) ✅ |
| `tagWindowOrWidgetAsFloatWindow` | `QOhosFunctions` (public) | `QOhosQpaFunctions` (internal) ✅ |

> 函数签名一致，但 Qt 6 中通过 `QPlatformNativeInterface` 访问而非公开的 `QOhosFunctions` 类。公开 API 取决于 QtOhosExtras 的 Qt 6 版本。

#### ShareKit API — 接口变更

| 维度 | Qt 5 | Qt 6 |
|------|------|------|
| 命名空间 | `QtOhosExtras::ShareKit` | `QOhosShareKit`（内部） |
| 分享函数 | `shareDataWithShareKit()` | `shareDataUsingShareKit()` |
| 记录类型 | `QOhosSharedRecord` | `ShareKit::SharedRecord` |

## 模块适配状态

Qt 6 模块适配状态**独立于 Qt 5**，当前仅 qtbase 模块已合并。

| 模块分类 | Qt 5 状态 | Qt 6 状态 |
|---------|----------|----------|
| **qtbase**（Core/Gui/Widgets/Network/Qml/Quick） | ✅ Completed | ✅ 已合并到 dev |
| **qtbase**（Test/Sql/Concurrent/OpenGL） | ✅ Completed | ✅ 已验证：Test 有 OHOS hilog 集成，Sql/Concurrent/OpenGL 无需 OHOS 特定代码 |
| **非 qtbase**（Multimedia/3D/Charts/...） | ✅/❌ 见 [[qt-harmonyos-modules]] | ❌ 未开始 |
| **QtOhosExtras** | ✅ Completed | ❌ **不作为独立模块存在** — 功能已分散到 `corelib/platform/ohos/`（QOhosAppContext）和 `plugins/platforms/ohos/`（startAppProcess、ShareKit、窗口标记等），所有 API 均为**私有内部**（`_p.h` 头文件） |

详细 Qt 6 模块状态：参见 [Qt for HarmonyOS Module Adaptation Status](https://wiki.qt.io/Qt_for_HarmonyOS)（wiki 页面中 Qt6 部分）

## Qt 6 项目适配策略

当前 Qt for HarmonyOS 的主力分支仍是 **Qt 5.12.12 / 5.15.16**。如果收到 Qt 6 项目的鸿蒙化需求，有两种策略：

### 策略 A：降级到 Qt 5（推荐，当前可行）

详见 [[qt-ohos-project-analyzer-workflow]] §Qt6 项目 → Qt5 兼容性评估：
1. 检测源码中的 Qt 6 独有特性
2. 查找项目的 Qt 5 兼容分支或 tag
3. 使用 `QT_VERSION_CHECK` 宏做条件编译

### 策略 B：使用 Qt 6 dev 分支（前沿，风险较高）

1. 基于 qtbase dev 分支编译 Qt 6 for OHOS
2. 仅 qtbase 模块可用，非 qtbase 模块需等待适配
3. 需要处理上述 Qt 5→6 API 差异

## 已知问题与待验证项

| # | 项目 | 状态 |
|---|------|------|
| 1 | Qt 6 QStandardPaths 新枚举在 OHOS 上的映射 | ✅ 已验证：`PublicShareLocation`/`TemplatesLocation` 不支持，`StateLocation`/`GenericStateLocation` → `filesDir` |
| 2 | QtOhosExtras 模块是否有 Qt 6 版本 | ✅ 已验证：**不作为独立模块存在**。功能分散到 `corelib/platform/ohos/`（QOhosAppContext）和 `plugins/platforms/ohos/`（QPA 内部），所有 API 为私有（`_p.h`） |
| 3 | Qt 6 QPA 插件（qohos）与 Qt 5 的功能差异 | ✅ 已验证：196 文件，关闭事件 API 重大变更（私有化 + 枚举值改变），窗口标记 API 签名一致 |
| 4 | 非 qtbase 模块的鸿蒙适配时间表 | ❓ 待确认（本地仅有 qtbase 源码，无其他模块仓库；QtQuick.Controls 不在 qtbase 中） |
| 5 | Qt 6 的 `qt_add_qml_modules` 在 OHOS 交叉编译中的行为 | 🟡 部分验证：qtbase cmake 中仅在 `QtInitProject.cmake`（项目模板）中出现，实际实现在 `qtdeclarative` 仓库中（本地无源码）。OHOS 特定行为无法从 qtbase 源码验证 |
| 6 | Qt 6 最低 SDK API Level 是否仍为 20 | ✅ 已更新：Qt5 wiki 记载 API 20；Qt6 源码无硬编码最低 API；本地 SDK 为 **API 24**（HarmonyOS 6.1.1 Beta1） |
| 7 | `AppLocalDataLocation` 映射变更 | ✅ 已验证：Qt5 `filesDir` → Qt6 `preferencesDir`（破坏性变更） |
| 8 | 关闭事件公开 API 缺失 | ✅ 已验证：Qt6 `CloseRootCause` 为私有 API，无公开 `getCloseEventRootCause()` |
| 9 | qtbase Test/Sql/Concurrent/OpenGL 模块在 OHOS 上的状态 | ✅ 已验证：Test 有 OHOS hilog 集成（`qOhosLogMessage`），Sql/Concurrent/OpenGL 无需 OHOS 特定代码 |

## 参考来源

- [Building Qt6 for HarmonyOS](https://wiki.qt.io/Building_Qt6_for_HarmonyOS) — Qt 6 构建指南
- [Qt for HarmonyOS](https://wiki.qt.io/Qt_for_HarmonyOS) — 主页（含 Qt5/Qt6 模块适配状态）
- [Building Qt for HarmonyOS (Qt5)](https://wiki.qt.io/Building_Qt_for_HarmonyOS) — Qt 5 构建指南（对比参考）
- [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations) — 平台限制（Qt5/Qt6 共用）
- [Long live Qt for HarmonyOS! (Reddit)](https://www.reddit.com/r/QtFramework/comments/1te37o5/long_live_qt_for_harmonyos/) — Gerrit 733351 合并公告
- [Qt 6 Build System (Qt Blog)](https://www.qt.io/blog/qt-6-build-system) — Qt 6 CMake 构建系统介绍
- **Qt 6 qtbase 源码**（本地验证）：
  - `<LOCAL_PATH>` — QStandardPaths OHOS 映射
  - `<LOCAL_PATH>` — 关闭事件 API（私有）
  - `<LOCAL_PATH>` — 窗口标记 API
  - `<LOCAL_PATH>` — QPA 函数（ShareKit/FloatWindow）
