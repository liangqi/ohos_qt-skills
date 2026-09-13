---
id: stage-uiability-lifecycle
title: The Stage model and the UIAbility lifecycle
status: active
confidence: 0.7
sources:
  - type: official
    name: "HarmonyOS Stage model and UIAbility development guide"
    date: 2026-08-03
    uri: "https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/uiability-overview"
  - type: experience
    name: "Practical adaptation of Qt to Stage/UIAbility, Want, and the lifecycle"
    date: 2026-08-03
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-03
review_by: null
superseded_by: null
tags: [stage, uiability, lifecycle, want, skills, launch-type]
refs: []
summary: "Platform semantics of UIAbility creation, WindowStage, Want routing, launchType, skills, and save/restore in the Stage model."
audience: public
---

# The Stage model and the UIAbility lifecycle

The Stage model organizes UI applications around the application, modules, AbilityStage, and UIAbility. Cross-platform frameworks typically hook their own event loop, windows, and launch parameters into this lifecycle, but they cannot replace the platform callbacks or manifest-based routing.

## Core objects

| Object | Role | Concepts an adapter must not conflate it with |
|---|---|---|
| `AbilityStage` | Module-level runtime context and lifecycle entry point | Not the same as a framework's application singleton |
| `UIAbility` | A UI-bearing application component that receives Want and lifecycle events | Not the same as any particular framework window |
| `WindowStage` | The UIAbility's window stage and main window host | A framework may manage several internal windows within one WindowStage |
| `Want` | A launch description specifying the target, action, URI, type, and parameters | A framework's argv/IPC is an adapter mapping, not the Want itself |

## Launch and restoration

The typical sequence is: the system creates/reuses the UIAbility based on `module.json5` → `onCreate(want, launchParam)` → `onWindowStageCreate(windowStage)` → the page/native content loads → foreground/background lifecycle changes.

Cold start and warm start must be handled separately: a new instance gets the initial Want from `onCreate`, while an existing instance may receive subsequent requests through `onNewWant`. Don't verify only cold start and then claim deep links, opening files, or share receiving work completely.

State saving and restoration are constrained by the timing of system callbacks and by resource limits. Business data that needs to persist should be written to the application's data layer — don't rely on the process staying alive or run long operations in a termination callback.

## Want routing

- An **explicit Want** normally names the bundle/module/ability, so the target is unambiguous.
- An **implicit Want** matches against the target Ability's `skills` via action, entities, URI/MIME, and so on.
- A capability that can be launched externally must also satisfy the platform's exported, permission, and skills configuration.
- Handle the data structures and access permissions of URIs/parameters according to the target API — don't treat them as plain file paths or command-line strings.

The actions/entities/uris in `module.json5` define how the system discovers a target. Framework pages should keep "how a Want maps to framework events/parameters"; this common knowledge base maintains the matching and lifecycle invariants.

## launchType and instances

The launchType the platform supports determines whether a new Want creates a new instance or routes to an existing one. The number of processes, tasks, UIAbility instances, and framework top-level windows are all different dimensions; a multi-window framework must not infer from "creating a second framework window" that a second Ability or system task is necessarily created.

## Closing and backgrounding

Closing a window, terminating a UIAbility, removing a task, system reclamation, and a forced process kill are not the same event. An adapter may map some of them to framework close/background callbacks, but it must:

1. Record the triggering source.
2. Distinguish an interactive close from a time-limited save.
3. Not promise that a forced kill can be intercepted.
4. Verify against system lifecycle and process logs, not merely by observing framework window state.

## Verification matrix

Cover at least: cold start, warm start with a new Want, foreground/background switching, closing from the task center, closing a window, restoration after the system terminates the process, explicit/implicit Wants, no matching target, permission denial, and multi-instance configurations.
