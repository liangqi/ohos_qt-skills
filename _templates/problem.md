# 问题记录模板

> 用于记录编译/部署/运行时遇到的实际错误。存放于 `problems/`。
> 报错类知识**直接写入 `problems/`**，无需走 `drafts/` 草稿流程。

```yaml
---
id: {{type}}-{{slug}}
title: "{{问题标题}}"
type: problem
status: active
confidence: 0.8
contributors: [{{your-name}}]
sources:
  - type: experience
    name: "{{遇到问题的场景}}"
    date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
last_confirmed: {{YYYY-MM-DD}}
superseded_by: null
tags: [problem, {{build|deploy|runtime|link|config}}]
refs: []
summary: "{{问题一句话摘要}}"
domain: {{构建|部署|运行时|窗口|多媒体|网络}}
severity: {{high|medium|low}}
error_message: |
  {{完整错误信息，用于 Agent 全文搜索匹配}}
---
```

# {{问题标题}}

## 错误信息

```
{{完整的错误输出}}
```

## 场景

{{在什么情况下遇到此问题（Qt 版本、OS 版本、构建配置等）}}

## 原因

{{根本原因分析}}

## 解决方案

{{如何解决（含具体命令/代码修改）}}

## 预防措施

{{如何避免再次遇到}}

## 关联

- {{相关 semantic/procedural 页面链接}}
