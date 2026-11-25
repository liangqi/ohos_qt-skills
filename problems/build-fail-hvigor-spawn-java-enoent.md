---
id: problem-build-fail-hvigor-spawn-java-enoent
type: problem
domain: build
tags: [build, hvigor, PackageHap, java, ENOENT, windows, PATH, bash, build-bat, JBR]
created: 2026-07-23
updated: 2026-07-23
status: solved
severity: high
audience: public
refs: [procedural-qt-ohos-run-test, procedural-demo-generation]
summary: >
  hvigor stalls packaging the HAP at PackageHap with `Error Code: 00308018 spawn java ENOENT`. Root cause: the PATH exported in bash is in Unix format
  (`:`-separated + `/c/...` paths), while the Windows node.exe running hvigorw.js reads process.env.PATH expecting Windows format (`;`-separated +
  `C:\...`), so node's child_process.spawn('java') can't find java.exe (node's spawn doesn't append .exe or consult PATHEXT);
  setting JAVA_HOME alone doesn't help (hvigor's PackageHap spawns 'java' directly). Fix: write a native Windows .bat (backslashes + a `;`-separated PATH
  including DevEco's jbr/bin) plus `JAVA_HOME=<DevEco>\jbr`, and run it via cmd.exe /c.
leader_summary: >
  Captured the troubleshooting for hvigor's "spawn java ENOENT" when packaging a HAP: bash's Unix PATH doesn't match what Windows node expects, fixed by switching to a .bat,
  which unblocks CLI builds for every Qt HarmonyOS demo.
impact: [Build troubleshooting, Demo generation, Migration efficiency]
deliverables: [problem record, ${DEMOS_ROOT}/tray-ohos/build.bat]
evidence: [BUILD SUCCESSFUL in 3s 324ms (entry-default-unsigned.hap, 37.7 MB), before/after comparison of the java ENOENT failure]

# ====== Search keywords (for fast agent matching) ======
error_message: >
  > hvigor ERROR: Failed :entry:default@PackageHap...
  > hvigor ERROR: Error Code: 00308018 Unknown Error
  spawn java ENOENT
  * Try: Run with --stacktrace / --debug option ...
  > hvigor ERROR: BUILD FAILED
  (all the C++/ArkTS compiles succeed; only the final PackageHap fails)
error_code: "00308018"
keywords: [spawn java ENOENT, PackageHap, 00308018, hvigor, java not found, windows PATH, bash PATH, node spawn, java.exe, JBR, DEVECO, build.bat, cmd.exe]
symptoms: >
  Running `node hvigorw.js assembleHap` from bash for a Qt5 HarmonyOS demo: CMake/ninja compiles the C++ fine and ArkTS compiles fine,
  but the final PackageHap step fails with `spawn java ENOENT`. Even with DevEco's jbr/bin added to PATH, `which java` in bash
  can't find it (or finds it, yet node's spawn still reports ENOENT).

# ====== Problem details ======
environment: >
  Windows 11 + Git Bash (MSYS). DevEco Studio at `C:\Program Files\Huawei\DevEco Studio` (jbr/bin/java.exe =
  JBR 21.0.8). A Qt 5.12 OHOS demo (${DEMOS_ROOT}/tray-ohos). hvigorw.js launched via `node`. Device: HUAWEI MateBook Fold.
---

## Error message

```
> hvigor Finished :entry:default@BuildNativeWithNinja... after 95 ms   ← C++/ninja compile succeeds
> hvigor Finished :entry:default@PackageHap... after 116 ms             ← fails at this point
> hvigor ERROR: Failed :entry:default@PackageHap...
> hvigor ERROR: Error Code: 00308018 Unknown Error
spawn java ENOENT
> hvigor ERROR: BUILD FAILED in 6 s 205 ms
```

## Scenario

Packaging a Qt5 HarmonyOS HAP from the CLI in Git Bash:
```bash
DEVECO="C:/Program Files/Huawei/DevEco Studio"
export DEVECO_SDK_HOME='C:/Program Files/Huawei/DevEco Studio/sdk'
export JAVA_HOME='C:\Program Files\Huawei\DevEco Studio\jbr'
export PATH="$DEVECO/jbr/bin:$DEVECO/tools/node:$PATH"
node "$DEVECO/tools/hvigor/bin/hvigorw.js" assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```
All the C++ and ArkTS compiles succeed, and it gets stuck at `PackageHap` (the HAP packaging + signing step, which needs java).

## Cause

Three factors compound:

