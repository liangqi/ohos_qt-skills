# Knowledge page template

> All knowledge pages use this template. After copying it, replace the `{{...}}` placeholders.
> This repository is the public trunk, so there is no `audience:` field (anything here is public).

```yaml
---
id: {{slug}}
title: {{Title}}
type: {{semantic|procedural|episodic|preference}}
status: active
confidence: 0.5
contributors: [{{your-name}}]
sources:
  - type: {{doc|experience|discussion|code}}
    name: "{{Source name}}"
    date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
last_confirmed: {{YYYY-MM-DD}}
review_by: null
superseded_by: null
tags: []
refs: []
summary: "{{One-sentence summary; the agent uses it to decide whether to load this page}}"
---
```

# {{Title}}

## Overview

{{Briefly describe the topic of this page}}

## Core content

{{Main content}}

## Why

{{Why this rule/workflow exists — so you know when the exceptions apply. Recommended for the procedural domain}}

## How to apply

{{Concrete steps to follow next time. Recommended for the procedural domain}}

## Related

- {{Related page 1 (use the id of an existing page)}}
- {{Related page 2}}
