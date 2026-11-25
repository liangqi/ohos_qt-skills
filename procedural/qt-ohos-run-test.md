---
id: procedural-qt-ohos-run-test
type: procedural
domain: workflow
tags: [qt, harmonyos, device, verification, hdc, hvigor, signing, cli, build, deploy, run, troubleshoot, rendering, lifecycle, window, platform-limits, input-event, run-test, cli-build]
created: 2026-07-08
updated: 2026-09-29
status: active
audience: public
refs: [semantic-qt-harmonyos-build-run-workflow, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-window-model, semantic-qt-harmonyos-lifecycle, problem-render-black-rgba8-zink-mipmap, problem-ohos-mainthread-mismatch, problem-runtime-qpa-plugin-not-found, problem-runtime-fail-libqtdbus-missing, problem-runtime-sqlite-open-database, problem-runtime-dlopen-writable-path, problem-runtime-crash-sandbox-readonly-path, problem-runtime-crash-null-pointer-entry-shim, problem-surfaceholder-nativexcomponent-incompatibility, episodic-quit-deadlock-tsfn, episodic-wa-nativewindow-leave-bug, episodic-toolwindow-crossscreen-flicker, procedural-qt-app-harmonyos-completion, problem-runtime-crash-libqohos-modules-mismatch]
summary: >
  The HarmonyOS run-test workflow (a full CLI flow, a seven-phase loop): environment and SDK pre-checks → static build pre-checks (DT_NEEDED / symbol visibility / QML plugin deployment) →
  signing and installation → launch and runtime testing (localizing the three classes of black-screen rendering failure / Ability lifecycle exit / window behavior regressions / input events / platform limitation regressions) →
  crash log analysis → fix and regress → Playbook B demo. The focus is getting the application running on a physical device, not full feature verification (for the feature-case loop see the application-polish workflow).
  Includes the standard trio (an ASCII loop diagram / the loop exit condition ✅ / gate checks ⚠️). Reused by application porting, build troubleshooting, and fix verification.
leader_summary: >
  Distills a reusable on-device run-test workflow covering the whole chain from source to a running application on real hardware, including deployment pre-checks, localizing the three classes of black screen, lifecycle exit, window behavior, and platform limitation regressions, plus capturing the problems found. For the feature-level case loop see the application-polish workflow.
impact: [faster migration, framework support]
deliverables: [a workflow, captured problems]
evidence: [the <APP_NAME> on-device verification commit, <WORKLOG>]
---

# The HarmonyOS run-test workflow

> **When to use it**: a Qt project that has already been ported to HarmonyOS and needs to run end to end on a physical device (the focus is "getting it running", not full feature verification — for the feature-level case loop see [[qt-app-harmonyos-completion]]).
> **Prerequisites**: the project already has a `HarmonyOS/` project directory + `OhosExampleApp/CMakeLists.txt` + a Qt OHOS SDK.
> **Expected time**: 30-60 minutes (including troubleshooting).

---

## When to use this

- A Qt project that's been ported to HarmonyOS and needs an end-to-end run test on a device (getting the application running)
- An application porting / build troubleshooting / fix verification task that needs an on-device loop (all three reuse this workflow — see routes [A][E][J] in _index/_task-routing.md)
- Desktop/emulator verification isn't enough to expose device-specific rendering, lifecycle and window behavior problems

---

## Flow overview

```
§1 Environment & SDK pre-checks → §2 Build & static pre-checks → §3 Signing & installation → §4 Launch & runtime verification
                                                              │
                              ┌───────────────────────────────┤
                              ↓                               ↓
                         pass → close        crash/anomaly → §5 Crash log analysis → §6 Fix & regress → close
§7 Playbook B demo (an optional appendix for library-only projects)
```

> **📋 TODO sync point**: this is a multi-step workflow — update this task's "progress" column in `<LOCAL_TODO>` at each phase transition (format: `Phase N [complete|in progress]: the key output`); when the task finishes, move it to "✅ Done" in the same session and append to `<WORKLOG>`. Pure lookup tasks don't use this flow.

---

