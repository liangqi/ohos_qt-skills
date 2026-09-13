---
id: semantic-qt-harmonyos-build-run-workflow
type: semantic
domain: tech
tags: [qt, harmonyos, devecocli, hvigor, hdc, build, run, hilog, ui-test, troubleshooting, workflow]
created: 2026-06-02
updated: 2026-08-15
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-overview]
summary: >
  The Qt HarmonyOS build-and-run workflow: use devecocli first for building, installing, launching, logs, and UI operations;
  fall back to minimal, auditable hvigor/hdc calls when the wrapper doesn't cover something or you're diagnosing the wrapper itself, while
  keeping the Qt project checks and the failure-troubleshooting loop.
---

# The Qt HarmonyOS build-and-run workflow

For the platform tools' current capabilities and selection rules, the common knowledge base is authoritative:

- [[ohos-common-kb/procedural/deveco-cli-usage-rules|DevEco CLI usage rules]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/deveco-cli-usage-rules.md))
- [[ohos-common-kb/semantic/deveco-mcp-capabilities|DevEco MCP capabilities and usage boundaries]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/deveco-mcp-capabilities.md))
- [[ohos-common-kb/semantic/harmonyos-development-fundamentals|HarmonyOS development fundamentals]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md))

Today deveco-mcp handles only static `check` and LSP `restart`; it provides no project sync, build, launch, log, or UI operations. The historical names `project_sync`, `build_project`, `start_app`, `get_app_ui_tree`, and `perform_ui_action` must not be invoked in the current process.

For setting up the build environment (configure, MinGW, Perl, and so on), see [[qt-harmonyos-build]]; for full on-device acceptance, see [[qt-ohos-run-test]].

## The core process

```text
prepare dependencies → build an unsigned HAP → sign separately → install and launch → logs → Qt UI/rendering verification
```

### Step 1: prepare dependencies

On a first checkout, or whenever `oh-package.json5` changes, prefer the dependency sync capability the project/devecocli provides. For a Qt project, also check:

- `externalNativeOptions.path` in `entry/build-profile.json5` points at the intended CMakeLists
- `CMAKE_PREFIX_PATH` points at the correct Qt OHOS SDK
- The Qt application target name matches `APP_LIBRARY_NAME` in `QtAppConstants.ets`
- `local.properties` / SDK paths live only in local configuration and are never written into a shared knowledge page

### Step 2: build

The normal path:

```bash
devecocli build --modules entry --product default --build-mode debug
```

The Qt build stage is complete when you see `BUILD SUCCESSFUL` and `entry-default-unsigned.hap`; signing is a separate follow-up step.

When devecocli doesn't yet cover the option you need, the wrapper is being maintained, or you're constructing a minimal failure reproduction, you may call hvigor directly. Record why you did so, and afterwards return to devecocli or the project's standard gates to verify:

```bash
node <DEVECO>/tools/hvigor/bin/hvigorw.js assembleHap \
  --mode module -p product=default -p buildMode=debug --no-daemon
```

Low-level diagnosis carries only these constraints: use the Node/JBR/SDK from the same DevEco installation; confirm task names with `tasks --no-daemon` first; don't bake personal absolute paths into the repository.

### Step 3: sign, install, and launch

Once signing is configured, the normal path is:

```bash
devecocli run --module entry
```

When you need to verify a specific HAP, particular Ability/Want parameters, or an action the wrapper doesn't cover, minimal hdc diagnosis is allowed:

```bash
hdc install <signed.hap>
hdc shell aa start -b <bundleName> -a <abilityName>
```

Don't use low-level commands to paper over a bundleName/profile/signingConfig inconsistency; once a low-level call succeeds, go back to the normal delivery flow.

### Step 4: logs

```bash
devecocli log --bundle-name <bundleName> --level E
devecocli log --crash --bundle-name <bundleName>
```

Qt-specific keywords:

| Log line | What to check on the Qt side |
|---|---|
| `libqohos.so not found` | Whether the QPA plugin made it into the final HAP |
| `libQt5Core.so not found` | Whether the Qt runtime dependency closure is complete |
| `Cannot load Qt platform plugin` | The plugin path, its dependencies, and the ABI |
| `module "QtQuick" is not installed` | QML module and resource deployment |

When devecocli's filtering isn't enough, use minimal `hdc shell hilog` diagnosis and record the bundle/PID filter conditions.

### Step 5: Qt UI verification

Prefer whatever `ui` subcommands devecocli actually provides today. The Qt UI lives on the XComponent/QPA hosting layer, so an ordinary ArkUI inspector may only see the XComponent; to get the Qt widget tree, enable the Qt accessibility bridge, then verify through whatever uitest capability the target environment supports.

When devecocli has no corresponding key/uitest action, you can use a minimal low-level call such as `hdc shell uitest uiInput keyEvent ...`. That is an explicit capability gap and shouldn't be promoted to the default path for all device operations.

A screenshot existing doesn't mean Qt rendered correctly; check for a non-black screen, window layering, input, lifecycle, and logs as well.

## The static check MCP

When deveco-mcp is connected in the current environment, run `check` after modifying supported ArkTS/C++ files; run `restart` once if the LSP index misbehaves. When the MCP is unavailable, run the project's existing compile/lint/typecheck instead — don't invoke the historical build/run/UI MCP tools.

## The failure-troubleshooting loop

1. First search the KB for the same error keywords and the corresponding problem page
2. Classify it as dependency / compile / link / packaging / signing / installation / launch / runtime
3. Retry the same hypothesis at most three times, keeping the command, input, output, and the differing evidence each time
4. On success, capture the minimal root cause and a regression; if it still fails, stop and submit the error context, what you tried, and the missing permissions/environment

| Stage | Typical signal | Check first |
|---|---|---|
| CMake | package/target not found | The Qt kit, toolchain, find root path |
| Compile | header/API error | Qt5/Qt6 and OHOS conditional branches |
| Link | undefined symbol / missing library | Target links, ABI, dependency closure |
| Packaging | Hvigor/HAP/resource failure | build-profile, templates, resource paths |
| Install/launch | profile/bundle/ability error | Identity, signing, device API, Want |
| Runtime | dlopen/QPA/QML/crash | The final HAP, hilog/faultlog, the Qt adapter |

## Acceptance checklist

- [ ] No historical MCP build/run/UI tools were invoked
- [ ] The normal path used devecocli first; any low-level call had a clear reason and exit condition
- [ ] The unsigned HAP, the signed HAP, and the running application were recorded as three separate stages
- [ ] The Qt runtime/QPA/QML/third-party dependency closure passed static pre-checks
- [ ] Device logs, screenshots, Qt widget interaction, and lifecycle were all verified
- [ ] `check` was run when deveco-mcp was available; the project's alternative gates were run when it wasn't

## References

- [[qt-harmonyos-build]] — The Qt SDK and build environment
- [[qt-ohos-run-test]] — Qt on-device CLI acceptance
- [[ohos-common-kb/procedural/deveco-cli-usage-rules|common: DevEco CLI usage rules]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/deveco-cli-usage-rules.md))
