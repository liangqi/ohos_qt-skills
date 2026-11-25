---
id: fault-C-0010
cid: C-0010
type: cause
title: "The stale glue template lacks @ohos.* eager import registration, so libqohos's bare eval is rejected by the ArkTS runtime (onAcceptWant crash)"
nature: defect
domain: runtime
fault_type: crash
responsible: qt-port
co_responsible: []
component: "qtbase/src/harmonyos/templates OhosExportModules.ts / QtUtils.ets (stale minimal version) × libqohos 515-generation qohosjsmain.cpp initDeviceInfo × ArkTS runtime libark_jsruntime.so"
severity: critical
evidence_type: both
status: workaround
fix_route: "On the Qt side, update the template in the same batch as libqohos (eager default-import list aligned + objects API); arrives with the harmonyos-5.15.16 branch / the next Qt OHOS SDK"
review_note: "Check whether the harmonyos-5.15.16 template has switched to the complete OhosExportModules (eager import list aligned with libqohos); whether the 7/14-generation sibling issue should get an edge to this C is pending a decision; before sending the ticket out, add run logs of the pure HarmonyOS control demo"
depends_on: []
affects_qt: ["Qt 5.15.16 (libqohos 515 generation built 2026-07-17; source-tree template version 2026-04-21)"]
affects_ohos: ["HarmonyOS 6.0.0.29 (HUAWEI MateBook Fold HPR-W72 real device)"]
qoh: [QOH009]
first_seen: 2026-07-23
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [qt, harmonyos, crash, arkts, ohos-deviceinfo, bare-eval, known-module-path, OhosExportModules, QtUtils, stale-template, eager-import, onAcceptWant, objects-api, workaround]
audience: public
refs: [problem-runtime-crash-ohos-deviceinfo-global-expression, procedural-qt-bug-report-sample, problem-runtime-crash-libqohos-libqt5core-version-mismatch, procedural-demo-generation, semantic-qt-harmonyos-project-structure]
summary: >
  The source-tree template (4/21) is older than libqohos (7/17): OhosExportModules.ts has only 5 @kit.* lazy
  imports and no @ohos.* eager import at all, so libqohos's startup-time jsState.eval("@ohos.deviceInfo")
  bare global expression eval is rejected by the ArkTS runtime as "not a known module path", and the uncaught Napi::Error makes
  onAcceptWant crash (the factories/objects API mismatch also silently drops the @kit.* modules). defect/
  qt-port (triage decided by a human; not a system bug); W-0008 (replace 4 files with the complete reference template)
  is verified on a real device; no tracking ticket yet.
---

# C-0010 The stale glue template lacks @ohos.* eager imports

> nature: defect | responsible: qt-port | status: workaround | symptoms: S-0009 | workarounds: W-0008 | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0009 Qt5 HarmonyOS app crashes when onAcceptWant fires (the @ohos.deviceInfo bare eval is rejected)

- The signed HAP installs fine, and after `aa start` the app starts normally (the Qt window appears, QtWatchdog runs); the process can stay alive for minutes -- **it does not crash at startup**;
- when `onAcceptWant` fires (multi-instance launch / window recreate / a second QApplication construction) the process crashes, every time the trigger condition is met;
- faultlog `LAST_FATAL_MESSAGE`: `terminating due to uncaught exception of type Napi::Error: global expression doesn't start with known module path: '@ohos.deviceInfo'` (SIGABRT);
- crash stack: `MainThread::HandleScheduleAcceptWant → JsAbilityStage::OnAcceptWant → initQtAppContextIfNeeded → initQtAppContextImpl (QAbilityStage.ets) → qpa.setupQtApplication({modules}) → libqohos initAppData → initDeviceInfo → jsState.eval("@ohos.deviceInfo")`.

## Root cause / classification basis (faultlog + strings criteria + pure HarmonyOS control, triage decided)

Three layers of root cause (from the surface inward):

