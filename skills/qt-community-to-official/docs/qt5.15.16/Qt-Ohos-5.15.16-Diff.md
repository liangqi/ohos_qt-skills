# Qt for HarmonyOS 5.12.12 vs 5.15.16 HarmonyOS Port Difference Analysis

> **Compared paths**
> - 5.12.12: `qt-5.12.12/qt-harmonyos-src`
> - 5.15.16: `qt-5.15.16/qt5.15.16`
>
> **Purpose**: developers and skills can use this document to switch/migrate code between the two versions.

---

## Contents

1. [Overview](#1-overview)
2. [Build system differences (.pro / .qmake.conf / configure)](#2-build-system-differences)
3. [Header file differences (added / renamed / removed)](#3-header-file-differences)
4. [Public API differences (QtOhosExtras module)](#4-public-api-differences-qtohosextras-module)
5. [Platform plugin API differences (qtbase ohos QPA)](#5-platform-plugin-api-differences-qtbase-ohos-qpa)
6. [Permission differences](#6-permission-differences)
7. [File sharing (ShareKit / UDMF) differences](#7-file-sharing-sharekit--udmf-differences)
8. [Theme (ColorMode) differences](#8-theme-colormode-differences)
9. [Accessibility differences](#9-accessibility-differences)
10. [Pasteboard (clipboard) differences](#10-pasteboard-clipboard-differences)
11. [Window management differences](#11-window-management-differences)
12. [Input method differences](#12-input-method-differences)
13. [New classes in detail](#13-new-classes-in-detail)
14. [Internal architecture refactoring](#14-internal-architecture-refactoring)
15. [Version switching and migration guide](#15-version-switching-and-migration-guide)

---

## 1. Overview

| Dimension | 5.12.12 | 5.15.16 |
|------|---------|---------|
| Qt baseline version | Qt 5.12.12 | Qt 5.15.16 |
| Git branch | `tqtc/harmonyos-5.12.12` | `tqtc/harmonyos-5.15.16` |
| Line endings | **CRLF** (Windows style) | **LF** (Unix style) |
| Module version | Hard-coded `MODULE_VERSION = 5.12.12` | Dynamic `MODULE_VERSION = $$[QT_VERSION]` |
| N-API integration | `include(node-addon-api.pri)` + `-lace_napi.z` | `CONFIG += qnapi` (built-in qnapi feature) |
| Optional type | `QOhosOptional<T>` (custom) | `nonstd::optional<T>` (optional-lite) |
| Where enums are defined | Scattered across files | Centralized in `qohosqpaenums.h` |
| Device information | No separate module | New `QOhosDeviceInfo` |
| Icon engine | `qohosimageformat` (pixel format conversion) | `qohosiconengine` (QIconEngine implementation) |

### File change statistics

| Area | CRLF-only differences | Real content differences | Added files | Removed files |
|------|-------------|-------------|---------|---------|
| `qtohosextras/src` | 24 | 17 | 9 | 0 |
| `qtohosextras/include` | — | — | 6 | 0 |
| qtbase ohos QPA plugin | 64 | 149 | 8 | 4 |
| qtohosextras/examples | — | — | 2 | 0 |

---

## 2. Build system differences

### 2.1 N-API integration change (key)

**5.12.12** (`ohosextras.pro` / `ohos.pro`):
```qmake
include($$PWD/../../../qtbase/src/3rdparty/node-addon-api.pri)
```
The platform plugin also links:
```qmake
LIBS += -lace_napi.z
```

**5.15.16** (`ohosextras.pro` / `ohos.pro`):
```qmake
CONFIG += qnapi
```
The platform plugin no longer links `-lace_napi.z`; instead:
```qmake
LIBS += -lace_ndk.z    # use ace_ndk instead of ace_napi
include($$PWD/../../../3rdparty/optional-lite.pri)
```

> **Migration impact**: if a custom `.pro` file references `node-addon-api.pri`, change it to `CONFIG += qnapi`; if it links `-lace_napi.z`, remove that.

### 2.2 Module version

**5.12.12** (`.qmake.conf`):
```qmake
MODULE_VERSION = 5.12.12
```

**5.15.16** (`.qmake.conf`):
```qmake
MODULE_VERSION = $$[QT_VERSION]
```

### 2.3 optional-lite dependency

5.15.16 adds a dependency on the `optional-lite` third-party library:
```qmake
include($$PWD/../../../3rdparty/optional-lite.pri)
```
It brings in the `<nonstd/optional.hpp>` header, replacing the former `QOhosOptional<T>`.

### 2.4 Platform plugin link library differences

| Library | 5.12.12 | 5.15.16 |
|----|---------|---------|
| `-lace_napi.z` | ✅ | ❌ (removed) |
| `-lace_ndk.z` | ✅ | ✅ |
| `-lhiappevent_ndk.z` | ✅ | ✅ |
| `-lhilog_ndk.z` | ✅ | ✅ |
| `-lEGL` | ✅ | ✅ |
| `-lnative_display_manager` | ✅ | ✅ |
| `-lnative_vsync` | ✅ | ✅ |
| `-lnative_window` | ✅ | ✅ |
| `-lnative_window_manager` | ✅ | ✅ |
| `-lohfileshare` | ✅ | ✅ |
| `-lohfileuri` | ✅ | ✅ |
| `-lohhicollie` | ✅ | ✅ |
| `-lohinput` | ✅ | ✅ |
| `-lpasteboard` | ✅ | ✅ |
| `-lpixelmap` | ✅ | ✅ |
| `-lqos` | ✅ | ✅ |
| `-ludmf` | ✅ | ✅ |
| `-lohinputmethod` | ✅ | ✅ |

### 2.5 headers.pri (syncqt header registration)

5.15.16 adds the following to `SYNCQT.HEADER_FILES` / `SYNCQT.PRIVATE_HEADER_FILES` / `SYNCQT.CLEAN_HEADER_FILES`:
- `qohosdistributeddataobject.h` (public)
- `qohosdragkeyframepolicy.h` (public)
- `qohoswindowmaximizeoptions.h` (public)
- `qohosdistributeddataobject_p.h` (private)
- `qohosdragkeyframepolicy_p.h` (private)
- `qohoswindowmaximizeoptions_p.h` (private)

### 2.6 configure / license

- License changed from `LGPL21` to `GPL-EXCEPT`
- Copyright year updated from 2015 to 2020
- `qt.pro` and `configure.json` have identical content

---

## 3. Header file differences

### 3.1 New public headers in the QtOhosExtras module

| Header | Class | Purpose |
|--------|------|------|
| `qohosdistributeddataobject.h` | `QOhosDistributedDataObject` | Distributed data object (cross-device data sync) |
| `qohosdragkeyframepolicy.h` | `QOhosDragKeyFramePolicy` | Window drag key frame policy |
| `qohoswindowmaximizeoptions.h` | `QOhosWindowMaximizeOptions` | Window maximize options |

New private headers:
- `qohosdistributeddataobject_p.h`
- `qohosdragkeyframepolicy_p.h`
- `qohoswindowmaximizeoptions_p.h`

### 3.2 Platform plugin (qtbase ohos QPA) header changes

#### Added

| Header | Purpose |
|--------|------|
| `qohosdeviceinfo_p.h` | Device information queries (device type/model/SDK version, etc.) |
| `qohosiconengine.h` | QIconEngine factory function `tryCreateQOhosIconEngine()` |
| `qohosqpaenums.h` | Unified definitions of **all** OHOS enums (replacing scattered definitions) |
| `qohosdragkeyframepolicy.h` | Drag key frame policy (platform side) |
| `qohoswindowmaximizeoptions.h` | Maximize options (platform side) |
| `doc/jsscopedata.md` | Documentation of the JsScopeData design pattern |

#### Renamed

| 5.12.12 | 5.15.16 | Notes |
|----------|---------|------|
| `qohosenums.h` | `qohosqpaenums.h` | Enums centralized; namespace changed from `QtOhos::enums` to `QtOhosQpa::enums` |
| `qohosimageformat.h` | `qohosiconengine.h` | Changed from pixel format conversion to an icon engine |

#### Removed

| Header | Notes |
|--------|------|
| `qohospointerstyle.h` | The `QOhosPointerStyle` enum is merged into `ohos::multimodalInput::pointer::PointerStyle` in `qohosqpaenums.h` |

---

## 4. Public API differences (QtOhosExtras module)

> The following are headers in `qtohosextras/src/ohosextras/` with real content differences.
> The remaining headers (such as `qohosenums.h`, `qohosapppermissions.h`, `qohosfileshare.h`, `qohossharekit.h`) have identical content; only the line endings changed from CRLF to LF.

### 4.1 qohosabilitycontext.h — distributed data object support

**New include:**
```cpp
#include <QtOhosExtras/qohosdistributeddataobject.h>
```

**New methods in `QOhosOnContinueContext`:**
```cpp
// Set the callback for the save results of distributed data objects during cross-device continuation
virtual void setResponseOnDistributedDataObjectsSaveResults(
    const QList<QSharedPointer<QOhosDistributedDataObject>> &dataObjects,
    QObject *saveResultsHandlerContext,
    std::function<void(QList<bool>)> saveResultsHandler) = 0;

// Get the target device ID
virtual QString targetDeviceId() const = 0;
```

**New free function:**
```cpp
// Restore the distributed data objects of a cross-device continuation from a Want
Q_OHOS_EXTRAS_EXPORT QList<QSharedPointer<QOhosDistributedDataObject>>
    tryRestoreOnContinueDistributedDataObjects(const QOhosWant &want);
```

### 4.2 qohoswindowutils.h — window drag key frames & maximize options

**New includes:**
```cpp
#include <QtOhosExtras/qohosdragkeyframepolicy.h>
#include <QtOhosExtras/qohoswindowmaximizeoptions.h>
```

**New functions (each with QWindow* and QWidget* overloads):**
```cpp
// Drag key frame policy
void enableWindowDragKeyFramePolicy(QWindow *window, const QOhosDragKeyFramePolicy &policy);
void enableWindowDragKeyFramePolicy(QWidget *widget, const QOhosDragKeyFramePolicy &policy);
void disableWindowDragKeyFramePolicy(QWindow *window);
void disableWindowDragKeyFramePolicy(QWidget *widget);

// Window maximize options
void setWindowMaximizeOptions(QWindow *window, const QOhosWindowMaximizeOptions &options);
void setWindowMaximizeOptions(QWidget *widget, const QOhosWindowMaximizeOptions &options);
void clearWindowMaximizeOptions(QWindow *window);
void clearWindowMaximizeOptions(QWidget *widget);
```

### 4.3 .cpp implementation change patterns

The main changes in all `.cpp` files with real differences:
1. `QOhosOptional` API migration: `.hasValue()` → `.has_value()`, `.valueOr(x)` → `.value_or(x)`, `makeQOhosOptional(x)` → `nonstd::make_optional(x)`, `makeEmptyQOhosOptional()` → `{}` / `nonstd::nullopt`
2. `QOhosOptional::andThen(f)` → `qAndThen(opt, f)` (helper function form)
3. Documentation additions (such as docs for the `ShareAbilityType` enum, `LaunchReason`, and `isPermissionGranted(QString)`)

---

## 5. Platform plugin API differences (qtbase ohos QPA)

### 5.1 qohosqpaenums.h — enum unification (the most important change)

5.12.12's `qohosenums.h` defines only a few enums (258 lines). 5.15.16's `qohosqpaenums.h` is greatly expanded (907 lines), centralizing all the enums that used to be scattered across `qohospointerstyle.h`, `render/qohoswindowproxy.h`, `qohossharekit.h`, `qohosdisplayinfo.h`, and other files.

**Namespace change:**
```
QtOhos::enums  →  QtOhosQpa::enums
```

**New enum categories:**

| Namespace | Enums | Notes |
|----------|------|------|
| `kit::ShareKit::systemShare` | `SelectionMode`, `ShareAbilityType`, `SharePreviewMode` | System sharing (moved in from qohossharekit.h) |
| `ohos::app::ability::AbilityConstant` | `OnContinueResult` (new), `LaunchReason`, `ContinueState`, `WindowMode` | Ability constants |
| `ohos::app::ability::ConfigurationConstant` | `ColorMode` | Color mode |
| `ohos::app::ability::contextConstant` | `ProcessMode` (**adds ATTACH_TO_STATUS_BAR_ITEM**), `StartupVisibility` | Process mode |
| `ohos::app::ability::wantConstant` | `Flags` (**new**) | Want flags |
| `ohos::bundle::bundleManager` | `SupportWindowMode` | Supported window modes |
| `ohos::display` | `DisplaySourceMode`, `Orientation` | Display (moved in from qohosdisplayinfo.h) |
| `ohos::file::picker` | `DocumentSelectMode` (**new**) | File picker |
| `ohos::inputMethod` | `Direction`, `EnterKeyType`, `RequestKeyboardReason`, `TextInputType` (**new**) | Input method |
| `ohos::multimodalInput::pointer` | `PointerStyle` (**adds SCREENRECORDER_CURSOR**, 46 values in total) | Mouse pointer style (moved in from qohospointerstyle.h) |
| `ohos::net::connection` | `NetBearType`, `NetCap` (**new**) | Network |
| `ohos::notificationManager` | `ContentType` | Notification content type |
| `ohos::window` | `AnimationType`, `AvoidAreaType`, `MaximizePresentation` (**adds FOLLOW_APP_IMMERSIVE_SETTING**), `ModalityType`, `RectChangeReason`, `WindowEventType`, `WindowStatusType` | Window (moved in from qohoswindowproxy.h) |
| `Api26::ohos::window` | `AcrossDisplayPresentation` (**new**) | API26 cross-display presentation |

**Usage change:**
```cpp
// 5.12.12 — enums defined in each file
QOhosWindowProxy::WindowEventType::WINDOW_SHOWN
QOhosShareKit::SelectionMode::SINGLE
QOhosDisplayInfo::JsDisplayOrientation::PORTRAIT

// 5.15.16 — centralized definitions referenced via using aliases
QOhosWindowProxy::WindowEventType::WINDOW_SHOWN  // using = QtOhosQpa::enums::ohos::window::WindowEventType
QOhosShareKit::SelectionMode                     // using = QtOhosQpa::enums::kit::ShareKit::systemShare::SelectionMode
QOhosDisplayInfo::JsDisplayOrientation            // using = QtOhosQpa::enums::ohos::display::Orientation
```

### 5.2 QOhosOptional → nonstd::optional (global migration)

This is the most widespread change, affecting 149+ files:

| 5.12.12 (QOhosOptional) | 5.15.16 (nonstd::optional) |
|--------------------------|----------------------------|
| `QOhosOptional<T>` | `nonstd::optional<T>` |
| `.hasValue()` | `.has_value()` |
| `.valueOr(default)` | `.value_or(default)` |
| `.value()` | `.value()` or `*opt` |
| `makeQOhosOptional(x)` | `nonstd::make_optional(x)` |
| `makeEmptyQOhosOptional()` | `{}` / `nonstd::nullopt` |
| `#include <QtCore/private/qohoscommon_p.h>` (indirect) | `#include <nonstd/optional.hpp>` |

### 5.3 qohosplugincore.h — core interface changes

```cpp
// Optional type changes
QOhosOptional<QNapi::Promise> → nonstd::optional<QNapi::Promise>
QOhosOptional<QNapi::Object> → nonstd::optional<QNapi::Object>
QOhosOptional<std::string>   → nonstd::optional<std::string>

// New method
virtual void forceResolveQWindowDestroyPromiseIfPresent(Napi::Env env) = 0;

// Removed methods
// virtual void tagWidgetOrWindowAsFloatWindow(QObject *, bool) = 0;  // removed
// virtual QNapi::Object getModule(const std::string &) = 0;           // removed (marked QT_DEPRECATED)
// virtual QOhosOptional<QNapi::Object> optAppLaunchParam() = 0;      // removed
// virtual void startAppProcess(...) old overload                     // removed
// virtual void addNewWantConsumer(...) = 0;                          // removed

// startNewQAbilityInstance parameter change
// 5.12: std::shared_ptr<QAbilityPeer> baseQAbilityPeer
// 5.15: QNapi::Object baseQAbility

// Timeout type change
std::chrono::milliseconds timeout → std::chrono::nanoseconds timeout

// Type alias
QOhosAbilityOnContinueResult → using = QtOhosQpa::enums::ohos::app::ability::AbilityConstant::OnContinueResult
```

### 5.4 qohosdisplayinfo.h — display information

```cpp
// Enums removed (now using references to qohosqpaenums.h)
enum class JsDisplayOrientation { ... } → using JsDisplayOrientation = QtOhosQpa::enums::ohos::display::Orientation;
enum class DisplaySourceMode { ... }     → using DisplaySourceMode = QtOhosQpa::enums::ohos::display::DisplaySourceMode;

// New field
uint refreshRate;  // refresh rate

// Optional changes
QOhosOptional<QNapi::Object> tryGetDisplayById(...) → nonstd::optional<QNapi::Object>
QOhosOptional<JsDisplayOrientation> orientation     → nonstd::optional<JsDisplayOrientation>
QOhosOptional<DisplaySourceMode> sourceMode            → nonstd::optional<DisplaySourceMode>
QOhosOptional<QPoint> topLeftOffsetPixels             → nonstd::optional<QPoint>
```

### 5.5 qohoswindowproperty.h — window properties

```cpp
// New
void clearQOhosPropertyOnQObject(QObject *qObject);  // clear the property
bool hasLiveConsumers() const;                        // check whether there are live consumers

// Property descriptor change
constexpr QOhosPropertyDescriptor()                  → explicit QOhosPropertyDescriptor(const char *name)
                                                        const char *name() const;  // new

// Property name generation change
// 5.12: name generated at runtime with printfToString("_q_platform_ohos_%d_%p", ...)
// 5.15: uses propertyPtr->name() directly (determined at compile time)

// Optional changes
QOhosOptional<T> tryGetQOhosPropertyFromQObject(...) → nonstd::optional<T>
QOhosOptional<T> tryGetProperty()                     → nonstd::optional<T>
```

### 5.6 qohosscreenmanager.h — screen management

```cpp
// Header normalization
#include <QObject> → #include <QtCore/qobject.h>
#include <QPointer> → #include <QtCore/qpointer.h>

// Dependency removed
// #include <qohosplugincore.h>  // removed

// Optional changes
QOhosOptional<QOhosDisplayInfo> displayInfoOrEmpty() → nonstd::optional<QOhosDisplayInfo>
QOhosOptional<JsDisplayId> displayIdOrEmpty()         → nonstd::optional<JsDisplayId>
```

### 5.7 qohosplatformscreen.h — platform screen

```cpp
// New
qreal refreshRate() const override;  // refresh rate
mutable nonstd::optional<Qt::ScreenOrientation> m_nativeOrientation;  // native orientation cache

// Header normalization
#include <QList> → #include <QtCore/qlist.h>
#include <QPainter> → #include <QtGui/qpainter.h>
#include <QTimer> → #include <QtCore/qtimer.h>
#include <QWaitCondition> → #include <QtCore/qwaitcondition.h>
```

### 5.8 qohosplatformtheme.h — platform theme

```cpp
// New
QIconEngine *createIconEngine(const QString &iconName) const override;  // icon engine creation
```

### 5.9 qohossettings.h — settings (refactored into a singleton)

```cpp
// 5.12.12 — namespace + free functions
namespace QOhosSettings {
    double fontSizeScale();
    bool isWindowPcModeEnabled();
}

// 5.15.16 — singleton class
class QOhosSettings {
public:
    static QOhosSettings &instance();
    std::shared_ptr<void> installSettingsCache();  // new: settings cache
    double fontSizeScale() const;
    bool isWindowPcModeEnabled() const;
private:
    QOhosSettings();
    QOhosSupplier<bool> m_windowPcModeEnabled;
};
```

### 5.10 qohosplatformintegration.h — platform integration

```cpp
// New
std::shared_ptr<void> m_settingsCacheHandle;  // settings cache handle

// Header normalization
#include <QTouchDevice> → #include <QtGui/qtouchdevice.h>
```

### 5.11 qohospixelmapconversions.h — pixel map conversions

```cpp
// Removed
// std::shared_ptr<::OH_PixelmapNative> createNativePixelMapFromQImage(QImage);
// std::shared_ptr<::OH_PixelmapNative> makeEmptyNativePixelMap();
// std::shared_ptr<::OH_PixelmapNative> wrapNativePixelMapPtr(::OH_PixelmapNative *);
// QNapi::Object createNapiPixelMapFromQImage(...);

// Renamed
makeEmptyNativePixelMap() → makeEmptyOhosNativePixelMap()  // called in qohosudsobject.h

// Changed
QNapi::Object createNapiPixelMapFromQImage(...) → QNapi::Object makeDisplayDensityScaledJsPixelMapFromQImage(...)

// Header dependency change
// #include <qohosimageformat.h>  → removed (uses QtGui/private/qohosimageconversions_p.h instead)
```

### 5.12 qohosplatformservices.h — platform services

```cpp
// Static methods removed
// static std::string mapPathToOhosUriInJsThread(const std::string &path);
// static std::string mapOhosFileUriToPathInJsThread(const std::string &ohosFileUri);
```

### 5.13 qohosfloatingwindow.h — floating window

```cpp
// Method signature change
bool startSystemMove(const QPoint &pos) → bool startSystemMove()  // position argument no longer needed

// New window event handling methods
void handleWindowEvent(QOhosWindowProxy::WindowEvent evt);
void handleWindowStatusChange(QOhosWindowProxy::WindowStatus evt);
void handleWindowVisibilityChange(bool visible);
void handleAvoidAreaChanged(QOhosWindowProxy::AvoidAreaType, const QOhosWindowProxy::AvoidArea &);
void updateSafeAreaMargins();
void handleWindowRectChanged(const QOhosWindowProxy::RectChangeOptions &);
void handleSurfaceStatusChanged(const nonstd::optional<QSize> &);
void handleWindowDisplayIdChanged(QOhosDisplayInfo::JsDisplayId);

// New members
nonstd::optional<QOhosWindowProxy::WindowEvent> m_activationEventDeferredUntilWindowUnblocked;
QMap<QOhosWindowProxy::AvoidAreaType, QOhosWindowProxy::AvoidArea> m_avoidAreaCache;
```

### 5.14 qohosdeviceinfo_p.h — device information (new)

```cpp
namespace QOhosDeviceInfo {
    enum class Type { deviceType, manufacture, brand, marketName, /* ... 30+ properties */ };
    enum class RecognizedDeviceType { _2in1, tablet, phone };

    void init(QMap<Type, QVariant> devinfo);
    QVariant getProperty(Type prop);
    nonstd::optional<RecognizedDeviceType> tryGetRecognizedDeviceType();
    bool isTablet();
    bool is2in1();
    bool isPhone();
    int sdkApiVersion();
    bool isCurrentDeviceSupported();
}
```

### 5.15 render/qohoswindowproxy.h — window proxy

```cpp
// Enum changes: local enums replaced with using references
enum class WindowEventType { ... } → using WindowEventType = QtOhosQpa::enums::ohos::window::WindowEventType;
enum class WindowStatusType { ... } → using WindowStatusType = QtOhosQpa::enums::ohos::window::WindowStatusType;
enum class AvoidAreaType { ... }   → using AvoidAreaType = QtOhosQpa::enums::ohos::window::AvoidAreaType;
enum class RectChangeReason { ... } → using RectChangeReason = QtOhosQpa::enums::ohos::window::RectChangeReason;
enum class MaximizePresentation { ... } → using MaximizePresentation = QtOhosQpa::enums::ohos::window::MaximizePresentation;
enum class ModalityType { ... }   → using ModalityType = QtOhosQpa::enums::ohos::window::ModalityType;

// New MaximizePresentation value
ENTER_IMMERSIVE_DISABLE_TITLE_AND_DOCK_HOVER  // not present in 5.12

// New methods
void setDragKeyFramePolicy(const QtOhos::QOhosKeyFramePolicy &policy);
void maximize(const QtOhos::QOhosWindowMaximizeOptions &options);  // signature changed
QList<QRect> getDisplayCutoutRects() const;                          // new: get the display cutout areas
void shiftAppWindowFocus(QOhosWindowProxy &targetProxy);            // new: shift window focus

// maximize signature change
void maximize(MaximizePresentation maximizePresentation)  // 5.12
void maximize(const QtOhos::QOhosWindowMaximizeOptions &options)  // 5.15

// Touch event struct change
struct NonClientAreaTouchEvent {
    std::int32_t id;
    std::chrono::milliseconds timestamp;
    Qt::TouchPointState state;    // 5.12
    QEvent::Type action;           // 5.15 (changed)
    QPointF displayPosition;
    QPointF localPosition;         // new
    QPointF globalPosition;
};

// JsScopeData constructor change
JsScopeData(..., std::shared_ptr<QtOhos::QAbilityPeer> qAbilityPeer);  // 5.12
JsScopeData(..., std::shared_ptr<QtOhos::QAbilityPeer> qAbilityPeer,
            QtOhos::QObjectThreadSafeRef owningQWindowRef);              // 5.15 (new parameter)

// Optional changes (all)
QOhosOptional<double> → nonstd::optional<double>
QOhosOptional<QOhosDisplayInfo::JsDisplayId> → nonstd::optional<...>
QOhosOptional<QSize> → nonstd::optional<QSize>
QOhosOptional<bool> → nonstd::optional<bool>
```

---

## 6. Permission differences

### 6.1 Public API (qtohosextras)

`qohosapppermissions.h` and `qohosapppermissionsutils_p.h` have **identical** content (CRLF→LF only).

Documentation changes in `qohosappcontext.cpp`:
- **Removed** the documentation of the `AppPermission` enum (the enum itself is unchanged; only the documentation location moved)
- **Added** documentation for `isPermissionGranted(const QString &permissionName)`

### 6.2 Platform plugin (qohosapppermissions_p.h)

Permission request function signature change:

```cpp
// 5.12.12 — uses a QAbilityPeer pointer
void requestAppPermissionFromUser(
    QtOhos::JsState &jsState,
    std::shared_ptr<QtOhos::QAbilityPeer> abilityPeer,  // old
    const std::string &permissionName, ...);

// 5.15.16 — uses QNapi::Object
void requestAppPermissionFromUser(
    QtOhos::JsState &jsState,
    QNapi::Object qAbility,  // new
    const std::string &permissionName, ...);
```

This change affects three functions: `requestAppPermissionFromUser`, `requestAppPermissionFromUserWithResult`, and `requestAppPermissionOnSetting`.

---

## 7. File sharing (ShareKit / UDMF) differences

### 7.1 ShareKit (qtohosextras public layer)

`qohossharekit.h` has **identical** content (CRLF→LF only).

Implementation changes in `qohossharekit.cpp`:
- Added documentation for the `ShareAbilityType` enum
- `QOhosOptional` API migrated to `nonstd::optional`
- `.hasValue()` → `.has_value()`, `.valueOr()` → `.value_or()`

### 7.2 ShareKit (platform plugin qohossharekit.h)

```cpp
// Enum definition change: local definition → using reference
enum class SelectionMode { SINGLE, BATCH }              → using SelectionMode = QtOhosQpa::enums::kit::ShareKit::systemShare::SelectionMode;
enum class SharePreviewMode { DEFAULT, DETAIL }         → using SharePreviewMode = QtOhosQpa::enums::kit::ShareKit::systemShare::SharePreviewMode;
enum class ShareAbilityType { COPY_TO_PASTEBOARD, ... } → using ShareAbilityType = QtOhosQpa::enums::kit::ShareKit::systemShare::ShareAbilityType;

// New
#include <QtCore/qmap.h>

// Optional changes
QOhosOptional<std::string> content → nonstd::optional<std::string> content
QOhosOptional<std::string> filePath → nonstd::optional<std::string> filePath
// ... same for all fields
QOhosOptional<ShareControllerAnchor> anchor → nonstd::optional<ShareControllerAnchor>
QOhosOptional<SelectionMode> selectionMode → nonstd::optional<SelectionMode>
```

### 7.3 UDMF (Unified Data Management Framework)

`qohosudmf.h`:
```cpp
QOhosOptional<QOhosSpan<const std::uint8_t>> tryGetGeneralEntry(...) → nonstd::optional<...>
```

`qohosudmfconversions.h`:
```cpp
QOhosOptional<bool> shareInAppOnly → nonstd::optional<bool>
QOhosOptional<std::string> tryMapUtdTypeIdToMimeType(...) → nonstd::optional<std::string>
QOhosOptional<std::string> tryMapMimeTypeToUtdTypeId(...) → nonstd::optional<std::string>
```

`qohosudsobject.h`:
```cpp
// Header dependency change
#include <qohospixelmapconversions.h> → #include <QtGui/private/qohosimageconversions_p.h>

// Function renamed
makeEmptyNativePixelMap() → makeEmptyOhosNativePixelMap()
```

### 7.4 File sharing (qohosfileshare.cpp)

```cpp
// Optional API migration
optInternalValue.hasValue() → optInternalValue.has_value()
optInternalValue.value()    → optInternalValue.value()

// Chained operation change
policyErrorResult.error.andThen(tryMap...).valueOr(...)           // 5.12
qAndThen(policyErrorResult.error, tryMap...).value_or(...)       // 5.15
```

---

## 8. Theme (ColorMode) differences

### 8.1 qohosplatformtheme

```cpp
// New icon engine creation
QIconEngine *createIconEngine(const QString &iconName) const override;
```

`qohosplatformtheme.cpp`:
- Adds a call to `tryCreateQOhosIconEngine` (replacing the old `qohosimageformat` pixel format conversion)

### 8.2 ColorMode enum

The `ColorMode` enum definition is unchanged, but moved from `qohosenums.h` to `qohosqpaenums.h`:
```
QtOhos::enums::ohos::app::ability::ConfigurationConstant::ColorMode
→ QtOhosQpa::enums::ohos::app::ability::ConfigurationConstant::ColorMode
```

### 8.3 Dark theme

In `qohosappcontext.cpp`:
```cpp
// Optional API migration
darkModeFlag.valueOr(darkModeFlagDefault) → darkModeFlag.value_or(darkModeFlagDefault)
m_ohosConfigDarkModeFlagSupplier().valueOr(darkModeFlagDefault) → .value_or(darkModeFlagDefault)
```

The dark theme's `setDarkThemeEnabled` / `darkThemeActiveChanged` signal mechanism itself is unchanged.

### 8.4 Settings system refactoring

`qohossettings.h` was refactored from a namespace into a singleton class:
- New `installSettingsCache()` for the settings cache
- `fontSizeScale()` / `isWindowPcModeEnabled()` became const member methods
- `qohosplatformintegration.h` gains an `m_settingsCacheHandle` member

---

## 9. Accessibility differences

### 9.1 New event type

```cpp
// qohosaccessibilitytree.h
enum class AccessibilityEvent {
    // ...
    ElementTextUpdated,  // new: text updated event
    // ...
};

// qohosaccessibleeventsconsumer.h
virtual void notifyInterfaceTextChanged(QAccessible::Id interfaceId) = 0;  // new: text change notification
```

### 9.2 Optional migration

```cpp
// qohosaccessibilitytree.h
QOhosOptional<std::pair<std::string, std::string>> minMaxRange → nonstd::optional<...>
QOhosOptional<Id> parentId → nonstd::optional<Id>

// qohosaccessibilityarkuihelpers.h
QOhosOptional<AccessibilityNode::Id> tryMapOhosElementIdToNodeId(...) → nonstd::optional<...>
QOhosOptional<AccessibilityNode::Id> tryMapNumericIdToValidNodeId(...) → nonstd::optional<...>

// qohosaccessibilitytreeeventsconsumercommand.h
QOhosOptional<AccessibilityEvent> getOptEventType() → nonstd::optional<...>
QOhosOptional<AccessibilityWindowEvent> getOptWindowEventType() → nonstd::optional<...>
```

### 9.3 Accessibility tree lookup

```cpp
// qohosaccessibilitytree.h
virtual QOhosOptional<std::pair<AccessibilityNode::Id, QXComponentRender>>
    tryFindNodeUpwardsWithXComponent(...) → nonstd::optional<...>
```

---

## 10. Pasteboard (clipboard) differences

### 10.1 qohosclipboardobject.h — structural refactoring

```cpp
// Optional migration
QOhosOptional<PasteboardDataSource> dataSource → nonstd::optional<PasteboardDataSource>
QOhosOptional<bool> shareInAppOnly → nonstd::optional<bool>

// New JsScopeData struct (following the JsScopeData design pattern)
struct JsScopeData {
    std::shared_ptr<::OH_Pasteboard> pasteboard;
    std::shared_ptr<void> pasteboardDataChangedListenerHandle;
};

// Member changes
// 5.12: held directly
std::shared_ptr<::OH_Pasteboard> m_pasteboard;
std::shared_ptr<void> m_pasteboardDataChangedListenerHandle;

// 5.15: held through JsScopeData (destroyed safely on the JS thread)
std::shared_ptr<QOhosConsumer<nonstd::optional<PasteboardDataSource>>> m_pasteboardUpdatesNotifier;
std::shared_ptr<JsScopeData> m_jsScopeData;
```

### 10.2 qohosplatformclipboard.h

```cpp
QOhosOptional<bool> &shareInAppOnlyFlagRef() → nonstd::optional<bool> &shareInAppOnlyFlagRef()
```

### 10.3 qohospasteboard.cpp (qtohosextras)

Documentation tweak:
```cpp
\brief The QOhosPasteboard class is to manage native pasteboard.
→ \brief The QOhosPasteboard namespace provides functions to manage the native pasteboard.
```

---

## 11. Window management differences

### 11.1 Maximize options (new feature)

5.15.16 adds `QOhosWindowMaximizeOptions`:
```cpp
enum class MaximizePresentation {
    EnterImmersive,
    EnterImmersiveDisableTitleAndDockHover,  // new
    ExitImmersive,
    FollowAppImmersiveSetting,
};

enum class AcrossDisplayPresentation {  // brand new
    EnterAcrossDisplayMode,
    ExitAcrossDisplayMode,
    FollowAcrossDisplaySetting,
};

// Factory function
QSharedPointer<QOhosWindowMaximizeOptions> createWindowMaximizeOptions();
```

### 11.2 Drag key frame policy (new feature)

5.15.16 adds `QOhosDragKeyFramePolicy`:
```cpp
void setInterval(std::chrono::milliseconds interval);
void setDistance(int distancePx);
void setAnimationDuration(std::chrono::milliseconds animationDuration);
void setAnimationDelay(std::chrono::milliseconds animationDelay);

// Factory function
QSharedPointer<QOhosDragKeyFramePolicy> createDragKeyFramePolicy();
```

### 11.3 Window proxy signature changes

```cpp
// maximize signature change
void maximize(MaximizePresentation)                          → void maximize(const QOhosWindowMaximizeOptions &)

// startSystemMove signature change (floatingwindow)
bool startSystemMove(const QPoint &pos)                      → bool startSystemMove()

// New
void setDragKeyFramePolicy(const QtOhos::QOhosKeyFramePolicy &policy);
QList<QRect> getDisplayCutoutRects() const;                   // display cutout areas
void shiftAppWindowFocus(QOhosWindowProxy &targetProxy);      // window focus shift
```

### 11.4 Window property system

```cpp
// New
void clearQOhosPropertyOnQObject(QObject *);  // clear the property
bool hasLiveConsumers() const;                  // check for live consumers
const char *name() const;                       // property descriptor name

// Property name generation change
// 5.12: generated at runtime as "_q_platform_ohos_%d_%p"
// 5.15: compile-time propertyPtr->name()
```

---

## 12. Input method differences

### 12.1 qohosinputmethodproxy.h — preview text callback change

```cpp
// onInsertPreviewText callback signature change (adds start/end parameters)
virtual void onInsertPreviewText(std::string text)                                    // 5.12
virtual void onInsertPreviewText(std::string text, int start, int end)               // 5.15

// New methods
void notifySelectionChange(std::u16string text, int start, int end);
void setTextAroundCursor(std::u16string leftText, std::u16string rightText, int cursorIndex);

// New internal struct
struct TextAroundCursor {
    std::u16string leftText;
    std::u16string rightText;
    int cursorIndex = 0;
};
std::shared_ptr<QOhosMutexProtectedValue<TextAroundCursor>> m_textAroundCursor;  // new member

// New registerCallbacks parameter
std::shared_ptr<QOhosMutexProtectedValue<TextAroundCursor>> textAroundCursor  // new
```

### 12.2 qohosinputmethodeventhandler.h — focus events

```cpp
// New focus event struct
struct QOhosFocusEvent {
    QPointer<QWindow> targetWindow;
    bool isFocus = false;
};

// New methods
void onFocusEvent(const QOhosFocusEvent &focusEvent);
void requestActivationOnPressIfNeeded(QWindow *pressTargetWindow);

// New members
QPointer<QWindow> m_pendingActivationWindow;
nonstd::optional<std::int32_t> m_optNonClientAreaTouchPointerId;

// Optional migration
QOhosOptional<QPoint> singleTouchPointEventGlobalPosition → nonstd::optional<QPoint>
QOhosOptional<std::pair<QWindow*, std::uint64_t>> getLastTouchedWindowWithSeqNoIfPresent() → nonstd::optional<...>
QOhosOptional<QOhosMouseEvent> m_lastWsiMouseEvent → nonstd::optional<...>
QOhosOptional<QWindowSystemInterfaceTouchEvent> m_lastWsiTouchEvent → nonstd::optional<...>
```

### 12.3 Input method enums

Input method enums added to `qohosqpaenums.h`:
- `ohos::inputMethod::Direction`
- `ohos::inputMethod::EnterKeyType`
- `ohos::inputMethod::RequestKeyboardReason` (new)
- `ohos::inputMethod::TextInputType`

---

## 13. New classes in detail

### 13.1 QOhosDistributedDataObject (distributed data object)

**Header:** `QtOhosExtras/qohosdistributeddataobject.h`
**Namespace:** `QtOhosExtras`

```cpp
class Q_OHOS_EXTRAS_EXPORT QOhosDistributedDataObject : public QObject {
    Q_OBJECT
public:
    enum class Status { Online, Offline, Restored };

    // Factory creation (from a JSON configuration)
    static QSharedPointer<QOhosDistributedDataObject> create(const QJsonObject &source);

    // Data access
    virtual QJsonValue get(const QString &key) const = 0;
    virtual QStringList fieldNames() const = 0;

    // Asset management
    virtual void addAssets(const QList<QSharedPointer<QFile>> &files) = 0;
    virtual QString assetKey() const = 0;
    virtual QJsonArray assets() const = 0;
    virtual bool areAssetsSynced() const = 0;

    virtual QString sessionId() const = 0;
    virtual void save(const QString &deviceId) = 0;

Q_SIGNALS:
    void dataChanged(QString sessionId, QStringList changedFields);
    void statusChanged(QString sessionId, QString networkId, Status status);
    void progressChanged(QString sessionId, int progress);
    void saveFinished(bool success);
};
```

**Use case:** synchronizes distributed data objects during cross-device continuation; handle it in the continuation callback via `QOhosOnContinueContext::setResponseOnDistributedDataObjectsSaveResults`.

### 13.2 QOhosDragKeyFramePolicy (drag key frame policy)

**Header:** `QtOhosExtras/qohosdragkeyframepolicy.h`
**Namespace:** `QtOhosExtras`

```cpp
class Q_OHOS_EXTRAS_EXPORT QOhosDragKeyFramePolicy {
public:
    virtual void setInterval(std::chrono::milliseconds interval) = 0;
    virtual void setDistance(int distancePx) = 0;
    virtual void setAnimationDuration(std::chrono::milliseconds animationDuration) = 0;
    virtual void setAnimationDelay(std::chrono::milliseconds animationDelay) = 0;
};

QSharedPointer<QOhosDragKeyFramePolicy> createDragKeyFramePolicy();
```

**Usage:**
```cpp
auto policy = QtOhosExtras::createDragKeyFramePolicy();
policy->setInterval(std::chrono::milliseconds(16));
policy->setDistance(8);
QtOhosExtras::enableWindowDragKeyFramePolicy(window, *policy);
```

### 13.3 QOhosWindowMaximizeOptions (window maximize options)

**Header:** `QtOhosExtras/qohoswindowmaximizeoptions.h`
**Namespace:** `QtOhosExtras`

```cpp
enum class MaximizePresentation {
    EnterImmersive,
    EnterImmersiveDisableTitleAndDockHover,
    ExitImmersive,
    FollowAppImmersiveSetting,
};

enum class AcrossDisplayPresentation {
    EnterAcrossDisplayMode,
    ExitAcrossDisplayMode,
    FollowAcrossDisplaySetting,
};

class Q_OHOS_EXTRAS_EXPORT QOhosWindowMaximizeOptions {
public:
    virtual void setMaximizePresentation(MaximizePresentation) = 0;
    virtual void setAcrossDisplayPresentation(AcrossDisplayPresentation) = 0;
    virtual void setSnapshotAnimationDuration(std::chrono::milliseconds duration) = 0;
    virtual void setSnapshotAnimationDelay(std::chrono::milliseconds delay) = 0;
};

QSharedPointer<QOhosWindowMaximizeOptions> createWindowMaximizeOptions();
```

**Usage:**
```cpp
auto opts = QtOhosExtras::createWindowMaximizeOptions();
opts->setMaximizePresentation(QtOhosExtras::MaximizePresentation::EnterImmersive);
QtOhosExtras::setWindowMaximizeOptions(window, *opts);
```

---

## 14. Internal architecture refactoring

### 14.1 JsScopeData design pattern (new)

5.15.16 introduces the `JsScopeData` design pattern to resolve resource lifetime conflicts between the Qt thread and the JS thread.

**Core idea:** package all JS-thread-related state (JS object references, listener handles) into a `struct JsScopeData`, and manage its lifetime with a `shared_ptr` + a JS-thread deleter.

**Documentation location:** `qtbase/src/plugins/platforms/ohos/doc/jsscopedata.md`

**Classes that already apply this pattern:**
- `QOhosClipboardObject` (clipboard object)
- Other classes involving JS-thread state

**Rules:**
1. Strict partitioning: JS-thread state goes into `JsScopeData`; Qt-thread state stays in class members
2. `m_jsScopeData->...` denotes JS-thread state; `m_xxx` denotes Qt-thread state
3. Access `JsScopeData` contents only inside JS-thread closures (`runInJsThreadAndWait`, `evalInJsThread`)

### 14.2 Enum centralization

All OHOS enums are unified in `qohosqpaenums.h` and referenced from each module via `using` aliases:
- Eliminates duplicate definitions
- Unifies the `OhosEnumMeta` template specializations
- Adds `Q_DECLARE_METATYPE` for all enums
- Adds an `Api26` namespace to distinguish enums of different API levels

### 14.3 Header include normalization

Qt module-style includes are changed to full-path includes globally:
```cpp
// 5.12                           // 5.15
#include <QObject>            →    #include <QtCore/qobject.h>
#include <QPointer>          →    #include <QtCore/qpointer.h>
#include <QList>             →    #include <QtCore/qlist.h>
#include <QPainter>          →    #include <QtGui/qpainter.h>
#include <QTimer>            →    #include <QtCore/qtimer.h>
#include <QWaitCondition>    →    #include <QtCore/qwaitcondition.h>
#include <QAtomicInt>        →    #include <QtCore/qatomic.h>
#include <QOpenGLPaintDevice>→   #include <QtGui/qopenglpaintdevice.h>
#include <QOpenGLContext>    →    #include <QtGui/qopenglcontext.h>
#include <QScopedPointer>    →    #include <QtCore/qscopedpointer.h>
#include <QTouchDevice>      →    #include <QtGui/qtouchdevice.h>
#include <QtCore/QtGlobal>   →    #include <QtCore/qglobal.h>
#include <QtCore/QSizeF>     →    #include <QtCore/qsize.h>
```

### 14.4 More precise timeout type

```cpp
std::chrono::milliseconds timeout → std::chrono::nanoseconds timeout
```
Affects `tryInvokeInQtThreadAndTryWaitForContinue` and `tryInvokeInMasterThreadAndTryWaitForContinue`.

### 14.5 Code style adjustments

- Braces `{}` removed from single-line `if` statements (some files)
- Unnecessary `#include <utility>` removed

---

## 15. Version switching and migration guide

### 15.1 Migrating from 5.12.12 to 5.15.16

#### Step 1: Build system

1. In `.qmake.conf`, change `MODULE_VERSION` to `$$[QT_VERSION]`
2. In `.pro` files:
   - `include(.../node-addon-api.pri)` → `CONFIG += qnapi`
   - Remove `LIBS += -lace_napi.z`
   - Add `include(.../optional-lite.pri)` (if you use nonstd::optional)

#### Step 2: Header includes

1. `#include <qohosenums.h>` → `#include <qohosqpaenums.h>`
2. `#include <qohosimageformat.h>` → `#include <qohosiconengine.h>` (different functionality)
3. `#include <qohospointerstyle.h>` → remove (merged into `qohosqpaenums.h`)
4. The `qohosimageformat.h` referenced in `#include <qohospixelmapconversions.h>` → `QtGui/private/qohosimageconversions_p.h`
5. Change all `#include <QObject>` and similar → full-path form

#### Step 3: Optional type migration

Global replacement:
```
QOhosOptional<T>           → nonstd::optional<T>
.hasValue()                → .has_value()
.valueOr(x)                → .value_or(x)
makeQOhosOptional(x)       → nonstd::make_optional(x)
makeEmptyQOhosOptional()   → nonstd::nullopt or {}
opt.andThen(f)             → qAndThen(opt, f)
```

#### Step 4: Enum references

```cpp
// Namespace change
QtOhos::enums::xxx → QtOhosQpa::enums::xxx

// If you use locally defined enums, change them to using references
// e.g. SelectionMode etc. in qohossharekit.h
```

#### Step 5: Permission request API

```cpp
// 5.12 — pass a QAbilityPeer pointer
requestAppPermissionFromUser(jsState, abilityPeer, permissionName, ...);

// 5.15 — pass a QNapi::Object
requestAppPermissionFromUser(jsState, qAbility, permissionName, ...);
```

#### Step 6: Window management API

```cpp
// maximize change
window->maximize(MaximizePresentation::ENTER_IMMERSIVE);  // 5.12
auto opts = createWindowMaximizeOptions();                 // 5.15
opts->setMaximizePresentation(...);
setWindowMaximizeOptions(window, *opts);

// startSystemMove change
floatingWindow->startSystemMove(pos);  // 5.12
floatingWindow->startSystemMove();     // 5.15

// New features available
enableWindowDragKeyFramePolicy(window, *policy);  // new in 5.15
```

#### Step 7: Input method callbacks

```cpp
// onInsertPreviewText signature change
void onInsertPreviewText(std::string text)                            // 5.12
void onInsertPreviewText(std::string text, int start, int end)       // 5.15
```

#### Step 8: JsScopeData pattern (platform plugin development)

When developing new platform plugin classes, follow the JsScopeData pattern in `doc/jsscopedata.md` to manage JS-thread resources.

### 15.2 Rolling back from 5.15.16 to 5.12.12

1. `CONFIG += qnapi` → `include(.../node-addon-api.pri)`
2. Add `LIBS += -lace_napi.z`
3. `nonstd::optional` → `QOhosOptional`
4. `qohosqpaenums.h` → `qohosenums.h` + enums inside each file
5. `qohosiconengine` → `qohosimageformat`
6. Restore the permission API form that takes a `QAbilityPeer` parameter
7. `maximize(QOhosWindowMaximizeOptions)` → `maximize(MaximizePresentation)`
8. `startSystemMove()` → `startSystemMove(pos)`
9. Remove the JsScopeData pattern (hold JS resources directly)
10. Full-path includes → module-style includes

### 15.3 Migration checklist

- [ ] `.qmake.conf` MODULE_VERSION
- [ ] N-API integration in `.pro` files
- [ ] LIBS link libraries in `.pro` files
- [ ] Global replacement `QOhosOptional` → `nonstd::optional`
- [ ] `qohosenums.h` → `qohosqpaenums.h`
- [ ] `qohosimageformat` → `qohosiconengine`
- [ ] `qohospointerstyle.h` → `qohosqpaenums.h`
- [ ] Enum namespace `QtOhos::` → `QtOhosQpa::`
- [ ] Permission API parameter `QAbilityPeer` → `QNapi::Object`
- [ ] `maximize` signature
- [ ] `startSystemMove` signature
- [ ] Input method `onInsertPreviewText` signature
- [ ] Conditional compilation for new APIs (distributed data object/drag key frames/maximize options)
- [ ] Include path normalization
- [ ] Timeout type `milliseconds` → `nanoseconds`
- [ ] `QOhosSettings` namespace → singleton class
- [ ] Path mapping methods removed from `QOhosPlatformServices`
- [ ] Methods removed from `QOhosPluginCore` (getModule/optAppLaunchParam/tagWidgetOrWindowAsFloatWindow, etc.)
- [ ] `makeEmptyNativePixelMap` → `makeEmptyOhosNativePixelMap`
- [ ] JsScopeData pattern adaptation

---

## Appendix A: Complete file difference index

### A.1 qtohosextras files with real content differences (17)

| File | Main changes |
|------|---------|
| `ohosextras.pro` | Build system (napi + new files) |
| `qohosabilitycontext.h` | Distributed data object API |
| `qohosabilitycontext.cpp` | Optional migration + new API implementation |
| `qohosappbundleinfo.cpp` | Optional migration |
| `qohosappcontext.cpp` | Documentation + Optional migration |
| `qohosapppermissionsutils.cpp` | Optional migration |
| `qohosfileshare.cpp` | Optional migration + qAndThen |
| `qohosmultimediautils.cpp` | Optional migration |
| `qohosoperationstatus.cpp` | Optional migration |
| `qohospasteboard.cpp` | Documentation tweak |
| `qohossharekit.cpp` | Documentation + Optional migration |
| `qohosstartoptions.cpp` | Optional migration |
| `qohosstartrequest.cpp` | Optional migration |
| `qohoswant.cpp` | LaunchReason documentation |
| `qohoswantutils.cpp` | Optional migration |
| `qohoswindowutils.h` | Drag key frame + maximize options API |
| `qohoswindowutils.cpp` | New API implementation |

### A.2 qtohosextras files with CRLF-only differences (24)

Identical content; only the line endings changed from CRLF to LF:
`qohosenums.h`, `qohosapppermissions.h`, `qohosfileshare.h`, `qohossharekit.h`, `qohosstartoptions.h`, `qohosstartrequest.h`, `qohoswant.h`, `qohospasteboard.h`, `qohosfileutils.h`, `qohosappcontext.h`, `qohosappbundleinfo.h`, `qohosappbundleinfo_p.h`, `qohosbundlemanager.h`, `qohosoperationstatus.h`, `qohosoperationstatus_p.h`, `qohosmultimediautils.h`, `qohosuiabilitycontext.h`, `qohossharekit_p.h`, `qohosstartoptions_p.h`, `qohosstartrequest_p.h`, `qohoswantutils_p.h`, `qohosapppermissionsutils_p.h`, `qtohosextrasglobal.h`, `qohosfileutils.cpp`

### A.3 New platform plugin files (8)

`doc/jsscopedata.md`, `qohosdeviceinfo_p.h`, `qohosdeviceinfo.cpp`, `qohosdragkeyframepolicy.h`, `qohosiconengine.cpp`, `qohosiconengine.h`, `qohosqpaenums.h`, `qohoswindowmaximizeoptions.h`

### A.4 Removed/renamed platform plugin files (4)

| Status | File |
|------|------|
| Renamed | `qohosenums.h` → `qohosqpaenums.h` |
| Renamed | `qohosimageformat.h/cpp` → `qohosiconengine.cpp/h` |
| Removed | `qohospointerstyle.h` |
| Removed | `qohosimageformat.cpp` |

### A.5 New example (1)

`examples/qtohosextras/windowdragkeyframe/` — drag key frame policy example

---

## Appendix B: Enum change quick reference

| Enum | 5.12 location | 5.15 location | Change |
|------|----------|----------|------|
| `SelectionMode` | `qohossharekit.h` | `qohosqpaenums.h` | Moved |
| `ShareAbilityType` | `qohossharekit.h` | `qohosqpaenums.h` | Moved |
| `SharePreviewMode` | `qohossharekit.h` | `qohosqpaenums.h` | Moved |
| `LaunchReason` | `qohosenums.h` | `qohosqpaenums.h` | Moved |
| `ContinueState` | `qohosenums.h` | `qohosqpaenums.h` | Moved |
| `WindowMode` | `qohosenums.h` | `qohosqpaenums.h` | Moved |
| `ColorMode` | `qohosenums.h` | `qohosqpaenums.h` | Moved |
| `ProcessMode` | `qohosenums.h` | `qohosqpaenums.h` | **Adds** `ATTACH_TO_STATUS_BAR_ITEM` |
| `StartupVisibility` | `qohosenums.h` | `qohosqpaenums.h` | Moved |
| `SupportWindowMode` | `qohosenums.h` | `qohosqpaenums.h` | Moved |
| `AnimationType` | `qohosenums.h` (WindowCreateParams) | `qohosqpaenums.h` | Namespace change |
| `ContentType` | `qohosenums.h` (NotificationKit) | `qohosqpaenums.h` (ohos) | Namespace change |
| `PointerStyle` | `qohospointerstyle.h` | `qohosqpaenums.h` | **Adds** `SCREENRECORDER_CURSOR` |
| `WindowEventType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | Moved |
| `WindowStatusType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | Moved |
| `AvoidAreaType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | Moved |
| `RectChangeReason` | `qohoswindowproxy.h` | `qohosqpaenums.h` | Moved |
| `MaximizePresentation` | `qohoswindowproxy.h` | `qohosqpaenums.h` | **Adds** `ENTER_IMMERSIVE_DISABLE_TITLE_AND_DOCK_HOVER` |
| `ModalityType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | Moved |
| `JsDisplayOrientation` | `qohosdisplayinfo.h` | `qohosqpaenums.h` (Orientation) | Moved + renamed |
| `DisplaySourceMode` | `qohosdisplayinfo.h` | `qohosqpaenums.h` | Moved |
| `OnContinueResult` | `qohosplugincore.h` (QOhosAbilityOnContinueResult) | `qohosqpaenums.h` | Moved + type alias |
| `Flags` | — | `qohosqpaenums.h` | **New** |
| `DocumentSelectMode` | — | `qohosqpaenums.h` | **New** |
| `Direction` | — | `qohosqpaenums.h` | **New** |
| `EnterKeyType` | — | `qohosqpaenums.h` | **New** |
| `RequestKeyboardReason` | — | `qohosqpaenums.h` | **New** |
| `TextInputType` | — | `qohosqpaenums.h` | **New** |
| `NetBearType` | — | `qohosqpaenums.h` | **New** |
| `NetCap` | — | `qohosqpaenums.h` | **New** |
| `AcrossDisplayPresentation` | — | `qohosqpaenums.h` (Api26) | **New** |

---

*Document generated: 2026-10-08*
*Based on source comparison: qt-harmonyos-src (5.12.12, tag a5efc71) vs qt5.15.16 (5.15.16, tag 4af6065)*
