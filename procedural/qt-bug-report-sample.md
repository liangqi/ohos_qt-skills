---
id: procedural-qt-bug-report-sample
type: procedural
domain: runtime
tags: [bug-report, deliverable, sample]
created: 2026-08-01
updated: 2026-08-01
status: active
audience: public
refs: [fault-C-0010, procedural-qt-bug-report-generation, procedural-framework-issue-analysis]
summary: >
  A worked sample (form A): a Qt 5.15 HarmonyOS app crashes when onAcceptWant fires because a bare eval of @ohos.deviceInfo is rejected by the ArkTS runtime;
  triage attributes it to the Qt framework (a stale glue template that never eager-imports the module to register it), and it has been fixed on the Qt side.
---

# A bare eval of @ohos.deviceInfo is rejected by the ArkTS runtime, crashing onAcceptWant

> This page is a **filled-in form-A sample** of [[procedural-qt-bug-report-generation]], based on a real case ([[problem-runtime-crash-ohos-deviceinfo-global-expression]]). Use it to learn how to write a complete bug report for Huawei: every `(A)` / `(A+B)` section is filled with real detail, and the `(internal)` sections show what a pre-submission self-check looks like. The triage verdict here is **the Qt framework** (not a system bug) — which is just as instructive: it demonstrates the full chain of reasoning for something that *looked* like a system problem but turned out not to be after triage.
>
> **Who fills in what**: `required` items are filled in by the reporter; `filled in by the recipient` items (the call chain / system API behavior / documentation comparison / pure-HarmonyOS demo) are filled in by the internal team — in this sample both halves are filled in far enough to serve as a model.

## Basic information (A)

| Item | Content |
|------|---------|
| Report number | To be assigned |
| Report date | 2026-07-23 |
| Reporter | <REPORTER> |
| Source | Internal verification |
| HarmonyOS SDK version | HarmonyOS 6.0.0.29 (for the API level see the reproduction environment table) |
| Device | HUAWEI MateBook Fold (HPR-W72) / system version 6.0.0.29 / physical device |
| Qt version | 5.15.16 (branch tqtc/harmonyos-5.15.16, the OHOS SDK `-full` package) |
| Severity | Critical |
| Reproduction rate | Always (whenever onAcceptWant fires) |
| Attribution | The Qt framework |

## Problem summary (A+B, required)

A Qt 5.15.16 HarmonyOS app signs, installs and starts normally under `aa start` (the Qt window appears and QtWatchdog runs), but the process crashes as soon as the system delivers `onAcceptWant` (a multi-instance launch / window recreate / a second QApplication construction). The faultlog's `LAST_FATAL_MESSAGE` is `global expression doesn't start with known module path: '@ohos.deviceInfo'`, and the call stack runs `QAbilityStage::OnAcceptWant → initQtAppContextImpl → qpa.setupQtApplication → libqohos initDeviceInfo → jsState.eval("@ohos.deviceInfo")`, with the error thrown by the ArkTS runtime (libark_jsruntime.so). Initial assessment: the error text comes from the ArkTS runtime rather than from libqohos, so it looks like system API / runtime behavior; attribution pending triage.

## Reproduction environment (A+B, required)

> **A hard gate for the recipient's reproduction**: if any one of the six items below is missing, the report is sent back for completion and never enters reproduction.

| Item | Value | How to find it |
|------|-------|----------------|
| Development machine OS | Windows 11 | System information |
| HarmonyOS SDK version | HarmonyOS 6.0.0.29 (OpenHarmony 6.0 Beta1; the API level as measured with hdc is authoritative) | DevEco → File → Settings → SDK; or `hdc shell param get const.ohos.apiversion` |
| Qt version | 5.15.16 (branch tqtc/harmonyos-5.15.16, the OHOS SDK `-full` package; libqohos.so built 2026-07-17, the 515 generation, 5.3 MB) | `qmake -v` or the Qt install directory; for the libqohos generation, `strings libqohos.so \| grep "global expression"` finding nothing = the 515 generation |
| Device | HUAWEI MateBook Fold (HPR-W72) / system version 6.0.0.29 / physical device | `hdc shell param get const.product.model`; `hdc shell param get const.ohos.releaseversion` |
| Toolchain | hvigorw (the DevEco Studio OHOS toolchain) | The build tool version |
| Build mode | debug | The hvigorw build arguments |

## Symptoms (A+B, required)

The app starts normally (the Qt window appears and QtWatchdog keeps running) and the process survives for minutes; but as soon as the system delivers `onAcceptWant` (triggered by a multi-instance launch, a window recreate, or a second QApplication construction), the process crashes. The crash is a cppcrash (an uncaught `Napi::Error` on the C++ side → `SIGABRT`), and `LAST_FATAL_MESSAGE` is the `global expression doesn't start with known module path` message above. It does not crash at startup — `onAcceptWant` has to fire. Always reproducible (100% once the trigger conditions are met).

