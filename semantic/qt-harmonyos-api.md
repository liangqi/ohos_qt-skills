---
id: semantic-qt-harmonyos-api
type: semantic
domain: tech
tags: [qt, harmonyos, api, porting, qprocess, qwindow, dialog, modality, fullscreen, platform, setSurfaceConsumer, OHNativeWindow]
created: 2026-06-02
updated: 2026-08-06
status: active
audience: public
refs: [fault-C-0001, semantic-qt-harmonyos-overview, semantic-qt-ohos-extras]
summary: >
  Key Qt API compatibility points for HarmonyOS porting: argv differences; choosing a child-process approach per scenario (headless can use QProcess / a Qt UI uses startAppProcess / a non-Qt UI uses startAbility);
  window model differences (QDialog/Popup are subwindows);
  modality only applies to subwindows; winId() isn't a native handle; the public path to an OHNativeWindow* via setSurfaceConsumer; hide() has different semantics;
  setMask() only works on subwindows; closeEvent may come from the system lifecycle.
  Platform detection: Qt.platform.os returns "linux" on HarmonyOS (upstream's os() has no Q_OS_OHOS branch) — use pluginName for now, and an upstream fix is recommended.
  Device type detection: Qt exposes no public device-type interface; QtCore's private QOhosDeviceInfo (Q_CORE_EXPORT, includable and linkable, but with only three tiers — 2in1/tablet/phone — and essentially a cache of @ohos.deviceInfo) is usable, though applications are better off calling @ohos.deviceInfo directly through Node-API.
---

# Qt for HarmonyOS API compatibility notes

> Source: [API Compatibility Notes](https://wiki.qt.io/Qt_for_HarmonyOS/api_inconsistencies_on_harmonyos)

## Platform detection (QML and C++)

> **Verified in the source** (Qt 5.15.16 OHOS commit `962aa625`, branch tqtc/harmonyos-5.15.16)

### The current situation: `Qt.platform.os` returns `"linux"` on HarmonyOS, not `"ohos"`

```qml
Qt.platform.os === "ohos"    // false (os returns "linux" on HarmonyOS)
Qt.platform.os === "linux"   // true, but you can't tell HarmonyOS from desktop Linux
```

**Root cause (an upstream Qt implementation gap)**: the `#ifdef` chain in `QQmlPlatform::os()` (`qtdeclarative/src/qml/qml/qqmlplatform.cpp:59`) **has no `Q_OS_OHOS` branch**, while `qsystemdetection.h:115-117` has `__OHOS__` define both `Q_OS_OHOS` **and** `Q_OS_LINUX`, so it matches `Q_OS_LINUX → "linux"`. That's inconsistent with `QSysInfo::productType()` on the same platform, which returns `"ohos"` (`qglobal.cpp:2718`, which does have a `Q_OS_OHOS` branch) — an internal Qt inconsistency that should be reported upstream for a fix.

### The interim approach: detect via `pluginName` (until upstream fixes it)

The HarmonyOS QPA plugin's key is `"ohos"` (the `Keys` in `qtbase/src/plugins/platforms/ohos/ohos.json`, and `key.compare("ohos")` at `qohosplatformplugin.cpp:23`), and `Qt.platform.pluginName` returns exactly that:

```qml
readonly property bool isHarmony: Qt.platform.pluginName === "ohos"
```

> ⚠️ `pluginName` depends on the QPA plugin loaded at runtime, so it changes when running in a test environment with `-platform offscreen` and the like. For absolute reliability, inject a context property from C++ using a compile-time `#ifdef Q_OS_OHOS`.

### Detection on the C++ side

```cpp
// At runtime
const bool isHarmony = QSysInfo::productType() == "ohos";  // qglobal.cpp:2718 has a Q_OS_OHOS branch

// At compile time (the most reliable, with zero runtime cost)
#ifdef Q_OS_OHOS
    // HarmonyOS-specific code
#endif
```

> **Note**: `QSysInfo::productType()` returns `"ohos"` while `Qt.platform.os` returns `"linux"` — they have different implementations, so **don't cross-check one against the other**.

### Device type detection: Qt doesn't export it, so go through Node-API

> **Conclusion**: Qt (including QtOhosExtras) has **no** public interface for determining the HarmonyOS device type (phone/tablet/2in1/tv/car/wearable).

**Verified in the source** (Qt 5.15.16 OHOS commit `962aa625`):

1. **The QtOhosExtras public headers have no device-type interface**: none of the public headers in `qtohosextras/src/ohosextras/` (appcontext/want/startrequest/sharekit/pasteboard/...) contain any deviceType/deviceInfo/deviceProfile symbols.
2. **Qt's standard platform APIs identify the "system", not the "device"**: `productType()` → `"ohos"`, `Qt.platform.os` → `"linux"`, `pluginName` → `"ohos"` — none of them report the device form factor.
3. **The framework does determine device type internally, in two layers**:
   - **✅ The usable layer, `QOhosDeviceInfo` (a private QtCore export, Q_CORE_EXPORT)**: `is2in1()`/`isPhone()`/`isTablet()`/`sdkApiVersion()`/`tryGetRecognizedDeviceType()` in `QtCore/private/qohosdeviceinfo_p.h`. The symbols **are exported from libQt5Core.so**, so an application can `#include <QtCore/private/qohosdeviceinfo_p.h>` (with qmake's `QT += core-private`) and link against them. But **`RecognizedDeviceType` has only three tiers — `_2in1/tablet/phone`** — with no tv/car/wearable.
   - **❌ The unusable layer (internal to the QPA plugin, not exported and not includable)**: `queryQOhosRuntimeDeviceAndMode()`/`isHandheldDeviceType()` in `qohosruntimedevicetypeandmode.h`, and `QOhosSettings::isWindowPcModeEnabled()` in `qohossettings.h`. These are just secondary wrappers around `QOhosDeviceInfo`; the headers aren't in the SDK and the symbols are `-fvisibility=hidden`.
   - **The data source**: both layers ultimately come from the static cache that `qohosjsmain.cpp` fills at startup via `eval("@ohos.deviceInfo")` → `QOhosDeviceInfo::init(map)`. In other words, **`QOhosDeviceInfo` is essentially a C++ cache shell around `@ohos.deviceInfo`**.

**The cost of using the private entry point**: ① no ABI guarantee (the header says in plain text that it may change/be removed without notice); ② it depends on QPA init timing, so calling it too early gives empty values; ③ only three device-type tiers; ④ it's fundamentally just a cache of the system's deviceInfo.

**The recommended approach**: call `@ohos.deviceInfo` directly through Node-API and read `deviceInfo.deviceType` — the same data, a public and stable HarmonyOS API, full granularity, and no coupling to the Qt version. Only use `QOhosDeviceInfo` when you need to match the QPA's determination exactly and can accept the tight Qt coupling.

### A suggested upstream fix

We suggest Qt add a `Q_OS_OHOS` branch to `QQmlPlatform::os()` returning `"ohos"`:

```diff
 QString QQmlPlatform::os()
 {
 #if defined(Q_OS_ANDROID)
     return QStringLiteral("android");
+#elif defined(Q_OS_OHOS)
+    return QStringLiteral("ohos");
 #elif defined(Q_OS_IOS)
     return QStringLiteral("ios");
 #elif defined(Q_OS_TVOS)
     return QStringLiteral("tvos");
 #elif defined(Q_OS_MAC)
     return QStringLiteral("osx");
 #elif defined(Q_OS_WINRT)
     return QStringLiteral("winrt");
 #elif defined(Q_OS_WIN)
     return QStringLiteral("windows");
 #elif defined(Q_OS_LINUX)
     return QStringLiteral("linux");
```

**Key points**:
- The branch must come **before** `Q_OS_LINUX` — `Q_OS_OHOS` implies `Q_OS_LINUX` (following the existing pattern where `Q_OS_ANDROID` precedes `Q_OS_LINUX`).
- It makes things consistent with `QSysInfo::productType()` (which already returns `"ohos"`), removing the internal Qt inconsistency.
- After the fix, QML can use `Qt.platform.os === "ohos"` normally and the interim `pluginName` approach can be dropped.
- **Compatibility**: this is a behavior change, affecting OHOS code that relies on `os==="linux"` and `QFileSelector`'s platform selectors (if they use "linux"). It should be noted in the release notes. The same applies to Qt6 (whose `os()` implementation is identical).

## Application launch and argument passing

### main(int argc, char *argv[])
- `argv[0]` is the application library path, **not** a traditional executable path
- When arguments come through a Want, `want.uri` may occupy `argv[1]`
- **Don't assume** your own arguments start at `argv[1]`
- Parse based on the actual contents of `argc/argv`

### Launching processes/instances
- **Don't** think in desktop terms of "start a process from a path"
- Use the Ability/Want interfaces:
  - `QtOhosExtras::startAbility()` — launch an Ability
  - `QtOhosExtras::startNewAbilityInstance()` — launch a new instance
  - `QtOhosExtras::startAppProcess()` — launch an application process

### QProcess

> See [[qt-harmonyos-api-mapping]] §1 Process management (the decision tree + before/after).

### UI-less child processes
- `QtOhosExtras::QOhosAppContext::startNoUiChildProcess()` — uses HarmonyOS's Child Process Manager
- Once in NoUiChildProcess mode, the UI rendering pipeline isn't initialized
- Use `isNoUiChildMode()` to check the state
- **Never** create or manipulate windows/UI in this mode

## Window types and relationships

### QDialog / Qt::Popup / Qt::ToolTip / Qt::Tool
- On HarmonyOS these behave like **subwindows** (not independent top-level windows)
- The parent-child relationship is enforced strictly, and activation/closing behavior depends on the main window
- You **must** set an explicit parent or transientParent

### setParent() / reparenting
- HarmonyOS places extra restrictions on changing parent-child relationships
- **Don't** treat an externally embedded window as a standard parent window

## Modality, minimizing, and fullscreen

### Qt::WindowModality

> **Verified in the source** (Qt 5.12.12 OHOS commit `613336de`): HarmonyOS **doesn't support desktop-semantics application-level modality**. The QPA maps `Qt::WindowModality` onto HarmonyOS's `@ohos.window.ModalityType` enum (`WINDOW_MODALITY` / `APPLICATION_MODALITY`) via the `setSubWindowModal` interface, but with several layers of restriction.

- Modality **only applies to subwindows** — setting modality on the main window is dropped by two early returns in the QPA (`qohosview.cpp:910`, `qohoswindowproxy.cpp:967`)
- `Qt::ApplicationModal` is **not desktop global modality**:
  - The QPA prints the warning `ApplicationModal policy is unsupported by the platform` (`qohosview.cpp:914`), but in fact it is still mapped to `APPLICATION_MODALITY` and passed to HarmonyOS (it is **not** downgraded to `WINDOW_MODALITY` — the source's warning wording is slightly misleading)
  - It only takes effect when `QOhosSettings::isWindowPcModeEnabled()` is true — that is, on a **2-in-1 device** or a **tablet with PC window mode enabled** (free multi-window state); otherwise `setSubWindowModalEnabled` simply `return`s and skips it (`qohoswindowproxy.cpp:971`)
  - The PC mode determination is at `qohossettings.cpp:98` (`is2in1()` ‖ the system setting `window_pcmode_switch_status=="true"`)
- **Don't rely on** traditional desktop global application modality; on phones `ApplicationModal` has no effect at all (it's silently skipped)

**The call chain**: `QWindow::setModality` → `modalityChanged` → (`qohosfloatingwindow.cpp:351`) → `QOhosView::setModality` (`qohosview.cpp:765`) → `updateWindowModality` (`qohosview.cpp:907`, doing the subwindow/warning checks) → `mapQtWindowModalityToOhosOrDefault` (`qohosview.cpp:55`, WindowModal→WINDOW_MODALITY / ApplicationModal→APPLICATION_MODALITY) → `setSubWindowModalEnabled` (`qohoswindowproxy.cpp:965`, doing the main-window/PC-mode checks) → the HarmonyOS JS `setSubWindowModal(true, ModalityType)`

### showFullScreen()
- Supported; calling it at runtime toggles fullscreen
- The **first main window** takes a different creation path than later windows: the first one may not support "launch straight into fullscreen"
- **Recommendation**: call `showFullScreen()` after the window has been created and shown

### showMinimized()
- **Only the main window** supports minimizing
- Subwindows don't support desktop-style minimizing

### hide()
- **The main window**: prefers a system-level hide (which needs a system tray) and falls back to minimizing when that isn't supported
- **Subwindows/floating windows**: hide that window, without the main-window-level "hidden" semantics
- **Don't** use `hide()` in `closeEvent()` as a general "alternative to closing"
- To keep the main window alive, prefer `showMinimized()`

## Window flags and the title bar

### MinimizeButtonHint / MaximizeButtonHint / CloseButtonHint
- These mainly target the main window and usually only take effect in PC mode
- **Don't assume** these flags behave consistently across device/window types

### Qt::FramelessWindowHint
- Hides the system decorations on both main windows and subwindows
- Once enabled on the main window, the standard three buttons (minimize/maximize/close) are unavailable too

### Qt::WindowStaysOnTopHint
- Main window + PC mode only

### System drag-to-move: startSystemMove ↔ startMoving()

This is the scenario of dragging a custom title bar on a frameless window (`Qt::FramelessWindowHint`). On the HarmonyOS side, the system-level window-move API is actually `window.Window.startMoving()` (API 14+, no arguments), `startMoving(offsetX, offsetY)` (API 15+), and `stopMoving()` (API 15+) — there is **no** HarmonyOS API named `startSystemMove` in the public documentation; "startSystemMove" is Qt's name for it.

| Qt interface | Version | Notes |
|--------------|---------|-------|
| `QPlatformWindow::startSystemMove(QPoint)` | ≥5.11 | A platform virtual; the base class returns `false` (a no-op) |
| `QWindow::startSystemMove()` | **New in Qt6** | A public convenience method with no arguments, returning bool |

**The OHOS QPA connection chain** (present in 5.12/5.15/6; source: `qohosfloatingwindow.cpp`):
`QOhosFloatingWindow::startSystemMove()` → `QOhosView::startMoving()` → `QOhosWindowProxy::startMoving()` → an eval/call of `"startMoving()"` on the ArkTS-side `jsWindowRef` (5.x uses `evalToPromiseOrRejectOnThrow`, Qt6 uses `call<QNapi::Promise>`).

**The key point**: the `createPlatformWindow` factory creates a `QOhosFloatingWindow` for **almost every top-level window** (the main window, Tool, Dialog, and other ordinary windows); only the native `QFileDialogClassWindow` dialog and UIExtension windows use the base class — so **the main window goes through this chain too**, and `startSystemMove` is wired up for it.

**Whether it actually moves depends on HarmonyOS policy**: `startMoving()` works for system windows, subwindows, global floating windows, and modal windows; for an **application main window it only works in the free-window (FLOATING) state**, otherwise it returns `801`/`1300004`. On mobile / non-free-window devices, calling it returns `801`.

**How to call it**:
- Qt6: `window->startSystemMove()`
- Qt 5.12/5.15: there's no public `QWindow::startSystemMove()`, so go through `window->handle()->startSystemMove(pos)` (a public `QPlatformWindow` virtual)
- Typically called from a custom title bar's mousePress / `onTouch(TouchType.Down)`

## Window shape and clipping

### setMask()
- **Only works on subwindows**; the main window doesn't support it
- For a special main window appearance, use content-level clipping or custom painting

## Window geometry persistence

- Relies on `QtOhosExtras::setMainWindowGeometryPersistenceHint()`
- Applies only to the **first main window**
- Must be set before the first main window is shown
- Currently supported only on **2-in-1 devices**

## Window close semantics

### closeEvent(QCloseEvent *)
- A close event may come from a user action or from the system terminating the Ability's lifecycle
- **Don't** treat every `closeEvent()` as "the user clicked the close button"
- You need to distinguish a window close from lifecycle termination

## Native window handles

### QWindow::winId()
- On HarmonyOS this returns a Qt-internal private structure, **not** a native window handle
- Its type and layout may change at any time
- `QtOhosExtras::tryGetNativeWindowId(QWindow *)` returns the ArkTS-side WindowProperties.id
  - But the official warning is that it isn't guaranteed to stay valid for the application's lifetime, and stability/performance may suffer if you use it

### setSurfaceConsumer (the public path to an OHNativeWindow*)

> **Verified in the source** (Qt 5.15.16 OHOS commit `962aa625`, branch tqtc/harmonyos-5.15.16)

The QPA plugin exposes the `OHNativeWindow*` through `platformFunction("setSurfaceConsumer")`; this is the **only public** path within Qt for obtaining the native window handle. `winId()` does not return an OHNativeWindow.

**Registration** (`qohosplatformnativeinterface.cpp`):
```cpp
} else if (functionName == "setSurfaceConsumer") {
    return reinterpret_cast<QFunctionPointer>(&QOhosPlatformWindow::setSurfaceConsumer);
}
```

**The signature** (`qohosplatformwindow.h`):
```cpp
static std::shared_ptr<void> setSurfaceConsumer(
    QWindow *targetWindow,
    QObject *surfaceConsumerContext,
    std::function<void(QOhosOptional<void *>)> surfaceConsumer);
```

**The `void*` in the callback** is the `OHNativeWindow*` returned by `QOhosSurface::nativeWindow()`. The callback fires when the surface is created/destroyed/changed (including for the initial surface and on the `surfaceStatusChanged` signal). The returned `shared_ptr<void>` is a handle that unregisters the consumer when it's destroyed.

**QtMultimedia already uses it** (`qtmultimedia/src/plugins/ohos/src/mediaplayer/qohosvideowidget.cpp`):
```cpp
auto setSurfaceConsumerFunc = reinterpret_cast<...>(
    qApp->platformFunction("setSurfaceConsumer"));
m_surfaceConsumerHandle = setSurfaceConsumerFunc(
    m_displayWindow.get(), this,
    [this](QOhosOptional<void *> nativeSurface) {
        m_playerControl->setVideoSurface(
            static_cast<::OHNativeWindow *>(nativeSurface.value()));
    });
```

**Use cases**:
- C++ applications: get the function pointer directly with `qApp->platformFunction("setSurfaceConsumer")`
- Python/PyQt5 applications: you need to bridge through ctypes + a C++ shim `.so` (PyQt5's sip doesn't expose `platformFunction`)
- A typical use: passing the OHNativeWindow to a third-party rendering library (libvlc, OpenGL, and so on)

**Note**: `QOhosOptional` is an internal Qt OHOS QPA type, so its binary layout compatibility needs verifying at compile time.

## References

- [Qt for HarmonyOS API Compatibility Notes](https://wiki.qt.io/Qt_for_HarmonyOS/api_inconsistencies_on_harmonyos)
