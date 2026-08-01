# CLAUDE.md

本文件指导 AI 工具（Claude Code / Codex / Cursor 等）使用本知识库。

> **这是一份 Qt for HarmonyOS 移植参考知识库**，面向进行 Qt 应用鸿蒙化与 Qt 应用问题分析的开发者。
> 它由一个更大的个人工作流知识库裁剪、脱敏后生成（见 `_scripts/kb-dev-edition.sh`）。

---

## 知识库结构

```
_index/      → 索引层（知识地图 _map、标签 _tags、仪表盘 _dashboard、任务路由 _task-routing）
semantic/    → 语义知识：技术概念、API 参考、平台限制、模块状态、构建/工程
procedural/  → 程序知识：工作流（应用迁移、问题分析、修复验证、Demo 生成）
episodic/    → 情景知识：实际移植项目复盘
problems/    → 错误知识库：实际编译/部署/运行时报错与解决方案
```

## 快速开始（Agent 必读）

**接到任务后，按此顺序加载**：

```
① _index/_task-routing.md    → 匹配任务类型，确定工作流和必读页
② semantic/qt-harmonyos-golden-rules.md  → 扫描 33 条铁律（避免已知陷阱）
③ _index/_map.md             → 知识地图，按 summary 判断相关性
④ 只读相关的知识页           → 不要全量加载
⑤ 沿 refs 字段追踪交叉引用    → 获取深度上下文
```

**四个核心页面**：

| 页面 | 作用 |
|------|------|
| `_index/_dashboard.md` | 仪表盘：计数、分域统计、使用建议入口 |
| `_index/_task-routing.md` | 任务路由：用户请求 → 任务类型 → 必读页 |
| `semantic/qt-harmonyos-golden-rules.md` | 33 条铁律速查（构建/窗口/API/限制/生命周期/跨平台） |
| `_index/_map.md` | 知识地图：每页一句话摘要 |

## 按场景入口

| 我想做... | 读哪些页 |
|----------|---------|
| 移植 Qt 应用到鸿蒙 | `procedural/qt-app-harmonyos-migration` + `semantic/qt-harmonyos-porting-workflow` + `qt-harmonyos-api-mapping` + `qt-harmonyos-code-patterns` |
| 查 API 替换 | `semantic/qt-harmonyos-api-mapping` + `qt-harmonyos-code-patterns` |
| 查某个 Qt 模块是否支持鸿蒙 | `semantic/qt-harmonyos-modules` |
| 查鸿蒙平台限制 | `semantic/qt-harmonyos-platform-limits` |
| 编译失败/构建报错/部署不了 | `semantic/qt-harmonyos-build` + `qt-harmonyos-build-run-workflow` + 先查 `problems/_lookup.md` |
| 窗口显示异常/对话框行为不对 | `semantic/qt-harmonyos-window-model` + golden-rules §二 |
| 生命周期/closeEvent/接续/分享 | `semantic/qt-harmonyos-lifecycle` |
| QtOhosExtras 怎么用 | `semantic/qt-ohos-extras` |
| 判断问题是否出在 Qt 鸿蒙框架层 | `golden-rules` + `qt-harmonyos-platform-limits` + `qt-harmonyos-api` + 先查 `problems/_lookup.md` |
| Qt 应用行为异常的排查思路 | `qt-harmonyos-build-run-workflow` §构建失败排查四步法 + `problems/_lookup.md` |
| 写个 demo/测试工程 | `procedural/demo-generation` |
| 三方库/依赖/交叉编译 | `semantic/qt-harmonyos-third-party-libs` |
| 遇到执行报错 | **先读 `problems/_lookup.md`**，按错误码/错误信息/症状搜索 |

## 读取约定

- **summary**：每页 frontmatter 的一句话摘要，Agent 据此判断是否需要加载该页
- **refs**：交叉引用的其他知识页 id，沿其追踪深度上下文
- **tags**：经 `_index/_tags.md` 按主题聚合浏览
- **problems/ 记录的是实际执行报错**（编译失败、部署失败、运行时崩溃），不是 Qt 文档中的平台限制——后者在 `semantic/qt-harmonyos-platform-limits.md`

## 路径变量

知识页以变量名（如 `QT5_15_SRC`、`OHOS_SDK_NATIVE`）引用本地路径，不硬编码。实际路径值见 `ENV.md`（开发者版为占位模板，需替换为你本机路径）。

## 待办与进度同步

- `TODO.md`：入库的待办模板（结构/分类规范，不含实际条目）。
- `TODO.local.md`：个人实际待办，记录进行中的任务与进展（已 gitignore，不入库）。
- 多步骤工作流任务在阶段转换时更新 `TODO.local.md` 的进展列；纯查询类任务无需同步。

## 多工具兼容

| 工具 | 集成方式 |
|------|---------|
| Claude Code | 本文件（CLAUDE.md）自动加载 |
| Codex | AGENTS.md 自动加载（与本文件内容相同） |
| Cursor | 在 `.cursorrules` 中引用 `_index/_map.md` |
| Windsurf | 在 `.windsurfrules` 中引用 `_index/_map.md` |
| Obsidian | 直接作为 Vault 打开，利用图谱可视化 |

## 内容来源

| 来源类型 | 说明 |
|----------|------|
| Qt 官方文档 | wiki.qt.io、doc.qt.io（API 映射、模块状态） |
| HarmonyOS 官方文档 | developer.huawei.com（生命周期、窗口模型、平台限制） |
| Qt 源码验证 | QtOhosExtras 模块、QPA 插件源码（API 签名、枚举路径） |
| 实践经验 | 框架问题分析、迁移项目复盘、实际报错积累 |

### Qt 框架版本（校验基准）

| 版本 | 分支 | Commit | 日期 |
|------|------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |
