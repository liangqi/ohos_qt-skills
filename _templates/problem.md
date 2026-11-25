# Problem record template

> Used to record real errors encountered during build/deployment/runtime. Stored in `problems/`.
> Error knowledge is **written directly into `problems/`**; it doesn't go through the `drafts/` draft workflow.

```yaml
---
id: {{type}}-{{slug}}
title: "{{Problem title}}"
type: problem
status: active
confidence: 0.8
contributors: [{{your-name}}]
sources:
  - type: experience
    name: "{{Scenario in which the problem was hit}}"
    date: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
updated: {{YYYY-MM-DD}}
last_confirmed: {{YYYY-MM-DD}}
superseded_by: null
tags: [problem, {{build|deploy|runtime|link|config}}]
refs: []
summary: "{{One-sentence summary of the problem}}"
domain: {{build|deploy|runtime|window|multimedia|network}}
severity: {{high|medium|low}}
error_message: |
  {{The full error message, used for the agent's full-text search matching}}
---
```

# {{Problem title}}

## Error message

```
{{The full error output}}
```

## Scenario

{{The circumstances in which this problem was hit (Qt version, OS version, build configuration, and so on)}}

## Cause

{{Root cause analysis}}

## Solution

{{How to fix it (including the concrete commands/code changes)}}

## Prevention

{{How to avoid hitting it again}}

## Related

- {{Links to related semantic/procedural pages}}
