---
id: semantic-qt-harmonyos-porting-workflow
type: semantic
domain: tech
tags: [qt, harmonyos, porting, workflow, decision-tree]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-api, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-modules, semantic-qt-ohos-extras]
summary: >
  HarmonyOS porting orchestration for Qt applications: an 8-step adaptation process mapping the common library's lifecycle,
  window model, and platform limitations onto Qt/QPA, QtOhosExtras, the build system, and module acceptance.
---

# The 8-step decision-tree workflow for porting Qt to HarmonyOS

This page is the **process hub for the Qt adaptation layer**; it doesn't duplicate the HarmonyOS platform specification. Before you start porting, treat these pages in the common knowledge base as the canonical source of facts:

- The Stage/UIAbility lifecycle: [[ohos-common-kb/semantic/stage-uiability-lifecycle|common: the Stage/UIAbility lifecycle]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md))
- The ArkUI window and XComponent model: [[ohos-common-kb/semantic/arkui-window-xcomponent-model|common: the ArkUI window and XComponent model]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/arkui-window-xcomponent-model.md))
- HarmonyOS platform limitations: [[ohos-common-kb/semantic/harmonyos-platform-limits|common: HarmonyOS platform limitations]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md))

What follows only answers how those common constraints map onto Qt applications, the QPA plugin, and QtOhosExtras.

## Five core principles

Before you start porting, internalize these five things — they run through the whole process:

### Principle 1: explicitly audit Qt's Linux compatibility branches

`Q_OS_OHOS` overlaps with some Linux conditions, so `#ifdef Q_OS_LINUX` may be taken in a HarmonyOS build. Audit each of those branches, leave conclusions about platform capabilities to the common platform limitations page, and record on the Qt side only the classes, call sites, and build conditions that need replacing.

### Principle 2: distinguish the Qt event loop from the ArkUI runtime

The Qt event loop, the QPA platform plugin, and the ArkUI/Ability runtime each have their own threading and callback constraints. Don't lump every cross-boundary call together as "N-API"; prefer the interfaces QtOhosExtras or the QPA already wrap, and make thread ownership and dispatch explicit wherever you write a custom bridge.

### Principle 3: map Stage/UIAbility events onto the Qt lifecycle

A Qt application still enters through `main()`, but its creation, foreground/background transitions, Want delivery, and destruction are carried by Stage/UIAbility. Understand the common lifecycle first, then decide how Qt signals, `closeEvent()`, and QtOhosExtras callbacks should respond; don't explain every scenario with a single "process startup" model.

### Principle 4: explicitly maintain the QWindow → system window mapping

The common window model defines the system-side constraints; the Qt adaptation is about how the first `QWindow`, subsequent top-level windows, `transientParent`, and subwindow tagging get mapped onto that model by the QPA, and about the ordering around `show()` / `winId()`.

### Principle 5: make Qt file and plugin paths obey the sandbox

Audit `QFile`, `QStandardPaths`, `QPluginLoader`, and third-party library load paths against the common platform limitations page. The Qt pages only maintain how those limitations manifest in the Qt APIs, the alternative interfaces, and the acceptance method.

---

## Step 1: scan for platform-specific code

Search the whole application codebase for the patterns below to build a complete porting inventory.

### Platform macros

Search for every platform conditional-compilation macro:

```
Q_OS_WIN
Q_OS_LINUX
Q_OS_ANDROID
Q_OS_MAC / Q_OS_MACOS / Q_OS_DARWIN
```

> Note: `Q_OS_LINUX` is also matched on HarmonyOS (because `Q_OS_OHOS` implies `Q_OS_LINUX`), so you need to check whether the code in every `Q_OS_LINUX` branch is HarmonyOS-compatible.

### Platform-specific APIs

The APIs below behave differently or are unavailable on HarmonyOS, so check each one:

```
QProcess                        — Process management (fine when headless; with a UI, switch to startAppProcess/startAbility depending on Qt vs non-Qt)
QDesktopServices                — Desktop services (openUrl and so on)
QFileDialog                     — The native file dialog
QSystemTrayIcon                 — The system tray icon
QClipboard                      — The clipboard
setMask()                       — Window masks (only effective on subwindows)
showFullScreen()                — Fullscreen (with ordering requirements)
showMinimized()                 — Minimizing (unsupported for subwindows)
chmod() / fchmod()              — Changing permissions (unsupported)
symlink()                       — Symbolic links (unavailable to third-party applications)
dlopen()                        — Dynamic loading (rejects writable paths)
QStandardPaths                  — Standard paths (some locations return empty)
```

