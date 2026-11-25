---
id: problem-runtime-crash-ohos-deviceinfo-global-expression
type: problem
domain: runtime
tags: [runtime, crash, @ohos.deviceInfo, global-expression, ArkTS, bare-eval, known-module-path, OhosExportModules, QtUtils, demo-gen, stale-template, objects-api, reference-template]
created: 2026-07-23
updated: 2026-07-23
status: solved
severity: critical
audience: public
refs: [fault-C-0010, problem-runtime-crash-libqohos-libqt5core-version-mismatch, procedural-demo-generation, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-build-run-workflow]
summary: >
  A Qt5 HarmonyOS application crashes at runtime with the Napi::Error "global expression doesn't start with known module path: '@ohos.deviceInfo'".
  Root cause: at startup, libqohos (the 515 generation) does a bare global-expression eval of jsState.eval("@ohos.deviceInfo"), and the ArkTS runtime rejects bare @ohos.* evals
  unless that module path has been registered as "known" by an eager import. Demos generated from the Qt source tree template (qtbase/src/harmonyos/templates)
  ship a stale, minimal OhosExportModules.ts (only 5 @kit.* lazy imports + the factories API) with no @ohos.* imports at all
  → deviceInfo isn't registered → the bare eval is rejected → crash. Fix: replace it with the OhosExportModules.ts + QtUtils.ets from the canonical full reference template
  (26 @ohos.* + 13 @kit.* eager default-imports + the objects API + getModulesMapForQt).
leader_summary: >
  Captured the root cause and fix for "a stale glue template makes the bare @ohos.deviceInfo eval crash" when generating Qt HarmonyOS demos (aligning with the full reference template),
  completing the @ohos.deviceInfo crash family with its other generational error (the 515 bare eval vs. the 7/14 napi_get_named_property).
impact: [Migration efficiency, Framework support, Demo generation]
deliverables: [problem record, the qapp-recreate-test fix (4 files), running successfully on a device]
evidence: [faultlog cppcrash-60469 (com.example.qapprecreatetest), shot-after-fix.png, hilog showing QtWatchdog alive]

# ====== Search keywords (for fast agent matching) ======
error_message: >
  jscrash/cppcrash: terminating due to uncaught exception of type Napi::Error:
  global expression doesn't start with known module path: '@ohos.deviceInfo'
  REASON: Signal: SIGABRT(SI_TKILL)
  PNAME: com.example.<app>
  Call stack: MainThread::HandleScheduleAcceptWant → JsAbilityStage::OnAcceptWant
    → initQtAppContextIfNeeded → initQtAppContextImpl (entry/src/main/ets/qabilitystage/QAbilityStage.ets)
    → qpa.setupQtApplication({modules}) → libqohos initAppData → initDeviceInfo
    → jsState.eval<QNapi::Object>("@ohos.deviceInfo")  ← the ArkTS runtime throws the Napi::Error here
  The .so files at the bottom of the stack: libqohos.so (the 515 generation, with no qohosplugincore.cpp fallback) + libQt5Core.so + libark_jsruntime.so
  Precursor: the process survives for minutes and only crashes later (or when a recreate / second construction triggers onAcceptWant) — not an immediate startup crash.
