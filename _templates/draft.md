# 知识草稿模板

> 新知识（概念、流程、复盘、API 差异）先写入 `drafts/E{N}-<slug>.md`。
> 合入 main 后由 bot 自动 promote 到正式目录。
> 编译/运行时错误请直接写 `problems/<type>-<slug>.md`（无需草稿）。

```yaml
---
id: e{{N}}-{{slug}}
title: "{{标题}}"
type: {{semantic|procedural|episodic}}
status: draft
confidence: 0.5
contributors: [{{your-name}}]
sources:
  - type: {{doc|experience|discussion|code}}
    name: "{{来源名称}}"
    date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
tags: []
refs: []
summary: "{{一句话摘要，Agent 通过它判断是否需要加载此页}}"
---
```

# {{标题}}

## 概述

{{简要描述本页主题}}

## 核心内容

{{主体内容}}

## Why

{{为什么是这个规则/流程——知道何时例外}}

## How to apply

{{下次具体执行步骤}}

## 关联

- {{相关页面链接（仅引用已存在的正式页面，不要引用其他 draft）}}

---

## 自检清单（提交 PR 前）

- [ ] `id` 使用 `e{N}-{slug}` 格式，N 是当前最大编号 +1
- [ ] `type` 正确（决定 promote 后的目标目录）
- [ ] `summary` 是一句话，能让 Agent 判断相关性
- [ ] 不含客户名/商业内容/内部路径/同事真名
- [ ] 路径使用 `${ENV_VAR}` 占位符
- [ ] `refs` 只引用已存在的正式页面 id
- [ ] 本地 `bash _scripts/verify.sh` 通过