### Platform branches in the build configuration

```qmake
# Platform conditional blocks in a .pro file
win32 { ... }
unix { ... }
android { ... }
macx { ... }
```

```cmake
# Platform conditionals in CMake
if(WIN32) ...
if(UNIX AND NOT APPLE) ...
if(ANDROID) ...
```

> **Step 1 output**: a complete list of every code location that needs replacing or adapting.

---

## Step 2: replace APIs using the mapping

For each platform pattern found in step 1, apply the mappings below:

### Process management

> For the four-scenario decision tree (keep QProcess when headless / use startAppProcess for a Qt UI / use startAbility for a non-Qt UI / use startNoUiChildProcess for supervised headless work), see [[qt-harmonyos-api-mapping]] §1 Process management.

### Services and interaction

| Source pattern | HarmonyOS alternative |
|----------------|-----------------------|
| `QDesktopServices::openUrl()` | `QtOhosExtras::startAbility()` with a Want URI |
| A standalone `QDialog` / `QPopup` (with no parent) | Tag it with `QOhosFunctions::tagWindowOrWidgetAsSubWindowOf()` |

### Windows

| Source pattern | HarmonyOS alternative |
|----------------|-----------------------|
| `showFullScreen()` on the first window | Must be called **after** the window has been created and shown |
| `QFile::setPermissions()` | Unsupported (a silent no-op for existing files) |
| `QFile::link()` / `symlink()` | Unavailable to third-party applications |

### Paths and arguments

| Source pattern | HarmonyOS alternative |
|----------------|-----------------------|
| `QStandardPaths::PublicShareLocation` | Returns an empty string; unsupported |
| Using `argv[0]` as an executable path | ❌ On OHOS, `argv[0]` is the **library path** (a .so path), not an executable path |
| `closeEvent()` assuming a user click | You must use `QtOhosExtras::getCloseEventRootCause(event)` to distinguish where the close came from |

> For the full API differences, see [[qt-harmonyos-api]]; for QtOhosExtras usage, see [[qt-ohos-extras]].

---

## Step 3: adapt window management

Using the common ArkUI window model as the baseline, confirm one by one how the QPA maps a `QWindow`/`QWidget` onto a system main window or subwindow; this step only records the Qt-side binding and call ordering.

### Window binding rules

- The **first** `QWindow` / `QWidget` (a parentless top-level window) binds automatically to the system's first main window
- **Subsequent** top-level windows become **new main windows** by default, unless tagged as subwindows
- A `QDialog` with a `transientParent` set works correctly without manual tagging

### The key operation: tagging a subwindow

```cpp
#include <QtPlatformHeaders/QOhosFunctions>

// ⚠️ Must be called before show() or winId()!
QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(
    widget,
    mainWindow->windowHandle()
);
```

> **The ordering is a hard requirement**: `tagWindowOrWidgetAsSubWindowOf()` must be called before `show()` and `winId()`, or the tag has no effect.

### Window limitation checklist

| Limitation | Notes |
|------------|-------|
| `setMask()` only works on subwindows | Calling `setMask()` on the main window does nothing |
| Subwindows can't be minimized | Calling `showMinimized()` on a subwindow does nothing |
| The first main window can't start fullscreen | Create and show the window first, then call `showFullScreen()` |
| `hide()` on the main window falls back to minimizing | Without a system tray, `hide()` actually minimizes |

---

## Step 4: adapt the application lifecycle

Confirm the system events against the common Stage/UIAbility lifecycle first, then map them onto Qt's entry point, signals, and close handling. What follows is the Qt adaptation, not a copy of the lifecycle specification.

### Entry point and launch

- `main()` is still the application's entry point, but the semantics differ — application launch is managed by the system's Ability framework
- Use `QtOhosExtras::startAbility()` instead of traditional process launching
- Don't rely on `argv[0]` for the executable path (on OHOS it's the library path)

### Cross-application communication

Handle the `newWantReceived` callback for inter-application communication, replacing traditional IPC.

### Close event handling

`closeEvent()` can come from several sources (a user click, Ability lifecycle termination, a WindowStage close), so you must check the root cause. See [[qt-harmonyos-lifecycle]] §the three levels of close interception (distinguishing WindowStageClose / AbilityClose / InternalClose).

