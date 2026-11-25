---
id: agent-mesh
type: meta
domain: workflow
tags: [agent, multi-agent, protocol, handoff, flow-log, human-in-the-loop, task-ledger]
created: 2026-09-23
updated: 2026-09-23
status: active
refs: [agent-task-routing, faults-index, qt-app-porting, qt-sdk-forge, framework-issue-analysis, qt-ohos-run-test, framework-fix-verification]
summary: >
  The master multi-agent collaboration protocol (single source of truth): the interface cards for the 7 core agents + 2 optional agents the knowledge base is split into
  (trigger / CLI / gate / state plane / inbound and outbound deliverables / human touchpoints), the task ledger and flow log formats
  (task.yaml + flow.jsonl + ho-*.yaml handoff envelopes), the three task chains, the three-level classification of human involvement (H1 blocking decision /
  H2 human execution / H3 review and confirmation) with the general red lines, and the concurrency contract. The communication contract of every split-out agent is defined by this page;
  each SKILL.md only references it and doesn't copy it (avoiding drift from writing it twice).
---

# Agent Mesh — the master multi-agent collaboration protocol

> In one sentence: once the knowledge base is split into several independent collaborating agents, **who takes which task, what deliverables they produce,
> which gate counts as success, when a human must be called in, and how the log keeps a trail** are defined by this page as the single contract source.
> Single-agent scenarios don't need this page — just follow [_task-routing](_task-routing.md).

## 1. Collaboration principles (five, the same for every agent)

1. **The LLM does the reasoning, the tool supplies the facts**: gate verdicts (G0-G12 / SV0-SV8 / check) are copied only from machine output;
   an agent must never fill them in or upgrade them — PARTIAL can't be reported as PASS, and TIMEOUT is never PASS.
2. **No refs, no handoff**: every cross-agent handoff must carry refs (`fault-C-xxxx` / `QOHxxx` / `TSK-xxx`);
   the recipient bounces any handoff without refs (matching the machine-enforced discipline of sdk-forge patch-import).
3. **Single source of truth; envelopes only store pointers**: the task ledger is in `workspace/tasks/`, the knowledge source of truth is inside the knowledge base
   (`faults/_data/`, `knowledge/`, the knowledge pages), and build state is in each agent's own state plane
   (`.qt-ohos/`, `.qtsdk/`); handoff envelopes record pointers, not copies of the content.
4. **Submit drafts only; never change the source of truth**: business agents' knowledge output can only go through drafts
   (`faults/_drafts/draft-*.md` or `knowledge/drafts/`); write access to the source of truth belongs solely to
   kb-iterator (the editor-in-chief gate), mirroring the collaborative drafts model of faults.
5. **Human involvement always leaves a trail**: every action that stops to wait for a human writes a `human-required` event to flow.jsonl
   (with reason and options); the human's decision is recorded naturally by the subsequent events.

## 2. Agent interface cards

### 2.1 Roster (overview)

| # | Agent (skill name) | Responsibility | Execution plane | Success criterion | State plane | Definition file |
|---|------|------|---------|---------|---------|---------|
| 1 | task-dispatcher | Task ledger, routing and dispatch, flow log, closing tasks | — | Ledger complete, routing correct | `workspace/tasks/` | [skills/task-dispatcher](../skills/task-dispatcher/SKILL.md) |
| 2 | port-assessor | Feasibility assessment and dependency closure (**step 0**) | `portgraph/portgraph.py` | analyze verdict + closure check | portgraph SQLite + assessment report | §2.2 of this page + [portgraph/README](../portgraph/README.md) |
| 3 | app-porter (qt-app-porting) | End-to-end application migration | `tools/qt-ohos-run.py` | verify **G0-G12** | The target project's `.qt-ohos/` | [skills/qt-app-porting](../skills/qt-app-porting/SKILL.md) |
| 4 | sdk-forge (qt-sdk-forge) ★split out | Qt SDK builds/patches/version management | `tools/qt-sdk-run.py` | verify **SV0-SV8** | `workspace/qt-sdk/.qtsdk/` | [skills/qt-sdk-forge](../skills/qt-sdk-forge/SKILL.md) |
| 5 | framework-analyst | Four-phase framework issue analysis | Reuses the porter CLI (demo/logs) | Evidence gate `evidence_type` | Analysis workspace + tickets | §2.2 of this page + [framework-issue-analysis](../procedural/framework-issue-analysis.md) |
| 6 | test-verifier | Run tests / fix regressions / test case closed loop | Reuses the porter CLI build/smoke | All cases pass / regression passes | Test workspace | §2.2 of this page + [qt-ohos-run-test](../procedural/qt-ohos-run-test.md) |
| 7 | kb-iterator | Editor-in-chief merging, index regeneration, evolution review | `tools/faults-build.py` etc. | check ERROR=0 + the editor's six steps | `faults/_drafts/` + `knowledge/drafts/` | [skills/kb-iterator](../skills/kb-iterator/SKILL.md) |
| 8 (optional) | demo-builder | The standalone demo six-step closed loop | — | Build + run verification | Demo project directory | [demo-generation](../procedural/demo-generation.md) |
| 9 (optional) | bug-reporter | Upstream bug report form A/B | — | Reproducibility HARD gate | Report deliverables | [qt-bug-report-generation](../procedural/qt-bug-report-generation.md) |

