---
id: semantic-qt-ohos-extras
type: semantic
domain: tech
tags: [qt, harmonyos, ohos, ohosextras, ability, want, startability, context-menu, touch, long-press, window, cornerradius, permissions, share, fileshare, continuation, multimedia, startoptions, serialport, startrequest, nativewindow, colortheme]
created: 2026-06-02
updated: 2026-07-21
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-api, semantic-qt-ohos-js-thread-gateway, semantic-qt-harmonyos-lifecycle, semantic-qt-harmonyos-qt6-status, semantic-qt-harmonyos-window-model, semantic-qt-ohos-extras-examples]
summary: >
  The QtOhosExtras module: the bridge between Qt and the HarmonyOS system. Qt5 exposes 145+ public APIs (completed by a full source scan on 2026-07-15; only ~9 had been recorded before).
  It covers: windows (setWindowCornerRadius/tryGetNativeWindowId/setShowWindowAsFloatWindowHint/privacy mode/keep-awake/drag-resizing),
  launching abilities (startAbility/startAbilityForResult★async/startAppProcess/startNoUiChildProcess/startAbilityByType),
  permission requests, system sharing (ShareKit), file sharing (FileShare), cross-device continuation, launch options (QOhosStartOptions),
  Want/WantInfo, and clipboard/file/multimedia utilities. Usage: QT += ohosextras. It's private in Qt6.
---

# The QtOhosExtras module

## Overview

QtOhosExtras is Qt for HarmonyOS's proprietary extension module, providing the APIs for interacting with the HarmonyOS system.

> **Completed by a full scan on 2026-07-15**: a complete scan of every public header under `qtohosextras/src/ohosextras/` in the source found **145+** public APIs (including `qohoswindowutils.h`). The knowledge base had previously recorded only ~9 — missing over 90% — including several misleading errors (see the ⚠️ notes in each section and "Historical errors corrected" at the end).
>
> **Versions**: these are all Qt5 public APIs. The `qtohosextras` headers in Qt 5.12.12 (commit `613336de`) and 5.15.16 (commit `962aa625`) are **identical word for word**, so every API on this page exists in both. In Qt6, QtOhosExtras is no longer standalone and the APIs are private (`_p.h`) with no public equivalent (see [[qt-harmonyos-qt6-status]]).

## Usage

```cpp
#include <QtOhosExtras>          // the module-level umbrella header (recommended), or a sub-header such as <QtOhosExtras/qohoswindowutils.h>
// In the project file (.pro):  QT += ohosextras
// CMake:                       find_package(Qt5 REQUIRED COMPONENTS OhosExtras)
//                              target_link_libraries(... Qt5::OhosExtras)
```

## The core APIs

### Windows (`qohoswindowutils.h`, free functions in the `QtOhosExtras` namespace)

> ⚠️ This section used to be badly incomplete: before 2026-07-15 only 2 APIs were recorded and 11 were missing (including `setWindowCornerRadius`) — which directly led to the wrong answer that "QtOhosExtras has no window corner radius interface".

**Enums**:
- `enum class CloseEventRootCause { InternalClose, AbilityClose, WindowStageClose }` — the root cause of a close event
- `enum class WindowGeometryPersistenceHint { Disabled, Enabled, FollowSystemSetting }` — the main window's geometry persistence policy

**Functions** (those marked "overloaded" have a `QWindow*` and a `QWidget*` version):

