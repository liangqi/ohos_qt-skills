---
id: agent-task-routing
type: meta
domain: workflow
tags: [agent, routing, task-types, workflow, decision-tree]
created: 2026-06-27
updated: 2026-08-29
status: active
refs: [semantic-qt-harmonyos-golden-rules, procedural-demo-generation]
summary: >
  The developer task routing table: match a user request to a task type and determine the required pages and workflow.
  Covers porting, API/module/platform-limitation lookups, build troubleshooting, windows, lifecycle, problem analysis,
  fix verification, Qt6, third-party libraries, toolchains, demo generation, and more. Agents should scan this page first when they receive a task.
---

# Task routing table

> **How to use this**: when you receive a request, match it against the routing tree below to determine the task type, then load context from the "required pages" and execute the "workflow".

---

## The routing decision tree

```
User request
    │
    ├─ "port/migrate an app to HarmonyOS" ────────→ [A] Application porting
    ├─ "how do I replace this API on HarmonyOS" ──→ [B] API replacement lookup
    ├─ "does HarmonyOS support some Qt module" ───→ [C] Module support lookup
    ├─ "what are HarmonyOS's limits / what can't it do" → [D] Platform limitation lookup
    ├─ "build failure / build error / can't deploy" ──→ [E] Build troubleshooting
    ├─ "window display glitch / dialog misbehaves" ──→ [F] Window problems
    ├─ "lifecycle / closeEvent / continuation / sharing" → [G] Lifecycle
    ├─ "how do I use QtOhosExtras / some function" ──→ [H] QtOhosExtras APIs
    ├─ "something about Qt6" ─────────────────────→ [L] Qt6 status
    ├─ "third-party libs / dependencies / cross-compiling" → [M] Third-party libraries
    ├─ "DevEco / MCP / toolchain" ────────────────→ [N] Toolchain
    ├─ "a Qt+CEF demo / a WebEngine migration demo" → [Q] Demo generation (+ qt-cef-ohos-dev-guide + tools/kb-cef-graft.py)
    └─ "write a demo / generate a test project / rendering demo" → [Q] Demo generation
```

---

## Routing details

### [A] Application porting

**Trigger words**: port, migrate, HarmonyOS-ify, porting, migration

| Item | Content |
|------|---------|
| **Workflow** | `procedural/qt-app-harmonyos-migration.md` |
| **Required pages** | ① `golden-rules.md` ② `porting-workflow.md` (the 8-step decision tree) |
| **Load as needed** | `api-mapping.md`, `code-patterns.md`, `window-model.md`, `lifecycle.md`, `project-structure.md`, `third-party-libs.md` |
| **Expected output** | Feasibility assessment → project creation → the 8-step migration → build verification |

### [B] API replacement lookup

**Trigger words**: API, replace, alternative, how do I change, QProcess, chmod, symlink

| Item | Content |
|------|---------|
| **Required pages** | ① `api-mapping.md` (12 categories of mapping tables) |
| **Load as needed** | `code-patterns.md` (before/after code), `platform-limits.md` (if the API is restricted by the platform) |
| **Expected output** | A concrete replacement plan + code examples |

### [C] Module support lookup

**Trigger words**: module, support, QtWebEngine, QtMultimedia, module status

| Item | Content |
|------|---------|
| **Required pages** | ① `modules.md` |
| **Load as needed** | `qt6-status.md` (for questions about Qt6 modules); `qt-cef-ohos-dev-guide.md` (for QtWebEngine — out of scope; CEF for OpenHarmony is a full Chromium replacement, with a WebEngine→CEF API mapping + migration plan + the de-versioned/stripped CEF component package + the `tools/kb-cef-graft.py` one-shot grafting script) |
| **Expected output** | Whether the module is supported + alternatives (if not: QtWebEngine → the CEF replacement in `qt-cef-ohos-dev-guide.md` + grafting via `tools/kb-cef-graft.py`; for lightweight display, the native Qt WebView bridge can work as a first step) |

### [D] Platform limitation lookup

**Trigger words**: limitation, can't, forbidden, chmod, symlink, dlopen, sandbox

| Item | Content |
|------|---------|
| **Required pages** | ① `platform-limits.md` |
| **Load as needed** | `golden-rules.md` §4 (P1-P5) |
| **Expected output** | A description of the limitation + the QTBUG number + a workaround |

### [E] Build troubleshooting

**Trigger words**: build failure, build error, find_package, can't deploy, dlopen failed, black screen

| Item | Content |
|------|---------|
| **Workflow** | `build-run-workflow.md` §The four-step build failure triage |
| **Required pages** | ① `golden-rules.md` §1 (B1-B11) ② `project-structure.md` |
| **Load as needed** | `build.md` (building Qt), `third-party-libs.md` (building third-party libraries), `problems/_lookup.md` (known errors) |
| **Expected output** | Error classification → root cause → fix steps |

