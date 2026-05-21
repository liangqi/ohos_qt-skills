# OHOS Qt Skills

Qt for HarmonyOS 开发的 AI Agent Skills 集合——帮助开发者将 Qt 项目编译、运行到鸿蒙系统上。

## 三个 Skill 的关系

**`compile-qt-tool` 是总开关**，编排整个鸿蒙化编译流程，在需要时调用另外两个子 skill：

````
compile-qt-tool（总开关）
  ├── 调用 → create-qt-app（工程生成）
  └── 调用 → build-run-qt-app（编译运行）
````

子 skill 也可以独立使用，但在总开关编排下会进入**快速模式**（跳过重复确认、共享环境信息）。

---

## 各 Skill 主要功能

### compile-qt-tool — 总开关 / 编排器

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
├── README.md                   # 项目说明
├── skills/                     # Skills 目录
│   ├── compile_qt_tool/        # 总开关 / 编排器
│   │   └── SKILL.md            # Skill 主文档
│   ├── create-qt-app/          # 创建 Qt 鸿蒙应用
│   │   └── SKILL.md            # Skill 主文档
│   │   ├── references/         # 参考文档
│   │   ├── templates/          # 模板文件
│   │   └── scripts/            # 脚本文件
│   ├── build-run-qt-app/       # 编译运行 Qt 鸿蒙应用
│   │   └── SKILL.md            # Skill 主文档
│   └── INDEX.md                # Skills 索引
├── docs/                       # 额外文档
│   └── qt-harmonyos-setup.md   # Qt 鸿蒙环境配置指南
└── LICENSE                     # 许可证文件
```

## Skills 列表

| Skill | 角色 | 描述 | 状态 |
|-------|------|------|------|
| [compile-qt-tool](skills/compile_qt_tool/SKILL.md) | **总开关** | 编排整个鸿蒙化编译流程：铁律 + 环境确认 + 依赖梳理 + 编排编译 + 验证交付 | ✅ 可用 |
| [create-qt-app](skills/create-qt-app/SKILL.md) | 子 skill | 生成 Qt 鸿蒙应用工程结构（QWidget 或 QML），或已有工程鸿蒙化 | ✅ 可用 |
| [build-run-qt-app](skills/build-run-qt-app/SKILL.md) | 子 skill | 使用 DevEco MCP 工具链编译、运行 Qt 鸿蒙应用并查看日志 | ✅ 可用 |

## 如何使用

### 1. 安装 Skills

将 skills 目录复制到你的 AI Agent 配置目录：

```bash
# 方法一：直接复制到 agent 的 skills 目录
cp -r skills/* <agent-config-dir>/skills/

# 方法二：克隆仓库
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
# 然后在 agent 配置文件中添加 skills 路径
```

> 三个 skill 都需安装，子 skill 会被总开关调用。单独使用子 skill 时也要先读取 `compile_qt_tool/SKILL.md` 的铁律章节（§0）。

### 2. 在 AI Agent 中使用

**通过总开关（推荐）**：直接调用 `compile-qt-tool`，它自动编排调用子 skill：

```
帮我把 CopyQ 项目鸿蒙化编译。
项目路径：/home/user/copyq
Qt 编译产物路径：/opt/qt5.15.16-arm64
```

**单独使用 create-qt-app 创建工程**：

```
帮我生成一个俄罗斯方块的 demo 工程，使用 QML。
工程目录放到：C:\Users\<username>\Documents\TetrisDemo
模板胶水代码路径：C:\Users\<username>\Downloads\ohostemplateforqtapplication.zip
```

**单独使用 build-run-qt-app 编译运行**（工程已就绪时）：

```
帮我在 DevEco 中编译运行这个 Qt 鸿蒙工程。
工程路径：/home/user/TetrisDemo
```

## 开发贡献

### Skill 文档规范

每个 skill 目录应包含：

- `SKILL.md` - Skill 主文档（必需）
  - YAML frontmatter：name, description
  - 详细的步骤说明
  - 常见问题和解决方案

- `references/` - 参考文档（可选）
  - API 文档、官方指南链接等

- `templates/` - 模板文件（可选）
  - 代码模板、配置文件模板等

- `scripts/` - 脚本文件（可选）
  - 辅助脚本、自动化工具等

### 提交新 Skill

1. Fork 本仓库
2. 在 `skills/` 目录下创建新的 skill 目录
3. 编写 `SKILL.md` 文档
4. 更新 README.md 中的 Skills 列表
5. 提交 Pull Request

## 相关链接

- [Qt for HarmonyOS 官方文档](https://wiki.qt.io/Qt_for_HarmonyOS)
- [DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/)
- [DevEco Toolbox GitHub](https://github.com/open-deveco/deveco-toolbox)
- [DevEco MCP Releases](https://github.com/open-deveco/deveco-mcp/releases)

## 许可证

本项目采用 Apache 2.0 许可证，详见 [LICENSE](LICENSE) 文件。