error_code: ""
keywords: [global expression doesn't start with known module path, @ohos.deviceInfo, Napi::Error, bare eval, known module path, ArkTS runtime, OhosExportModules, getOhosExportModulesFactories, getModulesMapForQt, objects api vs factories api, stale template, demo generation, reference-template, eager default-import, onAcceptWant, initQtAppContextImpl, setupQtApplication]
symptoms: >
  The signed HAP installs successfully and the application launches after aa start (the Qt window appears and QtWatchdog runs), but the process crashes when onAcceptWant fires
  (multi-instance / window recreate / a second QApplication construction); the faultlog's LAST_FATAL_MESSAGE is the Napi::Error above.
  Note: this error and "object has no property named 'deviceType'" are two different generational errors in the @ohos.deviceInfo crash family (see below).

# ====== Problem details ======
environment: >
  The Qt 5.15.16 OHOS SDK (${QT5_15_OHOS_SDK_FULL}), with libqohos.so 5.3 MB (7/17, the 515 generation: reads the "modules" field,
  makeJsModulesMap expects object values, and there's no napi_load_module fallback from qohosplugincore.cpp).
  An OHOS device: HUAWEI MateBook Fold (HPR-W72 6.0.0.29).
  Demo: ${DEMOS_ROOT}/qapp-recreate-test (verifying a second QApplication construction), with the glue template from qtbase/src/harmonyos/templates.
---

## Root cause (three layers, from surface to root)

### Layer 1: the error comes from the ArkTS runtime, not libqohos

The error text `global expression doesn't start with known module path: '@ohos.deviceInfo'` **isn't in libqohos.so**
(`strings libqohos.so` finds nothing). It's thrown by the **ArkTS runtime (libark_jsruntime.so) when it rejects a bare @ohos.* global eval**.
libqohos (the 515 generation, qohosjsmain.cpp:1677) executes:

```cpp
auto deviceInfoObj = jsState.eval<QNapi::Object>("@ohos.deviceInfo");  // a bare global-expression eval
```

The ArkTS runtime strictly validates bare global-expression evals that start with `@ohos.`: **only @ohos.* modules already registered as "known module paths" by an import may be bare-evaluated**, otherwise it throws `global expression doesn't start with known module path`. This is an ArkTS security restriction in HarmonyOS 6.0 (both the README immersive-subwindow §258 and the comment at qohosplugincore.cpp:652-654 confirm that "bare @ohos.* global script evals are rejected by the ArkTS runtime").

> **The key diagnostic**: if that error text **isn't found** in the libqohos.so binary but the faultlog reports it → the ArkTS runtime threw it (libqohos merely propagated the uncaught exception). If it **is** found in libqohos.so → libqohos's extractModuleFromEvalExpr threw it (see layer 2 of [[problem-runtime-crash-libqohos-libqt5core-version-mismatch]] — that's the newer 7/14 mechanism).

### Layer 2: the stale, minimal OhosExportModules.ts lacks @ohos.* eager imports

The glue template copied from `qtbase/src/harmonyos/templates` (OHOS_TEMPLATE_SRC) ships a **stale, minimal** `OhosExportModules.ts`:

```ts
// ❌ The template's version (only 5 @kit.* lazy imports, no @ohos.* imports at all)
import lazy { textToSpeech as __kit__CoreSpeechKit__textToSpeech } from '@kit.CoreSpeechKit';
// ... 4 more @kit.* ...
export function getOhosExportModulesFactories(): object {
  return { '@kit.CoreSpeechKit.textToSpeech': () => __kit__CoreSpeechKit__textToSpeech, ... };
}
```

The template's date (4/21 in the source tree) predates libqohos (7/17) → it lacks eager imports for `@ohos.deviceInfo/display/window/font/resourceManager/i18n/intl/settings/...` → `@ohos.deviceInfo` isn't registered as a "known module path" → the layer 1 bare eval is rejected → crash.

**Only an eager (non-lazy) `import X from '@ohos.X'` registers the module path as globally known when the bundle loads**; `import lazy` defers loading, so the module still isn't registered when the bare eval happens at startup → it crashes the same way. So the fix must use an **eager default-import**.

### Layer 3: an API-form mismatch (factories vs. objects) — @kit.* breaks too

The stale template's `QtUtils.ets` uses the **factories API**: `getModulesFactoriesMapForQt()` → `getOhosExportModulesFactories()` returns `() => value` (arrow factories), and LocalStorage/QEmbeddedComponentCreator store **function references** (uncalled).

But the 515-generation libqohos uses the **objects API**: `makeJsModulesMap` (qohosjsmain.cpp:861) returns a `map<string, Reference<Object>>`, validating each value with `propValue.IsObject()` — **an arrow function is a napi_function, not a napi_object, so IsObject() returns false and the entry is silently discarded**. So @kit.*, LocalStorage, and QEmbeddedComponentCreator are all lost (a latent bug that breaks UI Extension/LocalStorage).

| API | .ets function | Return value | What libqohos consumes | Corresponding generation |
|-----|---------------|--------------|------------------------|--------------------------|
| factories (old/wrong) | getOhosExportModulesFactories | `() => value` | makeJsModulesFactoriesMap (map<string,Function>) + reads "modulesFactories" | The newer 7/14 |
| **objects (correct)** | **getOhosExportModules** | `value` (the object directly) | **makeJsModulesMap (map<string,Object>) + reads "modules"** | **The 515 generation** |

**The diagnostic**: check libqohos.so's strings for whether the field name is `modules` (objects) or `modulesFactories` (factories), and pick the API accordingly. This project's `.so` has `modules` → objects.

## Distinguishing it from "object has no property named 'deviceType'" (the @ohos.deviceInfo crash family)

| Error | libqohos generation | Mechanism | Fix |
|-------|---------------------|-----------|-----|
| **global expression doesn't start with known module path** (this page) | 515 (a bare jsState.eval) | The ArkTS runtime rejects a bare (unregistered) @ohos.* eval | An eager import to register the module path |
| object has no property named 'deviceType' (layer 2) | The newer 7/14 (extractModuleFromEvalExpr + a napi_load_module fallback) | The module resolves but returns a namespace wrapper, so reading .deviceType fails | An eager **default** import to expose the default export |

The two are **the same class of problem (@ohos.* resolution failure) with the same fix direction (an eager import) but different error text in different generations**. An eager default-import fixes both (registering the path and exposing the default export).

## How to verify

1. `hdc install <hap> && hdc shell aa start -b <bundle> -a QAbility`, then trigger onAcceptWant (multi-instance / recreate / a second construction)
2. After the crash, `hdc shell ls -t /data/log/faultlog/temp/` and take the newest cppcrash-*.json
3. `LAST_FATAL_MESSAGE` containing `global expression doesn't start with known module path: '@ohos.deviceInfo'` + a stack reaching `initQtAppContextImpl` + `.so` files including libqohos.so = this problem
4. **To determine the generation**: `strings <SDK>/plugins/platforms/libqohos.so | grep "global expression"` — nothing found = the 515 generation (the ArkTS runtime threw it); found = the 7/14 generation (libqohos threw it; go to layer 2)
5. **To determine the API**: `strings libqohos.so | grep -E "^modules$|^modulesFactories$"` → modules = objects / modulesFactories = factories

## Solution

**Replace 4 files with the canonical full reference template** (the KB's canonical reference implementation; [[problem-runtime-crash-libqohos-libqt5core-version-mismatch]] points at the same fix):

1. `entry/src/main/ets/qability/OhosExportModules.ts` ← the full reference template:
   - 26 `import __ohos__X from '@ohos.X'` statements (eager default-imports, covering deviceInfo/display/window/font/resourceManager/i18n/intl/settings/abilityAccessCtrl/bundle.bundleManager/...)
   - 13 `import { Y as __kit__... } from '@kit.Z'` statements (eager, covering the @kit.* roots the `.so` actually evaluates)
   - `export function getOhosExportModules(): object` returning **the objects directly** (not arrow factories)
2. `entry/src/main/ets/qability/QtUtils.ets` ← the full reference template: `getModulesMapForQt()` calls `getOhosExportModules()` + `getLocalStorageTsInterface()` + `getQEmbeddedComponentCreatorTsInterface()` (**calling them to get objects**, not storing functions)
3. `QAbilityStage.ets` / `QChildProcess.ets`: rename `getModulesFactoriesMapForQt()` → `getModulesMapForQt()` (2 call sites; keep QAbilityStage's resourceDir)
4. Rebuild with `build_project(entry@default, debug)` → install → trigger onAcceptWant → no crash and QtWatchdog keeps running = the fix works

> **Where the @ohos.* / @kit.* list comes from**: use `strings libqohos.so | grep -E "^@ohos\.|^@kit\."` to get the module roots this libqohos actually evaluates (deduplicated) and make sure each one has an eager import. The full reference template's 26+13 is a verified superset you can adopt as-is.

## Key diagnostic signals

- The source tree template's date (qtbase/src/harmonyos/templates) < libqohos's date → the template must be stale, and OhosExportModules.ts will lack the @ohos.* mappings.
- `strings libqohos.so` not containing "global expression" → the 515-generation bare eval mechanism (this page); containing it → the 7/14 generation (layer 2).
- The field name in libqohos.so's strings being `modules` → the objects API (direct values); `modulesFactories` → the factories API (arrow factories). The .ets must match.
- ArkTS-Check reporting `getOhosExportModules` "no exported member" plus lots of `arkts-no-any-unknown` is usually a stale LSP index (the checker skips .ts files); trust the hvigor build instead (the build compiler re-reads the .ts and passes).

## Related

- [[problem-runtime-crash-libqohos-libqt5core-version-mismatch]] — The newer 7/14 branch of the @ohos.deviceInfo crash family ("object has no property named 'deviceType'"); the same eager-import fix.
- [[procedural-demo-generation]] phase three, 3.2 — The source tree template pitfall checkpoint (added because of this).
- [[semantic-qt-harmonyos-project-structure]] — Where the HarmonyOS project template comes from.
- The canonical full reference template (local path in ENV.local) — OhosExportModules.ts/QtUtils.ets reference implementation.