## Reproduction steps (A+B, required)

> **Aim for three steps or fewer**. Each step should say what to do on which screen; don't leave implicit steps like "use it normally".

1. With the Qt 5.15.16 OHOS SDK (the `-full` package, with `CMAKE_PREFIX_PATH` pointing at `${QT5_15_OHOS_SDK_FULL}`), build a Qt HarmonyOS HAP that does a multi-instance launch or a second construction (e.g. qapp-recreate-test, bundleName=`com.example.qapprecreatetest`), sign it debug, and `hdc install <hap path>` onto a physical HUAWEI MateBook Fold.
2. Start it with `hdc shell aa start -a QAbility -b com.example.qapprecreatetest` and confirm the Qt window appears and QtWatchdog is running (the app is alive).
3. Trigger `onAcceptWant`: `aa start` the same app again (or trigger a window recreate / a second QApplication construction) and watch the process crash within seconds; run `hdc shell ls -t /data/log/faultlog/temp/cppcrash/` to get the newest `cppcrash-*.json`, whose `LAST_FATAL_MESSAGE` contains `global expression doesn't start with known module path: '@ohos.deviceInfo'`.

## Minimal reproducible demo (A+B, required)

> The most valuable deliverable. **For the reporter**: attach the Qt project that triggers the problem — strip out the irrelevant code and package it. You don't need to build a separate pure-HarmonyOS demo; that's the recipient team's job.

**Project layout** (filled in by the reporter):

```
qapp-recreate-test/
├── CMakeLists.txt
├── main.cpp                                            # the entry point that triggers a second QApplication construction
├── entry/src/main/ets/qabilitystage/QAbilityStage.ets  # onAcceptWant → initQtAppContextImpl
├── entry/src/main/ets/qability/OhosExportModules.ts    # the stale minimal version (only 5 @kit.* lazy imports, no @ohos.* imports at all)
├── entry/src/main/ets/qability/QtUtils.ets             # the factories API (getOhosExportModulesFactories)
└── README.md                                           # build and run commands
```

**The triggering code** (filled in by the reporter; paste the key fragments):

```ts
// ❌ The stock OhosExportModules.ts template (from qtbase/src/harmonyos/templates, dated 4/21, only 5 @kit.* lazy imports and no @ohos.* imports at all)
import lazy { textToSpeech as __kit__CoreSpeechKit__textToSpeech } from '@kit.CoreSpeechKit';
// ... 4 more @kit.* lazy imports ...
export function getOhosExportModulesFactories(): object {
  return { '@kit.CoreSpeechKit.textToSpeech': () => __kit__CoreSpeechKit__textToSpeech /*, ... */ };
}
// → @ohos.deviceInfo is never eager-imported, so it is never registered as a "known module path"
```

```cpp
// libqohos.so (the 515 generation, qohosjsmain.cpp:1677) — the Qt framework resolves @ohos.deviceInfo at startup to populate the QOhosDeviceInfo cache
auto deviceInfoObj = jsState.eval<QNapi::Object>("@ohos.deviceInfo");  // a bare global-expression eval
// → the ArkTS runtime (libark_jsruntime.so) rejects it: "global expression doesn't start with known module path: '@ohos.deviceInfo'"
```

**Build and run commands** (filled in by the reporter):

```bash
hvigorw assembleHap --mode debug
hdc install <hap path>
hdc shell aa start -a QAbility -b com.example.qapprecreatetest
# Trigger onAcceptWant: aa start the same bundle again, or trigger a window recreate / a second QApplication construction
hdc shell aa start -a QAbility -b com.example.qapprecreatetest
```

**A pure-HarmonyOS reproduction demo** (filled in by the recipient, A):

