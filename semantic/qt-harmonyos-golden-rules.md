---
id: semantic-qt-harmonyos-golden-rules
type: semantic
domain: tech
tags: [qt, harmonyos, golden-rules, quick-reference, porting, checklist]
created: 2026-06-03
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-porting-workflow, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-lifecycle, semantic-qt-harmonyos-api-mapping, semantic-qt-harmonyos-code-patterns, semantic-qt-harmonyos-window-model, semantic-qt-ohos-extras, semantic-qt-harmonyos-build, semantic-qt-harmonyos-third-party-libs]
summary: >
  A quick reference of the iron rules for porting Qt to HarmonyOS: 38 golden rules covering build and deployment, window management, API/enum paths,
  how platform limitations affect Qt, lifecycle adapters, and cross-platform guards. Each rule has a severity (🔴🟠🟡🟢), a "why", and a source.
  Agents should scan this page before performing any Qt for HarmonyOS task.
---

# Golden rules for porting Qt to HarmonyOS

> **Agent guidance**: scan this page before performing any Qt for HarmonyOS task.
> Each rule cites its source; follow the links when you need the details.
> This page is a quick decision hub for Qt, not a second canonical source for platform facts. For HAP/signing, see [[ohos-common-kb/semantic/hap-native-project-structure|HAP native project structure and its relationship to signing]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/hap-native-project-structure.md)); for platform limitations, see [[ohos-common-kb/semantic/harmonyos-platform-limits|HarmonyOS platform limitations]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md)); for Stage/UIAbility, see [[ohos-common-kb/semantic/stage-uiability-lifecycle|The Stage model and the UIAbility lifecycle]] ([standalone](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md)). The tables below keep only how those facts affect Qt and what Qt must do about them.
>
> **⚠️ Version applicability**: this rule set is based on **Qt 5.12/5.15**. Qt 6 for OHOS has the following major changes:
> - **The QtOhosExtras module no longer exists standalone** — its functionality is inlined into the QPA plugin as private API (`_p.h`), so rules B6/A3/A4/A5/A6 don't apply in Qt6
> - **The close event API is now private** — `CloseEventRootCause` → `CloseRootCause` (private), with renamed enumerators (`AbilityClose` → `OnPrepareToTerminate`)
> - **The CMake API changed comprehensively** — `find_package(Qt6...)`, `qt_add_resources()`, `qt_add_qml_modules()`, and so on
>
> For the Qt6 differences in detail, see [[qt-harmonyos-qt6-status]].
>
> **Severity legend**: 🔴 blocks the build/deployment | 🟠 silent failure (hard to debug) | 🟡 misbehavior (recoverable) | 🟢 informational / best practice

---

## 1. Build and deployment (12 rules)