| Function | Purpose |
|----------|---------|
| `getCloseEventRootCause(QCloseEvent*)` → `CloseEventRootCause` | Query a close event's root cause |
| `setShowWindowAsFloatWindowHint(QWindow*/QWidget*, bool)` (overloaded) | Switch it to floating window mode (used by the floating window demo; see [[qt-harmonyos-window-model]] §Floating windows) |
| `setMainWindowGeometryPersistenceHint(WindowGeometryPersistenceHint)` | Main window geometry persistence (2-in-1 only) |
| `setWindowPrivacyMode(QWindow*, bool)` | Window privacy mode (screenshot blocking) |
| `setSurfaceBackgroundColor(QWindow*/QWidget*, const QColor&)` (overloaded) | Set the window surface's background color |
| **`setWindowCornerRadius(QWindow*/QWidget*, double radius)`** (overloaded) | ★ **Set the window's corner radius** (an extras wrapper around HarmonyOS's system window corner radius; the official demo is `windowcornerradius`) |
| `setWindowKeepScreenOn(QWindow*/QWidget*, bool)` (overloaded) | Keep the screen on |
| `setWindowDragResizable(QWindow*/QWidget*, bool)` (overloaded) | Toggle drag-resizing |
| `tryGetNativeWindowId(QWindow*)` → `QSharedPointer<double>` | The ArkTS-side WindowProperties.id (not guaranteed valid for the process's lifetime) |
| `tryGetScreenDisplayId(QScreen*)` → `QSharedPointer<double>` | The screen's display id |
| `setBundledAbilityAndQWindowBindingKeyForQWindow(QWindow*, const QString&)` | Bind an Ability-QWindow key |

> **Using `setWindowCornerRadius`** (the official demo `qtohosextras/examples/qtohosextras/windowcornerradius/main.cpp`):
> ```cpp
> auto *w = new QWidget; w->setWindowFlags(Qt::Window); w->resize(300, 300);
> QtOhosExtras::setWindowCornerRadius(w, 16.0);   // a double; the official example calls it before show()
> w->show();
> ```
> It acts on the HarmonyOS window corresponding to the `QWindow`/`QWidget`; for short-lived popups (QMenu/dropdowns) it must be called after the window is created but before `show()`, and the exact timing needs verifying with a demo.

### Launching abilities and contexts (`qohosabilitycontext.h`)

> ⚠️ **A historical error corrected**: this page used to claim there was "no `startAbilityForResult`". The source at `qohosabilitycontext.h:79-80` **clearly provides** two `QOhosAbilityContext::startAbilityForResult` overloads (asynchronous, returning a `requestId`, with the result delivered by signal). You only need [[qt-ohos-js-thread-gateway]]'s `evalWithPromise` to make it **synchronously blocking** (QtOhosExtras has no blocking variant — see "Historical errors corrected" at the end).

> **Choosing a child-process mechanism**: there's no one-size-fits-all way to start a child process (`QProcess`/`startAppProcess()`/`startAbility()`/`startNoUiChildProcess()` each have their place); for the decision tree, see [[qt-harmonyos-api-mapping]] §1.

**Namespace-level free functions**:

| Function | Purpose |
|----------|---------|
| `startAbility(const QOhosWant&)` → `QSharedPointer<QOhosOperationStatus>` | Launch the specified Ability (fire-and-forget) |
| `startAbility(const QOhosWant&, const QOhosStartOptions&)` | Launch an Ability with StartOptions |
| `startAbilityByType(const QString &appType, const QJsonObject &wantParameters)` | Launch by application type (an implicit Want) |
| `startNewAbilityInstance(QWidget *instanceWidget)` | Launch a new Ability instance |
| `startAppProcess(const QString &processId, const QOhosWant &requestWant)` | Launch an application process |
| `startAppProcess(..., const QOhosStartOptions &options)` | Launch an application process with options |
| `setAbilityInstanceDestroyEnabled(QWindow*, bool)` | Set whether the system may destroy a given Ability instance's window |
| `tryGetOnContinueData(const QOhosWant&)` → `QSharedPointer<QByteArray>` | Get cross-device continuation data from a Want |

**`QOhosAbilityContext` class methods** (inherits QObject, with an `instance()` singleton):

| Method | Purpose |
|--------|---------|
| `static instance()` / `getDefaultInstance()` | The singleton / the default instance (a shared pointer) |
| `static getInstanceForMainWindow(QWindow*)` | Get the instance for a given main window |
| `setDestroyFromSystemEnabled(bool)` | Whether the system may destroy this Ability instance |
| `requestPermissionFromUserIfNeeded(Permission)` / `(const QString&)` | Request a permission from the user if needed (by enum/by name) |
| `requestPermissionOnSettingIfNeeded(Permission)` / `(const QString&)` | Request a permission via the settings page if needed |
| ★ `startAbilityForResult(const QOhosWant&)` → `QByteArray` | Launch an Ability and wait **asynchronously** for the result (returns a requestId) |
| ★ `startAbilityForResult(const QOhosWant&, const QOhosStartOptions&)` | The same with StartOptions |
| `shareDataWithShareKit(records, controllerOptions)` | Share data through the ShareKit system sheet |
| `tryOpenLink(const QString&)` / `(..., const QOhosOpenLinkOptions&)` | Open a link with the system (optionally with options) |
| `setContinuationActive(bool)` | Set the cross-device continuation active state |

**`QOhosAbilityContext` signals** (the entry points for asynchronous results):

| Signal | Purpose |
|--------|---------|
| `newWantReceived(QOhosWant)` / `newWantInfoReceived(QSharedPointer<QOhosWantInfo>)` | A new Want/WantInfo arrived |
| `continueRequestReceived(QSharedPointer<QOhosOnContinueContext>)` | A cross-device continuation request arrived |
| `permissionRequestResponseReceived(Permission, PermissionResult)` / `namedPermissionRequestResponseReceived(...)` | A permission request response |
| `permissionRequestOnSettingResponseReceived(Permission, bool)` / `named...` | A settings-page permission response |
| ★ `startAbilityForResultResponseReceived(requestId, resultCode, optWant)` | A successful `startAbilityForResult` response |
| ★ `startAbilityForResultErrorResponseReceived(requestId)` | A `startAbilityForResult` error response |
| `shareKitPanelClosed(requestId)` / `shareKitCompleted(requestId, result)` | The ShareKit sheet closed / the share completed |

> **Link-opening helpers**: the `createOpenLinkOptions()` factory + `QOhosOpenLinkOptions::setAppLinkingOnly(bool)` (open only via app linking, not the browser).

### The application context `QOhosAppContext` (`qohosappcontext.h`, a singleton)

| Method | Purpose |
|--------|---------|
| `static instance()` | The AppContext singleton |
| `static isNoUiChildMode()` | Whether we're currently in UI-less child process mode |
| `static startNoUiChildProcess(QString libraryName, QStringList args)` | Start a UI-less background child process (by library name + arguments) |
| `static getAppLaunchWant()` / `getAppLaunchWantInfo()` | The Want / WantInfo the application was launched with (essential for continuation/deep links) |
| `isPermissionGranted(Permission)` / `(const QString&)` | Query whether a permission has been granted |
| `requestPermissionFromUserIfNeeded(Permission)` / `requestPermissionOnSettingIfNeeded(Permission)` | Request a permission if needed |
| `fontSizeScale()` | The system's font size scale factor |
| `darkThemeActive()` / `setColorThemeMode(ColorThemeMode)` | Query/set the dark theme |
| `enableContextMenuEventOnLongPress()` | Enable a touch long press to produce a `QContextMenuEvent` (by default only a right click does) |
| `getBundleInfo()` → `QSharedPointer<QOhosBundleInfo>` | The application's bundle information |
| `restartApp()` / `restartApp(const QOhosWant&)` | Restart the application (`Q_NORETURN`) |
| `hasSerialPortAccessRight(const QString &portName)` / `requestSerialPortAccessRightIfNeeded(const QString &portName)` | ★ Query/request serial port access permission (source: `qohosappcontext.h:53-54`; the official demo is `serialportpermissions`, with `QT += serialport`) |

**Enum**: `enum class ColorThemeMode { LightTheme, DarkTheme, FollowSystemSetting }`
**Signals**: `permissionRequestResponseReceived` / `...WithResultReceived` / `...OnSettingResponseReceived` / `fontSizeScaleChanged(double)` / `darkThemeActiveChanged(bool)` / ★ `serialPortAccessRightResponseReceived(QString portName, QSharedPointer<QObject> accessRightContext)`

> ⚠️ **A serial port permission constraint** (the official demo `serialportpermissions`): the `accessRightContext` must be kept alive — destroying it revokes the permission (the example stores it as a `PermissionWindow` member, so closing the window revokes it). `QSerialPort` requires `QT += serialport`.

> ⚠️ **Notes on `enableContextMenuEventOnLongPress`** (source: `qohosappcontext.cpp:501-513`):
> - **When to call it**: once, before `app.exec()`; it applies globally (not per widget).
> - **The trigger reason is `Other`**: a `QContextMenuEvent` produced by a long press has `reason()` == `Other`, **not** `Mouse`. If you filter by reason, you must also accept `Other`.
> - **Qt5 only**: this API is private in Qt6 with no public equivalent.

### Launch options: `QOhosStartOptions` (`qohosstartoptions.h`)

> The core of multi-window/split-screen/splash configuration, used heavily when porting applications. This whole block used to be missing.

**Factories**: `createStartOptions()` → `QSharedPointer<QOhosStartOptions>`; `createWindowCreateParams()` → `QSharedPointer<QOhosWindowCreateParams>`

**`QOhosStartOptions` setters**:

| Group | Setters |
|-------|---------|
| Window geometry | `setWindowLeft/Top/Width/Height(int)` |
| Window bounds | `setMinWindowWidth/Height`, `setMaxWindowWidth/Height` |
| Window mode | `setWindowMode(WindowMode)`, `setSupportWindowModes(QList<SupportWindowMode>)` |
| Display | `setDisplayId(int)` |
| Animation/visibility | `setWithAnimation(bool)`, `setStartupVisibility(StartupVisibility)`, `setHideStartWindow(bool)` |
| Process | `setProcessMode(ProcessMode)` |
| The splash screen | `setStartWindowIcon(QImage)`, `setStartWindowBackgroundColor(QColor)` |
| Window creation parameters | `setWindowCreateParams(QOhosWindowCreateParams)` |
| ⚠️ Deprecated | `setWindowFocused(bool)` (`QT_DEPRECATED_X`, no effect) |

**`QOhosWindowCreateParams`**: `setAnimationType(AnimationType)`, with `enum class AnimationType { FADE_IN_OUT = 0 }`

**Enums**:
- `QOhosStartOptions::ProcessMode { NEW_PROCESS_ATTACH_TO_PARENT, NEW_PROCESS_ATTACH_TO_STATUS_BAR_ITEM }`
- `QOhosStartOptions::StartupVisibility { STARTUP_HIDE, STARTUP_SHOW }`
- `QOhosStartOptions::WindowMode { WINDOW_MODE_SPLIT_PRIMARY, WINDOW_MODE_SPLIT_SECONDARY, WINDOW_MODE_FULLSCREEN }`
- `QOhosStartOptions::SupportWindowMode { FULL_SCREEN, SPLIT, FLOATING }`

### Launch requests: `QOhosStartRequest` (`qohosstartrequest.h`, `qohosbundlemanager.h`)

> ⚠️ **Added 2026-07-21 when the examples were surveyed**: the older KB didn't record this. Source headers: `qohosstartrequest.h` + `qohosbundlemanager.h`; demonstrated by the official demo `abilitycontext/startoptions`.

**The factory**: `QtOhosExtras::createStartRequest(const QOhosStartOptions &options)` → `QSharedPointer<QOhosStartRequest>`

**The `QOhosStartRequest` class** (a QObject that can't be constructed directly — use the factory):

| Signal | Purpose |
|--------|---------|
| `requestSucceeded(QOhosElementName elementName, QString message)` | The launch-succeeded callback (a completion handler) |
| `requestFailed(QOhosElementName elementName, QString message)` | The launch-failed callback |

**The `QOhosElementName` struct** (`qohosbundlemanager.h`, `Q_DECLARE_METATYPE`): `deviceId / bundleName / abilityName / uri / shortName / moduleName`

**The matching `startAbility` / `startAbilityForResult` overloads** (namespace-level and `QOhosAbilityContext` methods, all taking a `QOhosStartRequest`):
- `startAbility(const QOhosWant&, const QOhosStartRequest&)` — launching with a completion callback
- `QOhosAbilityContext::startAbilityForResult(const QOhosWant&, const QOhosStartRequest&)` — launching for a result with a callback
- `startAppProcess(processId, requestWant, const QOhosStartRequest&)` — launching an application process with a callback

> **When to use StartRequest**: a plain `startAbility(want, startOptions)` is fire-and-forget (you only learn `operationStatus->success()`). To get the launch's final result (success/failure + the ElementName), use `createStartRequest` + `startAbility(want, *startRequest)` and receive the result through the `requestSucceeded`/`requestFailed` signals. For usage, see [[qt-ohos-extras-examples]] §4.

### Want / WantInfo (`qohoswant.h`)

**The `QOhosWant` struct** (the C++ mapping of HarmonyOS's Want): `deviceId / bundleName / moduleName / abilityName / uri / type / action / entities / flags / parameters / fds`
- `enum class QOhosWantFlag { AuthReadUriPermission, AuthWriteUriPermission, InstallOnDemand }` (combinable as QFlags)

**`QOhosWantInfo` accessors** (pure virtual members):

| Method | Purpose |
|--------|---------|
| `want() const` → `QOhosWant` | Get the complete Want |
| `tryGetSharedRecordsFromShareKit() const` | Get the share records passed in through ShareKit |
| `tryGetContactInfo() const` → `ContactInfo` | Get the contact information carried in the Want |
| `launchReason() const` → `LaunchReason` | Why the application was launched |

- `enum class LaunchReason { Unknown, StartAbility, Continuation, PrepareContinuation, Preload }`
- `struct ContactInfo { QString contactType; QString contactId; }`

### System sharing: ShareKit (`qohossharekit.h`, the `ShareKit` namespace)

**Factories**: `createContentRecord(QMimeType, QString content)` / `createFileRecord(QFileInfo)` / `createUrlRecord(QUrl)` / `createControllerOptions()` — all returning a `QSharedPointer<...>`

**`QOhosSharedRecord`** getters/setters (16 of them): `mimeType/content/filePath/isUrlContent` (read-only); `setTitle/title`, `setLabel/label`, `setDescription/description`, `setThumbnail/thumbnail` (a QByteArray), `setThumbnailFilePath/thumbnailFilePath`, `setExtraData/extraData` (a QVariantMap)

**`QOhosShareControllerOptions`**: `setAnchor(QPoint)` / `setAnchor(QRect)`, `setSingleSelectionMode(bool)`, `setDefaultPreviewMode(bool)`, `setExcludedAbilities(QList<ShareAbilityType>)`
**`QOhosShareOperationResult`**: `targetAbilityName() const`
**Enum**: `enum class ShareAbilityType { CopyToPasteboard, SaveToMediaAsset, SaveAsFile, Print, SaveToSuperHub }`

> The entry point: `QOhosAbilityContext::shareDataWithShareKit(records, options)`, with completion delivered through the `shareKitCompleted` signal.

### File sharing: FileShare (`qohosfileshare.h`, the `FileShare` namespace)

The official route to authorizing access to files outside the sandbox. These are batch operations, all returning a `QSharedPointer<ActionResult>` / `QSharedPointer<CheckResult>`.

| Function | Purpose |
|----------|---------|
| `persistPermission(QList<PathPolicy>)` | Persist file-sharing permissions |
| `revokePermission(QList<PathPolicy>)` | Revoke permissions |
| `activatePermission(QList<PathPolicy>)` | Activate already-persisted permissions |
| `deactivatePermission(QList<PathPolicy>)` | Deactivate permissions |
| `checkPersistent(QList<PathPolicy>)` | Check the persistence state |

- `enum class OperationMode { Read=1<<0, Write=1<<1 }` (combinable as QFlags)
- `enum class PathPolicyError { Unknown, PersistenceForbidden, InvalidMode, InvalidPath, PermissionNotPersisted }`
- `struct PathPolicy { QString path; OperationModes operationModes; }`
- `ActionResult::operationStatus()` / `errorInfoList()`; `CheckResult::checkResultList()`

### Permissions: AppPermissions (`qohosapppermissions.h`, the `AppPermissions` namespace)

- `enum class Permission { ReadPasteboard, CustomScreenCapture, AccessBluetooth, ApproximatelyLocation, Location }` — the 5 requestable permissions QtOhosExtras predefines
- `struct PermissionResult { bool permissionGranted; bool dialogShown; }`

> The entry points: `requestPermissionFromUserIfNeeded` / `requestPermissionOnSettingIfNeeded` on `QOhosAppContext` / `QOhosAbilityContext`, with results delivered through the `permissionRequestResponse*` signals.

### Cross-device continuation: `QOhosOnContinueContext`

| Method | Purpose |
|--------|---------|
| `setAgreeResponse(const QByteArray &responseData)` | Agree to the handoff, carrying the response data |
| `setRejectResponse()` | Refuse the handoff |
| `setMismatchResponse()` | A handoff-mismatch response |
| `setExitAppOnSourceDeviceAfterMigration(bool)` | Whether to exit the application on the source device after the handoff |
| `sourceApplicationVersionCode() const` | The source application's version code |

> The entry points: the `QOhosAbilityContext::continueRequestReceived` signal + `setContinuationActive`; `tryGetOnContinueData` retrieves the data. See [[qt-harmonyos-lifecycle]] for details.

### Utility functions

| Header / namespace | Function | Purpose |
|--------------------|----------|---------|
| `qohosfileutils.h` | `moveFileToTrash(const QString&)` → bool | Move a file to the recycle bin |
| `qohosfileutils.h` | `authorizeFilePath(QWindow*, const QString&)` → bool | Show the system authorization dialog to access a path outside the sandbox |
| `qohosmultimediautils.h`, `Multimedia` | `setAudioStreamUsageHintProperty(QObject*, AudioStreamUsageHint)` | Set the audio stream scenario for a QSoundEffect/QSound |
| `qohosmultimediautils.h` | `tryGetAudioStreamUsageHintProperty(QObject*, AudioStreamUsageHint*)` | Read the audio stream scenario property |
| `qohospasteboard.h`, `QOhosPasteboard` | `setInAppOnlyPasteboardShareOption(bool)` | Restrict clipboard content to in-app sharing only |

- `enum class AudioStreamUsageHint { Unknown, Music, VoiceCommunication, VoiceAssistant, Alarm, VoiceMessage, Ringtone, Notification, Accessibility, Movie, Game, Audiobook, Navigation, VideoCommunication }` (14 values, affecting the system volume category and interruption policy)

### Enums and types (`qohosenums.h`)

- `enum class ColorMode { COLOR_MODE_NOT_SET, COLOR_MODE_DARK, COLOR_MODE_LIGHT }` (in the namespace `QtOhos::enums::...::ConfigurationConstant`, corresponding to `@ohos.app.ability.ConfigurationConstant.ColorMode`)
- The `struct OhosEnumMeta<Enum>` template: provides an OHOS enum's fully qualified type name plus enumerator↔string mappings (bridging NAPI reflection); currently only specialized for `ColorMode`

### `QOhosBundleInfo` (`qohosappbundleinfo.h`)

- `versionCode() const` — the application's version code

> `QOhosUiAbilityContext` (`qohosuiabilitycontext.h`) is a type alias for `QOhosAbilityContext` with no new APIs.
> `QOhosOperationStatus::success() const` — whether an asynchronous operation (startAbility and friends) succeeded.

## ⚠️ Historical errors corrected (2026-07-15)

| The original error (the old KB) | The correction (verified in the source) |
|--------------------------------|------------------------------------------|
| "There's no `startAbilityForResult`; you have to go around it via [[qt-ohos-js-thread-gateway]]" | `QOhosAbilityContext::startAbilityForResult` **exists** (2 overloads, asynchronous, returning a `requestId`, with results delivered through the `startAbilityForResultResponseReceived` / `...Error...` signals). You only need the gateway's `evalWithPromise` to wait **synchronously** (QtOhosExtras has no blocking variant) |
| "QtOhosExtras has no window corner radius interface" | `QtOhosExtras::setWindowCornerRadius(QWindow*/QWidget*, double)` **exists** (see the windows section; the official demo is `windowcornerradius`) |
| Only 2 window-related APIs recorded | `qohoswindowutils.h` has 13 window APIs + 2 enums |
| Only ~9 APIs recorded across the whole page | There are 145+ public APIs (including whole blocks: StartOptions/ShareKit/FileShare/permissions/continuation/utilities) |

## API references

- [Qt OHOS Extras C++ Classes](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc/Qt_Ohos_Extras_C%2B%2B_Classes) (the class index page, which **has no function signatures** — this is exactly why we wrongly concluded "there's no corner radius interface"; to check a specific API you must read the source headers)
- [Qt OHOS Extras Examples](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc/Qt_Ohos_Extras_Examples)
- [Qt OHOS Extras Document](https://wiki.qt.io/Qt_for_HarmonyOS/qtohosextras_doc)

## References

| Source | Notes |
|--------|-------|
| 🛠️ Qt source | `qtohosextras/src/ohosextras/*.h` (5.15.16 commit `962aa625` + 5.12.12 commit `613336de`, identical word for word) — the full scan on 2026-07-15 |
| 🛠️ Qt source | `qtohosextras/examples/qtohosextras/windowcornerradius/main.cpp` — the official `setWindowCornerRadius` demo |
| 📦 Installed headers | `<LOCAL_PATH>/include/QtOhosExtras/` |
| 🛠️ Qt source examples | `qtohosextras/examples/qtohosextras/` (all 24 examples, surveyed 2026-07-21) — see [[qt-ohos-extras-examples]]; the serial port and StartRequest APIs were filled in from the examples |

## Related context

- [[qt-harmonyos-overview]] — An overview of the QPA plugin architecture
- [[qt-harmonyos-api]] — Platform differences (`winId()` vs. `tryGetNativeWindowId`)
- [[qt-ohos-extras-examples]] — ★ A recipe book for the 24 official examples (feature → API → code pattern); check this page first when a developer asks "how do I implement X"
- [[qt-ohos-js-thread-gateway]] — The private Qt↔ArkTS bridge; making `startAbilityForResult`'s result synchronous (an async signal → a synchronous wait)
- [[qt-harmonyos-lifecycle]] — Lifecycle, Want continuation, cross-device handoff
- [[qt-harmonyos-window-model]] — The window model (floating windows, popups, XComponent hosting)
- [[qt-harmonyos-qt6-status]] — This module is private in Qt6