Until the optional agents are split out, their capabilities are embedded in app-porter (the [Q] route) and framework-analyst
(phase four of the four-phase workflow) respectively. When to split them: frequent demand for direct demo delivery → split out 8; frequent ticket filing with Qt/Huawei → split out 9.

### 2.2 Interface cards for the three agents without their own SKILL.md

**port-assessor** (the portgraph agent)

- Trigger: **step 0** of any "port/migrate/assess feasibility" task (a prerequisite of routes [A]/[P]; [M] third-party library consulting)
- Inbound: `task-order` (the app path)
- Outbound: `assessment.json` + deps-report + the fetch-deps closure manifest (type=`assessment` / `deps-manifest`)
- Boundary: analyze only, never modify the target project; **with ≥3 third-party library dependencies, judging each one by hand is forbidden** — the closure analysis output is authoritative
  (proven case: the closure analysis of a large application with 68 dependencies produced the solution of 59 bottles + 9 source builds in one go)

**framework-analyst** (the framework issue analysis agent)

- Trigger: the porter's `analyze-log` matched no known pattern and a framework-layer problem is suspected; the user directly reports "the application behaves abnormally and the root cause
  needs locating" ([E]/[F]/[G] deep dives, a new root cause for [R])
- Inbound: `task-order` + log / demo leads
- Outbound: a modification plan ticket (`proposal.yaml` + `patches/` + `notes.md`, dropped into `.qtsdk/inbox/`,
  type=`proposal`); a faults C draft (dropped into `faults/_drafts/`, type=`kb-draft`); an upstream report draft
- Boundary: doesn't rebuild Qt (forge's job), doesn't migrate applications (porter's job); hard requirements for demos:
  **a single-file main.cpp + reproduction steps numbered down to the operation level** (no steps counts as not done)

**test-verifier** (the test verification agent)

- Trigger: running tests is needed after the porter's build/smoke; fix regression after forge produces a new version (linked to faults review);
  the application feature test case closed loop ([qt-app-harmonyos-completion](../procedural/qt-app-harmonyos-completion.md))
- Inbound: `sdk-release` + the verification checklist (C page reproduction steps / test case set)
- Outbound: the verification verdict (a "version verification record" row on the C page, type=`test-verdict`)
- Boundary: test only, never fix — fix actions go back to porter / analyst / forge

> When these three agents are split into independent instances: copy the interface card from this page + the key points of the corresponding knowledge page into their own SKILL.md,
> and fill in the definition file link in the roster table.

### 2.3 Deliverable matrix

| from → to | type | Carrier (format) | Status |
|-----------|------|-------------|------|
| dispatcher → first agent | `task-order` | ho envelope + routing code | New |
| port-assessor → dispatcher/porter | `assessment` | `assessment.json` + deps-report.md | ✅ portgraph already has it |
| port-assessor → porter | `deps-manifest` | fetch-deps manifest + source gap list | ✅ Exists |
| framework-analyst → sdk-forge | `proposal` | `proposal.yaml` + `patches/` + `notes.md` (inbox protocol) | ✅ Exists |
| sdk-forge → porter/verifier | `sdk-release` | `manifest-<ver>.yaml` + ENV pointer | ✅ Exists |
| test-verifier → analyst/forge | `test-verdict` | A "version verification record" row on the C page | ✅ Exists |
| any → kb-iterator | `kb-draft` | `faults/_drafts/draft-*.md` or a QOH/R draft | ✅ Exists |
| business agent → dispatcher | `task-report` | qt-ohos-run report / each agent's own report | ✅ Exists |
| dispatcher → kb-iterator | Closing handoff | The full flow.jsonl + the draft list | New |

