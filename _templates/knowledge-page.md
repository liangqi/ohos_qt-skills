# 知识页模板

> 所有知识页使用此模板。复制后替换 `{{...}}` 占位符。
> 本仓为公开 trunk，无 `audience:` 字段（存在即公开）。

```yaml
---
id: {{slug}}
title: {{标题}}
type: {{semantic|procedural|episodic|preference}}
status: active
confidence: 0.5
contributors: [{{your-name}}]
sources:
  - type: {{doc|experience|discussion|code}}
    name: "{{来源名称}}"
    date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
last_confirmed: {{YYYY-MM-DD}}
review_by: null
superseded_by: null
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

{{为什么是这个规则/流程——知道何时例外。procedural 域建议填写}}

## How to apply

{{下次具体执行步骤。procedural 域建议填写}}

## 关联

- {{相关页面1（写已存在的页面 id）}}
- {{相关页面2}}