| # | Severity | Rule | Why | Source |
|---|:--------:|------|-----|--------|
| B1 | 🔴 | When cross-compiling, CMakeLists.txt **must** set `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` before `find_package` (the same applies to third-party libraries) | The OHOS toolchain defaults to `ONLY`, preventing Qt and third-party libraries from being found | [[qt-harmonyos-project-structure]] §4.2, [[qt-harmonyos-third-party-libs]] §2.2 |
| B2 | 🔴 | You **must** link `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin` (the QPA platform plugin) | Without it you get `dlopen failed: libqohos.so not found` | [[qt-harmonyos-project-structure]] §4.2 |
| B3 | 🔴 | `APP_LIBRARY_NAME` (in QtAppConstants.ets) **must** match the built library name exactly (including the `lib` prefix and `.so` suffix) | A mismatch means the ArkTS layer can't load the .so | [[qt-harmonyos-project-structure]] §5 |
| B4 | 🔴 | **Never** set `compileSdkVersion` or `targetSdkVersion` | Setting them causes "Schema validate failed" | [[qt-harmonyos-project-structure]] §9 |
| B5 | 🟡 | `runtimeOS` **must** be set to `"HarmonyOS"` (not `"OpenHarmony"`) | It affects application packaging and signing | [[qt-harmonyos-project-structure]] §4.3 |
| B6 | 🟡 | The QtOhosExtras module **only supports qmake** (`CONFIG -= create_cmake`); there's no find_package support in CMake. **In Qt6**: the module no longer exists standalone, its functionality having been inlined into the QPA plugin | CMake config generation is disabled in the source | [[qt-ohos-extras]] §Usage, [[qt-harmonyos-qt6-status]] |
| B7 | 🟡 | **Qt 5.15 kit**: `libqohosstyle.so` must be copied manually into `libs/${ABI_DIR}/styles/`. **Qt 6.12+**: `qt_add_executable` + `harmonydeployqt6` automatically deploy plugins sorted by plugin directory, so no manual copying is needed — copying by hand may actually overwrite the packaged output | `target_link_libraries` can't deploy plugins into a subdirectory; the Qt5 and Qt6 deployment pipelines differ (in Qt6 the macros collect and harmonydeployqt6 writes to disk) | [[qt-harmonyos-project-structure]] §6.2 |
| B8 | 🟡 | In scenario two (porting an existing project), the `path` in `build-profile.json5` **must** be absolute | A relative path won't find the source files | [[qt-harmonyos-project-structure]] §9 |
| B9 | 🔴 | qmake's `unix` branch **must** append `:!ohos` (`unix:!android:!macx:!ohos`) | Otherwise ohos also matches the unix branch and you compile the wrong (Linux) code | [[qt-harmonyos-code-patterns]] §Pattern 7 |
| B10 | 🔴 | QML applications **must** enable `CMAKE_AUTORCC ON` | Without it, qml.qrc isn't compiled, the QML files aren't packaged, and you get a black screen at runtime | [[qt-harmonyos-project-structure]] §4.2 |
| B11 | 🔴 | `bundleName` must be a stable dotted identifier the target SDK schema accepts, and must match the final generated project, the signing profile, and the install/launch commands | An inconsistent identity causes validation, signing, installation, or launch failures; the exact character range is determined by the target SDK | [[qt-harmonyos-project-structure]] §8 |
| B12 | 🟠 | **Qt 5.15 kit**: the SQL driver plugin `libqsqlite.so` must be copied manually into `libs/${ABI_DIR}/sqldrivers/` (the same class as B7 and `libqsvg.so` → `imageformats/`); **on Qt 6.12+ the packaging pipeline deploys it automatically** — after installing, just double-check with `unzip -l app.hap \| grep sqldrivers` | Dynamically categorized plugins can't be deployed via `target_link_libraries`; `QFactoryLoader` dlopens them from the subdirectory. If it's missing, `addDatabase("QSQLITE")` gives a null driver and `open()` returns false before ever touching the filesystem (`lastError="Driver not loaded"`). Note that in the OHOS SDK the filename is `libqsqlite.so` (not desktop's `libqsqlsqlite.so`) | [[qt-harmonyos-project-structure]] §6.2, [runtime-fail-sqlite-open-database](../problems/runtime-fail-sqlite-open-database.md) |

---

## 2. Window management (6 rules)

| # | Severity | Rule | Why | Source |
|---|:--------:|------|-----|--------|
| W1 | 🟡 | `tagWindowOrWidgetAsSubWindowOf()` **must** be called before `show()` and `winId()` | Calling it later has no effect — the window is already bound as a main window | [[qt-harmonyos-window-model]] §Tagging |
| W2 | 🟢 | The first `QWindow`/`QWidget` binds to the system main window automatically; **no** tagging is needed | The First Window Rule | [[qt-harmonyos-window-model]] §First Window Rule |
| W3 | 🟡 | A parentless `QDialog` is treated by the system as a **new main window**, so you must tag it or give it a parent. **A key concept**: a subwindow's "child" relationship is a system-level ownership relation (dock/taskbar visibility), **not** a Qt widget parent-child relationship — a `QWidget` with no Qt parent can still become a subwindow through tagging | Otherwise you get a separate dock icon and Alt+Tab entry | [[qt-harmonyos-window-model]] §Concepts, §Pattern 3 |
| W4 | 🟡 | The first window **can't** start fullscreen; you must `show()` first and then `showFullScreen()` | HarmonyOS requires Ability initialization to complete first | [[qt-harmonyos-window-model]] §Fullscreen |
| W5 | 🟡 | `hide()` on the main window falls back to minimizing (when there's no system tray) | This differs from desktop platform behavior | [[qt-harmonyos-api]] §hide |
| W6 | 🟠 | **Don't rely on the `WINDOW_HIDDEN`/`WINDOW_SHOWN` events as the only trigger for synchronizing window state** — they don't fire in file-acceleration/preload scenarios (device logs show 0 matches). The system can manage window visibility directly through WMS without going through Qt's window event callbacks | The WMS and Qt visibility state machines are independent, so when the system pushes a window to the foreground, Qt's Hidden flag may not be cleared → a white screen | [[qt-harmonyos-window-model]] §The independence of the WMS and Qt visibility state machines, and the white-screen retrospective |

---

## 3. API names and enum paths (6 rules)

| # | Severity | Rule | Why | Source |
|---|:--------:|------|-----|--------|
| A1 | 🟠 | Close event enumerators **must** use the fully qualified path: `QtOhosExtras::CloseEventRootCause::AbilityClose` (not `QtOhosExtras::AbilityClose`). **In Qt6**: the enum is renamed `CloseRootCause` and is now private | It's an enum class, so the short path doesn't compile | [[qt-harmonyos-lifecycle]] §Close events, [[qt-harmonyos-qt6-status]] |
| A2 | 🟠 | Theme enumerators **must** use the fully qualified path: `QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting` (omitting the `QOhosAppContext::` level doesn't compile). **In Qt6**: the enum may have moved or become private | It's an enum class nested inside `QOhosAppContext`, so the short path doesn't compile | [[qt-harmonyos-lifecycle]] §Themes, [[qt-harmonyos-qt6-status]] |
| A3 | 🟠 | The UI signals live on `QOhosUiAbilityContext` (not `QOhosAbilityContext`): `newWantReceived`, `continueRequestReceived`, `newWantInfoReceived`. **In Qt6**: the signal classes may have been restructured | The base class `QOhosAbilityContext` doesn't have these signals | [[qt-harmonyos-lifecycle]] §Continuation/sharing, [[qt-harmonyos-qt6-status]] |
| A4 | 🟢 | The factory methods live on `QOhosAbilityContext`: `getDefaultInstance()`, `getInstanceForMainWindow()`. **In Qt6**: the class may no longer exist | These are the base class's static methods | [[qt-harmonyos-lifecycle]] §Continuation, [[qt-harmonyos-qt6-status]] |
| A5 | 🟠 | qtohosextras headers are **lowercase only**, so `#include` **must** use lowercase: `<QtOhosExtras/qohosappcontext.h>` (**not** the CamelCase `<QtOhosExtras/QOhosAppContext>`). Note: unlike QtCore, qtohosextras **doesn't install CamelCase forwarding headers** (measured 2026-07-23: after install, `include/QtOhosExtras/` contains only `qohos*.h` with no `QOhos*` forwarding headers → CamelCase gives `file not found`). Core modules such as QtCore do have CamelCase forwarding headers (`QString` and friends); qtohosextras doesn't. **In Qt6**: the module doesn't exist, so these header paths are invalid | Measured: qtohosextras's install doesn't generate CamelCase forwarding headers; the old A5 rule ("always use CamelCase") does **not** hold for qtohosextras and has been corrected | [[qt-harmonyos-lifecycle]], [[qt-harmonyos-qt6-status]] |
| A6 | 🟠 | `getCloseEventRootCause()` is a **free function** (`QtOhosExtras::getCloseEventRootCause(event)`), not a member method. **In Qt6**: the function is now private (`_p.h`) | It lives in the QOhosWindowUtils header | [[qt-ohos-extras]] §Close events, [[qt-harmonyos-qt6-status]] |

---

## 4. Qt's response to platform limitations (5 rules)

| # | Severity | Rule | Why | Source |
|---|:--------:|------|-----|--------|
| P1 | 🟠 | Don't make a successful `QFile::setPermissions()` a prerequisite for your flow; resolve permissions for packaged files at packaging/installation time | A Qt wrapper can't bypass the platform's permission model | [[qt-harmonyos-platform-limits]] §chmod |
| P2 | 🟠 | `QFile::link()` — or any library that depends on symlinks — must offer a copy/direct-path alternative | Qt's file APIs are still bound by the platform sandbox | [[qt-harmonyos-platform-limits]] §symlink |
| P3 | 🟠 | Code artifacts for `QPluginLoader`/`QLibrary` go into the compliant native directory with the HAP, not loaded from an ordinary writable data directory | Qt's loader ultimately calls the platform's dynamic loader | [[qt-harmonyos-platform-limits]] §dlopen |
| P4 | 🟢 | Use Qt's cooperative thread stopping/interruption; don't introduce `pthread_cancel` assumptions on the OHOS path | A Qt adapter should keep portable stop semantics | [[qt-harmonyos-platform-limits]] §pthread |
| P5 | 🟢 | Qt time zone functionality should go through the verified ICU backend rather than scanning system tzdata paths directly | A framework backend must adapt to the platform's resource visibility | [[qt-harmonyos-platform-limits]] §Time zones |

---

## 5. Lifecycle and Ability (4 rules)

| # | Severity | Rule | Why | Source |
|---|:--------:|------|-----|--------|
| L1 | 🟠 | `closeEvent()` **must** check `CloseEventRootCause` to distinguish where the close came from. **⚠️ Level 2 (AbilityClose) must never show UI** — popping a dialog makes the application hang in the close flow and get force-killed by the system. Level 1 (WindowStageClose) may show a dialog; Level 2 can only autosave silently. **Qt6 note**: this API is now private and the enumerators changed (`AbilityClose` → `OnPrepareToTerminate`); see [[qt-harmonyos-qt6-status]] | Level 1 (the user closed the window) may show a dialog; Level 2 (the system is reclaiming it) **must not show UI** | [[qt-harmonyos-lifecycle]] §The three close levels |
| L2 | 🟢 | `argv[0]` is the **library path** (the .so), not an executable path | HarmonyOS loads Qt applications as shared libraries | [[qt-harmonyos-lifecycle]] §Passing arguments |
| L3 | 🟢 | The Qt event loop is started by the **Stage/UIAbility** adapter; don't build a separate legacy FA-model entry point | Qt's `main()` is a native entry point bridged by platform components | [[qt-harmonyos-lifecycle]] §Launch bridging |
| L4 | 🟢 | Choose your child-process mechanism **by scenario** rather than uniformly: headless can use `QProcess` / a Qt UI uses `startAppProcess()` or `startNewAbilityInstance()` / a non-Qt UI uses `startAbility(want)` / headless work that needs supervision uses `startNoUiChildProcess()` | Don't use a bare QProcess to start a child process with a UI (GUIs must go through the Ability framework); headless computation can keep using QProcess (corrected 2026-07-21 — the old "QProcess is unavailable" claim was inaccurate) | [[qt-harmonyos-lifecycle]] §Child processes, [[qt-harmonyos-api-mapping]] §1 |

---

## 6. Cross-platform guards (5 rules)

| # | Severity | Rule | Why | Source |
|---|:--------:|------|-----|--------|
| G1 | 🟢 | `Q_OS_OHOS` **implies** `Q_OS_LINUX` — `#ifdef Q_OS_LINUX` is also taken on HarmonyOS | You must check every Q_OS_LINUX branch for HarmonyOS compatibility | [[qt-harmonyos-porting-workflow]] §Principle 1 |
| G2 | 🟢 | Drag-and-drop event data can **only** be read in `dropEvent`; `dragEnterEvent`/`dragMoveEvent` only have the MIME types | HarmonyOS's drag-and-drop protocol transfers data asynchronously | [[qt-harmonyos-code-patterns]] §Pattern 9 |
| G3 | 🔴 | Platform guards **must accept both** `Q_OS_OHOS` and `Q_OS_HARMONY`: `#if defined Q_OS_OHOS \|\| defined Q_OS_HARMONY` | The Qt 5.15 kit defines `Q_OS_OHOS`, while Qt 6.12+ (including 6.13.0-dev) defines only `Q_OS_HARMONY`; a guard that names only one is **dead code** on the other kit and silently falls through to the Linux implementation | [[build-qt612-qos-harmony-macro]], [[platform-guard-needs-both-ohos-macros]] |
| G4 | 🔴 | Before changing platform dispatch, first distinguish **header dispatch** from **source file dispatch**: the former changes an `#ifdef` chain, the latter relies on the build selecting `ohos/xxx_ohos.cpp` by path | Changing only the `#ifdef`s permanently misses the source-dispatch half (typically 9 headers + 5 sources); what's missed shows up as undefined symbols at link time or silent degradation at runtime | [[platform-layer-two-dispatch-modes]] |
| G5 | 🟠 | **A manual `-DQ_OS_OHOS` is a fake fix**: `Q_OS_WIN` comes first in the dispatch chain, and `-D` can't rescue the case of the host triple | It turns a "kit fact" into a "build script convention", so it recurs when you switch kits; determine the branch taken with the full compile command + `-H`, not by looking at `flags.make` | [[platform-guard-needs-both-ohos-macros]] §4 |

### The "else means Linux" assumption in platform models (a new platform hits the full set)

The platform model of desktop applications (`desktop-app`-family projects like tdesktop) is "Win / Mac / **the rest**",
and "the rest" in practice means Linux. Any new platform hits four places at once, each with a different symptom:

| Location | Symptom | Existing criterion |
|------|------|---------|
| `cmake/nice_target_sources.cmake` | The platform filter doesn't recognize the `ohos/` directory → implementation files are marked `HEADER_FILE_ONLY` → zero errors at compile time, then a burst of undefined symbols at link time | [[build-qt612-qos-harmony-macro]] |
| `platform/platform_specific.h` | The dispatch chain lands on the Linux header → pulls in D-Bus / X11 / glib dependencies | [[platform-guard-needs-both-ohos-macros]] |
| `platform/platform_{tray,notification,main_window,overlay_widget,file_utilities,...}.h` | Each dispatches independently; fixing one doesn't fix the others | [[platform-layer-two-dispatch-modes]] |
| `base/screen_reader_state.cpp` | Lands on the Linux implementation → atspi/dbus dependencies | Same as above |

Audit method: `python tools/ohos-platform-audit.py <app>/SourceFiles/platform`
(header dispatch files must name both OHOS macros; a non-zero exit code blocks it).

---

## Quick decision flow

> For the full routing, see [[_task-routing|the task routing table]]. Here's the compact version:

```
A Qt for HarmonyOS task arrives
    │
    ├─ Port an entire application?     → porting-workflow (8 steps) + all of this page
    ├─ How do I replace an API?        → api-mapping (12 mapping categories)
    ├─ Is a module supported?          → modules
    ├─ Platform limitations?           → platform-limits
    ├─ A build/deployment problem?     → B1-B12 on this page + project-structure
    ├─ Odd window behavior?            → W1-W6 on this page + window-model
    ├─ The build says an API is missing? → A1-A6 on this page + ohos-extras
    ├─ Lifecycle/closeEvent?           → L1-L4 on this page + lifecycle
    ├─ How do I use QtOhosExtras?      → ohos-extras
    ├─ Something about Qt 6?           → qt6-status
    ├─ Third-party libs/dependencies?  → third-party-libs
    └─ DevEco/MCP/toolchain?           → the common DevEco CLI/MCP pages + qt-harmonyos-build-run-workflow
```

---

## References

This page is distilled from the knowledge pages below; follow the links for the details:

- [[qt-harmonyos-porting-workflow]] — The 8-step decision tree
- [[qt-harmonyos-project-structure]] — Project structure and the iron-rule checklist
- [[qt-harmonyos-platform-limits]] — How platform limitations affect Qt/QML/QPA + the QTBUG numbers
- [[qt-harmonyos-lifecycle]] — The Qt adapter for Stage/UIAbility and the Qt API reference
- [[qt-harmonyos-api-mapping]] — The API migration mapping tables
- [[qt-harmonyos-code-patterns]] — 14 before/after code patterns
- [[qt-harmonyos-window-model]] — The window model in detail
- [[qt-ohos-extras]] — The QtOhosExtras module APIs
- [[qt-harmonyos-build]] — The build guide
- [[qt-harmonyos-third-party-libs]] — The guide to porting third-party libraries
- [[qt-harmonyos-qt6-status]] — Qt 6 HarmonyOS porting status
- [[platform-guard-needs-both-ohos-macros]] — Dual macros for platform guards and how to determine the branch taken
- [[platform-layer-two-dispatch-modes]] — The two dispatch mechanisms of the platform layer and how to audit them
