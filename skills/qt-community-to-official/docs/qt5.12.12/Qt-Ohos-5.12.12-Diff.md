# Qt for HarmonyOS (OHOS) Version Difference Analysis

## Qt 5.12.12 (qt-harmonyos-src) vs Qt 5.15.12 (tqtc-qt5-5.15)

> **Purpose**: developers and the `qt-community-to-official` skill can use this document to switch between the Qt 5.12.12 and Qt 5.15.12 HarmonyOS ports.

---

## Contents

1. [Overview of differences](#1-overview-of-differences)
2. [The qtohosextras module (public API)](#2-the-qtohosextras-module-public-api)
3. [QPA platform plugin differences](#3-qpa-platform-plugin-differences)
4. [NAPI build system refactoring (the most important change)](#4-napi-build-system-refactoring-the-most-important-change)
5. [qohosdeviceinfo file relocation](#5-qohosdeviceinfo-file-relocation)
6. [Removal of qohospointerstyle.h](#6-removal-of-qohospointerstyleh)
7. [QPA plugin source differences (qohosplugincore / qohosplatformintegration / qohosplatformtheme)](#7-qpa-plugin-source-differences-qohosplugincore--qohosplatformintegration--qohosplatformtheme)
8. [mkspecs and build configuration differences](#8-mkspecs-and-build-configuration-differences)
9. [OHOS plugin differences per submodule](#9-ohos-plugin-differences-per-submodule)
10. [Permission configuration (module.json5)](#10-permission-configuration-modulejson5)
11. [DevEco application template](#11-deveco-application-template)
12. [Header list and class name index](#12-header-list-and-class-name-index)
13. [Line-ending differences](#13-line-ending-differences)
14. [Version switching migration guide](#14-version-switching-migration-guide)

---

## 1. Overview of differences

| Dimension | 5.12.12 (community/open-source baseline) | 5.15.12 (tqtc commercial edition) | Difference level |
|---|---|---|---|
| **qtohosextras public API** | 17 public headers | Identical (41 files compared one by one) | **No difference** |
| **QPA platform plugin source** | 214 .h/.cpp files | 214 files with identical content | **No difference** |
| **NAPI build approach** | `include(node-addon-api.pri)` + `-lace_napi.z` | `CONFIG += qnapi` (new qnapi.prf) | **Global refactoring** |
| **qohosdeviceinfo location** | `corelib/kernel/` | `plugins/platforms/ohos/` | **File relocation** |
| **qohospointerstyle.h** | Present in the QPA plugin | Removed | **File removal** |
| **qohosplugincore.h/.cpp** | Original version | New NAPI modules, enum refactoring, API changes | **Different** |
| **qohosplatformintegration** | Original version | New settings cache, PC-mode window capabilities | **Different** |
| **qohosplatformtheme.cpp** | QPixmap::loadFromData | QImageReader + setScaledSize | **Different** |
| **qmake.conf warnings** | `-Wno-error` | `-Werror` | **Configuration change** |
| **Permissions (module.json5)** | 17 permissions | Identical | **No difference** |
| **DevEco template** | Full template | Identical | **No difference** |
| **Per-module plugin source** | Original version | Minor enhancements (HEIC, super resolution, etc.) | **Minor differences** |
| **Line endings** | LF (Unix) | CRLF (Windows) | **Format difference** |

**Key conclusion**: the **public API of the HarmonyOS port is identical** in both versions. The differences are concentrated in the **build system refactoring** (how NAPI is pulled in), **internal file organization** (qohosdeviceinfo relocation), and a few **internal QPA plugin implementation enhancements**.

---

## 2. The qtohosextras module (public API)

### 2.1 Identical parts

The following are **identical file by file, byte by byte** in both versions (41 source files + headers + .pro in total):

**Public headers (17)**:

| Header | Class/function |
|---|---|
| `qohosabilitycontext.h` | `QOhosAbilityContext` — Ability context |
| `qohosuiabilitycontext.h` | `QOhosUiAbilityContext` — UIAbility context |
| `qohosappcontext.h` | `QOhosAppContext` — application context |
| `qohosappbundleinfo.h` | `QOhosAppBundleInfo` — bundle information |
| `qohosapppermissions.h` | `QOhosAppPermissions` — application permissions |
| `qohosbundlemanager.h` | `QOhosBundleManager` — bundle manager |
| `qohosenums.h` | OHOS enum definitions |
| `qohosfileshare.h` | `QOhosFileShare` — file sharing |
| `qohosfileutils.h` | `QOhosFileUtils` — file utilities |
| `qohosmultimediautils.h` | `QOhosMultimediaUtils` — multimedia utilities |
| `qohosoperationstatus.h` | `QOhosOperationStatus` — operation status |
| `qohospasteboard.h` | `QOhosPasteboard` — clipboard |
| `qohossharekit.h` | `QOhosShareKit` — Share Kit |
| `qohosstartoptions.h` | `QOhosStartOptions` — start options |
| `qohosstartrequest.h` | `QOhosStartRequest` — start request |
| `qohoswant.h` | `QOhosWant` — Want cross-component communication |
| `qohoswindowutils.h` | `QOhosWindowUtils` — window utilities |
| `qtohosextrasglobal.h` | Global macro definitions |

**Private headers (7)**:
- `qohosappbundleinfo_p.h`, `qohosapppermissionsutils_p.h`, `qohosoperationstatus_p.h`
- `qohossharekit_p.h`, `qohosstartoptions_p.h`, `qohosstartrequest_p.h`, `qohoswantutils_p.h`

**Build files**:
- `qtohosextras.pro`, `src/src.pro`, `src/ohosextras/ohosextras.pro`
- `.qmake.conf`, `sync.profile`

**All .cpp implementation files**: 15, identical when compared one by one.

### 2.2 Migration impact

> **Developers don't need to change any qtohosextras API calls**. All public class names, method signatures, enum values, and namespaces are identical in both versions.

---

## 3. QPA platform plugin differences

### 3.1 Source file list comparison

The QPA platform plugin (`qtbase/src/plugins/platforms/ohos/`) has 214 .h/.cpp source files in total, with **identical content**.

Only the following file-level differences exist:

| File | 5.12.12 | 5.15.12 | Notes |
|---|---|---|---|
| `qohospointerstyle.h` | ✅ Present | ❌ Removed | Pointer style enum header |
| `qohosdeviceinfo_p.h` | ❌ Not in this directory | ✅ Added | Moved here from corelib |
| `qohosdeviceinfo.cpp` | ❌ Not in this directory | ✅ Added | Moved here from corelib |

### 3.2 ohos.pro differences (QPA plugin build file)

```diff
--- 5.12.12 ohos.pro
+++ 5.15.12 ohos.pro

 # HEADERS section:
-    $$PWD/qohospointerstyle.h \           # Removed: pointer style header
+    $$PWD/qohosdeviceinfo_p.h \            # Added: device info header (moved in from corelib)

 # SOURCES section:
+    $$PWD/qohosdeviceinfo.cpp \            # Added: device info source (moved in from corelib)

 # LIBS section:
-    -lace_napi.z \                        # Removed: direct NAPI library link
     -lace_ndk.z \                         # Kept

 # Bottom:
-include($$PWD/../../../3rdparty/node-addon-api.pri)   # Removed: direct include of the NAPI pri
+CONFIG += qnapi                                        # Added: use the qnapi feature
+
+include($$PWD/../../../3rdparty/optional-lite.pri)    # Added: optional-lite dependency
```

### 3.3 QPA plugin source difference details

The following 4 internal QPA plugin source files have content differences (not public API; developers usually don't call them directly):

| File | Lines changed | Type of change |
|---|---|---|
| `qohosplugincore.h` | ~20 lines | Enum refactoring, new method, type change |
| `qohosplugincore.cpp` | ~50 lines | New NAPI modules, code style, API changes |
| `qohosplatformintegration.h` | ~3 lines | New member variable |
| `qohosplatformintegration.cpp` | ~16 lines | Settings cache, PC-mode window capabilities |
| `qohosplatformtheme.cpp` | ~30 lines | Improved file icon rendering |

See [section 7](#7-qpa-plugin-source-differences-qohosplugincore--qohosplatformintegration--qohosplatformtheme) for details.

---

## 4. NAPI build system refactoring (the most important change)

### 4.1 Overview of the change

5.15.12 introduces a brand-new **`qnapi.prf`** qmake feature file that centrally manages the NAPI (node-addon-api) header includes and library linking. Every module that previously did a direct `include(node-addon-api.pri)` + `-lace_napi.z` now uses `CONFIG += qnapi` instead.

### 4.2 New file: qnapi.prf

**Path**: `qtbase/mkspecs/features/ohos/qnapi.prf` (exists only in 5.15.12)

```qmake
# Build dependency for using QtCore's QNapi helpers (kernel/qnapi_p.h).
#
# Enable from any qtbase or sibling-submodule .pro/.pri with:
#
#     CONFIG += qnapi
#
# Provides everything a consumer of qnapi_p.h needs:
#   - the bundled node-addon-api headers (include path + NAPI defines), and
#   - the OHOS NAPI runtime library (-lace_napi.z).
include($$clean_path($$PWD/../../../src/3rdparty/node-addon-api.pri))
LIBS_PRIVATE += -lace_napi.z
```

### 4.3 Affected .pro/.pri files (complete list)

All of the following files moved from the old approach to the new one:

| Module | File path | 5.12.12 (old) | 5.15.12 (new) |
|---|---|---|---|
| QPA platform plugin | `qtbase/src/plugins/platforms/ohos/ohos.pro` | `include(node-addon-api.pri)` + `-lace_napi.z` | `CONFIG += qnapi` + `include(optional-lite.pri)` |
| QtCore kernel | `qtbase/src/corelib/kernel/kernel.pri` | `LIBS_PRIVATE += -lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Network bearer | `qtbase/src/plugins/bearer/ohos/src/src.pro` | `LIBS_PRIVATE += -lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Print support | `qtbase/src/plugins/printsupport/ohos/ohos.pro` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Font database | `qtbase/src/platformsupport/fontdatabases/ohos/openharmony.pri` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Multimedia | `qtmultimedia/src/plugins/ohos/src/src.pro` | `-lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Audio | `qtmultimedia/src/plugins/ohos-audio/src/src.pro` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Sensors | `qtsensors/src/plugins/sensors/ohos/ohos.pro` | `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Speech synthesis | `qtspeech/src/plugins/tts/ohos/ohos.pro` | `LIBS += -lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| WebView | `qtwebview/src/plugins/ohos/ohos.pro` | `-lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |
| Positioning | `qtlocation/src/plugins/position/ohos/ohos.pro` | `-lace_napi.z` + `include(node-addon-api.pri)` | `CONFIG += qnapi` |

### 4.4 Migration impact

> **When migrating to 5.15.12**: if you have custom .pro files that reference NAPI, replace:
> ```qmake
> # Old approach (5.12.12)
> LIBS += -lace_napi.z
> include($$PWD/path/to/node-addon-api.pri)
> ```
> with:
> ```qmake
> # New approach (5.15.12)
> CONFIG += qnapi
> ```
>
> **When migrating back to 5.12.12**: replace `CONFIG += qnapi` with the direct references again.

---

## 5. qohosdeviceinfo file relocation

### 5.1 Location change

| Version | Header path | Source path | Referenced from |
|---|---|---|---|
| 5.12.12 | `qtbase/src/corelib/kernel/qohosdeviceinfo_p.h` | `qtbase/src/corelib/kernel/qohosdeviceinfo.cpp` | `corelib/kernel/kernel.pri` |
| 5.15.12 | `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo_p.h` | `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo.cpp` | `plugins/platforms/ohos/ohos.pro` |

### 5.2 Content differences

The header content is **almost identical**; the only difference is the export macro:

```diff
--- 5.12.12 (corelib version, with Q_CORE_EXPORT)
+++ 5.15.12 (QPA plugin version, no export macro)

-Q_CORE_EXPORT void init(QMap<Type, QVariant> devinfo);
-Q_CORE_EXPORT QVariant getProperty(Type prop);
+void init(QMap<Type, QVariant> devinfo);
+QVariant getProperty(Type prop);

-Q_CORE_EXPORT QOhosOptional<RecognizedDeviceType> tryGetRecognizedDeviceType();
-Q_CORE_EXPORT bool isTablet();
-Q_CORE_EXPORT bool is2in1();
-Q_CORE_EXPORT bool isPhone();
-Q_CORE_EXPORT int sdkApiVersion();
-Q_CORE_EXPORT bool isCurrentDeviceSupported();
+QOhosOptional<RecognizedDeviceType> tryGetRecognizedDeviceType();
+bool isTablet();
+bool is2in1();
+bool isPhone();
+int sdkApiVersion();
+bool isCurrentDeviceSupported();
```

> **Reason**: after moving from the QtCore library to the QPA plugin, the `Q_CORE_EXPORT` export macro is no longer needed (used inside the plugin only, not exported across libraries).

### 5.3 API unchanged

The API provided by the `QOhosDeviceInfo` namespace is identical:

- `Type` enum: `deviceType`, `manufacture`, `brand`, `marketName`, ... `udid`, `distributionOSName`, ...
- `RecognizedDeviceType` enum: `_2in1`, `tablet`, `phone`
- Functions: `init()`, `getProperty()`, `tryGetRecognizedDeviceType()`, `isTablet()`, `is2in1()`, `isPhone()`, `sdkApiVersion()`, `isCurrentDeviceSupported()`

### 5.4 Migration impact

> **No direct impact on developers**. `qohosdeviceinfo` is an internal private header (`_p.h`) and not part of the public API.
>
> If you referenced `QtCore/private/qohosdeviceinfo_p.h` directly, in 5.15.12 you need to reference it from the QPA plugin directory instead.

---

## 6. Removal of qohospointerstyle.h

### 6.1 Description of the change

The 5.12.12 QPA plugin contains `qohospointerstyle.h`, which defines the `QOhosPointerStyle` enum (44 pointer style values) and its `OhosEnumMeta` template specialization. This file has been removed in 5.15.12.

### 6.2 Reason for removal

The enum definitions have probably moved into `qohosenums.h` for central management (5.15.12's `qohosplugincore.h` adds `#include <qohosenums.h>` and changes `QOhosAbilityOnContinueResult` from a custom enum to a reference to `enums::ohos::app::ability::AbilityConstant::OnContinueResult`).

### 6.3 Migration impact

> **No direct impact on developers**. `qohospointerstyle.h` is an internal QPA plugin header and not part of the public API.

---

## 7. QPA plugin source differences (qohosplugincore / qohosplatformintegration / qohosplatformtheme)

### 7.1 qohosplugincore.h differences

```diff
--- 5.12.12
+++ 5.15.12

 // Header include change
-#include <array>
+#include <qohosenums.h>

 // New virtual function
+virtual void forceResolveQWindowDestroyPromiseIfPresent(Napi::Env env) = 0;

 // Enum refactoring: QOhosAbilityOnContinueResult
-enum class QOhosAbilityOnContinueResult
-{
-    AGREE,
-    REJECT,
-    MISMATCH,
-};
+using QOhosAbilityOnContinueResult = enums::ohos::app::ability::AbilityConstant::OnContinueResult;

 // OhosEnumMeta template specialization removed
-template<>
-struct OhosEnumMeta<QOhosAbilityOnContinueResult>
-{
-    static constexpr const char *fullTypeName = "@ohos.app.ability.AbilityConstant.OnContinueResult";
-    static constexpr std::array<std::pair<QOhosAbilityOnContinueResult, const char *>, 3> enumeratorsNames = {{ ... }};
-};

 // Timeout parameter type change
-Q_REQUIRED_RESULT bool tryInvokeInQtThreadAndTryWaitForContinue(
-    std::function<void(std::function<void()>)> &&task,
-    std::chrono::milliseconds timeout);
+Q_REQUIRED_RESULT bool tryInvokeInQtThreadAndTryWaitForContinue(
+    std::function<void(std::function<void()>)> &&task,
+    std::chrono::nanoseconds timeout);
```

### 7.2 qohosplugincore.cpp differences

**New NAPI module registrations**:
```diff
+    "@ohos.data.distributedDataObject",    // distributed data object
+    "@ohos.net.connection",                // network connection management
```

**New virtual function implementation**:
```diff
+void DummyQAbilityPeer::forceResolveQWindowDestroyPromiseIfPresent(Napi::Env)
+{
+}
```

**API changes**:
- `hasValue()` → `has_value()` (optional-lite API upgrade)
- `std::chrono::milliseconds timeout` → `std::chrono::nanoseconds timeout`

**Code style changes**: braces removed from many single-line if statements (no effect on logic).

### 7.3 qohosplatformintegration.h differences

```diff
 private:
+    std::shared_ptr<void> m_settingsCacheHandle;    // Added: settings cache handle
+
     std::shared_ptr<void> m_eglDisplayHandle;
```

### 7.4 qohosplatformintegration.cpp differences

**New settings cache initialization**:
```diff
+#include <qohossettings.h>

 // Added in the constructor:
+m_settingsCacheHandle = QOhosSettings::instance().installSettingsCache();
```

**Window capability change (NonFullScreenWindows)**:
```diff
         case MultipleWindows: return true;
-        case WindowManagement: return true;
+        case WindowManagement:
+        case NonFullScreenWindows:
+            return QOhosSettings::instance().isWindowPcModeEnabled();
```

> **Note**: in 5.15.12, `WindowManagement` no longer unconditionally returns `true`; it is decided by `QOhosSettings::isWindowPcModeEnabled()`. Support for the `NonFullScreenWindows` capability was added, which also depends on the PC-mode setting.

### 7.5 qohosplatformtheme.cpp differences

**New headers**:
```diff
+#include <QtCore/qbuffer.h>
+#include <QtGui/qimagereader.h>
```

**Improved file icon rendering**:

5.12.12 loads with `QPixmap::loadFromData` and then scales with `scaled()`:
```cpp
// 5.12.12: simple load + scale afterwards
QPixmap pixmap;
pixmap.loadFromData(resourceContentBuffer.Data(), resourceContentBuffer.ByteLength());
return pixmap.scaled(size, Qt::KeepAspectRatio, Qt::SmoothTransformation);
```

5.15.12 switches to `QImageReader` + `setScaledSize` for efficient on-demand scaling:
```cpp
// 5.15.12: QImageReader scales on demand, avoiding loading the full-size image and then scaling it
QBuffer svgResourceBuffer(&svgResourceContent);
QImageReader imageReader(&svgResourceBuffer);
const auto sourceSize = imageReader.size();
const auto targetSize = sourceSize.scaled(requestedSize, Qt::KeepAspectRatio);
imageReader.setScaledSize(targetSize);
const auto image = imageReader.read();
return QPixmap::fromImage(image);
```

**Function signature changes**:
```diff
-QOhosOptional<QPixmap> tryGetFilePixmapByResourceObject(
-    QtOhos::JsState &jsState, QNapi::Object resource)
+QOhosOptional<QPixmap> tryGetFilePixmapByResourceObject(
+    QtOhos::JsState &jsState, QNapi::Object resource, const QSize &requestedSize)

-QOhosOptional<QPixmap> tryGetFilePixmapByFilenameExtension(
-    QtOhos::JsState &jsState, const std::string &filenameExtension)
+QOhosOptional<QPixmap> tryGetFilePixmapByFilenameExtension(
+    QtOhos::JsState &jsState, const std::string &filenameExtension, const QSize &requestedSize)
```

> **Note**: these are internal QPA plugin functions and don't affect the public API. They improve file icon rendering efficiency, especially for SVG icons.

### 7.6 Migration impact

> All of these differences are in the internal QPA plugin implementation and **don't affect the public API developers use**. However, the following behavior changes are worth noting:
>
> 1. **Window management**: in 5.15.12 the `WindowManagement` and `NonFullScreenWindows` capabilities are controlled by the PC-mode setting; make sure `QOhosSettings::isWindowPcModeEnabled()` returns the expected value on the target device.
> 2. **Timeout precision**: the timeout parameter of `tryInvokeInQtThreadAndTryWaitForContinue` changed from milliseconds to nanoseconds, a precision increase of 1,000,000x. If you called this internal function directly, adjust the timeout value.
> 3. **Distributed data object**: 5.15.12 adds support for the `@ohos.data.distributedDataObject` NAPI module.

---

## 8. mkspecs and build configuration differences

### 8.1 qmake.conf differences

**Path**: `qtbase/mkspecs/ohos-clang/qmake.conf`

```diff
--- 5.12.12
+++ 5.15.12

     -Wformat \
-    -Wno-error
-
-QMAKE_CXXFLAGS_WARN_ON += -Wno-error
-QMAKE_CFLAGS_WARN_ON += -Wno-error
+    -Werror
```

> **Impact**: 5.15.12 treats warnings as errors (`-Werror`). When migrating, make sure the code compiles without warnings, or the build will fail. When needed, temporarily add `-Wno-error` to restore the old behavior.

### 8.2 openharmonydeployqt.pro differences

```diff
--- 5.12.12
+++ 5.15.12

     shellcommandoutputstream.cpp
+
+DEFINES -= QT_NO_JAVA_STYLE_ITERATORS
```

> **Impact**: the deployment tool enables Java-style iterator support in 5.15.12.

### 8.3 Other unchanged build configuration

The following configuration files are **identical** in both versions:

| File | Notes |
|---|---|
| `ohos-clang/qplatformdefs.h` | Platform definitions |
| `features/ohos/ohos_deployment.prf` | Deployment feature |
| `configure.json` | Configuration detection |
| `platformheaders/ohosfunctions/qohosfunctions.h` | Platform functions header |
| `platformheaders/ohosfunctions/ohosfunctions.pri` | Platform functions pri |
| `tools/openharmonydeployqt/main.cpp` | Deployment tool main program |

---

## 9. OHOS plugin differences per submodule

### 9.1 .pro file differences (all from the NAPI refactoring)

The .pro file differences in all submodules are **only the NAPI build approach change** (see [section 4](#4-napi-build-system-refactoring-the-most-important-change)); there are no other configuration differences.

### 9.2 Source content differences

The following OHOS plugin source files have minor content differences (all feature enhancements or API adaptations):

#### Multimedia (qtmultimedia)

| File | Difference | Notes |
|---|---|---|
| `camera/qohoscameracommon.cpp` | +3 lines | Adds `CAMERA_FORMAT_HEIC` format support |
| `camera/qohosimagecommon.cpp` | Minor | Common image code adaptation |
| `mediaplayer/mediaplayer.pri` | Minor | pri file adjustment |
| `mediaplayer/qohosavplayer.cpp` | +9 lines | Adds handling of the `AV_ERR_SUPER_RESOLUTION_UNSUPPORTED`, `AV_ERR_SUPER_RESOLUTION_NOT_ENABLED`, and `AV_ERR_IO_CLEARTEXT_NOT_PERMITTED` error codes |

#### Sensors (qtsensors)

| File | Difference | Notes |
|---|---|---|
| `ohossensorbackendbase.h` | 1 line | `std::numeric_limits<qreal>::min()` → `lowest()` (fixes minimum-value semantics) |
| `ohosmagnetometerbackend.cpp` | Minor | Magnetometer backend adaptation |
| `ohossensorsmanager.cpp` | Minor | Sensor manager adaptation |
| `ohossensorutils.cpp` | Minor | Sensor utilities adaptation |

#### Speech synthesis (qtspeech)

| File | Difference | Notes |
|---|---|---|
| `qtexttospeech_ohos.cpp` | ~17 lines | `QSet::toList()` → `values()`, code style changes |
| `corespeechkit/texttospeechproxy.cpp` | Minor | TTS proxy adaptation |
| `qohosexpected_p.h` | Minor | expected helper header adaptation |

#### WebView (qtwebview)

| File | Difference | Notes |
|---|---|---|
| `qohoswebview.cpp` | +12 lines | Adds `httpUserAgent()` / `setHttpUserAgent()` methods (empty stub implementations) |

#### Positioning (qtlocation)

| File | Difference | Notes |
|---|---|---|
| `geoservices/ohosmapkit/qpoicategoryohosmapkit.cpp` | Minor | POI category adaptation |

### 9.3 Identical submodules

The OHOS plugin source of the following submodules is **identical** in both versions (no content differences at all):

- **Bluetooth** (`qtconnectivity/src/bluetooth/ohos/`): all 17 files identical
- **Print support** (`qtbase/src/plugins/printsupport/ohos/`): all 11 files identical
- **Styles** (`qtbase/src/plugins/styles/ohos/`): all 5 files identical
- **Network bearer** (`qtbase/src/plugins/bearer/ohos/`): all 19 files identical
- **Font database** (`qtbase/src/platformsupport/fontdatabases/ohos/`): all 3 files identical
- **Deployment tool** (`qtbase/src/tools/openharmonydeployqt/`): all 4 files identical
- **Serial port** (`qtserialport/src/serialport/ohos/`): all 7 files identical

### 9.4 Migration impact

> The submodule differences are all **internal feature enhancements** and don't affect the public API. Developers don't need to change application code. The HEIC format and super-resolution error codes in multimedia are a natural evolution brought by system SDK upgrades.

---

## 10. Permission configuration (module.json5)

### 10.1 Identical

The permission configuration file `qtbase/src/harmonyos/templates/entry/src/main/module.json5` is **identical** in both versions.

### 10.2 Permission list (17)

| Permission | Purpose |
|---|---|
| `ohos.permission.SYSTEM_FLOAT_WINDOW` | Floating window |
| `ohos.permission.FILE_ACCESS_PERSIST` | Persistent file access |
| `ohos.permission.PRINT` | Printing |
| `ohos.permission.PREPARE_APP_TERMINATE` | Prepare for app termination |
| `ohos.permission.STORE_PERSISTENT_DATA` | Persistent data storage |
| `ohos.permission.INTERNET` | Network |
| `ohos.permission.READ_PASTEBOARD` | Read clipboard |
| `ohos.permission.CAMERA` | Camera |
| `ohos.permission.MICROPHONE` | Microphone |
| `ohos.permission.CUSTOM_SCREEN_CAPTURE` | Custom screen capture |
| `ohos.permission.ACCELEROMETER` | Accelerometer |
| `ohos.permission.GYROSCOPE` | Gyroscope |
| `ohos.permission.APPROXIMATELY_LOCATION` | Approximate location |
| `ohos.permission.LOCATION` | Precise location |
| `ohos.permission.GET_WIFI_INFO` | Wi-Fi information |
| `ohos.permission.ACCESS_BLUETOOTH` | Bluetooth |
| `ohos.permission.GET_FILE_ICON` | File icons |

### 10.3 Ability declarations

- `QAbility`: main entry Ability (launchType=specified, continuable)
- `QEmbeddedUiExtensionAbility`: embedded UI extension
- `QBundledEmbeddedUiExtensionAbility`: bundled embedded UI extension

---

## 11. DevEco application template

### 11.1 Identical

All core configuration files of the DevEco Studio application template (`qtbase/src/harmonyos/templates/`) are **identical** in both versions:

| File | Notes |
|---|---|
| `build-profile.json5` | Build configuration (runtimeOS: HarmonyOS, compatibleSdkVersion: 5.0.0(12)) |
| `AppScope/app.json5` | App configuration (bundleName: com.ohos.ohosqttemplate) |
| `oh-package.json5` | Package configuration |
| `entry/src/main/module.json5` | Module manifest (including permissions) |
| `entry/src/main/cpp/CMakeLists.txt` | CMake build |
| `entry/src/main/ets/qability/QAbility.ets` | ArkTS Ability |
| `README.md` | Template description |

### 11.2 Build artifact differences

The 5.12.12 template directory contains build cache files (`.hvigor/`, `.idea/`, `entry/.cxx/`, `oh_modules/`), which are build artifacts rather than source. In the 5.15.12 template directory these caches have been cleaned up.

> **Migration impact**: none. Build artifacts shouldn't be under version control; cleaning them up is the right thing to do.

---

## 12. Header list and class name index

### 12.1 qtohosextras public headers (identical in both versions)

```
QtOhosExtras/
├── qohosabilitycontext.h        → QOhosAbilityContext
├── qohosappbundleinfo.h         → QOhosAppBundleInfo
├── qohosappcontext.h            → QOhosAppContext
├── qohosapppermissions.h        → QOhosAppPermissions
├── qohosbundlemanager.h         → QOhosBundleManager
├── qohosenums.h                 → OHOS enum definitions
├── qohosfileshare.h             → QOhosFileShare
├── qohosfileutils.h             → QOhosFileUtils
├── qohosmultimediautils.h       → QOhosMultimediaUtils
├── qohosoperationstatus.h       → QOhosOperationStatus
├── qohospasteboard.h            → QOhosPasteboard
├── qohossharekit.h              → QOhosShareKit
├── qohosstartoptions.h          → QOhosStartOptions
├── qohosstartrequest.h          → QOhosStartRequest
├── qohosuiabilitycontext.h      → QOhosUiAbilityContext
├── qohoswant.h                  → QOhosWant
├── qohoswindowutils.h           → QOhosWindowUtils
├── qtohosextrasglobal.h         → global macros
└── qtohosextrasversion.h        → version header
```

### 12.2 QPA platform plugin internal headers (not public)

The following headers live in the QPA plugin; developers usually don't reference them directly:

| Header | 5.12.12 | 5.15.12 | Notes |
|---|---|---|---|
| `qohosplugincore.h` | ✅ | ✅ (changed) | Plugin core |
| `qohosplatformintegration.h` | ✅ | ✅ (changed) | Platform integration |
| `qohosplatformtheme.h` | ✅ | ✅ | Platform theme |
| `qohosplatformwindow.h` | ✅ | ✅ | Platform window |
| `qohosplatformscreen.h` | ✅ | ✅ | Platform screen |
| `qohosplatformclipboard.h` | ✅ | ✅ | Clipboard |
| `qohosplatformcursor.h` | ✅ | ✅ | Cursor |
| `qohosplatformdrag.h` | ✅ | ✅ | Drag and drop |
| `qohoseventdispatcher.h` | ✅ | ✅ | Event dispatching |
| `qohosinputcontext.h` | ✅ | ✅ | Input method |
| `qohossettings.h` | ✅ | ✅ | Settings |
| `qohospointerstyle.h` | ✅ | ❌ (removed) | Pointer style |
| `qohosdeviceinfo_p.h` | ✅ (corelib) | ✅ (QPA) | Device information |
| `qohosenums.h` | ✅ | ✅ | Enums |
| ... (100+ internal headers in total) | | | |

### 12.3 Accessibility headers

All headers of the accessibility module (`qtbase/src/plugins/platforms/ohos/accessibility/`) are **identical** in both versions:

- `qohosplatformaccessibility.h` — platform accessibility implementation
- `qohosaccessibilitytree.h` — accessibility tree
- `qohosaccessibilityprovider.h` — accessibility provider
- `qohosaccessibilityarkuihelpers.h` — ArkUI accessibility helpers
- `qohosaccessibilityeventhandler.h` — accessibility event handling
- `qohosaccessibilitymenuactions.h` — accessibility menu actions
- `qohosaccessibilitynodehelpers.h` — accessibility node helpers
- `qohossafeqaccessibleinterfacewrapper.h` — safe interface wrapper

---

## 13. Line-ending differences

| Version | Line endings | Notes |
|---|---|---|
| 5.12.12 | LF (Unix) | Standard Unix line endings |
| 5.15.12 | CRLF (Windows) | Windows line endings |

> **Impact**: none on qmake builds. However, when comparing files with `diff`, line-ending differences can cause false positives. Use `diff --strip-trailing-cr` or normalize before comparing.
>
> **Note**: macOS `diff` may not show actual content differences when handling CRLF files (it returns exit code 0 even when the file contents differ). Use Python `difflib`, or normalize with `sed 's/\r$//'` first and then compare.

---

## 14. Version switching migration guide

### 14.1 Migrating from 5.12.12 to 5.15.12

#### Step 1: Update the SDK

Replace the Qt SDK with the build output of the 5.15.12 (tqtc) version.

#### Step 2: Update NAPI build references

Check the NAPI references in all `.pro` / `.pri` files:

```qmake
# Find old references
rg -n 'node-addon-api\.pri|lace_napi\.z' --type qmake

# Replace with:
# Old: LIBS += -lace_napi.z
# Old: include($$PWD/.../node-addon-api.pri)
# New: CONFIG += qnapi
```

#### Step 3: Handle -Werror

5.15.12 treats warnings as errors by default. If the code has compiler warnings:

```qmake
# Option A: fix all warnings (recommended)
# Option B: temporarily disable in the .pro
QMAKE_CXXFLAGS_WARN_ON += -Wno-error
QMAKE_CFLAGS_WARN_ON += -Wno-error
```

#### Step 4: Check qohosdeviceinfo references

If the code references `QtCore/private/qohosdeviceinfo_p.h` directly:

```cpp
// 5.12.12: referenced from corelib
#include <QtCore/private/qohosdeviceinfo_p.h>
// functions are exported with Q_CORE_EXPORT

// 5.15.12: referenced from the QPA plugin (path changed, no export macro)
// adjust the include path
```

#### Step 5: Check window capabilities

If the code relies on the `WindowManagement` capability always returning `true`:

```cpp
// 5.12.12: WindowManagement always returns true
// 5.15.12: WindowManagement returns QOhosSettings::isWindowPcModeEnabled()
// make sure PC mode is enabled, or adjust the window management logic
```

#### Step 6: Verify the build

```bash
# Build with hvigorw
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

### 14.2 Migrating from 5.15.12 to 5.12.12

#### Step 1: Update the SDK

Replace the Qt SDK with the build output of the 5.12.12 version.

#### Step 2: Revert NAPI build references

```qmake
# Find new references
rg -n 'CONFIG \+= qnapi' --type qmake

# Replace with:
# New: CONFIG += qnapi
# Old: LIBS += -lace_napi.z
#      include($$PWD/.../node-addon-api.pri)
```

#### Step 3: Handle qohosdeviceinfo

If the code references `qohosdeviceinfo` from the QPA plugin:

```cpp
// 5.15.12: referenced from the QPA plugin (no export macro)
// 5.12.12: referenced from corelib (exported with Q_CORE_EXPORT)
#include <QtCore/private/qohosdeviceinfo_p.h>
// functions have Q_CORE_EXPORT and can be called across libraries
```

#### Step 4: Restore -Wno-error

```qmake
# 5.12.12 defaults to -Wno-error; nothing special needed
# If you carried over a -Werror setting from 5.15.12, change it back to -Wno-error
```

#### Step 5: Verify the build

Same as 14.1 step 6.

### 14.3 Relationship with the community edition (qtohextras)

Both versions compared in this document use the **commercial edition** (`qtohosextras` / `QtOhosExtras`) HarmonyOS port code. To migrate from the **community edition** (`qtohextras` / `QtOhExtras`) to the commercial edition, see the migration documents in the `docs/` directory of the `qt-community-to-official` skill.

Main differences between the community and commercial editions (outside the scope of this document):

| Dimension | Community edition (qtohextras) | Commercial edition (qtohosextras) |
|---|---|---|
| Module name | `QtOhExtras` | `QtOhosExtras` |
| qmake reference | `QT += ohextras` | `QT += ohosextras` |
| Namespace | `QtOh` | `QtOhosExtras` |
| Context class | `QOhAppContext` | `QOhosAbilityContext` |
| Permission API | Synchronous (`checkPermission`) | Asynchronous (signal-slot) |
| File sharing | `QOhFileShare::shareFile()` | `QOhosAbilityContext::shareDataWithShareKit()` |
| Platform argument | `-platform openharmony` | `-platform ohos` |

### 14.4 Quick checklist

Use the following checklist during migration to make sure nothing is missed:

- [ ] NAPI build references (`CONFIG += qnapi` ↔ `include(node-addon-api.pri)` + `-lace_napi.z`)
- [ ] Warning level (`-Werror` ↔ `-Wno-error`)
- [ ] qohosdeviceinfo include path (corelib ↔ QPA plugin)
- [ ] Whether qohospointerstyle.h is referenced (removed in 5.15.12)
- [ ] Dependence on window management capabilities (`isWindowPcModeEnabled()` behavior change)
- [ ] Line endings (LF ↔ CRLF)
- [ ] qtohosextras public API (no changes needed, identical in both versions)
- [ ] Permission configuration module.json5 (no changes needed, identical in both versions)
- [ ] DevEco template (no changes needed, identical in both versions)

---

## Appendix A: Complete list of differing files

### A.1 Files with different content (OHOS-related)

| # | File path | Type of difference |
|---|---|---|
| 1 | `qtbase/src/plugins/platforms/ohos/ohos.pro` | NAPI refactoring + file relocation |
| 2 | `qtbase/src/plugins/platforms/ohos/qohosplugincore.h` | Enum refactoring + new method + type change |
| 3 | `qtbase/src/plugins/platforms/ohos/qohosplugincore.cpp` | New NAPI modules + API changes |
| 4 | `qtbase/src/plugins/platforms/ohos/qohosplatformintegration.h` | New member variable |
| 5 | `qtbase/src/plugins/platforms/ohos/qohosplatformintegration.cpp` | Settings cache + PC mode |
| 6 | `qtbase/src/plugins/platforms/ohos/qohosplatformtheme.cpp` | Improved file icon rendering |
| 7 | `qtbase/src/corelib/kernel/kernel.pri` | NAPI refactoring + qohosdeviceinfo removal |
| 8 | `qtbase/mkspecs/ohos-clang/qmake.conf` | Warning level change |
| 9 | `qtbase/src/plugins/bearer/ohos/src/src.pro` | NAPI refactoring |
| 10 | `qtbase/src/plugins/printsupport/ohos/ohos.pro` | NAPI refactoring |
| 11 | `qtbase/src/platformsupport/fontdatabases/ohos/openharmony.pri` | NAPI refactoring |
| 12 | `qtbase/src/tools/openharmonydeployqt/openharmonydeployqt.pro` | New DEFINES |
| 13 | `qtmultimedia/src/plugins/ohos/src/src.pro` | NAPI refactoring |
| 14 | `qtmultimedia/src/plugins/ohos-audio/src/src.pro` | NAPI refactoring |
| 15 | `qtmultimedia/src/plugins/ohos/src/camera/qohoscameracommon.cpp` | HEIC format |
| 16 | `qtmultimedia/src/plugins/ohos/src/camera/qohosimagecommon.cpp` | Image adaptation |
| 17 | `qtmultimedia/src/plugins/ohos/src/mediaplayer/mediaplayer.pri` | pri adjustment |
| 18 | `qtmultimedia/src/plugins/ohos/src/mediaplayer/qohosavplayer.cpp` | Super-resolution error codes |
| 19 | `qtmultimedia/src/plugins/ohos/src/mediaplayer/qohosvideorenderercontrol.cpp` | Rendering adaptation |
| 20 | `qtsensors/src/plugins/sensors/ohos/ohos.pro` | NAPI refactoring |
| 21 | `qtsensors/src/plugins/sensors/ohos/ohossensorbackendbase.h` | min→lowest |
| 22 | `qtsensors/src/plugins/sensors/ohos/ohosmagnetometerbackend.cpp` | Adaptation |
| 23 | `qtsensors/src/plugins/sensors/ohos/ohossensorsmanager.cpp` | Adaptation |
| 24 | `qtsensors/src/plugins/sensors/ohos/ohossensorutils.cpp` | Adaptation |
| 25 | `qtspeech/src/plugins/tts/ohos/ohos.pro` | NAPI refactoring |
| 26 | `qtspeech/src/plugins/tts/ohos/qtexttospeech_ohos.cpp` | QSet API + style |
| 27 | `qtspeech/src/plugins/tts/ohos/corespeechkit/texttospeechproxy.cpp` | Adaptation |
| 28 | `qtspeech/src/plugins/tts/ohos/qohosexpected_p.h` | Adaptation |
| 29 | `qtwebview/src/plugins/ohos/ohos.pro` | NAPI refactoring |
| 30 | `qtwebview/src/plugins/ohos/qohoswebview.cpp` | New userAgent stub |
| 31 | `qtlocation/src/plugins/position/ohos/ohos.pro` | NAPI refactoring |
| 32 | `qtlocation/src/plugins/geoservices/ohosmapkit/qpoicategoryohosmapkit.cpp` | POI adaptation |

### A.2 Files that exist only in 5.12.12

| File path | Notes |
|---|---|
| `qtbase/src/plugins/platforms/ohos/qohospointerstyle.h` | Pointer style enum (removed in 5.15.12) |
| `qtbase/src/corelib/kernel/qohosdeviceinfo_p.h` | Device info header (moved to the QPA plugin in 5.15.12) |
| `qtbase/src/corelib/kernel/qohosdeviceinfo.cpp` | Device info source (moved to the QPA plugin in 5.15.12) |

### A.3 Files that exist only in 5.15.12

| File path | Notes |
|---|---|
| `qtbase/mkspecs/features/ohos/qnapi.prf` | NAPI build feature (new) |
| `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo_p.h` | Device info header (moved in from corelib) |
| `qtbase/src/plugins/platforms/ohos/qohosdeviceinfo.cpp` | Device info source (moved in from corelib) |

### A.4 Identical OHOS modules (no differences at all)

| Module | File count | Notes |
|---|---|---|
| qtohosextras | 41 | Public API module, identical |
| Bluetooth (bluetooth) | 17 | Bluetooth backend, identical |
| Printing (printsupport) | 11 | Print support, identical |
| Styles (styles) | 5 | Style plugin, identical |
| Network bearer (bearer) | 19 | Network engine, identical |
| Font database (fontdb) | 3 | Font database, identical |
| Deployment tool (deploytool) | 4 | Deployment tool, identical |
| Serial port (serialport) | 7 | Serial port backend, identical |
| Map service (ohosmapkit) | 30 | Map service (.pro has the NAPI change; 1 source file differs) |
| Accessibility (accessibility) | 34 | Accessibility module, identical |
| ArkUI integration (qarkui) | 21 | ArkUI interaction layer, identical |
| Rendering layer (render) | 37 | Rendering and input handling, identical |

---

## Appendix B: qtohosextras API quick reference (common to both versions)

### B.1 Application context

```cpp
#include <QtOhosExtras/QOhosAbilityContext>

// Get the Ability context instance
auto ctx = QOhosAbilityContext::instance();

// Permission request (asynchronous signal-slot)
QObject::connect(ctx, &QOhosAbilityContext::namedPermissionRequestResponseReceived,
    [](QString permName, AppPermissions::PermissionResult result) { /* ... */ });
ctx->requestPermissionFromUserIfNeeded("ohos.permission.CAMERA");

// File sharing
auto record = QSharedPointer<ShareKit::QOhosSharedRecord>::create();
record->setTitle("title");
record->addImage(QUrl("file:///data/image.png"));
auto options = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();
QObject::connect(ctx.data(), &QOhosAbilityContext::shareKitCompleted,
    [](QByteArray, QSharedPointer<ShareKit::QOhosShareOperationResult> result) { /* ... */ });
ctx->shareDataWithShareKit({record}, options);
```

### B.2 Want cross-component communication

```cpp
#include <QtOhosExtras/QOhosWant>
#include <QtOhosExtras/QOhosStartOptions>
#include <QtOhosExtras/QOhosStartRequest>

QOhosWant want;
want.setAction("ohos.want.action.viewData");
want.addEntity("entity.system.browsable");
want.setUri(QUrl("https://example.com"));
```

### B.3 Window utilities

```cpp
#include <QtOhosExtras/QOhosWindowUtils>

// Rounded-corner window
QOhosWindowUtils::setWindowCornerRadius(window, 20.0);
// Privacy mode
QOhosWindowUtils::setWindowPrivacyMode(window, true);
// Keep the screen on
QOhosWindowUtils::setWindowKeepScreenOn(window, true);
```

### B.4 Theme

```cpp
#include <QtOhosExtras/QOhosPlatformIntegration>

// Enable the dark theme
QOhosPlatformIntegration::setDarkThemeEnabled(true);
```

### B.5 Clipboard

```cpp
#include <QtOhosExtras/QOhosPasteboard>

QOhosPasteboard::setText("text to copy");
QString text = QOhosPasteboard::text();
```

### B.6 .pro configuration

```qmake
QT += ohosextras core gui widgets
CONFIG += ohos
```

---

*This document was generated from a file-by-file, normalized comparison using Python difflib, excluding CRLF/LF line-ending differences and build artifact noise.*
