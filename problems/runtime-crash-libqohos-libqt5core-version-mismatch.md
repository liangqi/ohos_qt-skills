---
id: problem-runtime-crash-libqohos-libqt5core-version-mismatch
type: problem
domain: runtime
tags: [runtime, crash, libqohos, libQt5Core, symbol, version-mismatch, runInJsThreadAndWait, runAndWait, deviceType, OhosExportModules, ArkTS, napi, global-expression]
created: 2026-07-17
updated: 2026-07-23
status: solved
severity: critical
audience: public
refs: [procedural-qt-ohos-run-test, problem-runtime-crash-libqohos-modules-mismatch, problem-runtime-crash-ohos-deviceinfo-global-expression, semantic-qt-harmonyos-build-run-workflow]
summary: >
  A Qt5 HarmonyOS application crashes at startup: libqohos.so and libQt5Core.so come from internally inconsistent NEW/OLD builds.
  The default SDK's libqohos (NEW, 7/14, references QtOhos::runInJsThreadAndWait@Qt_5) vs its libQt5Core (OLD, 6/10, only defines QOhosJsThreadGateway::runAndWait@Qt_5_PRIVATE_API) → libqohos fails to load (symbol not found).
  The -full SDK's libQt5Core (NEW, 7/14, has runInJsThreadAndWait) but its libqohos is a stray OLD build (170 MB debug, references runAndWait) → also mismatched.
  Fix: combine the -full NEW libQt5Core with the default SDK's NEW libqohos, and fix @ohos.deviceInfo module resolution (OhosExportModules.ts).
leader_summary: >
  Captured the troubleshooting approach for the libqohos load crash caused by internally inconsistent NEW/OLD builds inside a Qt OHOS SDK, including symbol-level diagnosis, the SDK combination fix, and @ohos.* module resolution
impact: [Migration efficiency, Framework support]
deliverables: [problem record, veles running successfully on a device]
evidence: [faultlog jscrash-com.example.sqt, veles_run.png, kb_status.json (veles run_success)]

error_message: >
  jscrash: TypeError: Cannot read property handleAbilityStageOnCreate of undefined
  at onCreate (QAbilityStage.ets:47:9)
  Precursor: MUSL-LDSO: relocating failed: symbol not found
  _ZN6QtOhos20runInJsThreadAndWait...@Qt_5 (or @Qt_5_PRIVATE_API for runAndWait)
  dso=libqohos.so → napi module @app:.../qohos undefined → qpa undefined → TypeError → exit
  Or (after fixing the symbol): object has no property named 'deviceType'
  at initQtAppContextImpl (QAbilityStage.ets:22) — libqohos fails to resolve @ohos.deviceInfo through the QNapi global-expression mechanism
error_code: ""
keywords: [libqohos, libQt5Core, runInJsThreadAndWait, runAndWait, symbol not found, NEW OLD mismatch, deviceType, OhosExportModules, global-expression, @ohos.deviceInfo, ArkTS-engine]
symptoms: >
  The signed HAP installs successfully, but after aa start the process disappears within 1–9 s. The faultlog shows a jscrash TypeError
  (handleAbilityStageOnCreate of undefined, or a missing deviceType property).

environment: >
  Two Qt 5.15.16 OHOS SDKs (the default ${QT5_15_OHOS_SDK} + the full ${QT5_15_OHOS_SDK_FULL}), each internally inconsistent between libqohos and libQt5Core build versions.
  An OHOS device (HUAWEI MateBook Fold, UDID 9BFAF107...).
---

## Root cause (two layers)

### Layer 1: a symbol-level NEW/OLD mismatch between libqohos and libQt5Core

Inside the Qt OHOS SDK, libqohos.so and libQt5Core.so have inconsistent build dates/APIs:

| SDK | libqohos | libQt5Core | Match? |
|-----|----------|-----------|--------|
| Default (${QT5_15_OHOS_SDK}) | NEW (7/14, 5.5 MB, references `QtOhos::runInJsThreadAndWait@Qt_5`) | OLD (6/10, 37 MB, only defines `QOhosJsThreadGateway::runAndWait@Qt_5_PRIVATE_API`) | ✗ Both the symbol name and the version tag differ |
| -full (${QT5_15_OHOS_SDK_FULL}) | A stray OLD build (170 MB debug, references `runAndWait@Qt_5_PRIVATE_API`) | NEW (7/14, has `runInJsThreadAndWait@Qt_5`) | ✗ libqohos is the stale stray |

**The key point**: `runInJsThreadAndWait` (the NEW API, with the @Qt_5 version tag) ≠ `runAndWait` (the OLD API, with the @Qt_5_PRIVATE_API version tag). libqohos (NEW) references the former while libQt5Core (OLD) defines only the latter → the dynamic linker reports `symbol not found` → libqohos fails to load → the NAPI module is undefined → jscrash.

### Layer 2: @ohos.deviceInfo module resolution (libqohos vs. the ArkTS engine)

Once layer 1 is fixed (libqohos loads), libqohos (NEW, 7/14) resolves @ohos.* modules (deviceInfo/display/window, and so on) through the QNapi "global-expression" mechanism. Resolution of these @ohos.* modules **doesn't consult the modulesFactories map** (which only covers @kit.* + TS modules) — it goes straight to the ArkTS engine. If the ArkTS engine returns the module namespace object (which only has a `default` export) rather than the namespace of the default export → `napi_get_named_property(obj, "deviceType")` throws "object has no property named 'deviceType'".

The 7/10 OhosExportModules.ts template predates the 7/14 libqohos → it lacks correct mappings for the @ohos.* modules → crash.

## How to verify

1. `hdc install` + `aa start`; the faultlog contains `symbol not found ... runInJsThreadAndWait` or `object has no property named 'deviceType'`
2. `llvm-readelf --dyn-syms libqohos.so | grep runInJsThreadAndWait` → if it's UND (undefined), check whether libQt5Core DEFINES it
3. `llvm-readelf --dyn-syms libQt5Core.so | grep runInJsThreadAndWait` → if it doesn't define it, the SDK is internally inconsistent

## Solution

### Layer 1 fix: combine the SDKs

Use the **-full SDK's NEW libQt5Core/Gui/Network/Widgets** (7/14, with runInJsThreadAndWait + SSL) together with the **default SDK's NEW libqohos** (7/14, 5.5 MB, matching the NEW libQt5Core). Replace -full/plugins/platforms/libqohos.so (the 170 MB stray OLD build) with the default SDK's (5.5 MB NEW).

### Layer 2 fix: @ohos.* module resolution

Update OhosExportModules.ts to the version matching the 7/14 libqohos (adding correct eager default-imports + modulesFactories entries for @ohos.deviceInfo/display/window/font/resourceManager/i18n/intl/settings/abilityAccessCtrl and others).

## Key diagnostic signals

- Use `llvm-readelf --dyn-syms` to check libqohos's UND symbols against libQt5Core's DEFINED symbols: both the version tag (@Qt_5 vs @Qt_5_PRIVATE_API) and the symbol name (runInJsThreadAndWait vs runAndWait) must match.
- libqohos's build date (mtime) should be close to libQt5Core's (from the same build batch).
- OhosExportModules.ts's date should be ≥ libqohos's date (the template must match the libqohos version).

## Related

- [[qt-ohos-run-test]] §5 — the crash analysis table
- [[problem-runtime-crash-libqohos-modules-mismatch]] (the predecessor: the modulesFactories/modules field-name mismatch between libqohos and the .ets)
- [[problem-runtime-crash-ohos-deviceinfo-global-expression]] (another generational branch of the @ohos.deviceInfo crash family: in the 515 generation a bare eval throws "global expression doesn't start with known module path" — layer 2 on this page is the 7/14 generation, where napi_get_named_property throws "object has no property named 'deviceType'"; the same eager-import fix applies)
- ENV.local: the difference in libqohos/libQt5Core build versions between the default SDK (${QT5_15_OHOS_SDK}) and the -full SDK (${QT5_15_OHOS_SDK_FULL})
