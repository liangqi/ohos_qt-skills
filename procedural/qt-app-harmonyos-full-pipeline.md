---
id: procedural-qt-app-harmonyos-full-pipeline
title: The end-to-end pipeline for porting a Qt application to HarmonyOS
summary: Stitches the scattered Qt-to-HarmonyOS porting workflows into a single end-to-end orchestration: the common library supplies the canonical facts about the HarmonyOS lifecycle, windows, and platform limitations, and this page maps them onto the 8 stages of Qt migration, building, signing, deployment, testing, and store submission. Covers Qt 5.12/5.15/6.12 and flags the gaps in Qt6 end-to-end run+test and application distribution.
type: procedural
domain: procedural
status: active
audience: public
tags: [harmonyos-porting, end-to-end, build, signing, deploy, testing]
refs:
  - procedural-qt-app-harmonyos-migration
  - procedural-qt6-ohos-windows-build
  - procedural-qt6-qtcreator-harmonyos-setup
  - procedural-qt6-ohos-windows-app-dev-guide
  - procedural-qt6-ohos-qtmqtt-build
  - procedural-qt6-cef-ohos-integration-guide
  - procedural-fetch-ohos-third-party-lib
  - procedural-qt-ohos-concrete-build-recipe
  - procedural-qt-ohos-run-test
  - procedural-qt-app-harmonyos-completion
  - procedural-demo-generation
  - procedural-demo-archive-cleancode-upload
  - procedural-fork-qt-app-to-ohos-qt-org
  - semantic-qt-harmonyos-build
  - semantic-qt-harmonyos-build-run-workflow
  - semantic-qt-harmonyos-project-structure
  - semantic-qt-harmonyos-qt6-status
  - semantic-qt-harmonyos-modules
  - semantic-qt-harmonyos-platform-limits
  - semantic-qt-harmonyos-api-mapping
  - semantic-qt-harmonyos-code-patterns
  - semantic-qt-harmonyos-porting-workflow
  - semantic-qt-harmonyos-third-party-libs
  - semantic-qt-ohos-extras
  - semantic-qt-ohos-extras-examples
  - semantic-qt-harmonyos-window-model
  - semantic-qt-harmonyos-lifecycle
  - semantic-qt-harmonyos-api
  - semantic-qt-ohos-project-analyzer-workflow
  - semantic-qt-harmonyos-golden-rules
  - semantic-qt515-vs-qt512-api-diff
  - semantic-qt-harmonyos-accessibility
  - semantic-qt-harmonyos-system-tray
  - semantic-qt-ohos-js-thread-gateway
  - semantic-qt-harmonyos-overview
  - semantic-qt-huawei-cleancode-rules
created: 2026-08-04
updated: 2026-08-15
---

# The end-to-end pipeline for porting a Qt application to HarmonyOS

This page is the **internal orchestration hub for the Qt delivery layer**, stitching the Qt KB's scattered workflows into one chain from obtaining the source/SDK to the final release. HarmonyOS platform facts aren't duplicated here — before executing, the following pages in the common KB are authoritative:

- The Stage/UIAbility lifecycle: [[ohos-common-kb/semantic/stage-uiability-lifecycle|common: the Stage/UIAbility lifecycle]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md))
- The ArkUI window and XComponent model: [[ohos-common-kb/semantic/arkui-window-xcomponent-model|common: the ArkUI window and XComponent model]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/arkui-window-xcomponent-model.md))
- HarmonyOS platform limitations: [[ohos-common-kb/semantic/harmonyos-platform-limits|common: HarmonyOS platform limitations]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md))

The pipeline is organized into 8 stages:

```
Stage 1 Obtain  →  Stage 2 Environment  →  Stage 3 Migration  →  Stage 4 Build
→  Stage 5 Signing  →  Stage 6 Deploy & run  →  Stage 7 Test  →  Stage 8 Upload/publish
```

> **A note on the stage mapping**: the KB's original 6-stage model was `download → compile → sign → run → test → upload`. This pipeline explicitly inserts a "migration" stage between `download` and `compile` (carrying the 8-step decision tree / 14 code patterns / 13 API mapping categories / platform limitation handling) and splits `deploy` (installing on a device) out of `run` into its own "deploy & run" stage. The gaps are flagged as "⚠️ Not covered by the KB" at the end of each stage.
>
> **A timing overview (important)**: the static pre-checks (DT_NEEDED / main visibility / QML deployment) are a **hard gate** between compile and install and must be done before installing on a device. Within the run-test seven-phase loop the order is §2 (build + static pre-checks) → §3 (signing + install) → §4 (launch + runtime verification), i.e. the pre-checks come before the install. This page lists deploy/run as stage 6 and test as stage 7 because it splits things into "first deployment smoke test / the formal verification loop"; that does **not** mean the pre-checks happen after installing (see the stage 4 outputs and the timing clarification).

---

## Stage 1: obtaining what you need (download)

### Goal
Obtain every input a Qt HarmonyOS port needs: the Qt source tree or a prebuilt SDK (the arm64-v8a target kit + the MinGW host kit), the third-party library .so files, and DevEco Studio with its OHOS SDK (the native sysroot + clang + hvigor + node + jbr).

### Prerequisites (upstream deliverables)
- Upstream: Huawei's HarmonyOS system + the Qt Project Gerrit (codereview.qt-project.org) providing the tqtc-qt5 source + Huawei's official IDE/SDK
- Upstream sources (on the business side): HarmonyOS migration requests from commercial Qt customers / internal marketing demo requests / self-driven (assessing the feasibility of a new scenario)

### Steps

#### 1.1 Getting the Qt5 source (cloning from Gerrit)
Source: `qt-harmonyos-overview` / `qt-harmonyos-build`

