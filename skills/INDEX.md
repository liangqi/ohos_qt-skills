# Skills Index

本文件列出所有可用的 Qt 鸿蒙开发 Skills。

## 核心 Skills

### create-qt-app

**名称**: `create-qt-app`

**描述**: 生成 Qt 鸿蒙应用工程结构（QWidget 或 QML），或将已有 Qt 工程鸿蒙化。支持从零创建新工程和已有工程鸿蒙化两种场景。

**位置**: `skills/create-qt-app/SKILL.md`

**功能**:
- **场景一：从零创建新工程**
  - 创建 Qt 鸿蒙工程目录结构
  - 生成 QWidget 或 QML 应用源码
  - 配置 CMake 构建模板
  - 配置胶水代码（QtAppConstants.ets）
- **场景二：已有 Qt 工程鸿蒙化**
  - 在已有工程根目录放置胶水代码
  - 配置 build-profile.json5 指向已有工程的构建文件
  - 支持 CMake/qmake/其他工程类型

**使用示例**:
```
场景一（从零创建）：
帮我生成一个俄罗斯方块的 demo 工程，使用 QML。
工程目录放到：C:\Users\lzh\Documents\TetrisDemo
模板胶水代码路径：C:\Users\lzh\Downloads\ohostemplateforqtapplication.zip

场景二（已有工程鸿蒙化）：
帮我将已有的 Qt CMake 工程转换为鸿蒙应用。
工程目录：C:\code\MyQtApp
胶水代码模板：下载最新模板
```

**关键配置点**:
1. 使用场景（从零创建 / 已有工程鸿蒙化）
2. 应用类型或已有工程类型
3. 工程目录路径
4. 胶水代码模板来源

**后续步骤**（开发者完成）:
- 在 DevEco Studio 中配置 Qt SDK 路径
- 配置鸿蒙 SDK 路径
- 部署 Qt 运行时库（核心库 + QML 插件）
- 签名配置
- 构建运行

---

### build-run-qt-app

**名称**: `build-run-qt-app`

**描述**: 使用 DevEco MCP 工具链编译、运行 Qt 鸿蒙应用并查看日志。支持项目构建、应用启动、日志获取、UI 操作等功能。

**位置**: `skills/build-run-qt-app/SKILL.md`

**功能**:
- 项目构建（build_project）
- 应用启动（start_app）
- 日志获取（get_hilog_or_faultlog_recent）
- UI 树获取（get_app_ui_tree）
- UI 操作（perform_ui_action）
- 项目同步（project_sync）

**前置条件**:
- 安装配置 DevEco MCP 工具链
- DevEco Studio 已正确安装
- Qt 工程的 CMake 配置正确

**使用示例**:
```
帮我编译运行 Qt 鸿蒙应用：
工程目录：C:\code\MyQtApp
构建模式：debug
查看日志级别：Info
```

**核心流程**:
1. 项目同步（可选）
2. 项目构建
3. 启动应用
4. 查看日志
5. UI 测试（可选）

---

## 扩展 Skills

以下 Skills 用于集成鸿蒙系统 API 到 Qt 鸿蒙应用，需配合 AKI 桥接框架使用。

### aki-bridge-generator

**名称**: `aki-bridge-generator`

**描述**: 使用 AKI（Application Kit Interface）框架为 Qt 鸿蒙应用生成 C++↔ArkTS 桥接代码。基于实战经验，强调 SafetyCallback 跨线程同步调用、JSBIND_GLOBAL 全局函数模式（适配 Qt Q_OBJECT 单例）、SafetyCallback 指针成员管理、TaskRunner 初始化、windowId 传递、AKI 类型声明等关键实践。

**位置**: `skills/aki-bridge-generator/SKILL.md`

**功能**:
- **桥接方向确认** — C++→ArkTS / ArkTS→C++ / 双向桥接
- **接口设计** — Qt Q_OBJECT 单例 Bridge 类 + SafetyCallback 指针成员 + JSBIND_GLOBAL 全局函数模式
- **生成 C++ 桥接代码** — Bridge 类实现（SafetyCallback setter delete+new 模式）、QMetaObject 线程转发
- **生成 AKI JSBinding** — JSBIND_GLOBAL + JSBIND_FUNCTION 声明、JSBIND_ADDON 注册、CMakeLists.txt 配置
- **生成 ArkTS 调用代码** — import 方式、SafetyCallback 回调注册、init() 初始化、TaskRunner 创建
- **配置类型声明** — index.d.ts + oh-package.json5 + entry devDependencies（7 层一致性检查）

**核心概念**:
- SafetyCallback vs std::function（跨线程安全：SafetyCallback 使用 napi_threadsafe_function + std::promise/future）
- JSBIND_GLOBAL vs JSBIND_CLASS（Qt Q_OBJECT 单例必须用 JSBIND_GLOBAL，避免实例冲突）
- SafetyCallback 指针成员管理（nullptr 初始化 / delete 析构 / delete+new setter）
- 线程安全模型（C++ Qt主线程 ↔ SafetyCallback ↔ ArkTS JS线程，JS→C→QtMainThread 必须通过消息队列）

**使用示例**:
```
帮我为 Qt 鸿蒙应用生成 AKI 桥接代码，需要调用鸿蒙 NFC API。
桥接方向：C++ → ArkTS（双向）
需桥接的接口：
  - NfcBridge::startNfcDiscovery()
  - NfcBridge::stopNfcDiscovery()
  - NfcBridge::onNfcTagDetected(tagInfo)
工程目录：C:\code\NfcApp
```

**关键配置点**:
1. 桥接方向（C++→ArkTS / ArkTS→C++ / 双向）
2. 需桥接的 C++ 接口签名列表
3. 工程目录路径（桥接代码放在 entry/src/main/cpp/）
4. Bridge 类是否为 Qt Q_OBJECT 单例（决定 JSBIND_GLOBAL vs JSBIND_CLASS）
5. AKI 源码集成方式（add_subdirectory）

