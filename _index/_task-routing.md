---
id: agent-task-routing
type: meta
domain: workflow
tags: [agent, routing, task-types, workflow, decision-tree]
created: 2026-06-27
updated: 2026-11-16
status: active
refs: [agent-mesh, semantic-qt-harmonyos-golden-rules, procedural-demo-generation]
summary: >
  The developer task routing table: match a user request to a task type and determine the required pages and workflow.
  Covers porting, API/module/platform-limitation lookups, build troubleshooting, windows, lifecycle, problem analysis,
  fix verification, Qt6, third-party libraries, toolchains, demo generation, and more. Agents should scan this page first when they receive a task.
---

# Task routing table

> **How to use this**: when you receive a request, match it against the routing tree below to determine the task type, then load context from the "required pages" and execute the "workflow".

> **Multi-agent collaboration mode**: for the task ledger / handoff envelopes (ho-\*.yaml) / the flow log (flow.jsonl) / the human touchpoint contract, see
> [_agent-mesh](_agent-mesh.md); this table is the routing core of the task-dispatcher. Ignore this note in single-agent scenarios.

---

## The routing decision tree

```
User request
    │
    ├─ "port/migrate an app to HarmonyOS" ────────→ [A] Application porting
    ├─ "auto-migrate / one-click migration / run the migration" → [P] Automated migration (execution layer)
    ├─ "how do I replace this API on HarmonyOS" ──→ [B] API replacement lookup
    ├─ "does HarmonyOS support some Qt module" ───→ [C] Module support lookup
    ├─ "what are HarmonyOS's limits / what can't it do" → [D] Platform limitation lookup
    ├─ "build failure / build error / can't deploy" ──→ [E] Build troubleshooting
    ├─ "window display glitch / dialog misbehaves" ──→ [F] Window problems
    ├─ "lifecycle / closeEvent / continuation / sharing" → [G] Lifecycle
    ├─ "how do I use QtOhosExtras / some function" ──→ [H] QtOhosExtras APIs
    ├─ "something about Qt6" ─────────────────────→ [L] Qt6 status
    ├─ "how to build/package Qt6 / hvigor errors / won't install" → [O] Qt6 end-to-end build and deployment
    ├─ "third-party libs / dependencies / cross-compiling" → [M] Third-party libraries
    ├─ "DevEco / MCP / toolchain" ────────────────→ [N] Toolchain
    ├─ "a Qt+CEF demo / a WebEngine migration demo" → [Q] Demo generation (+ qt-cef-ohos-dev-guide)
    ├─ "write a demo / generate a test project / rendering demo" → [Q] Demo generation
    ├─ "is some issue fixed / unresolved issues / workarounds" → [R] Fault tracking
    └─ "build Qt / apply patches / release an SDK version / upstream evolution" → [S] SDK engineering
```

---

## Routing details

### [A] Application porting

**Trigger words**: port, migrate, HarmonyOS-ify, porting, migration

| Item | Content |
|------|---------|
| **Workflow** | `procedural/qt-app-harmonyos-migration.md` |
| **Required pages** | ① `golden-rules.md` ② `porting-workflow.md` (the 8-step decision tree) ③ `portgraph/docs/deps-report.md` (repo tool; dependency roles/version ranges) + `portgraph/docs/fetch-deps.md` (dependency closure artifacts) |
| **Load as needed** | `api-mapping.md`, `code-patterns.md`, `window-model.md`, `lifecycle.md`, `project-structure.md`, `third-party-libs.md` |
| **Expected output** | **Step 0 portgraph feasibility assessment** (analyze + deps + fetch-deps --dry-run: portable/blocked/uncertain + dependency role classification/version requirement checks + bottle count/source build gaps) → project creation → the 8-step migration → build verification |

