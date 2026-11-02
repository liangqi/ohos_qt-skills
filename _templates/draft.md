# 知识草稿模板

> 三处草稿入口，按内容类型选：
> - **故障/缺陷**（现象+根因+方案）：`faults/_drafts/`，套 `faults/_drafts/_template.md`
>   （证据类型、复现 demo、闭环要求都在那里，本模板不覆盖）
> - **知识页**（概念/流程/复盘/API 差异）：先写成本模板，合入时落到 `semantic/` `procedural/`
>   `episodic/postmortems/` 之一
> - **编译/运行时错误**（已修好）：直接写 `problems/<type>-<slug>.md`，不必草稿

```yaml
---
id: {{semantic|procedural|episodic}}-{{slug}}
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
