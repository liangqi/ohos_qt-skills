---
id: procedural-knowledge-sedimentation
type: procedural
domain: workflow
title: "Knowledge sedimentation protocol (triggered by verification events)"
status: active
audience: public
confidence: 1.0
contributors: [lzh]
sources:
  - type: experience
    name: "Trunk Flip v3.0.0 architecture design"
    date: 2026-09-07
created: 2026-09-07
updated: 2026-09-07
tags: [sedimentation, hook, protocol, automation]
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-golden-rules, faults/_index]
summary: "Trigger conditions, verification events, classification rules, and the operating procedure for knowledge sedimentation — a general protocol every agent must follow"
---

# Knowledge sedimentation protocol (hook-triggered)

> **This file is the general sedimentation protocol for every agent**. `AGENTS.md` / `CLAUDE.md` / `.cursorrules` / other tool configurations
> reference this file rather than copying the rules inline.

## Core principle

**Knowledge sedimentation is triggered by "verification events", not by timers.**

Finishing a HarmonyOS port = the knowledge has been verified in practice → only then is it worth capturing. Unverified knowledge doesn't go into the knowledge base.

## Verification events (hook trigger points)

| # | Verification event | Trigger condition | What to capture | Target path |
|---|----------|---------|---------|---------|
| 1 | **Application HarmonyOS port completed** | `verify` G0–G12 all PASS | A complete retrospective | `episodic/postmortems/` (or first into `faults/_drafts/`) |
| 2 | **Build error resolved** | The rebuild passes after the error is fixed | Error + cause + solution | `problems/build-fail-<slug>.md` |
| 3 | **Runtime issue resolved** | The fix is verified to work on a device | Error + cause + solution | `problems/runtime-<slug>.md` |
| 4 | **API difference discovered** | Real code verified the differing behavior | Update the API mapping table | Edit `semantic/qt-harmonyos-api-mapping.md` |
| 5 | **Platform limitation confirmed** | The limitation was actually triggered | Update the limitation list | Edit `semantic/qt-harmonyos-platform-limits.md` |
| 6 | **Third-party library built successfully** | The cross-compiled artifact runs correctly on a device | Update the compatibility record | Edit `semantic/qt-harmonyos-third-party-libs.md` |

### When not to trigger

- The task was abandoned midway (unverified)
- Only theoretical analysis, with no real code verification
- A repeat of a known issue (already in `problems/`)

## Sedimentation commands (the actual entry points in this repo)

This repo doesn't provide timer/hook scripts like `kb-sediment.sh`: sedimentation is triggered by the **final state of a verification event**, and the entry points are these:

```bash
# Build/runtime error fixed → create a draft first (with evidence type and reproduction demo requirements)
cp faults/_drafts/_template.md faults/_drafts/C-00XX-<slug>.md

# Fault characterization/closing the loop: after changing the source of truth you must rebuild the derived artifacts, and check must report error=0
python tools/faults-build.py build
python tools/faults-build.py check

# Page-type knowledge: write into the matching directory from a template, then run the gates
cp _templates/problem.md problems/build-<slug>.md
cp _templates/knowledge-page.md semantic/<slug>.md

# Self-check before wrapping up (after any write)
bash _scripts/ci.sh
```

Merging drafts goes through the editor-in-chief gate (`faults/_index.md` §6); for the agent-side process see `skills/kb-iterator/SKILL.md`.

## Classification rules (mandatory check before writing)

| Content characteristic | Belongs in | Action |
|----------|------|------|
| Contains commercial Qt customer correspondence or contract content | Private overlay | **Stop**, remind the user to write it to the private repo |
| Contains customer names or internal project code names | Private overlay | **Stop** |
| Contains internal absolute paths (C:/Users/xxx, etc.) | Needs sanitizing | Replace with `${ENV_VAR}` placeholders |
| Contains colleagues' real names | Needs sanitizing | Remove them or replace with roles |
| Contains framework-internal debug traces (with internal paths) | Private overlay | **Stop** |
| General technical knowledge (APIs, builds, errors, processes) | **This repo** | Go ahead and write it |

## Choosing the write path

| Knowledge type | Target | Template | Goes through a draft? |
|---------|------|------|:---------:|
| Build/deployment/runtime **errors** (fix verified) | `problems/<type>-<slug>.md` | `_templates/problem.md` | No (directly official) |
| **Small corrections** to existing pages | Edit directly + bump `updated` | — | No |
| **New knowledge**: retrospectives/processes/API differences | `faults/_drafts/` (fault-type) or directly an official page (knowledge-type) | `_templates/draft.md` | Yes |

## Operating procedure

```
A verification event occurs
    │
    ├─ 1. Classify (public or private?)
    │      └─ private → STOP, remind the user
    │
    ├─ 2. Choose the write path (problems/ or faults/_drafts/ or edit an existing page)
    │
    ├─ 3. Write the content (using the matching template)
    │      └─ contributors: [MY_NAME] read from ENV.local.md
    │
    ├─ 4. Verify
    │      python tools/faults-build.py build && python tools/faults-build.py check
    │      bash _scripts/ci.sh
    │
    ├─ 5. Commit
    │      git checkout -b <MY_NAME>/sediment-<slug>
    │      git add <files>
    │      git commit -m "add(<scope>): <summary> (verified)"
    │      git push origin <branch>
    │
    └─ 6. Create a PR (GitCode API or web)
           └─ the PR body states the verification status (build PASS / device PASS)
```

## What each stage corresponds to in this repo

| Responsibility | How this repo does it | How it's triggered |
|------|---------|---------|
| **Knowledge generation** | Agents write per this protocol; fault-type knowledge goes into `faults/_drafts/` first | Verification event (`verify` final state) |
| **Merging drafts** | The editor-in-chief gate (`faults/_index.md` §6) + `skills/kb-iterator` | Promoted after human verification |
| **Index maintenance** | Counts are guarded by `tests/test_kb_consistency.py`; the dashboard is updated on merge | Exposed as soon as a gate fails |
| **Rebuilding derived artifacts** | `python tools/faults-build.py build` | Mandatory after changing `knowledge/` or `faults/` |
| **Version releases** | `_scripts/gen-manifest.py` → tag → `release/vX.Y.Z` | Manually by maintainers; see `CONTRIBUTING.md` |

## Why

Problems with traditional timer-based sedimentation:
- Unverified knowledge enters the base → low quality, possibly misleading
- A timer doesn't know when there's something worth capturing → empty runs or missed content
- Agents can't tell "half done" from "verified complete"

Advantages of hook triggering:
- **Quality assurance**: only knowledge that passed verification enters the base
- **Nothing missed**: every verification event necessarily triggers sedimentation
- **Traceable**: every piece of knowledge is linked to a specific verification scenario
- **Reference**: `build_in_harmonyos`'s finish command → capture as soon as the build completes