## Phase one: environment and SDK pre-checks

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase one in progress: environment and SDK pre-checks`

### 1.1 Path configuration

Run `setup.ps1` (or `setup.sh`) to replace the placeholders in `entry/build-profile.json5`:

```powershell
powershell -File "HarmonyOS\setup.ps1" -QtSdk "$env:QT5_15_OHOS_SDK"
```

**⚠️ The non-ASCII path pitfall**: `setup.ps1`'s internal `Resolve-Path` can corrupt the encoding of paths containing non-ASCII (e.g. Chinese) characters. If you get mojibake, rewrite `build-profile.json5` by hand.

**⚠️ The hvigor path allowlist**: hvigor **rejects** project paths containing non-ASCII or special characters. The workaround:

```powershell
# Copy it to a pure-ASCII path
Copy-Item -Path "<original path>\ProjectName" -Destination "$env:TEMP\opencode\ProjectName" -Recurse -Force
# Fix the CMake paths in build-profile.json5 to point at the copy
```

### 1.2 Create local.properties

```powershell
"sdk.dir=${env:DEVECO_PATH}\sdk" | Set-Content "HarmonyOS\local.properties" -NoNewline
```

### 1.3 Environment variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `DEVECO_SDK_HOME` | `${DEVECO_PATH}\sdk` | Lets hvigor locate the SDK |
| `PATH` | Append `${DEVECO_PATH}\jbr\bin` | Java (needed to package the HAP) |

```powershell
$env:DEVECO_SDK_HOME = "${env:DEVECO_PATH}\sdk"
$env:PATH = "${env:DEVECO_PATH}\jbr\bin;" + $env:PATH
```

### 1.4 Tool path quick reference

| Tool | Path |
|------|------|
| hvigorw.js | `${DEVECO_PATH}\tools\hvigor\bin\hvigorw.js` |
| node.exe | `${DEVECO_PATH}\tools\node\node.exe` |
| java (JBR) | `${DEVECO_PATH}\jbr\bin\java.exe` |
| hdc | `${DEVECO_PATH}\sdk\default\openharmony\toolchains\hdc.exe` |
| clang | `${DEVECO_PATH}\sdk\default\hms\native\BiSheng\bin\clang.exe` |

### 1.5 Live-verify the SDK modules

> **⚠️ A meta-lesson**: don't trust the KB's static matrix (the "ported" markers on the modules page) — you **must live-verify**. The default SDK and the full SDK differ in module completeness, and the KB matrix records the wiki's porting status, which may not match what's actually available in your local default SDK. Just `ls` and check.

```powershell
# Verify the CMake configs are complete
Get-ChildItem "$env:QT5_15_OHOS_SDK\lib\cmake" -Directory | Select-Object Name
# Verify the Qt module .so files exist
Get-ChildItem "$env:QT5_15_OHOS_SDK\lib" -Filter "libQt5*.so" | Select-Object Name
```

- A missing module (e.g. QuickControls2/Qt3D) → switch to the full SDK (`QT5_15_OHOS_SDK_FULL`), or see the full-SDK rebuild retrospective
- A field lesson: one of the root causes of a black screen in a Qt3D planets demo was that the KB matrix said "ported" while the default SDK actually lacked the Qt3D module — only live verification is trustworthy

### Loop exit conditions (all must hold)

- ✅ hvigorw `--sync` succeeds with no errors
- ✅ The SDK module live-verification passes (all the required CMake configs and `.so` files exist)
- ✅ The project path has no non-ASCII/special characters that conflict with the allowlist

### Outputs

- A `HarmonyOS/` project that syncs
- An SDK module availability list (missing modules filled in, or switched to the full SDK)

> **⚠️ Gate check**: **do not enter phase two** until phase one's exit conditions are met. Building with an incomplete environment/SDK is pointless.

---

## Phase two: building and static pre-checks

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase two in progress: building and static pre-checks`

### 2.1 Building from the command line (recommended)

```powershell
$node = "${env:DEVECO_PATH}\tools\node\node.exe"
$hvigor = "${env:DEVECO_PATH}\tools\hvigor\bin\hvigorw.js"

# clean
& $node $hvigor clean --no-daemon

# build the debug HAP
& $node $hvigor --mode project -p product=default assembleApp -p buildMode=debug --no-daemon
```

### 2.2 Build artifacts

```
entry/build/default/outputs/default/
├── entry-default-unsigned.hap    ← unsigned (can't be installed on a device)
├── entry-default-signed.hap      ← signed (produced once §3 is configured)
└── app/
    └── entry-default.hap         ← an intermediate artifact
```

### 2.3 Verifying the native libraries are complete

```powershell
Get-ChildItem "entry\build\default\intermediates\cmake\default\obj\arm64-v8a" -Filter "*.so" | Select-Object Name
```

**The mandatory checklist** (the core libraries + the categorized plugins; see [[qt-harmonyos-golden-rules]] B7/B12):

| Library | Where it goes | What happens if you miss it |
|---------|---------------|-----------------------------|
| `libqohos.so` | `libs/arm64/` | Crashes at startup with `QPA platform plugin "qohos" not found` (see problem-runtime-qpa-plugin-not-found) |
| `libQt5Core.so` / `libQt5Gui.so` / `libQt5Widgets.so` | `libs/arm64/` | Core functionality missing |
| `libQt5DBus.so` | `libs/arm64/` | `libqohos.so`'s dependency chain breaks (see problem-runtime-fail-libqtdbus-missing — **frequently forgotten**) |
| Your application's library (e.g. `lib<APP_NAME>.so`) | `libs/arm64/` | The application's functionality is missing |
| `libqohosstyle.so` | `libs/arm64-v8a/styles/` | Styling is missing (iron rule B7; copy it manually) |
| `libqsqlite.so` | `libs/arm64-v8a/sqldrivers/` | `addDatabase("QSQLITE")` returns a null driver (iron rule B12, see problem-runtime-sqlite-open-database) |
| `libqsvg.so` | `libs/arm64-v8a/imageformats/` | SVG images don't display (the same class of categorized plugin) |

### 2.4 Static pre-checks for DT_NEEDED / symbol visibility

> **⚠️ A meta-lesson**: do these static pre-checks before deploying so you don't have to come back after `dlopen` fails on the device. For artifacts of a Qt6 OHOS Windows cross build you must **walk every native `.so` inside the HAP**, not just your own library (the Qt framework libraries can be affected too).

```powershell
# Walk every native .so inside the HAP (not just your own library)
$soDir = "entry\build\default\intermediates\cmake\default\obj\arm64-v8a"
Get-ChildItem $soDir -Filter "*.so" | ForEach-Object {
    $f = $_.FullName
    Write-Host "=== $($_.Name) ==="
    # Does DT_NEEDED contain an absolute Windows path (e.g. C:/<absolute path>/lib*.so)?
    & $readelf -d $f | Select-String "NEEDED.*[A-Z]:\\"
    # Is the main symbol GLOBAL DEFAULT (not HIDDEN)?
    & $readelf -s $f | Select-String "\bmain\b.*GLOBAL.*DEFAULT"
}
```

| Anomaly | The related problem | How to fix it |
|---------|---------------------|---------------|
| DT_NEEDED contains an absolute `C:/<absolute path>/lib*.so` | See the _lookup quick reference | Change the CMake to link by bare name, dropping the absolute path |
| The `main` symbol is HIDDEN / not GLOBAL DEFAULT | See the _lookup quick reference | Set `CMAKE_VISIBILITY_INLINES_HIDDEN=OFF` in CMake, or export main explicitly |

