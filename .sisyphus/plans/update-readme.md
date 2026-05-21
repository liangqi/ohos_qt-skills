# 计划：更新 README.md

## 目标

修改 `/Users/yu/business_qt/skills_program/ohos_qt-skills/README.md`，说明三个 skill 的关系和主要功能。

## 关系说明

qt-ohos-project-analyzer 是总开关，编排整个流程，调用另外两个子 skill：
- 需要创建工程时 → 调用 create-qt-app
- 需要编译运行时 → 调用 build-run-qt-app

## 各 Skill 主要功能（精简版）

### qt-ohos-project-analyzer（总开关 / 鸿蒙化项目分析器）

1. 铁律定义 — 所有 skill 共享的流程纪律
2. 需求沟通 + MCP 工具链就绪检查
3. Qt/OHOS 前置环境确认 → 生成 `qt_env.md`
4. 依赖梳理（Qt 版本、模块、三方库、构建系统）
5. 编排编译流程：调用 create-qt-app → 调用 build-run-qt-app → 双重交验确认 → 总结文档输出

### create-qt-app（工程生成）

1. 场景一：从零创建新工程（下载模板 → 放源码 → 配置 CMake → 复制样式库 → 配置胶水代码）
2. 场景二：已有 Qt 工程鸿蒙化（在工程根目录创建 HarmonyOS/ 子目录放胶水代码）

### build-run-qt-app（编译运行）

1. DevEco MCP 工具链安装配置
2. 项目同步 + 构建
3. 应用启动 + 日志查看（hilog/faultlog）
4. UI 树获取 + UI 操作（可选）

## 执行内容

将 README.md 的全文替换为以下内容：

```markdown
# OHOS Qt Skills

Qt for HarmonyOS 开发的 AI Agent Skills 集合——帮助开发者将 Qt 项目编译、运行到鸿蒙系统上。

## 三个 Skill 的关系

**`qt-ohos-project-analyzer` 是总开关**，编排整个鸿蒙化编译流程，在需要时调用另外两个子 skill：

```
qt-ohos-project-analyzer（总开关 / 鸿蒙化项目分析）
  ├── 调用 → create-qt-app（工程生成）
  └── 调用 → build-run-qt-app（编译运行）
```

子 skill 也可以独立使用，但在总开关编排下会进入**快速模式**（跳过重复确认、共享环境信息）。

---

## 各 Skill 主要功能

### qt-ohos-project-analyzer — 总开关 / 鸿蒙化项目分析器

1. **铁律定义** — 所有 skill 共享的流程纪律（禁止推测、知识库优先、修复必须沉淀等）
2. **MCP 工具链就绪检查** — 阻断性前置条件，未安装则暂停引导安装
3. **Qt/OHOS 前置环境确认** — 确认分支源码路径、编译产物路径、胶水模版 → 生成 `qt_env.md`
4. **依赖梳理** — Qt 版本兼容性评估、模块依赖、三方库、构建系统
5. **编排编译** — 调用 create-qt-app 创建工程 → 调用 build-run-qt-app 编译运行 → 双重交验确认 → 输出总结文档

### create-qt-app — 工程生成

1. **从零创建新工程** — 下载模板 → 放 Qt 源码（QWidget/QML）→ 配置 CMake → 复制样式库 → 配置胶水代码
2. **已有 Qt 工程鸿蒙化** — 在工程根目录创建 `HarmonyOS/` 子目录放胶水代码，不干扰原有结构

### build-run-qt-app — 编译运行

1. **DevEco MCP 安装配置** — 覆盖 Trae、Cursor、VS Code 等多种 IDE
2. **项目构建** — 调用 build_project，含构建失败排查流程（知识库优先 → 错误分类 → 修复沉淀）
3. **应用启动 + 日志查看** — 调用 start_app + get_hilog_or_faultlog_recent
4. **UI 测试**（可选）— UI 树获取 + UI 操作（点击/滑动/输入/截图）

---

## 目录结构

```
ohos_qt-skills/
├── skills/
│   ├── qt-ohos-project-analyzer/  # 总开关 / 鸿蒙化项目分析器
│   ├── create-qt-app/        # 工程生成
│   └── build-run-qt-app/     # 编译运行
│   └── INDEX.md
├── docs/
│   └── qt-harmonyos-setup.md
└── LICENSE
```

## Skills 列表

| Skill | 角色 | 主要功能 | 状态 |
|-------|------|---------|------|
| [qt-ohos-project-analyzer](skills/qt-ohos-project-analyzer/SKILL.md) | **总开关** | 鸿蒙化项目分析：铁律 + 环境确认 + 依赖梳理 + 编排编译流程 + 验证交付 | ✅ |
| [create-qt-app](skills/create-qt-app/SKILL.md) | 子 skill | 从零创建 / 已有工程鸿蒙化，生成工程结构和配置 | ✅ |
| [build-run-qt-app](skills/build-run-qt-app/SKILL.md) | 子 skill | 编译、启动、日志查看、UI 测试 | ✅ |

## 如何使用

**通过总开关（推荐）**：直接调用 qt-ohos-project-analyzer，它自动编排调用子 skill。

**单独使用子 skill**：工程已就绪时只用 build-run-qt-app 编译运行；只需创建工程时只用 create-qt-app。

### 安装

```bash
cp -r skills/* <agent-config-dir>/skills/
```

> 三个 skill 都需安装，子 skill 会被总开关调用。

## 相关链接

- [Qt for HarmonyOS 官方文档](https://wiki.qt.io/Qt_for_HarmonyOS)
- [DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/)
- [DevEco Toolbox](https://github.com/open-deveco/deveco-toolbox)

## 许可证

Apache 2.0，详见 [LICENSE](LICENSE)。
```

## 执行方式

委托一个 quick category agent 执行：读取当前 README.md，用上述内容替换全文。