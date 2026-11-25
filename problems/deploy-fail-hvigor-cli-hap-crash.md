---
id: problem-deploy-fail-hvigor-cli-hap-crash
type: problem
domain: deploy
tags: [hvigor, cli, hap-packaging, napi, crash, deveco-ide, modules, qt, harmonyos]
created: 2026-08-06
updated: 2026-08-06
status: workaround
severity: medium
audience: public
refs: [fault-C-0015, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-build-run-workflow]
summary: >
  A HAP packaged from the hvigor command line (--mode module) crashes at startup: Cannot read property handleAbilityStageOnCreate of undefined.
  Reverting to an unpatched libqohos.so crashes the same way -> this is not a Qt code problem, but a difference between CLI packaging and DevEco Studio IDE packaging.
  Workaround: deploy by running directly from the DevEco Studio IDE.
leader_summary: >
  Identified the hvigor CLI HAP packaging crash as a CLI-vs-IDE packaging difference, not a Qt code problem
impact: [Framework support, Runtime troubleshooting]
deliverables: [problem record]
evidence: [ohos-qt-patch-delivery]

error_message: >
  Cannot read property 'handleAbilityStageOnCreate' of undefined
  at QAbilityStage.ets
  (packaged with hvigor --mode module)
error_code: ""
keywords: [hvigor, CLI, HAP packaging, NAPI, DevEco Studio, IDE, startup crash]
symptoms: "A HAP packaged by the hvigor CLI crashes at startup after installation, while DevEco Studio IDE Run works fine"

environment: "OHOS + hvigor CLI (--mode module) + Qt 5.15.16"
---

# HAP packaged by the hvigor CLI crashes at startup

## Error message

```
Cannot read property 'handleAbilityStageOnCreate' of undefined
at QAbilityStage.ets
```

## Scenario

After packaging a HAP with `hvigor --mode module` from the command line and installing it on the device, the application crashes at startup.
Reverting libqohos.so to an unpatched version crashes identically -> rules out Qt code changes.

## Cause

The hvigor CLI packaging flow differs from the DevEco Studio IDE packaging flow:
- CLI packaging registers NAPI modules incompletely
- IDE packaging handles NAPI module registration and the `.so` dependency chain correctly

The exact difference is still under investigation.

## Solution

**Workaround**: deploy by running directly from the DevEco Studio IDE (Build -> Run); the IDE packaging flow handles all module registration correctly.

## Notes

- Command-line packaging and IDE packaging are **not equivalent** — keep this in mind for CI/CD.
- The fact that it still crashes after reverting the `.so` rules out code changes as a factor.