### 2.5 Verifying QML / categorized plugin deployment

**Mandatory for QML applications** (otherwise you get a black screen — see the _lookup quick reference):

```powershell
# Copy the SDK's whole qml/ directory into the HAP's resfile (a read-only directory, where dlopen is allowed)
Copy-Item "$env:QT5_15_OHOS_SDK\qml" -Destination "entry\src\main\resources\resfile\qml" -Recurse -Force
```

- At startup the QPA sets `QML2_IMPORT_PATH = bundle/entry/resources/resfile/qml` (verified in the source)
- Verify the `styles/`, `sqldrivers/` and `imageformats/` subdirectory structure (see the §2.3 table)

### 2.6 Debug vs. release build differences

| Aspect | Debug | Release |
|--------|-------|---------|
| `Q_ASSERT` crashes | They fire (e.g. a theMainThread mismatch, see problem-ohos-mainthread-mismatch) | **Silent** (Q_ASSERT compiles away, hiding the problem) |
| Verification strategy | Use Debug for the first verification to expose the assertions | Add a Release pass for stability verification to confirm nothing is hidden |

> **Recommendation**: do the first end-to-end verification with a Debug build to expose `Q_ASSERT`s; once Debug passes, add a Release regression pass so assertion problems don't lurk silently in Release.

### 2.7 Pre-checking that libqohos and the .ets glue template are the same version

> **⚠️ A meta-lesson**: libqohos.so's NAPI `setupQtApplicationImpl` reads a different field name depending on the source version — the 5.12 source (qohosjsmain.cpp:1736) reads `"modulesFactories"` while the 5.15 source (:1735) reads `"modules"`. And which field the OHOS glue template's `QAbilityStage.ets` passes depends on where that template came from (the 5.12 template passes `modulesFactories`). **The SDK's libqohos and the .ets template must come from the same version**, or the app crashes at startup with the jscrash `object has no property named 'modules'` (QAbilityStage.ets:22, see problem-runtime-crash-libqohos-modules-mismatch).

| Where the .ets template came from | The field it passes | The matching SDK (libqohos) |
|---|---|---|
| `${QT5_15_SRC}` (labelled 5.15 in ENV but actually a dirty 5.12 tree) | `modulesFactories` | `${QT5_15_OHOS_SDK}` (the old SDK, whose libqohos reads modulesFactories) |
| A 5.15 template (not in the source tree; obtain it separately) | `modules` | `${QT5_15_OHOS_SDK_FULL}` (the full SDK, whose libqohos reads modules) |

**The rule of thumb**: the reference implementation uses `${QT5_15_OHOS_SDK}` + the 5.12 template → consistent → it runs. If a port agent mistakenly uses `${QT5_15_OHOS_SDK_FULL}` + the 5.12 template → it builds but crashes at runtime. **Producing a HAP ≠ being able to run it**; you must verify on a device in §4.

### Loop exit conditions (all must hold)

- ✅ The HAP builds, with the artifacts in `entry/build/default/outputs/default/`
- ✅ The native library completeness checklist passes in full (including the categorized plugin subdirectories `styles/`/`sqldrivers/`/`imageformats/`)
- ✅ Every DT_NEEDED entry is a bare name with no absolute Windows path
- ✅ The `main` symbol is GLOBAL DEFAULT
- ✅ For QML applications, the `qml/` directory has been deployed to `resfile/qml/`
- ✅ libqohos and the .ets template are the same version (use ${QT5_15_OHOS_SDK_FULL} only with a 5.15 template; otherwise use ${QT5_15_OHOS_SDK})

### Outputs

- A signing-ready HAP (or an unsigned HAP awaiting signing)
- A static pre-check report (DT_NEEDED + symbol visibility + the plugin deployment checklist)

> **⚠️ Gate check**: **do not install on a device** until every static pre-check passes. Deploying something broken just gets you a meaningless "crashes at startup" result and wastes a device round trip.

---

## Phase three: signing and installation

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase three in progress: signing and installation`

### 3.1 Signing configuration

A device refuses to install an unsigned HAP (`code:9568320 error: no signature file`).

**Reuse an existing debug certificate** (extracted from `~/.ohos/config/` or an existing project):

```json5
// build-profile.json5 → app.signingConfigs
{
  "name": "default",
  "type": "HarmonyOS",
  "material": {
    "certpath": "C:\\Users\\<user>\\.ohos\\config\\<name>.cer",
    "keyAlias": "debugKey",
    "keyPassword": "<encrypted>",
    "profile": "C:\\Users\\<user>\\.ohos\\config\\<name>.p7b",
    "signAlg": "SHA256withECDSA",
    "storeFile": "C:\\Users\\<user>\\.ohos\\config\\<name>.p12",
    "storePassword": "<encrypted>"
  }
}
```

**The key point**: the `.p7b` profile is bound to a specific bundleName. You must change `AppScope/app.json5`'s `bundleName` to match the certificate, or SignHap fails (see the _lookup quick reference).

```json5
// AppScope/app.json5
{ "app": { "bundleName": "<the bundleName the certificate is bound to>", ... } }
```

Reference the signingConfig in the products:

> **⚠️ A mandatory step**: defining the certificate in `app.signingConfigs` **isn't enough** — you must also add `"signingConfig": "default"` to `app.products[]` to reference it, or hvigor still produces an unsigned HAP (`entry-default-unsigned.hap` rather than `-signed.hap`) and the device refuses to install it with `code:9568320 error: no signature file`. The sign that it worked: after the build, `entry-default-signed.hap` appears in `entry/build/default/outputs/default/`.

```json5
// build-profile.json5 → app.products
{ "name": "default", "signingConfig": "default", ... }
```

### 3.2 Installing on a device

```powershell
$hdc = "${env:DEVECO_PATH}\sdk\default\openharmony\toolchains\hdc.exe"

