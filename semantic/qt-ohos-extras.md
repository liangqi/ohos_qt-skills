---
id: semantic-qt-ohos-extras
type: semantic
domain: tech
tags: [qt, harmonyos, ohos, ohosextras, ability, want, startability]
created: 2026-06-02
updated: 2026-06-02
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-api, semantic-qt-ohos-js-thread-gateway]
summary: >
  QtOhosExtras 模块：Qt 与鸿蒙系统交互的桥梁。提供 startAbility()、
  startNewAbilityInstance()、startAppProcess()、startNoUiChildProcess()、
  QOhosWant、tryGetNativeWindowId() 等鸿蒙专有 API。使用方式：QT += ohosextras。
---

# QtOhosExtras 模块

## 概述

QtOhosExtras 是 Qt for HarmonyOS 的专有扩展模块，提供与鸿蒙系统交互的 API。

## 使用方式

```cpp
// 头文件
#include <QtOhosExtras>

// 项目文件 (.pro)
QT += ohosextras
```

## 核心 API

### 启动 Ability / 进程

| 函数 | 用途 |
|------|------|
| `startAbility()` | 启动指定 Ability |
| `startNewAbilityInstance()` | 启动新 Ability 实例 |
| `startAppProcess()` | 启动应用进程 |

### 子进程管理

| 函数 | 用途 |
|------|------|
| `QOhosAppContext::startNoUiChildProcess()` | 启动无 UI 后台子进程 |
| `QOhosAppContext::isNoUiChildMode()` | 检测当前是否处于无 UI 子进程模式 |

### 窗口相关

| 函数 | 用途 |
|------|------|
| `tryGetNativeWindowId(QWindow *)` | 获取 ArkTS 侧 WindowProperties.id（注意：不保证生命周期内有效） |
| `setMainWindowGeometryPersistenceHint()` | 设置主窗口几何持久化提示（仅 2in1 设备） |

### Want 相关

| 类 | 用途 |
|----|------|
| `QOhosWant` | 封装鸿蒙 Want，用于跨 Ability 通信 |

## API 参考

- [C++ Classes and Namespaces](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc/Qt_Ohos_Extras_C%2B%2B_Classes)
- [Examples](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc/Qt_Ohos_Extras_Examples)

## 参考来源

- [Qt OHOS Extras Document](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc)
