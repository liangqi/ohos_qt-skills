# ohos_qt-skills — Qt for HarmonyOS Knowledge Base

> **Canonical trunk**: Qt for HarmonyOS 移植知识的唯一公开真相源。
>
> 所有人（团队成员 + 外部 Qt 开发者）clone 本仓库。私有/敏感内容在独立的 overlay 仓维护，**绝不写入此处**。
>
> **跨 KB 知识提示**：HarmonyOS 平台通用知识见本仓内嵌 `ohos-common-kb-public/`；完整生态见 [crossplatform-harmonyos-kb](https://gitcode.com/su-meiyan/crossplatform-harmonyos-kb)（扩展阅读，非运行依赖）。

---
updated: 2026-09-07
---

## 知识库结构

```
_index/      -> 索引层（知识地图、标签索引、仪表盘、任务路由）[committed, 勿手编]
semantic/    -> 语义知识：技术概念、API 映射、平台限制、窗口模型
procedural/  -> 程序知识：工作流、构建步骤、迁移流程
episodic/    -> 情景知识：项目复盘、决策记录
preference/  -> 偏好知识：编码风格、协作习惯
problems/    -> 错误知识库：编译/部署/运行时报错及解决方案
drafts/      -> 草稿暂存区：新知识待审核（合入后自动 promote）
skills/      -> 自动化技能（kb-init 等）
team/        -> 公开协作文件（贡献者列表、入门指南）
_scripts/    -> 门禁、索引重建、promote、release 等自动化脚本
_templates/  -> 知识页/草稿/问题模板
ohos-common-kb-public/  -> 内嵌的 HarmonyOS 平台通用知识
```

## 快速开始（Agent 必读）

> **30 秒了解本知识库**
>
> Qt for HarmonyOS 移植专用知识库，覆盖 API 映射、窗口模型、生命周期、平台限制、构建部署等核心主题。

**接到任务后，按此顺序加载**：

```
1. _index/_task-routing.md    -> 匹配任务类型，确定工作流和必读页
2. semantic/qt-harmonyos-golden-rules.md  -> 扫描铁律（避免已知陷阱）
3. 按任务路由表加载具体页面    -> 只读需要的，不要全量加载
```

**核心页面速览**：

| 页面 | 作用 |
|------|------|
| `_index/_task-routing.md` | 任务路由表：请求 -> 任务类型 -> 工作流 -> 必读页 |
| `semantic/qt-harmonyos-golden-rules.md` | 铁律速查：规则分类（构建/窗口/API/限制/生命周期/跨平台） |
| `_index/_map.md` | 知识地图：所有页面的 summary 聚合 |
| `_index/_dashboard.md` | KB 健康仪表盘 |
| `ENV.md` | 环境变量与路径占位符清单 |

## 身份识别（每次会话必做）

1. 读取 `ENV.local.md`（gitignored，由 `kb-init.py` 生成）
2. 获取 `MY_NAME`（slug，用于 `contributors` 字段与分支命名）
3. 获取 `GIT_USERNAME`（= git user.name）
4. 所有新建/修改页面，`contributors` 字段填入 `MY_NAME`
5. 如果 `ENV.local.md` 不存在 → 提示运行 `python _scripts/kb-init.py`

## 读取知识

索引已 committed，fresh clone 即可用，无需 bootstrap。

1. **确定任务类型**：读 `_index/_task-routing.md`
2. **扫描铁律**：`semantic/qt-harmonyos-golden-rules.md`
3. **知识地图**：`_index/_map.md`（按 summary 判断相关性）
4. **错误检索**：`problems/_lookup.md`（按错误码/症状/域检索）
5. **只读取相关页面**，沿 `refs` 追踪交叉引用
6. **标签浏览**：`_index/_tags.md`

> `status: archived/deprecated` 的页面**不可用于回答**（仅供历史查阅）。

## 知识沉淀（Hook 触发 — 验证通过时自动执行）

### 核心原则

**知识沉淀由「验证事件」触发，不由定时器触发。**

当一个应用成功完成鸿蒙化（编译通过 + 设备运行成功），说明相关知识经过了实战验证，
此时 Agent 必须自动执行沉淀。未经验证的知识不值得入库。

### 触发点（Hook）

| 验证事件 | 触发条件 | 沉淀内容 |
|----------|---------|---------|
| **应用鸿蒙化完成** | 编译 PASS + 设备运行 PASS | 完整复盘 → `drafts/E{N}-<app>-porting-retro.md` |
| **编译错误解决** | 错误修复后重新编译通过 | 错误记录 → `problems/<type>-<slug>.md` |
| **运行时问题解决** | 设备上验证修复有效 | 错误记录 → `problems/runtime-<slug>.md` |
| **API 差异发现** | 实际代码验证了差异行为 | 更新 `semantic/qt-harmonyos-api-mapping.md` |
| **平台限制确认** | 实际触发了限制 | 更新 `semantic/qt-harmonyos-platform-limits.md` |
| **三方库编译成功** | 交叉编译产物在设备运行正常 | 更新 `semantic/qt-harmonyos-third-party-libs.md` |

### 沉淀命令

```bash
# 应用鸿蒙化完成时（主路径）
bash _scripts/kb-sediment.sh --task "AppName" --stage done --notes "关键发现..."

# 编译/运行时错误解决时
bash _scripts/kb-sediment.sh --error "完整错误信息" --solution "解决方案" --type build

# Agent 引导式（由 Agent 自行判断沉淀内容）
bash _scripts/kb-sediment.sh --interactive
```

### 第一步：分类判断（强制）

**在写入任何内容前，必须判断**：

| 内容特征 | 归属 | 动作 |
|----------|------|------|
| 含商业 Qt 客户往来、合同内容 | 私有 overlay | **停止**，提醒用户写入私有仓 |
| 含客户名称、内部项目代号 | 私有 overlay | **停止** |
| 含内部绝对路径（C:/Users/xxx 等） | 需脱敏 | 用 `${ENV_VAR}` 占位符替代 |
| 含同事真名 | 需脱敏 | 移除或用角色代替 |
| 含框架内部调试 trace（带内部路径） | 私有 overlay | **停止** |
| 通用技术知识（API、构建、错误、流程） | **本仓** | 继续写入 |

### 第二步：选择写入路径

| 知识类型 | 目标 | 模板 |
|---------|------|------|
| 编译/部署/运行时**报错**（已验证修复） | `problems/<type>-<slug>.md`（直接正式目录） | `_templates/problem.md` |
| 对已有页面的**小修正** | 直接编辑 + bump `updated` 日期 | — |
| **新知识**：复盘/流程/API 差异（经验证） | `drafts/E{N}-<slug>.md` | `_templates/draft.md` |

### 第三步：验证 + 提交

```bash
# 1. 重生成索引（如修改了正式页面）
bash _scripts/kb-regen-indexes.sh

# 2. 运行完整门禁
bash _scripts/verify.sh

# 3. 创建分支 + commit + push + PR
git checkout -b <MY_NAME>/<type>-<slug>
git add <files>
git commit -m "<type>(<scope>): <summary>"
git push origin <branch>
# 通过 GitCode Web 或 API 创建 PR -> main
```

**铁律**：
- **永不直接 push main**（分支保护，PR 必须）
- Commit 格式：`<type>(<scope>): <简述>`（type: add/fix/update/archive/ci/doc）
- 分支格式：`<MY_NAME>/<type>-<slug>`
- PR 描述含：变更类型、摘要、影响文件、自检清单
- 不加 AI 署名（无 Co-Authored-By、无 Generated with...）

### 草稿 Promote 说明

`drafts/` 中的草稿合入 main 后，由 bot 自动执行 promote：
- `status: draft` -> `active`
- 移入正式目录（按 `type` 字段路由）
- 索引自动重建
- **无需手动移动或编辑索引**

## 更新已有知识

1. 直接编辑对应页面
2. 更新 frontmatter `updated` 日期
3. `bash _scripts/verify.sh`
4. 提交 PR

## 归档过时知识

1. `status` -> `archived`（或 `deprecated`）
2. 添加 `archive_date`、`archive_reason`、`superseded_by`
3. 文件顶部添加归档说明
4. `bash _scripts/kb-regen-indexes.sh`（索引自动排除归档页）
5. 提交 PR

## 错误检索（遇到执行错误时）

1. `grep -rl '<错误关键字>' problems/` 或查 `problems/_lookup.md`
2. 匹配到 -> 读取解决方案
3. 未匹配 -> 用 `_templates/problem.md` 新建（直接写入 `problems/`，不走草稿）

## Git 操作规范

**分支命名**：`<MY_NAME>/<type>-<slug>`
**Commit message**：`<type>(<scope>): <简述>`
**PR 流程**：branch -> push -> GitCode PR -> bot 审核 -> editor 合入

## 共享文件保护

以下文件修改需在 PR 描述中说明理由：
- `CLAUDE.md` / `AGENTS.md`（必须同步修改，内容一致）
- `ENV.md`（变量定义文档）
- `kb.yaml`（仓库契约）
- `_scripts/` 下的门禁脚本

## 多工具兼容

| 工具 | 集成方式 |
|------|---------|
| Claude Code | CLAUDE.md 自动加载 |
| Codex | AGENTS.md 自动加载（与 CLAUDE.md 同步） |
| Cursor | `.cursorrules` 引用 `_index/_task-routing.md` |
| Obsidian | 直接作为 Vault 打开 |

## 内容来源

| 来源类型 | 说明 |
|----------|------|
| Qt 官方文档 | wiki.qt.io、doc.qt.io |
| HarmonyOS 官方文档 | developer.huawei.com |
| Qt 源码验证 | QtOhosExtras、QPA 插件源码 |
| 社区贡献 | 开发者 PR（经门禁审核） |
| 工作经验 | 移植实战、问题分析 |

### Qt 框架版本（校验基准）

| 版本 | 分支 | 说明 |
|------|------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 主要支持版本 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 遗留支持版本 |