1. Log in to Gerrit (https://codereview.qt-project.org) → Settings → HTTP Credentials → GENERATE NEW PASSWORD
2. Clone + switch branch + initialize the submodules:
```bash
git clone https://codereview.qt-project.org/qt/tqtc-qt5
cd tqtc-qt5
git checkout tqtc/harmonyos-5.12.12   # or tqtc/harmonyos-5.15.16
git submodule update --init --recursive
```

#### 1.2 Getting the Qt6 source (a source superbuild, strategy B)
Source: `qt6-ohos-windows-build`

```bash
cd <QT6_SRC_ROOT>          # a root directory of your choice, with no spaces
git clone git://code.qt.io/qt/qt5.git
cd qt5
git reset --hard c7581743be5270fbf4343508123a0897487cca87   # Qt 6.12.0
git submodule update --init qtbase qtsvg qtimageformats qtshadertools qtlanguageserver qtdeclarative
```

#### 1.3 Getting the Qt6 prebuilt installer (strategy B', recommended)
Source: `qt6-ohos-windows-app-dev-guide` / `qt6-qtcreator-harmonyos-setup`

Under Qt 6.12.0 in the Qt online installer (the maintenance tool), check at least:
- **HarmonyOS arm64_v8a** (required, = `<QT6_OHOS_KIT>`; its bin/ contains no .exe at all — only .bat wrappers, a few tool .so files, and shell scripts)
- **MinGW 64-bit** (the required host kit = `<QT6_HOST>`, containing qmake.exe, harmonydeployqt6.exe and qt-cmake.bat)
- **CMake + Ninja** (optional; you can use the cmake 3.28.2 + ninja 1.12.0 bundled with the OHOS SDK)
- **The Src source component** (which contains add-ons such as Src/qtmqtt, or you can git clone them later)

> The key insight: the OHOS kit's bin/ has no .exe files — every executable you need (moc/rcc/uic/qmake/harmonydeployqt6) lives in the HOST kit's mingw_64/bin/.

> **⚠️ Not covered by the KB**: this step is purely descriptive (a table of components to check + the DevEco install) with no `maintenance-tool.exe --install ...` CLI, which is asymmetric with the command density of stage 4 §4.3's B' compile. **The minimal viable suggestion**: add the maintenance-tool CLI, or archive a screenshot of the checked component list (the current list serves as the stand-in).

#### 1.4 Installing DevEco Studio + the OHOS SDK
Source: `qt6-ohos-windows-app-dev-guide` / `qt6-ohos-qtmqtt-build` / `qt6-cef-ohos-integration-guide`

- Install it into a **root directory with no spaces** (`D:/DevEco` = `<DEVECO>` is recommended; don't use the default `C:/Program Files/Huawei/DevEco Studio` — the spaces break the build and packaging)
- The OHOS SDK lands at `<DEVECO>/sdk/default/openharmony/native` = `<NATIVE_OHOS_SDK>` (the native sysroot + clang + cmake/ninja + ohos.toolchain.cmake)
- Verify the API level: read the `apiVersion` field of `<NATIVE_OHOS_SDK>/oh-uni-package.json` (on this machine = 24, HarmonyOS 6.1.1)
- DevEco provides the HAP packaging chain (hvigor + node + jbr + ohpm)

#### 1.5 Getting prebuilt third-party libraries (Harmonybrew bottles)
Source: `fetch-ohos-third-party-lib`

When a C/C++ third-party library the application needs has an arm64_ohos prebuilt bottle in Harmonybrew (atomgit.com/Harmonybrew/homebrew-core), one command pulls it in and you skip cross-compiling:

```bash
bash _scripts/fetch-ohos-bottle.sh -f abseil -o ${DELIVERABLES_ROOT}/ohos-libs
```

The script pulls the runtime dependencies recursively, verifies the sha256, extracts them, recreates the missing .so symlinks that Windows NTFS turns into copies, and produces `<out-dir>/<formula>/<version>/{lib,include,lib/cmake}` + qmake/CMake link snippets. With no bottle, fall back to cross-compiling from source (see the standalone "Building third-party libraries" section).

#### 1.6 Getting the additional third-party package (for the Qt6 source superbuild)
Source: `qt6-ohos-windows-build`

Download `ohos-additional-packages-20260415.zip` from the link on the official wiki (wiki.qt.io/Building_Qt6_for_HarmonyOS) (Google Drive / Baidu Netdisk) and extract it to `<ADDITIONAL_PACKAGES>` (e.g. `<QT6_SRC_ROOT>/additional-packages/`); it contains the prebuilt fontconfig/freetype/openssl/unicode/node/uuid/brotli/libpng and other third-party libraries (include/, lib/, node-addon-api/, share/).

### Outputs (downstream deliverables)
- The Qt source tree (the tqtc-qt5 HarmonyOS branches) / the Qt6 prebuilt kits (`<QT6_OHOS_KIT>` + `<QT6_HOST>`)
- The third-party .so files (with their CMake configs/headers, in `${DELIVERABLES_ROOT}/ohos-libs/<formula>/<version>/`)
- The DevEco SDK (the native sysroot + clang + hvigor + node + jbr + ohpm)

These feed stage 2's `CMAKE_PREFIX_PATH` / `CMAKE_TOOLCHAIN_FILE` / `QT_CHAINLOAD_TOOLCHAIN_FILE` configuration.

### Caveats and pitfalls
Source: `qt-harmonyos-overview` / `qt6-ohos-windows-build` / `fetch-ohos-third-party-lib`

- The submodules must be initialized with `--init --recursive` or the source is incomplete
- Don't use llvm-mingw clang 22 (it triggers the NTSYSCALLAPI redeclaration and the D3D12MemAlloc -Werror); strategy B's host compiler is MinGW g++ 13.1.0 (bundled with the Qt SDK)
- The only target architecture is arm64-v8a
- In bottle URLs there is a **single hyphen** between the name and the version (`<formula>-<version>.arm64_ohos.bottle[.rebuild].tar.gz`), not Homebrew's default double hyphen
- The .so files inside a bottle are arm64-OpenHarmony ABI — on Windows you can only link them, not run them; running requires deploying to a device
- CloudWAF blocking: the script uses `git clone --sparse` to read the formula, since you can't curl the raw .rb

---

## Stage 2: preparing the environment (env)

### Goal
Configure every environment variable, toolchain path and project skeleton the build/packaging needs, so that later builds find the Qt SDK and the OHOS toolchain on the first try.

### Prerequisites (upstream deliverables)
- The SDK paths, third-party library paths and DevEco install path from stage 1
- The `${PROJECTS_ROOT}` working root (each migration project gets its own folder under it)

### Steps

#### 2.1 Setting the DevEco toolchain environment variables
Source: `qt6-ohos-windows-app-dev-guide` / `qt6-ohos-qtmqtt-build` / `qt6-cef-ohos-integration-guide`

You have to set these in every new shell (shell state doesn't persist).

**The cmd form** (`qt6-ohos-windows-app-dev-guide`):
```bat
set JAVA_HOME=<DEVECO>/jbr
set NODE_HOME=<DEVECO>/tools/node
set DEVECO_SDK_HOME=<DEVECO>
set QT_HARMONYOS_HVIGOR=<DEVECO>/tools/hvigor/bin/hvigorw.bat
set PATH=<NATIVE_OHOS_SDK>/build-tools/cmake/bin;<DEVECO>/tools/node;<DEVECO>/jbr/bin;<DEVECO>/tools/hvigor/bin;<DEVECO>/tools/ohpm/bin;<DEVECO>/sdk/default/openharmony/toolchains;%PATH%
```

**The bash form** (`qt6-ohos-qtmqtt-build`, verified in git-bash):
```bash
export NODE_HOME=<DEVECO>/tools/node
export JAVA_HOME=<DEVECO>/jbr
export DEVECO_SDK_HOME=<DEVECO>/sdk
export QT_HARMONYOS_HVIGOR=<DEVECO>/tools/hvigor/bin/hvigorw.bat
export PATH="<NATIVE_OHOS_SDK>/build-tools/cmake/bin:<DEVECO>/tools/node:<DEVECO>/jbr/bin:<DEVECO>/tools/hvigor/bin:<DEVECO>/tools/ohpm/bin:$PATH"
```

**The PowerShell form** (`qt-ohos-run-test`):
```powershell
$env:DEVECO_SDK_HOME = "${env:DEVECO_PATH}\sdk"
$env:PATH = "${env:DEVECO_PATH}\jbr\bin;" + $env:PATH
```

A quick reference of tool paths: hvigorw.js=`${DEVECO_PATH}\tools\hvigor\bin\hvigorw.js`, node=`${DEVECO_PATH}\tools\node\node.exe`, java=`${DEVECO_PATH}\jbr\bin\java.exe`, hdc=`${DEVECO_PATH}\sdk\default\openharmony\toolchains\hdc.exe`, clang=`${DEVECO_PATH}\sdk\default\openharmony\native\llvm\bin\clang.exe`.

> **⚠️ An inconsistency between the sources (DEVECO_SDK_HOME)**: the cmd form uses `<DEVECO>` (without `/sdk`; source: qt6-ohos-windows-app-dev-guide §3.1), while the bash and PowerShell forms use `<DEVECO>/sdk` (with `/sdk`; sources: qt6-ohos-qtmqtt-build §4.1 / qt-ohos-run-test §1.3). The DevEco SDK layout is `<DEVECO>/sdk/default/openharmony/...`, and hvigor's `DEVECO_SDK_HOME` should normally point at the sdk directory containing `default/openharmony` (i.e. `<DEVECO>/sdk`). **The recommendation**: prefer `<DEVECO>/sdk` (consistent with the bash/PS forms); if hvigor can't find the SDK, try `<DEVECO>` (the cmd form), using whether `hvigorw --sync` resolves the SDK as the test.
>
> **⚠️ Path completeness (the bash form)**: this page has corrected the bash form's PATH node directory from the source's `tools/node/bin` to `tools/node` (matching where `node.exe` actually lives per the quick reference above) and added `<NATIVE_OHOS_SDK>/build-tools/cmake/bin` (qt-cmake.bat depends on cmake being on PATH, see stage 4 §4.3), bringing it in line with the cmd form.

#### 2.2 Deciding between the three Qt6 HarmonyOS porting strategies
Source: `qt-harmonyos-qt6-status`

When a Qt6 HarmonyOS porting request comes in, pick one of three strategies:
- **Strategy A**: downgrade to Qt5 (workable today, using the `QT_VERSION_CHECK` macro for conditional compilation; see `qt-ohos-project-analyzer-workflow` §3.1)
- **Strategy B**: a source superbuild (verified on Windows, a MinGW host + an OHOS Clang target, needing 4 extra Windows configuration items + the DT_NEEDED patch; see stage 4 §4.1-4.2)
- **Strategy B'**: the prebuilt-installer SDK (**recommended**, less work than building from source, eliminating the three big pitfalls of patch_dt_needed / shim-trim / the Qt6_DIR junction; see stage 4 §4.3-4.4)

#### 2.3 Creating the project directory structure
Source: `qt-app-harmonyos-migration` / `qt-ohos-concrete-build-recipe`

```bash
mkdir -p "${PROJECTS_ROOT}/<app-name>-ohos"
```
The naming convention: `<original-app-name>-ohos` (e.g. calculator-ohos), all lowercase with spaces replaced by hyphens.

#### 2.4 Copying the glue template bundled with the Qt source
Source: `qt-app-harmonyos-migration` / `qt-harmonyos-project-structure` / `qt-ohos-concrete-build-recipe` / `qt6-ohos-windows-app-dev-guide`

**The iron rule**: a HarmonyOS project must be generated by copying the glue code template bundled with the Qt source; never create the directory structure by hand. The template contains the complete ArkTS glue, the build-profile and qEmbeddedUiExtensionHost, and creating it by hand very easily misses a critical file.

**The Qt5 path (a manual cp)**:
```bash
cp -r <QT5_15_SRC>/qtbase/src/harmonyos/templates/. "${PROJECTS_ROOT}/<app-name>-ohos/"
# The Qt 5.12 equivalent: <QT5_12_SRC>/qtbase/src/harmonyos/templates
```
The old Gerrit ZIP template route is retired.

**Without the Qt source**: download the standalone template archive `templates-0625.zip` from the GitCode releases:
```bash
bash skills/kb-init/scripts/download-template.sh --dest=workspace/templates
cp -r workspace/templates/. "${PROJECTS_ROOT}/<app-name>-ohos/"
```
Download page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

**The Qt6 strategy B' path (no manual cp needed)**: the prebuilt OHOS kit bundles the template at `<QT6_OHOS_KIT>/src/harmonyos/templates`, and `harmonydeployqt6` copies it into hap-out during the package step (stage 4 §4.3 step 3b) and rewrites `app.json5`/`module.json5`/`QtAppConstants.ets`, so no manual cp is needed. Strategy B's source superbuild still needs a manual cp from the source tree at `<QT6_SRC>/qtbase/src/harmonyos/templates`.

After copying you must (for Qt5/strategy B):
1. Write your Qt C++ source and CMakeLists.txt in `entry/src/main/cpp/`
2. Set `APP_LIBRARY_NAME` in `QtAppConstants.ets`
3. Set `CMAKE_PREFIX_PATH` in `entry/build-profile.json5`
4. Put the Qt runtime library `libqohos.so` into `entry/libs/arm64-v8a/`
5. Manually copy `libqohosstyle.so` into `libs/arm64-v8a/styles/`
6. Change the application's display name

Scenario two (porting an existing project): put the template in a `HarmonyOS/` subdirectory and make `build-profile.json5`'s path an absolute path pointing at the root CMakeLists.txt.

#### 2.5 Changing the application's display name (mandatory)
Source: `qt-app-harmonyos-migration` / `qt-ohos-concrete-build-recipe`

The template's default display names are placeholders (`app_name=ohosQtTemplate`, `QAbility_label=label`), and without changing them the home screen icon and the task manager show the placeholders. **Change the value in string.json, not the label reference in app.json5/module.json5** (the HarmonyOS spec requires labels to go through resource references):

- `AppScope/resources/base/element/string.json`: the `app_name` value → your application name (the home screen icon's name)
- `entry/src/main/resources/{base,en_US,zh_CN}/element/string.json`: the `QAbility_label` value → your application name (change all three locale directories; `zh_CN` can hold the Chinese name)

#### 2.6 A DevEco CLI quick reference (this pipeline is CLI throughout, no MCP)
For general platform command capabilities, common's [[ohos-common-kb/procedural/deveco-cli-usage-rules|DevEco CLI usage rules]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/deveco-cli-usage-rules.md)) is authoritative.

This pipeline uses the command line throughout and doesn't depend on the DevEco MCP. Prefer devecocli for normal project operations; the hvigor/hdc calls kept in the table below are the auditable calls Qt delivery needs when it has to control unsigned HAPs, Ability parameters, the a11y Want, or low-level logs precisely — and they still close through the full Qt gate afterwards:

| Stage | The CLI command | The historical MCP name it corresponds to (not callable) |
|-------|-----------------|----------------------------------------------------------|
| Build and package | `hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon` | build_project |
| Install and launch | `hdc install <signed.hap>` / `hdc shell aa start -b <bundle> -a <ability>` | start_app |
| Logs | `hdc shell "hilog -x -e '<bundle>'"` | get_hilog_or_faultlog_recent |
| Screenshots | `hdc shell uitest screenCap -p <path>` | perform_ui_action(screenshot) |
| The UI widget tree (via the accessibility channel) | `hdc shell uitest dumpLayout -b <bundle>` (requires launching with `aa start --pb io.qt.experimental.enableA11ySupport true`, see `qt-harmonyos-accessibility`) | get_app_ui_tree |
| UI interaction | `hdc shell uitest uiInput click <x> <y>` (the center of the widget's bounds) | perform_ui_action(click) |
| Signing | `java -jar <hap-sign-tool.jar> sign ...` or a build-profile signingConfig | — |

> The historical MCP's `get_app_ui_tree` only reached the XComponent and isn't part of the current deveco-mcp tool set. To get the Qt widget tree, use `uitest dumpLayout` (the accessibility channel) after enabling the Want parameter. The current MCP is only used for check/restart; for its capability boundaries see [[ohos-common-kb/semantic/deveco-mcp-capabilities|DevEco MCP capabilities and boundaries]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/deveco-mcp-capabilities.md)); this pipeline doesn't use the MCP for build/run/UI.

### Outputs (downstream deliverables)
- A working Qt 6.12 HarmonyOS kit configuration (the CMake initial configuration + the environment variables)
- The HarmonyOS project skeleton (with the HarmonyOS/ project directory + OhosExampleApp/CMakeLists.txt + the Qt OHOS SDK paths)
- `local.properties`: `sdk.dir=<DEVECO>\sdk`

These feed stage 3's migration and stage 4's build.

### Caveats and pitfalls
Source: `qt6-ohos-windows-app-dev-guide` / `qt6-qtcreator-harmonyos-setup` / `qt-ohos-run-test`

- The DevEco path must contain no spaces (the default `C:/Program Files/Huawei/DevEco Studio` has spaces and breaks the build/packaging)
- The hvigor project path must be ASCII with no spaces and no non-ASCII characters (hvigor's path allowlist rejects non-ASCII, spaces and special characters)
- cmd defaults to the GBK (936) code page, so hvigor's non-ASCII output shows up as ??? — put `chcp 65001 >nul` on the first line of your script to switch to UTF-8
- A `.bat`'s `set` only affects the current cmd process; `setlocal/endlocal` scopes expire on exit; a manual rerun means setting them again in the same session
- The `DEVECO_PATH`/`OHOS_SDK_NATIVE` registered in ENV.local.md may be the space-containing `C:\Program Files\...` (used by the Qt5 workflow); the Qt 6.12 workflow uses the space-free `C:/DevecoStudio` instead — don't mix them

### ⚠️ Not covered by the KB
- There's no unified "environment preparation checklist" page (it's spread across the first step of each compile workflow). **The minimal viable suggestion**: take this page's §2.1 + §2.4 as the baseline and create `procedural/env-checklist.md` collecting the Qt5/Qt6/strategy B/B' environment checks.

---

## Stage 3: migration (migration)

> **A stage named for a KB gap**: the original 6-stage model went straight from `download` to `compile`, but the core activities of porting Qt to HarmonyOS — source scanning / API mapping / window adaptation / lifecycle adaptation / platform limitation handling / build system adaptation — happen between download and compile, and were lumped into compile or migration with no named stage to carry them. This stage carries them explicitly.

### Goal
Adapt a Qt application's source from another platform (Windows/Linux/macOS/Android/iOS) into HarmonyOS-aware code: pre-flight feasibility → scan for platform-bound APIs → replace them per the API mapping → adapt windows/lifecycle/platform limitations → adapt the build system.

### Prerequisites (upstream deliverables)
- The original Qt project/source (from the upstream sources)
- The target feature requirements
- The Qt version (determined from the APIs the code actually uses, not the .pro declaration)
- The HarmonyOS project skeleton from stage 2

### Steps

#### 3.1 Pre-flight (before you write any CMake)
Source: `qt-app-harmonyos-migration`

Before starting the port for real, run 7 pre-flight checks with grep/source scanning:

```bash
# ① The Qt version (from the code, not the declaration — grep for Qt6-only C++ APIs)
grep -rn "QList::emplace_back\|std::as_const\|QVariant::toModelIndex\|std::ranges\|std::views" src/
# ② Which Qt SDK (the ready-made Qt 5.15.16 vs. a Qt6 6.12 superbuild) — a decision driven by ① the Qt version and ③ module availability together
# ③ Module availability (against the module matrix; the Qt5 SDK lacks Multimedia/D-Bus/WebEngine/Charts/SerialBus/QuickControls2/Quick3D/WebSockets and others)
#    live-verify (don't trust the static matrix table; ls the local SDK to see what's actually available):
ls <QT5_15_OHOS_SDK>/lib/cmake/                       # Qt5: how complete the CMake configs are
ls <QT5_15_OHOS_SDK>/lib/libQt5*.so                   # Qt5: which module .so files exist
ls <QT6_OHOS_KIT>/lib/cmake/                          # Qt6: the CMake configs
ls <QT6_OHOS_KIT>/lib/libQt6*.so                      # Qt6: the module .so files
# ④ The project type
grep -rn "int main(" src/   # → playbook A/B; for source-only projects look for .cpp/.h
# ⑤ Platform coupling
grep -rn "X11\|xcb\|windows.h\|HWND\|WM_\|QDBus\|Cocoa" src/
# ⑥ foreach usage
grep -rn "foreach(\|Q_FOREACH" src/   # if it's used you must OMIT QT_NO_FOREACH (defining it breaks the build)
# ⑦ Third-party dependencies (bundled vs. system, and cross-compilation feasibility)
grep -rn "vcpkg\|conan\|find_package.*REQUIRED\|add_subdirectory.*third_party\|FetchContent" CMakeLists.txt .pro 2>/dev/null
find . -type d \( -name "third_party" -o -name "3rdparty" -o -name "vendor" \) 2>/dev/null   # embedded third-party source trees
```

The pre-flight report decides whether to start the real migration. **The point of the pre-flight is to weed out projects that are bound to fail before you write any CMake** (three real batches totalling 207 applications proved that skipping it makes the agent waste 3-4 build attempts on Qt6 code).

#### 3.2 Feasibility assessment + settling on a playbook
Source: `qt-app-harmonyos-migration` / `qt-ohos-concrete-build-recipe`

Assess six things — the Qt version, module dependencies, platform APIs, UI complexity, child processes and third-party libraries — and produce a feasibility report (portable / has risk items / not portable). Then settle on a playbook by project type:

| Project type | Playbook | Artifact | Build method |
|--------------|----------|----------|--------------|
| application/example (has `int main()`) | A | `entry-default-unsigned.hap` | hvigorw assembleHap + OhosExampleApp + the HarmonyOS template |
| library/plugin/header-only (no main) | B | `libOhos<Slug>.a`/`.so` | cmake + ninja + ohos.toolchain.cmake + ohos-build |

Qt5/Qt6 is an orthogonal axis; both A and B work with either.

#### 3.3 Establishing the context for the Qt adaptation decisions
Source: `qt-harmonyos-porting-workflow`

Read the common specification pages linked above first, then apply those shared constraints to five categories of Qt adaptation decision:

1. Review the Qt conditional branches where `Q_OS_LINUX` and `Q_OS_OHOS` both match;
2. Distinguish which thread the Qt event loop, the QPA, and the ArkUI/Ability callbacks belong to, and prefer the existing QtOhosExtras/QPA bridges;
3. Map the Stage/UIAbility events onto the Qt entry point, signals, Want handling and close events;
4. Explicitly confirm, for each `QWindow`/`QWidget`, whether the QPA maps it to a system main window or a subwindow;
5. Review how `QFile`, `QStandardPaths`, `QPluginLoader` and the third-party library paths comply with the sandbox.

For the complete 8-step Qt-side orchestration see [[qt-harmonyos-porting-workflow]]; the common pages own the platform facts, and this page only puts the checks into the end-to-end delivery order.

#### 3.4 Scanning for platform-dependent code (step 1 of the 8-step decision tree)
Source: `qt-harmonyos-porting-workflow` / `qt-app-harmonyos-completion`

```bash
# Platform macros
grep -rn "Q_OS_WIN\|Q_OS_LINUX\|Q_OS_ANDROID\|Q_OS_MAC" src/
# Platform-dependent APIs
grep -rn "QProcess\|QDesktopServices\|QFileDialog\|QSystemTrayIcon\|setMask()\|showFullScreen()\|chmod()\|symlink()\|dlopen()" src/
# Platform branches in the build configuration
grep -rn "win32 {\|unix {\|android {\|macx {\|if(WIN32)\|if(UNIX AND NOT APPLE)\|if(ANDROID)" .pro CMakeLists.txt
```

#### 3.5 Replacing APIs per the mapping (step 2, 13 categories)
Source: `qt-harmonyos-api-mapping` / `qt-harmonyos-code-patterns`

Work through the 12 categories one by one (13 including argument parsing). The key decision tree:

**Process management (no one-size-fits-all answer)**:
- A headless QProcess → usable as is (you can fork/exec a headless binary inside the HarmonyOS sandbox)
- A Qt program with a UI → `QtOhosExtras::startAppProcess()` / `startNewAbilityInstance()`
- A non-Qt program with a UI → `startAbility(want)`
- Headless but needing native HarmonyOS hosting → `QOhosAppContext::startNoUiChildProcess(libName, args)` (an .so hosted by the Child Process Manager, with no QApplication/GUI pipeline)

```cpp
// Inter-application communication: QDesktopServices::openUrl → startAbility(want)
QtOhosExtras::QOhosWant want;
want.uri = "https://example.com";
want.action = "ohos.want.action.viewData";
QtOhosExtras::startAbility(want);
```

**The filesystem**:
```cpp
#ifndef Q_OS_OHOS
file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
#endif
// symlink → copy the file instead; dlopen → only load .so files from the application's lib directory
```

**Argument parsing**: `argv[0]` is the .so library path, not an executable path, and `want.uri` may occupy `argv[1]`, so never index `argv[N]` directly — use `QCommandLineParser`.

#### 3.6 Window adaptation (step 3)
Source: `qt-harmonyos-window-model` / `qt-harmonyos-code-patterns`

Use the common ArkUI window model to establish the system constraints first, then use the Qt window model page to confirm the QPA mapping and the call ordering:

```cpp
#include <QtPlatformHeaders/QOhosFunctions>
QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(dlg, mainWindow->windowHandle());
dlg->exec();   // tagging before show()/winId()
```

**Iron rule W1**: `tagWindowOrWidgetAsSubWindowOf()` must be called after the main window is created and before the subwindow's `show()` and `winId()`; once the window is shown or the native handle is created, the tag is fixed and has no effect.

**Iron rule W4**: the first window can't go fullscreen directly — it takes two steps, `show()` → `showFullScreen()`.

#### 3.7 Lifecycle adaptation (step 4, the 3 levels of close interception)
Source: `qt-harmonyos-lifecycle` / `qt-harmonyos-code-patterns`

The semantics of the Stage/UIAbility events are defined by the common lifecycle page; the code below only shows how Qt's `closeEvent()` consumes the already-mapped close root cause:

```cpp
void MainWindow::closeEvent(QCloseEvent *event) {
    auto cause = QtOhosExtras::getCloseEventRootCause(event);
    if (cause == QtOhosExtras::CloseEventRootCause::WindowStageClose) {
        // the user closed the window → full interaction is allowed, you can show a QMessageBox
    } else if (cause == QtOhosExtras::CloseEventRootCause::AbilityClose) {
        // the system is reclaiming the Ability → autoSave silently, no dialogs (showing UI gets you force-killed)
        if (unsavedChanges()) autoSave();
        event->accept();
    } else {
        event->accept();   // InternalClose
    }
}
```
The enumerator must use its full path, `QtOhosExtras::CloseEventRootCause::AbilityClose` (the short path doesn't compile for an enum class).

#### 3.8 Handling the Qt impact of the platform limitations (step 5)
Source: `qt-harmonyos-platform-limits` / `qt-harmonyos-third-party-libs`

The limitations themselves and the evidence for them live in the common platform limitations page; in Qt delivery, record the affected wrapper layer and the acceptance result for each:

- `QFile` / `QFileInfo`: whether permissions, links and system path probing need guards or replacements;
- `QPluginLoader` / third-party `.so` files: whether the libraries ship in the HAP at an allowed read-only load location and retain the ELF information loading requires;
- `QTimeZone`: whether an available ICU backend is used;
- `QFontDatabase`: whether the application needs to ship its own monospace font;
- Thread wrappers: whether anything still depends on cancellation semantics the target libc doesn't provide.

For the known behavior of the Qt APIs, the alternative idioms and the QTBUG tracking, see [[qt-harmonyos-platform-limits]] — don't duplicate the platform conclusions in this pipeline.

**Qt6-specific**: a `Q_OS_LINUX` guard isn't trustworthy — Qt6 OHOS defines both `Q_OS_HARMONY` and `Q_OS_LINUX` (it does **not** define `Q_OS_OHOS`, which is the Qt5 kit's macro), so a bare `#ifdef Q_OS_LINUX` guarding desktop-only functionality fires on OHOS too. The correct form is `#if defined(Q_OS_LINUX) && !defined(__OHOS__)`; writing `&& !defined(Q_OS_OHOS)` is always true on Qt6, so it guards nothing.

#### 3.9 Build system adaptation (step 6)
Source: `qt-harmonyos-porting-workflow` / `qt-harmonyos-project-structure` / `qt-ohos-concrete-build-recipe`

**qmake (Qt5 only; the Qt6 module no longer exists standalone — see iron rule B6, and CMake has no find_package)**: the `unix` branch must have `:!ohos` appended (`unix:!android:!macx:!ohos`), or ohos also matches unix and compiles the Linux code; any new `ohos {}` branch must add `QT += ohosextras`.

**CMake (for both Qt5 and Qt6)**: four key settings
```cmake
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)   # ① the cross-compilation search path (iron rule B1)
find_package(Qt5 REQUIRED COMPONENTS Core Gui Widgets)   # ② link the Qt modules
add_library(myapp SHARED ${SOURCES})          # ③ produce a shared library (required by HarmonyOS)
target_link_libraries(myapp PRIVATE Qt5::QOhosPlatformIntegrationPlugin)   # ④ link the QPA plugin (iron rule B2)
```

#### 3.10 The migration completion checklist (12 items)
Source: `qt-harmonyos-porting-workflow`

Every Q_OS_* macro branch handles Q_OS_OHOS / child processes are handled per scenario / every parentless top-level window is tagged as a subwindow / the tagging function is called before show()/winId() / closeEvent handles the cause via getCloseEventRootCause / nothing depends on chmod, symlink or dlopen from a writable path / the .pro/CMake has the ohos condition and QT+=ohosextras / every Qt module used is supported on OHOS / argv[0] isn't treated as an executable path / drag-and-drop data is only read in dropEvent / the first main window doesn't go fullscreen at startup / the main window's hide() behavior has been verified.

### Outputs (downstream deliverables)
- The pre-flight report (Qt version + SDK choice + playbook + module gaps + platform coupling + foreach + third-party dependencies)
- The feasibility report (portable / has risk items / not portable)
- The adapted project source and structure

These feed stage 4's build.

### Caveats and pitfalls
Source: `qt-app-harmonyos-migration` / `qt-harmonyos-api-mapping` / `qt-harmonyos-code-patterns`

- **The "declared Qt5 but actually Qt6 code" trap**: determine the Qt version from the APIs the code actually uses, not from .pro/`QT +=`/the spreadsheet (canonic/B23Downloader went off the rails and took 3-4 build attempts to confirm)
- `QFileDialog` works natively on OHOS with no `#ifdef` replacement needed (the platform plugin QOhosPlatformIntegrationPlugin has built-in native file dialog support)
- A standalone parentless QDialog is treated by the system as a new main window, so set a parent or call `tagWindowOrWidgetAsSubWindowOf()`
- During `dragEnterEvent`/`dragMoveEvent` only the MIME types are available; the complete QMimeData is only available in `dropEvent`
- OHOS Qt Network has no OpenSSL, so SSL branches need a `#ifndef QT_NO_SSL` guard
- OHOS clang 15 doesn't support C++23 P0847 (deducing-this), so switch to CRTP; clang strictly rejects the double implicit conversion MSVC allows, so construct explicitly
- Qt6 OHOS has no DBus (a hard wall): an unconditional `#include <QtDBus>` + Q_OBJECT inheritance / an unguarded `find_package(Qt6 DBus REQUIRED)` → it can't be built, can't be stubbed, and can't be `-DCMAKE_DISABLE`d
- Child-process selection isn't one-size-fits-all (a 2026-07-21 correction to the old "QProcess is unusable" claim)

### ⚠️ Not covered by the KB
- The migration stage has no single named workflow page carrying the complete 8 steps + 13 mapping categories + 14 patterns (they're spread across `qt-harmonyos-porting-workflow` / `qt-harmonyos-api-mapping` / `qt-harmonyos-code-patterns`). **The minimal viable suggestion**: this stage is the stitched-together unified migration reference.

---

## Stage 4: building (compile)

### Goal
Produce an unsigned HAP (`entry-default-unsigned.hap`, `BUILD SUCCESSFUL`) + your .so + `harmony-deployment-settings.json` + the static pre-check report.

> **A KB consistency constraint**: several compile workflows (`qt-app-harmonyos-migration` / `qt-ohos-concrete-build-recipe` / `qt6-ohos-qtmqtt-build`) state explicitly that "the build verification target is an unsigned HAP; signing is a separate follow-up step outside this workflow", and don't configure signing in `build-profile.json5`. The compile→sign handoff means the user jumps to stage 5 themselves.

> **Placeholder conventions**: in this stage `<QT6_SRC>` = the Qt6 superbuild source root (the qt5 repository directory); `<QT6_HOST_BUILD>` = the host build output directory; `<NATIVE_OHOS_SDK>` = `<DEVECO>/sdk/default/openharmony/native` (see stage 1 §1.4); `<ADDITIONAL_PACKAGES>` = the extraction directory of the additional third-party package (see stage 1 §1.6). The strategy B/B' paths use a consistent placeholder style; hardcoding personal absolute paths is forbidden.

### Prerequisites (upstream deliverables)
- The adapted project source and structure from stage 3
- The Qt OHOS SDK (`CMAKE_PREFIX_PATH` pointing at the right Qt SDK)
- `entry/build-profile.json5`'s `externalNativeOptions.path` pointing at the CMakeLists.txt
- `HarmonyOS/local.properties`: `sdk.dir=...`

### Steps (split by Qt version/strategy)

#### 4.1 The Qt6 source superbuild (strategy B)
Source: `qt6-ohos-windows-build`

**The host build** (building the host tools):
```powershell
mkdir <QT6_HOST_BUILD>; cd <QT6_HOST_BUILD>
<QT6_SRC>/configure.bat -release -developer-build -opensource -confirm-license `
  -nomake examples -nomake tests -verbose `
  -submodules qtbase,qtsvg,qtimageformats,qtshadertools,qtlanguageserver,qtdeclarative
cmake --build . --parallel -j14
```
It produces 41 exes + 68 dlls (moc/rcc/uic/qsb/harmonydeployqt/qmlcachegen).

**The target build** (cross-compiling the OHOS build, + the 7 extra Windows CMake variables):
```powershell
<QT6_SRC>/configure.bat -developer-build -nomake tests -debug `
  -no-dbus -no-use-gold-linker -no-pch -no-openssl `
  -ohos-sdk "<DEVECO>/sdk/default/openharmony" `
  -qt-host-path "<QT6_HOST_BUILD>/qtbase" -verbose `
  -submodules qtbase,qtsvg,qtimageformats,qtshadertools,qtlanguageserver,qtdeclarative `
  -- `
  "-DCMAKE_PREFIX_PATH=<ADDITIONAL_PACKAGES>" `
  "-DNodeAddonApi_INCLUDE_DIR=<ADDITIONAL_PACKAGES>/node-addon-api" `
  "-DGLESv2_INCLUDE_DIR=<NATIVE_OHOS_SDK>/sysroot/usr/include" `
  "-DGLESv2_LIBRARY=<NATIVE_OHOS_SDK>/sysroot/usr/lib/aarch64-linux-ohos/libGLESv2.so" `
  "-DEGL_INCLUDE_DIR=<NATIVE_OHOS_SDK>/sysroot/usr/include" `
  "-DEGL_LIBRARY=<NATIVE_OHOS_SDK>/sysroot/usr/lib/aarch64-linux-ohos/libEGL.so" `
  "-DFontconfig_INCLUDE_DIR=<ADDITIONAL_PACKAGES>/include" `
  "-DFontconfig_LIBRARY=<ADDITIONAL_PACKAGES>/lib/libfontconfig.so"
cmake --build . --parallel -j8
```
> The EGL paths follow the same sysroot pattern as GLESv2 (the same include directory, and the lib at `aarch64-linux-ohos/libEGL.so`).
It produces 65 .so files + 7 platform plugins (including the libqohos.so QPA).

#### 4.2 The Qt6 OHOS-specific runtime patch (only for the strategy B source superbuild)
Source: `qt6-ohos-windows-build` / `qt-harmonyos-qt6-status` / `qt-ohos-concrete-build-recipe` [the Qt6 variant]

The strategy B superbuild (§4.1) still uses `-developer-build` → it still writes absolute NEEDED paths, so **both checks are still mandatory** (before deploying to a device):

```bash
patch_needed.py   # rewrite the DT_NEEDED entries of every .so (your libraries + the Qt libraries themselves) to bare names
llvm-readelf -d <lib.so>          # verify NEEDED contains no C:/ absolute paths
llvm-readelf --dyn-syms <lib.so>  # verify main is GLOBAL DEFAULT
# Add __attribute__((visibility("default"))) to main  # only under OHOS
```
When patching NEEDED the byte length must stay the same (the bare name + null padding) so the ELF offsets don't move.

> **Strategy B' prebuilt doesn't have this problem**: the prebuilt .so files already have bare NEEDED names, and `qt_add_executable` already makes main GLOBAL DEFAULT, so no hand-written visibility attribute or patch is needed (see §4.3).

#### 4.3 The Qt6 prebuilt CLI (strategy B', recommended)
Source: `qt6-ohos-windows-app-dev-guide` / `qt6-ohos-qtmqtt-build` / `qt6-cef-ohos-integration-guide`

**Step 1, configure (qt-cmake.bat generates the ninja project)**:
```bat
call "<QT6_OHOS_KIT>/bin/qt-cmake.bat" -S "%SRC%" -B "%BUILD%" -G Ninja ^
  -DCMAKE_TOOLCHAIN_FILE="<QT6_OHOS_KIT>/lib/cmake/Qt6/qt.toolchain.cmake" ^
  -DQT_HOST_PATH="<QT6_HOST>" ^
  -DQT_CHAINLOAD_TOOLCHAIN_FILE="<NATIVE_OHOS_SDK>/build/cmake/ohos.toolchain.cmake" ^
  -DOHOS_ARCH=arm64-v8a ^
  -DOHOS_SDK_NATIVE="<NATIVE_OHOS_SDK>" ^
  -DCMAKE_PREFIX_PATH="<QT6_OHOS_KIT>"
```
**Pitfall #1**: calling qt-cmake.bat from a .bat requires `call`, otherwise control transfers to the called .bat and never returns, so the subsequent build/package steps never run and errorlevel=0 makes it look like success.
**Pitfall #3**: `-DQT_CHAINLOAD_TOOLCHAIN_FILE` can't be omitted — it overrides the Linux path hardcoded in qt.toolchain.cmake; without it the OHOS toolchain isn't loaded and clang builds for the host, linking Windows libraries.
**Pitfall #8**: configure printing "Qt6GrpcTools/Protobuf not found" can be ignored (an optional plugin dependency warning).
> qt-cmake.bat depends on cmake being on PATH (put `<NATIVE_OHOS_SDK>/build-tools/cmake/bin` on PATH, see stage 2 §2.1).
Success looks like: `-- Configuring done` / `-- Generating done`. qt_add_executable generates `<target>-harmony-deployment-settings.json` automatically at configure time.

**Step 2, build (cross-compiling your .so)**:
```bash
cmake --build "%BUILD%" --parallel
```

**Step 3a, create hvigor-wrapper.bat to inject java** (fixing spawn java ENOENT, pitfall #5):
```bat
:: hvigor-wrapper.bat — re-inject jbr/bin + JAVA_HOME for hvigorw's node workers
@echo off
set JAVA_HOME=<DEVECO>/jbr
set PATH=<DEVECO>/jbr/bin;<DEVECO>/tools/node;<DEVECO>/tools/hvigor/bin;<NATIVE_OHOS_SDK>/build-tools/cmake/bin;%PATH%
"<DEVECO>/tools/hvigor/bin/hvigorw.bat" %*
```
Comments must use `::` or `rem` with ASCII text only — never non-ASCII text after rem, because on the GBK code page cmd mangles it and tries to execute it as a command.

**Step 3b, package the HAP (harmonydeployqt6)**:
```bat
"<QT6_HOST>/bin/harmonydeployqt6.exe" ^
  --input "%BUILD%/<target>-harmony-deployment-settings.json" ^
  --output "%HAP%" ^
  --hvigor "<WORK>/hvigor-wrapper.bat" ^
  --verbose
```
**Pitfall #2**: harmonydeployqt6.exe is in the HOST kit's bin (not the OHOS kit's bin).
**Pitfall #6**: `--hvigor` must be an absolute path (a relative one reports "Failed to start hvigorw").

harmonydeployqt6 will: copy the HAP template (`<QT6_OHOS_KIT>/src/harmonyos/templates`) → rewrite `app.json5`/`module.json5`/`QtAppConstants.ets` (injecting `APP_LIBRARY_NAME`) → copy your `.so` + the Qt libraries + the plugins + `libc++_shared.so` → call hvigor's `assembleHap`.

Success looks like: `HAP build completed successfully` + `Generated HAP: <HAP>/entry/build/default/outputs/default/entry-default-unsigned.hap`.

#### 4.4 Qt6 IDE configuration (strategy B' + Qt Creator)
Source: `qt6-qtcreator-harmonyos-setup`

Qt Creator → Edit → Preferences → Kits → the harmonyOS kit → CMake → Initial Configuration; clear every existing entry and paste these 9 CMake settings (values without quotes + the correct types FILEPATH/PATH/STRING):
```
-DCMAKE_CXX_COMPILER:FILEPATH=%{Compiler:Executable:Cxx}
-DCMAKE_C_COMPILER:FILEPATH=%{Compiler:Executable:C}
-DCMAKE_PREFIX_PATH:PATH=%{Qt:QT_INSTALL_PREFIX}
-DCMAKE_GENERATOR:STRING=Ninja
-DCMAKE_TOOLCHAIN_FILE:FILEPATH=<QT6_OHOS_KIT>/lib/cmake/Qt6/qt.toolchain.cmake
-DQT_CHAINLOAD_TOOLCHAIN_FILE:FILEPATH=C:/DevecoStudio/sdk/default/openharmony/native/build/cmake/ohos.toolchain.cmake
-DOHOS_SDK_NATIVE:PATH=C:/DevecoStudio/sdk/default/openharmony/native
-DOHOS_ARCH:STRING=arm64-v8a
-DQT_HOST_PATH:PATH=<QT6_HOST_BUILD>
```
plus 5 environment variables in the kit environment (NODE_HOME/JAVA_HOME/DEVECO_SDK_HOME/QT_HARMONYOS_HVIGOR/PATH).

**Three iron rules**:
1. The CMake initial configuration values take no surrounding quotes and must use the correct types — don't leave them `:UNINITIALIZED`
2. `QT_CHAINLOAD_TOOLCHAIN_FILE` must be present and point at a real Windows path (without it you fall back to the default Linux path → clang++ builds for the host → broken)
3. `OHOS_SDK_NATIVE` must come from the same place as the compiler (both from `<DEVECO>/sdk/default/openharmony/native`); keep only one `CMAKE_TOOLCHAIN_FILE`

For packaging use option two, the `_make_hap` target (generated automatically by Qt's CMake, which builds the .so first and then calls harmonydeployqt6):
```
cmake --build . --target samegame_make_hap
```

#### 4.5 Qt5 playbook A (an application → a HAP)
Source: `qt-ohos-concrete-build-recipe` / `qt-app-harmonyos-migration`

**[A1] Write OhosExampleApp/CMakeLists.txt**:
```cmake
project(Ohos<Slug> LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)
if(CMAKE_CROSSCOMPILING)
  set(_saved "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()
find_package(Qt5 5.15 REQUIRED COMPONENTS <Core Gui Widgets Network …>)
set(APP_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../<srcsubdir>")
add_library(Ohos<Slug> SHARED main.cpp ${APP_SOURCES} ${APP_HEADERS} ${APP_FORMS} ${APP_RESOURCES})
target_compile_definitions(Ohos<Slug> PRIVATE QT_DEPRECATED_WARNINGS NO_X11)
target_link_libraries(Ohos<Slug> PRIVATE Qt5::Core Qt5::Gui Qt5::Widgets Qt5::QOhosPlatformIntegrationPlugin)
```
APP_SOURCES comes from the .pro's SOURCES, excluding `*win32*/*x11*/*cocoa*/*osx*/*android*`. Only define `QT_NO_FOREACH` if you've confirmed the project doesn't use Qt's foreach macro; otherwise OMIT it.

**[A2] Write OhosExampleApp/main.cpp (the OHOS entry shim)**:
```cpp
#include <QApplication>
#include "<mainwindow header>"
extern "C" int main(int argc, char *argv[]) {   // the QPA finds the entry point via dlsym("main")
    QApplication app(argc, argv);
    MainWindow w;
    w.show();
    return app.exec();
}
```
Adapt it from the project's original main.cpp: keep the org/app name, the high-DPI setup and the command line parsing; exclude the original main.cpp from APP_SOURCES (the shim replaces it to avoid duplicate symbols). For Qt6, drop the `AA_EnableHighDpiScaling` branch.

**[A3-A5] Configure the 7 files under HarmonyOS/ + copy styles/libqohosstyle.so**:
1. `entry/build-profile.json5`: externalNativeOptions.path (an absolute path), arguments=`-DCMAKE_PREFIX_PATH=...`, abiFilters=`["arm64-v8a"]`
2. `AppScope/app.json5`: bundleName=`com.example.<slug-lower>`
3. `QtAppConstants.ets`: APP_LIBRARY_NAME=`libOhos<Slug>.so`, LOG_TAG
4. `string.json`: app_name → the application name
5. `entry/src/main/resources/{base,en_US,zh_CN}/element/string.json`: QAbility_label → the application name
6. Overwrite the root `build-profile.json5` with the unsigned configuration (`signingConfigs: []`; the template's own signingConfig:"default" is invalid and must be changed)
7. `local.properties`: sdk.dir

Copy: `cp <QT_SDK>/plugins/styles/libqohosstyle.so <project>/HarmonyOS/entry/libs/arm64-v8a/styles/` (the other Qt runtime .so files are linked and packaged automatically by CMake/hvigorw — no manual copying needed).

**[A6] Build with hvigorw → an unsigned HAP**:
```bash
export PATH="/c/Program Files/Huawei/DevEco Studio/jbr/bin:/c/Program Files/Huawei/DevEco Studio/tools/node:$PATH"
export DEVECO_SDK_HOME='C:\Program Files\Huawei\DevEco Studio\sdk'
cd "<…>/HarmonyOS"
node ".../tools/hvigor/bin/hvigorw.js" assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```
Success looks like: `entry/build/default/outputs/default/entry-default-unsigned.hap` exists + `BUILD SUCCESSFUL`.

#### 4.6 Qt5 playbook B (a library → a .a/.so)
Source: `qt-ohos-concrete-build-recipe`

```bash
OHOS_NATIVE="C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/native"
CMAKE="$OHOS_NATIVE/build-tools/cmake/bin/cmake.exe"
NINJA="$OHOS_NATIVE/build-tools/cmake/bin/ninja.exe"
cd "<…>/ohos-build"
"$CMAKE" -S . -B build -G Ninja -DCMAKE_MAKE_PROGRAM="$NINJA" \
  -DCMAKE_TOOLCHAIN_FILE="$OHOS_NATIVE/build/cmake/ohos.toolchain.cmake" \
  -DOHOS_ARCH=arm64-v8a -DCMAKE_PREFIX_PATH="${QT5_15_OHOS_SDK}" \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH
"$CMAKE" --build build
```
Success looks like: `build/libOhos<Slug>.a` (or .so) exists. A library doesn't need the QPA plugin. Prefer writing a fresh minimal CMakeLists that lists the sources directly rather than `add_subdirectory`-ing the original CMake (which often contains Qt6 find_package calls, install/export rules and CPack that pollute the cross build).

#### 4.7 Cross-compiling a Qt6 add-on module (e.g. qtmqtt)
Source: `qt6-ohos-qtmqtt-build`

```bash
QTMQTT_SRC=<QTMQTT_SRC>; KIT=<QT6_OHOS_KIT>; MINGW64=<QT6_HOST>; NATIVE=<NATIVE_OHOS_SDK>
BD=<QTMQTT_SRC>-build-ohos
mkdir -p "$BD" && cd "$BD"
cmd //c "$KIT/bin/qt-cmake.bat" -G Ninja \
  -DQT_HOST_PATH="$MINGW64" -DOHOS_SDK_NATIVE="$NATIVE" \
  -DQT_CHAINLOAD_TOOLCHAIN_FILE="$NATIVE/build/cmake/ohos.toolchain.cmake" \
  -DOHOS_ARCH=arm64-v8a -DCMAKE_PREFIX_PATH="$KIT" \
  -DCMAKE_INSTALL_PREFIX="$KIT" \   # the key move: install into the kit
  -DQT_BUILD_EXAMPLES=OFF -DQT_BUILD_TESTS=OFF "$QTMQTT_SRC"
cmake --build . -j8
cmake --install .   # install into the kit (libQt6Mqtt.so into the kit's lib/, the cmake config into lib/cmake/Qt6Mqtt/, the headers into include/QtMqtt/)
```

Verify: `libQt6Mqtt.so` (~395 KB) has all-bare NEEDED names + `$KIT/lib/cmake/Qt6Mqtt/` has 10 .cmake files + `$KIT/include/QtMqtt/` has the headers.

#### 4.8 Qt6 + CEF integration (a complex third-party engine)
Source: `qt6-cef-ohos-integration-guide`

A 12-step migration path (reusing the Qt5 prebuilt CEF engine + the native adapter + the CEF client layer, with the rework confined to the CMake + the Ability launch glue + the Inject IoC initialization + manually deploying the CEF libraries):

1. Prepare the environment (`export DEVECO_PATH/OHOS_SDK_NATIVE/QT6_SDK/QT_HOST_PATH`)
2. Copy the OpenQtCef project into the workspace
3. Write the Qt6 CMakeLists (`qt_add_executable` instead of `add_library(SHARED)`)
4. Build `libqtmodule.so` with `qt-cmake.bat`
5. Generate the hap-out Qt6 template project with `harmonydeployqt6`
6. Write hvigor-wrapper.bat to fix spawn java ENOENT (pitfall #1)
7. Manually deploy the CEF libraries into hap-out/entry/libs/arm64-v8a/ (pitfall #2 — harmonydeployqt6 doesn't collect .so files CMakeLists linked by absolute path)
8. Migrate the web_engine har module
9. Merge QAbility (extends WebQtAbility, pitfall #4)
10. Merge QAbilityStage + the Inject IoC initialization (pitfall #5, the core one)
11. The CEF permissions (user_grant requires reason+usedScene, pitfall #6)
12. Build a signed HAP (`hvigor-wrapper.bat assembleHap --mode module -p product=default --no-daemon`)

It produces `entry-default-signed.hap` (~261 MB, including the 163 MB libcef.so).

### Outputs (downstream deliverables)
- The unsigned HAP: `entry/build/default/outputs/default/entry-default-unsigned.hap` (gallery ~33 MB; ~70 MB after manually staging the third-party .so files)
- Your library `.so` (in `<BUILD>/`, a MODULE shared library cross-compiled by OHOS clang)
- `<target>-harmony-deployment-settings.json` (the input to the package step)
- The one-command scripts `build-<app>-ohos.bat` + `hvigor-wrapper.bat`
- **The static pre-check report** (bare DT_NEEDED names + main GLOBAL DEFAULT + the plugin deployment checklist) — strategy B does the `patch_needed.py` + readelf verification in §4.2; the full static pre-check (native library completeness / DT_NEEDED / symbol visibility / QML plugin deployment) is formalized in run-test §2 (see the "phase two, build + static pre-checks" row of the stage 7 §7.1 table) as a hard gate on installing

> **⚠️ Timing clarification (static pre-checks vs. installing)**: the static pre-checks are a **hard gate** between compile and install and must be done before installing. Within run-test the order is §2 (build + static pre-checks) → §3 (signing + install) → §4 (launch + runtime verification), i.e. the pre-checks come before the install. This page lists deploy/run as stage 6 and test as stage 7 because it splits things into "first deployment smoke test / the formal verification loop"; that does **not** mean the pre-checks happen after installing. Before installing you must already have passed: strategy B's §4.2 `patch_needed.py` + readelf; and, on every path, run-test §2's static pre-check gate (which precedes §3's install).

### Caveats and pitfalls
Source: `qt6-ohos-windows-app-dev-guide` / `qt6-ohos-qtmqtt-build` / `qt-ohos-concrete-build-recipe` / `qt-app-harmonyos-migration`

- **ABI**: the prebuilt kits only target arm64-v8a (there's no x86_64 kit). DevEco's default emulator is often x86_64 and can't load the arm64 .so you produce — use an arm64 emulator or a real device
- **Pitfall #12 (the most important runtime trap)**: the HAP installs fine with hdc install but aa start flashes and dies, with hilog reporting `dlopen failed: library 'libicui18n.so' not found`. The root cause: the Qt6 kit's Qt .so files carry HARD DT_NEEDED entries on third-party libraries, and harmonydeployqt6 only copies the Qt .so files and plugins listed in deployment-settings.json from the kit without recursively copying the third-party NEEDED entries. The fix: manually stage the 9 third-party .so files into `<HAP>/entry/libs/arm64-v8a/` and repackage with `hvigorw assembleHap --no-daemon` (don't rerun harmonydeployqt6). The HAP grows from ~33 MB to ~70 MB (libicudata alone is ~33 MB)
- **The autouic cross-directory trap**: when the .ui and .cpp files are in different directories, AUTOUIC doesn't automatically search the .ui directory — you must list `CMAKE_AUTOUIC_SEARCH_PATHS` explicitly
- **Disable the x86 intrinsics**: arm64 doesn't support AESNI/SSE/AVX, so don't define macros like `USE_INTEL_AES_IF_AVAILABLE`
- **Infeasibility criteria** (defer straight away, don't enter the build batch): core functionality bound to X11/Win32/D-Bus (QHotkey, qxtglobalshortcut and the like); proprietary or heavyweight native engines (VLC/CEF/Skia and the like); packet capture / system-level work (WinPcap/Winsock2)
- **hvigorw's ArkTS WARNs aren't errors**: the template layer's deprecated NODE/getShared, the napi verification, SDK 5.0.5 on 5.0.0(12) — the build still succeeds
- **The B' route avoids B's three big pitfalls**: the DT_NEEDED patch script (the prebuilt .so files already have bare NEEDED names) / shim-trimming third-party libraries (it's a complete 50+ module distribution, missing only WebEngine/DBus/Wayland/Pdf/Script) / the Qt6_DIR junction for the forwarding headers

### ⚠️ Not covered by the KB
- The compile stage has 8+ overlapping workflow paths with the CMake configuration duplicated across pages, and there's no unified "build recipe index page" routing by SDK source/playbook. **The minimal viable suggestion**: use this stage's §4.1-4.8 as the index table, looking things up along the three axes (Qt5/Qt6) × (playbook A/B) × (strategy B/B').
- **The risk of mixing the two Qt6 CMake modes**: `qt-ohos-concrete-build-recipe`'s Qt6 variant uses `add_library` + a hand-written `main __attribute__((visibility(default)))`, while `qt6-ohos-windows-app-dev-guide` uses `qt_add_executable` (automatic main GLOBAL DEFAULT); the two modes target different SDK sources and don't conflict, but mixing them causes main visibility problems. **The minimal viable suggestion**: use the former for the strategy B source superbuild (§4.1-4.2) and the latter for the strategy B' prebuilt route (§4.3-4.4), and never mix across strategies.

---

## Stage 5: signing (sign)

### Goal
Produce a signed HAP (`entry-default-signed.hap`), with the bundleName bound to the `.p7b` profile verified against `AppScope/app.json5` and `products[]` referencing the `signingConfig`.

> This stage merges the KB's 4 scattered signing methods into one set of steps (they were spread across `qt-ohos-run-test` §3, `qt6-qtcreator-harmonyos-setup` §3.6/§5, common's DevEco CLI rules, and `qt6-ohos-windows-app-dev-guide` §6.3).

### Prerequisites (upstream deliverables)
- The unsigned HAP from stage 4 (`entry-default-unsigned.hap`)
- The debug signing material (a .p12 keystore + a .p7b profile + a .cer, extracted from `~/.ohos/config/` or an existing project)

> **Obtaining the signing material (read this first)**: generating the debug signing material (.p12 + .p7b + .cer) **requires using DevEco Studio at least once** — the single exception to the pure-CLI "no IDE required" promise. The generation entry point is method one below (Auto Signing): sign once in DevEco and Auto Signing generates the debug .p12/.p7b/.cer from its bundled debug keystore + profile, after which the command-line hvigor reuses the same configuration. Without having run method one, methods two/three/four have no material to work with.

### Steps (the 4 methods merged)

#### Method one: DevEco Auto Signing (recommended the first time; the material generation entry point)
Source: `qt6-qtcreator-harmonyos-setup` §3.6 / `qt6-ohos-windows-app-dev-guide` §6.3 / `qt6-cef-ohos-integration-guide`

Open harmonydeployqt6's `--output` (hap-out) directory in DevEco Studio, and DevEco Auto Signing signs the debug HAP with its bundled debug keystore + profile: the first time it walks you through logging into a Huawei developer account and generates the debug .p12 + .p7b + .cer (stored in `~/.ohos/config/`) and signs the debug HAP; afterwards the command-line hvigor reuses the same configuration. hap-out's `build-profile.json5` is configured for signing automatically.

> **⚠️ Not covered by the KB**: method one's exact menu navigation (the precise path through File → Project Structure → Signing Configs → checking "Automatically generate signature") isn't recorded in the source workflows, so you can't do it blind from here. It's worth archiving a screenshot of the menu path the first time, or consulting DevEco's official "signing configuration" documentation.

#### Method two: a build-profile.json5 signingConfig + a products[] reference
Source: `qt-ohos-run-test` §3.1 / `qt6-ohos-windows-app-dev-guide` §6.3/§12

Configure signingConfigs in `<HAP>/build-profile.json5` and **you must add the signingConfig reference to products[]**:
```json
"signingConfigs": [
  {
    "name": "default",
    "type": "HarmonyOS",
    "material": {
      "storeFile": "<KEYS_DIR>/debug.p12",
      "storePassword": "***",
      "keyAlias": "debug",
      "keyPassword": "***",
      "signAlg": "SHA256withECDSA",
      "profile": "<KEYS_DIR>/debug.p7b",
      "certPath": "<KEYS_DIR>/debug.cer"
    }
  }
],
"products": [
  { "name": "default", "signingConfig": "default", ... }
]
```
hvigor's SignHap task does the signing. Without it, hvigor prints `WARN: Will skip sign 'hos_hap'` and the output stays unsigned.

#### Method three: signing separately on the command line with hap-sign-tool.jar
Source: common's DevEco CLI usage rules

```bash
java -jar "<DEVECO>/sdk/default/openharmony/toolchains/lib/hap-sign-tool.jar" sign ...
```
This command is independent of hvigor's signing configuration. From pure CLI you can also self-sign with DevEco's bundled `OpenHarmony.p12`/`OpenHarmonyProfileDebug.pem`.

> **⚠️ Not covered by the KB**: the full sub-arguments/flags of the `sign ...` above were already truncated to `...` in the existing material (a gap at the source), and this page can't fill them in. For the complete sign sub-arguments see Huawei's official [hap-sign-tool documentation](https://developer.huawei.com/) (`--keystore`/`--store-pass`/`--key-alias`/`--key-pass`/`--profile`/`--cert`/`--sign-alg` and so on); it's fairly involved to configure.

#### Method four: harmonydeployqt6's six command-line arguments
Source: `qt6-qtcreator-harmonyos-setup` §3.6/§5

```bash
harmonydeployqt6 --signing-cert-path <.cer> --signing-profile <.p7b> \
  --signing-store-file <.p12> --signing-key-alias <alias> \
  --signing-key-password <the encrypted string> --signing-store-password <the encrypted string>
```
All six must be given together (otherwise the HAP stays unsigned), and the passwords must be hvigor-encrypted strings (not plaintext). To install on a device use `harmonydeployqt6 --install` (via hdc; it needs a connected device and a signed HAP).

> **⚠️ Not covered by the KB**: method four requires the passwords to be hvigor-encrypted strings rather than plaintext, but the source workflows don't explain how to generate that encrypted string from the plaintext. The generation mechanism needs filling in (probably an `encrypt` subcommand of the hvigor/keystore tooling, which the KB doesn't record).

### Outputs (downstream deliverables)
- The signed HAP: `entry/build/default/outputs/default/entry-default-signed.hap`

This feeds stage 6's deploy and run.

### Caveats and pitfalls
Source: `qt-ohos-run-test` §3 / `qt6-ohos-windows-app-dev-guide` §6.3/§12 / common's DevEco CLI usage rules

- **Mandatory**: defining the certificate in `app.signingConfigs` alone isn't enough — you must add a `signingConfig` reference in `app.products[]`, or hvigor still produces an unsigned HAP and the device refuses it with `code:9568320`
- **The .p7b profile is bound to a specific bundleName**: `AppScope/app.json5`'s bundleName must be changed to match the certificate, or SignHap fails
- For a normal package, don't add `--no-build` (that's for verification) or `--install` (that's for installing on a device); only add `--release` for a release
- Generating the debug signing material (.p12 + .p7b) usually requires DevEco Studio at least once — the single exception to the pure-CLI "no IDE required" promise

---

## Stage 6: deploy and run (deploy/run)

> **A stage named for a KB gap**: deploy (installing on a device) is a physically necessary step between sign and run, but the original 6-stage model had no deploy stage. `qt-ohos-run-test` folds deploy into §3.2 (hdc install after signing), and `qt6-ohos-windows-app-dev-guide` folds it into step 10 (merged with run). This stage merges deploy + run.
>
> **The boundary (stage 6 vs. stage 7)**: the runtime verification in §6.2-6.5 here (process survival / the three classes of black screen / lifecycle / windows / input / platform limitation regressions) corresponds to run-test §4 (the "phase four, launch + runtime verification" row of the stage 7 §7.1 table). Stage 6 is the **first deployment plus a run smoke test** (getting to "it runs"), while stage 7 §7.1 is the **gated formal verification loop** (rerunning build → pre-check → sign → install → start → verify with a gate at each phase). The overlap is by design — stage 6 is the quick first verification and stage 7 is the formalized loop.

### Goal
Deploy the signed HAP onto a device/emulator, launch the application, verify the process survives and the rendering isn't a black screen, and produce the run logs and screenshots.

### Prerequisites (upstream deliverables)
- The signed HAP from stage 5
- A target device (a real device reachable by hdc, or an arm64 emulator)
- **The static pre-checks have passed** (see the stage 4 outputs and the timing clarification) — a hard gate on installing. You must already have passed strategy B's §4.2 `patch_needed.py` + readelf verification, and, on every path, run-test §2's static pre-checks (native library completeness / DT_NEEDED / symbol visibility / QML deployment), which come before run-test §3's install

### Steps

#### 6.1 Installing the HAP on the device
Source: `qt-ohos-run-test` §3.2 / `qt6-ohos-windows-app-dev-guide` §10 / `qt6-cef-ohos-integration-guide` step 13

```bash
HDC="<DEVECO>/sdk/default/openharmony/toolchains/hdc.exe"
"$HDC" list targets                          # confirm the device is connected
"$HDC" uninstall <bundleName>                # uninstall the old version
"$HDC" install "entry/build/default/outputs/default/entry-default-signed.hap"
# install each module separately when there are several
"$HDC" install "<module>/build/default/outputs/default/<module>-default-signed.hap"
```
A real device needs developer mode + debug installation allowed + the computer trusted; the emulator is managed by DevEco and hdc recognizes it automatically.

#### 6.2 Launching the application and verifying the process survives
Source: `qt-ohos-run-test` §4.1 / `qt6-ohos-windows-app-dev-guide` §10

```bash
"$HDC" shell aa start -a <AbilityName> -b <bundleName>   # usually QAbility or EntryAbility
sleep 5
"$HDC" shell "ps -ef" | grep "<bundleName>"
```
Output → the process is alive, so move on to rendering verification; no output → the process crashed, so go straight to crash analysis. The bundle name is in deployment-settings.json's harmonyos-app-bundle-name; the launch ability is module.json5's mainElement (which the Qt OHOS template fixes as QAbility, not MainAbility).

#### 6.3 Verifying rendering correctness (telling the three black screens apart)
Source: `qt-ohos-run-test` §4.2

```bash
"$HDC" shell uitest screenCap -p /data/local/tmp/screenshot.png
"$HDC" file recv /data/local/tmp/screenshot.png <local path>
```

**A screenshot "existing" ≠ rendering being correct** — use the matrix to tell the three classes of black screen apart:
1. **The Qt3D RGBA8 mipmap silent pure black** (no GL errors, alpha-PNG entities are pure black, ZINK's glGenerateMipmap fails on RGBA8 alpha) → turn mipmaps off + guard on `Qt.platform.pluginName` (os returns linux on OHOS so a guard on it never fires)
2. **The EGL_BAD_CONFIG black screen** (12293, setSamples(4)'s 4x MSAA has no matching config) → add a Q_OS_OHOS guard to drop the samples
3. **The QML-modules-not-deployed black screen** (module not installed) → copy the SDK's qml/ into `entry/src/main/resources/resfile/qml/`

#### 6.4 Lifecycle/window/input/platform limitation regressions
Source: `qt-ohos-run-test` §4.3-4.6

```bash
"$HDC" shell "hilog -x -e '<bundleName>'"
```
- Lifecycle: the 3 levels of closeEvent (L1 may show a dialog / L2 must not show UI, autoSave only), exiting with `qApp->quit()` (the ~2-minute deadlock — see episodic-quit-deadlock-tsfn), theMainThread matching (a Q_ASSERT crash in Debug, silent in Release, so verify in Debug)
- Windows: the subwindow tagging order (W1), dialog-as-main-window (W3), the first window's fullscreen order (W4), hide → minimize (W5), cross-screen dragging with no flicker
- Input: clicks/touch/hover/Leave (hover and Leave are the unreliable dual blind spot)
- Platform limitation regressions: take the common platform limitation list as the input and verify the corresponding Qt APIs, QPA/QML symptoms and workarounds in [[qt-harmonyos-platform-limits]]; this page doesn't duplicate the platform rule matrix

#### 6.5 Reading the run logs
Source: `qt6-ohos-windows-app-dev-guide` §11 / `qt-harmonyos-build-run-workflow`

```bash
"$HDC" shell "hilog -x -e '<bundleName>'" | grep "Error\|FATAL\|SIGSEGV\|TypeError"
"$HDC" shell hilog | findstr gallery   # Qt's logs are routed through hilog (qOhosLogMessage)
```
Qt-specific runtime log keywords: `dlopen failed: library "libqohos.so" not found` (the platform plugin isn't deployed), `libQt5Core.so not found`, `Cannot load Qt platform plugin`, `module "QtQuick" is not installed`.

### Outputs (downstream deliverables)
- The application running on a device (process alive + non-black rendering + the lifecycle/window/input/platform limitation regressions all passing)
- The hilog run logs
- Screenshots
- The static pre-check report (bare DT_NEEDED names + main GLOBAL DEFAULT + the plugin deployment checklist, from stage 4)

These feed stage 7's testing.

### Caveats and pitfalls
Source: `qt-ohos-run-test` / `qt6-ohos-windows-app-dev-guide` / `qt6-cef-ohos-integration-guide`

- **The non-ASCII path trap**: setup.ps1's internal Resolve-Path can corrupt the encoding of paths with non-ASCII characters; if you get mojibake, rewrite build-profile.json5 by hand
- **The hvigor path allowlist**: hvigor rejects project paths containing non-ASCII or special characters, so copy to a pure-ASCII path (e.g. `$env:TEMP\opencode`)
- **A meta-lesson**: don't trust the KB's static matrix table (the "ported" markers on the modules page) — you must live-verify, because the default SDK and the full SDK differ in module completeness
- **A meta-lesson**: you must static-pre-check DT_NEEDED and symbol visibility before deploying, so you don't have to come back after `dlopen` fails on the device; for Qt6 OHOS Windows cross-build artifacts you must walk every native .so inside the HAP (not just your own library)
- **A meta-lesson**: libqohos.so's NAPI setupQtApplicationImpl reads a different field name depending on the source version (5.12 reads modulesFactories, 5.15 reads modules), so the SDK's libqohos and the .ets template must come from the same version or the app crashes at startup with `jscrash object has no property named 'modules'`
- **Producing a HAP ≠ being able to run it** — verify on a device (qView runs with QT5_15_OHOS_SDK + the 5.12 template; mistakenly using the FULL SDK + the 5.12 template builds but crashes at runtime)
- **Debug vs. Release**: Q_ASSERT compiles away silently in Release; do the first end-to-end run with Debug to expose the assertions, then add a Release regression pass
- **closeEvent L2 must not show UI**: showing a dialog hangs the close flow and the system force-kills the app
- **The qApp->quit() exit deadlock**: NAPI TSFN callbacks aren't processed during Ability destruction, so the Promise never resolves and it doesn't exit for ~2 minutes

### ⚠️ Not covered by the KB
- **There's no unified Qt6 run+test end-to-end workflow** (a gap): the existing `qt-ohos-run-test` seven-phase loop is based on the Qt5 SDK/templates, and Qt6's run+test verification is scattered across individual cases like `qt6-cef-ohos-integration-guide` (on-device launch verification) and `qt6-ohos-qtmqtt-build` (broker loopback verification). `qt6-ohos-windows-app-dev-guide` explicitly marks hdc install/aa start/signing as "not actually run end to end on this machine (no device connected)" operational guidance. **The minimal viable suggestion**: create `procedural/qt6-ohos-run-test.md` mirroring `qt-ohos-run-test`'s seven phases but with the Qt6 HAP generation chain (harmonydeployqt6 + hvigor-wrapper.bat + manually staging the third-party .so files).

---

## Stage 7: testing (test)

### Goal
Move from "the application runs" to "every core feature has been verified": the run-test seven-phase loop + the feature-level 10-case loop.

### Prerequisites (upstream deliverables)
- The application running on a device from stage 6
- Readable application source
- An available device/emulator

### Steps

#### 7.1 The run-test seven-phase loop (qt-ohos-run-test)
Source: `qt-ohos-run-test`

| Phase | Content | Gate |
|-------|---------|------|
| 1 Environment/SDK pre-checks | setup.ps1 placeholder replacement + local.properties + the environment variables + the SDK module live-verification | Phase 1 must pass before phase 2 |
| 2 Build + static pre-checks | The debug HAP build + native library completeness + the DT_NEEDED/main symbol static pre-checks + QML/plugin deployment | No installing on a device until every static pre-check passes |
| 3 Signing + installation | The build-profile signingConfig + the bundleName check + the products[] reference + hdc install | hdc install succeeds |
| 4 Launch + runtime verification | aa start + process survival + telling the three black screens apart + the lifecycle/window/input/platform limitation regressions | All pass |
| 5 Crash log analysis | Classifying JSCrash(TypeError)/SIGSEGV/SIGABRT/dlopen failures + the 14-problem quick reference | The root cause is localized |
| 6 Fixing and regressing | Edit the source → rebuild → uninstall + install → verify the launch → confirm the logs | The original failure is gone and nothing new was introduced |
| 7 Playbook B demo (optional) | For library-only projects, write a playbook A-style demo linking the static library for end-to-end verification | — |

**The gating iron rules**: no entering phase 2 until phase 1's exit conditions are met; no installing on a device until every static pre-check passes; if runtime verification doesn't fully pass, go to phase 5's crash analysis.

> **A note on the ordering**: in the table above phase 2 (static pre-checks) → phase 3 (signing + install) → phase 4 (launch + runtime verification) is run-test's internal order, with the pre-checks before the install. This page's stage 6 (deploy/run) first-deployment smoke test corresponds to the first execution of the table's phases 3 and 4; stage 7's formal loop reruns all seven phases with a gate at each.

#### 7.2 The feature-level 10-case loop (qt-app-harmonyos-completion)
Source: `qt-app-harmonyos-completion`

**Prerequisite**: all seven phases of `qt-ohos-run-test` pass (process survival + rendering + lifecycle + windows + input + platform limitation regressions).

| Phase | Content | Gate |
|-------|---------|------|
| 1 Locating the source and scanning the core features | Mapping the entry chain + grepping to identify the P0/P1/P2 features + flagging the platform-dependent APIs (15-20 items) | No generating cases before the scan is done |
| 2 The AI drafts 10 cases + a human review finalizes them | Each case has the feature, the preconditions, the steps, the expected result, the actual result and the status | No manual testing before they're finalized |
| 3 Running the cases + judging + localizing and fixing + regressing | hdc aa start + manual interaction + screenshots/hilog + rebuilding and regressing after a fix | Closes when all 10 pass |
| 4 The test report + captured problems + closure confirmation | A table of TC#/case name/status/number of fixes/related problem | All 10 ✅ |

**The loop exit iron rule**: all 10 core cases must be ✅ pass (not 9/10), every failed case's fix must be regression-verified (not just claimed fixed), and flaky cases must be reproduced several times to confirm they pass stably.

#### 7.3 The four-step method for build failures and runtime errors
Source: `qt-harmonyos-build-run-workflow` / `qt-ohos-project-analyzer-workflow`

```
Step A Check the knowledge base first: look in compile_fix_pro.md and search for a known solution if it's there
Step B Classify the error: preprocessing (#include not found) / compilation (error: / undefined reference) / linking (undefined symbol / cannot find -l) / packaging (BUILD FAILED / hap / sign)
Step C Fix and retry: at most 3 retries for the same error, each with a different approach; stop immediately and ask the user once you exceed that
Step D Capture the fix: on success, record it in compile_fix_pro.md; on failure, give the user the error message + the root cause analysis + the N approaches tried and why they failed
```

### Outputs (downstream deliverables)
- The test report (all 10 core cases pass / all seven run-test phases pass / adversarial verification passes)
- Captured problems (new `problems/` entries using `_templates/qt-problem.md` + the `problems/_lookup.md` index updated)
- The regression conclusions for the fixes

These feed stage 8's upload/publish.

### Caveats and pitfalls
Source: `qt-ohos-run-test` / `qt-app-harmonyos-completion` / `qt-ohos-project-analyzer-workflow`

- **A meta-lesson**: fixing one file ≠ fixing one piece of knowledge; grep for every reference before capturing so the propagation across files isn't missed (this workflow page itself once missed 67% because of a file-by-file fixing habit)
- **The knowledge-base-first iron rule**: the first step on hitting a problem is searching `compile_fix_pro.md` for a matching solution; skipping the knowledge base and analyzing directly is a violation
- **The platform isolation iron rule**: OHOS adaptations must be isolated behind conditional branches (`Q_OS_OHOS` / CMake `if(OHOS)` / qmake `ohos:{}`); never change the shared logic directly
- **The source-first iron rule**: only change the sources (CMakeLists.txt/.pro/the code), never the generated artifacts (the build directory's Makefiles/intermediates)
- **The gate-failure iron rule**: missing build artifacts / no HAP produced / a failed install / a failed launch / missing Qt .so files → you must not mark it a success
- **The dual cross-check protocol**: it only passes with ✅ (the AI's log review) + ✅ (the user's manual confirmation); the first-round keywords (ERROR/FAILED/fatal/undefined reference/cannot find/No such file/BUILD FAILED/Install Failed/crash/SIGSEGV/SIGABRT) must each be searched for

### ⚠️ Not covered by the KB
- **§6.4 overlaps with §7.1 (run-test §4)**: stage 6's §6.2-6.5 and this stage's §7.1 "phase four, launch + runtime verification" row are both runtime verification (process survival / the three black screens / lifecycle / windows / input / platform limitation regressions). The boundary: stage 6 = the first deployment smoke test (getting to "it runs"), stage 7 §7.1 = the gated formal verification loop. **The minimal viable suggestion**: use stage 6 for the quick first verification and stage 7's loop for troubleshooting/regression.
- In the test stage, `qt-ohos-run-test` §5's crash analysis and `qt-app-harmonyos-completion` §3.5's localization and fixing overlap on hilog analysis and crash localization knowledge. The boundary is defined (run-test = getting it running / completion = getting it correct), but the cross-references are dense. **The minimal viable suggestion**: state the boundary explicitly as "run-test §5 = process-level crashes (SIGSEGV/dlopen/JSCrash)" vs. "completion §3.5 = feature-level failures (pass/fail/flaky)".

---

## Stage 8: upload/publish (upload)

### Goal
Publish the verified HarmonyOS-ported application/demo source to an external repository or archive it.

### Prerequisites (upstream deliverables)
- The test report + captured problems + the regression conclusions from stage 7

> **Delivery routing**: after completion §4's closure confirmation (all 10 cases ✅), you enter this stage. Open-source Qt applications go through §8.1; this month's problem reproduction/verification demos go through §8.2. **There is no KB workflow for distributing a customer application to end users/customers (AppGallery/app stores)** (see the ⚠️ at the end).

#### 8.0 The human review gate (mandatory, before uploading)
Source: new in this pipeline (aligned with demo-generation's human confirmation gate + the dual cross-check protocol)

> **The iron rule**: before uploading/publishing, a human must review and approve ✅; without human confirmation, pushing/committing is forbidden. The AI doesn't make the final publishing decision — publishing to an external repository is irreversible and may be indexed or cached.

Before uploading, a human must confirm each of these:

| Review item | What to confirm | Command/method |
|-------------|-----------------|----------------|
| The test conclusions | The stage 7 test report: all seven run-test phases pass + all 10 completion cases ✅ | Read the test report |
| HAP validity | The signed HAP installs and launches (fresh-clone build verification per §8.1 step 11) | `hdc install` + `aa start` |
| Source cleanliness | No leaked signing keys/absolute paths/build artifacts/caches | The secret grep (`C:/Users`, `keyPassword`, `.p12`/`.p7b`/`.cer`, `.so`, `local.properties`, `/build/`) must come back empty |
| Public safety | No personal paths/names/tokens; no private content on public pages | The 25-item gate §19/§20 |
| Screenshots/docs | Run screenshots + a complete README | Check them by hand |

All human review items ✅ → proceed to §8.1 (the open-source fork) or §8.2 (the demo archive). Any item failing → go back to stage 4/6/7 and fix it; **publishing is forbidden**.

### Steps (split by scenario)

#### 8.1 Publishing an open-source fork to the AtomGit ohos-qt organization
Source: `fork-qt-app-to-ohos-qt-org`

Fork an open-source Qt application that has been ported to HarmonyOS (the scenario-two OhosExampleApp pattern, with an unsigned HAP already built) and upload it to AtomGit (= the renamed GitCode) so external Qt developer partners can clone it and build it themselves.

The 12 steps:
1. A fresh full clone of upstream (not `--depth=1`)
2. Selectively overlay the OHOS files (the subsets of OhosExampleApp/ + HarmonyOS/, excluding build artifacts/caches/local.properties/entry/libs/)
3. Clean up 4 pieces of configuration (overwrite the root build-profile.json5 with the unsigned template; templatize entry/build-profile.json5; change PORT_RESULT.json's hap_path to a relative path; append the automatic .so copy snippet to the end of CMakeLists.txt)
4. Merge the .gitignore (append the OHOS section; if upstream has `*.ts` you must add the `!HarmonyOS/**/*.ts` negation; if upstream has `*build-*` you need the `!HarmonyOS/build-profile.json5` negation)
5. A new README.md, with the original renamed to `README_original.md`
6. The setup scripts (setup.ps1 + setup.sh, with the `<REPO_ROOT>` + `<YOUR_QT_OHOS_SDK>` placeholders)
7. Pre-commit verification (against leaks and artifacts): `git grep -nE 'C:\\Users|C:/Users|keyPassword|storePassword|\.p12|\.p7b|\.cer'` must be empty; `git ls-files | grep -E '\.(so|p12|p7b|cer)$|local\.properties|/build/'` must be empty
8. Commit (with no AI attribution)
9. Create the organization repository through the AtomGit API (`Authorization: Bearer $TOKEN`)
10. Push (token-in-URL + `-c credential.helper=` to disable GCM; force with `--force`, not `--force-with-lease`)
11. Fresh-clone build verification (a clean clone + setup filling in the placeholders + hvigorw assembleHap producing a HAP)
12. Add run screenshots to the README (optional, after the run verification)

#### 8.2 Archiving and packaging demo source per CleanCode
Source: `demo-archive-cleancode-upload` / `qt-huawei-cleancode-rules`

Collect the reproduction/verification demo sources produced by this month's problem handling into an archive folder, tidy them per Huawei's CleanCode (18 rules), preserve the reproduction logic, verify adversarially, then write a README, package and git commit them.

The eight steps:
1. Locate this month's problem demo sources (scan WORKLOG.md + the deliverables directories)
2. Filter for Qt-related .cpp/.h (excluding build artifacts/vendored third-party/non-Qt-native files)
3. Collect them into the archive folder (isolating identically-named files in subdirectories)
4. Tidy them per Huawei CleanCode (the 18 rules: the copyright header / no magic numbers / lines ≤120 / functions ≤50 lines / nesting ≤4 / braces on the same line / braces around control flow / one declaration per line / C++ casts / explicit lambda captures / naming / Qt5 function-pointer signals and slots / override + nullptr / tr() / include order / no file-scope static in headers / inline functions ≤10 lines)
5. **The preserve-the-reproduction-logic iron rule**: don't delete leaked objects, don't add the missing delete, don't change connection semantics, don't change values, keep the root-cause comments, keep `#include "main.moc"`, keep the public API unchanged
6. Adversarial verification (CleanCode + preservation of the reproduction logic + cross-file consistency — three dimensions)
7. Line-count calibration (optional)
8. The README + packaging and committing (`zip -r qt-demos-cleancode.zip qt-demos-cleancode` + `git commit`, with no AI attribution)

### Outputs (downstream deliverables)
- The published AtomGit ohos-qt organization repository (external developers can clone and build it themselves)
- The CleanCode archive zip (the demo source committed)
- The end of the pipeline

### Caveats and pitfalls
Source: `fork-qt-app-to-ohos-qt-org` / `demo-archive-cleancode-upload`

- **The iron rule**: commit only source and configuration, never build artifacts/caches/binaries/keys (~1 MB of source vs. ~430-500 MB of artifacts)
- **Lesson 1**: upstream's `*.ts` (Qt translation files) catches DevEco's hvigorfile.ts by mistake → add the `!HarmonyOS/**/*.ts` negation
- **Lessons 2/22**: leaked signing keys — the root build-profile.json5 may contain a real keyPassword/storePassword → overwrite it with the unsigned template; the secret grep must check both slash forms, `C:\\Users|C:/Users`
- **Lesson 4**: `git push` defaults to a GCM GUI popup and hangs in a non-interactive environment → always use `git -c credential.helper= push 'https://oauth2:<token>@...'`
- **Lesson 10**: `bash setup.sh` must use `cygpath -m` to convert to the mixed C:/ path form
- **Lesson 16**: the LFS pointer file trap — overwrite the pointer with the real file + amend + a pre-commit `git grep -l 'version https://git-lfs'`
- **CleanCode**: a local clangd will report `QApplication file not found` / `Q_OBJECT unknown` — that's environment noise (no Qt header paths, moc hasn't run), not a code defect; the archive isn't required to compile
- **Line-count calibration** must not pad with blank lines or filler comments; if you're under target, only add real helpers or named-constant blocks

### ⚠️ Not covered by the KB
- **The upload stage is very thinly covered** (a gap): only 2 workflows (publishing an open-source fork / archiving demo source), with nothing for distributing the final HAP (AppGallery/app stores) or for publishing a Qt6 SDK/add-on module for the team to reuse; after completion's feature verification passes there's no customer application distribution workflow to hand off to. **The minimal viable suggestion**: create `procedural/hap-distribute-appgallery.md` (the AppGallery submission process) and `procedural/qt6-addon-publish.md` (the process for installing an add-on module into the team's shared kit); and add a "delivery handoff" section after completion §4's closure confirmation routing into this stage (this page already adds the routing note before stage 8).

---

## A standalone section: building third-party libraries

> First referenced in stage 1 §1.5 (getting a bottle) / stage 3 §3.8 (the platform limitation checks) / stage 4 §4.6 (CMake cross-compilation integration) / §4.7 (Qt6 add-ons).

Source: `qt-harmonyos-third-party-libs` / `fetch-ohos-third-party-lib`

The platform NDK, ABI, sysroot, build and HAP native deployment contracts are defined by [[ohos-common-kb/semantic/ohos-native-third-party-libraries|common: the OHOS native third-party library contract]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/ohos-native-third-party-libraries.md)). This pipeline only orchestrates the Qt-side consumption:

1. Obtain the headers, static or shared libraries and the complete dependency closure that have passed common's artifact checks;
2. Consume them in the Qt target through `find_package`/imported targets, without letting host metadata into the cross build;
3. Check that the Qt runtime, the QPA/plugins and the third-party libraries all end up in the final HAP together;
4. Verify the actual result against [[qt-harmonyos-third-party-libs]]'s Qt compatibility list and an application regression;
5. Route platform limitation failures to common, and Qt symptoms and workarounds to [[qt-harmonyos-platform-limits]].

Getting a prebuilt bottle is still covered in stage 1 §1.5; this section doesn't maintain a second copy of the CMake/autotools platform cross-compilation commands.

### Qt6 IoT add-ons (e.g. qtmqtt)
The source-only add-on modules aren't in the prebuilt installer, but the prebuilt OHOS kit ships `Qt6BuildInternalsConfig.cmake`, which supports building add-ons. For the process see stage 4 §4.7. The open-source QtMqtt is GPLv3 (not LGPL), so a closed-source commercial release needs a Qt commercial license or a switch to Paho.mqtt-c/mosquitto (EPL/EDL, non-viral).

---

## A standalone section: demo generation

> For when this applies see stage 3 (the migration feasibility pre-flight) / stage 7 (generating test cases); this is not the bug reproduction scenario (for that use `framework-issue-analysis`).

Source: `demo-generation`

### When it applies
When the user directly asks to "write a demo" / "generate a test project" and similar standalone demo scenarios (not the bug reproduction scenario — for that use `framework-issue-analysis`).

### The six-step loop
1. **Understand the requirement**: clarify the demo's goal (feature verification / a rendering effect / demonstrating API usage / performance testing), the core features, the target platform (desktop/OHOS), the Qt version, and any special requirements
2. **Technical design**: choose the Qt modules, choose the build system (desktop qmake / HarmonyOS CMake / one cross-platform CMake), the project structure, the technical approach
3. **Create the project**: a HarmonyOS project must be created from the glue template bundled with the Qt source (`<QT_SRC>/qtbase/src/harmonyos/templates`). **⚠️ A trap**: the source tree template's OhosExportModules.ts is the stale minimal version and using it as is always crashes (it lacks every `@ohos.*` eager import, so libqohos's bare eval of "@ohos.deviceInfo" at startup is rejected by ArkTS → SIGABRT). The mandatory check: `strings <SDK>/plugins/platforms/libqohos.so | grep -E "^modules$|^modulesFactories$"` to determine the API (modules=objects / modulesFactories=factories), then replace it with the canonical complete version from qView-ohos
4. **Write the code**: prefer a single file, use Qt 5.12-compatible APIs, comment it, give the file a header comment covering its purpose/structure diagram/compatible versions/usage, and produce meaningful visual output
5. **Verify the build**: on the desktop `qmake && mingw32-make.exe -j8`; for HarmonyOS build and deploy through DevEco or the hdc command line. On a build failure check `problems/_lookup.md`
6. **Documentation and knowledge capture**: a README is optional but recommended; `git commit` (message format `<type>: <short description>`); capture new findings in `episodic/` or `problems/`

---

## A standalone section: the Qt5→Qt6 migration differences

> First referenced in stage 2 §2.2 (the three-strategy decision) / stage 3 §3.5-3.8 (API mapping/windows/lifecycle/platform limitations) / stage 4 §4.1-4.2 (the strategy B superbuild + patch).

Source: `qt-harmonyos-qt6-status` / `qt515-vs-qt512-api-diff`

### The key Qt5→Qt6 OHOS differences
- **CloseRootCause made private**: in Qt6 it's a private internal API in a `_p.h` header, so Qt5's public `QtOhosExtras::getCloseEventRootCause()` can't be migrated directly — you have to wait for a public API or a Qt6 version of QtOhosExtras
- **The breaking AppLocalDataLocation change**: Qt5 maps it to filesDir, Qt6 to preferencesDir, so watch out for the path difference when migrating
- **CMake changed throughout**: `find_package(Qt6 ...)`, `qt_add_executable` (not `add_executable`; it produces a MODULE .so + main GLOBAL DEFAULT + the deployment-settings.json + the bundled ets glue automatically), `qt_add_resources()`, `qt_add_qml_modules()` (the version prefix is gone)
- **Versionless QML imports**: `import QtQuick`, not `import QtQuick 2.15`
- **QRegExp removed**: use QRegularExpression or a Qt5Compat forwarding header (when many files use QRegExp's own API, write a forwarding header defining QRegExp as a QRegularExpression subclass and put it ahead of Qt5Compat's `-isystem` via `-I`)
- **The minimum C++ standard is C++17** (Qt5's was C++14)
- **main's dynamic visibility**: when the target uses `CXX_VISIBILITY_PRESET hidden`, main is a local symbol and `dlsym(main)` fails, so add `__attribute__((visibility("default")))` (strategy B); strategy B' with `qt_add_executable` makes main GLOBAL DEFAULT automatically and needs nothing hand-written
- **Absolute DT_NEEDED paths** (strategy B only): Qt6's .so files have no SONAME and `-developer-build` imported targets are linked by absolute path → `dlopen` fails on the device, so rewrite them to bare names with `patch_needed.py`
- **The DBus hard wall**: the prebuilt SDK has no Qt6DBus, so an unconditional DBus REQUIREMENT can't be built and can't be stubbed
- **The C++23 ceiling**: OHOS's native clang 15.0.4 doesn't implement P0847R7 (which needs Clang 18.0+) and libc++ lacks the ranges adaptors, so you have to downgrade at the source level (deducing-this → CRTP, ranges → hand-written loops)
- **8 mechanical fixes**: setCodec→setEncoding, DataLocation→AppDataLocation, QPrinter paper→QPageSize and so on

### The Qt 5.15 vs. 5.12 OHOS SDK API differences (the QtWidgets module)
Source: `qt515-vs-qt512-api-diff`

- **Downgrading 5.15→5.12 🔴 high risk**: the OHOS-specific QSystemTrayIcon/QFileDialog APIs, QTextBrowser::doSetSource and the QCalendar methods simply don't exist, so the build fails
- **Upgrading 5.12→5.15 🟡 low risk**: every 5.12 API is retained (possibly deprecated but still compiling), around 50+ produce deprecation warnings, and QDirModel should be migrated to QFileSystemModel
- The verification baseline: Qt 5.15.16 (962aa625, 2026-04-19) vs. Qt 5.12.12 (613336de, 2026-05-25)

---

## The iron rules quick reference (scan this before any task)

> This quick reference is a Qt navigation snapshot within the end-to-end pipeline, not an independent authority. The rule text and conflict resolution are governed by [[qt-harmonyos-golden-rules]]; the HarmonyOS platform facts by common.

Source: `qt-harmonyos-golden-rules` (35 rules, based on Qt 5.12/5.15; for the major Qt6 changes see `qt-harmonyos-qt6-status`)

The severity key: 🔴 blocks the build/deployment | 🟠 fails silently | 🟡 misbehaves | 🟢 informational/best practice

### Build and deployment B1-B12
- B1(🔴) CMake must set `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` before `find_package` (the default ONLY prevents it from finding Qt/third-party libraries)
- B2(🔴) You must link `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin`, or you get `dlopen failed: libqohos.so not found`
- B3(🔴) `APP_LIBRARY_NAME` (in QtAppConstants.ets) must exactly match the built library's name (including the lib prefix and the .so suffix)
- B4(🔴) Never set `compileSdkVersion`/`targetSdkVersion` (Schema validate failed)
- B5(🟡) `runtimeOS` must be `"HarmonyOS"`, not `"OpenHarmony"`
- B6(🟡) QtOhosExtras only supports qmake (`CONFIG -= create_cmake`), with no CMake find_package; the Qt6 module no longer exists standalone
- B7(🟡) `libqohosstyle.so` must be copied manually into `libs/${ABI_DIR}/styles/`
- B8(🟡) In scenario two, build-profile.json5's path must be an absolute path
- B9(🔴) A qmake unix branch must have `:!ohos` (`unix:!android:!macx:!ohos`)
- B10(🔴) QML applications must enable `CMAKE_AUTORCC ON`, or qml.qrc isn't compiled and you get a black screen at runtime
- B11(🔴) The bundleName must be a stable dotted identifier the target SDK's schema accepts, and must be consistent across the generated project, the signing profile, and the install/launch commands
- B12(🟠) `libqsqlite.so` must be copied manually into `libs/${ABI_DIR}/sqldrivers/` (on OHOS the filename is libqsqlite.so, not the desktop's libqsqlsqlite.so); miss it and `addDatabase("QSQLITE")` gives a null driver, `open()` returns false, and `lastError="Driver not loaded"`

### Window management W1-W6
- W1(🟡) `tagWindowOrWidgetAsSubWindowOf()` must be called before `show()` and `winId()`
- W2(🟢) The first QWindow/QWidget binds to the system main window automatically, with no tagging needed
- W3(🟡) A parentless QDialog is treated as a new main window, so it must be tagged or given a parent
- W4(🟡) The first window can't go fullscreen at startup — `show()` first, then `showFullScreen()`
- W5(🟡) The main window's `hide()` degrades to minimizing (when there's no system tray)
- W6(🟠) Don't rely on the WINDOW_HIDDEN/WINDOW_SHOWN events as the only trigger for state synchronization (they don't fire in the file acceleration / preloading scenarios)

### API names and enum paths A1-A6
- A1(🟠) The close event enumerator must use its full path, `QtOhosExtras::CloseEventRootCause::AbilityClose` (the short path doesn't compile for an enum class); in Qt6 the enum was renamed to CloseRootCause and made private
- A2(🟠) The theme enumerator must use its full path, `QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting`
- A3(🟠) The UI signals are on QOhosUiAbilityContext (not QOhosAbilityContext)
- A4(🟢) The factory methods are on QOhosAbilityContext: `getDefaultInstance()`/`getInstanceForMainWindow()`
- A5(🟠) The qtohosextras headers are lowercase only, so `#include` must be lowercase: `<QtOhosExtras/qohosappcontext.h>` (no CamelCase forwarding headers are installed)
- A6(🟠) `getCloseEventRootCause()` is a free function, `QtOhosExtras::getCloseEventRootCause(event)` (not a member); in Qt6 it's private

### Platform limitations P1-P5
- The platform limitation content isn't duplicated in this quick reference; read [[ohos-common-kb/semantic/harmonyos-platform-limits|common's platform limitations]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md)) first.
- Within this pipeline, P1-P5 only mean: check the `QFile`/`QStandardPaths`, `QPluginLoader`, Qt worker cancellation and `QTimeZone` adapters, and record the results in the Qt application regression.

### Lifecycle L1-L4
- L1(🟠) closeEvent must check the CloseEventRootCause; level 2 (AbilityClose) must never show UI
- L2(🟢) argv[0] is the library path (the .so), not an executable path
- L3(🟢) Qt for HarmonyOS uses the Stage model; the FA model has been deprecated since API 9
- L4(🟢) Child-process selection depends on the scenario, with no one-size-fits-all answer (headless QProcess / a Qt UI with startAppProcess / a non-Qt UI with startAbility / headless but needing hosting with startNoUiChildProcess)

### Cross-platform guards G1-G2
- G1(🟢) `Q_OS_OHOS` implies `Q_OS_LINUX`, so `#ifdef Q_OS_LINUX` also matches on HarmonyOS
- G2(🟢) Drag-and-drop event data can only be read in dropEvent

---

## The supply chain view

```
Upstream contacts               This pipeline                    Downstream deliverables
─────────────────────────────────────────────────────────────────────────────────
The Qt Project Gerrit       ┐
(codereview.qt-project.org) │ Stage 1 Obtain              → The Qt source tree / the prebuilt kits
Huawei's official IDE/SDK   │   Stage 2 Environment       → The project skeleton + the kit configuration
The Harmonybrew repository  ┘   Stage 3 Migration         → The adapted source
                              │ Stage 4 Build             → The unsigned HAP + your .so + the static pre-check report
Commercial Qt customers       │   Stage 5 Signing         → The signed HAP
(HarmonyOS migration requests)│   Stage 6 Deploy & run    → The application running on a device + the logs
Internal marketing demos      │   Stage 7 Test            → The test report + the captured problems
Self-driven (new scenarios)   │   Stage 8 Upload/publish  → The AtomGit repository / the CleanCode zip
                              │   The standalone sections: third-party libraries / demos / Qt5→6
                              ┘
```

**The end-to-end delivery chain**:
- Stage 1 → stage 4: delivers the Qt source tree/prebuilt SDK + the third-party .so files + the DevEco SDK, for compile to configure CMAKE_PREFIX_PATH/CMAKE_TOOLCHAIN_FILE/QT_CHAINLOAD_TOOLCHAIN_FILE
- Stage 4 → stage 5: delivers the unsigned HAP + your .so + harmony-deployment-settings.json + the static pre-check report, for signing (the static pre-check report doubles as stage 6's pre-install gate)
- Stage 5 → stage 6: delivers the signed HAP, with the bundleName bound to the .p7b profile verified and products[] referencing the signingConfig, for hdc install
- Stage 6 → stage 7: delivers the application running on a device + hilog + screenshots + the static pre-check report, for feature verification and crash analysis
- Stage 7 → stage 8: delivers the test report + the captured problems + the regression conclusions, for publishing or archiving
- Stage 8 → the end: delivers the published AtomGit ohos-qt organization repository or the CleanCode archive zip

---

## The list of source workflows

The source files this page stitches together (KB-relative paths):

**Procedural (13)**:
- `procedural/qt-app-harmonyos-migration.md` — Migrating a Qt application to HarmonyOS (the main workflow)
- `procedural/qt6-ohos-windows-build.md` — Building Qt 6.12 for OHOS on Windows (the superbuild)
- `procedural/qt6-qtcreator-harmonyos-setup.md` — Configuring the Qt 6.12 HarmonyOS development environment in Qt Creator
- `procedural/qt6-ohos-windows-app-dev-guide.md` — The Windows Qt 6.12 prebuilt end-to-end CLI development guide
- `procedural/qt6-ohos-qtmqtt-build.md` — Cross-compiling the Qt 6.12 qtmqtt add-on for HarmonyOS
- `procedural/qt6-cef-ohos-integration-guide.md` — Qt6 + CEF HarmonyOS integration (a 12-step migration)
- `procedural/fetch-ohos-third-party-lib.md` — Getting prebuilt arm64-OpenHarmony third-party libraries from Harmonybrew
- `procedural/qt-ohos-concrete-build-recipe.md` — The concrete Qt→OHOS build recipe (playbooks A/B)
- `procedural/qt-ohos-run-test.md` — The HarmonyOS run-test workflow (a seven-phase loop)
- `procedural/qt-app-harmonyos-completion.md` — Application polish (the feature-level test case loop)
- `procedural/demo-generation.md` — The demo generation workflow (a six-step loop)
- `procedural/demo-archive-cleancode-upload.md` — The demo archiving workflow (an eight-step loop)
- `procedural/fork-qt-app-to-ohos-qt-org.md` — Forking a HarmonyOS-ported Qt application to the AtomGit ohos-qt organization

**Semantic (23)**:
- `semantic/qt-harmonyos-overview.md` — A Qt for HarmonyOS overview
- `semantic/qt-harmonyos-build.md` — The Qt for HarmonyOS build guide
- `semantic/qt-harmonyos-build-run-workflow.md` — The full Qt HarmonyOS build-and-run flow
- `semantic/qt-harmonyos-project-structure.md` — The Qt HarmonyOS project structure in detail
- `semantic/qt-harmonyos-qt6-status.md` — The Qt6 HarmonyOS porting status
- `semantic/qt-harmonyos-modules.md` — A quick reference for the Qt HarmonyOS module porting status
- `semantic/qt-harmonyos-platform-limits.md` — The Qt HarmonyOS platform limitations
- `semantic/qt-harmonyos-api-mapping.md` — The API migration mapping table
- `semantic/qt-harmonyos-code-patterns.md` — A quick reference of porting code patterns
- `semantic/qt-harmonyos-porting-workflow.md` — The Qt HarmonyOS porting 8-step decision tree workflow
- `semantic/qt-harmonyos-third-party-libs.md` — The guide to porting third-party libraries
- `semantic/qt-ohos-extras.md` — The QtOhosExtras module (145+ APIs)
- `semantic/qt-ohos-extras-examples.md` — A recipe book for the official QtOhosExtras examples
- `semantic/qt-harmonyos-window-model.md` — The Qt HarmonyOS window model in detail
- `semantic/qt-harmonyos-lifecycle.md` — The Qt HarmonyOS application lifecycle in detail
- `semantic/qt-harmonyos-api.md` — Qt HarmonyOS API compatibility
- `semantic/qt-ohos-project-analyzer-workflow.md` — The Qt-OHOS project analyzer workflow
- `semantic/qt-harmonyos-golden-rules.md` — The Qt HarmonyOS iron rules quick reference (35 rules)
- `semantic/qt515-vs-qt512-api-diff.md` — The Qt 5.15 vs. 5.12 OHOS SDK API differences
- `semantic/qt-harmonyos-accessibility.md` — The Qt for HarmonyOS accessibility bridge and enabling it via a Want parameter
- `semantic/qt-harmonyos-system-tray.md` — The Qt HarmonyOS system tray
- `semantic/qt-ohos-js-thread-gateway.md` — The Qt↔JS thread bridge
- `semantic/qt-huawei-cleancode-rules.md` — Huawei's Qt CleanCode rules (18 of them)
- [[ohos-common-kb/procedural/deveco-cli-usage-rules|DevEco CLI usage rules]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/deveco-cli-usage-rules.md))
- [[ohos-common-kb/semantic/harmonyos-development-fundamentals|HarmonyOS development fundamentals]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-development-fundamentals.md))

---

## ⚠️ A summary of what the KB doesn't cover

| The gap | Where | Status / the minimal viable suggestion |
|---------|-------|----------------------------------------|
| Asymmetric command density on the download side (B' is descriptive with no CLI) | Stage 1 §1.3 | ⚠️ Still open; add the `maintenance-tool.exe --install` CLI or archive a screenshot of the checked component list (the current list is the stand-in) |
| No unified environment preparation checklist page | Stage 2 | ⚠️ Still open; take §2.1 + §2.4 here as the baseline and create `procedural/env-checklist.md` collecting the Qt5/Qt6/strategy B/B' environment checks |
| DEVECO_SDK_HOME is inconsistent across the three shell forms in the sources | Stage 2 §2.1 | Flagged ⚠️ with a recommendation to prefer `<DEVECO>/sdk` (matching bash/PS), using whether `hvigorw --sync` resolves the SDK as the test |
| The Qt6 B' template source was missing | Stage 2 §2.4 | Filled in: the B' template is at `<QT6_OHOS_KIT>/src/harmonyos/templates` and harmonydeployqt6 copies it automatically, so no manual cp is needed |
| No single named workflow page for migration | Stage 3 | This stage is the stitched-together unified migration reference |
| Nested stage numbering conflicted in §3.1 | Stage 3 §3.1 | Fixed: the internal "stage zero/one" naming was dropped in favor of consistent §3.x numbering, and the ②③⑦ ls/grep scanning commands were added |
| §3.9's qmake part wasn't marked Qt5-only | Stage 3 §3.9 | Fixed: it now says "qmake (Qt5 only)" |
| No unified build recipe index page for compile | Stage 4 | Use §4.1-4.8 as the index table, looking things up along the three axes (Qt5/Qt6) × (playbook A/B) × (strategy B/B') |
| §4.1 hardcoded personal absolute paths + left EGL as `...` | Stage 4 §4.1 | Fixed: placeholders throughout + EGL filled in following the same sysroot pattern as GLESv2 |
| §4.6's narrative order was disjointed | Stage 4 | Fixed: the patch section was moved to directly follow §4.1's superbuild as §4.2, with the old §4.2-4.5 renumbered to §4.3-4.6 |
| The static pre-check report's ownership was contradictory and the ordering inverted | Stages 4→6 | Fixed: stage 4's outputs now list the static pre-check report explicitly plus a timing clarification callout; stage 6's prerequisites now reference stage 4's outputs, making clear that run-test §2 precedes §3's install |
| §6.4 overlaps with §7.1 (run-test §4) | Stages 6/7 | The boundary is now flagged: stage 6 = the first deployment smoke test, stage 7 §7.1 = the gated formal verification loop |
| The risk of mixing the two Qt6 CMake modes | Stage 4 | Strategy B (§4.1-4.2) uses `add_library` + hand-written visibility, strategy B' (§4.3-4.4) uses `qt_add_executable`, and mixing across strategies is forbidden |
| No unified signing workflow page | Stage 5 | This stage merges the 4 methods into one reference; method one's menu navigation + method three's sign sub-arguments + generating the encrypted string are still ⚠️ truncated at the source |
| Obtaining the signing material wasn't stated as a prerequisite | Stage 5 | Filled in: generating the material depends on running DevEco Auto Signing (method one) once |
| deploy had no named stage | Stage 6 | This stage merges deploy + run |
| No unified Qt6 run+test end-to-end workflow | Stages 6/7 | ⚠️ Still open; create `procedural/qt6-ohos-run-test.md` mirroring `qt-ohos-run-test`'s seven phases with the Qt6 HAP generation chain |
| run-test §5 and completion §3.5 overlap in the test stage | Stage 7 | The boundary is now explicit: run-test §5 = process-level crashes / completion §3.5 = feature-level failures |
| upload is covered by only 2 workflows and the general test→upload path is broken | Stage 8 | ⚠️ Still open; create `procedural/hap-distribute-appgallery.md` + `procedural/qt6-addon-publish.md`; add a "delivery handoff" route after completion §4's closure (this page already adds the note before stage 8) |
