# Qt HarmonyOS Porting API Differences

> **Community edition**: `/qt-sig` (module name `QtOhExtras`, naming prefixes `QOh`/`QOpenHarmony`)
> **Official edition**: `/qt5.15.16` (module name `QtOhosExtras`, naming prefix `QOhos`)
>
> This document compares how the two editions implement their interfaces for porting to HarmonyOS (OpenHarmony/HarmonyOS), covering the differences in the scope of implemented capabilities, API design paradigms, and architectural layers.

---

## Table of contents

1. [Overall architecture differences](#1-overall-architecture-differences)
2. [Naming convention differences](#2-naming-convention-differences)
3. [QPA platform plugin interface comparison](#3-qpa-platform-plugin-interface-comparison)
4. [Corelib kernel support interface comparison](#4-corelib-kernel-support-interface-comparison)
5. [Extras module public API comparison](#5-extras-module-public-api-comparison)
6. [Feature module plugin interface comparison](#6-feature-module-plugin-interface-comparison)
7. [Interface capabilities only in the community edition](#7-interface-capabilities-only-in-the-community-edition)
8. [Interface capabilities only in the official edition](#8-interface-capabilities-only-in-the-official-edition)
9. [API paradigm differences in shared interfaces](#9-api-paradigm-differences-in-shared-interfaces)
10. [Summary](#10-summary)

---

## 1. Overall architecture differences

| Dimension | Community edition (qt-sig) | Official edition (qt-5.15.16) |
|------|----------------|-------------------|
| **Design paradigm** | Concrete classes + synchronous APIs + NAPI callbacks | Abstract classes + factory functions + `QSharedPointer` lifetimes + asynchronous signals |
| **Naming prefix** | `QOh` / `QOpenHarmony` / `QtOh` | `QOhos` / `QtOhos` / `QtOhosExtras` |
| **Extras module name** | `QtOhExtras` (`qtohextras`) | `QtOhosExtras` (`qtohosextras`) |
| **Export macro** | `Q_OPENHARMONYEXTRAS_EXPORT` | `Q_OHOS_EXTRAS_EXPORT` |
| **NAPI dependency** | Public APIs depend directly on `QtNapi/napi.h` | Public APIs hide NAPI completely |
| **Want parameter type** | `QVariantMap` | `QJsonObject` |
| **StartOptions** | Plain struct, assigned directly | Abstract class; virtual setters + factory creation |
| **Permission requests** | Synchronous bool return | Asynchronous void + signal notification |
| **Result return** | Callback class (`QAbilityResultReceiver`) | Qt signals |
| **Error handling** | Enum error codes + output parameters | `QOhosOperationStatus` abstract object |
| **Window helpers** | Instance class (`QOhWidgetHelper`) | Free functions in a namespace (`QOhosWindowUtils`) |
| **License** | LGPL (iSoftStone) | Qt Commercial / LGPL-3.0 / GPL |
| **Number of public headers** | 13 | 22 + 10 private |
| **Number of QPA files** | ~120 | ~133 |
| **Third-party libraries** | None bundled | Bundles fontconfig / libjpeg / libpng / openssl |
| **Deployment tool** | None | `openharmonydeployqt` |
| **DevEco template** | Simple EntryAbility | Full template including QAbility/QAbilityStage/embedded extensions/child processes |

---

## 2. Naming convention differences

### 2.1 Prefix mapping

| Community edition | Official edition | Notes |
|--------|--------|------|
| `openharmony` (directory/plugin name) | `ohos` (directory/plugin name) | Platform adaptation directory naming |
| `QtOhExtras` | `QtOhosExtras` | Extras module name |
| `QOh*` / `QOpenHarmony*` | `QOhos*` | Class name prefix |
| `QtOh::` | `QtOhosExtras::` | Namespace |
| `Q_OPENHARMONYEXTRAS_EXPORT` | `Q_OHOS_EXTRAS_EXPORT` | Export macro |
| `qopenharmonyextrasglobal.h` | `qtohosextrasglobal.h` | Global header |
| `Q_OS_OPENHARMONY` | `Q_OS_OHOS` | Compile-time macro |

### 2.2 Key class name mapping

| Community edition class | Official edition class |
|-----------|-----------|
| `QOhAppContext` | `QOhosAppContext` |
| `QOHFileShare` | `QtOhosExtras::FileShare` |
| `QOhWidgetHelper` | `QtOhosExtras::QOhosWindowUtils` |
| `QOhProcess` | (no direct counterpart; use `startAppProcess()` / `startNoUiChildProcess()`) |
| `QOhChildProcess` | (no direct counterpart; use `startNoUiChildProcess()`) |
| `QOpenHarmonyAbility` (namespace) | `QtOhosExtras::QOhosAbilityContext` |
| `QOpenHarmonyWant` | `QOhosWant` |
| `QOpenHarmonyStartOptions` | `QOhosStartOptions` |
| `QOhAbstractLocalSocket` | (no counterpart) |
| `QOhLocalServer` / `QOhLocalSocket` | (no counterpart) |
| `QOhWindowFunctions` | `QOhosFunctions` |
| `QtOh::Utility` | (no counterpart) |

---

## 3. QPA platform plugin interface comparison

### 3.1 PlatformIntegration (platform integration)

| Capability | Community edition `QOhPlatformIntegration` | Official edition `QOhosPlatformIntegration` |
|---------|-------------------------------|--------------------------------|
| Window/BackingStore/OpenGL context creation | ✅ | ✅ |
| Event dispatcher | ✅ | ✅ |
| Fonts/clipboard/drag and drop/input method/services | ✅ | ✅ |
| Theme management | ✅ `QOhPlatformTheme` | ✅ `QOhosPlatformTheme` |
| Accessibility | ✅ conditional on SDK > 13 | ✅ unconditional + `tryInitializeAccessibilityForQWindowWithXComponent()` |
| Touch device management | ✅ `touchDevice()` / `setTouchDevice()` | ❌ handled internally |
| Keyboard modifier query | ✅ `queryKeyboardModifiers()` | ❌ |
| Vulkan support | ✅ `createPlatformVulkanInstance()` | ❌ |
| Ability control hook | ✅ `abilityCtrl()` → `QPlatformAbilityCtrl` | ❌ implemented via `QOhosQpaFunctions` |
| Access control hook | ✅ `accessCtrl()` → `QPlatformAccessCtrl` | ❌ |
| System locale | ❌ | ✅ `systemLocale()` / `setSystemLocale()` |
| Window geometry persistence policy | ❌ | ✅ `WindowGeometryPersistencePolicy` enum + global setting |
| Context menu on long press | ❌ | ✅ `setContextMenuOnLongPressEnabled()` / `getSyntheticQPointForContextMenuOnLongPress()` |
| Static dark theme control | ❌ | ✅ `setDarkThemeEnabled()` (static) |
| Singleton access | ❌ | ✅ `instance()` (static) |
| Pre-initialized display metrics | ❌ | ✅ `setDefaultDisplayMetrics()` (static) |

### 3.2 PlatformWindow (platform window)

| Capability | Community edition `QOhPlatformWindow` | Official edition `QOhosPlatformWindow` |
|---------|------------------------|---------------------------|
| Basic window operations (geometry/visibility/cursor/parent-child) | ✅ | ✅ |
| Window property tag system | ❌ set directly through virtual functions | ✅ 13 static property descriptors (`QOhosPropertyDescriptor<T>`) |
| Sub-window/main window/float window tags | ❌ | ✅ `tagWindowOrWidgetAsSubWindowOf()` / `tagWindowOrWidgetAsMainWindow()` / `tagWindowOrWidgetAsFloatWindow()` |
| Widget-window host tag | ❌ | ✅ `tagWidgetWindowAsHostOfWidget()` |
| Privacy mode | ✅ `QOhWidgetHelper::setPrivacyMode()` | ✅ static `setWindowPrivacyMode()` |
| Window corner radius | ✅ `QOhWidgetHelper` | ✅ static `setWindowCornerRadius()` |
| Window brightness/contrast/saturation | ❌ | ✅ `setBrightness()` / `setContrast()` / `setSaturation()` |
| Drag to resize | ✅ `setResizeByDragEnabled()` | ✅ static `setWindowDragResizable()` |
| Drag key frame policy | ❌ | ✅ `setWindowDragKeyFramePolicy()` |
| Window maximize options | ❌ | ✅ `setWindowMaximizeOptions()` / `clearWindowMaximizeOptions()` |
| Float window hint | ❌ | ✅ `setShowWindowAsFloatWindowHint()` |
| Window geometry persistence hint | ✅ `setWindowRectAutoSave()` (per instance) | ✅ `setMainWindowGeometryPersistenceHint()` (global, 3 policies) |
| Native window ID | ❌ | ✅ `tryGetNativeWindowId()` |
| Screen display ID | ❌ | ✅ `tryGetScreenDisplayId()` |
| Safe area margins | ❌ | ✅ `safeAreaMargins()` |
| Actual frame margins | ✅ `setFrameMargins()` (no-op) | ✅ `frameMargins()` (real implementation) |
| Window snapshot | ❌ | ✅ `makeSnapshot()` |
| Window decoration presets | ❌ | ✅ `DecorationPreset` (Standard/Frameless) |
| Non-client area pointer events | ❌ | ✅ `onNonClientAreaPointerPress/Move/Release()` |
| Surface consumer API | ❌ | ✅ `setSurfaceConsumer()` |
| OHOS→Qt state callbacks | ❌ one-way (Qt→OHOS) | ✅ two-way: `setWindowStateFromOhos()`, `setWindowGeometryFromOhos()`, `setExposedFromOhos()`, `setDisplayIdFromOhos()`, `notifyWindowDestroyedFromOhos()` and so on |
| DPI change handling | ❌ | ✅ `handleDpiChange()` |
| Window flag management | ❌ | ✅ `setWindowFlags()` / `windowFlags()` / `platformWindowFlagsForQWindow()` |
| Window activation request | ❌ | ✅ `requestActivateWindow()` |
| Soft keyboard needed flag | ❌ | ✅ `setNeedSoftKeyboard()` |
| Close event root cause | ❌ | ✅ `CloseEventRootCause` enum |
| Ability-QWindow binding key | ❌ | ✅ `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| Close popups | ❌ | ✅ `closeAllActivePopups()` (static) |
| Direct access to the window node | ✅ `nativeWindowNode()` → `QOhWindowNode*` | ❌ replaced by the property system |
| Manually triggered expose | ✅ `fireFullExpose()` / `fireExpose()` | ❌ handled internally |
| XComponent size | ✅ `xcomponentSize()` | ❌ |
| Decoration button style | ✅ `DecorButtonStyle` struct | ❌ |
| Decoration visibility | ✅ `windowDecorVisible()` / `setWindowDecorVisible()` | ❌ |
| Window shadow radius | ✅ `setWindowShadowRadius()` | ❌ |
| Move by title bar/button visibility | ✅ `setWindowTitleMoveEnabled()` / `setWindowTitleButtonVisible()` | ❌ |
| Title button rect | ✅ `titleButtonRect()` + signal | ❌ |
| Remove starting window | ✅ `removeStartingWindow()` | ❌ |

### 3.3 NativeInterface (native interface)

| Capability | Community edition `QOhPlatformNativeInterface` | Official edition `QOhosPlatformNativeInterface` |
|---------|-----------------------------------|-------------------------------------|
| Exposes native resource pointers | ✅ `"UIAbility"`, `"UIAbilityContext"`, `"nativeSettings"` | ❌ does not expose native pointers |
| Window-level native resources | ✅ `"nativeXComponent"`, `"NativeNode"`, `"nativeWindow"`, `"nativeWindowStage"`, `"vkSurface"` | ❌ |
| Platform functions | ✅ `setNativeNodeRenderFit`, `setNativeNodeRenderBackgroundColor` | ✅ `tagWindowOrWidgetAsSubWindowOf`, `getWindowOrWidgetAsSubWindowOfTagValue`, `tagWindowOrWidgetAsMainWindow`, `setInAppOnlyPasteboardShareOption`, `tagWidgetWindowAsHostOfWidget`, `setSurfaceConsumer` |
| Native resource function query | ✅ `"isFreeWindowEnable"` | ❌ |

### 3.4 Other QPA interfaces

| Interface | Community edition | Official edition |
|------|--------|--------|
| **Cursor** | Rich: override cursor/pixmap cache/`setPos()`/`size()`/per-window cursors | Minimal: only `changeCursor()` + `pos()` |
| **System tray** | Full class: `ContentType` (5 values)/`SlotType` (5 values)/light and dark icons | Implementation hidden behind a factory function |
| **Menus** | ✅ `QOhPlatformMenu` + `QOhPlatformMenuItem` | ❌ no `QPlatformMenu` subclass |
| **Drag and drop** | Concrete classes `QOhDrag` + `QOhDropTarget` | Abstract class `QOhosPlatformDrag`: `handlePreDrop()` + `updateDropAction()` |
| **Clipboard** | Direct `OH_Pasteboard` API + progress (SDK≥15) + observer | `QOhosClipboardObject` abstraction + lazy loading + in-app sharing |
| **BackingStore** | Plain `QPlatformBackingStore` + simple `BufferRegionHandler` | `QRasterBackingStore` + `QImageView`/`BufferRegionHandler`/`FlushData`/`WindowContext`/`WindowContextManager` (multi-window dirty region merging + deferred flushing) |
| **GL BackingStore** | ❌ | ✅ `makeGlOhosPlatformBackingStore()` |
| **EGL context** | Plain `QEGLPlatformContext` subclass | Structured `CreateInfo` + overridden `swapBuffers()` + swap state tracking |
| **System locale** | ❌ | ✅ `QOhosSystemLocale`: `query()` / `fallbackUiLocale()` |
| **Screen management** | `QOhDisplayManager`: `allScreens()`/`screenAt()` | `QOhosScreenManager`: `rebuildScreenList()`/display ID lookup |
| **Accessibility** | `QOhPlatformAccessibility::notifyAccessibilityUpdate()` (SDK>13) | Full subsystem: `QOhosAccessibilityTree`/`Provider`/`EventHandler`/`ArkUIHelpers`/`MenuActions`/`TabBars`/`TableModelChangeEventHandler` and others, 17+ file pairs |
| **Application state** | `applicationStateChanged()` (window-level) | Dedicated `QOhosApplicationStateTracker` |
| **Icon engine** | ❌ | ✅ `QOhosPlatformTheme::createIconEngine()` |

---

## 4. Corelib kernel support interface comparison

### 4.1 Centralized platform function interface

| Capability | Community edition | Official edition |
|------|--------|--------|
| **Central API interface** | Scattered across the `QtOh` namespace + the `QtOhPrivate` namespace | ✅ `QtOhos::QOhosQpaFunctions` — **a unified interface of 66+ virtual functions** |

All capability categories covered by the official edition's `QOhosQpaFunctions`:

| Category | Method count | Capabilities |
|------|--------|------|
| Window operations | 15 | Privacy mode/corner radius/background color/keep screen on/drag resizing/key frame policy/maximize options/brightness/contrast/saturation/float window tag/render fit policy/destroy flag/Ability binding |
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

### 4.2 Device/system information

| Capability | Community edition | Official edition |
|------|--------|--------|
| Device information query | ✅ `QtOh::Utility` — **27 static methods** (manufacturer/brand/model/OS version/SDK version/build info/distribution OS info/device type detection) | ✅ `QOhosDeviceInfo` (private implementation) |
| Device type enum | ✅ `DeviceType`: PC/Phone/Wearable/LiteWearable/Tablet/Tv/Car/SmartVision | ✅ `QOhosRuntimeDeviceTypeAndMode` |
| SDK API version | ✅ `QtOh::Utility::sdkApiVersion()` + `QtOh::ohSdkVersion()` | ✅ internal `apiVersion()` |
| Watchdog | ✅ `QOhosWatchdog` (Hicollie): `Init()`/`Stop()`/`SetAppMainThreadState()` | ✅ `QOhosWatchdog` (similar implementation) |
| HiAppEvent | ✅ `QOhHiAppEvent` singleton: event types (FAULT/STATISTIC/SECURITY/BEHAVIOR)/`writeDataTag()` | ❌ replaced by `QOhosBigDataEventLogging` |
| Logging infrastructure | Simple `LOGI/D/W/E` macros | ✅ full logging system: `qOhosDebug`/`Warning`/`Critical`/`Fatal`/`DUMP` macros, `qOhosLogMessage()`, `qOhosVPrintf()`, `QCScopedDebug` RAII |
| Deadlock detection | ❌ | ✅ `QOhosDeadlockProtector` |

### 4.3 Thread bridging infrastructure

| Capability | Community edition | Official edition |
|------|--------|--------|
| JS thread dispatch | ✅ `QtOh::runOnJsUIThreadNoWait()` / `runOnJsUIThreadAndWait()` | ✅ `QOhosJsThreadGateway::invoke()` / `runAndWait()` |
| JS thread dispatch with return value | ✅ `runOnJsUIThreadWithResult<>()` template (direct `uv_queue_work` + `std::promise`) | ✅ `QOhosJsThreadGateway::eval<Func>()` / `evalWithPromise<T>()` |
| JS state abstraction | ❌ exposes `napi_env` directly | ✅ `QOhosJsState` abstract class: `env()` / `defaultWindowStageOrEmpty()` / `defaultUiContextOrEmpty()` / `tryGetJsWindowByQWindow()` / `tryGetQAbilityByQWindow()` / `defaultQAbility()` / `appLaunchWant()` / `eval<T>()` / `mapOhosEnumToJs<Enum>()` |
| JS thread operation registration | ❌ | ✅ `QOhosJsThreadOps`: `registerInstance()` / `instance()` |
| Qt thread state | ❌ | ✅ `QtState`: `isQtThread()` / `invokeTask()` / `qpaFunctions()` |
| Thread-safe QObject references | ❌ | ✅ `QObjectThreadSafeRef` / `QThreadSafeRef<T>`: `visitInQtThreadIfAlive()` |
| JS-thread-safe deleter proxy | ❌ | ✅ `makeProxyWithJsThreadDeleter<T>()` |
| Qt thread initialization | ❌ | ✅ `initQtThreadState()` / `getQtState()` / `invokeInQtThread()` |
| Callback info extension | ❌ | ✅ `QOhosCallbackInfo` extends `QNapi::CallbackInfo` |

### 4.4 General utilities

| Capability | Community edition | Official edition |
|------|--------|--------|
| Asynchronous promise chains | ❌ | ✅ `QOhosTaskPromise<Args...>`: `makeChained()` / `makeBranched()` / `makeThenCatchBranches()`, with caller-context chain tracking |
| Array view | ❌ | ✅ `QOhosSpan<T>`: `begin()` / `end()` / `data()` / `size()` / `operator[]` / `subspan()` |
| Mutex-protected value | ❌ | ✅ `QOhosMutexProtectedValue<T>`: `processValue()` / `evalWithValue()` |
| Optional type | ❌ | ✅ `QOhosOptional<T>` |
| Named function wrapper | ❌ | ✅ `QOhosNamedFunc<FuncPtr, Invoker>` |
| Consumer/supplier types | ❌ | ✅ `QOhosConsumer<Ts...>` / `QOhosSupplier<T>` |
| Fatal error reporting | ❌ | ✅ `qOhosReportFatalErrorAndAbort` |

### 4.5 Standard paths/paths/locale backends

| Backend | Community edition | Official edition |
|------|--------|--------|
| `QStandardPaths` | ✅ `qstandardpaths_openharmony.cpp` — calls `OH_Environment_*` directly | ✅ `qstandardpaths_ohos.cpp` — uses the `QOhosAppContext::Type` enum |
| `QSettings` | ✅ `qsettings_openharmony.cpp` | ✅ similar implementation |
| Locale | ✅ `qlocale_harmony.cpp` | ✅ full `QOhosSystemLocale` integration |
| Time zone | ✅ `qtimezoneprivate_openharmony.cpp` | ✅ similar implementation |
| OS version | ✅ `qoperatingsystemversion_openharmony.cpp` | ✅ similar implementation |
| App directory paths | Direct `QtOh::dir()` calls | ✅ `QOhosAppContext` namespace: 8 directory type enum values |
| URI/path conversion | ✅ `QtOh::pathFromUri()` / `uriFromPath()` | ❌ handled internally |

### 4.6 GUI kernel

| Capability | Community edition | Official edition |
|------|--------|--------|
| Ability control | ✅ `QtOhPrivate` namespace: `startAbility(QVariantMap)` / `startAbilityForResult()` / `terminateSelfWithResult()` | ✅ implemented via `QOhosQpaFunctions` |
| Close event context | ❌ | ✅ `QOhosCloseEventContext`: `CloseRootCause` (4 values) / `CloseResolution` enum, `makeForNewEvent()` / `getCloseRootCauseForEventOrDefault()` |
| Image conversion | ❌ | ✅ `QOhosImageConversions` (QImage ↔ OHOS PixelMap) |
| Window hints | ❌ | ✅ `QOhosWindowHints` |
| Gesture recognizers | ❌ | ✅ `QOhosGestureRecognizer` (pinch gesture) |

### 4.7 Public platform headers

| Capability | Community edition `QOhWindowFunctions` | Official edition `QOhosFunctions` |
|------|---------------------------|------------------------|
| Native node render fit | ✅ `setNativeNodeRenderFit()` — **16 fit modes** | ❌ moved to the QPA-internal `NativeNodeRenderFitPolicy` (2 values) |
| Native node background color | ✅ `setNativeNodeBackgroundColor()` | ❌ moved to `QOhosWindowUtils::setSurfaceBackgroundColor()` |
| Window tags | ❌ | ✅ `tagWindowOrWidgetAsSubWindowOf()` / `tagWindowOrWidgetAsMainWindow()` / `getWindowOrWidgetAsSubWindowOfTagValue()` |
| In-app clipboard sharing | ❌ | ✅ `setInAppOnlyPasteboardShareOption()` |

---

## 5. Extras module public API comparison

### 5.1 AppContext (application context)

| Capability | Community edition `QOhAppContext` | Official edition `QOhosAppContext` |
|---------|----------------------|------------------------|
| Theme mode | `ColorMode` (Dark/Light/Default/FollowSystemSetting) + `SysThem` (Dark/Light) | `ColorThemeMode` (LightTheme/DarkTheme/FollowSystemSetting) |
| Get theme | `colorMode()` / `sysThem()` | `darkThemeActive()` |
| Set theme | `setColorMode(ColorMode)` | `setColorThemeMode(ColorThemeMode)` |
| Theme change signals | `sysThemChanged` / `colorModeChanged` | `darkThemeActiveChanged(bool)` |
| PC mode signal | ✅ `pcModeChanged(bool)` | ❌ |
| Font size scaling | ❌ | ✅ `fontSizeScale()` + `fontSizeScaleChanged(double)` signal |
| Permission query | `isPermissionGranted(QString)` → bool (synchronous) | `isPermissionGranted(Permission)` + `(QString)` → bool (virtual) |
| Permission request | `requestPermissionFromUser(QString)` → bool (synchronous) | `requestPermissionFromUserIfNeeded(Permission)` → void (asynchronous + signal) |
| Permission request via settings page | `requestPermissionsOnSetting(QString)` → bool | `requestPermissionOnSettingIfNeeded(Permission)` → void |
| Serial port permission | ❌ | ✅ `hasSerialPortAccessRight()` / `requestSerialPortAccessRightIfNeeded()` + signal |
| Context menu on long press | ❌ | ✅ `enableContextMenuEventOnLongPress()` |
| Bundle info | ❌ | ✅ `getBundleInfo()` → `QOhosBundleInfo` (`versionCode()`) |
| App restart | ❌ | ✅ `restartApp()` / `restartApp(QOhosWant)` — `Q_NORETURN` |
| No-UI child process mode | ❌ | ✅ `isNoUiChildMode()` / `startNoUiChildProcess(libraryName, args)` |
| App launch Want | ❌ | ✅ `getAppLaunchWant()` / `getAppLaunchWantInfo()` |
| Class design | Concrete class, private constructor, singleton | Abstract class, all pure virtual functions |

### 5.2 AbilityContext (Ability context)

| Capability | Community edition `QOpenHarmonyAbility` (namespace) | Official edition `QOhosAbilityContext` |
|---------|---------------------------------------|---------------------------|
| Start Ability | `start(want)` / `start(want, options, receiver)` / `start(want, receiver)` | `startAbility(want)` / `startAbility(want, options)` / `startAbility(want, startRequest)` |
| Start for result | `startForResult(want)` / `startForResult(want, options, receiver)` | `startAbilityForResult(want)` → `QByteArray` (requestId) / `(want, options)` / `(want, startRequest)` |
| Result callback | `QAbilityResultReceiver` abstract class: `handleResult(Napi::Value, Napi::Value)` | Qt signals: `startAbilityForResultResponseReceived(requestId, resultCode, want)` / `startAbilityForResultErrorResponseReceived(requestId)` |
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

### 5.3 Want data structure

| Field/capability | Community edition `QOpenHarmonyWant` | Official edition `QOhosWant` |
|----------|------------------------|-----------------|
| parameters type | `QVariantMap` | `QJsonObject` |
| flags type | `int` | `QOhosWantFlags` (QFlags) |
| Want flag enum | ❌ plain int | ✅ `QOhosWantFlag`: AuthReadUriPermission / AuthWriteUriPermission / InstallOnDemand |
| File descriptors | ❌ | ✅ `QHash<QString,int> fds` |
| WantInfo | ❌ | ✅ `QOhosWantInfo` abstract class: `LaunchReason` enum (5 values) / `ContactInfo` struct / `tryGetSharedRecordsFromShareKit()` / `tryGetContactInfo()` |
| Termination result | ✅ `QOpenHarmonyAbilityResult` (resultCode + want) | ❌ |

### 5.4 StartOptions (start options)

| Field/capability | Community edition `QOpenHarmonyStartOptions` | Official edition `QOhosStartOptions` |
|----------|-------------------------------|--------------------------|
| Type | Plain struct; public fields assigned directly | Abstract class, 15 pure virtual setters |
| Window mode | `int windowMode` | ✅ `enum class WindowMode`: SPLIT_PRIMARY / SPLIT_SECONDARY / FULLSCREEN |
| Process mode | `int processMode` | ✅ `enum class ProcessMode`: NEW_PROCESS_ATTACH_TO_PARENT / NEW_PROCESS_ATTACH_TO_STATUS_BAR_ITEM |
| Startup visibility | `int startupVisibility` | ✅ `enum class StartupVisibility`: STARTUP_HIDE / STARTUP_SHOW |
| Starting window icon | `QPixmap startWindowIcon` | `QImage` (via `setStartWindowIcon(QImage)`) |
| Starting window background color | `QString startWindowBackgroundColor` | `QColor` (via `setStartWindowBackgroundColor(QColor)`) |
| Window min/max size | ❌ | ✅ `setMinWindowWidth/Height` / `setMaxWindowWidth/Height` |
| Hide starting window | ❌ | ✅ `setHideStartWindow(bool)` |
| Window creation parameters | ❌ | ✅ `setWindowCreateParams(QOhosWindowCreateParams)` |
| Window creation animation type | ❌ | ✅ `QOhosWindowCreateParams::AnimationType`: FADE_IN_OUT |
| How created | Direct construction + default constructor | Factory functions `createStartOptions()` / `createWindowCreateParams()` |

### 5.5 File sharing

| Capability | Community edition `QOHFileShare` | Official edition `QtOhosExtras::FileShare` |
|---------|----------------------|-------------------------------|
| Mode enum | `Mode`: READ_MODE / WRITE_MODE | `OperationMode`: Read / Write |
| Error enum | `Error`: ERR_OK / EXCEED_LIMIT / PERSISTENCE_FORBIDDEN / INVALID_MODE / INVALID_PATH / PERMISSION_NOT_PERSISTED | `PathPolicyError`: Unknown / PersistenceForbidden / InvalidMode / InvalidPath / PermissionNotPersisted |
| Policy struct | `Policy { Modes mode; QString file; }` | `PathPolicy { QString path; OperationModes operationModes; }` |
| API pattern | Static methods return `Error` + output parameter `Results&` | Free functions return `QSharedPointer<ActionResult>` |
| Operation status | Error code only | ✅ `QOhosOperationStatus` object (`success()` method) |
| Check method name | `checkPersistentPermission` | `checkPersistent` |

### 5.6 Window helpers

| Capability | Community edition `QOhWidgetHelper` | Official edition `QOhosWindowUtils` |
|---------|------------------------|--------------------------|
| API style | Instance class, attached to a QWidget/QWindow | Free functions in a namespace, with QWindow*/QWidget* overloads |
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

### 5.7 Process management

| Capability | Community edition | Official edition |
|---------|--------|--------|
| QProcess-style wrapper | ✅ `QOhProcess`: `start()` / `startDetached()` / `setMode()` / `stop()` / `isRunning()` / `pid()` / `errorString()` + 4 signals | ❌ no counterpart class |
| Native child processes | ✅ `QOhChildProcess` namespace: `startChildProcess()` / `startNativeChildProcess()` / `createNativeChildProcess()` / `createNativeChildProcessWithConfig()` | ❌ simplified to `startNoUiChildProcess(libraryName, args)` |
| Child process configuration | ✅ `StartMode` / `IsolationMode` / `Options` / `Fd` / `Args` / `ChildProcessConfig` structs | ❌ |
| Child process management | ✅ `getSubProcessPid()` / `getSubProcessAliveState()` / `killSubProcess()` | ❌ |

### 5.8 Local IPC

| Capability | Community edition | Official edition |
|---------|--------|--------|
| Abstract local socket | ✅ `QOhAbstractLocalSocket`: `send()` / `errorString()` / `close()` / `messageReady` signal | ❌ **does not exist at all** |
| Local socket client | ✅ `QOhLocalSocket`: `connect()` / `disconnectFromHost()` / `isConnected()` | ❌ |
| Local socket server | ✅ `QOhLocalServer`: `listen()` / `nextPendingConnection()` / `newConnection` signal | ❌ |
| Local socket connection | ✅ `QOhLocalConnection` | ❌ |

### 5.9 Permission management

| Capability | Community edition `QtOh` namespace | Official edition `AppPermissions` + `QOhosAbilityContext` |
|---------|------------------------|----------------------------------------------|
| Permission type | String `QString` | ✅ Typed enum `Permission` (ReadPasteboard/CustomScreenCapture/AccessBluetooth/ApproximatelyLocation/Location) + string overloads |
| Synchronous request | ✅ `requestPermissionsSync(QStringList, timeoutMs)` | ❌ asynchronous only |
| Asynchronous request | ✅ `requestPermissions(QStringList, callback)` | ✅ `requestPermissionFromUserIfNeeded(Permission)` + signal |
| Synchronous request via settings page | ✅ `requestPermissionsOnSettingSync(QStringList, timeoutMs)` | ❌ |
| Asynchronous request via settings page | ✅ `requestPermissionsOnSetting(QStringList, callback)` | ✅ `requestPermissionOnSettingIfNeeded(Permission)` + signal |
| Permission check | `checkPermission(QString)` → `PermissionResult` enum | `isPermissionGranted(Permission)` → bool |
| Result type | `PermissionResult` enum (Denied/Granted/InValidRequest) + `dialogShownResults` list | `PermissionResult` struct (bool permissionGranted, bool dialogShown) |
| Notification permission | ✅ `requestEnableNotification()` / `requestEnableNotificationSync()` / `isNotificationEnabled()` / `openNotificationSettings()` | ❌ |
| SDK version | ✅ `ohSdkVersion()` | ❌ |

### 5.10 Extras interfaces only in the official edition

| Interface | Capability |
|------|------|
| `QOhosDistributedDataObject` | Cross-device distributed data sync: `create()` / `get()` / `fieldNames()` / `addAssets()` / `assetKey()` / `assets()` / `areAssetsSynced()` / `sessionId()` / `save(deviceId)` + 4 signals (dataChanged/statusChanged/progressChanged/saveFinished) |
| `QOhosShareKit` namespace | System share framework: `QOhosSharedRecord` (13 properties) / `QOhosShareControllerOptions` (anchor/single selection/preview/exclusion) / `QOhosShareOperationResult` / factory functions createContentRecord/createFileRecord/createUrlRecord |
| `QOhosMultimedia` namespace | Audio stream usage hint: `AudioStreamUsageHint` enum (14 values) / `setAudioStreamUsageHintProperty()` / `tryGetAudioStreamUsageHintProperty()` |
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

## 6. Feature module plugin interface comparison

### 6.1 Multimedia (qtmultimedia)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Player | ✅ `qohplayer` / `qohdecoder` / `qohdemuxer` / `qohcodekit` | ✅ `qohosavplayer` / `qohosavplayerlist` / `qohosmediaplayercontrol` |
| Camera | ✅ `qohcaptureservice` / `qohcameracontrol` / `qohcamerasession` and others | ✅ `qohoscameraservice` / `qohoscamerasession` / `qohoscapturesession` and others |
| Recording | ✅ `qohrecordercontrol` / `qohaudioencodercontrol` / `qohvideoencodercontrol` | ✅ `qohosavrecorder` / `qohosmediarecordercontrol` |
| Audio devices | ✅ `ohaudiodevice` plugin: `qohaudiodeviceplugin` / `qopenharmonyengine` | ✅ `ohos-audio` plugin: `qohosaudioplugin` / `qohosaudioinput` / `qohosaudiooutput` |
| Video rendering | ✅ `qopenharmonysgvideonode` | ✅ `qohosvideorenderercontrol` / `qohosvideowidget` |
| NAPI wrappers | ✅ `ohcamera` / `ohmediarecorder` / `ohmultimediautils` | ❌ uses ArkTS bridging directly |
| Audio stream usage hint | ❌ | ✅ `QOhosMultimedia::AudioStreamUsageHint` (14 values) |

### 6.2 Connectivity (qtconnectivity)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Bluetooth state management | ✅ `qbluetoothlocaldevice_ohos.cpp` | ✅ `qohosbluetoothaccess` |
| Device discovery | ✅ `qbluetoothdevicediscoveryagent_ohos.cpp` + `ohdevicediscoverybroadcastreceiver` | ✅ `qohosbluetoothdevicediscovery` |
| Service discovery | ✅ `qbluetoothservicediscoveryagent_ohos.cpp` + `ohservicediscoverybroadcastreceiver` | ❌ |
| Bluetooth sockets | ✅ `qbluetoothsocket_ohos.cpp` + `qjssocket` | ✅ `qohosbluetoothsocket` |
| Bluetooth server | ✅ `qbluetoothserver_ohos.cpp` + `serveracceptancethread` | ✅ `qohosbluetoothserver` |
| GATT/LE | ✅ `qlowenergycontroller_ohos.cpp` + `lowenergynotificationhub` + `qjsble` | ❌ |
| NFC | ✅ `qnearfieldmanager_openharmony` / `qnearfieldtarget_openharmony` / `qllcpsocket_openharmony` / `qllcpserver_openharmony` | ❌ |
| ArkTS bridging | ✅ 11 `QtBluetooth*.ts` + 3 `JsNfc*.ts` | ❌ uses C++ wrappers |

### 6.3 Location (qtlocation)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Position info source | ✅ `qgeopositioninfosource_openharmony` | ✅ `qohosgeopositioninfosource` |
| Satellite info | ❌ | ✅ `qohosgeosatelliteinfosource` |
| Map services | ❌ | ✅ `ohosmapkit`: tiled map manager/tile fetcher/file cache/geocoding/routing/place search/POI categories |
| Plugin factory | ✅ `qgeopositioninfosourcefactory_openharmony` | ✅ `positionfactory_ohos` |

### 6.4 Sensors (qtsensors)

| Capability | Community edition | Official edition |
|------|--------|--------|
| Sensor manager | ✅ `sensormanager` | ✅ `OhosSensorsManager` |
| Backend template | ❌ standalone backends | ✅ `OhosSensorBackendBase<T>` template base class |
| Accelerometer | ✅ `openharmonyaccelerometer` | ✅ `ohosaccelerometerbackend` |
| Gyroscope | ✅ `openharmonygyroscope` | ✅ `ohosgyroscopebackend` |
| Magnetometer | ✅ `openharmonymagnetometer` | ✅ `ohosmagnetometerbackend` |
| Light | ✅ `openharmonylight` | ✅ `ohoslightsensorbackend` |
| Proximity | ✅ `openharmonyproximity` | ❌ |
| Pressure | ✅ `openharmonypressure` | ❌ |
| Humidity | ✅ `openharmonyhumidity` | ❌ |
| Temperature | ✅ `openharmonytemperature` | ❌ |
| Rotation | ✅ `openharmonyrotation` | ✅ `ohosrotationsensorbackend` |
| ArkTS bridging | ✅ `JsSensor.ts` / `JsSensorManager.ts` / `JsSensorsModule.ts` | ❌ uses `oh_sensor.h` directly |

### 6.5 WebView (qtwebview)

| Capability | Community edition `QHarmonyWebView` | Official edition |
|------|----------------------|--------|
| WebView implementation | ✅ `qharmonywebview.cpp` | ✅ `qohoswebview.cpp` |
| WebView controller | ❌ | ✅ `qohoswebviewcontroller` |
| Web component listener | ❌ | ✅ `qohoswebcomponentlistener` |
| Web resource errors | ❌ | ✅ `qohoswebresourceerror` |
| ArkTS bridging | ✅ `JsWebView.ets` | ❌ |

### 6.6 Other modules

| Module | Community edition | Official edition |
|------|--------|--------|
| **Network bearer** | ❌ | ✅ `ohos` bearer plugin: WiFi/cellular/Bluetooth/Ethernet/VPN |
| **Printing** | ✅ `openharmony` print support plugin | ✅ `ohos` print support plugin: `QOhosNativePrint` (connect to printers/start print jobs/query printers/print service management) |
| **Text to speech** | ❌ | ✅ `ohos` TTS plugin: `QTextToSpeechEngineOhos` + CoreSpeechKit |
| **Serial port** | ❌ | ✅ `ohos` serial port backend: `QOhosSerialManager` + `QOhosUsbManager` |
| **Style** | ✅ `QHarmonyStyle` | ✅ `QOhosStyle` |
| **Font database** | ✅ `QOhFontDatabase` | ✅ `QOhosPlatformFontDatabase` (inherits `QFontconfigDatabase`) |
| **Deployment tool** | ❌ | ✅ `openharmonydeployqt` |
| **DevEco template** | Simple EntryAbility | ✅ Full template: QAbility/QAbilityStage/QEmbeddedUiExtensionAbility/QBundledEmbeddedUiExtensionAbility/QChildProcess/4 kinds of page nodes/OhosExportModules |
| **Third-party libraries** | None bundled | ✅ Bundles fontconfig/libjpeg/libpng/openssl |
| **Enum generation** | ❌ | ✅ `qohosenumsgen.py` Python script that generates OHOS enum mappings |

---

## 7. Interface capabilities only in the community edition

### 7.1 Local IPC socket stack

| Interface | Implemented capability |
|------|---------|
| `QOhAbstractLocalSocket` | Local IPC base class: `send(QString)` / `errorString()` / `close()` / `messageReady` signal |
| `QOhLocalSocket` | Client: `connect(address)` / `disconnectFromHost()` / `isConnected()` |
| `QOhLocalServer` | Server: `listen(address)` / `nextPendingConnection()` / `newConnection` signal |
| `QOhLocalConnection` | Connection object accepted by the server |

> The official edition has **no local IPC subsystem at all**; `startAppProcess()` and `startNoUiChildProcess()` are used instead.

### 7.2 Full process management

| Interface | Implemented capability |
|------|---------|
| `QOhProcess` | QProcess-style wrapper: `start()` / `startDetached()` / `setMode()` / `stop()` / `isRunning()` / `pid()` / `errorString()` + `started`/`finished`/`errorOccurred`/`stateChanged` signals |
| `QOhChildProcess` | Native child processes: `startChildProcess()` / `startNativeChildProcess()` / `createNativeChildProcess()` / `createNativeChildProcessWithConfig()` + `StartMode`/`IsolationMode`/`Options`/`Fd`/`Args`/`ChildProcessConfig` structs |
| `QOpenHarmonyAbility::getSubProcessPid/AliveState/killSubProcess` | Child process management (non-official API) |

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
| `QOhWidgetHelper::DecorButtonStyle` | Decoration button style struct: colorMode/buttonBackgroundSize/spacingBetweenButtons/closeButtonRightMargin |
| `QOhWidgetHelper::setWindowDecorVisible()` / `windowDecorVisible()` | Window decoration visibility |
| `QOhWidgetHelper::setWindowShadowRadius()` | Window shadow radius |
| `QOhWidgetHelper::setWindowTitleMoveEnabled()` | Move the window by dragging the title bar |
| `QOhWidgetHelper::setWindowTitleButtonVisible(bool, bool, bool)` | Visibility of the title buttons (maximize/minimize/close) |
| `QOhWidgetHelper::titleButtonRect()` + signal | Title button rect query |
| `QOhWidgetHelper::removeStartingWindow()` | Remove the starting window |

### 7.6 Vulkan rendering support

| Interface | Implemented capability |
|------|---------|
| `QOhPlatformIntegration::createPlatformVulkanInstance()` | Create a Vulkan instance |
| `QOhPlatformVulkanInstance` | Vulkan instance implementation: `createOrAdoptInstance()` / `createSurface()` |
| `QOhPlatformNativeInterface::nativeResourceForWindow("vkSurface")` | Get the Vulkan surface |

### 7.7 Other community-only capabilities

| Interface | Implemented capability |
|------|---------|
| `QtOh::Utility` | 27 device/system information query methods |
| `QOhHiAppEvent` | HiAppEvent event reporting (FAULT/STATISTIC/SECURITY/BEHAVIOR) |
| `QtOh::pathFromUri()` / `uriFromPath()` | URI-path conversion |
| `QtOh::setBundleName()` / `setModuleName()` / `setAbilityName()` | Explicit identity setting |
| `QtOh::setUIEnv(napi_env)` / `uiEnv()` | Direct access to the NAPI environment |
| `QOhWindowFunctions::setNativeNodeRenderFit()` | 16 native node render fit modes |
| `QOhPlatformNativeInterface` | Exposes native resource pointers (UIAbility/UIAbilityContext/nativeSettings/nativeWindow/nativeWindowStage/nativeXComponent/NativeNode/vkSurface) |
| `QOhPlatformCursor` | Override cursor / pixmap cache / `setPos()` / `size()` / per-window cursors |
| `QOhPlatformMenu` / `QOhPlatformMenuItem` | Full platform menu implementation |
| `QOhSystemTrayIcon::ContentType` / `SlotType` | Notification content type (5 values) / notification slot type (5 values) |
| `QOhPlatformClipboard` | Clipboard progress (SDK≥15) / pasteboard observer |
| `QOhDisplayManager::screenAt(point)` | Find a screen by coordinates |
| `QOhPlatformScreen::densityPixels()` / `logicalBaseDpi()` | Pixel density / base logical DPI |
| NFC support | `qnearfieldmanager` / `qnearfieldtarget` / `qllcpsocket` / `qllcpserver` |
| Bluetooth GATT/LE | `qlowenergycontroller_ohos` + `lowenergynotificationhub` |
| Bluetooth service discovery | `qbluetoothservicediscoveryagent_ohos` |

---

## 8. Interface capabilities only in the official edition

### 8.1 Centralized QPA function interface

| Interface | Implemented capability |
|------|---------|
| `QtOhos::QOhosQpaFunctions` | **A unified interface of 66+ virtual functions**: window operations (15) / theme configuration (6) / clipboard (3) / file operations (2) / context menu (2) / screen ID (3) / Ability lifecycle (4) / Want management (3) / process management (4) / Ability start (3) / permission management (5) / serial port (2) / file sharing (5) / ShareKit (1) / link opening (1) / distributed data (3) / accessibility (1) / audio streams (2) |

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
| Window property tag system | 13 static property descriptors |
| Non-client area pointer events | `onNonClientAreaPointerPress/Move/Release()` |
| Safe area margins | `safeAreaMargins()` |
| Window snapshot | `makeSnapshot()` |
| Window decoration presets | `DecorationPreset` (Standard/Frameless) |
| Two-way OHOS↔Qt state sync | `setWindowStateFromOhos()` and 7 callbacks in total |

### 8.6 Screens/color picking

| Interface | Implemented capability |
|------|---------|
| `startPickingColorFromScreenWithConsumer()` | Pick a color from the screen |
| `tryGetNativeWindowId()` | Get the native window ID |
| `tryGetScreenDisplayId()` | Get the screen display ID |
| `QOhosScreenManager` | Multi-screen management: `rebuildScreenList()` / `platformScreenForDisplayIdOrNull()` |
| `QOhosPlatformScreen::notifyWindowVisibleAndActivated()` | Compositor API — window visibility tracking |

### 8.7 Audio stream usage hints

| Interface | Implemented capability |
|------|---------|
| `AudioStreamUsageHint` enum | 14 values: Music/VoiceCommunication/VoiceAssistant/Alarm/VoiceMessage/Ringtone/Notification/Accessibility/Movie/Game/Audiobook/Navigation/VideoCommunication/Unknown |
| `setAudioStreamUsageHintProperty(QObject*, hint)` | Set the stream usage hint on an audio object |
| `tryGetAudioStreamUsageHintProperty(QObject*, hint*)` | Get the stream usage hint of an audio object |

### 8.8 Other official-only capabilities

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
| Network bearer plugin | WiFi/cellular/Bluetooth/Ethernet/VPN |
| Map services (MapKit) | Tiled maps/geocoding/routing/place search/POI |
| Text to speech (TTS) | CoreSpeechKit proxy |
| Serial port support | `QOhosSerialManager` + `QOhosUsbManager` |
| `openharmonydeployqt` | Deployment packaging tool |
| Bundled third-party libraries | fontconfig / libjpeg / libpng / openssl |
| `qohosenumsgen.py` | OHOS enum mapping code generation |
| Full DevEco template | QAbility/QAbilityStage/embedded extensions/child processes/4 kinds of page nodes/OhosExportModules |

---

## 9. API paradigm differences in shared interfaces

### 9.1 Object creation pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Object creation | Direct `new` / stack construction | Factory functions return `QSharedPointer<T>` |
| Class concreteness | Concrete classes with implementations | Abstract classes, all pure virtual functions |
| Lifetime | Managed manually / Qt parent objects | `QSharedPointer` reference counting |

### 9.2 Permission request pattern

| Pattern | Community edition | Official edition |
|------|--------|--------|
| Calling style | Synchronous: `bool result = requestPermissionFromUser(permission)` | Asynchronous: `requestPermissionFromUserIfNeeded(permission)` → void |
| Getting the result | Direct return value | Signal notification: `permissionRequestResponseReceived(Permission, bool)` |
| Timeout control | ✅ `timeoutMs` parameter | ❌ no timeout |
| Permission type | String `QString` | Typed enum `Permission` + string overloads |

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

---

## 10. Summary

### 10.1 Capability coverage comparison

| Capability area | Community edition | Official edition |
|---------|--------|--------|
| QPA platform abstraction | ✅ complete | ✅ complete and richer |
| Ability lifecycle | ✅ basic support | ✅ full support (including continuation/migration/multiple instances/instance destruction control) |
| Window management | ✅ basic property control | ✅ advanced property control (brightness/contrast/saturation/maximize options/key frame policy/safe area/non-client area) |
| Permission management | ✅ synchronous + asynchronous | ✅ asynchronous only (typed enums) |
| Process management | ✅ full QProcess style | ✅ simplified startAppProcess/startNoUiChildProcess |
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
| Thread bridging | ✅ direct uv_queue_work templates | ✅ full abstraction layer (JsState/JsThreadGateway/JsThreadOps/QtState/ThreadSafeRef) |
| Close events | ❌ | ✅ CloseEventContext |
| Deadlock detection | ❌ | ✅ DeadlockProtector |
| Logging | ✅ basic macros | ✅ full logging system |

### 10.2 Differences in design philosophy

Design philosophy of the **community edition**:
- **Practicality first**: provides synchronous APIs for convenience in simple scenarios
- **Direct exposure**: public APIs depend directly on NAPI and expose native resource pointers
- **Instance management**: window helpers manage state through instance classes
- **Rich but not unified**: capabilities are scattered across multiple namespaces and classes
- **Process/IPC oriented**: provides full process management and a local IPC stack

Design philosophy of the **official edition**:
- **Abstraction first**: everything is abstract classes + factory functions, hiding implementation details
- **Asynchronous first**: permission and Ability results are all delivered asynchronously through signals
- **Type safety**: strongly typed enums replace raw ints; QJsonObject replaces QVariantMap
- **Centralized and unified**: the 66+-method `QOhosQpaFunctions` unified interface
- **Lifetime management**: `QSharedPointer` + RAII manage object lifetimes
- **Advanced features**: distributed data/ShareKit/Ability continuation/window brightness, contrast and saturation/audio stream hints and more
- **Engineering**: deployment tool/enum generation/deadlock detection/full template/bundled third-party libraries

### 10.3 Migration notes

When migrating from the community edition to the official edition, note the following:

1. **Renaming**: `QOh*` → `QOhos*`, `QtOh::` → `QtOhosExtras::`, `QOpenHarmony*` → `QOhos*`
2. **API paradigm conversion**: synchronous calls → asynchronous signals; callback classes → Qt signals; direct construction → factory functions + `QSharedPointer`
3. **Type conversion**: `QVariantMap` → `QJsonObject`; `int` flags → strongly typed enums; `QPixmap` → `QImage`
4. **IPC migration**: `QOhLocalSocket/Server` must be replaced with another IPC mechanism (such as `startAppProcess`)
5. **Process management migration**: `QOhProcess/QOhChildProcess` must be replaced with `startAppProcess()/startNoUiChildProcess()`
6. **Notification permission migration**: the community edition's `QtOh::requestEnableNotification()` and related functions must be implemented yourself or removed
7. **Window decoration migration**: `DecorButtonStyle`/`setWindowShadowRadius`/`setWindowTitleButtonVisible` and similar have no counterpart interfaces
8. **Vulkan migration**: if you render with Vulkan, the official edition does not support it; switch to OpenGL/EGL
9. **Removing the NAPI dependency**: public APIs no longer depend on `QtNapi/napi.h`; replace `QAbilityResultReceiver` with signal connections
10. **Taking advantage of new capabilities**: you can use the official edition's new capabilities, such as distributed data objects/ShareKit/Ability continuation/audio stream hints/serial port/TTS/map services
