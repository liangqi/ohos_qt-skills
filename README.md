# Qt for HarmonyOS 知识库（开发者版）

## 这是什么？

这是一个 **Agent 友好**的 Qt for HarmonyOS 移植参考知识库，核心设计理念：

- **编译而非检索** — 借鉴 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，将原始经验"蒸馏"为结构化知识页
- **分层加载** — 借鉴 Claude Code 的层级上下文机制，索引层始终加载，知识页按需加载
- **文件即数据** — 纯 Markdown + Git，零基础设施依赖
- **类型化记忆** — 借鉴认知科学，将知识分为四类 + 错误库

本版本由一个更大的个人工作流知识库经 `_scripts/kb-dev-edition.sh` 裁剪、脱敏后生成，仅保留对 Qt 应用鸿蒙化与 Qt 应用问题分析有用的技术内容。

## 快速开始

### 给 Agent 使用
如果你的 AI 工具支持 `CLAUDE.md`（如 Claude Code），它会自动读取本文件。
否则，将 `CLAUDE.md` 的内容复制到你的工具的系统提示或规则文件中。`AGENTS.md` 是同内容副本（供 Codex/OpenCode 使用）。

### 给 Obsidian 使用
1. 在 Obsidian 中将此文件夹作为 Vault 打开
2. 安装 Dataview 插件，可用 frontmatter 做高级查询
3. 使用 Graph View 查看知识之间的关联图谱

### 给人类使用
直接浏览各域目录下的 `.md` 文件即可。每个文件都是自包含的知识单元。从 `_index/_map.md` 或 `_index/_dashboard.md` 开始。

## 目录结构

```
qt-for-harmonyos-kb/
├── CLAUDE.md                  # Agent 操作规范（Claude Code 自动加载）
├── AGENTS.md                  # 同上（Codex 用，与 CLAUDE.md 内容相同）
├── ENV.md                     # 本地路径变量（占位模板，需替换为你的路径）
├── README.md                  # 本文件
│
├── _index/                    # 索引层
│   ├── _map.md                # 知识地图（Agent 入口）
│   ├── _tags.md               # 标签索引
│   ├── _dashboard.md          # 健康仪表盘
│   └── _task-routing.md       # 任务路由表
│
├── semantic/                  # 语义知识：我知道什么
│   ├── _index.md
│   └── <主题>.md
│
├── procedural/                # 程序知识：我怎么做
│   ├── _index.md
│   └── <流程>.md
│
├── episodic/                  # 情景知识：发生过什么
│   ├── _index.md
│   └── postmortems/           # 复盘
│
├── problems/                  # 错误知识库：实际报错与解决方案
│   ├── _lookup.md             # 错误速查表（按错误码/错误信息/症状检索）
│   ├── _index.md
│   └── <错误描述>.md
│
└── LICENSE
```

## 知识类型说明

| 类型 | 目录 | 核心问题 | 示例 |
|------|------|---------|------|
| 语义知识 | `semantic/` | 我知道什么？ | Qt 鸿蒙化架构、API 兼容性、平台限制 |
| 程序知识 | `procedural/` | 我怎么操作？ | 应用迁移工作流、问题分析、Demo 生成 |
| 情景知识 | `episodic/` | 发生过什么？ | SARibbon/Coin3D 迁移复盘、退出死锁分析 |
| 错误库 | `problems/` | 遇到这个执行错误怎么办？ | 编译失败、部署失败、运行时崩溃 |

## 错误知识库设计

**核心理念：一错一文件，速查优先**

`problems/` 记录实际操作中遇到的执行错误（编译失败、部署失败、运行时崩溃、开发工具问题等），**不是** Qt 官方文档中的已知平台限制——后者在 `semantic/qt-harmonyos-platform-limits.md`。

遇到执行错误时，读取 `problems/_lookup.md`，通过错误码、错误信息或症状快速定位到具体问题文件，获取完整的原因分析和解决方案。

## 设计参考

- [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 3层架构，编译知识而非检索
- [Claude Code Memory](https://code.claude.com/docs/en/memory) — 层级上下文加载
- [4-Layer File-Based Architecture](https://dev.to/oblivionlabz/building-persistent-memory-for-ai-agents-a-4-layer-file-based-architecture-4gc4) — Markdown 文件记忆系统

## License

MIT（见 `LICENSE`）。