1. **On Windows, node's `child_process.spawn('java', ...)` doesn't append `.exe` or consult PATHEXT** (unlike `exec`, which goes through a shell). Even with java.exe on PATH, spawn('java') can still report ENOENT unless the PATH is parsed correctly by the Windows process.
2. **The PATH exported by bash is in Unix format** (`:`-separated + `/c/...` or `C:/...` paths). MSYS converts the PATH format when passing it to a Windows child process, but when the PATH already contains Windows-style `C:/...` entries, that conversion may be incomplete → the Windows node reads a `:`-separated PATH it can't split on `;` → `spawn('java')` finds nothing.
3. **`JAVA_HOME` is ineffective**: hvigor's PackageHap calls `spawn('java')` directly (it doesn't read `JAVA_HOME/bin/java`), so setting JAVA_HOME alone doesn't fix anything.

> Note: this differs from [[build-hvigor-native-skip]] (where a missing DEVECO_SDK_HOME causes the native build to be **skipped**) — here the native build fully succeeds and only the **packaging step** fails because java can't be found.

## Solution

Write a native Windows `.bat` (a PATH using backslashes and `;` separators, including DevEco's jbr/bin) and run it with `cmd.exe /c` so the Windows node gets a correctly formatted PATH:

```bat
@echo off
set "JAVA_HOME=C:\Program Files\Huawei\DevEco Studio\jbr"
set "DEVECO_SDK_HOME=C:\Program Files\Huawei\DevEco Studio\sdk"
set "PATH=C:\Program Files\Huawei\DevEco Studio\jbr\bin;C:\Program Files\Huawei\DevEco Studio\tools\node;%PATH%"
cd /d "${DEMOS_ROOT}/<demo-name>"
where java
node "C:\Program Files\Huawei\DevEco Studio\tools\hvigor\bin\hvigorw.js" assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```

Call it from bash with: `cmd.exe //c "C:\\path\\to\\build.bat"` (`//c` is MSYS's escape for `/c`).

`where java` should print `C:\Program Files\Huawei\DevEco Studio\jbr\bin\java.exe`. After that you get `BUILD SUCCESSFUL`, with the artifact at `entry/build/default/outputs/default/entry-default-unsigned.hap` (unsigned when there's no signingConfig; installing it requires separate signing — see signhap-bundlename-mismatch).

## Notes

- **The CLAUDE.md warning that "Qt OHOS builds must run in PowerShell" applies only to `mingw32-make.exe`** (building the Qt source, where mingw32-make calls `/usr/bin/sh` and swallows backslashes). Demos use hvigor+ninja, so **bash works** — but the PATH format must be native Windows (hence this .bat).
- Setting `JAVA_HOME` alone isn't enough (hvigor doesn't use it to locate java); you must put `jbr\bin` on a Windows-format PATH.
- This .bat also works well placed at a demo's root as a reusable build entry point (${DEMOS_ROOT}/tray-ohos/build.bat follows this pattern).
- Installing an unsigned HAP gives `code:9568320 error: no signature file` — you need to configure a signingConfig in the DevEco GUI (Automatically generate signature, using a Huawei account to generate a bundle-bound .p7b), or reuse an existing signature (see signhap-bundlename-mismatch).

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured the troubleshooting for hvigor's "spawn java ENOENT" when packaging a HAP (bash's Unix PATH vs. what Windows node expects), fixed by switching to a .bat |
| Scope of impact | CLI builds for every Qt HarmonyOS demo, demo generation, migration builds |
| Deliverables | problem record, ${DEMOS_ROOT}/tray-ohos/build.bat |
| Evidence | BUILD SUCCESSFUL in 3s 324ms / entry-default-unsigned.hap 37.7 MB / before-and-after comparison |
| How to reuse | Whenever any Qt HarmonyOS demo reports spawn java ENOENT while packaging a HAP with hvigor from bash, apply the .bat |

## Related

- See semantic/qt-harmonyos-build-run-workflow.md (devecocli/hvigor invocation) — the 5.12 cmake+hvigor commands (this problem adds the Windows PATH details)
- [[procedural-qt-ohos-run-test]] — The build → install → run CLI flow
- [[build-hvigor-native-skip]] — The distinction: a missing DEVECO_SDK_HOME makes the native build **skip** (here the native build fully succeeds and only PackageHap's java lookup fails)
- signhap-bundlename-mismatch — The signing requirement for installing an unsigned HAP
- [[build-fail-bash-path-escape]] — Related: Git Bash path escaping problems (PROGRA~1)