> **The step 0 gate (aligned with [P]'s assess)**: when you receive an application porting task, first run
> `python portgraph/portgraph.py analyze <app>`, `deps <app>`, and
> `fetch-deps <app> --dry-run`.
> With ≥3 third-party library dependencies, judging feasibility one by one by hand is forbidden; the closure analysis output is authoritative. A blocked result requires reviewing
> the guard evidence for the blockers (only an unconditional ohos-active hit on a core path is a hard block; optional branches are let through);
> the unknowns are the source build gap list, and **each item must be reported to the user explicitly**.
> A counterexample from practice (2026-09, a large application with 68 dependencies): the first round judged dependencies one by one by hand, bypassing the closure analysis entirely;
> after that detour, the portgraph closure analysis produced the solution of 59 bottles + 9 source builds in one go,
> avoiding the wrong path of cross-compiling everything from source.

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
| **Load as needed** | `qt6-status.md` (for questions about Qt6 modules); `qt-cef-ohos-dev-guide.md` (for QtWebEngine — out of scope; CEF for OpenHarmony is a full Chromium replacement, with a WebEngine→CEF API mapping + migration plan + the de-versioned/stripped CEF component package) |
| **Expected output** | Whether the module is supported + alternatives (if not: QtWebEngine → the CEF replacement in `qt-cef-ohos-dev-guide.md`; for lightweight display, the native Qt WebView bridge can work as a first step) |

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
| **Required pages** | ① `golden-rules.md` §1 (B1-B12) ② `project-structure.md` |
| **Load as needed** | `build.md` (building Qt), `third-party-libs.md` (building third-party libraries), `problems/_lookup.md` (known errors); for Qt6 cross-compilation/packaging/hvigor, see [O]'s required pages |
| **Expected output** | Error classification → root cause → fix steps |

### [F] Window problems

**Trigger words**: window, dialog, fullscreen, floating window, tagging, setMask, hide, minimize

| Item | Content |
|------|---------|
| **Required pages** | ① `golden-rules.md` §2 (W1-W6) ② `window-model.md` |
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
| **Required pages** | ① `ohos-extras.md` (145+ APIs) |
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
| **Load as needed** | `project-structure.md` (deployment directories), `platform-limits.md` (limitations that affect third-party libraries); when packaging Qt6, imported libraries don't go into the HAP automatically — see `problems/runtime-hap-missing-so-closure.md` |
| **Expected output** | The cross-compilation method / deployment steps / a compatibility assessment |

### [N] Toolchain

**Trigger words**: DevEco, MCP, toolchain, hdc, DevEco Studio

| Item | Content |
|------|---------|
| **Required pages** | ① [[ohos-common-kb/procedural/deveco-cli-usage-rules|common: DevEco CLI usage rules]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/deveco-cli-usage-rules.md)) ② [[ohos-common-kb/semantic/deveco-mcp-capabilities|common: DevEco MCP capability boundaries]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/deveco-mcp-capabilities.md)) |
| **Load as needed** | [[ohos-common-kb/semantic/harmonyos-development-fundamentals|common: HarmonyOS development fundamentals]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md)), [[qt-harmonyos-build-run-workflow]] |
| **Expected output** | Installation/configuration steps |

### [O] Qt6 end-to-end build and deployment

**Trigger words**: Qt6 build, qt-cmake, harmonydeployqt6, _make_hap, hvigor, hvigorw,
signing, signingConfigs, compatibleSdkVersion, 00303082, EPERM symlink,
No hvigor path specified, won't install, aa start fails

| Item | Content |
|------|---------|
| **Required pages** | ① `procedural/qt6-ohos-windows-cli-deploy.md` (end to end with the Qt 6.12 prebuilt kit on the Windows command line: toolchain, `_make_hap`, the hvigor five-piece set, the signing six-piece set) ② `procedural/qt6-ohos-manual-deploy.md` (manual deployment bypassing harmonydeployqt6) |
| **Load as needed** | `skills/qt-app-porting/SKILL.md` (the three subcommands `doctor` / `sign` / `smoke-interact`); `problems/runtime-hap-missing-so-closure.md` (the HAP dependency closure), `problems/build-fail-hvigor-spawn-java-enoent.md`, `problems/build-hvigor-native-skip.md`, `problems/build-local-openharmony-signing-chain.md` |
| **Expected output** | Reproducible build/package/sign/install commands + the failure criterion for each step; **don't** answer "just click it in DevEco" |

> Before `trunk`, this body of knowledge existed only in procedural pages; neither the SKILL nor the routing pointed to it, so porters
> had to re-derive it all (`QT_HARMONYOS_HVIGOR` must be an absolute path, and if missing it still returns 0; junction permissions for
> non-administrators; the hardcoded `compatibleSdkVersion`). The routing moves it forward: read the pages before you start.

### [P] Automated migration (Execution Plane)

**Trigger words**: auto-migrate, one-click migration, run the migration, port this project to HarmonyOS, verify the migration result, analyze build/run logs

| Item | Content |
|------|---------|
| **Workflow** | `skills/qt-app-porting/SKILL.md` (unified CLI: `tools/qt-ohos-run.py`) |
| **Required pages** | ① `golden-rules.md` ② `skills/qt-app-porting/SKILL.md` |
| **Load as needed** | The `kb`/`refs` fields that come with risk findings and log hits (the R*.yaml / QOH*.yaml machine entries link directly to knowledge pages) |
| **Expected output** | Feasibility assessment (assess: portable/blocked/uncertain, driven by the three `knowledge/adaptation/` libraries) → risk report → migration plan → automatic shell project generation (templates/qt-ohos-app) → tracked modifications (.qt-ohos/patches) → build/package/install/launch → G0-G12 gate verdicts → report + knowledge draft (the draft→promote closed loop) |

> End-to-end data flow: `app → scan → assess → plan → project_generation → patch → compile → package → install → launch → smoke → verify → report → draft → promote → index regeneration → kb-release publishing`. assess is step 0 of the migration: if blocked, stop and produce the report (`assessment.json`).

> Key constraint: success is judged only by the gate results of `qt-ohos-run verify` (the LLM does the reasoning, the tool supplies the facts).
> Machine knowledge: `knowledge/rules/` (pre-scan rules R*.yaml), `knowledge/errors/` (error patterns QOH*.yaml, corresponding to problems/).

