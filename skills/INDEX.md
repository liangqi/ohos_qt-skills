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