# Confirm the device is connected
& $hdc list targets
# It prints the device ID, e.g. <DEVICE_ID>

# Uninstall the old version (if any)
& $hdc uninstall <bundleName>

# Install the signed HAP
& $hdc install "entry\build\default\outputs\default\entry-default-signed.hap"

# With multiple modules (e.g. <EmbeddedUiExtensionHost>), install each one
& $hdc install "<module>\build\default\outputs\default\<module>-default-signed.hap"
```

### Loop exit conditions (all must hold)

- ✅ `hdc install` succeeds (no `error: no signature file`, no `9568320`)
- ✅ The device shows an installation record for the bundleName

### Outputs

- A signed HAP installed on a physical device

---

## Phase four: launch and runtime verification ★ the core of the workflow

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase four in progress: launch and runtime verification`

> **This phase is the heart of the verification**: the process surviving is only the minimum bar — the value of on-device verification lies in the rendering, lifecycle, window, input and platform limitation regressions.

### 4.1 Launch the application and verify the process survives

```powershell
# Get abilityName from module.json5 (usually QAbility or EntryAbility)
& $hdc shell aa start -a <AbilityName> -b <bundleName>

Start-Sleep -Seconds 5
& $hdc shell "ps -ef" | Select-String "<bundleName>"
```

- **Output** → the process is alive; go to §4.2 rendering verification
- **No output** → the process has crashed; go straight to §5 crash log analysis

### 4.2 Verifying rendering correctness

> **⚠️ A meta-lesson**: a screenshot "existing" ≠ rendering being correct. All three classes of black screen show up together on real hardware with different root causes, so use the matrix to tell them apart. **Race conditions and final rendering verdicts must come from a physical device — static analysis gives you a direction, the device gives you the conclusion.**

**The black screen classification matrix**:

| Black screen type | Log signature | Root cause | Fix |
|-------------------|---------------|------------|-----|
| Qt3D RGBA8 mipmap silent pure black | **No GL errors** (completely silent); Phong lighting/JPG textures are fine, only alpha-PNG-textured entities are pure black | ZINK's `glGenerateMipmap` fails on RGBA8 alpha textures → the mipmap is incomplete → sampling returns 0 | Turn mipmaps off for alpha-PNG entities (`generateMipMaps:false` + `minificationFilter:Texture.Linear`) and guard with `Qt.platform.pluginName!=="ohos"` (note that `Qt.platform.os` returns "linux" on OHOS, so a guard on it never fires) — see problem-render-black-rgba8-zink-mipmap |
| EGL_BAD_CONFIG black screen | `Cannot find EGLConfig` + `Failed to create surface with error: 12293 - EGL_BAD_CONFIG` | `QSurfaceFormat::setSamples(4)` requests 4x MSAA and OHOS EGL has no matching config | Add a `#ifndef Q_OS_OHOS` guard to drop the samples (keeping depth24+stencil8) — see the _lookup quick reference |
| QML modules not deployed black screen | `module "Qt3D"/"QtQuick"/"QtQuick.Scene3D" is not installed`; the process doesn't crash but the QML tree fails to load → blank | The HAP has no `qml/` directory, so the QML type plugins aren't deployed | Copy the SDK's `qml/` into `entry/src/main/resources/resfile/qml/` — see §2.5 / the _lookup quick reference |

**The black screen localization loop**:

```
┌──────────────────────────────────────────────────────────┐
│  Start the black screen diagnostic loop                   │
│  ↓                                                       │
│  4.2a Get hilog + a screenshot                            │
│  ↓                                                       │
│  4.2b Do the logs contain EGL_BAD_CONFIG / 12293 ?        │
│  ├─ Yes → an EGL sample config problem (setSamples(4))    │
│  │       → add a Q_OS_OHOS guard → back to phase two      │
│  └─ No ↓                                                  │
│  4.2c Do the logs contain "module not installed" / a QML  │
│       error ?                                             │
│  ├─ Yes → QML modules not deployed                        │
│  │       → copy the SDK's qml/ into resfile/qml/          │
│  │       → back to phase two                              │
│  └─ No ↓                                                  │
│  4.2d No GL errors and the screenshot is pure black ?     │
│  ├─ Yes → likely the ZINK mipmap black (RGBA alpha-PNG)   │
│  │       → turn mipmaps off for alpha-PNG entities        │
│  │         (guarding on pluginName)                       │
│  │       → back to phase two                              │
│  └─ No → not one of the three; go to phase five           │
│                                                           │
│  Exit condition: the screenshot isn't pure black and      │
│  there are no EGL/QML errors                              │
└──────────────────────────────────────────────────────────┘
```

**Screenshot verification** (kept and extended into a "screenshot comparison"):

```
# Through the DevEco MCP
deveco-mcp_perform_ui_action(actionType="screenshot", hvd="<device name>", localPath="<save path>")

# Or from the hdc command line
& $hdc shell uitest screenCap -p /data/local/tmp/screenshot.png
& $hdc file recv /data/local/tmp/screenshot.png <local path>
```

**Race-condition rendering problems**: if, while dragging or resizing a window, the size the surface reports is decoupled from the native geometry (the match=0 smoking gun), it's a HarmonyOS system-side bug — move to system issue verification and analysis.

### 4.3 Ability lifecycle and exit verification

> See the gold standard in [[qt-harmonyos-lifecycle]] + iron rule L1 in [[qt-harmonyos-golden-rules]].