## 3. Task ledger and flow log

`workspace/tasks/` (gitignored runtime state, created by task-dispatcher on first use):

```
workspace/tasks/
└── TSK-YYYYMMDD-NNN/
    ├── task.yaml          # ledger: created/maintained by the dispatcher
    ├── flow.jsonl         # flow log: append-only; whoever executes writes
    ├── handoffs/
    │   └── ho-NNN.yaml    # handoff envelope (one per cross-agent delivery)
    └── reports/           # user-facing task reports (optional)
```

### task.yaml (the ledger)

```yaml
id: TSK-20260923-001
title: HarmonyOS migration of some Qt application v1.0
status: in-progress      # created | in-progress | waiting-human | blocked | closed
created: 2026-09-23
route: "[A]+[P]"         # the _task-routing routing code(s) matched
agents: [port-assessor, app-porter, framework-analyst, sdk-forge, test-verifier]
handoffs: [TSK-20260923-001/handoffs/ho-001.yaml]
deliverables: []         # pointers to key deliverables (paths in each state plane, no copied content)
kb_distilled: []         # filled in by kb-iterator on closing: C-xxxx / QOHxxx / episodic page ids
```

### flow.jsonl (the flow log)

One JSON object per line, **append-only, never rewritten**. The event enumeration and the seven fixed write points:

| event | Write point | Required fields |
|-------|------|---------|
| `task-created` | dispatcher creates the record | task |
| `handoff-in` / `handoff-out` | Accepting / handing off | to / from + artifact + refs |
| `gate` | Machine gate verdict | gate + verdict (copied only from machine output) |
| `anomaly` | Anomalies, unexpected behavior | reason |
| `budget-exhausted` | Task budget exhausted (checkpoint written) | budget |
| `human-required` | **Human involvement** (see §5) | reason + options |
| `draft-produced` | A knowledge draft was produced | artifact + refs |
| `task-closed` | Closing the task | distilled |

Example:

```jsonl
{"ts":"2026-09-23T10:05:00+08:00","agent":"port-assessor","event":"gate","gate":"analyze","verdict":"portable","artifact":"assessment.json","refs":["TSK-20260923-001"]}
{"ts":"2026-09-23T13:10:00+08:00","agent":"framework-analyst","event":"handoff-out","to":"sdk-forge","artifact":"handoffs/ho-001.yaml","refs":["C-0003","QOH012"]}
{"ts":"2026-09-23T13:30:00+08:00","agent":"app-porter","event":"human-required","reason":"Signing certificate and password (H2)","options":["Provide the certificate path","Skip installation and stop at G5"],"refs":["TSK-20260923-001"]}
```

### ho-NNN.yaml (the handoff envelope, generalized from sdk-forge's inbox protocol)

```yaml
id: ho-001
task: TSK-20260923-001
from: framework-analyst
to: sdk-forge
type: proposal      # task-order | assessment | deps-manifest | proposal | sdk-release | test-verdict | task-report | kb-draft
artifact: workspace/qt-sdk/.qtsdk/inbox/prop-20260923-001/proposal.yaml
refs: [fault-C-0003, QOH012, TSK-20260923-001]
verdict: null       # pass | fail | partial (the machine gate verdict; required if there is one)
next: sdk-forge.forge
```

## 4. Task flow (three chains)

**The porting chain** (the main chain):
dispatcher creates the record → port-assessor step 0 (**if blocked, stop and produce the report**, H1 ruling) → app-porter
(shell project + adaptation + tracked modifications; on build failure run `analyze-log` first and self-fix known matches) → no match and a suspected framework
problem → framework-analyst (reproduction demo → root cause → characterization) → rebuild needed for verification → sdk-forge (proposal →
SV gates → test version) → test-verifier regression → app-porter re-verification → G0-G12 PASS → task-report +
drafts → dispatcher closes and hands off to kb-iterator.

**The issue chain**: user-observed symptom → dispatcher → framework-analyst (four phases) → C draft + upstream ticket material →
kb-iterator editor-in-chief gate promote (rebuild verification goes through sdk-forge, verification goes through test-verifier).

