# Knowledge draft template

> There are three draft entry points; pick one by content type:
> - **Faults/defects** (symptom + root cause + solution): `faults/_drafts/`, using `faults/_drafts/_template.md`
>   (evidence types, reproduction demos, and closed-loop requirements are all there; this template doesn't cover them)
> - **Knowledge pages** (concepts/workflows/retrospectives/API differences): write it with this template first; when merged it lands in one of
>   `semantic/`, `procedural/`, or `episodic/postmortems/`
> - **Build/runtime errors** (already fixed): write `problems/<type>-<slug>.md` directly; no draft needed

```yaml
---
id: {{semantic|procedural|episodic}}-{{slug}}
title: "{{Title}}"
type: {{semantic|procedural|episodic}}
status: draft
confidence: 0.5
contributors: [{{your-name}}]
sources:
  - type: {{doc|experience|discussion|code}}
    name: "{{Source name}}"
    date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
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

{{Why this rule/workflow exists — so you know when the exceptions apply}}

## How to apply

{{Concrete steps to follow next time}}

## Related

- {{Links to related pages (only reference existing formal pages, not other drafts)}}

---

## Self-check list (before submitting the PR)

- [ ] `id` uses the `e{N}-{slug}` format, where N is the current highest number + 1
- [ ] `type` is correct (it determines the target directory after promotion)
- [ ] `summary` is one sentence that lets the agent judge relevance
- [ ] No customer names/commercial content/internal paths/colleagues' real names
- [ ] Paths use `${ENV_VAR}` placeholders
- [ ] `refs` only references ids of existing formal pages
- [ ] `bash _scripts/verify.sh` passes locally
