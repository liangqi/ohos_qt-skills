# Qt HarmonyOS Porting API Differences

> **Community edition**: `<YOUR_HOME>/code/gitcode/qt-sig` (module name `QtOhExtras`, naming prefixes `QOh`/`QOpenHarmony`, platform plugin key `openharmony`)
> **Official edition**: `<YOUR_HOME>/code/AiProject/qt-5.12.12/qt-harmonyos-src` (module name `QtOhosExtras`, naming prefix `QOhos`, platform plugin key `ohos`)
>
> This document compares how the two editions implement their interfaces for porting to HarmonyOS (OpenHarmony/HarmonyOS), covering the scope of implemented capabilities, API design paradigms, and architectural layers.

---

## Table of contents

1. [Overall architecture differences](#1-overall-architecture-differences)
2. [Naming convention differences](#2-naming-convention-differences)
3. [Extras module public API comparison](#3-extras-module-public-api-comparison)
4. [QPA platform plugin interface comparison](#4-qpa-platform-plugin-interface-comparison)
5. [Corelib kernel support interface comparison](#5-corelib-kernel-support-interface-comparison)
6. [Feature module plugin interface comparison](#6-feature-module-plugin-interface-comparison)
7. [Interface capabilities only in the community edition](#7-interface-capabilities-only-in-the-community-edition)
8. [Interface capabilities only in the official edition](#8-interface-capabilities-only-in-the-official-edition)
9. [API paradigm differences in shared interfaces](#9-api-paradigm-differences-in-shared-interfaces)
10. [Summary](#10-summary)

---

## 1. Overall architecture differences

| Dimension | Community edition (qt-sig) | Official edition (qt-5.12.12) |
|------|----------------|-------------------|
| **Qt base version** | Based on late Qt 5 / Qt 6 style (includes Qt 6 overrides such as `darkThemeEnabled`/`setThemeColorMode`) | Qt 5.12.12 |
| **Design paradigm** | Concrete classes + synchronous APIs + NAPI callbacks + direct calls to native C APIs | Abstract classes + factory functions + `QSharedPointer` + asynchronous signals + a JS/NAPI bridging abstraction layer |
| **Naming prefix** | `QOh` / `QOpenHarmony` / `QtOh` | `QOhos` / `QtOhos` / `QtOhosExtras` |
| **Extras module name** | `QtOhExtras` (`qtohextras`) | `QtOhosExtras` (`qtohosextras`) |
| **Export macro** | `Q_OPENHARMONYEXTRAS_EXPORT` | `Q_OHOS_EXTRAS_EXPORT` |
| **Platform plugin key** | `"openharmony"` | `"ohos"` |
| **NAPI dependency** | Public APIs depend directly on `QtNapi/napi.h` (e.g. `QAbilityResultReceiver::handleResult(Napi::Value&)`) | Public APIs hide NAPI completely (pure Qt abstractions) |
| **Central QPA interface** | No central interface; functionality is scattered across the `QtOh` namespace + the `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` abstractions | ✅ `QtOhos::QOhosQpaFunctions` — a unified interface of 60+ pure virtual functions |
| **Want parameter type** | `QVariantMap` | `QJsonObject` |
| **StartOptions** | Plain struct; public fields assigned directly | Abstract class; virtual setters + factory creation |
| **Permission requests** | Synchronous bool return / callback function | Asynchronous void + Qt signal notification |
| **Ability result return** | Callback class `QAbilityResultReceiver` (`Napi::Value` parameters) | Qt signal (`startAbilityForResultResponseReceived`) |
| **Error handling** | Enum error codes + output parameters | `QOhosOperationStatus` abstract object + `QSharedPointer` |
| **Window helpers** | Instance class `QOhWidgetHelper` (bound to a QWidget/QWindow) | Free functions in the `QOhosWindowUtils` namespace |
| **Window property system** | Identified by name strings (`windowName`/`parentWindowName`) | Type-safe property descriptors `QOhosPropertyDescriptor<T>` |
| **File sharing API** | Static methods + error codes + output parameters | Free functions in a namespace + `QSharedPointer<ActionResult>` |
| **Thread bridging** | Simple `runOnJsUIThreadNoWait/AndWait` wrappers + `uv_queue_work` templates | Full `QOhosJsThreadGateway` + `QOhosJsState` + `QOhosTaskPromise` chain tracking |
| **Smart pointers** | `QScopedPointer` | `std::unique_ptr` / `std::shared_ptr` |
| **License** | LGPL (iSoftStone, 2024-2025) | Qt Commercial / LGPL-3.0 / GPL |
| **Number of public headers** | 13 (including 1 private) | 22 public + 7 private |
| **Third-party libraries** | None bundled | Bundles fontconfig / libjpeg / libpng / openssl |
| **Deployment tool** | None | `openharmonydeployqt` |
| **DevEco template** | Simple EntryAbility | Full template including QAbility/QAbilityStage/embedded extensions/child processes/4 kinds of page nodes |
| **Feature modules** | Bluetooth (including GATT/LE/NFC) + location + sensors (9 kinds) + multimedia + WebView + printing + style | Bluetooth (basic) + location (including MapKit) + sensors (5 kinds) + multimedia + WebView + printing + style + TTS + serial port + network bearer |

---

## 2. Naming convention differences

### 2.1 Prefix mapping

| Community edition | Official edition | Notes |
|--------|--------|------|
| `openharmony` (directory/plugin name) | `ohos` (directory/plugin name) | Platform adaptation directory naming |
| `QtOhExtras` | `QtOhosExtras` | Extras module name |
| `QOh*` / `QOpenHarmony*` | `QOhos*` | Class name prefix |
| `QtOh::` | `QtOhosExtras::` / `QtOhos::` | Namespace |
| `Q_OPENHARMONYEXTRAS_EXPORT` | `Q_OHOS_EXTRAS_EXPORT` | Export macro |
| `qopenharmonyextrasglobal.h` | `qtohosextrasglobal.h` | Global header |

### 2.2 Key class name mapping

| Community edition class | Official edition class | Notes |
|-----------|-----------|------|
| `QOhAppContext` | `QOhosAppContext` | Application context |
| `QOHFileShare` | `QtOhosExtras::FileShare` | File sharing |
| `QOhWidgetHelper` | `QtOhosExtras::QOhosWindowUtils` | Window helpers |
| `QOhProcess` | (no direct counterpart) | Process management |
| `QOhChildProcess` | (no direct counterpart) | Child processes |
| `QOpenHarmonyAbility` (namespace) | `QtOhosExtras::QOhosAbilityContext` | Ability context |
| `QOpenHarmonyWant` | `QOhosWant` | Want data |
| `QOpenHarmonyStartOptions` | `QOhosStartOptions` | Start options |
| `QOhAbstractLocalSocket` | (no counterpart) | Local IPC |
| `QOhLocalServer` / `QOhLocalSocket` | (no counterpart) | Local IPC |
| `QOhWindowFunctions` | `QOhosFunctions` | Platform header functions |
| `QtOh::Utility` | `QOhosDeviceInfo` | Device information |
| `QOhFontDatabase` | `QOhosPlatformFontDatabase` | Font database |
| `QHarmonyStyle` | `QOhosStyle` | Style plugin |
| `QHarmonyWebView` | `QOhosWebView` | WebView |
| `QOhPlatformIntegration` | `QOhosPlatformIntegration` | Platform integration |
| `QOhPlatformWindow` | `QOhosPlatformWindow` | Platform window |
| `QOhPlatformNativeInterface` | `QOhosPlatformNativeInterface` | Native interface |
| `QOhPlatformTheme` | `QOhosPlatformTheme` | Platform theme |
| `QOhPlatformClipboard` | `QOhosPlatformClipboard` | Clipboard |
| `QOhPlatformInputContext` | `QOhosInputContext` | Input method |
| `QOhPlatformAbilityCtrl` | (no counterpart; capabilities live in `QOhosQpaFunctions`) | Ability control |
| `QPlatformAccessCtrl` | (no counterpart; capabilities live in `QOhosQpaFunctions`) | Access control |

---

## 3. Extras module public API comparison

### 3.1 AppContext (application context)

| Capability | Community edition `QOhAppContext` | Official edition `QOhosAppContext` |
|---------|----------------------|------------------------|
| **Class design** | Concrete class, private constructor, singleton | Abstract class, all pure virtual functions, singleton |
| Theme mode enum | `ColorMode{Dark,Light,Default,FollowSystemSetting}` + `SysThem{Dark,Light}` | `ColorThemeMode{LightTheme,DarkTheme,FollowSystemSetting}` |
| Get theme | `colorMode()` / `sysThem()` | `darkThemeActive()` |
| Set theme | `setColorMode(ColorMode)` (slot) | `setColorThemeMode(ColorThemeMode)` (virtual) |
| Theme signals | `sysThemChanged(SysThem)` / `colorModeChanged(ColorMode)` | `darkThemeActiveChanged(bool)` |
| PC mode signal | ✅ `pcModeChanged(bool)` | ❌ |
| Font size scaling | ❌ | ✅ `fontSizeScale()` + `fontSizeScaleChanged(double)` signal |
| Permission query | `isPermissionGranted(QString)` → bool (synchronous) | `isPermissionGranted(Permission)` + `(QString)` → bool (virtual) |
| Permission request | `requestPermissionFromUser(QString)` → bool (synchronous) | `requestPermissionFromUserIfNeeded(Permission)` → void (asynchronous + signal) |
| Permission via settings page | `requestPermissionsOnSetting(QString)` → bool | `requestPermissionOnSettingIfNeeded(Permission)` → void |
| Serial port permission | ❌ | ✅ `hasSerialPortAccessRight()` / `requestSerialPortAccessRightIfNeeded()` + signal |
| Context menu on long press | ❌ | ✅ `enableContextMenuEventOnLongPress()` |
| Bundle info | ❌ | ✅ `getBundleInfo()` → `QOhosBundleInfo` (`versionCode()`) |
| App restart | ❌ | ✅ `restartApp()` / `restartApp(QOhosWant)` — `Q_NORETURN` |
| No-UI child process mode | ❌ | ✅ `isNoUiChildMode()` / `startNoUiChildProcess(libraryName, args)` |
| App launch Want | ❌ | ✅ `getAppLaunchWant()` / `getAppLaunchWantInfo()` |
| Permission signals | ❌ | ✅ `permissionRequestResponseReceived` / `permissionRequestResponseWithResultReceived` / `permissionRequestOnSettingResponseReceived` / `serialPortAccessRightResponseReceived` |

### 3.2 AbilityContext (Ability context)

| Capability | Community edition `QOpenHarmonyAbility` (namespace) | Official edition `QOhosAbilityContext` |
|---------|---------------------------------------|---------------------------|
| **Class design** | Free functions in a namespace + `QAbilityResultReceiver` callback class | Abstract class + signal notification |
| Start Ability | `start(want)` / `start(want, options, receiver)` / `start(want, receiver)` — void | `startAbility(want)` / `startAbility(want, options)` / `startAbility(want, startRequest)` → `QSharedPointer<QOhosOperationStatus>` |
| Start for result | `startForResult(want)` / `startForResult(want, options, receiver)` — void | `startAbilityForResult(want)` → `QByteArray` (requestId) / `(want, options)` / `(want, startRequest)` |
| Result callback | `QAbilityResultReceiver::handleResult(Napi::Value err, Napi::Value result)` | Qt signals: `startAbilityForResultResponseReceived(requestId, resultCode, want)` / `startAbilityForResultErrorResponseReceived(requestId)` |
| Terminate self | ✅ `terminateSelfWithResult(QOpenHarmonyAbilityResult)` | ❌ not in the public API |
| Start by type | ❌ | ✅ `startAbilityByType(appType, wantParameters)` |
| Start a new instance | ❌ | ✅ `startNewAbilityInstance(QWidget*)` |
| Start an app process | ❌ (via `QOhProcess`/`QOhChildProcess`) | ✅ `startAppProcess(processId, want, ...)` (3 overloads) |
| Ability instance destruction control | ✅ `getSubProcessPid/AliveState/killSubProcess` (non-official) | ✅ `setAbilityInstanceDestroyEnabled(QWindow*, bool)` |
| System destruction control | ❌ | ✅ `setDestroyFromSystemEnabled(bool)` |
| Share data | ❌ | ✅ `shareDataWithShareKit(records, options)` → `QByteArray` |
| Open link | ❌ | ✅ `tryOpenLink(url)` / `tryOpenLink(url, QOhosOpenLinkOptions)` |
| Continuation active | ❌ | ✅ `setContinuationActive(bool)` |
| Get continuation data | ❌ | ✅ `tryGetOnContinueData(want)` / `tryRestoreOnContinueDistributedDataObjects(want)` |
| NewWant signals | ❌ | ✅ `newWantReceived(want)` / `newWantInfoReceived(wantInfo)` |
| Continue request signal | ❌ | ✅ `continueRequestReceived(QOhosOnContinueContext)` |
| Share panel signals | ❌ | ✅ `shareKitPanelClosed(requestId)` / `shareKitCompleted(requestId, result)` |

### 3.3 Want data structure

| Field/capability | Community edition `QOpenHarmonyWant` | Official edition `QOhosWant` |
|----------|------------------------|-----------------|
| parameters type | `QVariantMap` | `QJsonObject` |
| flags type | `int` (assigned directly) | `QOhosWantFlags` (QFlags) |
| Want flag enum | ❌ plain int | ✅ `QOhosWantFlag`: AuthReadUriPermission / AuthWriteUriPermission / InstallOnDemand |
| File descriptors | ❌ | ✅ `QHash<QString,int> fds` |
| WantInfo | ❌ | ✅ `QOhosWantInfo` abstract class: `LaunchReason` enum (Unknown/StartAbility/Continuation/PrepareContinuation/Preload) / `ContactInfo` struct / `tryGetSharedRecordsFromShareKit()` / `tryGetContactInfo()` |
| Termination result | ✅ `QOpenHarmonyAbilityResult` (resultCode + want) | ❌ |
| NAPI dependency | ✅ indirectly via `QAbilityResultReceiver` | ❌ pure Qt types |

### 3.4 StartOptions (start options)

| Field/capability | Community edition `QOpenHarmonyStartOptions` | Official edition `QOhosStartOptions` |
|----------|-------------------------------|--------------------------|
| Type | Plain struct; public fields assigned directly | Abstract class; pure virtual setters + factory creation |
| Window mode | `int windowMode` (raw int) | ✅ `enum class WindowMode`: SPLIT_PRIMARY / SPLIT_SECONDARY / FULLSCREEN |
| Process mode | `int processMode` | ✅ `enum class ProcessMode`: NEW_PROCESS_ATTACH_TO_PARENT / NEW_PROCESS_ATTACH_TO_STATUS_BAR_ITEM |
| Startup visibility | `int startupVisibility` | ✅ `enum class StartupVisibility`: STARTUP_HIDE / STARTUP_SHOW |
| Starting window icon | `QPixmap startWindowIcon` | `QImage` (via `setStartWindowIcon(QImage)`) |
| Starting window background color | `QString startWindowBackgroundColor` | `QColor` (via `setStartWindowBackgroundColor(QColor)`) |
| Window min/max size | ❌ | ✅ `setMinWindowWidth/Height` / `setMaxWindowWidth/Height` |
| Hide starting window | ❌ | ✅ `setHideStartWindow(bool)` |
| Window creation parameters | ❌ | ✅ `setWindowCreateParams(QOhosWindowCreateParams)` |
| Window creation animation | ❌ | ✅ `QOhosWindowCreateParams::AnimationType`: FADE_IN_OUT |
| How created | Direct construction + default constructor | Factory functions `createStartOptions()` / `createWindowCreateParams()` |
| SupportWindowMode | Global `enum class SupportWindowMode{FULL_SCREEN,SPLIT,FLOATING,INVALID_VAL}` | Nested `enum class QOhosStartOptions::SupportWindowMode{FULL_SCREEN,SPLIT,FLOATING}` |

### 3.5 File sharing

| Capability | Community edition `QOHFileShare` | Official edition `QtOhosExtras::FileShare` |
|---------|----------------------|-------------------------------|
| Container | Static class | Namespace |
| Mode enum | `Mode{READ_MODE=1, WRITE_MODE=2}` | `OperationMode{Read=1, Write=2}` |
| Error enum | `Error{ERR_OK, EXCEED_LIMIT, PERSISTENCE_FORBIDDEN, INVALID_MODE, INVALID_PATH, PERMISSION_NOT_PERSISTED}` | `PathPolicyError{Unknown, PersistenceForbidden, InvalidMode, InvalidPath, PermissionNotPersisted}` |
| Policy struct | `Policy{Modes mode; QString file;}` | `PathPolicy{QString path; OperationModes operationModes;}` |
| API pattern | Static methods return `Error` + output parameter `Results&` | Free functions return `QSharedPointer<ActionResult>` |
| Operation status | Error code only | ✅ `QOhosOperationStatus` object (`success()` method) |
| Check method name | `checkPersistentPermission` | `checkPersistent` |

### 3.6 Window helpers

| Capability | Community edition `QOhWidgetHelper` | Official edition `QOhosWindowUtils` |
|---------|------------------------|--------------------------|
| API style | Instance class, bound to a QWidget/QWindow at construction | Free functions in a namespace, with QWindow*/QWidget* overloads |
| Privacy mode | `setPrivacyMode(bool)` / `isPrivacyMode()` | `setWindowPrivacyMode(QWindow*, bool)` (no getter) |
| Corner radius | `setWindowCornerRadius(qreal)` / `windowCornerRadius()` | `setWindowCornerRadius(QWindow*, double)` (no getter) |
| Keep screen on | `setWindowKeepScreenOn(bool)` | `setWindowKeepScreenOn(QWindow*/QWidget*, bool)` |
| Background color | `setWindowBackgroundColor(QColor)` | `setSurfaceBackgroundColor(QWindow*/QWidget*, QColor)` |
| Drag to resize | `setResizeByDragEnabled(bool)` | `setWindowDragResizable(QWindow*/QWidget*, bool)` |
| Geometry persistence | `setWindowRectAutoSave(bool)` (per instance) | `setMainWindowGeometryPersistenceHint(WindowGeometryPersistenceHint)` (global) |
| Float window hint | ❌ | ✅ `setShowWindowAsFloatWindowHint()` |
| Close event root cause | ❌ | ✅ `getCloseEventRootCause(QCloseEvent*)` |
| Drag key frame policy | ❌ | ✅ `enableWindowDragKeyFramePolicy()` / `disableWindowDragKeyFramePolicy()` |
| Maximize options | ❌ | ✅ `setWindowMaximizeOptions()` / `clearWindowMaximizeOptions()` |
| Native window ID | ❌ | ✅ `tryGetNativeWindowId()` |
| Screen display ID | ❌ | ✅ `tryGetScreenDisplayId()` |
| Ability binding key | ❌ | ✅ `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| Decoration button style | ✅ `DecorButtonStyle` struct + getter/setter | ❌ |
| Decoration visibility | ✅ `windowDecorVisible()` / `setWindowDecorVisible()` | ❌ |
| Window shadow | ✅ `setWindowShadowRadius()` | ❌ |
| Move by title bar | ✅ `setWindowTitleMoveEnabled()` | ❌ |
| Title button visibility | ✅ `setWindowTitleButtonVisible(bool, bool, bool)` | ❌ |
| Title button rect | ✅ `titleButtonRect()` + `titleButtonRectChanged` signal | ❌ |
| Remove starting window | ✅ `removeStartingWindow()` | ❌ |
| PC mode signal | ✅ `pcModeChanged(bool)` | ❌ |

### 3.7 Process management

| Capability | Community edition | Official edition |
|---------|--------|--------|
| QProcess-style wrapper | ✅ `QOhProcess`: `start()` / `startDetached()` / `setMode()` / `stop()` / `isRunning()` / `pid()` / `errorString()` + `started`/`finished`/`errorOccurred`/`stateChanged` signals | ❌ no counterpart class |
| Native child processes | ✅ `QOhChildProcess` namespace: `startChildProcess()` / `startNativeChildProcess()` / `createNativeChildProcess()` / `createNativeChildProcessWithConfig()` | ❌ simplified to `QOhosAppContext::startNoUiChildProcess(libraryName, args)` |
| Child process configuration | ✅ `StartMode`/`IsolationMode`/`Options`/`Fd`/`Args`/`ChildProcessConfig` structs | ❌ |
| Child process management | ✅ `getSubProcessPid()` / `getSubProcessAliveState()` / `killSubProcess()` | ❌ |

### 3.8 Local IPC

| Capability | Community edition | Official edition |
|---------|--------|--------|
| Abstract local socket | ✅ `QOhAbstractLocalSocket`: `send(QString)` / `errorString()` / `close()` / `messageReady` signal | ❌ **does not exist at all** |
| Local socket client | ✅ `QOhLocalSocket`: `connect(address)` / `disconnectFromHost()` / `isConnected()` | ❌ |
| Local socket server | ✅ `QOhLocalServer`: `listen(address)` / `nextPendingConnection()` / `newConnection` signal | ❌ |
| Local socket connection | ✅ `QOhLocalConnection` | ❌ |

### 3.9 Permission management

| Capability | Community edition `QtOh` namespace | Official edition `AppPermissions` + `QOhosAbilityContext` |
|---------|------------------------|----------------------------------------------|
| Permission type | String `QString` | ✅ Typed enum `Permission` (ReadPasteboard/CustomScreenCapture/AccessBluetooth/ApproximatelyLocation/Location) + string overloads |
| Synchronous request | ✅ `requestPermissionsSync(QStringList, timeoutMs)` | ❌ asynchronous only |
| Asynchronous request | ✅ `requestPermissions(QStringList, callback)` | ✅ `requestPermissionFromUserIfNeeded(Permission)` + signal |
| Synchronous request via settings page | ✅ `requestPermissionsOnSettingSync(QStringList, timeoutMs)` | ❌ |
| Asynchronous request via settings page | ✅ `requestPermissionsOnSetting(QStringList, callback)` | ✅ `requestPermissionOnSettingIfNeeded(Permission)` + signal |
| Permission check | `checkPermission(QString)` → `PermissionResult` enum | `isPermissionGranted(Permission)` → bool |
| Result type | `PermissionResult` enum (Denied/Granted/InValidRequest) | `PermissionResult` struct (bool permissionGranted, bool dialogShown) |
| Notification permission | ✅ `requestEnableNotification()` / `requestEnableNotificationSync()` / `isNotificationEnabled()` / `openNotificationSettings()` | ❌ |
| SDK version | ✅ `ohSdkVersion()` | ❌ |

### 3.10 Extras interfaces only in the official edition

| Interface | Implemented capability |
|------|---------|
| `QOhosDistributedDataObject` | Cross-device distributed data sync: `create(QJsonObject)` / `get(key)` / `fieldNames()` / `addAssets(files)` / `assetKey()` / `assets()` / `areAssetsSynced()` / `sessionId()` / `save(deviceId)` + 4 signals (dataChanged/statusChanged/progressChanged/saveFinished) |
| `QOhosShareKit` namespace | System share framework: `QOhosSharedRecord` (13 properties) / `QOhosShareControllerOptions` (anchor/single selection/preview/exclusion) / `QOhosShareOperationResult` / factory functions createContentRecord/createFileRecord/createUrlRecord |
| `QOhosMultimedia` namespace | Audio stream usage hint: `AudioStreamUsageHint` enum (14 values: Unknown/Music/VoiceCommunication/VoiceAssistant/Alarm/VoiceMessage/Ringtone/Notification/Accessibility/Movie/Game/Audiobook/Navigation/VideoCommunication) |
| `QOhosOnContinueContext` | Distributed migration context: `setAgreeResponse()` / `setRejectResponse()` / `setMismatchResponse()` / `setResponseOnDistributedDataObjectsSaveResults()` / `setExitAppOnSourceDeviceAfterMigration()` / `sourceApplicationVersionCode()` / `targetDeviceId()` |
| `QOhosOpenLinkOptions` | Link opening options: `setAppLinkingOnly(bool)` |
| `QOhosStartRequest` | Asynchronous start request: `requestSucceeded` / `requestFailed` signals |
| `QOhosOperationStatus` | Operation status: `success()` |
| `QOhosFileUtils` | File utilities: `moveFileToTrash()` / `authorizeFilePath()` |
| `QOhosBundleInfo` | Bundle info: `versionCode()` |
| `QOhosPasteboard` | Clipboard: `setInAppOnlyPasteboardShareOption()` |
| `QOhosDragKeyFramePolicy` | Drag key frame policy: `setInterval()` / `setDistance()` / `setAnimationDuration()` / `setAnimationDelay()` |
| `QOhosWindowMaximizeOptions` | Window maximize options: `MaximizePresentation` (4 values) / `AcrossDisplayPresentation` (3 values) / snapshot animation configuration |
| `QOhosElementName` | Element name struct: deviceId/bundleName/abilityName/uri/shortName/moduleName |
| `QOhosWantInfo` | Want info: `LaunchReason` enum (5 values) / `ContactInfo` / `tryGetSharedRecordsFromShareKit()` / `tryGetContactInfo()` |

---

## 4. QPA platform plugin interface comparison

### 4.1 PlatformIntegration (platform integration)

| Capability | Community edition `QOhPlatformIntegration` | Official edition `QOhosPlatformIntegration` |
|---------|-------------------------------|--------------------------------|
| Window/BackingStore/OpenGL/Offscreen creation | ✅ | ✅ |
| Event dispatcher | ✅ | ✅ |
| Fonts/clipboard/drag and drop/input method/services | ✅ | ✅ |
| Theme management | ✅ `QOhPlatformTheme` | ✅ `QOhosPlatformTheme` |
| Accessibility | ✅ conditional on SDK > 13 | ✅ unconditional + `tryInitializeAccessibilityForQWindowWithXComponent()` |
| Touch device management | ✅ `touchDevice()` / `setTouchDevice()` | ❌ handled internally |
| Keyboard modifier query | ✅ `queryKeyboardModifiers()` | ❌ |
| Virtual desktop | ✅ `isVirtualDesktop()` | ❌ |
| Vulkan support | ✅ `createPlatformVulkanInstance()` | ❌ |
| Ability control hook | ✅ `abilityCtrl()` → `QPlatformAbilityCtrl` | ❌ implemented via `QOhosQpaFunctions` |
| Access control hook | ✅ `accessCtrl()` → `QPlatformAccessCtrl` | ❌ implemented via `QOhosQpaFunctions` |
| Singleton access | ❌ | ✅ `instance()` (static) |
| Pre-initialized display metrics | ❌ | ✅ `setDefaultDisplayMetrics()` (static) |
| System locale | ❌ | ✅ `systemLocale()` / `setSystemLocale()` |
| Window geometry persistence policy | ❌ | ✅ `WindowGeometryPersistencePolicy` enum (Disabled/Enabled/FollowSystemSetting) |
| Context menu on long press | ❌ | ✅ `setContextMenuOnLongPressEnabled()` / `getSyntheticQPointForContextMenuOnLongPress()` |
| Static dark theme control | ❌ | ✅ `setDarkThemeEnabled()` (static) |
| Application state tracking | ❌ (window-level `applicationStateChanged()`) | ✅ dedicated `QOhosApplicationStateTracker` |
| Multi-screen management | ❌ single screen `screen()` | ✅ `screenManager()` → `QOhosScreenManager` |
| Input method event handler | ❌ | ✅ `inputMethodEventHandler()` |
| File engine handler | ✅ `QOhFileEngineHandler` member | ❌ not exposed in the integration header |
| Password mode flag | ✅ `m_showPasswordEnabled` static flag | ❌ |
| SDK-conditional display backend | ✅ `QJsDisplay*` (SDK≤13) / `QOhDisplayManager` (SDK>13) | ❌ uses `QOhosScreenManager` + `QOhosDisplayInfo` uniformly |

### 4.2 PlatformWindow (platform window)

| Capability | Community edition `QOhPlatformWindow` | Official edition `QOhosPlatformWindow` |
|---------|------------------------|---------------------------|
| Basic window operations (geometry/visibility/cursor/parent-child) | ✅ | ✅ |
| Window opacity | ✅ `setOpacity(qreal)` override | ❌ |
| Window modality | ✅ `modality()` virtual function | ❌ |
| Window property tag system | ❌ identified by name strings | ✅ 12 static property descriptors `QOhosPropertyDescriptor<T>` |
| Sub-window/main window/float window tags | ❌ | ✅ `tagWindowOrWidgetAsSubWindowOf()` / `tagWindowOrWidgetAsMainWindow()` / `tagWindowOrWidgetAsFloatWindow()` |
| Widget-window host tag | ❌ | ✅ `tagWidgetWindowAsHostOfWidget()` |
| Window decoration presets | ❌ | ✅ `DecorationPreset` (Standard/Frameless) |
| Safe area margins | ❌ | ✅ `safeAreaMargins()` |
| Actual frame margins | ✅ `setFrameMargins()` (no-op virtual function) | ✅ `frameMargins()` (real implementation) |
| Window snapshot | ❌ | ✅ `makeSnapshot()` → QPixmap |
| Surface consumer API | ❌ | ✅ `setSurfaceConsumer()` |
| Non-client area pointer events | ❌ | ✅ `onNonClientAreaPointerPress/Move/Release()` |
| Window brightness/contrast/saturation | ❌ | ✅ `setBrightness()` / `setContrast()` / `setSaturation()` |
| Fixed window size | ❌ | ✅ `windowFixedSizeStateProperty` |
| Two-way OHOS↔Qt state sync | ❌ one-way (Qt→OHOS) | ✅ `setWindowStateFromOhos()` / `setWindowGeometryFromOhos()` / `setExposedFromOhos()` / `setDisplayIdFromOhos()` / `notifyWindowDestroyedFromOhos()` and so on |
| DPI change handling | ❌ | ✅ `handleDpiChange()` |
| Window flag management | ❌ | ✅ `setWindowFlags()` / `windowFlags()` / `platformWindowFlagsForQWindow()` / `onWindowFlagsChanged()` |
| Window activation request | ❌ | ✅ `requestActivateWindow()` |
| Soft keyboard needed flag | ❌ | ✅ `setNeedSoftKeyboard()` |
| Close event root cause | ❌ | ✅ `CloseEventRootCause` enum |
| Ability-QWindow binding key | ❌ | ✅ `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| Close popups | ❌ | ✅ `closeAllActivePopups()` (static) |
| Type-safe window lookup | ❌ | ✅ `fromQWindow()` / `fromQWindowOrNull()` (static) |
| Template property system | ❌ | ✅ `setWindowOrWidgetProperty<T>()` / `tryGetWindowOrWidgetProperty<T>()` |
| Direct access to the window node | ✅ `nativeWindowNode()` → `QOhWindowNode*` | ❌ replaced by the property system |
| Manually triggered expose | ✅ `fireFullExpose()` / `fireExpose()` | ❌ handled internally |
| XComponent size | ✅ `xcomponentSize()` | ❌ |
| Decoration button style | ✅ `DecorButtonStyle` struct | ❌ |
| Decoration visibility | ✅ `windowDecorVisible()` / `setWindowDecorVisible()` | ❌ |
| Window shadow radius | ✅ `setWindowShadowRadius()` | ❌ |
| Move by title bar | ✅ `setWindowTitleMoveEnabled()` | ❌ |
| Title button visibility | ✅ `setWindowTitleButtonVisible(bool, bool, bool)` | ❌ |
| Title button rect | ✅ `titleButtonRect()` + signal | ❌ |
| Remove starting window | ✅ `removeStartingWindow()` | ❌ |
| 16-value render fit | ✅ `setNativeNodeRenderFit(NativeNodeRenderFit)` — 16 modes | ❌ 2-value `NativeNodeRenderFitPolicy` (TopLeft/Fill) |
| Native node background color | ✅ `setNativeNodeBackgroundColor(QColor)` instance method | ❌ static + property descriptor + QPA function |
| Window status events | ✅ `handleWindowStatusEvent(WindowStatusType)` + 7-value enum | ❌ `setWindowStateFromOhos()` + `onWindowStateChanged()` |
| Window cursor type | ✅ custom `QCursorInfo*` struct | ✅ standard `QCursor` + `QOhosOptional<QCursor>` |
| Window identity | ✅ name strings (`windowName`/`parentWindowName`) | ✅ typed `InternalWindowId` + property tags |
| Native window ID | ✅ `nativeWindowId()` → `int32_t` (instance method) | ✅ `tryGetNativeWindowId(QObject*)` → `QOhosOptional<double>` (QPA function) |

### 4.3 NativeInterface (native interface)

| Capability | Community edition `QOhPlatformNativeInterface` | Official edition `QOhosPlatformNativeInterface` |
|---------|-----------------------------------|-------------------------------------|
| Exposes native resource pointers | ✅ `"UIAbility"`, `"UIAbilityContext"`, `"nativeSettings"` (via `nativeResourceForIntegration`) | ❌ does not expose native pointers |
| Window-level native resources | ✅ `"nativeXComponent"`, `"NativeNode"`, `"nativeWindow"`, `"nativeWindowStage"`, `"vkSurface"` (via `nativeResourceForWindow`) | ❌ |
| Native resource function query | ✅ `"isFreeWindowEnable"` (via `nativeResourceFunctionForIntegration`) | ❌ |
| Platform functions | ✅ `setNativeNodeRenderFit`, `setNativeNodeRenderBackgroundColor` | ✅ `tagWindowOrWidgetAsSubWindowOf`, `getWindowOrWidgetAsSubWindowOfTagValue`, `tagWindowOrWidgetAsMainWindow`, `setInAppOnlyPasteboardShareOption`, `tagWidgetWindowAsHostOfWidget`, `setSurfaceConsumer` |
| Custom event handling | ❌ | ✅ `customEvent(QEvent*)` override |

### 4.4 Other QPA interfaces

| Interface | Community edition | Official edition |
|------|--------|--------|
| **Cursor** | Rich: `setOverrideCursor()`/`clearOverrideCursor()`/`enforceOverrideCursor()`/`setPos()`/`size()`/per-window cursors/pixmap cache | Minimal: only `changeCursor()` + `pos()` |
| **System tray** | Full class: `ContentType` (5 values)/`SlotType` (5 values)/light and dark icons/NAPI bridging | Implementation hidden behind a factory function |
| **Menus** | ✅ full implementation of `QOhPlatformMenu` + `QOhPlatformMenuItem` | ❌ no `QPlatformMenu` subclass |
| **Drag and drop** | Concrete classes `QOhDrag` + `QOhDropTarget` | Abstract class `QOhosPlatformDrag`: `handlePreDrop()` + `updateDropAction()` |
| **Clipboard** | Direct `OH_Pasteboard` C API + progress (SDK≥15) + observer + singleton | `QOhosClipboardObject` abstraction + lazy loading + in-app sharing + `setInAppOnlyPasteboardShareOption()` |
| **BackingStore** | Plain `QPlatformBackingStore` + simple `BufferRegionHandler` + VSync (SDK>14) | `QRasterBackingStore` + `QImageView`/`BufferRegionHandler`/`FlushData`/`WindowContext`/`WindowContextManager` (multi-window dirty region merging + deferred flushing) + GL BackingStore |
| **EGL context** | Plain `QEGLPlatformContext` subclass | Structured `CreateInfo` + overridden `swapBuffers()` + swap state tracking |
| **System locale** | ❌ | ✅ `QOhosSystemLocale`: `query()` / `fallbackUiLocale()` |
| **Screen management** | `QOhDisplayManager`: `allScreens()`/`screenAt()` | `QOhosScreenManager`: `rebuildScreenList()`/display ID lookup |
| **Accessibility** | `QOhPlatformAccessibility::notifyAccessibilityUpdate()` (SDK>13) | Full subsystem: `QOhosAccessibilityTree`/`Provider`/`EventHandler`/`ArkUIHelpers`/`MenuActions`/`TabBars`/`TableModelChangeEventHandler` and others, 17+ file pairs |
| **Application state** | `applicationStateChanged()` (window-level) | Dedicated `QOhosApplicationStateTracker` |
| **Icon engine** | ❌ | ✅ `QOhosPlatformTheme::createIconEngine()` |
| **Input method controller** | `InputMethod::QOhController` (external C API `inputmethod_controller_capi.h`) | `QOhosInputMethodProxy` (JS/NAPI) + `ImConnectionState` state machine (Attached/Detached) |
| **Input method event filtering** | `filterEvent(QEvent*)` override | `eventFilter(QObject*, QEvent*)` override |
| **Input method text/enter key types** | No own enums; uses the C API types `InputMethod_TextInputType`/`InputMethod_EnterKeyType` + conversion functions | ✅ own enums `TextInputType` (10 values) + `EnterKeyType` (9 values) + `Direction` (4 values) + `OhosEnumMeta` JS mapping |
| **Input method cursor handling** | `setKeyboardRect()` + private slots `cursorRectangleChanged()`/`updateCursor()` | `updateOhosCursor()` + `onCursorRectangleChanged()` + `tryQueryCursorPosition()` |
| **Input method preview text** | `m_previewText` + `finishTextPreview()` slot | `m_pendingPreeditText` + `sendInsertedPreviewTextToQt()` + `PreviewReplaceRange` |
| **Deadlock detection** | ❌ | ✅ `QOhosDeadlockProtector` |
| **Big data event logging** | ❌ | ✅ `QOhosBigDataEventLogging` |
| **Window property descriptors** | ❌ | ✅ `QOhosPropertyDescriptor<T>` template + `QOhosPropertiesStore` + `QOhosPropertiesProvider` |
| **Gesture recognizers** | ❌ | ✅ `makeQOhosPinchGestureRecognizer()` (widgets) |

---

## 5. Corelib kernel support interface comparison

### 5.1 Centralized platform function interface

| Capability | Community edition | Official edition |
|------|--------|--------|
| **Central API interface** | Scattered across the `QtOh` namespace + the `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` abstractions | ✅ `QtOhos::QOhosQpaFunctions` — **a unified interface of 60+ pure virtual functions** |

All capability categories covered by the official edition's `QOhosQpaFunctions`:

| Category | Method count | Capabilities |
|------|--------|------|
| Window operations | 15+ | Privacy mode/corner radius/background color/keep screen on/drag resizing/key frame policy/maximize options/brightness/contrast/saturation/float window tag/render fit policy/destroy flag/fixed size/Ability binding |
| Theme configuration | 6 | Dark theme/font size scaling/dark mode data source/font size data source/geometry persistence policy |
| Clipboard | 3 | In-app sharing/get image/get text |
| File operations | 2 | Move to trash/file dialog authorization |
| Context menu | 2 | Enable long-press menu/synthetic menu point detection |
| Screen/window ID | 3 | Native window ID/screen display ID/screen color picking |
| Ability lifecycle | 4 | Continue request handler/continuation active/destroy flag/app restart |
| Want management | 3 | Get launch Want/get launch WantInfo/add Want consumer (2 overloads) |
| Process management | 4 | Start app process/no-UI child process/read no-UI mode/version code |
| Ability start | 3 | Start Ability/start by type/start for result |
| Permission management | 5 | Named permission check/request from user/request via settings/batch request from user/batch request via settings |
| Serial port permission | 2 | Check serial port permission/request serial port permission |
| File sharing | 5 | Persist/revoke/activate/deactivate/check persistent permission |
| Share Kit | 1 | Share data (including SharedRecord/ShareControllerOptions) |
| Link opening | 1 | Try to open a link (with the appLinkingOnly option) |
| Distributed data | 3 | Generate session ID/get distributed file directory/create distributed data object |
| Accessibility | 1 | Notify that an accessible interface was deleted |
| Audio streams | 2 | Set/get audio stream usage hint (14 kinds of AudioStreamUsage) |

### 5.2 Device/system information

| Capability | Community edition `QtOh::Utility` | Official edition `QOhosDeviceInfo` |
|------|------------------------|------------------------|
| Return type | Typed `QString`/`int` | `QVariant` |
| Number of properties | 27 static methods | 32 Type enum values |
| Device type | `DeviceType` bit-flag enum (9 values: Unknown/PC/Phone/Wearable/LiteWearable/Tablet/Tv/Car/SmartVision) | `RecognizedDeviceType` enum (3 values: _2in1/tablet/phone) |
| Detection methods | `isTabletDevice()`/`isPhoneDevice()`/`isSupportFreeWindow()`/`isOpenHarmonyDevice()` (in `qohauxiliary.h`) | `isTablet()`/`is2in1()`/`isPhone()`/`isCurrentDeviceSupported()`/`tryGetRecognizedDeviceType()` |
| Edition-specific properties | `productSeries` | `hardwareProfile`/`serial`/`majorVersion`/`seniorVersion`/`featureVersion`/`buildVersion`/`udid` |
| SDK version | `QtOh::Utility::sdkApiVersion()` + `QtOh::ohSdkVersion()` | `QOhosDeviceInfo::sdkApiVersion()` |

### 5.3 Watchdog and events

| Capability | Community edition | Official edition |
|------|--------|--------|
| Watchdog | ✅ `QOhosWatchdog` (Hicollie): `Init()`/`Stop()`/`SetAppMainThreadState()`/`AllowReportEvent()`/`IsReportEvent()`/`Timer()` | ✅ `QOhosWatchdog` (similar implementation) |
| HiAppEvent | ✅ `QOhHiAppEvent` singleton: event types (FAULT/STATISTIC/SECURITY/BEHAVIOR)/`writeDataTag()` | ✅ `QOhosBigDataEventLogging` |
| Deadlock detection | ❌ | ✅ `QOhosDeadlockProtector` |

### 5.4 Thread bridging infrastructure

| Capability | Community edition | Official edition |
|------|--------|--------|
| JS thread dispatch | ✅ `QtOh::runOnJsUIThreadNoWait()` / `runOnJsUIThreadAndWait()` | ✅ `QOhosJsThreadGateway::invoke()` / `invokeAndWaitForContinue()` / `runAndWait()` |
| JS thread dispatch with return value | ✅ `runOnJsUIThreadWithResult<>()` template (direct `uv_queue_work` + `std::promise`) | ✅ `QOhosJsThreadGateway::eval<Func>()` / `evalWithPromise<T>()` (with a static_assert that prevents NAPI values from leaking outside the JS thread) |
| JS state abstraction | ❌ exposes `napi_env` directly | ✅ `QOhosJsState` abstract class: `env()` / `defaultWindowStageOrEmpty()` / `defaultUiContextOrEmpty()` / `tryGetJsWindowByQWindow()` / `tryGetQAbilityByQWindow()` / `defaultQAbility()` / `appLaunchWant()` / `eval<T>()` / `mapOhosEnumToJs<Enum>()` |
| JS thread operation registration | ❌ | ✅ `QOhosJsThreadOps`: `registerInstance()` / `instance()` |
| Qt thread state | ❌ | ✅ `QtState`: `isQtThread()` / `invokeTask()` / `qpaFunctions()` |
| Thread-safe QObject references | ❌ | ✅ `QObjectThreadSafeRef` / `QThreadSafeRef<T>`: `visitInQtThreadIfAlive()` |
| JS-thread-safe deleter proxy | ❌ | ✅ `makeProxyWithJsThreadDeleter<T>()` |
| Qt thread initialization | ❌ | ✅ `initQtThreadState()` / `getQtState()` / `invokeInQtThread()` |
| Callback info extension | ❌ | ✅ `QOhosCallbackInfo` extends `QNapi::CallbackInfo` |
| Enum-to-JS mapping | ❌ | ✅ `OhosEnumMeta<Enum>` template + `OhosEnumInfo`/`OhosEnumFullTypeNameFetcher` SFINAE |
| NAPI error handling | ✅ `GET_AND_THROW_LAST_ERROR`/`NAPI_ASSERT_*`/`NAPI_CALL_*` macros | ✅ `logJsCallbackError()` / `makeErrorLoggingJsCallback()` |
| Qt main thread dispatch | ✅ `runOnQtMainThread()`/`runOnQtMainThreadWithResult()`/`runOnQtMainThreadAndWait()`/`runOnQtMainThreadLater()` template family | ✅ `invokeInQtThread()` (simplified) |

### 5.5 General utilities

| Capability | Community edition | Official edition |
|------|--------|--------|
| Asynchronous promise chains | ❌ | ✅ `QOhosTaskPromise<Args...>`: `makeChained()` / `makeBranched()` / `makeThenCatchBranches()`, with caller-context chain tracking + dead promise detection |
| Array view | ❌ | ✅ `QOhosSpan<T>`: `begin()` / `end()` / `data()` / `size()` / `operator[]` / `subspan()` + `as_bytes()` |
| Mutex-protected value | ❌ | ✅ `QOhosMutexProtectedValue<T>`: `processValue()` / `evalWithValue()` |
| Optional type | ❌ | ✅ `QOhosOptional<T>`: `hasValue()` / `value()` / `valueOr()` / `andThen()` / `transform()` + full set of comparison operators + `QOhosOptional<void>` specialization |
| Named function wrapper | ❌ | ✅ `QOhosNamedFunc<FuncPtr,Invoker>` |
| Consumers/suppliers | ❌ | ✅ `QOhosConsumer<Ts...>` / `QOhosSupplier<T>` / `QOhosNoOpConsumer` |
| Fatal error reporting | ❌ | ✅ `qOhosReportFatalErrorAndAbort` macro |
| UDMF helper | ✅ `UdmfHelper`: `createQImageFromPixelmapNative()` / `createNativePixelMapFromQImage()` / `acquireDatasFromUdmfToMime()` / `makeUdmfDataFromMime()` | ❌ |

### 5.6 Standard paths and other backends

| Backend | Community edition | Official edition |
|------|--------|--------|
| `QStandardPaths` | ✅ `qstandardpaths_openharmony.cpp` — calls `OH_Environment_*` directly | ✅ `qstandardpaths_ohos.cpp` — uses the `QOhosAppContext::Type` enum |
| `QSettings` | ✅ `qsettings_openharmony.cpp` | ✅ similar implementation |
| Locale | ✅ `qlocale_harmony.cpp` | ✅ full `QOhosSystemLocale` integration |
| Time zone | ✅ `qtimezoneprivate_openharmony.cpp` | ✅ similar implementation |
| OS version | ✅ `qoperatingsystemversion_openharmony.cpp` | ✅ similar implementation |
| App directory paths | `QtOh::dir(QString)` / `setDir(QString, QString)` — string IDs | ✅ `QOhosAppContext` namespace: 8 `Type` enum values + `init()` / `getProperty()` / `getAllProperties()` |
| URI/path conversion | ✅ `QtOh::pathFromUri()` / `uriFromPath()` | ❌ handled internally |

### 5.7 New QPA abstractions in the GUI kernel (community edition only)

| Interface | Community edition | Official edition |
|------|--------|--------|
| `QPlatformAccessCtrl` | ✅ a new abstract base class added in `gui/kernel`, integrated into `QPlatformIntegration::accessCtrl()`: `checkPermission` / `requestPermissions` / `requestPermissionsOnSetting` / `requestEnableNotification` / `isNotificationEnabled` / `openNotificationSettings` (with synchronous convenience implementations) + `accessTokenId` / `atManagerAcquire` / `bundleManagerAcquire` / `notificationManagerAcquire` | ❌ no such abstraction; capabilities live in `QOhosQpaFunctions` |
| `QPlatformAbilityCtrl` | ✅ a new pure virtual interface added in `gui/kernel`: `startAbility` / `startAbilityForResult` / `terminateSelfWithResult` (using `QVariantMap` + `Napi::Value`) | ❌ no such abstraction; capabilities live in `QOhosQpaFunctions` |
| `QtOhPrivate` convenience functions | ✅ `qohosabilityctrl.h`: `startAbility()` / `startAbilityForResult()` / `terminateSelfWithResult()` — delegate to the platform `QPlatformAbilityCtrl` | ❌ |

### 5.8 Public platform headers

| Capability | Community edition `QOhWindowFunctions` | Official edition `QOhosFunctions` |
|------|---------------------------|------------------------|
| Native node render fit | ✅ `setNativeNodeRenderFit()` — **16 fit modes** | ❌ moved to the QPA-internal `NativeNodeRenderFitPolicy` (2 values) |
| Native node background color | ✅ `setNativeNodeBackgroundColor()` | ❌ moved to `QOhosWindowUtils::setSurfaceBackgroundColor()` |
| Window tags | ❌ | ✅ `tagWindowOrWidgetAsSubWindowOf()` / `tagWindowOrWidgetAsMainWindow()` / `getWindowOrWidgetAsSubWindowOfTagValue()` |
| In-app clipboard sharing | ❌ | ✅ `setInAppOnlyPasteboardShareOption()` |

### 5.9 Logging

| Capability | Community edition | Official edition |
|------|--------|--------|
| Logging macros | ✅ `qopenharmonydefines.h`: `LOGI`/`LOGD`/`LOGW`/`LOGE` via `OH_LOG_Print` (domain `0xff11`, tag `QPAForOpenHarmony`) | ✅ `qohoslogger_p.h`: `qOhosPrintfDebug`/`qOhosPrintfInfo`/`qOhosPrintfWarning`/`qOhosPrintfError` + `qOhosLogMessage()` / `qOhosVPrintf()` + `QCScopedDebug` RAII + `QtForOhos()` logging category |
| NAPI macros | ✅ `GET_AND_THROW_LAST_ERROR` / `NAPI_ASSERT_*` / `NAPI_CALL_*` / `DECLARE_NAPI_*` property/function descriptors | ❌ uses the `QNapi` wrapper library |

---

## 6. Feature module plugin interface comparison

### 6.1 Multimedia (qtmultimedia)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Player | ✅ `qohplayer` (wraps `OH_AVPlayer`) / `qohdecoder` / `qohdemuxer` / `qohcodekit` | ✅ `qohosavplayer` (wraps `OH_AVPlayer`) / `qohosavplayerlist` / `qohosmediaplayercontrol` |
| Camera | ✅ `qohcaptureservice` / `qohcameracontrol` / `qohcamerasession` / `qohcamerarendercontrol` / `qohcameraimagecapturecontrol` and others | ✅ `qohoscameraservice` / `qohoscamerasession` / `qohoscapturesession` / `qohoscamerainput` / `qohoscameraphotooutput` / `qohoscamerapreviewoutput` / `qohoscameravideooutput` and others |
| Recording | ✅ `qohrecordercontrol` / `qohaudioencodercontrol` / `qohvideoencodercontrol` / `qohcontainercontrol` | ✅ `qohosavrecorder` / `qohosmediarecordercontrol` |
| Audio devices | ✅ `ohaudiodevice` plugin: `qohaudiodeviceplugin` / `qopenharmonyengine` / `qopenharmonyaudiomanager` / `qopenharmonyaudioinput` / `qopenharmonyaudiooutput` | ✅ `ohos-audio` plugin: `qohosaudioplugin` / `qohosaudioinput` / `qohosaudiooutput` / `qohosaudiodeviceinfo` |
| Video rendering | ✅ `qopenharmonysgvideonode` (scene graph video node) | ✅ `qohosvideorenderercontrol` / `qohosvideowidget` / `qohosvideobuffer` |
| NAPI wrappers | ✅ `ohcamera` / `ohmediarecorder` / `ohmultimediautils` | ❌ uses ArkTS bridging directly |
| Audio stream usage hint | ❌ | ✅ `QOhosMultimedia::AudioStreamUsageHint` (14 values) |
| Recording timer | ❌ | ✅ `qohosrecordingtimer` |
| Image encoding/packing/receiving | ❌ | ✅ `qohosimageencodercontrol` / `qohosimagepacker` / `qohosimagereceiver` |
| Video device selection | ❌ | ✅ `qohosvideodeviceselectorcontrol` |
| Viewfinder controls | ✅ `qohviewfindersettingscontrol2` | ✅ `qohoscameraviewfindersettingscontrol2` + `qohoscameraviewfinderwidget` + `qohoscameraviewfindercontrol` |

### 6.2 Connectivity (qtconnectivity)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Bluetooth state management | ✅ `qbluetoothlocaldevice_ohos.cpp` | ✅ `qohosbluetoothaccess`: `BluetoothState` enum (OFF/TURNING_ON/ON/.../BLE_ON) + `setBluetoothEnabled()` |
| Device discovery | ✅ `qbluetoothdevicediscoveryagent_ohos.cpp` | ✅ `qohosbluetoothdevicediscovery` |
| Service discovery | ✅ `qbluetoothservicediscoveryagent_ohos.cpp` | ❌ |
| Bluetooth sockets | ✅ `qbluetoothsocket_ohos.cpp` + `qjssocket` | ✅ `qohosbluetoothsocket`: `BluetoothSppType` enum (SPP_RFCOMM) |
| Bluetooth server | ✅ `qbluetoothserver_ohos.cpp` + `serveracceptancethread` | ✅ `qohosbluetoothserver` |
| Bluetooth service info | ✅ `qbluetoothserviceinfo_ohos.cpp` | ❌ |
| GATT/LE | ✅ `qlowenergycontroller_ohos.cpp` + `lowenergynotificationhub` + `qjsble` | ❌ |
| NFC | ✅ `qnearfieldmanager_openharmony` / `qnearfieldtarget_openharmony` / `qllcpsocket_openharmony` / `qllcpserver_openharmony` + `openharmonynfc` / `openharmonynfclistener` + `qjscontroller` / `qjstag` | ❌ |
| ArkTS bridging | ✅ 11 `QtBluetooth*.ts` + 3 `JsNfc*.ts` | ❌ uses C++ wrappers |
| Remote devices | ❌ | ✅ `qohosbluetoothremotedevice` |
| Bluetooth common utilities | ❌ | ✅ `qohosbluetoothcommon` |

### 6.3 Location (qtlocation)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Position info source | ✅ `qgeopositioninfosource_openharmony` (wraps `LocationKit/oh_location.h`) | ✅ `qohosgeopositioninfosource` |
| Satellite info | ❌ | ✅ `qohosgeosatelliteinfosource` |
| Map services | ❌ | ✅ `ohosmapkit`: service provider plugin/tiled map manager/tile fetcher/file cache/geocoding/routing/place search/search suggestions/POI categories |
| Plugin factory | ✅ `qgeopositioninfosourcefactory_openharmony` | ✅ `positionfactory_ohos` |
| JS bridging | ❌ | ✅ `qohosjsutils` |
| Common utilities | ❌ | ✅ `qohospositioncommon` |

### 6.4 Sensors (qtsensors)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Sensor manager | ✅ `JsSensor` + `SensorManager` singleton (JS bridging) | ✅ `OhosSensorsManager` singleton (direct `oh_sensor.h` C API) |
| Backend template | ❌ standalone backend classes | ✅ `OhosSensorBackendBase<T>` template base class |
| Accelerometer | ✅ `openharmonyaccelerometer` | ✅ `ohosaccelerometerbackend` |
| Gyroscope | ✅ `openharmonygyroscope` | ✅ `ohosgyroscopebackend` |
| Magnetometer | ✅ `openharmonymagnetometer` | ✅ `ohosmagnetometerbackend` |
| Light | ✅ `openharmonylight` | ✅ `ohoslightsensorbackend` |
| Proximity | ✅ `openharmonyproximity` | ❌ |
| Pressure | ✅ `openharmonypressure` | ❌ |
| Humidity | ✅ `openharmonyhumidity` | ❌ |
| Temperature | ✅ `openharmonytemperature` | ❌ |
| Rotation | ✅ `openharmonyrotation` | ✅ `ohosrotationsensorbackend` |
| Sensor capability query | ❌ | ✅ `OhosSensorCapabilities` (resolution/min-max data rate) |
| ArkTS bridging | ✅ `JsSensor.ts` / `JsSensorManager.ts` / `JsSensorsModule.ts` | ❌ uses `oh_sensor.h` directly |
| Sensor ID mapping | ✅ OHOS↔Qt enum mapping (12 kinds) | ✅ `ohossensorutils` |

### 6.5 WebView (qtwebview)

| Capability | Community edition | Official edition |
|------|--------|--------|
| WebView implementation | ✅ `QHarmonyWebView` | ✅ `QOhosWebView` |
| WebView controller | ❌ | ✅ `qohoswebviewcontroller` |
| Web component listener | ❌ | ✅ `qohoswebcomponentlistener` |
| Web resource errors | ❌ | ✅ `qohoswebresourceerror` |
| ArkTS bridging | ✅ `JsWebView.ets` | ❌ |

### 6.6 Other modules

| Module | Community edition | Official edition |
|------|--------|--------|
| **Network bearer** | ❌ | ✅ `ohos` bearer plugin: `QOhosBearerEngine` + `QOhosManagerInterface` + `QOhosWifiInterfaceProxy` (WiFi/cellular/Bluetooth/Ethernet/VPN) |
| **Printing** | ✅ `openharmony` print support: `QOpenHarmonyPrinterSupport` + `QOpenHarmonyPrintEngine` + `OHPrinter` struct | ✅ `ohos` print support: `QOhosPrinterSupport` + `QOhosNativePrint` (connect/print/query/manage + `PrinterCapabilities`/`PrinterDefaultValues`/`PrinterInfo`/`PageSize` structs) + `QOhosPdfPrintEngine` + `QOhosPrintDevice` |
| **Text to speech** | ❌ | ✅ `ohos` TTS plugin: `QTextToSpeechEngineOhos` + `texttospeechproxy` (CoreSpeechKit) + `QOhosExpected<T,E>` |
| **Serial port** | ❌ | ✅ `ohos` serial port backend: `QtOhosSerialManager` (`BaudRates`/`DataBits`/`Parity`/`StopBits`/`OhosSerialPort`/`OhosSerialAttribute`) + `QOhosUsbManager` |
| **Style** | ✅ `QHarmonyStyle` (1499-line implementation) | ✅ `QOhosStyle` |
| **Font database** | ✅ `QOhFontDatabase` (inherits `QGenericUnixFontDatabase`) | ✅ `QOhosPlatformFontDatabase` (inherits `QFontconfigDatabase`, uses the bundled fontconfig) |
| **Deployment tool** | ❌ | ✅ `openharmonydeployqt` packaging tool |
| **DevEco template** | Simple EntryAbility | ✅ Full template: `QAbility`/`QAbilityStage`/`QEmbeddedUiExtensionAbility`/`QBundledEmbeddedUiExtensionAbility`/`QEmbeddedComponentCreator`/`QChildProcess`/4 kinds of page nodes/`OhosExportModules` + `libqohos.d.ts` TS declarations |
| **Third-party libraries** | None bundled | ✅ Bundles fontconfig/libjpeg/libpng/openssl |
| **mkspecs** | `openharmony.prf` (app template soname) | ✅ `ohos-clang` toolchain spec + `ohos_deployment.prf` deployment feature |
| **Enum generation** | ❌ | ✅ (if present) |
| **Gesture recognition** | ❌ | ✅ `makeQOhosPinchGestureRecognizer()` (widgets) |

---

## 7. Interface capabilities only in the community edition

### 7.1 Local IPC socket stack

| Interface | Implemented capability |
|------|---------|
| `QOhAbstractLocalSocket` | Local IPC base class: `send(QString)` / `errorString()` / `close()` / `messageReady` signal |
| `QOhLocalSocket` | Client: `connect(address)` / `disconnectFromHost()` / `isConnected()` |
| `QOhLocalServer` | Server: `listen(address)` / `nextPendingConnection()` / `newConnection` signal |
| `QOhLocalConnection` | Connection object accepted by the server |

> The official edition has **no local IPC subsystem at all**.

### 7.2 Full process management

| Interface | Implemented capability |
|------|---------|
| `QOhProcess` | QProcess-style wrapper: `start()` / `startDetached()` / `setMode(Mode)` / `stop()` / `isRunning()` / `pid()` / `errorString()` + `started`/`finished`/`errorOccurred`/`stateChanged` signals |
| `QOhChildProcess` | Native child processes: `startChildProcess()` / `startNativeChildProcess()` / `createNativeChildProcess()` / `createNativeChildProcessWithConfig()` + `StartMode`/`IsolationMode`/`Options`/`Fd`/`Args`/`ChildProcessConfig` structs |
| `getSubProcessPid/AliveState/killSubProcess` | Child process management (non-official API) |

### 7.3 Notification permission management

| Interface | Implemented capability |
|------|---------|
| `QtOh::requestEnableNotification(callback)` | Request notification permission asynchronously |
| `QtOh::requestEnableNotificationSync(timeoutMs)` | Request notification permission synchronously |
| `QtOh::isNotificationEnabled()` | Check whether notifications are enabled |
| `QtOh::openNotificationSettings()` | Open the notification settings page |

### 7.4 Synchronous permission APIs

| Interface | Implemented capability |
|------|---------|
| `QtOh::requestPermissionsSync(permissions, timeoutMs)` | Request a batch of permissions synchronously, with a timeout |
| `QtOh::requestPermissionsOnSettingSync(permissions, timeoutMs)` | Request permissions synchronously via the settings page |

### 7.5 Window decoration control

| Interface | Implemented capability |
|------|---------|
| `QOhWidgetHelper::DecorButtonStyle` | Decoration button style: colorMode/buttonBackgroundSize/spacingBetweenButtons/closeButtonRightMargin |
| `setWindowDecorVisible()` / `windowDecorVisible()` | Window decoration visibility |
| `setWindowShadowRadius()` | Window shadow radius |
| `setWindowTitleMoveEnabled()` | Move the window by dragging the title bar |
| `setWindowTitleButtonVisible(bool, bool, bool)` | Visibility of the title buttons (maximize/minimize/close) |
| `titleButtonRect()` + `titleButtonRectChanged` signal | Title button rect query |
| `removeStartingWindow()` | Remove the starting window |

### 7.6 Vulkan rendering support

| Interface | Implemented capability |
|------|---------|
| `QOhPlatformIntegration::createPlatformVulkanInstance()` | Create a Vulkan instance |
| `QOhPlatformVulkanInstance` | Vulkan instance implementation: `createOrAdoptInstance()` / `createSurface()` |
| `nativeResourceForWindow("vkSurface")` | Get the Vulkan surface |

### 7.7 Other community-only capabilities

| Interface | Implemented capability |
|------|---------|
| `QtOh::Utility` | 27 device/system information query methods (typed return values) |
| `QOhHiAppEvent` | HiAppEvent event reporting (FAULT/STATISTIC/SECURITY/BEHAVIOR) |
| `QtOh::pathFromUri()` / `uriFromPath()` | URI-path conversion |
| `QtOh::setBundleName/ModuleName/AbilityName` | Explicit identity setting |
| `QtOh::setUIEnv(napi_env)` / `uiEnv()` | Direct access to the NAPI environment |
| `QOhWindowFunctions::setNativeNodeRenderFit()` | 16 native node render fit modes |
| `QOhPlatformNativeInterface` | Exposes native resource pointers (UIAbility/UIAbilityContext/nativeSettings/nativeWindow/nativeWindowStage/nativeXComponent/NativeNode/vkSurface) |
| `QOhPlatformCursor` | Override cursor / pixmap cache / `setPos()` / `size()` / per-window cursors |
| `QOhPlatformMenu` / `QOhPlatformMenuItem` | Full platform menu implementation |
| `QOhSystemTrayIcon::ContentType` / `SlotType` | Notification content type (5 values) / notification slot type (5 values) |
| `QOhPlatformClipboard` | Clipboard progress (SDK≥15) / pasteboard observer / singleton |
| `UdmfHelper` | UDMF data conversion: QImage↔PixelMap / UDMF↔MimeData |
| `QOhDisplayManager::screenAt(point)` | Find a screen by coordinates |
| `QOhPlatformScreen::densityPixels()` | Pixel density |
| `WindowStatusType` enum (7 values) | Window status type |
| `WindowState` enum (5 values) | Window state |
| `QOhCompatibility` | SDK version resilience layer: `OhosFunction<>` template (dlsym + fallback) |
| `QOhFileEngineHandler` | OpenHarmony file engine (URI/rawdir) |
| `isFreeWindowEnable()` | Free-window capability check |
| `isOpenHarmonyDevice()` | OpenHarmony device check |
| NFC support | `qnearfieldmanager` / `qnearfieldtarget` / `qllcpsocket` / `qllcpserver` + `qjscontroller`/`qjstag` + ArkTS bridging |
| Bluetooth GATT/LE | `qlowenergycontroller_ohos` + `lowenergynotificationhub` + `qjsble` |
| Bluetooth service discovery | `qbluetoothservicediscoveryagent_ohos` |
| Bluetooth service info | `qbluetoothserviceinfo_ohos` |
| Input method C API controller | `InputMethod::QOhController` (uses the native C API `inputmethod_controller_capi.h`) |
| Input method capability query | `QOhPlatformInputContext::hasCapability()` |
| Input method ignores mouse | `QOhPlatformInputContext::ignoreMouse()` |
| Static input method access | `QOhPlatformInputContext::ohInputContext()` (static) |
| Qt main thread dispatch template family | `runOnQtMainThread()` / `runOnQtMainThreadWithResult()` / `runOnQtMainThreadAndWait()` / `runOnQtMainThreadLater()` |
| NAPI macro set | `GET_AND_THROW_LAST_ERROR` / `NAPI_ASSERT_*` / `NAPI_CALL_*` / `DECLARE_NAPI_*` |

---

## 8. Interface capabilities only in the official edition

### 8.1 Centralized QPA function interface

| Interface | Implemented capability |
|------|---------|
| `QtOhos::QOhosQpaFunctions` | **A unified interface of 60+ pure virtual functions**: window operations (15+) / theme configuration (6) / clipboard (3) / file operations (2) / context menu (2) / screen ID (3) / Ability lifecycle (4) / Want management (3) / process management (4) / Ability start (3) / permission management (5) / serial port (2) / file sharing (5) / ShareKit (1) / link opening (1) / distributed data (3) / accessibility (1) / audio streams (2) |

### 8.2 Distributed data objects

| Interface | Implemented capability |
|------|---------|
| `QOhosDistributedDataObject` | Cross-device data sync: `create(QJsonObject)` / `get(key)` / `fieldNames()` / `addAssets(files)` / `assetKey()` / `assets()` / `areAssetsSynced()` / `sessionId()` / `save(deviceId)` |
| Signals | `dataChanged(sessionId, changedFields)` / `statusChanged(sessionId, networkId, Status)` / `progressChanged(sessionId, progress)` / `saveFinished(success)` |
| `QOhosQpaFunctions::genDistributedDataObjectSessionId()` | Generate a session ID |
| `QOhosQpaFunctions::tryGetDistributedFilesDir()` | Get the distributed files directory |

### 8.3 ShareKit share framework

| Interface | Implemented capability |
|------|---------|
| `QOhosSharedRecord` | Shared record abstract class (13 properties): mimeType/content/filePath/isUrlContent/title/label/description/thumbnail/thumbnailFilePath/extraData |
| `QOhosShareControllerOptions` | Controller options: anchor (QPoint/QRect)/single selection mode/preview mode/excluded Abilities |
| `QOhosShareOperationResult` | Share operation result: targetAbilityName() |
| `ShareAbilityType` enum | CopyToPasteboard/SaveToMediaAsset/SaveAsFile/Print/SaveToSuperHub |
| Factory functions | `createContentRecord()` / `createFileRecord()` / `createUrlRecord()` / `createControllerOptions()` |

### 8.4 Ability continuation (distributed migration)

| Interface | Implemented capability |
|------|---------|
| `QOhosOnContinueContext` | Migration context: `setAgreeResponse()` / `setRejectResponse()` / `setMismatchResponse()` / `setResponseOnDistributedDataObjectsSaveResults()` / `setExitAppOnSourceDeviceAfterMigration()` / `sourceApplicationVersionCode()` / `targetDeviceId()` |
| `QOhosAbilityContext::setContinuationActive(bool)` | Set continuation active |
| `tryGetOnContinueData(want)` | Get continuation data |
| `tryRestoreOnContinueDistributedDataObjects(want)` | Restore distributed data objects |
| `continueRequestReceived` signal | Continue request notification |

### 8.5 Advanced window control

| Interface | Implemented capability |
|------|---------|
| Window brightness/contrast/saturation | `setBrightness()` / `setContrast()` / `setSaturation()` |
| Window maximize options | `MaximizePresentation` (4 values) / `AcrossDisplayPresentation` (3 values) / snapshot animation configuration |
| Drag key frame policy | `setInterval(ms)` / `setDistance(px)` / `setAnimationDuration(ms)` / `setAnimationDelay(ms)` |
| Float window hint | `setShowWindowAsFloatWindowHint()` |
| Native window/screen ID | `tryGetNativeWindowId()` / `tryGetScreenDisplayId()` |
| Ability-window binding key | `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| Window property tag system | 12 static property descriptors `QOhosPropertyDescriptor<T>` |
| Non-client area pointer events | `onNonClientAreaPointerPress/Move/Release()` |
| Safe area margins | `safeAreaMargins()` |
| Window snapshot | `makeSnapshot()` |
| Window decoration presets | `DecorationPreset` (Standard/Frameless) |
| Two-way OHOS↔Qt state sync | `setWindowStateFromOhos()` and 7+ other callbacks |
| Fixed window size | `windowFixedSizeStateProperty` |
| Template property system | `setWindowOrWidgetProperty<T>()` / `tryGetWindowOrWidgetProperty<T>()` |
| Type-safe window lookup | `fromQWindow()` / `fromQWindowOrNull()` (static) |

### 8.6 Screens/color picking

| Interface | Implemented capability |
|------|---------|
| `startPickingColorFromScreenWithConsumer()` | Pick a color from the screen |
| `tryGetNativeWindowId()` | Get the native window ID |
| `tryGetScreenDisplayId()` | Get the screen display ID |
| `QOhosScreenManager` | Multi-screen management: `rebuildScreenList()` / `platformScreenForDisplayIdOrNull()` |
| `QOhosPlatformScreen::notifyWindowVisibleAndActivated()` | Compositor API — window visibility tracking |
| `QOhosPlatformScreen::fromQScreen()` (static) | Reverse lookup from a QScreen |

### 8.7 Audio stream usage hints

| Interface | Implemented capability |
|------|---------|
| `AudioStreamUsageHint` enum | 14 values: Music/VoiceCommunication/VoiceAssistant/Alarm/VoiceMessage/Ringtone/Notification/Accessibility/Movie/Game/Audiobook/Navigation/VideoCommunication/Unknown |
| `setAudioStreamUsageHintProperty(QObject*, hint)` | Set the stream usage hint on an audio object |
| `tryGetAudioStreamUsageHintProperty(QObject*, hint*)` | Get the stream usage hint of an audio object |

### 8.8 Thread bridging infrastructure

| Interface | Implemented capability |
|------|---------|
| `QOhosJsState` | JS state abstraction: `env()` / `defaultWindowStageOrEmpty()` / `defaultUiContextOrEmpty()` / `tryGetJsWindowByQWindow()` / `tryGetQAbilityByQWindow()` / `defaultQAbility()` / `appLaunchWant()` / `eval<T>()` / `evalToPromiseOrRejectOnThrow()` / `mapOhosEnumToJs<Enum>()` |
| `QOhosJsThreadGateway` | Thread-safe JS calls: `invoke()` / `invokeAndWaitForContinue()` / `runAndWait()` / `eval<Func>()` (with a static_assert that prevents NAPI values from leaking) / `evalWithPromise<T>()` |
| `QOhosJsThreadOps` | JS thread operation registration: `registerInstance()` / `instance()` |
| `QObjectThreadSafeRef` / `QThreadSafeRef<T>` | Thread-safe QObject references: `visitInQtThreadIfAlive()` |
| `QtState` | Qt thread state: `isQtThread()` / `invokeTask()` / `qpaFunctions()` |
| `OhosEnumMeta<Enum>` | Enum-to-JS mapping template + `OhosEnumInfo` / `OhosEnumFullTypeNameFetcher` SFINAE |
| `makeProxyWithJsThreadDeleter<T>()` | JS-thread-safe deleter proxy |
| `QOhosTaskPromise<Args...>` | Promise chain tracking: `makeChained()` / `makeBranched()` / `makeThenCatchBranches()` + dead promise detection |
| `QOhosOptional<T>` | Full Optional type: `andThen()` / `transform()` + comparison operators |
| `QOhosSpan<T>` | Array view: `begin()` / `end()` / `subspan()` / `as_bytes()` |
| `QOhosMutexProtectedValue<T>` | Mutex-protected value: `processValue()` / `evalWithValue()` |
| `QOhosNamedFunc` | Named function wrapper |

### 8.9 Other official-only capabilities

| Interface | Implemented capability |
|------|---------|
| `QOhosAppContext::restartApp()` | App restart (with an optional Want) |
| `QOhosAppContext::getAppLaunchWant/WantInfo()` | Get the app launch Want |
| `QOhosAppContext::fontSizeScale()` | Font size scaling |
| `QOhosAppContext::enableContextMenuEventOnLongPress()` | Context menu on long press |
| `QOhosAppContext::getBundleInfo()` | Bundle info |
| `QOhosAppContext::isNoUiChildMode()/startNoUiChildProcess()` | No-UI child process |
| `QOhosAppContext::hasSerialPortAccessRight()` | Serial port permission |
| `QOhosFileUtils::moveFileToTrash()` | Move to trash |
| `QOhosFileUtils::authorizeFilePath()` | File path authorization |
| `QOhosPasteboard::setInAppOnlyPasteboardShareOption()` | Restrict clipboard sharing to within the app |
| `QOhosQpaFunctions::getImageDataFromPasteboard/getTextDataFromPasteboard()` | Read clipboard data |
| `QOhosQpaFunctions::setDarkThemeEnabled()` / `makeOhosConfigDarkModeFlagDataSource()` | Dark theme data source (reactive) |
| `QOhosQpaFunctions::getFontSizeScale()` / `makeOhosConfigFontSizeScaleDataSource()` | Font size data source (reactive) |
| `QOhosCloseEventContext` | Close event context: `CloseRootCause` (4 values) / `CloseResolution` enum |
| `QOhosSystemLocale` | System locale integration |
| `QOhosPlatformBackingStore` | Multi-window dirty region merging + deferred flushing + GL BackingStore |
| `QOhosEGLPlatformContext` | Structured CreateInfo + custom swapBuffers |
| `QOhosPlatformDrag` | Pre-/post-drop drag hooks |
| `QOhosApplicationStateTracker` | Application state tracking |
| `QOhosDeadlockProtector` | Deadlock detection |
| `QOhosBigDataEventLogging` | Big data event logging |
| `QOhosDeviceInfo` | 32 device properties + `RecognizedDeviceType` (3 values) + `isCurrentDeviceSupported()` |
| `QOhosPropertyDescriptor<T>` | Type-safe property descriptors + `QOhosPropertiesStore` |
| Input method state machine | `ImConnectionState` (Attached/Detached) + `dispatchRequestedImConnectionStateChange()` |
| Input method's own enums | `TextInputType` (10 values) + `EnterKeyType` (9 values) + `Direction` (4 values) + `OhosEnumMeta` |
| Input method cursor query | `tryQueryCursorPosition()` |
| Input method functional key events | `sendFocusObjectFunctionalKeyEvent()` |
| Network bearer plugin | WiFi/cellular/Bluetooth/Ethernet/VPN |
| Map services (MapKit) | Tiled maps/geocoding/routing/place search/POI |
| Text to speech (TTS) | CoreSpeechKit proxy |
| Serial port support | `QtOhosSerialManager` + `QOhosUsbManager` |
| `openharmonydeployqt` | Deployment packaging tool |
| Bundled third-party libraries | fontconfig / libjpeg / libpng / openssl |
| Full DevEco template | QAbility/QAbilityStage/embedded extensions/child processes/4 kinds of page nodes/OhosExportModules/libqohos.d.ts |
| Deadlock detection | `QOhosDeadlockProtector` |
| Big data event logging | `QOhosBigDataEventLogging` |
| Gesture recognizers | `makeQOhosPinchGestureRecognizer()` (pinch gesture) |

---

## 9. API paradigm differences in shared interfaces

### 9.1 Object creation pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Object creation | Direct `new` / stack construction | Factory functions return `QSharedPointer<T>` |
| Class concreteness | Concrete classes with implementations | Abstract classes, all pure virtual functions |
| Lifetime | Managed manually / Qt parent objects | `QSharedPointer` reference counting |
| Smart pointers | `QScopedPointer` | `std::unique_ptr` / `std::shared_ptr` |

### 9.2 Permission request pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Calling style | Synchronous: `bool result = requestPermissionFromUser(permission)` | Asynchronous: `requestPermissionFromUserIfNeeded(permission)` → void |
| Getting the result | Direct return value | Signal notification: `permissionRequestResponseReceived(Permission, bool)` |
| Timeout control | ✅ `timeoutMs` parameter | ❌ no timeout |
| Permission type | String `QString` | Typed enum `Permission` + string overloads |
| Notification permission | ✅ fully supported | ❌ does not exist |

### 9.3 Ability result return pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Result delivery | Callback class `QAbilityResultReceiver::handleResult(Napi::Value err, Napi::Value result)` | Qt signal `startAbilityForResultResponseReceived(QByteArray requestId, int resultCode, QSharedPointer<QOhosWant> want)` |
| Error delivery | Callback parameter `Napi::Value err` | Separate signal `startAbilityForResultErrorResponseReceived(QByteArray requestId)` |
| Request identification | ❌ not tracked | ✅ `QByteArray requestId` |
| NAPI dependency | ✅ the public API depends on NAPI | ❌ the public API has no NAPI dependency |

### 9.4 File sharing API pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Function signature | `static Error persistPermission(Policys, Results &results)` | `QSharedPointer<ActionResult> persistPermission(QList<PathPolicy>)` |
| Return value | Enum error code + output parameter | Abstract result object wrapped in a smart pointer |
| Accessing results | Iterate the `Results` list directly | `ActionResult::operationStatus()` + `ActionResult::errorInfoList()` |

### 9.5 StartOptions configuration pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Construction | `QOpenHarmonyStartOptions options; options.windowMode = 1;` | `auto options = createStartOptions(); options->setWindowMode(WindowMode::FULLSCREEN);` |
| Type safety | ❌ raw int assignment | ✅ strongly typed enums + virtual setters |
| Extensibility | Requires changing the struct | Just add a virtual function |

### 9.6 Window helper API pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Usage | `QOhWidgetHelper *helper = new QOhWidgetHelper(widget); helper->setPrivacyMode(true);` | `QOhosWindowUtils::setWindowPrivacyMode(window, true);` |
| Bound object | Bound to a specific QWidget/QWindow instance | The target QWidget/QWindow is passed on every call |
| State management | The instance maintains state | Stateless function calls |

### 9.7 Window identity/property pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Window identity | Name strings (`windowName`/`parentWindowName`/`transientParentName`) | Typed `InternalWindowId` + property tags (`subWindowOfTagProperty`/`mainWindowTagProperty`/`floatWindowTagProperty`) |
| Setting window properties | Set directly through instance virtual functions (`setNativeNodeRenderFit`/`setNativeNodeBackgroundColor`) | Template property descriptors `QOhosPropertyDescriptor<T>` + static methods + QPA functions |
| Property query | ❌ | ✅ `tryGetWindowOrWidgetProperty<T,propertyPtr>()` |
| Property write callbacks | ❌ | ✅ `QOhosPropertiesStore::addPropertyWriteCallback<T,propertyPtr>()` |

### 9.8 Thread bridging pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| JS thread dispatch | `QtOh::runOnJsUIThreadNoWait(lambda)` — simple wrapper | `QOhosJsThreadGateway::invoke(lambda)` — with deadlock protection + wait-for-continue |
| Dispatch with return value | `runOnJsUIThreadWithResult<T>()` template (direct `uv_queue_work` + `std::promise`) | `QOhosJsThreadGateway::eval<Func>()` (with a `static_assert` that prevents NAPI values from leaking outside the JS thread) |
| Promise dispatch | `runOnJsUIThreadWithPromise<ReturnType>()` template | `QOhosJsThreadGateway::evalWithPromise<T>()` + `QOhosTaskPromise` chain tracking |
| NAPI leak protection | ❌ | ✅ blocked at compile time by `static_assert` |

### 9.9 Device information pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Interface style | `QtOh::Utility` class; static methods return typed `QString`/`int` | `QOhosDeviceInfo` namespace; `Type` enum + `getProperty(Type)` returns `QVariant` |
| Device type | `DeviceType` bit-flag enum (9 values) | `RecognizedDeviceType` enum (3 values: _2in1/tablet/phone) + `tryGetRecognizedDeviceType()` |
| Detection methods | `isTabletDevice()`/`isPhoneDevice()` (in `qohauxiliary.h`) | `isTablet()`/`is2in1()`/`isPhone()`/`isCurrentDeviceSupported()` (in `qohosdeviceinfo_p.h`) |
| Edition-specific properties | `productSeries` | `hardwareProfile`/`serial`/`majorVersion`/`seniorVersion`/`featureVersion`/`buildVersion`/`udid` |

### 9.10 Input method pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Controller | `InputMethod::QOhController` (external, delegates to the C API `inputmethod_controller_capi.h`) | `QOhosInputMethodProxy` (internal) + `ImConnectionState` state machine (Attached/Detached) |
| Event filtering | `filterEvent(QEvent*)` override | `eventFilter(QObject*, QEvent*)` override |
| Text/enter key types | No own enums; uses the C API types + conversion functions `ohEnterKeyType()`/`ohTextInputType()` | ✅ own `TextInputType` (10 values) + `EnterKeyType` (9 values) + `OhosEnumMeta` JS mapping |
| Cursor handling | `setKeyboardRect()` + private slots | `updateOhosCursor()` + `onCursorRectangleChanged()` + `tryQueryCursorPosition()` |
| Keyboard visibility tracking | ❌ | ✅ `setSoftwareKeyboardVisibilityStatus()` |
| Input method connection management | ❌ | ✅ `attachToInputMethodController()` / `detachFromInputMethodController()` / `dispatchRequestedImConnectionStateChange()` |

---

## 10. Summary

### 10.1 Capability coverage comparison

| Capability area | Community edition | Official edition |
|---------|--------|--------|
| QPA platform abstraction | ✅ complete | ✅ complete and richer |
| Ability lifecycle | ✅ basic support | ✅ full support (including continuation/migration/multiple instances/instance destruction control) |
| Window management | ✅ basic property control + decoration control | ✅ advanced property control (brightness/contrast/saturation/maximize options/key frame policy/safe area/non-client area) |
| Permission management | ✅ synchronous + asynchronous | ✅ asynchronous only (typed enums) |
| Process management | ✅ full QProcess style + native child processes | ✅ simplified startAppProcess/startNoUiChildProcess |
| Local IPC | ✅ full socket stack | ❌ does not exist |
| Distributed data | ❌ | ✅ full distributed data objects |
| Sharing | ❌ | ✅ full ShareKit framework |
| File operations | ✅ file sharing | ✅ file sharing + trash + path authorization |
| Notification permission | ✅ complete | ❌ does not exist |
| Serial port | ❌ | ✅ serial port permission + serial port manager |
| Multimedia | ✅ playback/recording/camera/audio | ✅ playback/recording/camera/audio + audio stream usage hints |
| Bluetooth | ✅ complete (including GATT/LE/NFC) | ✅ basic (no GATT/LE/service discovery/NFC) |
| Location | ✅ position info | ✅ position info + satellite info + map services |
| Sensors | ✅ 9 kinds of sensors | ✅ 5 kinds of sensors |
| WebView | ✅ basic | ✅ complete (controller/component listener/resource errors) |
| Text to speech | ❌ | ✅ TTS |
| Network | ❌ | ✅ Bearer plugin |
| Printing | ✅ basic printing | ✅ native printing (connect/jobs/query/manage) |
| Style | ✅ QHarmonyStyle | ✅ QOhosStyle |
| Accessibility | ✅ basic notifications | ✅ full subsystem (17+ file pairs) |
| Vulkan | ✅ fully supported | ❌ not supported |
| Deployment tool | ❌ | ✅ openharmonydeployqt |
| Third-party libraries | None bundled | ✅ bundles fontconfig/libjpeg/libpng/openssl |
| Thread bridging | ✅ direct uv_queue_work templates | ✅ full abstraction layer (JsState/JsThreadGateway/JsThreadOps/QtState/ThreadSafeRef/TaskPromise) |
| Close events | ❌ | ✅ CloseEventContext |
| Deadlock detection | ❌ | ✅ DeadlockProtector |
| Window property system | ❌ name strings | ✅ type-safe property descriptors |
| Input method | ✅ C API controller | ✅ JS/NAPI proxy + state machine + own enums |
| Device information | ✅ 27 methods + bit-flag enum | ✅ 32 properties + recognized device type enum |
| Logging | ✅ basic macros | ✅ full logging system |
| UDMF | ✅ UdmfHelper | ❌ |
| SDK resilience | ✅ QOhCompatibility (dlsym + fallback) | ❌ (SDK conditional compilation) |

### 10.2 Differences in design philosophy

Design philosophy of the **community edition**:
- **Practicality first**: provides synchronous APIs for convenience in simple scenarios
- **Direct exposure**: public APIs depend directly on NAPI and expose native resource pointers
- **Instance management**: window helpers manage state through instance classes
- **Rich but not unified**: capabilities are scattered across multiple namespaces and classes
- **Process/IPC oriented**: provides full process management and a local IPC stack
- **Native C API oriented**: the input method uses `inputmethod_controller_capi.h`; the clipboard uses `OH_Pasteboard`
- **SDK resilience**: `QOhCompatibility` provides a dlsym + fallback mechanism
- **Platform abstraction extensions**: adds the `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` abstractions in `gui/kernel`

Design philosophy of the **official edition**:
- **Abstraction first**: everything is abstract classes + factory functions, hiding implementation details
- **Asynchronous first**: permission and Ability results are all delivered asynchronously through signals
- **Type safety**: strongly typed enums replace raw ints, QJsonObject replaces QVariantMap, property descriptors replace name strings
- **Centralized and unified**: the 60+-method `QOhosQpaFunctions` unified interface
- **Lifetime management**: `QSharedPointer` + RAII manage object lifetimes
- **NAPI encapsulation**: public APIs hide NAPI completely; `static_assert` blocks NAPI values from leaking at compile time
- **Advanced features**: distributed data/ShareKit/Ability continuation/window brightness, contrast and saturation/audio stream hints and more
- **Engineering**: deployment tool/deadlock detection/full template/bundled third-party libraries/multi-screen management
- **JS/NAPI bridging**: the input method uses `QOhosInputMethodProxy` (JS/NAPI) with its own enums + `OhosEnumMeta`

### 10.3 Migration notes

When migrating from the community edition to the official edition, note the following:

1. **Renaming**: `QOh*` → `QOhos*`, `QtOh::` → `QtOhosExtras::`, `QOpenHarmony*` → `QOhos*`, `openharmony` → `ohos`
2. **API paradigm conversion**: synchronous calls → asynchronous signals; callback classes → Qt signals; direct construction → factory functions + `QSharedPointer`
3. **Type conversion**: `QVariantMap` → `QJsonObject`; `int` flags → strongly typed enums; `QPixmap` → `QImage`
4. **IPC migration**: `QOhLocalSocket/Server` must be replaced with another IPC mechanism (such as `startAppProcess`)
5. **Process management migration**: `QOhProcess/QOhChildProcess` must be replaced with `startAppProcess()/startNoUiChildProcess()`
6. **Notification permission migration**: the community edition's `QtOh::requestEnableNotification()` and related functions must be implemented yourself or removed
7. **Window decoration migration**: `DecorButtonStyle`/`setWindowShadowRadius`/`setWindowTitleButtonVisible` and similar have no counterpart interfaces
8. **Vulkan migration**: if you render with Vulkan, the official edition does not support it; switch to OpenGL/EGL
9. **Removing the NAPI dependency**: public APIs no longer depend on `QtNapi/napi.h`; replace `QAbilityResultReceiver` with signal connections
10. **Platform abstraction migration**: the `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` abstractions in `gui/kernel` no longer exist; the capabilities live in `QOhosQpaFunctions`
11. **Device information migration**: `QtOh::Utility` static methods → `QOhosDeviceInfo` namespace + `Type` enum + `QVariant` return values
12. **Input method migration**: `InputMethod::QOhController` (C API) → `QOhosInputMethodProxy` (JS/NAPI) + own enums
13. **Window identity migration**: name strings (`windowName`) → property tags (`subWindowOfTagProperty`)
14. **Render fit migration**: 16-value `NativeNodeRenderFit` → 2-value `NativeNodeRenderFitPolicy`
15. **Taking advantage of new capabilities**: you can use the official edition's new capabilities, such as distributed data objects/ShareKit/Ability continuation/audio stream hints/serial port/TTS/map services