### Optional: cross-device continuation

```cpp
// Get the continuation data
auto data = QtOhosExtras::tryGetOnContinueData(want);

// Listen for cross-device continuation requests
connect(abilityContext, &QOhosAbilityContext::continueRequestReceived,
        this, &MyApp::onContinueRequest);
```

---

## Step 5: check how platform limitations affect Qt

The common platform limitations page maintains the limitations themselves and their evidence; here we only keep the Qt API impact checks, to decide whether a feature needs wrapping, replacing, or dropping:

| Qt area to check | What to do at this stage | Pass condition |
|------------------|--------------------------|----------------|
| `QFile` / `QFileInfo` | List every permission-change, link-creation, and system-path-probe call, and check each against the common platform limitations | Nothing relies on unverified POSIX file semantics |
| `QLibrary` / `QPluginLoader` | Record where each native artifact is packaged and how it's loaded, checked against the common loader/sandbox contract | Plugins only load from accepted delivery locations |
| `QTimeZone` | Run time zone enumeration and conversion regressions on the target device; the backend choice is driven by the common capability conclusions | The time zone cases you need pass on the target device |
| `QFontDatabase` | Enumerate the font families the application actually needs; where they're missing, ship your own fonts as Qt resources | The UI doesn't depend on undeclared platform font directories |
| The native dependency closure | Run the common artifact checks on every ELF in the final HAP, then verify the Qt target's `DT_NEEDED` | The ABI, dependency, and load verifications all pass |

> For the Qt-side compatibility symptoms and QTBUG tracking, see [[qt-harmonyos-platform-limits]]; for the canonical facts about platform limitations, defer to the common pages linked at the top of this page.

---

## Step 6: adapt the build system

### qmake (.pro files)

```qmake
ohos {
    QT += ohosextras
    # OHOS-specific sources and libraries
}
```

### CMake

```cmake
if(OHOS)
    find_package(Qt5 COMPONENTS OhosExtras REQUIRED)
    target_link_libraries(${PROJECT_NAME} Qt5::OhosExtras)
endif()
```

> ⚠️ **Whenever you use any OHOS-specific API, you must add `QT += ohosextras` (qmake) or `find_package(Qt5 COMPONENTS OhosExtras)` (CMake).**

---

## Step 7: add OHOS-specific features (optional)

Once the basic port is done, you can optionally enhance it with HarmonyOS-specific capabilities:

| Feature | API | When to call it |
|---------|-----|-----------------|
| Floating windows | `QtOhosExtras::setShowWindowAsFloatWindowHint(widget, true)` | Before `show()` |
| Following the dark/light theme | `QOhosAppContext::setColorThemeMode(FollowSystemSetting)` | At application initialization |
| Application sharing | `QtOhosExtras::ShareKit::shareDataWithShareKit()` | When the user triggers sharing |
| Cross-device continuation | The `QOhosAbilityContext::continueRequestReceived` signal | As needed |
| Fullscreen (for the 2nd+ window) | `widget->showFullScreen()` | After the window is created |
| Embedding a subwindow in-process | `winId()` or setting the `Qt::WA_NativeWindow` attribute | Embedding scenarios |
| Cross-process embedding | `QEmbeddedUiExtensionAbility` | Embedding scenarios |

### Theme adaptation example

```cpp
auto *ctx = QtOhosExtras::QOhosAppContext::instance();
ctx->setColorThemeMode(QtOhosExtras::QOhosAppContext::ColorThemeMode::FollowSystemSetting);

// Query whether dark mode is currently active
bool isDark = ctx->darkThemeActive();
```

### Sharing example

```cpp
auto record = QtOhosExtras::ShareKit::createContentRecord(mimeType, text);
auto ability = QtOhosExtras::QOhosAbilityContext::getInstanceForMainWindow(
    window.windowHandle()
);
ability->shareDataWithShareKit({record}, nullptr);
```

> See [[qt-ohos-extras]] for details.

---

## Step 8: verify module support

Confirm that every Qt module your application uses is supported on OHOS.

### Core modules — all supported ✅

```
QtCore, QtGui, QtWidgets, QtQML, QtQuick, QtQuickControls,
QtNetwork, QtSQL, QtMultimedia
```

### Unsupported modules — you need alternatives ❌

