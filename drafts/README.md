# drafts/ — 知识草稿暂存区

> 参考 `build_in_harmonyos` 的知识图谱草稿机制。

## 生命周期

```
新建草稿 → PR 提交 → 门禁审核 → 合入 main → 自动 promote 到正式目录
```

### 状态流转

| 状态 | 含义 | 位置 |
|------|------|------|
| `draft` | 待审核的新知识 | `drafts/E{N}-<slug>.md` |
| `active` | 已 promote 到正式目录 | `semantic/` `procedural/` `episodic/` `problems/` 等 |

### 编号规则

- 文件名格式：`E{N}-<slug>.md`，N 为递增整数（如 `E001-egl-surface-recreate.md`）
- 查看当前最大编号：`ls drafts/E*.md | sort -V | tail -1`
- 新草稿取 max+1

## 何时用草稿 vs 直接写入

| 场景 | 目标 |
|------|------|
| 编译/部署/运行时 **报错** | 直接写 `problems/<type>-<slug>.md`（无需草稿） |
| 对已有页面的 **小修正**（typo、补充一行） | 直接编辑已有页面 |
| **新知识**：概念、流程、复盘、API 差异发现 | 写 `drafts/E{N}-<slug>.md` |
| **不确定是否公开安全** 的内容 | 写 `drafts/` 并在 PR 描述中标注需重点审核 |

## 草稿模板

使用 `_templates/draft.md`。最小 frontmatter：

```yaml
---
id: e{N}-{slug}
title: "标题"
type: semantic|procedural|episodic|problem
status: draft
contributors: [your-name]
created: YYYY-MM-DD
summary: "一句话摘要"
tags: []
---
```

## Promote 规则（合入后自动执行）

`kb-promote-drafts.sh` 在 PR 合入 main 后由 bot 自动运行：

1. 扫描 `drafts/E*.md` 中 `status: draft` 的文件
2. 根据 `type` 字段决定目标目录：
   - `semantic` → `semantic/{id}.md`
   - `procedural` → `procedural/{id}.md`
   - `episodic` → `episodic/postmortems/{id}.md`
   - `problem` → `problems/{id}.md`
3. 设置 `status: active`，移除 `id` 前缀中的 `e{N}-` 编号（保留语义 slug）
4. 移动文件到正式目录
5. 在 `drafts/_promoted/` 留下 tombstone（记录原文件名、目标路径、promote 时间）
6. 运行 `kb-regen-indexes.sh` 重建索引
7. 自动 commit：`ci(promote): E{N} → {target_dir}/{final_name}.md`

## 禁止事项

- **禁止**在正式页面中 `refs:` 引用 draft id（draft 随时可能被拒/改 id）
- **禁止**手动编辑 `_index/` 来包含 draft（索引只收 `status: active`）
- **禁止**在草稿中包含：客户名称、商业合同内容、内部绝对路径、同事真名
- **禁止**手动移动草稿到正式目录（由 bot 执行，确保审计轨迹）