**前置条件**:
- Qt 鸿蒙工程已创建（使用 `create-qt-app` skill）
- AKI 框架源码已获取（https://gitcode.com/CPF-ApplicationTPC/aki）

**核心流程**:
1. 确认桥接方向与接口列表
2. 设计桥接接口（Bridge 类 + SafetyCallback 指针成员）
3. 生成 C++ 桥接代码（share_bridge.h/cpp）
4. 生成 AKI JSBinding（share_aki_binding.cpp）
5. 生成 ArkTS 调用代码（ShareBridgeProxy.ets）
6. 配置 AKI 类型声明（index.d.ts + oh-package.json5）

---

### hmos-share-integration

**名称**: `hmos-share-integration`

**描述**: 集成鸿蒙碰一碰分享和手势分享（隔空传送）功能到 Qt 鸿蒙应用。通过 AKI 框架将 harmonyShare（华为分享）API 桥接到 Qt C++ 层，实现碰一碰/手势分享文件分享、链接分享、沙箱接收（dataReceive）。所有代码基于实际开发验证（knocksharedemo）。

**位置**: `skills/hmos-share-integration/SKILL.md`

**功能**:
- **碰一碰/手势分享发送端**
  - 注册 knockShare/gesturesShare 监听（需 windowId）
  - SharableTarget.share() 文件分享（utd + uri）
  - SharableTarget.share() 链接分享（HYPERLINK utd + content）
  - SharableTarget.reject() 拒绝分享
  - SharableTarget.updateShareData() 更新预览图
- **沙箱接收端（dataReceive）**
  - 注册 dataReceive 监听（RecvCapabilityRegistry + windowId）
  - ReceivableTarget.receive() 接收数据流程
  - 取消监听 off('dataReceive')（必须传入 RecvCapabilityRegistry）
- **AKI 桥接集成** — ShareBridge C++ 桥接类 + JSBinding + ShareBridgeProxy.ets

**关键教训**（开发踩坑总结）:
1. RecvCapabilityRegistry 类型（NOT ReceivableTargetConfig）— capabilities 必填，maxSupportedCount 必须 > 0
2. ReceivableTarget 回调流程（NOT SharableData）— 必须调用 receive() 才能接收数据
3. off('dataReceive') 必须传入 RecvCapabilityRegistry 参数
4. windowId 必须从 Qt 侧获取（QtOhosExtras::tryGetNativeWindowId），不能从 ArkTS 侧获取
5. @kit.ShareKit 是系统 Kit，绝不能在 oh-package.json5 dependencies 中声明
6. JSON5 文件必须为合法标准 JSON（禁止尾部逗号、单引号、注释）
7. modules.xml 必须注册 entry.iml 和 qEmbeddedUiExtensionHost.iml
8. receiveDir 使用 context.filesDir，在 QAbility.onCreate 设置
9. targetSdkVersion = 6.0.0(20) 硬约束
10. 设备类型限制：API≤22 仅 PC/2in1，≥23 支持 tablet

**使用示例**:
```
帮我把碰一碰分享功能集成到 Qt 鸿蒙应用中。
分享角色：发送端 + 接收端
分享类型：文件分享 + 链接分享
Qt UI 类型：QWidget
目标设备：tablet + 2in1
工程目录：C:\code\ShareDemo
```

**关键配置点**:
1. 分享角色（发送端 / 接收端 / 两者都要）
2. 分享类型（文件分享 / 链接分享 / 手势分享）
3. Qt UI 类型（QWidget / QML）
4. 目标设备类型（tablet+2in1 / phone）
5. 工程目录路径

**前置条件**:
- Qt 鸿蒙工程已创建（使用 `create-qt-app` skill）
- AKI 框架已集成到项目（使用 `aki-bridge-generator` skill）
- DevEco MCP 工具链已配置（用于构建和测试）

**核心流程**:
1. 确认需求与场景（分享角色、类型、设备）
2. 设计桥接方案（API 路径设计、数据流设计）
3. 创建 ArkTS 侧代码（ShareBridgeProxy.ets + QAbility.ets）
4. 创建 AKI JSBinding 声明（share_bridge.h/cpp + share_aki_binding.cpp）
5. Qt 侧集成（windowId 获取、回调注册、消息队列转发）
6. 配置权限与依赖（module.json5、oh-package.json5、modules.xml、CMakeLists.txt）

---

## 规划中的 Skills

以下 Skills 正在开发或计划开发中：

| Skill | 描述 | 状态 |
|-------|------|------|
| deploy-qt-runtime | 自动部署 Qt 运行时库到 libs 目录 | 🚧 计划中 |
| qt-harmonyos-debug | Qt 鸿蒙应用调试辅助 | 🚧 计划中 |

---

## Skill 文档格式

每个 Skill 目录应包含以下文件：

```
skills/<skill-name>/
├── SKILL.md          # 主文档（必需）
├── references/       # 参考文档（可选）
│   └── api.md        # API 参考
│   └── guide.md      # 使用指南
├── templates/        # 模板文件（可选）
│   └── cmake.txt     # CMake 模板
│   └── main.qml      # QML 模板
└── scripts/          # 脚本文件（可选）
    └── deploy.sh     # 部署脚本
```

### SKILL.md 格式

```markdown
---
name: skill-name
description: Skill 简短描述
---

# Skill 标题

## 功能说明

详细描述 Skill 的功能...

## 前置确认

使用 clarify 工具确认参数...

## 核心流程

1. Step 1
2. Step 2
...

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| ... | ... |

## 关键约束

**禁止**: ...
**必须**: ...
```