1. **The error comes from the ArkTS runtime (libark_jsruntime.so), not libqohos** -- the text `global expression doesn't start with known module path` is not found by strings in libqohos.so. For a **bare global expression eval** starting with `@ohos.`, the ArkTS runtime only lets through modules that have been registered as a "known module path" by an eager import, and otherwise throws Napi::Error; libqohos (515 generation, `qohosjsmain.cpp:1677`) runs `jsState.eval<QNapi::Object>("@ohos.deviceInfo")` at startup to fill the QOhosDeviceInfo cache, and the exception is uncaught → SIGABRT.
2. **The stale minimal template lacks the registration** -- the `OhosExportModules.ts` copied from `qtbase/src/harmonyos/templates` (source tree, 4/21) has only 5 `@kit.*` **lazy** imports and no `@ohos.*` import at all; the template predates libqohos (7/17) → `@ohos.deviceInfo` and others are not registered → the bare eval is rejected. Note that `import lazy` (deferred loading) doesn't register startup-time known paths either; the fix must use **eager default-imports**.
3. **API form mismatch (also breaks @kit.*)** -- the stale template's `QtUtils.ets` uses the factories API (`getOhosExportModulesFactories()` returns arrow factories, storing function references), while the 515-generation libqohos uses the objects API (reads the `"modules"` field; `makeJsModulesMap` checks `IsObject()` on each value) → an arrow function is a napi_function, not a napi_object → the entries are **silently dropped**, and @kit.* + LocalStorage + QEmbeddedComponentCreator are all lost (potential UI Extension / LocalStorage failures).

Diagnostic criteria (reusable):

- Determine the generation: `strings libqohos.so | grep "global expression"` -- not found = 515 generation (thrown by ArkTS, this page); found = the newer 7/14 generation (thrown by libqohos, the sibling issue, error text `object has no property named 'deviceType'`);
- determine the API: `strings libqohos.so | grep -E "^modules$|^modulesFactories$"` -- `modules` = objects / `modulesFactories` = factories; the .ets side must match.

Triage conclusion (bug report sample, recorded with the human-signed wording): **owned by the Qt framework, not a system bug** -- ① the error text comes from the ArkTS runtime, and the design of the pure HarmonyOS control demo (controls A/B) shows that "rejecting unregistered bare eval" is unrelated to Qt and consistent with the module resolution security restrictions (the official documentation only covers eager import usage); ② the actual defect is the stale template on the Qt side (4/21 predates 7/17).