### [F] Window problems

**Trigger words**: window, dialog, fullscreen, floating window, tagging, setMask, hide, minimize

| Item | Content |
|------|---------|
| **Required pages** | ① `golden-rules.md` §2 (W1-W5) ② `window-model.md` |
| **Load as needed** | `code-patterns.md` §Pattern 3 (dialogs) |
| **Expected output** | An explanation of the rule + the fixed code |

### [G] Lifecycle

**Trigger words**: closeEvent, Ability, lifecycle, continuation, sharing, Want, argv, dark mode

| Item | Content |
|------|---------|
| **Required pages** | ① `lifecycle.md` (the gold standard) |
| **Load as needed** | `golden-rules.md` §5 (L1-L4), `ohos-extras.md` (the relevant APIs) |
| **Expected output** | A description of the behavior + code examples + enum paths |

### [H] QtOhosExtras APIs

**Trigger words**: QtOhosExtras, startAbility, QOhosWant, QOhosAppContext, ShareKit

| Item | Content |
|------|---------|
| **Required pages** | ① `ohos-extras.md` (~36 APIs) |
| **Load as needed** | `lifecycle.md` (usage examples), `golden-rules.md` §3 (A1-A6) |
| **Expected output** | The API signature + its purpose + a usage example |

### [L] Qt6 status

**Trigger words**: Qt6, Qt 6, qtbase dev

| Item | Content |
|------|---------|
| **Required pages** | ① `qt6-status.md` |
| **Load as needed** | `overview.md`, `build.md` §Qt6 |
| **Expected output** | The current status + known differences + items still to be verified |

### [M] Third-party libraries

**Trigger words**: third-party library, dependency, cross-compile, vcpkg, OpenSSL, boost, zlib

| Item | Content |
|------|---------|
| **Required pages** | ① `third-party-libs.md` |
| **Load as needed** | `project-structure.md` (deployment directories), `platform-limits.md` (limitations that affect third-party libraries) |
| **Expected output** | The cross-compilation method / deployment steps / a compatibility assessment |

### [N] Toolchain

**Trigger words**: DevEco, MCP, toolchain, hdc, DevEco Studio

| Item | Content |
|------|---------|
| **Required pages** | ① [[ohos-common-kb/procedural/deveco-cli-usage-rules|common: DevEco CLI usage rules]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/deveco-cli-usage-rules.md)) ② [[ohos-common-kb/semantic/deveco-mcp-capabilities|common: DevEco MCP capability boundaries]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/deveco-mcp-capabilities.md)) |
| **Load as needed** | [[ohos-common-kb/semantic/harmonyos-development-fundamentals|common: HarmonyOS development fundamentals]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md)), [[qt-harmonyos-build-run-workflow]] |
| **Expected output** | Installation/configuration steps |

### [Q] Demo generation

**Trigger words**: write a demo, generate a demo, test project, rendering demo, feature demo, demo project, CEF demo, WebEngine demo

| Item | Content |
|------|---------|
| **Workflow** | `procedural/demo-generation.md` (the six-step loop) |
| **Required pages** | ① The workflow itself |
| **Load as needed** | `project-structure.md` (HarmonyOS projects), `build.md` (build configuration); `qt-cef-ohos-dev-guide.md` + `tools/kb-cef-graft.py` + `tools/kb-cef-graft.config.example.json` (Qt+CEF / WebEngine migration demos — HarmonyOS has no WebEngine, so use CEF; `tools/kb-cef-graft.py --config <config> --run` does grafting + signing + installation + launch + crash checking in one shot) |
| **Expected output** | Understand the requirement → technical design → create the project → write the code → verify the build → capture documentation; for a Qt+CEF demo, just use `tools/kb-cef-graft.py --run` |

---

## Handling ambiguous requests

When a request doesn't clearly match any type:

1. **Scan `golden-rules.md` first** — the 33 iron rules cover the most common scenarios
2. **Ask for clarification** — offer the 3 most likely options
3. **If it spans several types** — orchestrate it through the [A] Application porting process, which pulls in the other types automatically

### Common ambiguous requests

| What the user says | The actual type | Routing |
|--------------------|-----------------|---------|
| "This app won't run on HarmonyOS" | [E] Build troubleshooting or [A] Porting | Ask first: is this a new port or an existing project? |
| "What's the difference between HarmonyOS and Android?" | [D] Platform limitations + [G] Lifecycle | Load platform-limits + lifecycle |
| "Can you look at how to change this code?" | [B] API replacement | Load api-mapping + code-patterns |
| "What databases can I use on HarmonyOS?" | [C] Modules + [M] Third-party libraries | Check the Qt SQL module first, then SQLite as a third-party library |
