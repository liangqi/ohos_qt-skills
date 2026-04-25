# OHOS Qt Skills

Qt for HarmonyOS 开发的 Hermes Agent Skills 集合。

本项目包含用于 Hermes Agent 的 Qt 鸿蒙化开发技能（Skills），帮助开发者快速创建和管理 Qt for HarmonyOS 项目。

## 目录结构

```
ohos_qt-skills/
├── README.md                   # 项目说明
├── skills/                     # Skills 目录
│   ├── create-qt-app/          # 创建 Qt 鸿蒙应用
│   │   ├── SKILL.md            # Skill 主文档
│   │   ├── references/         # 参考文档
│   │   ├── templates/          # 模板文件
│   │   └── scripts/            # 脚本文件
│   └── ...                     # 其他 skills
├── docs/                       # 额外文档
│   └── qt-harmonyos-setup.md   # Qt 鸿蒙环境配置指南
└── LICENSE                     # 许可证文件
```

## Skills 列表

| Skill | 描述 | 状态 |
|-------|------|------|
| [create-qt-app](skills/create-qt-app/SKILL.md) | 生成 Qt 鸿蒙应用工程结构（QWidget 或 QML） | ✅ 可用 |

## 如何使用

### 1. 安装 Skills

将 skills 目录复制到 Hermes Agent 的 skills 目录：

```bash
# 方法一：直接复制
cp -r skills/* ~/.hermes/skills/

# 方法二：克隆仓库到 skills 目录
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git ~/.hermes/skills/ohos_qt-skills
# 然后在 config.yaml 中配置 skills 路径
```

### 2. 在 Hermes Agent 中使用

在 Hermes Agent 对话中，直接请求创建 Qt 鸿蒙应用：

```
帮我生成一个俄罗斯方块的 demo 工程，使用 QML。
工程目录放到：C:\Users\<username>\Documents\TetrisDemo
模板胶水代码路径：C:\Users\<username>\Downloads\ohostemplateforqtapplication.zip
```

Hermes Agent 会自动加载 `create-qt-app` skill 并按照规范创建工程。

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
- [Hermes Agent](https://github.com/nousresearch/hermes-agent)
- [DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/)

## 许可证

本项目采用 Apache 2.0 许可证，详见 [LICENSE](LICENSE) 文件。