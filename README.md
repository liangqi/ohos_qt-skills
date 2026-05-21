# OHOS Qt Skills

Qt for HarmonyOS 开发的 AI Agent Skills 集合——帮助开发者将 Qt 项目编译、运行到鸿蒙系统上。

## 三个 Skill 的关系

**`qt-ohos-project-analyzer` 是总开关**，编排整个鸿蒙化编译流程，在需要时调用另外两个子 skill：

```
qt-ohos-project-analyzer（总开关 / 鸿蒙化项目分析）
  ├── 调用 → create-qt-app（工程生成）
  └── 调用 → build-run-qt-app（编译运行）
```
ohos_qt-skills/
├── README.md                   # 项目说明
├── skills/                     # Skills 目录
│   ├── qt-ohos-project-analyzer/  # 总开关 / 鸿蒙化项目分析器
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
| [qt-ohos-project-analyzer](skills/qt-ohos-project-analyzer/SKILL.md) | **总开关** | 鸿蒙化项目分析：铁律 + 环境确认 + 依赖梳理 + 编排编译 + 验证交付 | ✅ 可用 |
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

> 三个 skill 都需安装，子 skill 会被总开关调用。单独使用子 skill 时也要先读取 `qt-ohos-project-analyzer/SKILL.md` 的铁律章节（§0）。

### 2. 在 AI Agent 中使用

**通过总开关（推荐）**：直接调用 `qt-ohos-project-analyzer`，它自动编排调用子 skill：

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