### [Q] Demo generation

**Trigger words**: write a demo, generate a demo, test project, rendering demo, feature demo, demo project, CEF demo, WebEngine demo

| Item | Content |
|------|---------|
| **Workflow** | `procedural/demo-generation.md` (the six-step loop) |
| **Required pages** | ① The workflow itself |
| **Load as needed** | `project-structure.md` (HarmonyOS projects), `build.md` (build configuration); `qt-cef-ohos-dev-guide.md` (Qt+CEF / WebEngine migration demos — HarmonyOS has no WebEngine, so use CEF; the grafting script ships with the CEF component package, not this knowledge base — see dev-guide §2.3/§5 for usage) |
| **Expected output** | Understand the requirement → technical design → create the project → write the code → verify the build → capture documentation; for a Qt+CEF demo, follow the grafting flow in `qt-cef-ohos-dev-guide.md` §2.3 |

### [R] Fault tracking

**Trigger words**: is it fixed, resolved, unresolved, known problem, known issue, workaround, temporary fix, follow-up status, fixed in the new version, fault status

| Item | Content |
|------|---------|
| **Required pages** | ① `faults/_registry.md` §Symptom index (symptom → root cause) ② `faults/_graph.yaml` (the machine-readable full graph, loaded in one go) |
| **Load as needed** | The matched root cause C page (defect: fix version / workaround W; limitation: alternative W / evolution); `faults/_index.md` (the four-entity graph model and state machines); the corresponding `problems/` page (solution details); `procedural/framework-fix-verification.md` (when you need to verify a fix) |
| **Tools** | `python tools/faults-build.py review` (scan for due reviews + advance states); after changing the source of truth, `build` regenerates the derived artifacts |
| **Expected output** | Characterization (defect awaiting a fix / platform limitation) + responsible domain + workaround or alternative (W, with its retirement condition) + tracking ticket status and fix version (T.fix_version) or the evolution/review plan |

### [S] SDK engineering (Execution Plane)

**Trigger words**: build Qt, rebuild Qt, apply a patch, apply a modification plan, release an SDK version, publish the SDK, switch/roll back the SDK version, upstream evolution, check for upstream updates, maintain the local SDK

| Item | Content |
|------|---------|
| **Workflow** | `skills/qt-sdk-forge/SKILL.md` (the unified CLI `tools/qt-sdk-run.py` is implemented: init/env/src-clone/status/patch-*/configure/build/install/verify/smoke-mark/release/release-list/use/diff/upstream-check/forge/resume, native cross-platform Python) |
| **Required pages** | ① `semantic/qt-harmonyos-build.md` (configure options / the three incremental build pitfalls) ② `procedural/framework-issue-analysis.md` §4.3-4.5 (the iron rules for patch generation and cleanup) ③ `skills/qt-sdk-forge/SKILL.md` |
| **Load as needed** | `procedural/framework-fix-verification.md` (fix verification), `problems/_lookup.md` (build errors), `faults/_registry.md` (root causes linked to patches), `skills/kb-init/references/qt-compile-guide.md` (build troubleshooting) |
| **Expected output** | Review of the modification plan → patch application (with provenance recorded) → build and install → SV0-SV8 gate verdicts → version release (manifest + SHA256) → ENV.local.md sync; periodically produce an upstream "evolution report" + a superseded-patch review + linkage with faults review |

> Relationship with [P]: [P] (qt-app-porting) doesn't rebuild the Qt framework — when you need a rebuild for verification or a release with patches, switch to this route;
> the SDK versions this route produces are consumed by [P] (the `qt_sdk_prefix` config item).
> When "has the new version fixed some issue" ([R]) needs a rebuild through the SDK to verify, it's also routed here.

---

## Handling ambiguous requests

When a request doesn't clearly match any type:

1. **Scan `golden-rules.md` first** — the iron rules cover the most common scenarios
2. **Ask for clarification** — offer the 3 most likely options
3. **If it spans several types** — orchestrate it through the [A] Application porting process, which pulls in the other types automatically

### Common ambiguous requests

| What the user says | The actual type | Routing |
|--------------------|-----------------|---------|
| "Help me migrate this Qt project to HarmonyOS (I want you to do it)" | [P] Automated migration | Run `tools/qt-ohos-run.py scan/plan/patch/verify`, following `skills/qt-app-porting/SKILL.md` |
| "This app won't run on HarmonyOS" | [E] Build troubleshooting or [A] Porting | Ask first: is this a new port or an existing project? |
| "What's the difference between HarmonyOS and Android?" | [D] Platform limitations + [G] Lifecycle | Load platform-limits + lifecycle |
| "Can you look at how to change this code?" | [B] API replacement | Load api-mapping + code-patterns |
| "What databases can I use on HarmonyOS?" | [C] Modules + [M] Third-party libraries | Check the Qt SQL module first, then SQLite as a third-party library |
| "Is this a known issue on HarmonyOS / has it been fixed?" | [R] Fault tracking (+ [E]/[D] for the verdict) | Check `faults/_registry.md` first, then `problems/_lookup.md` |