**The evolution chain** (periodic): sdk-forge `upstream-check` evolution report → kb-iterator (`faults review`
due reviews → version baseline table bump → disposing of superseded patches requires forge to produce a new version).

## 5. Human touchpoints (HITL)

### Level definitions

| Level | Meaning | Agent behavior |
|------|------|-----------|
| **H1 blocking decision** | Must stop and wait for a human ruling before continuing | Write a `human-required` log entry; task.status → `waiting-human`; present the options |
| **H2 human execution** | A physical/environment operation the agent can't do on the human's behalf | Explain the action needed, wait for the human to complete it, record the result, and continue |
| **H3 review and confirmation** | The agent can produce first, but the output must be confirmed by a human before it moves to the next hop | Present the output together with the review points; nothing moves on until confirmed |

### Human touchpoints for each agent

**task-dispatcher**

| Level | Trigger condition |
|------|---------|
| H3 | An ambiguous request can't be routed uniquely: offer the 3 most likely options for the user to choose (following the ambiguous request discipline of _task-routing) |
| H1 | The ruling after port-assessor judges blocked: give up / reduce scope / invest in a source port |
| H1 | Whether to continue after `budget-exhausted` (checkpoint written) |
| H1 | Resource conflict (concurrent use of the same forge home): switch to a separate home or queue |

**port-assessor**

| Level | Trigger condition |
|------|---------|
| H1 | analyze=blocked: the blocker review conclusion (hard block vs. trimmable branch) + options handed to the user for a ruling |
| H1 | unknowns source build gaps: report the effort item by item; only proceed to the porter after the user confirms acceptance |
| H3 | Version requirement conflict / incomparable cross-name constraints: human confirmation |

**app-porter**

| Level | Trigger condition |
|------|---------|
| H2 | Signing certificate and password: the human provides them while staying at the machine; never written to disk, never held in custody |
| H3 | Non-allowlisted modifications (especially `Q_OS_LINUX` guards — on HarmonyOS `Q_OS_OHOS` implies `Q_OS_LINUX`): patch only after human review |
| H1 | verify=FAIL and the error matches no known pattern: whether to hand over to framework-analyst for the issue chain |
| H2 | One-click mode `project_generation` (shell project creation) pauses and gives guidance |

**sdk-forge**