| Module | Notes | Alternative |
|--------|-------|-------------|
| **Qt WebEngine** | Unsupported | Use the system WebView or open an external browser |
| **Qt D-Bus** | HarmonyOS has no D-Bus | Use HarmonyOS's IPC mechanisms |
| **Qt Remote Objects** | Out of scope | — |
| **Qt Serial Bus** | Windows/Linux-only | — |
| **Qt Virtual Keyboard** | Out of scope | Use the system input method |
| **Active Qt** | Windows-only | Not applicable |
| **Qt Win Extras / X11 Extras / Mac Extras** | Platform-specific | Not applicable |

### Partially supported

- **Qt PDF** — Qt 5.15 only
- **Qt Quick Timeline** — Qt 5.15 only

> For the complete module porting status table, see [[qt-harmonyos-modules]].

---

## Important reminders

These are the 8 rules most often tripped over during porting; check them repeatedly:

1. **`QT += ohosextras` is mandatory** — whenever you use any OHOS-specific API, the build system must include the ohosextras module
2. **The window tagging function must be called before `show()` / `winId()`** — calling it later has no effect and the window is already bound incorrectly
3. **`argv[0]` is the library path, not an executable path** — don't use `argv[0]` to build resource paths or launch child processes
4. **Drag-and-drop: only read the actual data in `dropEvent`** — `dragEnterEvent` and `dragMoveEvent` only have MIME type information; the data is only available in `dropEvent`
5. **The first main window can't start fullscreen** — create and show the window first, then call `showFullScreen()`
6. **`hide()` on the main window falls back to minimizing** — without a system tray, `hide()` doesn't actually hide the window
7. **Subwindows can't be minimized** — calling `showMinimized()` on a subwindow does nothing
8. **Choose your child-process mechanism by scenario** (corrected 2026-07-21) — headless can use `QProcess`; a Qt UI uses `startAppProcess()`, a non-Qt UI uses `startAbility()`; supervised headless work uses `startNoUiChildProcess()`. Don't use a bare QProcess to start a child process with a UI

---

## Porting completion checklist

The final confirmation after the 8 steps:

- [ ] Every `Q_OS_*` macro branch handles `Q_OS_OHOS`
- [ ] Child processes are handled per scenario: keep `QProcess` when headless / `startAppProcess` for a Qt UI / `startAbility` for a non-Qt UI / `startNoUiChildProcess` when supervision is needed
- [ ] Every parentless top-level window is tagged as a subwindow (using `tagWindowOrWidgetAsSubWindowOf`)
- [ ] The window tagging function is called before `show()` / `winId()`
- [ ] `closeEvent()` handles Ability/WindowStage-level closes via `getCloseEventRootCause()`
- [ ] Nothing relies on `chmod()`, `symlink()`, or `dlopen()` from a writable path
- [ ] The `.pro` / CMake files have the `ohos` condition and `QT += ohosextras`
- [ ] Every Qt module the application uses is supported on OHOS
- [ ] `argv[0]` isn't used as an executable path
- [ ] Drag-and-drop data is only read in `dropEvent`
- [ ] The first main window doesn't start fullscreen
- [ ] The main window's `hide()` behavior has been verified (it falls back to minimizing)

---

## Related

- [[ohos-common-kb/semantic/stage-uiability-lifecycle|common: the Stage/UIAbility lifecycle]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/stage-uiability-lifecycle.md))
- [[ohos-common-kb/semantic/arkui-window-xcomponent-model|common: the ArkUI window and XComponent model]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/arkui-window-xcomponent-model.md))
- [[ohos-common-kb/semantic/harmonyos-platform-limits|common: HarmonyOS platform limitations]] ([stable link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md))
- [[qt-harmonyos-api]] — API compatibility details
- [[qt-harmonyos-platform-limits]] — Platform limitations and QTBUG numbers
- [[qt-harmonyos-modules]] — The module porting status table
- [[qt-ohos-extras]] — The QtOhosExtras module API reference

## References

- Qt Application Porting to HarmonyOS (SKILL.md) — The agent skill's decision-tree workflow definition
- [Qt for HarmonyOS Wiki](https://wiki.qt.io/Qt_for_HarmonyOS)
- [API Compatibility Notes](https://wiki.qt.io/Qt_for_HarmonyOS/api_inconsistencies_on_harmonyos)
- [User Development Guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide)