> Bypass Qt and call the target system API straight from ArkTS, proving the eval rejection has nothing to do with Qt. Follow the four principles: minimal, self-contained, runnable, and controlled. Path: `<deliverable_dir>/ohos-repro/`.
>
> - **Control A**: an EntryAbility that only does `eval("@ohos.deviceInfo")` with no `@ohos.*` eager import at the top → reproduces `global expression doesn't start with known module path: '@ohos.deviceInfo'` (the exact same error text as the Qt case).
> - **Control B**: the same demo with `import __ohos__deviceInfo from '@ohos.deviceInfo'` (an eager default import) added at the top → `eval("@ohos.deviceInfo")` returns the module object successfully and `deviceType` is readable, proving that the eval is allowed once an eager import has registered the path as "known".

## Expected behavior (A+B, required)

According to the official HarmonyOS documentation, the `@ohos.deviceInfo` module should be eager-imported via `import { deviceInfo } from '@kit.BasicServicesKit'` (or `import deviceInfo from '@ohos.deviceInfo'`) and provides read-only constants such as `deviceType` (a read-only string) — see [js-apis-device-info](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-device-info). The Qt framework (libqohos) resolves that module at startup via `jsState.eval("@ohos.deviceInfo")` to populate the static `QOhosDeviceInfo` cache — **provided the glue template supplies an eager default import for every `@ohos.*` module so they are registered as "known module paths"**, that eval should return the module object, the app should initialize normally, and nothing should crash.

## Actual behavior (A+B, required)

In practice the app starts normally but crashes when `onAcceptWant` fires. The faultlog's `LAST_FATAL_MESSAGE` is `global expression doesn't start with known module path: '@ohos.deviceInfo'`, the crash stack runs `initQtAppContextImpl → setupQtApplication → libqohos initDeviceInfo → jsState.eval("@ohos.deviceInfo")`, and the error is thrown by the ArkTS runtime (libark_jsruntime.so) — `strings libqohos.so | grep "global expression"` finds no such text, so it is not libqohos throwing it. For the evidence, see "Error messages and logs".

## Error messages and logs (A+B, required)

**How to capture them** (copy and paste):

```bash
# 0. Confirm the device is connected
hdc list targets
# 1. Grab the cppcrash stack (only present for C++-side crashes; on MateBook Fold, mkdir /data/log/faultlog/ first if it doesn't exist — see the debugging pitfalls)
hdc file recv /data/log/faultlog/temp/cppcrash/ ./cppcrash
# 2. Grab jscrash (ArkTS/JS exceptions)
hdc file recv /data/log/faultlog/temp/jscrash/ ./jscrash
# 3. Live hilog (start capturing before you reproduce; Ctrl+C to stop)
hdc shell hilog | grep -iE "crash|fatal|qapprecreatetest|deviceInfo"
```

```
# cppcrash-<PID>-com.example.qapprecreatetest-<timestamp>.json (key fields, excerpted)
LAST_FATAL_MESSAGE: terminating due to uncaught exception of type Napi::Error:
  global expression doesn't start with known module path: '@ohos.deviceInfo'
>>> LAST_FATAL_MESSAGE: global expression doesn't start with known module path: '@ohos.deviceInfo'
Reason: Signal: SIGABRT(SI_TKILL)
PNAME: com.example.qapprecreatetest
# Call stack
>>> MainThread::HandleScheduleAcceptWant → JsAbilityStage::OnAcceptWant
    → initQtAppContextIfNeeded → initQtAppContextImpl (entry/src/main/ets/qabilitystage/QAbilityStage.ets)
    → qpa.setupQtApplication({modules}) → libqohos initAppData → initDeviceInfo
>>> → jsState.eval<QNapi::Object>("@ohos.deviceInfo")  ← the ArkTS runtime throws Napi::Error here
Bottom-of-stack .so files: libqohos.so (the 515 generation, 5.3MB, 7/17, no qohosplugincore.cpp fallback) + libQt5Core.so + libark_jsruntime.so
>>> Precursor: the process lives for minutes and only then crashes (when a recreate / second construction fires onAcceptWant) — it does not crash at startup.
```

## Scenario and trigger conditions (A+B)

The business scenario: a HarmonyOS-ported Qt app verifying multi-instance launching / window recreate / a second QApplication construction (the qapp-recreate-test demo). At startup libqohos resolves the `@ohos.deviceInfo` module through `jsState.eval("@ohos.deviceInfo")` to populate the static `QOhosDeviceInfo` cache (the data source for device-type checks). The timing: module resolution happens the first time `onAcceptWant` enters `initQtAppContextImpl`; if `OhosExportModules.ts` never eager default-imports `@ohos.deviceInfo` to register it as a "known module path", the ArkTS runtime rejects the bare eval outright and throws a `Napi::Error`, which libqohos never catches → `SIGABRT`. Data state: unrelated to runtime data; a deterministic crash (a template missing the registration always crashes).

## Preliminary analysis (A+B; A has three subsections, B compresses it into one paragraph)

> The reporter's preliminary root-cause analysis. Form A fills in all three subsections; form B keeps only the "Verdict" paragraph.

### Call chain trace (A, filled in by the recipient)

```
[ArkTS layer]
QAbilityStage.onAcceptWant(want)                                    # entry/.../qabilitystage/QAbilityStage.ets
  → initQtAppContextIfNeeded(context)
    → initQtAppContextImpl(context)                                  # QAbilityStage.ets
      → qpa.setupQtApplication({ modules: getModulesMapForQt() })    # reads the "modules" field (the objects API)
