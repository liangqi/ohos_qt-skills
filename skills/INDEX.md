# Skills Index

本文件列出所有可用的 Qt 鸿蒙开发 Skills。

## 核心 Skills

### create-qt-app

**名称**: `create-qt-app`

**描述**: 生成 Qt 鸿蒙应用工程结构（QWidget 或 QML）。只负责创建工程目录、源码文件、CMake 配置模板，不负责编译和 SDK 配置。

**位置**: `skills/create-qt-app/SKILL.md`

**功能**:
- 创建 Qt 鸿蒙工程目录结构
- 生成 QWidget 或 QML 应用源码
- 配置 CMake 构建模板
- 配置胶水代码（QtAppConstants.ets）

**使用示例**:
```
帮我生成一个俄罗斯方块的 demo 工程，使用 QML。
工程目录放到：C:\Users\lzh\Documents\TetrisDemo
模板胶水代码路径：C:\Users\lzh\Downloads\ohostemplateforqtapplication.zip
```

**关键配置点**:
1. 应用类型（QWidget / QML）
2. 工程目录路径
3. 胶水代码模板来源

**后续步骤**（开发者完成）:
- 在 DevEco Studio 中配置 Qt SDK 路径
- 配置鸿蒙 SDK 路径
- 部署 Qt 运行时库（核心库 + QML 插件）
- 签名配置
- 构建运行

---

## 规划中的 Skills

以下 Skills 正在开发或计划开发中：

| Skill | 描述 | 状态 |
|-------|------|------|
| deploy-qt-runtime | 自动部署 Qt 运行时库到 libs 目录 | 🚧 计划中 |
| qt-harmonyos-debug | Qt 鸿蒙应用调试辅助 | 🚧 计划中 |
| convert-qt-project | 将现有 Qt 项目转换为鸿蒙版本 | 🚧 计划中 |

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