| Check | Action | Expected | Related failures |
|-------|--------|----------|------------------|
| The 3 levels of closeEvent | Trigger WindowStageClose (L1) and AbilityClose (L2) separately | L1 may show a dialog; L2 **must not show any UI** (a dialog hangs the close flow and the system force-kills the app) — autoSave only | Violating iron rule L1 → the dialog hangs |
| Exiting with `qApp->quit()` | Call quit() | The process exits promptly | A ~2-minute deadlock instead (HarmonyOS doesn't process NAPI TSFN callbacks during Ability destruction, so the Promise never resolves) — see episodic-quit-deadlock-tsfn |
| theMainThread matching | Click/type in a Debug build | Input events work | A `Q_ASSERT` crash in Debug (`sendThroughApplicationEventFilters` theMainThread mismatch) — see problem-ohos-mainthread-mismatch; **silent in Release**, so verify in Debug |

### 4.4 Window behavior regression verification

> See [[qt-harmonyos-window-model]] + iron rules W1-W5 in [[qt-harmonyos-golden-rules]].

| Check | Action | Expected | Related |
|-------|--------|----------|---------|
| Subwindow tagging order | Call `tagWindowOrWidgetAsSubWindowOf()` before the subwindow's `show()`/`winId()` | The subwindow belongs to the right main window | Iron rule W1; for event-bug methodology see episodic-wa-nativewindow-leave-bug (a 10-scenario risk matrix) |
| Dialog-as-main-window | Pop up a parentless `QDialog` | No separate Dock icon or Alt+Tab entry appears | Iron rule W3; for MDI switching breaking after a dialog see the _lookup quick reference |
| First-window fullscreen order | `show()` first, then `showFullScreen()` | The first window goes fullscreen correctly | Iron rule W4 (going fullscreen directly at startup misbehaves) |
| hide → minimize | `hide()` the main window | It degrades to minimizing (with no system tray, unlike desktop behavior) | Iron rule W5 |
| Cross-screen dragging | Drag the window to another screen | No flicker | The moveWindowToGlobalDisplay/resizeAsync conflict — see episodic-toolwindow-crossscreen-flicker |
| SurfaceHolder opaque | Set the surface opaque | Opaque takes effect | SurfaceHolder (the Node API) and OH_NativeXComponent (the old NAPI) are mutually exclusive — see problem-surfaceholder-nativexcomponent-incompatibility (a known open issue) |

### 4.5 Input event verification

| Check | Action | Expected | Related |
|-------|--------|----------|---------|
| Mouse clicks | Click a button/menu | It responds correctly | — |
| Touch | Touch interaction | It responds correctly | — |
| Hover | Hover the mouse | The hover callback fires | Unreliable hover callbacks are one half of the dual blind spot (see episodic-wa-nativewindow-leave-bug) |
| Leave events | Move the mouse out of the window | The Leave event fires | The unresponsive-Leave dual blind spot (an "event convergence point" fix; 5 methodology points in episodic-wa-nativewindow-leave-bug) |

> **How to verify**: perform the action and watch the event sequence in `hilog` at the same time to confirm the event delivery path is intact.

### 4.5.1 UI injection in practice (CLI automated verification, distilled from hands-on work in 2026-09)

> **⚠️ Meta-lesson (clicking an occluding window by mistake)**: before injecting a click, you must first get the target window's rect with `hidumper -s WindowManagerService -a '-a'` **and confirm it's the application window with the highest Z order**. In practice, a leftover test application's window (with a higher ZOrd) happened to cover the target point, so the injected click landed on the occluding window and sent the application under test into recent tasks, requiring manual intervention by the owner. **Force-stop unrelated third-party test applications before starting the test**, and before injecting, check that the target point falls only inside the window under test.

| Injection need | Command | Key points |
|---------|------|------|
| Key press | `hdc shell "uitest uiInput keyEvent <keyID>"` | OHOS key codes: digits 0-9 = 2000-2009, letters start at A=2017 and increase (R=2034, E=2021); click the center of the target window to focus it before injecting |
| Click | `uitest uiInput click <x> <y>` | Absolute coordinates; check the window rect and Z order first (see the meta-lesson above) |
| PC window edge resize | `uitest uiInput drag <corner x> <corner y> <x2> <y2> 200` | **A touch drag from the midpoint of an edge doesn't trigger a PC resize; only a corner drag works**; after a window resize the remembered normal geometry changes, so re-read the rect before dragging |
| Relative mouse movement | `uinput -M -m <dx> <dy>` | **Affected by acceleration, so unusable for absolute positioning** (and -q doesn't report coordinates either); don't use it |
| Judging stepped vs. continuous resize | Sample the rect with `hidumper` in a loop during the drag | Keyframe strategy on = holds for ~interval and then jumps; off = continuous small steps at every sample point; the two time series can be told apart objectively, without relying on eyeballing |

- **hilog buffer**: on a device producing lots of logs, the default ring buffer flushes out the verification logs in ~1 min; for long sessions first enlarge it with `hdc shell "hilog -G 16M"`, and save to disk separately per scenario (`hilog -x > logs/hilog-s<n>.log`).
- Background streaming capture (`hdc shell hilog -x > file &`) is interrupted when the host shell exits, so don't rely on it; use per-scenario snapshots instead.

### 4.6 Platform limitation regression checklist

> See the 8 categories in [[qt-harmonyos-platform-limits]] + iron rules P1-P5/G1-G2 in [[qt-harmonyos-golden-rules]]. Confirm item by item that the application doesn't misuse a restricted API.

| Limitation class | How to verify | Expected | Related |
|------------------|---------------|----------|---------|
| chmod unavailable | `QFile::setPermissions()` | Returns false, failing silently | P1; QTBUG-146619 |
| symlink forbidden | `QFile::link()` | EACCES 13900012 | P2; QTBUG-146621 |
| stat on system paths | `QFileInfo("/bin/sh").isFile()` | false (stat returns EACCES) | findExecutable breaks; QTBUG-146625 |
| dlopen rejects writable paths | Load a .so from `/data/storage/el2/` | EINVAL errno=22 (only the read-only el1 is accessible) | P3; see problem-runtime-dlopen-writable-path |
| No tzdata | `QTimeZone::systemTimeZone()` | Needs the ICU backend | P5; QTBUG-146717 |
| No monospace font | `QFontDatabase::systemFont(FixedFont)` | Returns a non-monospace font; ship your own | QTBUG-146623 |
| XComponent deprecated | The SURFACE type | Deprecated in API 20; migrate towards ContentSlot | QTBUG-146622 |
| ZINK mipmap black + pluginName | `Qt.platform.os` / `Qt.platform.pluginName` | `os` returns "linux" (not "ohos"), so guards must use `pluginName` | G1; see problem-render-black-rgba8-zink-mipmap |

### Loop exit conditions (all must hold)

- ✅ The process is alive (`ps -ef` produces output)
- ✅ The screenshot isn't pure black and the content renders correctly (having ruled out the three classes of black screen)
- ✅ The 3 levels of closeEvent behave as expected (L1 may show UI / L2 must not)
- ✅ The window behavior regression checklist passes in full (tagging/dialogs/fullscreen/hide/cross-screen)
- ✅ Input events respond correctly (clicks/touch/hover/Leave)
- ✅ Nothing on the platform limitation regression checklist fires unexpectedly (no restricted API is misused)

### Outputs

- A runtime verification report (screenshots + logs + a behavior comparison table)
- The platform limitation regression checklist (confirmed / worked around / needs fixing)

> **⚠️ Gate check**: if runtime verification doesn't fully pass → go to phase five, crash log analysis. If it all passes → the workflow closes (optionally continue to phase six for regression or phase seven for a demo).

---

## Phase five: crash log analysis and problem localization

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase five in progress: crash log analysis`

### 5.1 Getting the crash log

```
# Through the DevEco MCP (recommended, it parses automatically)
deveco-mcp_get_hilog_or_faultlog_recent(
  bundle_name="<bundleName>",
  is_crash_log=true
)

# Or from the hdc command line
& $hdc shell "hilog -x -e '<bundleName>'" | Select-String "Error|FATAL|SIGSEGV|TypeError"
```

### 5.2 Classifying and investigating the crash

| Crash type | Log signature | Common causes | Where to look |
|------------|---------------|---------------|---------------|
| **JSCrash (TypeError)** | `Cannot read property X of undefined` | A native .so failed to load → the JS module export is undefined | Check the `MUSL-LDSO` log for `Error loading shared library` |
| **SIGSEGV (SEGV_MAPERR)** | `Signal:SIGSEGV@0x...` + C++ stack frames | A null/dangling pointer; the entry shim passing nullptr | Analyze the stack frames; for the entry shim nullptr see problem-runtime-crash-null-pointer-entry-shim |
| **SIGABRT** | `abort` + assertion text | A failed assertion; a theMainThread mismatch; a read-only sandbox path | For theMainThread see problem-ohos-mainthread-mismatch; for the read-only sandbox see problem-runtime-crash-sandbox-readonly-path |
| **dlopen failure** | `dlopen failed` / `library not found` | A missing .so / a wrong path / an absolute DT_NEEDED path / an invisible main | Check the HAP's `libs/arm64/`; see the §2.4 static pre-checks |

**The crash log analysis loop**:

```
┌──────────────────────────────────────────────────────────┐
│  Start the crash analysis loop                            │
│  ↓                                                       │
│  5.1 Get the faultlog (hilog --type crash)               │
│  ↓                                                       │
│  5.2 Classify the crash type                              │
│  ├─ JSCrash (TypeError)                                  │
│  │   → check MUSL-LDSO "Error loading library"           │
│  │   → match a deployment problem in _lookup → fix →     │
│  │     back to building                                   │
│  ├─ SIGSEGV (SEGV_MAPERR)                               │
│  │   ├─ the entry shim passing nullptr? →                │
│  │   │  problem-runtime-crash-null-pointer-entry-shim    │
│  │   └─ no → analyze the C++ frames to find the function │
│  ├─ SIGABRT (an assertion)                              │
│  │   ├─ a theMainThread mismatch? →                      │
│  │   │  problem-ohos-mainthread-mismatch                 │
│  │   ├─ a read-only sandbox path? →                      │
│  │   │  problem-runtime-crash-sandbox-readonly-path      │
│  │   └─ no → read the assertion message                  │
│  └─ a dlopen failure                                     │
│      ├─ an absolute DT_NEEDED path? → see §2.4 /         │
│      │  problem-runtime-absolute-needed-path             │
│      ├─ a writable path? →                               │
│      │  problem-runtime-dlopen-writable-path             │
│      ├─ main invisible? → see §2.4 /                     │
│      │  problem-runtime-main-symbol-hidden               │
│      └─ no → check the HAP's libs/arm64/ directory       │
│  ↓                                                       │
│  5.3 Did it match a known problem ?                       │
│  ├─ Yes → apply the known fix → go to phase six          │
│  └─ No → a new problem → draft a record → go to phase six│
│                                                           │
│  Exit condition: the root cause is localized and a fix    │
│  has been decided                                         │
└──────────────────────────────────────────────────────────┘
```

### 5.3 A quick reference of common runtime problems

> Organized by the _lookup categories, with two-way links into the problem library (deployment issues have been moved out of "runtime" into the "deployment and installation" category).

| Category | Problem | Log keywords | Related problem |
|----------|---------|--------------|-----------------|
| Deployment | The QPA plugin is missing | `QPA platform plugin "qohos" not found` | problem-runtime-qpa-plugin-not-found |
| Deployment | libQt5DBus is missing | `Error loading shared library libQt5DBus.so` | problem-runtime-fail-libqtdbus-missing |
| Deployment | The SQLite driver is missing | `QSQLITE driver not loaded` / `db->open()` returns false | problem-runtime-sqlite-open-database |
| Deployment | QML modules not deployed | `module "Qt3D/QtQuick" is not installed` | See the _lookup quick reference |
| Deployment | An absolute DT_NEEDED path | `needed by C:/<absolute path>/lib*.so` | See the _lookup quick reference |
| Deployment | main not exported | `dlsym() failed to find 'main' symbol` | See the _lookup quick reference |
| Rendering | The RGBA8 mipmap black screen | Qt3D entity textures are pure black with no GL errors | problem-render-black-rgba8-zink-mipmap |
| Rendering | EGL_BAD_CONFIG | `EGL_BAD_CONFIG 12293` / `Cannot find EGLConfig` | See the _lookup quick reference |
| Lifecycle | A theMainThread mismatch | `Q_ASSERT sendThroughApplicationEventFilters` | problem-ohos-mainthread-mismatch |
| Lifecycle | The exit deadlock | It doesn't exit for ~2 minutes after `qApp->quit()` | episodic-quit-deadlock-tsfn |
| Platform limits | dlopen from a writable path | `dlopen errno=22 EINVAL` | problem-runtime-dlopen-writable-path |
| Platform limits | A read-only sandbox SIGABRT | `SIGABRT` + `exit(1)` + a failed configuration write | problem-runtime-crash-sandbox-readonly-path |
| Entry point | The entry shim nullptr | `SIGSEGV` + frames in your own code | problem-runtime-crash-null-pointer-entry-shim |
| Template/SDK version | A libqohos/.ets mismatch | `object has no property named "modules"` / QAbilityStage.ets:22 / exits 1-2s after launch | problem-runtime-crash-libqohos-modules-mismatch |
| Windows | SurfaceHolder opaque doesn't work | `SurfaceHolder_Create returned null` | problem-surfaceholder-nativexcomponent-incompatibility |

### Loop exit conditions (all must hold)

- ✅ The crash's root cause is localized (type + the specific cause)
- ✅ It matched a known problem, or was confirmed to be a new one
- ✅ A fix has been decided

### Outputs

- A crash analysis report (type + stack frames + root cause + the fix)
- A draft record of any new problem (to be captured in phase six)

---

## Phase six: fixing and regression verification

> **📋 TODO sync point**: update `<LOCAL_TODO>` → `Phase six in progress: fixing and regression verification`

### 6.1 The fix process

1. **Localize the root cause**: based on the §5 analysis
2. **Change the source**: edit it in the temporary build directory
3. **Sync back to the original project**: make sure the original project has the fix too
4. **Rebuild**: `hvigorw clean` + `assembleApp` (back to phase two, **rerunning the static pre-checks**)
5. **Uninstall the old version + install the new one**: `hdc uninstall` + `hdc install`
6. **Verify the launch**: `aa start` + `ps -ef` to confirm the process is alive
7. **Confirm the logs**: no Error-level application logs

### 6.2 Capturing the fix in problems/

> **⚠️ A meta-lesson**: fixing one file ≠ fixing one piece of knowledge. Before capturing, `grep` for every reference so the propagation across files isn't missed (this workflow page itself once missed 67% of the places because of a file-by-file fixing habit).

- Use the `_templates/qt-problem.md` template and put the complete error text in the `error_message` field (so agents can full-text search for it)
- Link back to the existing problem library: this workflow's §5.3 quick reference already links 14 problems
- Run `bash _scripts/kb-regen-indexes.sh` to regenerate `problems/_lookup.md` (the symptom quick reference + domain grouping + the deployment/runtime/signing categories; it's a derived index, gitignored, rebuilt automatically from the frontmatter — don't edit it by hand)

### 6.3 Regression verification

- Rebuild + install + launch + verify (back through phases two to four)
- Confirm the original crash/black screen/misbehavior is gone
- Confirm nothing new was introduced (add a Release build regression pass)

---

## Phase seven: writing a Playbook B demo application (an optional appendix)

> When to use it: a playbook B project builds to a static library (`.a`), has no `HarmonyOS/` project directory, and can't be installed on a device directly, so you need to write a playbook A-style demo that links the static library to complete end-to-end verification.

> The demo project structure, the CMakeLists.txt essentials, the main.cpp design principles and the table of verified cases belong to the build recipe (an internal procedural page, not expanded here). This section only covers environment preparation and the handoff to on-device verification.

### 7.1 Preparing the environment

```powershell
# Copy the HarmonyOS/ directory from an existing playbook A project (use the real values from ENV.md; don't hardcode)
$base = "${PROJECTS_ROOT}/<batch-dir>"
robocopy "$base\<APP_NAME>\HarmonyOS" "$base\NewProject\HarmonyOS" /E /XD build .hvigor .cxx node_modules

# Replace the placeholders, the signing config and the bundleName (as in §1 / §3)
```

### 7.2 On-device verification after building

Once the demo builds, verify it on a device following §1-§6 of this workflow (environment pre-checks → build pre-checks → signing and installation → runtime verification → crash analysis → fix and regress), focusing on the library's runtime behavior on the device (e.g. qhttp's HTTP communication, QSqlMigrator's database migrations).

---

## Quick reference: the complete command sequence

```powershell
# ── Environment ──
$env:DEVECO_SDK_HOME = "${env:DEVECO_PATH}\sdk"
$env:PATH = "${env:DEVECO_PATH}\jbr\bin;" + $env:PATH
$node = "${env:DEVECO_PATH}\tools\node\node.exe"
$hvigor = "${env:DEVECO_PATH}\tools\hvigor\bin\hvigorw.js"
$hdc = "${env:DEVECO_PATH}\sdk\default\openharmony\toolchains\hdc.exe"

# ── Build ──
& $node $hvigor clean --no-daemon
& $node $hvigor --mode project -p product=default assembleApp -p buildMode=debug --no-daemon

# ── Install ──
& $hdc uninstall <bundleName>
& $hdc install "entry\build\default\outputs\default\entry-default-signed.hap"

# ── Launch ──
& $hdc shell aa start -a <AbilityName> -b <bundleName>
Start-Sleep -Seconds 5
& $hdc shell "ps -ef" | Select-String "<bundleName>"

# ── Logs ──
& $hdc shell "hilog -x -e '<bundleName>' -L E"
```

---

## Checklist (confirming the workflow is closed)

- [ ] Phase one: the SDK pre-checks pass and hvigor sync succeeds (SDK modules live-verified)
- [ ] Phase two: the HAP builds and every static pre-check passes (native library completeness + DT_NEEDED + symbol visibility + QML plugin deployment)
- [ ] Phase three: the signed HAP installs successfully
- [ ] Phase four: the process is alive + rendering is correct + the lifecycle/window/input/platform-limitation regressions all pass
- [ ] Phase five: no unresolved crashes (or the root cause is localized and a fix has been decided)
- [ ] Phase six: the fix has been regression-verified and the problem captured in `problems/`
- [ ] Index sync: `bash _scripts/kb-regen-indexes.sh` has been run to regenerate `_map.md` and the other derived indexes (if any page summaries changed), and a git commit has been made

---

## Common problem patterns

| Pattern | Symptom | Where to look | Related problem |
|---------|---------|---------------|-----------------|
| Crashes at startup | `dlopen failed` | A missing .so / a wrong path | problem-runtime-qpa-plugin-not-found, problem-runtime-fail-libqtdbus-missing |
| A black screen with no rendering | The screenshot is pure black | The black screen classification matrix (§4.2) | problem-render-black-rgba8-zink-mipmap, see the _lookup quick reference |
| A crash on input | `SIGSEGV` + `Q_ASSERT` | A theMainThread mismatch | problem-ohos-mainthread-mismatch |
| Hangs on exit | No response after `quit()` | The TSFN deadlock | episodic-quit-deadlock-tsfn |
| A sandbox crash | `SIGABRT` + `exit(1)` | A read-only path for the configuration file | problem-runtime-crash-sandbox-readonly-path |
| Window misbehavior | A separate Dock icon / tagging not taking effect | The subwindow rules | [[qt-harmonyos-window-model]] W1-W5 |

---

## Supply chain

> See §"Application porting" of the workflow supply chain (this page is the on-device verification sub-step of application porting, and is also reused by build troubleshooting and fix verification)

| Aspect | Details |
|--------|---------|
| **Upstream sources** | A migrated project / build troubleshooting that needs on-device verification / regression verification after a fix |
| **Upstream inputs** | A built HAP + the signing configuration + a target device |
| **Downstream recipients** | The migration delivery loop / troubleshooting conclusions / regression reports |
| **Deliverables** | A runtime verification report + a crash analysis report + captured problems |
| **Deliverables path** | No fixed directory (the results flow back into the upstream task) |
| **Routing rules** | A framework bug found → move to framework issue analysis; a system problem found → move to system issue verification and analysis; a known problem → look it up in `_lookup` |

---

## Related context

- [[qt-harmonyos-build-run-workflow]] — Building and running through the DevEco MCP (this page covers the CLI route)
- [[ohos-common-kb/semantic/deveco-mcp-capabilities|DevEco MCP capabilities and boundaries]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/deveco-mcp-capabilities.md)) — General installation, configuration, and capability boundaries
- [[qt-harmonyos-project-structure]] — The project structure in detail
- [[qt-harmonyos-golden-rules]] — The 35 iron rules (B7/B12 deployment, W1-W5 windows, L1 lifecycle, P1-P5/G1-G2 platform limitations)
- [[qt-harmonyos-platform-limits]] — The 8 categories of platform limitation (canonical for the §4.6 checklist)
- [[qt-harmonyos-window-model]] — The window model (tagging/first window/fullscreen; canonical for §4.4)
- [[qt-harmonyos-lifecycle]] — The lifecycle (the 3 levels of closeEvent / the Stage model; canonical for §4.3)
- [[qt-app-harmonyos-completion]] — Application polish (once it runs, move on to the feature-level case loop)
- The workflow supply chain — An overview of the workflow supply chain (upstream/downstream relationships and the contact list)

---

## Content sources

| Source type | Notes |
|-------------|-------|
| 🛠️ Working experience | The full CLI command flow, anonymized on-device verification experience, the black screen classification matrix, and the lifecycle/window/input verification checklists |
| 🔍 Framework source | The key QPA plugin file paths and how to check DT_NEEDED/symbol visibility (readelf) |
| 📄 Huawei official documentation | The hdc command reference, the Ability lifecycle documentation, the EGL/XComponent API documentation |
| 📦 The problem library | Anonymized methodology distilled from 14 runtime/deployment problems (see refs) |
| 💼 Postmortems | Verification methodology distilled from 3 public retrospectives (quit-deadlock / wa-nativewindow-leave / toolwindow-crossscreen) |

### Qt framework versions (the verification baseline)

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |

---

## References

- A workflow developed from personal experience verifying Qt on HarmonyOS devices; no external documentation sources
- Field material was anonymized before being written up (project names, device IDs and paths are all replaced with placeholders)
- The methodology draws on Qt's internal QA process + the retrospectives in this library's `episodic/postmortems/`