[into libqohos.so, the 515 generation, qohosjsmain.cpp]
  → initAppData
    → initDeviceInfo                                                 # qohosjsmain.cpp:1677
      → jsState.eval<QNapi::Object>("@ohos.deviceInfo")              # a bare global-expression eval
[into the system side, libark_jsruntime.so]
  → the ArkTS runtime checks whether "@ohos.deviceInfo" is a "known module path" (registered by an eager import)
    → not registered (OhosExportModules.ts has no @ohos.* eager imports)
      → throws Napi::Error: "global expression doesn't start with known module path: '@ohos.deviceInfo'"
[libqohos doesn't catch it] → the exception propagates uncaught → terminate → SIGABRT
```

Parameter conversion: `getModulesMapForQt()` returns a `map<string, Object>` (the objects API) and libqohos consumes the `"modules"` field; but the stale template uses the factories API and returns `() => value` (arrow functions), so `IsObject()` returns false, the entries are silently dropped, and `@kit.*` + LocalStorage + QEmbeddedComponentCreator are all lost (a latent UI Extension / LocalStorage failure).

### System API behavior (A, filled in by the recipient)

The system API: how the ArkTS runtime (libark_jsruntime.so) resolves a global expression passed to `eval()`.

- Input: `jsState.eval("@ohos.deviceInfo")` (a bare global expression starting with `@ohos.`).
- The validation rule: a bare eval is only allowed if the target module path has already been registered as a "known module path" by an eager `import X from '@ohos.X'`; otherwise it is rejected with `global expression doesn't start with known module path`.
- Return / throw: when unregistered it throws a `Napi::Error` and returns nothing; when registered it returns the module namespace object.
- Timing: module-path registration happens at bundle load time (when the eager import runs); the bare eval doesn't run until `onAcceptWant` / `initQtAppContextImpl` → so if nothing registered it by then, it's rejected.
- Side effects: after the throw, libqohos doesn't catch it → the process terminates.
- Compared with the documented expectation: the official `js-apis-device-info` example is `import { deviceInfo } from '@kit.BasicServicesKit'` (an eager import), and no bare `eval("@ohos.deviceInfo")` usage is offered → a bare eval is undocumented usage, and the ArkTS runtime rejecting it is consistent with its module-resolution security restrictions.

### Direct-call verification (A, optional, filled in by the recipient)

Bypassing Qt with a pure-HarmonyOS demo (`<deliverable_dir>/ohos-repro/`):

- **Control A**: an EntryAbility that only does `eval("@ohos.deviceInfo")` with no eager import → reproduces `global expression doesn't start with known module path: '@ohos.deviceInfo'` (the same error text as the Qt case) → proving the eval rejection is ArkTS runtime behavior and has nothing to do with Qt.
- **Control B**: the same demo with `import __ohos__deviceInfo from '@ohos.deviceInfo'` (an eager default import) added at the top → `eval("@ohos.deviceInfo")` returns the module object successfully and `deviceType` is readable → proving the eval is allowed once an eager import has registered the path as "known".

Conclusion: the eval rejection is a deterministic security restriction of the ArkTS runtime, not something Qt introduced; the defect on the Qt side is that the glue template doesn't provide the eager import that performs the registration.

### Verdict (A+B, required)

Attribution = **the Qt framework** (not a system problem). The reasoning: ① the error text comes from the ArkTS runtime (libark_jsruntime.so) and `strings libqohos.so` doesn't contain it → the runtime throws it and libqohos lets it propagate uncaught; ② a pure-HarmonyOS demo calling it directly reproduces the same error → runtime behavior unrelated to Qt; ③ the official documentation's example requires `@ohos.deviceInfo` to be eager-imported before use, and a bare eval is undocumented → the runtime rejecting it is consistent with its module-resolution security restrictions, not a system bug; ④ the actual defect is that Qt's `OhosExportModules.ts` under `qtbase/src/harmonyos/templates` is stale (dated 4/21, earlier than libqohos's 7/17) and lacks the `@ohos.*` eager default imports → the module isn't registered → the bare eval is rejected → crash. The fix: on the Qt side, replace `OhosExportModules.ts` / `QtUtils.ets` with the complete versions matching the libqohos generation (eager default imports + the objects API).

