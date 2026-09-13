---
id: problem-runtime-crash-arkts-template-modules-mismatch
type: problem
domain: runtime
tags: [arkts-template, modulesFactories, modules, libqohos, napi, crash, ohos-build, qt, harmonyos]
created: 2026-08-06
updated: 2026-08-06
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-window-model, semantic-qt-harmonyos-project-structure]
summary: >
  A freshly built libqohos.so reads the modulesFactories property, but the old ArkTS template passes modules -> NAPI throws -> the app crashes at startup.
  Root cause: the ArkTS template in the Qt source tree upgraded its API (modules -> modulesFactories), while the old project's QAbilityStage.ets was never updated to match.
  Fix: replace 19 files from the Qt source tree's entry/src/main/ets/.
leader_summary: >
  Identified the root cause of the ArkTS template version mismatch crash, fixed it by syncing the template from the Qt source tree, and captured it as a known pitfall
impact: [Framework support, Runtime troubleshooting]
deliverables: [problem record]
evidence: [ohos-qt-patch-delivery/template/]

error_message: >
  Cannot read property 'handleAbilityStageOnCreate' of undefined
  at QAbilityStage.ets:47
  import qpa from 'libqohos.so' returns undefined
  NAPI module not registered
error_code: ""
keywords: [modulesFactories, modules, libqohos.so, QAbilityStage, ArkTS template, startup crash, NAPI]
symptoms: "The HAP installs successfully but crashes when launched, reporting handleAbilityStageOnCreate undefined in QAbilityStage.ets"

environment: "OHOS + Qt 5.15.16 + freshly built libqohos.so + an old ArkTS project"
---

# ArkTS template version mismatch -> NAPI startup crash

## Error message

```
Cannot read property 'handleAbilityStageOnCreate' of undefined
at QAbilityStage.ets:47
```

## Scenario

After rebuilding libqohos.so (with new patches or updated Qt source) and deploying it into an old ohostemplate project, the application crashes at startup.
Reverting libqohos.so to the old version crashes identically -> proving the problem isn't libqohos.so itself.

## Cause

The ArkTS template in the Qt source tree upgraded its API:
- Old: `modules: QtUtils.getModulesMapForQt()`
- New: `modulesFactories: QtUtils.getModulesFactoriesMapForQt()`

The freshly built libqohos.so C++ code reads the `modulesFactories` property, while the old ArkTS project passes `modules`.
The property name mismatch means the NAPI module isn't registered correctly, so `import qpa from 'libqohos.so'` returns undefined.

## Solution

Replace the ArkTS template files from the Qt source tree:

```
Source: qtbase/src/harmonyos/templates/entry/src/main/ets/
Target: <project>/entry/src/main/ets/
```

Replace 19 files:
- 16 entry .ets/.ts files
- 3 qEmbeddedUiExtensionHost .ets files

Key change: `modules` -> `modulesFactories`, and `getModulesMapForQt()` -> `getModulesFactoriesMapForQt()`.

Keep the project's own customizations: cpp, resources, libs, and configuration files (build-profile contains signing settings).

## Notes

- Every time you update libqohos.so, check whether the ArkTS template needs updating too
- The `import lazy` syntax requires adding `compatibleSdkVersionStage: "beta3"` to build-profile.json5
- `APP_LIBRARY_NAME` must match the CMake `add_library` name