| Level | Trigger condition |
|------|---------|
| H2 | The Qt 6.12 prebuilt installer (requires an interactive login install; the agent doesn't download it): prompt the user to install manually, then register with `config set` |
| H2 | Credentials for cloning the commercial source: provided by the user, kept in memory only and never written to disk |
| H1 | Official release (`--type release`; switching the ENV pointer affects all downstream consumers) |
| H1 | What to do after the release gate rejects a diagnostic patch: revert / produce a test version instead |
| H1 | Retiring a patch after a superseded review passes + producing a new version without that patch |
| H2 | The human verification result of the SV7 smoke test (what `smoke-mark` records is a human conclusion) |
| H1 | Submitting patches upstream (this skill doesn't do it; a human submits after `patch-export`) |

**framework-analyst**

| Level | Trigger condition |
|------|---------|
| H3 | Characterization and layer attribution (nature / responsible): create the C draft only after human verification (final review at the kb-iterator editor-in-chief gate) |
| H1 | Before sending a modification plan ticket (proposal): human review of the plan |
| H1 | Submitting upstream issues: a human submits after the qt-bug report form A/B is generated; the agent doesn't submit on their behalf |
| H2 | Intermittent / environment-specific issues: the user provides the trigger scenario, hardware, and account |
| H3 | Sanitizing logs and demo material (before making them public) |

**test-verifier**

| Level | Trigger condition |
|------|---------|
| H2 | Human verification of UI behavior on a real device (the "manual verification" step of framework-fix-verification; smoke only checks the crash window, observing behavior takes a human) |
| H3 | AI-generated test cases must be reviewed by a human before execution (matching qt-app-harmonyos-completion's "AI scans the source + human review") |
| H3 | Human confirmation before the verification verdict is recorded in the C page's "version verification record" |

**kb-iterator** (the agent with the most human involvement)

| Level | Trigger condition |
|------|---------|
| H3 | Step 3 of the editor-in-chief gate, **human verification** (mandatory): evidence chain / characterization / layer attribution / severity calibration / version and ticket facts (better missing than fabricated) / sanitization |
| H1 | promote (deleting the draft, writing to the source of truth) and rejected / returned rulings |
| H1 | Recharacterization (undetermined → defect / limitation; the CID stays the same) |
| H1 | Version baseline table bump (the tail table of AGENTS.md / CLAUDE.md) |
| H2 | Scenarios in the mandatory reproduction demo tests that need human observation on a real device |

**demo-builder (optional)**: H2 checking the result on a real device;
**bug-reporter (optional)**: H1 the submission action is always manual (after the reproducibility HARD gate self-check passes).

### General red lines (the same for every agent, highest priority)

1. **Credentials / accounts / payments / external submissions** (QTBUG, Huawei issues, partner deliverables) → always manual; the agent only prepares the material.
2. **Official releases, deletions / rollbacks** (promote deleting drafts, patch revert), **ENV pointer switches** → executed only after human confirmation.
3. **Gate semantics must never be upgraded**: PARTIAL ≠ PASS, TIMEOUT ≠ PASS, and an SV7 SKIP can only be reported as "usable at build level".
4. **No characterization without evidence** (the evidence gate `evidence_type`); content made public (`audience: public`) is sanitized under human control.
5. Every human involvement writes a `human-required` trail; after the human decides, the result is recorded naturally by the follow-up event (gate / handoff-out).

## 6. Concurrency contract

- Follow the contract already proven in `.qtsdk/`: **file locks** (`<file>.lock`) + **atomic replacement** (tmp + `os.replace`).
- `flow.jsonl` appends (line-level append) are naturally concurrency-safe; changes to `task.yaml` / `ho-*.yaml` go through the lock.
- Only one forge process runs at a time per forge home; run in parallel with separate homes (`QT_SDK_HOME` / `--home`).
- `workspace/` is gitignored as a whole — the task ledger is runtime state, and captured knowledge enters the repo via drafts.

## 7. Relationship with the knowledge base planes

| Plane | Carrier | What this protocol adds |
|------|------|-------------|
| Task Router | `_index/_task-routing.md` | The dispatcher's routing core (nothing added) |
| Knowledge | `semantic/` `procedural/` `episodic/` `problems/` `faults/` | Nothing added |
| Execution | `tools/qt-ohos-run.py` `tools/qt-sdk-run.py` `portgraph/` | Nothing added (the CLIs are unchanged) |
| State | `.qt-ohos/` `.qtsdk/` | Nothing added |
| Verification | G0-G12 / SV0-SV8 / faults check | Nothing added |
| Learning | `knowledge/drafts/` `faults/_drafts/` | Nothing added |
| **Task Ledger (new)** | `workspace/tasks/` | task.yaml + flow.jsonl + ho envelopes; the dispatcher creates records, each agent appends, kb-iterator consumes |

## 8. Implementation status (2026-09-23)

- [x] `_index/_agent-mesh.md` (this page): the single source of truth for the contract
- [x] `skills/task-dispatcher/SKILL.md`, `skills/kb-iterator/SKILL.md`: definitions of the two new agents
- [x] `qt-app-porting` / `qt-sdk-forge` SKILL.md: added interface and human touchpoint sections
- [x] Registered in the AGENTS.md skills table; pointer hooked into _task-routing.md
- [x] **Internal dispatch platform integration (smoke-tested)**: the 7 agents are registered on the internal Multica platform and form an
  "application HarmonyOS porting" squad (captain task-dispatcher + 6 members). An issue can be assigned straight to the squad; once woken, the captain
  orchestrates **stage subtasks** along the porting chain (the captain is woken only when every task in a stage completes — the stage barrier semantics map natively onto
  the porting chain in §4): stage1 assessment (port-assessor) → stage2 migration (app-porter) → stage3 verification
  (test-verifier); a conditional branch (framework-analyst → sdk-forge → regression); a closing stage of
  knowledge distillation (kb-iterator). The squad-level instructions contain the same collaboration conventions.
  (The specific IDs of the platform / runtime / agents / squad are internal deployment information and aren't checked in)
- [ ] When port-assessor / framework-analyst / test-verifier are split into independent instances, generate each one's SKILL.md from the §2.2 interface cards
- [ ] The optional demo-builder / bug-reporter aren't split out yet (capabilities embedded; see §2.1)