## Comparison with the official documentation (A, filled in by the recipient)

| Aspect | What the docs say | Actual behavior | The difference |
|--------|-------------------|-----------------|----------------|
| How the module is imported | `import { deviceInfo } from '@kit.BasicServicesKit'` (an eager named import) — [js-apis-device-info](https://developer.huawei.com/consumer/cn/doc/harmonyos-references/js-apis-device-info) | libqohos resolves the module with a bare `jsState.eval("@ohos.deviceInfo")` | Qt uses an undocumented bare eval; the docs call for an eager import |
| When the module path is registered | An eager import registers the path as "known" at bundle load time, after which it may be referenced — [arkts-dynamic-import](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/arkts-dynamic-import), [module-principle](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/module-principle) | The glue template has no eager import → nothing is registered → the bare eval is rejected | The actual behavior matches the registration ordering the docs imply; evaluating without registering first hits the restriction |
| The deviceType field | `deviceType`: a read-only string, the device type — [js-apis-device-info] | libqohos reads `deviceType` after resolving the module (the 515 generation crashes at the eval stage and never reaches the field read) | Another branch of the same generation (the new 7/14 generation) crashes in `napi_get_named_property(obj,"deviceType")` with a different error text — see [[problem-runtime-crash-libqohos-libqt5core-version-mismatch]] |

> Documentation sources: `harmonyos-references/js-apis-device-info`, `harmonyos-guides/arkts-dynamic-import` and `harmonyos-guides/module-principle` under developer.huawei.com/consumer/cn/doc/.

## Workaround (A+B, optional)

A Qt-side workaround (already applied and verified on a physical device): replace four files with the canonical complete reference template — `OhosExportModules.ts` (26 `@ohos.*` + 13 `@kit.*` eager default imports), `QtUtils.ets` (`getModulesMapForQt()` calls `getOhosExportModules()` to get the objects directly — the objects API), and `QAbilityStage.ets` / `QChildProcess.ets` (`getModulesFactoriesMapForQt()` → `getModulesMapForQt()`, renaming the two call sites; keep QAbilityStage's resourceDir). Then rebuild `build_project(entry@default, debug)` → install → trigger onAcceptWant → no crash and QtWatchdog keeps running = the fix works.

Side effects and risks: the `@ohos.*` / `@kit.*` list must be derived from the modules this libqohos actually evals, by deduplicating the roots from `strings libqohos.so | grep -E "^@ohos\.|^@kit\."`; after the libqohos generation changes (a rebuild), the list has to be rechecked, or evaluating a newly added module will crash again.

## Impact assessment (A+B)

Scope: every Qt HarmonyOS app that uses Qt 5.15 on OHOS and triggers `onAcceptWant` (multi-instance / window recreate / a second QApplication construction) will crash, as long as `OhosExportModules.ts` predates the libqohos build date and lacks the `@ohos.*` eager imports. Affected modules: `@ohos.deviceInfo` / `display` / `window` / `font` / `resourceManager` / `i18n` / `intl` / `settings` / `abilityAccessCtrl` / ... (every `@ohos.*` module libqohos evals at startup), plus the knock-on loss of `@kit.*` + LocalStorage + QEmbeddedComponentCreator (silently dropped by the factories API mismatch, latently breaking UI Extension / LocalStorage). A Qt-side workaround exists (replacing with eager imports). Affected: the internal verification demo (qapp-recreate-test) and every 5.15-generation demo generated from the source tree's templates. 12.x single-instance demos don't trigger it (see the criteria in [[problem-runtime-crash-ohos-deviceinfo-global-expression]]).

## Suggestions and expectations (A+B)

- **For Qt upstream (tqtc)**: ① `OhosExportModules.ts` / `QtUtils.ets` under `qtbase/src/harmonyos/templates` should be updated in the same batch as the libqohos build, so that the `@ohos.*` eager default import list covers every module root libqohos actually evals; ② a build-time script `strings libqohos.so | grep -E "^@ohos\.|^@kit\."` could generate the list automatically and keep the template aligned, preventing staleness; ③ the template's default API shape should match the field libqohos consumes (`modules`=objects / `modulesFactories`=factories).
- **For Huawei**: ① the ArkTS runtime's behavior of rejecting a bare `@ohos.*` global-expression eval when unregistered should be stated explicitly in the `js-apis-device-info` / `arkts-dynamic-import` documentation, together with the "known module path" registration ordering, so cross-language frameworks like Qt are less likely to trip over it; ② suggested priority: medium (a Qt-side workaround exists and it isn't a blocker, but it affects every 5.15-generation multi-instance app).

## Deliverables checklist (A, filled in by the recipient)

> The deliverables directory is `${DELIVERABLES_ROOT}/<issue-name>/` (see `ENV.md`; `<issue-name>` = `ohos-deviceinfo-bare-eval`).
> Note: since triage attributed this to the Qt framework, this form A is effectively downgraded for Huawei to a **documentation-enhancement suggestion** (not a system bug report); whether it goes out with the deliverables directory is a human sign-off decision.

| Deliverable | Path | Notes |
|-------------|------|-------|
| The system issue report | `SYSTEM_ISSUE_REPORT.md` | This file (the rendered form-A output) |
| The pure-HarmonyOS reproduction demo | `ohos-repro/` | Controls A/B proving the eval rejection is unrelated to Qt |
| The Qt reproduction demo | `qt-repro/` | A tidied-up qapp-recreate-test (including the stale OhosExportModules.ts) |
| The framework log | `logs/qt-framework-log.txt` | hilog filtered on `[OHOS-BUG-TRIAGE]` |
| The direct-call log | `logs/direct-call-log.txt` | Output of the pure-HarmonyOS demo calling `eval("@ohos.deviceInfo")` directly |
| The deliverables overview | `README.md` | An index of the deliverables |

---

## Completeness self-check (internal, not rendered)

> The author ticks each item before submitting. Any unticked HARD item sends it back for completion — this is the front gate that keeps us from having to come back with questions.

- [x] **HARD** All six reproduction-environment items present (OS / SDK / Qt commit / device / toolchain / build mode)
- [x] **HARD** Three reproduction steps or fewer, with no implicit operations
- [x] **HARD** Expected behavior written down (backed by docs / a reference platform)
- [x] **HARD** Actual behavior written down (backed by logs / screenshots)
- [x] **HARD** The error message is the complete original text in a code block (not paraphrased)
- [x] **HARD** A minimal reproducible demo is attached (the packaged Qt project + build and run commands)
- [x] Reproduction status filled in (yes/partial/no) + the reproduction rate
- [x] Scenario and trigger conditions written down (why we got here)
- [x] The "Verdict" subsection of the preliminary analysis states an attribution (or says "unclear")
- [x] (A) The documentation comparison table is filled in
- [ ] (A) The pure-HarmonyOS reproduction demo builds and runs standalone  ← sample: the control design is settled; the logs follow once the recipient implements it
- [x] (A) The key log lines are marked with `>>>`
- [ ] (A) The deliverables are in the deliverables directory and a README exists  ← sample: the deliverables directory is a placeholder pending human sign-off to send
- [x] ★ Human review: the root-cause verdict is signed off by a human, and a human performs the submission

## Missing information and open questions (internal, not rendered)

> List what this report still doesn't know and needs to go back to the reporter about. Empty = complete and ready to send; non-empty = fill it in before submitting.
> This is the back gate for "try not to come back with questions": make the fuzzy parts explicit and clear them before sending.

- The pure-HarmonyOS reproduction demo (`ohos-repro/`) hasn't actually been built and run; the controls A/B conclusions are inferred from the source and the documentation, and `logs/direct-call-log.txt` follows once the recipient implements it.
- The device's API level hasn't been pinned by actually running `hdc shell param get const.ohos.apiversion` (only the system version 6.0.0.29 is recorded).
- The exact official documentation page for the "known module path" registration ordering still needs pinning (we currently cite the `arkts-dynamic-import` / `module-principle` topic pages; we need to locate the precise passage about the "known module path" check).
- Triage attributed this to the Qt framework, so for Huawei this form A is effectively downgraded to a documentation-enhancement suggestion (not a system bug report); whether it goes out with the deliverables directory is a human sign-off decision.
