---
id: semantic-qt-harmonyos-qt6-status
type: semantic
domain: tech
tags: [qt, qt6, harmonyos, ohos, status, cmake]
created: 2026-06-03
updated: 2026-09-09
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-build, semantic-qt-harmonyos-modules, semantic-qt-harmonyos-platform-limits, semantic-qt-ohos-project-analyzer-workflow]
summary: >
  Qt 6 HarmonyOS porting status: qtbase dev has merged HarmonyOS support (Gerrit 733351),
  the minimum SDK is API 20 (HarmonyOS 6.0.0), and the build system is CMake.
  **The Qt 6.12.0 Windows superbuild is verified (2026-07-13)**: a MinGW host + an OHOS Clang target,
  with the gallery demo running on a physical device ("Widget Gallery Qt 6.12.0").
  **⚠️ A major correction on 2026-07-25: the Qt 6.12 prebuilt-installer SDK is a complete distribution** (libQt6Quick.so/Multimedia/
  Charts/3D/OpenGL/DataVisualization/Bluetooth/Location/Sensors/SerialBus/UiTools/Core5Compat are all present,
  as is the QtQuick qml runtime); only WebEngine/DBus/Wayland/Pdf/Script are missing. This page's older notes — "nothing beyond qtbase has started",
  "Quick .so absent", "Multimedia missing" — are stale records from the **source superbuild (strategy B)** era and do not hold for the **prebuilt build (strategy B')**.
  Corroborated by the second batch of 10 applications (extending into modules such as opengl/qml/uitools) all building successfully.
  **⚠️ A beta3 re-check on 2026-08-25**: Qt6HarmonyExtras is a standalone module again (libQt6HarmonyExtras.so + cmake, with public headers that are only exports/version stubs and all 16 functional headers private `_p.h`) — overturning the beta2 conclusion that it "doesn't exist as a standalone module"; file permission granting = QtCore's public `QPermissions` API (which has no file permission type — only location/calendar/contacts/bluetooth/camera/microphone) + the private `QtHarmonyExtras::FileShare::persistPermission` API (corresponding to HarmonyOS's `@ohos.fileshare`).
  **⚠️ Measured verification on 2026-09-09 (kb-verify-qt.py, local beta3 install)**: libQt6Multimedia/Quick/OpenGL/RemoteObjects/QuickTimeline/Help/UiTools/Core5Compat are indeed present; but **libQt6Charts.so and libQt6DataVisualization.so are missing** — contradicting the 2026-07-25 claim above that "Charts/DataVisualization are all present". The difference may come from the components selected in the installer (this machine has a partial install); before depending on Charts/DataViz, verify with `ls <QT6_OHOS_SDK>/lib | grep -i chart`. The machine-readable matrix is in knowledge/adaptation/modules.yaml (charts/datavisualization marked restricted).
  Plus the key Qt5→Qt6 differences (QStandardPaths, the CMake API, QML, the QPA API).
---

# Qt 6 for HarmonyOS status

> **In one line**: Qt 6 HarmonyOS support has landed on the qtbase dev trunk and is currently at an early stage (qtbase only); the remaining modules haven't been ported.

## Current status