Evidence form: `both` -- the Qt repro project (qapp-recreate-test; the bug report sample includes 3 numbered repro steps and the build/run commands) + faultlog (cppcrash-60469: LAST_FATAL_MESSAGE + stack) + strings binary criteria. Note: the pure HarmonyOS control demo (ohos-repro/) has its control design settled but **has not been built and run yet** (recorded in the sample's self-check); run logs are needed before the ticket goes out.

## Responsibility

`qt-port` -- the defect is in a deliverable of the Qt HarmonyOS port: the glue template in `qtbase/src/harmonyos/templates` is not updated in the same batch as libqohos and doesn't provide `@ohos.*` eager import registration for libqohos's startup-time bare eval. Fix route: template update on the harmonyos-5.15.16 branch / the next Qt OHOS SDK. The ArkTS runtime rejecting unregistered bare eval is specified behavior (for the Huawei side the bug report only carries a documentation improvement suggestion, not a defect ticket).

## Permanent fix (defect)

Suggestions to Qt upstream (tqtc):

1. Update the `OhosExportModules.ts` / `QtUtils.ets` templates **in the same batch** as libqohos builds, with an eager default-import list covering every `@ohos.*` / `@kit.*` module root that libqohos actually evals;
2. a build-time script `strings libqohos.so | grep -E "^@ohos\.|^@kit\."` generates the list automatically to align the template and prevent it from going stale again;
3. the template's default API form matches the field libqohos consumes (`modules` = objects / `modulesFactories` = factories).

## Workarounds

- **W-0008 (adopted, verified 2026-07-23 on a real device)**: replace the 4 glue files with the designated complete reference template:
  1. `entry/src/main/ets/qability/OhosExportModules.ts` ← the complete reference template: 26 `import __ohos__X from '@ohos.X'` (eager default-imports covering deviceInfo/display/window/font/resourceManager/i18n/intl/settings/...) + 13 `@kit.*` eager imports; `getOhosExportModules()` returns a **plain object** (not an arrow factory);
  2. `entry/src/main/ets/qability/QtUtils.ets` ← the complete reference template: `getModulesMapForQt()` calls `getOhosExportModules()` + `getLocalStorageTsInterface()` + `getQEmbeddedComponentCreatorTsInterface()` (**calling them to get objects**, not storing function references);
  3. `QAbilityStage.ets` / `QChildProcess.ets`: `getModulesFactoriesMapForQt()` → `getModulesMapForQt()` (rename at 2 call sites; keep the resourceDir in QAbilityStage);
  4. rebuild `build_project(entry@default, debug)` → install on the device → trigger onAcceptWant → no crash and QtWatchdog keeps running = the fix works.

  Cost: after a libqohos generation change (rebuild), rerun `strings libqohos.so` to align the `@ohos.*`/`@kit.*` list, otherwise evals of newly added modules still crash; every project generated from the source-tree template needs the replacement.
  Retirement condition: once the Qt source-tree template is updated in the same batch as libqohos (eager import list aligned), go back to using the official template directly and drop the 4-file replacement.

## Tickets

- None yet (no evidenced ticket number). The bug report is written ([qt-bug-report-sample](../procedural/qt-bug-report-sample.md); triage conclusion: owned by the Qt framework): for the Huawei side it was downgraded to a documentation improvement suggestion (whether to send it out awaits human sign-off; not a defect ticket); the template fix suggestion to tqtc has not been submitted. Before filing, add the run logs of the pure HarmonyOS control demo per the reproducibility HARD gate.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-07-23 | Qt 5.15.16 (515-generation libqohos, built 7/17) / HarmonyOS 6.0.0.29 (MateBook Fold real device) | Reproduced by triggering onAcceptWant with qapp-recreate-test; collected faultlog + strings criteria | cppcrash-60469: LAST_FATAL_MESSAGE matches, stack reaches `jsState.eval("@ohos.deviceInfo")`; strings doesn't find the error text → 515 generation | → open |
| 2026-07-23 | Same as above | Replaced the 4 files with the complete reference template, rebuilt and installed, triggered onAcceptWant again | No crash, QtWatchdog keeps running (shot-after-fix.png) | → workaround |

(Sources for the historical facts: the evidence/deliverables of [runtime-crash-ohos-deviceinfo-global-expression](../problems/runtime-crash-ohos-deviceinfo-global-expression.md) and [qt-bug-report-sample](../procedural/qt-bug-report-sample.md); when the editor merges, register the review reproduction in the first row of this table per the gate.)

## Related

- Symptoms (S): S-0009
- Workarounds (W): W-0008
- Tickets (T): none yet
- problems: [runtime-crash-ohos-deviceinfo-global-expression](../problems/runtime-crash-ohos-deviceinfo-global-expression.md), [runtime-crash-libqohos-libqt5core-version-mismatch](../problems/runtime-crash-libqohos-libqt5core-version-mismatch.md) (the 7/14-generation sibling issue, same fix direction)
- procedural: [qt-bug-report-sample](../procedural/qt-bug-report-sample.md) (triage reasoning chain and deliverables list), [demo-generation](../procedural/demo-generation.md) phase 3, 3.2 (source-tree template pitfall checkpoint)
- semantic: [qt-harmonyos-project-structure](../semantic/qt-harmonyos-project-structure.md) (where the HarmonyOS project template comes from)
- QOH (machine layer): QOH009 (ohos_deviceinfo_global_expression)
- Related causes (C): none (the 7/14-generation sibling issue is not in the graph; whether to add an edge to this C or create a separate C awaits the editor's decision)
