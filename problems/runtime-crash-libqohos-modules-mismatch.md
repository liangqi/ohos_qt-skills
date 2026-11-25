---
id: problem-runtime-crash-libqohos-modules-mismatch
type: problem
domain: runtime
tags: [runtime, crash, libqohos, qpa, ets, template, sdk-version, modulesFactories, modules, signing, jscrash]
created: 2026-07-16
updated: 2026-07-16
status: solved
severity: critical
audience: public
refs: [procedural-qt-ohos-run-test, semantic-qt-harmonyos-build-run-workflow, semantic-qt-harmonyos-project-structure]
summary: >
  A Qt5 HarmonyOS application crashes at startup with the jscrash "object has no property named 'modules'" at QAbilityStage.ets:22.
  Root cause: a version mismatch between the .ets glue template (5.12, passes modulesFactories) and the libqohos.so it links against (5.15, reads modules).
  Fix: use a Qt OHOS SDK matching the template version (5.12 template → the older ${QT5_15_OHOS_SDK}, whose libqohos reads modulesFactories; or update the .ets to 5.15 and pass modules).
leader_summary: >
  Captured the troubleshooting approach for the SDK/template version mismatch that crashes Qt5 HarmonyOS applications at startup — the key blocker that on-device verification catches after batch-porting produces HAPs
impact: [Migration efficiency, Framework support]
deliverables: [problem record, fixed HAP (sqt passes on device)]
evidence: [faultlog jscrash-com.example.sqt, sqt_run.png, kb_status.json (sqt run_success)]

# ====== Search keywords ======
error_message: >
  jscrash: Error: object has no property named 'modules'
  at initQtAppContextImpl entry (entry/src/main/ets/qabilitystage/QAbilityStage.ets:22:11)
  at initQtAppContextIfNeeded entry (QAbilityStage.ets:38:19)
  at onAcceptWant entry (QAbilityStage.ets:60:19)
  HybridStack: .../libqohos.so ... napi_create_type_error
  AppKit: com.example.<app> is about to exit due to RuntimeError
  Precursor logs: hapModuleInfo null + Context.resourceDir is empty + resfile not exist
error_code: ""
keywords: [modulesFactories, modules, libqohos, QAbilityStage, setupQtApplication, initQtAppContextImpl, jscrash, template version mismatch, ${QT5_15_OHOS_SDK_FULL}]
symptoms: >
  The signed HAP installs successfully, but after aa start the process disappears within 1–2 seconds (crash at startup); no application window appears on the desktop, or it flashes and exits.

# ====== Problem details ======
environment: >
  Windows cross-compilation + an OHOS device.
  Two Qt 5.15.16 OHOS SDKs: ${QT5_15_OHOS_SDK} (older; its libqohos reads modulesFactories)
  and ${QT5_15_OHOS_SDK_FULL} (full; its libqohos reads modules).
  The .ets glue template came from ${QT5_15_SRC} (actually a dirty 5.12 tree, so it passes modulesFactories).
---

## Root cause

libqohos.so's NAPI `setupQtApplicationImpl` reads a different field name depending on the source version:
- 5.12 source (${QT5_15_SRC}, qohosjsmain.cpp:1736): `appStartupObj.get<Object>("modulesFactories")`
- 5.15 source (${QT5_15_SRC_FULL}, qohosjsmain.cpp:1735): `appStartupObj.get<Object>("modules")`

Meanwhile, the OHOS glue template `QAbilityStage.ets` (copied from `${QT5_15_SRC}/qtbase/src/harmonyos/templates`, the 5.12 version) calls `qpa.setupQtApplication({...})` passing `modulesFactories: QtUtils.getModulesFactoriesMapForQt()` (with no `modules` field).

If the application is built against **${QT5_15_OHOS_SDK_FULL}** (5.15 libqohos, reads `modules`) while the .ets is 5.12 (passes `modulesFactories`), then at runtime `appStartupObj.get<Object>("modules")` throws "object has no property named 'modules'" → AbilityStage.onAcceptWant crashes → the process exits.

The precursor logs are not the direct root cause; they're the framework querying context just before the NAPI crash: `hapModuleInfo null` + `Context.resourceDir is empty` + `dir:.../resources/resfile not exist`. The actual crash point is QNapi reading the missing `modules` property.

## How to verify

1. `hdc install entry-default-signed.hap && hdc shell aa start -b <bundle> -a <ability>`
2. `sleep 3; hdc shell ps -ef | grep <bundle>` — if the process is gone, it crashed at startup
3. MCP `get_hilog_or_faultlog_recent` (bundle_name, is_crash_log=true), or pull the faultlog via `hdc shell`
4. A faultlog containing "object has no property named 'modules'" + a stack reaching QAbilityStage.ets:22 + libqohos.so napi_create_type_error = this problem

## Solution (preferred: align the versions)

**Preferred**: rebuild using a Qt OHOS SDK matching your .ets template version. For a 5.12 .ets template (passing modulesFactories), use `${QT5_15_OHOS_SDK}` (the older libqohos reads modulesFactories, matching the template; the same combination the reference implementation runs on):
```json5
// externalNativeOptions.arguments in entry/build-profile.json5
"-DCMAKE_PREFIX_PATH=${QT5_15_OHOS_SDK}"   // not ${QT5_15_OHOS_SDK_FULL}
```
After the change, rebuild with `node hvigorw.js assembleHap --no-daemon` (it re-signs automatically if signingConfigs is set), then reinstall and retest.

**Alternative (requires the 5.15 template)**: if you must use ${QT5_15_OHOS_SDK_FULL} (for modules only the full SDK has, such as Multimedia), then the .ets template must also be the 5.15 version (passing `modules`). But the 5.15 source tree (${QT5_15_SRC_FULL}) doesn't contain templates/.ets, so you'd have to obtain the 5.15 template separately and also update the field names in the `QtApplicationSetupParams`/`QtChildProcessParams` type definitions. That's expensive; the preferred option is more reliable.

## Key diagnostic signals

- The reference implementation uses ${QT5_15_OHOS_SDK} + the 5.12 template → consistent → it runs.
- In a batch port, if the port agent mistakenly uses ${QT5_15_OHOS_SDK_FULL} + the 5.12 template → **every HAP crashes at runtime with the same error** (a successful build ≠ a working app).
- So after "the build produces a HAP", you must run it on a device once (see [[qt-ohos-run-test]]) to confirm this crash isn't present.

## Related

- [[qt-ohos-run-test]] §5 — this row is already in the crash analysis table
- ENV.md: the root cause is a source-version mismatch between the SDK and the template; OHOS_TEMPLATE_SRC is derived from the 5.12 source tree, so the template is the 5.12 version.