| Item | Content |
|------|---------|
| **Merge status** | ✅ Gerrit change [733351](https://codereview.qt-project.org/c/qt/qtbase/+/733351) has been merged into qtbase dev |
| **Minimum SDK** | HarmonyOS SDK **API 20** (HarmonyOS 6.0.0) |
| **Target architecture** | arm64-v8a |
| **Completed modules (the source superbuild, strategy B)** | Only **qtbase** + 5 submodules (qtsvg/qtimageformats/qtshadertools/qtlanguageserver/qtdeclarative). **The non-qtbase modules (Multimedia/3D/Charts etc.) have no HarmonyOS support in their sources.** |
| **Completed modules (the prebuilt installer, strategy B')** | ⚠️ **A complete Qt 6.12 distribution** (ground-truth re-check 2026-07-25): libQt6Quick/Multimedia/Charts/3DCore/3DRender/OpenGL/OpenGLWidgets/DataVisualization/Bluetooth/Location/Positioning/Sensors/SerialBus/UiTools/Core5Compat/WebSockets/SerialPort/PrintSupport/Svg/SvgWidgets/Help/Designer/NetworkAuth/TextToSpeech/HttpServer/ShaderTools/Qml/QmlModels/QuickWidgets/QuickControls2/Quick3D are all present, as is the QtQuick qml runtime (Controls/Dialogs/Layouts). **Only WebEngine/DBus/Wayland/Pdf/Script are missing.** |
| **Build system** | **CMake** (Qt 6 uses CMake throughout; qmake/configure are gone) |

> ⚠️ **Important**: the "completed modules" rows above are split by **build method**. The blocking conclusions in apps.csv and the older KB — "nothing beyond qtbase has started", "Quick .so absent", "Multimedia missing" — all refer to the **source superbuild (strategy B)** and **do not hold for the prebuilt installer (strategy B')**, which is a complete distribution. The second batch of 10 applications (extending into modules such as opengl/qml/uitools) all built successfully against the prebuilt SDK (see the batch 2 build retrospective). When a Qt6 HarmonyOS porting request comes in, **prefer the prebuilt SDK (strategy B')** and don't declare it blocked based on the old "missing modules" conclusions.

## Getting the source

```bash
# The Qt 6 trunk (the dev branch)
# Local path: <LOCAL_PATH>
git clone https://code.qt.io/qt/qtbase.git
cd qtbase
# the dev branch already contains HarmonyOS support
```

## How it's built

Building Qt 6 differs fundamentally from Qt 5:

| Aspect | Qt 5 for OHOS | Qt 6 for OHOS |
|--------|---------------|---------------|
| Build system | `configure` + `make` | **CMake** |
| Build command | `../configure -xplatform ohos-clang ...` | `cmake -GNinja -DQT_HOST_PATH=... -DCMAKE_TOOLCHAIN_FILE=...` |
| Module management | qmake `.pro` files | CMake `qt_add_executable` / `qt_add_qml_modules` |
| QML imports | `import QtQuick 2.x` | `import QtQuick` (no version number) |
| C++ standard | C++14 | **C++17** (the minimum) |

For detailed build steps see [Building Qt6 for HarmonyOS](https://wiki.qt.io/Building_Qt6_for_HarmonyOS)

## Key Qt 5 vs. Qt 6 differences (as they relate to HarmonyOS)

### New QStandardPaths enumerators

Qt 6 added several `QStandardPaths::StandardLocation` values; the mappings below are verified against the Qt6 qtbase source (`qstandardpaths_ohos.cpp`):

| The Qt 6 enumerator | The OHOS mapping | Qt 5 status |
|---------------------|------------------|-------------|
| `PublicShareLocation` | ❌ **NOT SUPPORTED** (returns an empty string) | ❌ Doesn't exist |
| `TemplatesLocation` | ❌ **NOT SUPPORTED** (returns an empty string) | ❌ Doesn't exist |
| `StateLocation` | ✅ Maps to `filesDir` | ❌ Doesn't exist |
| `GenericStateLocation` | ✅ Maps to `filesDir` | ❌ Doesn't exist |

> ⚠️ **Behavior change**: `AppLocalDataLocation` maps to `filesDir` on Qt 5 for OHOS but to **`preferencesDir`** on Qt 6. Watch out for the path difference when migrating.

### CMake API changes

| Qt 5 | Qt 6 | Notes |
|------|------|-------|
| `find_package(Qt5 ...)` | `find_package(Qt6 ...)` | The package name changed |
| `qt5_add_resources()` | `qt_add_resources()` | The version prefix is gone |
| — | `qt_add_qml_modules()` | Qt 6's QML module declaration |
| `add_executable()` | `qt_add_executable()` | Recommended in Qt 6 |

### QML changes

| Qt 5 | Qt 6 | Notes |
|------|------|-------|
| `import QtQuick 2.15` | `import QtQuick` | Versionless imports |
| `import QtQuick.Controls 2.15` | `import QtQuick.Controls` | Same |
| The `QtQuick.Controls` module is missing from the OHOS SDK | — | ⚠️ **Source superbuild (strategy B)**: it isn't in qtbase — it's a separate module (qtdeclarative/qtquickcontrols2) and needs porting on its own. **Prebuilt installer (strategy B')**: libQt6QuickControls2.so + the qml/QtQuick/Controls runtime are **all present** (ground-truth re-check 2026-07-25), so no separate porting is needed. Corroborated by CopyQ (qml) building successfully against the prebuilt SDK (the batch 2 build retrospective). |

### Other changes

| Change | Impact |
|--------|--------|
| `QFuture::then()` / `QPromise` | New concurrency APIs in Qt 6; on Qt 5 use `QtConcurrent::run()` instead |
| The `core5compat` module | Qt 6's Qt 5 compatibility layer, through which some APIs can be transitioned |
| Build artifact paths | Qt 6's CMake output paths may differ from Qt 5's, which affects `APP_LIBRARY_NAME` in `QtAppConstants.ets` |

### QPA plugin API changes (verified against the source)

Qt 6 has **inlined most of the old QtOhosExtras module's functionality into the QPA plugin** (`src/plugins/platforms/ohos/`, 196 files). The key API differences:

> ⚠️ **Corrected by the beta3 re-check on 2026-08-25**: as of beta3 QtHarmonyExtras **is a standalone module again** (`lib/libQt6HarmonyExtras.so` + `lib/cmake/Qt6HarmonyExtras/` + the `Qt6HarmonyExtrasPrivate/` cmake target), but its **public headers are only the two stubs `qtharmonyextrasexports.h`/`qtharmonyextrasversion.h`**, while all 16 functional headers (abilitycontext/appcontext/bundlemanager/fileshare/fileutils/pasteboard/sharekit/want/windowutils etc.) are **private `_p.h`**. So the module is standalone again, but the public API surface is still empty. The API differences in the table below were recorded in the dev-source era; after the beta3 modularization the functionality still lives in private headers and the signatures haven't been made public. See the "Qt6 beta3 file permission granting interfaces" section below and known issue #2.

#### Close event APIs — a major change

| Aspect | Qt 5 (QtOhosExtras) | Qt 6 (internal to the QPA) |
|--------|---------------------|----------------------------|
| Enum name | `CloseEventRootCause` | `CloseRootCause` (**private** `_p.h`) |
| `InternalClose` | ✅ Exists | ❌ Removed (replaced by `NotSpecified`) |
| `AbilityClose` | ✅ Exists | ⚠️ Renamed to `OnPrepareToTerminate` |
| `WindowStageClose` | ✅ Exists | ✅ Exists (same name) |
| `SubWindowClose` | ❌ Doesn't exist | ✅ **New** |
| The getter | `getCloseEventRootCause(QCloseEvent*)`, public API | `getCloseRootCauseForEventOrDefault(QEvent*)`, **private API** |

> ⚠️ **The key difference**: Qt 6's close event API is currently a **private internal API** (in `_p.h` headers) with no public interface. That means Qt 5 code using `QtOhosExtras::getCloseEventRootCause()` **can't be migrated directly** to Qt 6 — you have to wait for a public API or for a Qt 6 version of QtOhosExtras to provide one.

#### Window tagging APIs — unchanged

| API | Qt 5 | Qt 6 |
|-----|------|------|
| `tagWindowOrWidgetAsSubWindowOf` | `QOhosFunctions` (public) | `QPlatformNativeInterface` (internal) ✅ |
| `tagWindowOrWidgetAsMainWindow` | `QOhosFunctions` (public) | `QPlatformNativeInterface` (internal) ✅ |
| `tagWindowOrWidgetAsFloatWindow` | `QOhosFunctions` (public) | `QOhosQpaFunctions` (internal) ✅ |

> The signatures are the same, but in Qt 6 you reach them through `QPlatformNativeInterface` rather than the public `QOhosFunctions` class. A public API depends on the Qt 6 version of QtOhosExtras.

#### ShareKit APIs — interface changes

| Aspect | Qt 5 | Qt 6 |
|--------|------|------|
| Namespace | `QtOhosExtras::ShareKit` | `QOhosShareKit` (internal) |
| The share function | `shareDataWithShareKit()` | `shareDataUsingShareKit()` |
| The record type | `QOhosSharedRecord` | `ShareKit::SharedRecord` |

## Qt6 beta3 file permission granting interfaces (re-checked 2026-08-25)

> HarmonyOS file access permissions come in three layers; here's what Qt6 beta3 covers (based on ground truth from the local `${QT6_INSTALLER_ROOT}/6.12.0/harmonyos_arm64_v8a` headers).

### (1) The public cross-platform `QPermissions` API (QtCore, public headers)

- Header: `include/QtCore/qpermissions.h` (public, not `_p`); the OHOS backend is `include/QtCore/6.12.0/QtCore/private/qohospermissionshelper_p.h` (private)
- Entry points: `QCoreApplication::checkPermission(const QPermission&)` → `Qt::PermissionStatus` (a synchronous query); `QCoreApplication::requestPermission(const QPermission&, context, functor)` (an asynchronous request that shows the authorization dialog — see `qcoreapplication.h:131-165`)
- The status enum: `Qt::PermissionStatus{Undetermined, Granted, Denied}` (`qnamespace.h:1766`)
- There are **only 6** built-in permission types: `QLocationPermission` / `QCalendarPermission` / `QContactsPermission` / `QBluetoothPermission` / `QCameraPermission` / `QMicrophonePermission`
- ⚠️ **There is no `QFilePermission` / `QStoragePermission` / `QMediaPermission` type** — file/storage/media access is **not** part of Qt 6's public permissions API

### (2) HarmonyOS persistent file authorization (QtHarmonyExtras, private `_p.h`)

- Header: `include/QtHarmonyExtras/6.12.0/QtHarmonyExtras/private/qohosfileshare_p.h`
- Namespace: `QtHarmonyExtras::FileShare`
- APIs: `persistPermission(QList<PathPolicy>)` / `revokePermission` / `activatePermission` / `deactivatePermission` / `checkPersistent`
- `PathPolicy{QString path; OperationModes(Read|Write)}` — persists read/write authorization for a given file or directory path
- Corresponds to HarmonyOS's native `@ohos.fileshare` `grantPersistPermission` and requires `ohos.permission.FILE_ACCESS_PERSIST`
- ⚠️ **A private API** with no ABI guarantee across versions; use with care in production

### (3) Temporary file authorization (not wrapped; use the HarmonyOS native APIs)

- Qt doesn't wrap the file picker; use HarmonyOS's `@ohos.file.picker` (`DocumentViewPicker` / `PhotoViewPicker`). The picker returns a URI with temporary read/write permission that expires when the application exits or restarts
- To keep it across restarts → use (2) `FileShare::persistPermission`, or native `@ohos.fileshare`

> **The conclusion**: Qt6 beta3 offers no public wrapper for "granting file permissions". Temporary authorization goes through the HarmonyOS picker (no Qt wrapper), and persistent authorization goes through `QtHarmonyExtras::FileShare::persistPermission` (a private `_p.h`). The public `QPermissions` only covers the 6 categories location/calendar/contacts/bluetooth/camera/microphone, and files aren't among them — so when you get a "how does a Qt6 application request file read/write permission" question, don't point at Qt's permissions API; point at HarmonyOS's native `abilityAccessCtrl.requestPermissionsFromUser` + `@ohos.file.picker` + `@ohos.fileshare`.

## Module porting status

Qt 6's module porting status is **independent of Qt 5's**; currently only the qtbase module has been merged.

| Module category | Qt 5 status | Qt 6 status |
|-----------------|-------------|-------------|
| **qtbase** (Core/Gui/Widgets/Network/Qml/Quick) | ✅ Completed | ✅ Merged into dev |
| **qtbase** (Test/Sql/Concurrent/OpenGL) | ✅ Completed | ✅ Verified: Test has OHOS hilog integration, and Sql/Concurrent/OpenGL need no OHOS-specific code |
| **Non-qtbase** (Multimedia/3D/Charts/...) | ✅/❌ see [[qt-harmonyos-modules]] | ⚠️ **Source superbuild (strategy B) ❌ not started**. **Prebuilt installer (strategy B') ✅ all present**: libQt6Multimedia/Charts/3DCore/3DRender/OpenGL/OpenGLWidgets/DataVisualization/Bluetooth/Location/Positioning/Sensors/SerialBus/UiTools/Core5Compat/WebSockets/SerialPort/Svg/SvgWidgets/Help/Designer/NetworkAuth/TextToSpeech/HttpServer/ShaderTools/Qml/Quick/QuickControls2/Quick3D are all present (ground truth 2026-07-25, see decision 1 of the batch 2 build retrospective). **Only WebEngine/DBus/Wayland/Pdf/Script are missing.** |
| **QtOhosExtras** (the Qt5 name) / **QtHarmonyExtras** (the Qt6 beta3 name) | ✅ Completed | ⚠️ **beta2**: not a standalone module; the functionality is scattered across `corelib/platform/ohos/` (QOhosAppContext) and `plugins/platforms/ohos/` (startAppProcess, ShareKit, window tagging etc.), all in private `_p.h`. **beta3 (re-checked 2026-08-25)**: standalone again as the `Qt6HarmonyExtras` module (`libQt6HarmonyExtras.so` + cmake), but the public headers are only the exports/version stubs and all 16 functional headers are private `_p.h`. |

For the detailed Qt 6 module status see [Qt for HarmonyOS Module Adaptation Status](https://wiki.qt.io/Qt_for_HarmonyOS) (the Qt6 part of the wiki page)

## Strategies for porting Qt 6 projects

Qt for HarmonyOS's main branches are still **Qt 5.12.12 / 5.15.16**. If a Qt 6 HarmonyOS porting request comes in, there are two strategies:

### Strategy A: downgrade to Qt 5 (recommended, workable today)

See [[qt-ohos-project-analyzer-workflow]] §"Qt6 project → Qt5 compatibility assessment":
1. Detect Qt 6-only features in the source
2. Look for the project's Qt 5 compatible branch or tag
3. Use the `QT_VERSION_CHECK` macro for conditional compilation

### Strategy B: use a Qt 6.12 superbuild (✅ recommended, verified on Windows)

> **Verified 2026-07-13**: Qt 6.12.0 (`c7581743`) **builds** on Windows with a MinGW g++ 13.1.0 host and an OHOS Clang 15.0.4 target (API 23, HarmonyOS 6.1.0); the superbuild configures all the submodules in one go (qtbase/qtsvg/qtimageformats/qtshadertools/qtlanguageserver/qtdeclarative), and the gallery demo ran on a physical HUAWEI MateBook 14 ("Widget Gallery Qt 6.12.0"). It needs 4 extra Windows configuration items + the DT_NEEDED patch, but no source patches.

1. Build Qt **6.12.0** (`c7581743`) as a superbuild with MinGW g++ 13.1.0 as the host compiler (no source patches needed).
2. Extra Windows configuration (not mentioned in the wiki): specify `NodeAddonApi_INCLUDE_DIR` and `_INCLUDE_DIR` + `_LIBRARY` for `EGL/GLESv2/Fontconfig` by hand (7 CMake variables in total), and set the `DEVECO_SDK_HOME` + `JAVA_HOME` environment variables.
3. **A mandatory runtime check after building your library/application**: use a Python script to binary-patch the DT_NEEDED entries of every `.so`, removing the absolute Windows path prefixes (a developer build makes CMake write absolute paths → `dlopen` fails on the device).
4. Modules: **qtbase + qtsvg + qtimageformats + qtshadertools + qtlanguageserver + qtdeclarative (including Quick/QuickControls2)** all built and verified. The non-qtbase modules (Multimedia/3D/Charts etc.) are still unported.
5. Handle the Qt5→6 API differences (the close event API becoming private, the QStandardPaths `AppLocalDataLocation` mapping moving from `filesDir` to `preferencesDir`, the CMake `qt_add_executable`).

### Strategy B': use the Qt 6.12 prebuilt-installer SDK (✅ recommended, less work than a source superbuild)

> **Verified 2026-07-25 (two batches, 14 of 15 applications succeeded)**: the SDK installed by the Qt 6.12.0 beta2 prebuilt installer (the Qt online installer with `Qt 6.12.0 → HarmonyOS arm64_v8a` + `MinGW 64-bit` + `CMake + Ninja` checked — the Qt 6.12 prebuilt-installer SDK) was used to batch-build a list of not-yet-ported Qt6 applications. **Batch 1**: 4 of 5 pure-Widgets applications succeeded (password manager / Git client / data modeling / image viewer tools, adversarially verified real=true — see the batch 1 build retrospective). **Batch 2**: 10 applications (extending into the opengl/qml/uitools/svg modules) succeeded **10/10** (3D math visualization / CAD / clipboard / SQLite tools and others, including 2 that succeeded on retry + 2 with compile-boundary stubs + 1 Qt5→6 port — see the batch 2 build retrospective). **The key correction: the prebuilt SDK is a complete Qt 6.12 distribution** (50+ module .so files + the full qml runtime, missing only WebEngine/DBus/Wayland/Pdf/Script), not the "37 modules / qtbase+5" of the old notes.

**It eliminates 3 major pitfalls compared with the source superbuild (strategy B)** (contrast with the Qt6 porting retrospective of an editor application):
1. **No patch_dt_needed required**: the prebuilt libQt6Core.so already has bare NEEDED names (libicui18n/libicuuc/libicudata/libz/libc++_shared/libc etc.), and your own .so gets bare names too after linking against the Qt libraries. A source superbuild with `-developer-build` writes absolute Windows paths and needs patching (a lesson from practice).
2. **No shims or trimming required**: the prebuilt SDK is a **complete Qt 6.12 distribution** (ground truth 2026-07-25: libQt6Quick/Multimedia/Charts/3DCore/3DRender/OpenGL/OpenGLWidgets/DataVisualization/Bluetooth/Location/Positioning/Sensors/SerialBus/UiTools/Core5Compat/WebSockets/SerialPort/Svg/SvgWidgets/Help/Designer/NetworkAuth/TextToSpeech/HttpServer/ShaderTools/Qml/Quick/QuickControls2/Quick3D + the QtQuick qml runtime are all present, missing only WebEngine/DBus/Wayland/Pdf/Script). A source superbuild only has qtbase + 5 submodules, so Core5Compat/Svg/UiTools/Multimedia/Quick and friends have to be built yourself or shimmed. Batch 2's three kinds of applications — qml / uitools+svg+qml / opengl — all succeeding is direct corroboration.
3. **No Qt6_DIR/QT_DIR/junction required**: the prebuilt SDK is an installed SDK (the standard `lib/cmake/Qt6/` layout), not a build tree. A source superbuild's build-tree forwarding headers hardcode absolute source paths and need a junction (a lesson from practice).

**The build recipe (CLI, qt-cmake.bat + harmonydeployqt6)**:
```
# Environment variables (export them in every Bash invocation; shell state doesn't persist)
export NODE_HOME=<DevEco>/tools/node JAVA_HOME=<DevEco>/jbr/bin DEVECO_SDK_HOME=<DevEco> QT_HARMONYOS_HVIGOR=<DevEco>/tools/hvigor/bin/hvigorw.bat
export PATH="<DevEco>/tools/node/bin:<DevEco>/jbr/bin:<DevEco>/tools/hvigor/bin:<DevEco>/tools/ohpm/bin:$PATH"

# configure (qt-cmake.bat sets CMAKE_TOOLCHAIN_FILE=qt.toolchain.cmake automatically; you MUST add QT_CHAINLOAD_TOOLCHAIN_FILE or it falls back to the default Linux path → the OHOS toolchain isn't loaded → clang builds for the host and links Windows libraries → broken)
cmd //c "<harmonyos_arm64_v8a>/bin/qt-cmake.bat" -G Ninja -DQT_HOST_PATH=<mingw_64> -DOHOS_SDK_NATIVE=<native> -DQT_CHAINLOAD_TOOLCHAIN_FILE=<native>/build/cmake/ohos.toolchain.cmake -DOHOS_ARCH=arm64-v8a -DCMAKE_PREFIX_PATH=<harmonyos_arm64_v8a> <src>

cmake --build . -j8   # your .so (qt_add_executable makes it a MODULE with main GLOBAL DEFAULT automatically)

# Package the HAP (the json is generated automatically when qt_add_executable is configured)
<harmonydeployqt6.exe> --input <target>-harmony-deployment-settings.json --output <hap dir> --hvigor <wrapper.bat> --verbose
```

**The key fixes (common to the 3 successful projects)**:
- Use `qt_add_executable` (not `add_executable`) in the app's CMake → an automatic MODULE .so + `CXX_VISIBILITY_PRESET=default` (so main is GLOBAL DEFAULT automatically, with no manual visibility attribute) + a generated `<target>-harmony-deployment-settings.json` + bundled Qt 6.12-compatible ets glue (`APP_LIBRARY_NAME` pointing at your .so). Three shapes of app CMake conversion: already using qt_add_executable upstream (a Git client) / writing a CMakeLists that wraps the qmake sources (a password manager) / changing a custom macro → qt_add_executable on OHOS (a modeling tool).
- **harmonydeployqt6 sanitizes the child process env and loses java**: hvigorw's node workers spawn `java` (to run app_packing_tool.jar during PackageHap) → `spawn java ENOENT`, even when the parent process's PATH contains jbr/bin. The fix: write a `hvigor-wrapper.bat` that re-injects `jbr/bin` + `JAVA_HOME` before calling the real hvigorw.bat, and pass it via `harmonydeployqt6 --hvigor <wrapper.bat>`; or just run `hvigorw.bat assembleHap` directly (bypassing harmonydeployqt6's cmake `_make_hap` target — bash uses the MSYS `/c/` path for java and git-bash converts to Windows paths for child processes).
- When a third-party library has no OHOS arm64 prebuilt, use a **no-op static stub** (a modeling tool's libpq/libxml2: 29 PQ* + 7 xml* functions + self-consistent structs; the `.so` links and loads cleanly with no DT_NEEDED on libpq/libxml2, and the DB/XML runtime is non-functional — a compile-only boundary).

For the paths see the Qt 6.12 prebuilt QtC configuration workflow (the QtC IDE flow, whose recipe this batch turned into CLI form) + the Qt 6.12 prebuilt paths in ENV.local.md. For the source superbuild see the Qt 6.12 source superbuild workflow.

> ⚠️ **Four more lessons from batch 3 on 2026-07-27 (16 applications, 8 succeeded, 8 blocked)** (see the batch 3 build retrospective):
> - **"The module layer is feasible" ≠ "the application builds"**: the prebuilt SDK overturned 3 more old "missing module" blocks (a serial port tool's old "Quick absent" → Quick is all there and it builds; a video inspection tool's old "Multimedia missing" → Multimedia is complete now, the real blocker is native FFmpeg; a terminal emulator's old "Quick hard-requires" → Quick is complete now, the real blocker is DBus+xcb). Once overturned, the real blockers are usually heavyweight native libraries (FFmpeg, DBus+xcb), not Qt modules. For applications labelled "Quick/Multimedia/3D absent" you should: ① verify the module layer first (the prebuilt SDK very likely has it); ② then verify the heavyweight native dependency layer.
> - **Missing DBus is a hard, deterministic wall with the prebuilt SDK** (see known issue \#18): an application that requires DBus unconditionally can't be built, can't be stubbed, and can't be `-DCMAKE_DISABLE`d; an application with optional DBus (skipped behind a `Q_OS_OHOS` guard) builds fine.
> - **C++23 deducing-this/ranges is a compiler capability gap** (see known issue \#19): OHOS clang 15.0.4 doesn't support P0847 (which needs Clang 18+); a stub can't fix it, so it's a hard ceiling.
> - **`#ifdef Q_OS_LINUX` isn't trustworthy** (see known issue \#20): Qt6 OHOS defines both Q_OS_HARMONY + Q_OS_LINUX and does **not** define Q_OS_OHOS, so desktop-only feature guards must use `#if defined(Q_OS_LINUX) && !defined(__OHOS__)`; writing `&& !defined(Q_OS_OHOS)` is always true on Qt6, so it guards nothing.
> - More compile-boundary stubs: Merkaartor (a GDAL/PROJ C++ class hierarchy stub), Drawpile (libav/libwebp/libzip/KArchive/libsodium stubs). Across all 3 prebuilt batches: 22 of 31 applications succeeded.

## Known issues and open questions

| # | Item | Status |
|---|------|--------|
| 1 | How Qt 6's new QStandardPaths enumerators map on OHOS | ✅ Verified: `PublicShareLocation`/`TemplatesLocation` are unsupported; `StateLocation`/`GenericStateLocation` → `filesDir` |
| 2 | Whether there's a Qt 6 version of the QtOhosExtras module | ✅ Verified (beta2) + ⚠️ corrected for beta3 (2026-08-25): **beta2** (the 6.12.0-beta2 prebuilt) isn't a standalone module — the functionality is spread across `corelib/platform/ohos/` and the QPA internals, all private `_p.h`. **beta3** (re-checked against the local `${QT6_INSTALLER_ROOT}/6.12.0/harmonyos_arm64_v8a`) is **a standalone `Qt6HarmonyExtras` module again**: `lib/libQt6HarmonyExtras.so` + `lib/cmake/Qt6HarmonyExtras/` + the `Qt6HarmonyExtrasPrivate/` cmake target; `include/QtHarmonyExtras/`'s public headers are only the two stubs `qtharmonyextrasexports.h` + `qtharmonyextrasversion.h`, and all 16 functional headers are private `_p.h`. In other words: the module is standalone again, but the public API surface is still empty. See the "Qt6 beta3 file permission granting interfaces" section below. |
| 3 | Functional differences between the Qt 6 QPA plugin (qohos) and Qt 5's | ✅ Verified: 196 files, a major change to the close event API (made private + changed enumerators), and identical window tagging API signatures |
| 4 | The timeline for porting the non-qtbase modules | ⚠️ **Corrected (2026-07-25)**: the source superbuild (strategy B) is qtbase + 5 submodules only, and the non-qtbase modules have no HarmonyOS support. **The prebuilt installer (strategy B') is a complete Qt 6.12 distribution** — the Multimedia/3D/Charts/OpenGL/DataVisualization/Bluetooth/Location/Sensors/SerialBus/UiTools/Core5Compat/Quick/QuickControls2 .so files + the QtQuick qml runtime are **all present** (ground-truth re-check). Only WebEngine/DBus/Wayland/Pdf/Script are missing. Corroborated by batch 2's four kinds of applications — qml / uitools+svg+qml / opengl / openglwidgets — all building successfully against the prebuilt SDK (decision 1 of the batch 2 build retrospective) |
| 5 | How Qt 6's `qt_add_qml_modules` behaves when cross-compiling for OHOS | 🟡 Partly verified: it only appears in qtbase's cmake in `QtInitProject.cmake` (the project template); the actual implementation is in the `qtdeclarative` repository (not available locally). OHOS-specific behavior can't be verified from the qtbase source |
| 6 | Whether Qt 6's minimum SDK API level is still 20 | ✅ Updated: the Qt5 wiki records API 20; the Qt6 source hardcodes no minimum API; the local SDK is **API 24** (HarmonyOS 6.1.1 Beta1) |
| 7 | The `AppLocalDataLocation` mapping change | ✅ Verified: Qt5 `filesDir` → Qt6 `preferencesDir` (a breaking change) |
| 8 | The missing public close event API | ✅ Verified: Qt6's `CloseRootCause` is a private API and there's no public `getCloseEventRootCause()` |
| 9 | The status of the qtbase Test/Sql/Concurrent/OpenGL modules on OHOS | ✅ Verified: Test has OHOS hilog integration (`qOhosLogMessage`), and Sql/Concurrent/OpenGL need no OHOS-specific code |
| 10 | Whether Qt 6.12 can be built on Windows + the OHOS NDK musl | ✅ **Verified (2026-07-13)**: the 6.12.0 superbuild with a MinGW g++ 13.1.0 host builds with no source patches, and the gallery demo ran on a physical device. The original -isystem musl BLOCKER (llvm-mingw clang 22 + API 24 + per-module paths, see [build-fail-qt6-libcpp-musl-isystem]) didn't reproduce with this combination; the three variables weren't isolated individually |
| 11 | Qt6 `.so` files having absolute Windows paths in `DT_NEEDED` | ✅ Verified: **source superbuild (strategy B)**: Qt6 `.so` files have no SONAME and `-developer-build` imported targets are linked by absolute path → NEEDED records absolute Windows paths → `dlopen` fails on the device, so you **must rewrite them to bare names with `patch_needed.py`** (your libraries plus the Qt libraries themselves). **The prebuilt installer (strategy B') doesn't have this problem**: libQt6Core.so's NEEDED entries are already bare names, and your .so gets bare names after linking — all 14 successful projects in batches 1 and 2 needed 0 patch scripts. Verify with `llvm-readelf -d` (see the quick reference in problems/_lookup.md) |
| 12 | The dynamic visibility of `main` in a Qt6 application library | ✅ Verified: when the target uses `CXX_VISIBILITY_PRESET hidden`, `main` is a local symbol and `dlsym("main")` fails. **Add `__attribute__((visibility("default")))` to `main`** and verify it's `GLOBAL DEFAULT` with `llvm-readelf --dyn-syms` (see the quick reference in problems/_lookup.md) |
| 13 | The initial URI and file filters of the Qt6 OHOS native file picker | ✅ Verified: `DocumentViewPicker`'s `defaultFilePathUri` and `fileSuffixFilters` are both optional fields; you can't pass the application's private directory or an extensionless glob like `qmake*`. When the initial path is empty or the suffix filter can't be represented, the corresponding field must be omitted (see [runtime-fail-file-dialog-invalid-default-uri]) |
| 14 | Whether the prebuilt installer includes "non-qtbase" modules like Quick/Multimedia/3D/Charts | ✅ **Verified (ground truth 2026-07-25)**: the prebuilt SDK is a **complete Qt 6.12 distribution**. libQt6Quick.so (7.8 MB)/Multimedia/Charts/3DCore/3DRender/OpenGL/OpenGLWidgets/DataVisualization/Bluetooth/Location/Positioning/Sensors/SerialBus/UiTools/Core5Compat/WebSockets/SerialPort/Svg/SvgWidgets/Help/Designer/NetworkAuth/TextToSpeech/HttpServer/ShaderTools/Qml/QuickWidgets/QuickControls2/Quick3D are all present, as is the QtQuick qml runtime (Controls/Dialogs/Layouts). **Only WebEngine/DBus/Wayland/Pdf/Script are missing.** The old KB notes "Quick .so absent", "Multimedia missing" and "3D not started" are stale records from the source superbuild era and don't hold for the prebuilt SDK (decision 1 of the batch 2 build retrospective) |
| 15 | Whether the compile-only stub pattern works | ✅ **Verified (2026-07-25)**: for applications blocked on functionality (every Qt module present, but non-functional at runtime — e.g. QPS's /proc process control, a classroom management application's VNC/X11 injection), no-op stubs (a header-only INTERFACE + a no-op cmake module + a STATIC IMPORTED .a) let the .so link and load cleanly, producing a `builds ✓ / runs ✗` HAP. The stubs must be added to `CMAKE_FIND_ROOT_PATH` (required by `ohos.toolchain`'s `MODE_PACKAGE=ONLY`), not just CMAKE_PREFIX_PATH (decision 3 of the batch 2 build retrospective) |
| 16 | A QRegExp compatibility approach for Qt5→6 porting | ✅ **Verified (2026-07-25, a CAD application)**: Qt6 removed QRegExp, so when many files use QRegExp's own API (indexIn/cap/pos/setPatternSyntax), write a forwarding header defining `QRegExp` as a subclass of `QRegularExpression` and put it **ahead of** Qt5Compat's -isystem via `-I`, avoiding a file-by-file API rewrite. Along with 8 mechanical Qt5→6 fixes (setCodec→setEncoding, DataLocation→AppDataLocation, QPrinter paper→QPageSize, the QActionGroup include, the modifier operator+→\|, setMargin→setContentsMargins, QTabletEvent PointerType→QPointingDevice, wrapping int/char in QChar) (decision 4 of the batch 2 build retrospective) |
| 17 | The path requirements of harmonydeployqt6's `--hvigor` argument | ✅ **Verified (2026-07-25)**: `--hvigor <wrapper.bat>` must be an **absolute path** — a relative path reports 'Failed to start hvigorw' (harmonydeployqt6 invokes hvigor with the generated project dir as cwd). `harmonydeployqt6` has no `--sdk-root` flag, so a stale sdk-root has to be edited by hand in the deployment json input (failure points 1 and 3 of the batch 2 build retrospective) |
| 18 | Missing DBus is a hard, deterministic wall with the prebuilt SDK | ✅ **Verified (2026-07-27, batch 3: three applications hard-blocked on DBus)**: the prebuilt SDK has no Qt6DBus. **An application that requires DBus unconditionally can't be built** — it can't be stubbed (QDBusAbstractAdaptor/Interface are Q_OBJECT base classes needing moc, plus the whole QDBus API) and `-DCMAKE_DISABLE_FIND_PACKAGE_Qt6DBus` doesn't work (it has no effect on a component `find_package`). Case one (an unconditional top-level `#include <QtDBus>` in request.h + Q_OBJECT inheritance + the `!MACOS&&!WIN` path being taken), case two (`find_package(Qt6 DBus REQUIRED)` with no option guard), case three (DBus in the core sources). **By contrast, optional DBus builds fine**: three other applications demonstrably skip DBus behind a `Q_OS_OHOS` guard and build. The decision rule: grep the source for an unconditional top-level `#include <QtDBus>`, Q_OBJECT inheritance, and an unguarded find_package DBus REQUIRED → any one of the three means it can't be built (decision 2 of the batch 3 build retrospective) |
| 19 | Whether OHOS clang supports C++23 deducing-this / the ranges adaptors | ✅ **Verified (2026-07-27, batch 3: an application depending on C++23 features)**: OHOS's native clang **15.0.4 doesn't implement C++23 deducing-this (P0847R7)** (that needs Clang 18.0+) and no -std flag enables it on 15 (measured: under `-std=gnu++2b`, `auto f(this auto& self)` reports "expected parameter declarator", 20 errors); libc++ likewise lacks the C++23 ranges adaptors (`std::views::zip`/`cartesian_product`). Applications using these features must wait for the OHOS NDK to move to Clang 18+/libc++ 19+, or downgrade at the source level (deducing-this → CRTP, ranges → hand-written loops). **A compiler capability gap**, not a Qt module or platform limitation, and not fixable with a stub (decision 3 of the batch 3 build retrospective) |
| 20 | Whether a Q_OS_LINUX guard is reliable on Qt6 OHOS | ✅ **Verified (2026-07-27, batch 3, two desktop applications; macro names corrected from the `qsystemdetection.h` source on 2026-11-16)**: on OHOS, the `<kit>/include/QtCore/qsystemdetection.h` of Qt6.12+/6.13.0-dev takes the `#elif defined(__OHOS__)` branch, which **defines only `Q_OS_HARMONY`, from which `Q_OS_LINUX` is then derived; it does not define `Q_OS_OHOS`** (`Q_OS_OHOS` is a macro only the vendor Qt 5.15 kit has). So when source code guards desktop-only functionality (DBus/systemd/X11/procfs) with a bare `#ifdef Q_OS_LINUX`, it still fires on OHOS → the build fails (DBus is missing from the prebuilt SDK). **The correct guard**: `#if defined(Q_OS_LINUX) && !defined(__OHOS__)`, or `!(defined(Q_OS_OHOS) || defined(Q_OS_HARMONY))`; `&& !defined(Q_OS_OHOS)` is always true on Qt6 — a fake fix. Grepping for `Q_OS_LINUX` is still an early signal of DBus-class blockers (decision 5 of the batch 3 build retrospective) |

| 21 | HarmonyOS support for the Qt 6.12 IoT addon modules (Mqtt/Coap/Opcua/Knx) | ✅ **Verified (2026-08-03, qtmqtt `v6.12.0-beta2`)**: these are Qt **source-only add-on modules** and are **not in the prebuilt installer** (the open-source installer has no such component to check, and the commercial edition ships them as source), which is a different situation from "the distribution is missing WebEngine/DBus" — you have to build them yourself. But **the prebuilt OHOS kit ships `Qt6BuildInternalsConfig.cmake`** (`lib/cmake/Qt6BuildInternals/`), which by design supports building Qt add-on modules. The process: clone `qt/qtmqtt`, check out the matching tag → cross-compile with `qt-cmake.bat` + `ohos.toolchain.cmake` (`-DQT_BUILD_EXAMPLES=OFF -DQT_BUILD_TESTS=OFF`) → `CMAKE_INSTALL_PREFIX=<QT6_OHOS_KIT>` to **install it into the OHOS kit** (the key move: libQt6Mqtt.so goes into the kit's `lib/`, the cmake config into `lib/cmake/Qt6Mqtt/`, the headers into `include/QtMqtt/`, so that both your demo's `find_package(Qt6 Mqtt)` and harmonydeployqt6's library copying just work with no extra path configuration) → build your application normally with `qt_add_executable`. Verification: libQt6Mqtt.so (395 KB) + libsimplemqttclient.so + a 36 MB HAP were all produced, every NEEDED entry is a bare name (libQt6Mqtt.so's NEEDED includes libQt6WebSockets.so, and harmonydeployqt6 pulls the dependencies in recursively and correctly), 0 patches. ⚠️ Licensing: the open-source QtMqtt is **GPLv3** (not LGPL), so a closed-source commercial release needs a Qt commercial license or a switch to Paho.mqtt-c/mosquitto (EPL/EDL, non-viral). The same method should work for CoAP/Opcua/Knx (unverified). See [[qt-harmonyos-third-party-libs]] §9 QtMqtt. ⚠️ **A runtime correction on 2026-08-04**: #21 originally only verified the build artifacts (the library, the HAP, the bare NEEDED names) and never ran end to end on a device. Actually running it (the mqttclient-ohos demo) revealed that the Qt6 prebuilt kit's Qt `.so` files carry HARD DT_NEEDED entries on third-party libraries (libQt6Core→libicui18n/uc/data, libQt6Gui→libfontconfig/png16/freetype, libQt6Network→libbrotlidec/common, libfontconfig→libexpat) that are neither in the kit's `lib/` nor part of the OHOS system libraries, and harmonydeployqt6 doesn't copy them automatically → the HAP installs but crashes on startup with dlopen(libQt6Core) → libicui18n not found. The fix: manually stage the 9 third-party `.so` files into `hap/entry/libs/arm64-v8a/` (copied from additional-packages or from a gallery-ohos demo that already runs) + `hvigorw assembleHap` to repackage → the HAP goes from 34 MB to 73 MB with a complete dependency chain. The full root cause and fix steps are in the KB error library (problems/) and §6 pitfall #12 of the HarmonyOS Qt application development guide (both internal KB pages, not reachable in the public edition), so they aren't expanded here. |

## References

- [Building Qt6 for HarmonyOS](https://wiki.qt.io/Building_Qt6_for_HarmonyOS) — The Qt 6 build guide
- [Qt for HarmonyOS](https://wiki.qt.io/Qt_for_HarmonyOS) — The main page (including the Qt5/Qt6 module porting status)
- [Building Qt for HarmonyOS (Qt5)](https://wiki.qt.io/Building_Qt_for_HarmonyOS) — The Qt 5 build guide (for comparison)
- [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations) — Platform limitations (shared by Qt5/Qt6)
- [Long live Qt for HarmonyOS! (Reddit)](https://www.reddit.com/r/QtFramework/comments/1te37o5/long_live_qt_for_harmonyos/) — The announcement that Gerrit 733351 was merged
- [Qt 6 Build System (Qt Blog)](https://www.qt.io/blog/qt-6-build-system) — An introduction to Qt 6's CMake build system
- **The Qt 6 qtbase source** (verified locally):
  - `<LOCAL_PATH>` — The QStandardPaths OHOS mappings
  - `<LOCAL_PATH>` — The close event API (private)
  - `<LOCAL_PATH>` — The window tagging API
  - `<LOCAL_PATH>` — The QPA functions (ShareKit/FloatWindow)

## Change history

| Date | Change |
|------|--------|
| 2026-07-06 | Page created; the initial record of Qt6 HarmonyOS status (qtbase dev has merged Gerrit 733351, minimum SDK API 20) |
| 2026-07-13 | Strategy B source superbuild verified on Windows (a MinGW host + an OHOS Clang target, with gallery running on a physical device) → the Qt6 Windows source superbuild workflow (internal) |
| 2026-07-23 | Qt Creator kit configuration verified (the prebuilt installer + the QtC IDE, the samegame demo) → the Qt Creator kit configuration workflow (internal) |
| 2026-07-25 | Strategy B' prebuilt installer ground-truth re-check: a complete Qt 6.12 distribution (50+ module .so files + the qml runtime); 14 of the 15 applications in batches 1 and 2 succeeded |
| 2026-07-27 | Batch 3: 16 applications, 8 succeeded, 8 blocked; added the three lessons about the DBus hard wall, the C++23 ceiling, and the Q_OS_LINUX double definition |
| 2026-08-02 | Strategy B' prebuilt end-to-end CLI verification (the Qt6 prebuilt CLI end-to-end workflow, internal): the widgets/gallery demo configured → built → packaged into a ~33 MB HAP successfully; captured 11 pitfalls + a hvigor-wrapper.bat placeholder template |
| 2026-08-03 | Qt6 + CEF HarmonyOS integration verified (the Qt6 + CEF integration workflow, internal): the OpenQtCef Qt5→Qt6 migration, with the HAP launching on a physical device; IoT add-on (qtmqtt) HarmonyOS cross-compilation verified (known issue \#21) |
| 2026-08-25 | The beta3 ground-truth re-check (against the local `${QT6_INSTALLER_ROOT}/6.12.0/harmonyos_arm64_v8a`): `Qt6HarmonyExtras` is a standalone module again (`libQt6HarmonyExtras.so` + cmake, with public headers that are only exports/version stubs and all 16 functional headers private `_p.h`) → overturning the beta2 conclusion that it "doesn't exist as a standalone module" (correcting known issue #2 + the module porting status table + the QPA changes section); added the "Qt6 beta3 file permission granting interfaces" section (the public `QPermissions` API has no file permission type + `QtHarmonyExtras::FileShare::persistPermission` is private + the picker isn't wrapped, so use HarmonyOS's native `@ohos.file.picker`/`@ohos.fileshare`) |
