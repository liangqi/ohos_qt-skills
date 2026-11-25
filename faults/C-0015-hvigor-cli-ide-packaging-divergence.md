---
id: fault-C-0015
cid: C-0015
type: cause
title: hvigor CLI (--mode module) packaging is not equivalent to DevEco IDE packaging (incomplete NAPI module registration makes the HAP crash at startup)
nature: undetermined
domain: deploy
fault_type: crash
responsible: ohos-toolchain
co_responsible: []
component: "hvigor CLI (--mode module) packaging flow × DevEco Studio IDE packaging flow (NAPI module registration / .so dependency chain)"
severity: medium
evidence_type: logs
status: diagnosed
fix_route: "If classified as defect: the DevEco toolchain fixes NAPI module registration and dependency chain handling in CLI packaging, arriving with a DevEco / hvigor update; if classified as limitation: find the official CLI packaging contract and complete the command-line flow's configuration accordingly"
review_note: "The specific mechanism of the CLI vs IDE difference is to be investigated (the NAPI module registration step); reclassification (defect: toolchain defect / limitation: packaging contract / app: CLI usage); impact assessment for CI/CD"
depends_on: []
affects_qt: ["Qt 5.15.16 (source page environment; still crashes after reverting to an unpatched libqohos.so, ruling out Qt code)"]
affects_ohos: ["not recorded (hvigor CLI / DevEco Studio versions not recorded in the source page)"]
qoh: []
first_seen: 2026-08-06
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [harmonyos, hvigor, cli, hap, packaging, napi, deveco, ide, undetermined, workaround, cicd]
audience: public
refs: [problem-deploy-fail-hvigor-cli-hap-crash, semantic-qt-harmonyos-build-run-workflow, semantic-qt-harmonyos-project-structure]
summary: >
  A HAP packaged with the hvigor CLI (--mode module) crashes at startup (Cannot read property
  'handleAbilityStageOnCreate' of undefined), while DevEco Studio IDE Run works; reverting to an unpatched
  libqohos.so still crashes, ruling out Qt code changes. Root cause direction: a difference between the CLI and IDE packaging flows
  (incomplete NAPI module registration on the CLI side; the specific difference is to be investigated). undetermined/ohos-toolchain
  (diagnosed, awaiting defect/limitation classification); workaround W-0013 (use IDE Run instead) is
  verified; no tracking ticket yet (placeholder T-0008).
---

# C-0015 hvigor CLI packaging is not equivalent to DevEco IDE packaging

> nature: undetermined (leaning toolchain side) | responsible: ohos-toolchain | status: diagnosed | symptoms: S-0014 | workarounds: W-0013 | tickets: none yet (placeholder T-0008) | review: 2026-12-15

## Symptoms

### S-0014 HAP packaged by the hvigor CLI (--mode module) crashes at startup; DevEco IDE Run works

The verbatim error (source page [deploy-fail-hvigor-cli-hap-crash](../problems/deploy-fail-hvigor-cli-hap-crash.md)):

```
Cannot read property 'handleAbilityStageOnCreate' of undefined
at QAbilityStage.ets
```

Packaging the HAP on the command line with `hvigor --mode module` → install → crashes at startup; the same project deployed with DevEco
Studio IDE Run works.

## Root cause / classification basis

Controlled experiment (recorded in the source page):
1. the HAP packaged by the CLI crashes at startup (verbatim error above);
2. **reverting libqohos.so to the unpatched version → still crashes** -- ruling out Qt code changes;
3. deploying with DevEco Studio IDE Run → works.

→ Root cause direction: **the hvigor CLI packaging flow differs from the DevEco Studio IDE packaging flow** -- CLI
packaging leaves NAPI module registration incomplete; IDE packaging handles NAPI module registration and the .so dependency chain correctly.
**The specific step that differs is still to be investigated** (stated explicitly in the source page).

**Classification status**: the behavior is established empirically (CLI crashes / still crashes after revert / IDE works); whether "this is a toolchain defect
(defect: the CLI should handle it correctly but doesn't) or an official contract/usage requirement of command-line packaging
(limitation: the CLI needs extra configuration)" has no basis for classification yet (the source page has no official documentation to back either).
Leaning toolchain side -- the same project's outputs from the two channels aren't equivalent and the CLI output crashes. Reclassify after verifying the official CLI packaging
contract; the CID stays the same.

## Responsibility

`ohos-toolchain` (the hvigor CLI / DevEco Studio packaging chain; initial judgment). Qt code changes are ruled out
(revert experiment); no action on the Qt side. If it turns out to be a CLI usage/configuration requirement, reclassify as responsible=app
(Application usage issue; the disposition becomes "change the usage").

## Permanent fix (if classified as defect)

The DevEco toolchain fixes NAPI module registration and .so dependency chain handling in CLI packaging so that CLI and IDE
outputs are equivalent -- arriving with a DevEco Studio / hvigor update (a ticket with Huawei is needed to track it).

## Alternatives and evolution (if classified as limitation)

Find the configuration items the CLI packaging contract requires (module registration / dependency declarations), complete the command-line packaging flow per the contract,
and document the difference for CI/CD. Evolution watch: official statements from the DevEco toolchain on "CLI and IDE packaging equivalence".

## Workarounds

- **W-0013 (tested, verified 2026-08-06)**: drop hvigor CLI packaging and deploy directly with DevEco
  Studio IDE Run (Build → Run) -- the IDE packaging flow handles all module registration correctly.

  Cost: **unusable for CI/CD automation** (command-line packaging is a pipeline staple); the daily development workflow
  is tied to the IDE.
  Retirement condition: once the hvigor CLI packaging difference is identified and fixed (or the CLI offers configuration equivalent to IDE packaging),
  return to command-line packaging and rerun the startup test.

## Tickets

None yet (the source page has no ticket number). **Placeholder T-0008**: if the difference turns out to be a toolchain defect and an issue is filed with Huawei/DevEco,
open it as T-0008 (tracker=ohos-issue or gitee); if it is a CLI usage contract,
no ticket is needed and this section records the official documentation link instead.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-08-06 | OHOS + hvigor CLI (--mode module) + Qt 5.15.16 | HAP packaged by the CLI crashes at startup (verbatim error); still crashes after reverting to an unpatched libqohos.so; IDE Run works (control) | Ruled out Qt code changes; pinned down the CLI vs IDE packaging difference (incomplete NAPI module registration) | → diagnosed |

## Related

- Symptoms (S): S-0014
- Workarounds (W): W-0013
- Tickets (T): none yet (placeholder T-0008)
- problems: [deploy-fail-hvigor-cli-hap-crash](../problems/deploy-fail-hvigor-cli-hap-crash.md) (error lookup, controlled experiment record)
- semantic: [qt-harmonyos-build-run-workflow](../semantic/qt-harmonyos-build-run-workflow.md), [qt-harmonyos-project-structure](../semantic/qt-harmonyos-project-structure.md)
- Related causes (C, including depends_on notes): none
