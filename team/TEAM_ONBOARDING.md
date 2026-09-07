# 团队入门指南

> 本文档面向首次使用 ohos_qt-skills 知识库的开发者。

## 前置条件

- Git (>= 2.x)
- Bash (>= 4.x) — Windows 用户使用 Git Bash
- Python (>= 3.8)
- (可选) gitleaks 8.30.1 — 用于本地 secret 扫描

## 快速开始

### 1. Clone 仓库

```bash
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills
```

### 2. 初始化个人环境

```bash
python _scripts/kb-init.py
```

向导会引导你设置：
- 你的名称/slug（用于分支命名和 contributors 字段）
- Qt 源码路径（可选）
- HarmonyOS SDK 路径（可选）

生成 `ENV.local.md`（gitignored，不会提交）。

### 3. 安装 pre-push hook

```bash
cp _scripts/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

这会在每次 push 前自动检查是否意外包含私有内容。

### 4. 验证环境

```bash
bash _scripts/verify.sh
```

如果所有检查通过，环境就绪。

## 日常使用

### 查找知识

1. 打开 `_index/_task-routing.md`，找到你的任务类型
2. 按路由表指示读取对应页面
3. 搜索错误：`grep -rl '关键字' problems/` 或查看 `_index/_map.md`

### 贡献知识

见 [CONTRIBUTING.md](../CONTRIBUTING.md)。简要流程：

```bash
git checkout -b <your-name>/<type>-<slug>
# 编辑/新增文件
bash _scripts/verify.sh
git add <files>
git commit -m "<type>(<scope>): <summary>"
git push origin <branch>
# 在 GitCode 上创建 PR
```

### AI Agent 使用

本仓库的 `CLAUDE.md` / `AGENTS.md` 定义了 AI Agent 的行为规范。如果你使用 Claude Code、Codex 或其他 AI 编码工具，它们会自动加载这些指令。

Agent 会在每次任务结束后自动执行知识沉淀（写入 `drafts/` 或 `problems/`），并通过 PR 提交。

## 目录结构速览

| 目录 | 内容 |
|------|------|
| `semantic/` | 技术概念、API 映射、平台限制 |
| `procedural/` | 工作流、构建步骤 |
| `episodic/` | 项目复盘、决策记录 |
| `problems/` | 编译/运行时错误及解决方案 |
| `drafts/` | 待审核的新知识草稿 |
| `_index/` | 派生索引（自动生成，勿手动编辑） |
| `_scripts/` | 门禁、索引重建、bot 等自动化脚本 |
| `_templates/` | 知识页/草稿/问题模板 |
| `ohos-common-kb-public/` | HarmonyOS 平台通用知识（内嵌） |
| `skills/` | 自动化技能 |

## 常见问题

**Q: verify.sh 报错 "gitleaks not found"**
A: gitleaks 是可选的。安装方法见 https://github.com/gitleaks/gitleaks/releases。未安装只会 WARN，不会阻止工作。

**Q: 我不确定内容是否适合公开**
A: 写入 `drafts/` 并在 PR 描述中标注"需重点审核"。Editor 会帮你判断。

**Q: 索引文件 (_index/) 需要手动更新吗？**
A: 不需要。运行 `bash _scripts/kb-regen-indexes.sh` 会自动重建。Bot 也会在合入后自动检查。
