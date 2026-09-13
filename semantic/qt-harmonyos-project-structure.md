---
id: semantic-qt-harmonyos-project-structure
type: semantic
domain: tech
tags: [qt, harmonyos, cmake, project-structure, project-creation, template, glue-code, deveco]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-build, semantic-qt-harmonyos-modules]
summary: >
  The Qt HarmonyOS project structure in detail: the OHOS template (glue code) directory layout, CMake cross-compilation configuration,
  the library naming rule (QtAppConstants.ets ↔ add_library), and the two scenarios (creating from scratch / porting an existing project).
---

# The Qt HarmonyOS project structure in detail

> Templates, glue code, CMake configuration, and the library naming rule — everything you need for a Qt for HarmonyOS project skeleton in one place.
> For the platform-level relationships between AppScope, modules, products, native libs, and signingConfig, the authority is the common knowledge base's [[ohos-common-kb/semantic/hap-native-project-structure|HAP native project structure and its relationship to signing]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/hap-native-project-structure.md)). This page only explains the Qt template, the QAbility glue, `QtAppConstants.ets`, the Qt CMake targets, and the deployment rules.

## 1. The two usage scenarios

| Scenario | Description | The core difference |
|----------|-------------|---------------------|
| **Scenario one: creating from scratch** | Generating a brand-new Qt HarmonyOS application project | The Qt source goes in `entry/src/main/cpp/` |
| **Scenario two: porting an existing project** | Converting an existing Qt project into a HarmonyOS application | The glue code goes in a `HarmonyOS/` subdirectory, and `build-profile.json5` uses an absolute path pointing at the root CMakeLists.txt |

## 2. Obtaining the glue-code template

### 2.1 The modern approach (recommended): the template bundled with the Qt source

Newer Qt HarmonyOS branches **bundle the glue template in the source tree** at the standard path `<QT_SRC>/qtbase/src/harmonyos/templates`, so there's no need to download a ZIP from Gerrit.

| Qt version | Template path |
|------------|---------------|
| Qt 5.15.16 (`tqtc/harmonyos-5.15.16`) | `<QT5_15_SRC>/qtbase/src/harmonyos/templates` |
| Qt 5.12.12 (`tqtc/harmonyos-5.12.12`) | `<QT5_12_SRC>/qtbase/src/harmonyos/templates` |

```bash
# Copy the template directory straight from the Qt source tree into your project directory
cp -r <QT5_15_SRC>/qtbase/src/harmonyos/templates/. <project directory>/
```

The template directory structure:
```
templates/
├── AppScope/
├── entry/
├── hvigor/
├── qEmbeddedUiExtensionHost/
├── build-profile.json5
├── hvigorfile.ts
├── oh-package.json5
└── README.md
```

### 2.2 The standalone template archive (when there's no Qt source)

When you only have the prebuilt SDK without a full Qt source tree (for example when building on a HarmonyOS PC), download the template archive separately from the GitCode releases page.

**Download page**: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases
**Archive name**: `templates-0625.zip`

```bash
# Download it automatically with the kb-init script
bash skills/kb-init/scripts/download-template.sh --dest=workspace/templates

# Or download and extract it manually
curl -fSL -o /tmp/templates-0625.zip "<download link>"
unzip /tmp/templates-0625.zip -d workspace/templates/
```

The extracted directory structure matches the source-bundled template (`AppScope/`, `entry/`, `build-profile.json5`, and so on).
`OHOS_TEMPLATE_SRC` in `ENV.local.md` should point at `workspace/templates`.

### 2.3 The old approach (retired): downloading a ZIP from Gerrit

> **This approach is retired**: newer Qt HarmonyOS branches bundle the glue template in the source tree (see §2.1), so there's no need to download a ZIP from Gerrit.
> The old external ZIP template variables are kept in `ENV.md` only for compatibility with older `ENV.md` files and shouldn't be used.
> Copy the template from `<QT_SRC>/qtbase/src/harmonyos/templates` (when you have the source), or download the standalone archive (when you don't; see §2.2).

## 3. Directory structure

### 3.1 Scenario one: creating from scratch

```
<project directory>/                  # The root after extracting the template
├── entry/
│   ├── src/main/
│   │   ├── cpp/                      # ★ Where the Qt application code goes
│   │   │   ├── main.cpp              # The QWidget or QML entry point
│   │   │   ├── main.qml              # (QML applications) The QML UI file
│   │   │   ├── qml.qrc               # (QML applications) The resource mapping file
│   │   │   └── CMakeLists.txt        # ★ The CMake configuration (crucial!)
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets # ★ Where you set APP_LIBRARY_NAME
│   ├── build-profile.json5           # ★ The module-level build configuration
│   └── libs/arm64-v8a/               # The Qt runtime libraries
│       ├── libqohos.so               # The OHOS platform plugin (deployed automatically)
│       ├── styles/
│       │   └── libqohosstyle.so      # The OHOS style plugin (copied manually)
│       └── libQtHarmonyApp.so        # The application library (produced by the build)
├── qEmbeddedUiExtensionHost/
├── build-profile.json5               # The project-level build configuration
├── AppScope/app.json5                # The application's bundleName
└── local.properties                  # The SDK path
```

### 3.2 Scenario two: porting an existing project

> **The design philosophy**: HarmonyOS is one platform among many, so the glue code lives in its own `HarmonyOS/` directory, keeping the existing project structure clean.

```
<existing project root>/
├── CMakeLists.txt                    # ★ The existing project's CMake (needs OHOS configuration added)
├── src/                              # The existing source
└── HarmonyOS/                        # ★ New: the HarmonyOS glue-code directory
    ├── entry/
    │   ├── src/main/
    │   │   ├── cpp/                  # An empty directory (unused)
    │   │   └── ets/common/QtAppConstants.ets
    │   ├── build-profile.json5       # ★ path uses an absolute path pointing at the root CMakeLists.txt
    │   └── libs/arm64-v8a/
    ├── qEmbeddedUiExtensionHost/
    ├── build-profile.json5
    └── local.properties
```

**The key point**: open the **`HarmonyOS/` directory** in DevEco Studio, not the project root.

## 4. CMake configuration (the core)

### 4.1 The module-level build-profile.json5

`entry/build-profile.json5` (scenario one) or `HarmonyOS/entry/build-profile.json5` (scenario two):

```json5
{
  "apiType": 'stageMode',
  "buildOption": {
    "externalNativeOptions": {
      // Scenario one: a relative path
      "path": "./src/main/cpp/CMakeLists.txt",
      // Scenario two: an absolute path pointing at the project root's CMakeLists.txt
      // "path": "C:\\code\\MyQtApp\\CMakeLists.txt",
      "arguments": "-DCMAKE_PREFIX_PATH=<Qt SDK path>",  // ★ filled in by the developer
      "abiFilters": ["arm64-v8a"]
    }
  }
}
```

**The key parameters**:
- `path`: a relative path in scenario one; scenario two must use an **absolute path** (with backslashes escaped as `\\`)
- `arguments`: `-DCMAKE_PREFIX_PATH` pointing at the Qt SDK (such as `<LOCAL_PATH>`)
- `abiFilters`: must match the target device's ABI (`arm64-v8a`)

### 4.2 The CMakeLists.txt template

#### The cross-compilation find_package problem (an iron rule)

The OHOS toolchain sets `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY` by default, preventing CMake from finding Qt through `CMAKE_PREFIX_PATH`. **You must temporarily change it to BOTH before find_package**:

```cmake
if(CMAKE_CROSSCOMPILING)
  set(_saved_root_path_mode_package "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()

find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Widgets)  # add modules as needed

if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "${_saved_root_path_mode_package}")
  unset(_saved_root_path_mode_package)
endif()
```

#### CMakeLists.txt for a QWidget application

```cmake
cmake_minimum_required(VERSION 3.5)
project(QtHarmonyApp)

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# (the cross-compilation find_package fix — see the code block above)

find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Widgets)

set(PROJECT_SOURCES main.cpp)

# ★ The library name must match APP_LIBRARY_NAME in QtAppConstants.ets
add_library(QtHarmonyApp SHARED ${PROJECT_SOURCES})

target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::Core
  Qt${QT_VERSION_MAJOR}::Widgets
)

# ★ The OHOS platform plugin (which deploys libqohos.so automatically)
target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin
)
```

#### CMakeLists.txt for a QML application

```cmake
cmake_minimum_required(VERSION 3.5)
project(QtHarmonyApp)

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)  # ★ mandatory for QML applications, to compile qml.qrc

# (the cross-compilation find_package fix, as above)

find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Gui Qml Quick)

set(PROJECT_SOURCES
  main.cpp
  main.qml       # the QML UI file
  qml.qrc        # the resource mapping file
)

add_library(QtHarmonyApp SHARED ${PROJECT_SOURCES})

target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::Core
  Qt${QT_VERSION_MAJOR}::Gui
  Qt${QT_VERSION_MAJOR}::Qml
  Qt${QT_VERSION_MAJOR}::Quick
)

target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin
)
```

### 4.3 The project-level build-profile.json5

```json5
{
  "app": {
    "products": [{
      "name": "default",
      "signingConfig": "default",
      "compatibleSdkVersion": "5.0.0(12)",
      "runtimeOS": "HarmonyOS"    // ★ must be "HarmonyOS"
    }],
    "buildModeSet": [
      {"name": "debug"},
      {"name": "release"}
    ]
  },
  "modules": [
    {"name": "entry", "srcPath": "./entry"},
    {"name": "qEmbeddedUiExtensionHost", "srcPath": "./qEmbeddedUiExtensionHost"}
  ]
}
```

**The iron rule**: don't set `compileSdkVersion` or `targetSdkVersion`.

## 5. The library naming rule (crucial!)

### 5.1 The three-way correspondence

```
CMakeLists.txt:
  add_library(QtHarmonyApp SHARED ...)  →  the target name: QtHarmonyApp

The build artifact (produced by the build):
  entry/libs/arm64-v8a/libQtHarmonyApp.so  →  lib + the target name + .so

QtAppConstants.ets:
  APP_LIBRARY_NAME = 'libQtHarmonyApp.so'  →  ★ must match the actual filename exactly
```

### 5.2 Configuring QtAppConstants.ets

Path: `entry/src/main/ets/common/QtAppConstants.ets`

```typescript
export const APP_LIBRARY_NAME = 'libQtHarmonyApp.so';
```

### 5.3 Common mistakes

| A wrong example | The correct version | The problem |
|-----------------|---------------------|-------------|
| `'QtHarmonyApp.so'` | `'libQtHarmonyApp.so'` | Missing the `lib` prefix |
| `'libQtHarmonyApp'` | `'libQtHarmonyApp.so'` | Missing the `.so` suffix |
| `'libqtharmonyapp.so'` | `'libQtHarmonyApp.so'` | Inconsistent case |
| `'libMyApp.so'` | `'libQtHarmonyApp.so'` | Doesn't match the actual build artifact |

**How to verify**: after building, run `ls entry/libs/arm64-v8a/*.so` to see the actual library name.

## 6. Deploying the Qt runtime libraries

### 6.1 Automatic deployment

| Library | How it's deployed | Target path |
|---------|-------------------|-------------|
| `libqohos.so` | By linking `Qt5::QOhosPlatformIntegrationPlugin` | `libs/${ABI_DIR}/libqohos.so` |
| The Qt core libraries | `find_package` + `target_link_libraries` | `libs/${ABI_DIR}/` |

### 6.2 Manual copying

| Library | Source | Target path |
|---------|--------|-------------|
| `libqohosstyle.so` | `<Qt_SDK>/plugins/styles/libqohosstyle.so` | `libs/${ABI_DIR}/styles/libqohosstyle.so` |
| `libqsvg.so` (the SVG image format plugin) | `<Qt_SDK>/plugins/imageformats/libqsvg.so` | `libs/${ABI_DIR}/imageformats/libqsvg.so` |
| `libqsqlite.so` (the SQL driver plugin, for QSqlDatabase) | `<Qt_SDK>/plugins/sqldrivers/libqsqlite.so` | `libs/${ABI_DIR}/sqldrivers/libqsqlite.so` |

```bash
TARGET_DIR=<project directory>/entry/libs/arm64-v8a/styles/
mkdir -p "$TARGET_DIR"
cp <Qt_SDK path>/plugins/styles/libqohosstyle.so "$TARGET_DIR"

# The SVG image format plugin: required for QML Image / QImageReader to load .svg
mkdir -p <project directory>/entry/libs/arm64-v8a/imageformats/
cp <Qt_SDK path>/plugins/imageformats/libqsvg.so <project directory>/entry/libs/arm64-v8a/imageformats/
```

> `libqohosstyle.so` can't be deployed via `target_link_libraries` because it has to go in a `styles/` subdirectory.
>
> **⚠️ `libqsvg.so` is the same, and sneakier** — it's an **image format plugin** (`QSvgPlugin:QImageIOPlugin`), loaded dynamically at runtime by `QImageReader`, and must go in the `imageformats/` subdirectory; it can't be deployed via `target_link_libraries`. **If you forget it**: `QML Image { source: "*.svg" }`, `QImageReader`, and `QPixmap::loadFromData(bytes,"SVG")` **fail silently** (`Image.status=Error`, `sourceSize=0x0`, no exception), while `QSvgRenderer`/`QSvgWidget` (compiled into `libQt5Svg`) work fine — which very easily gets misdiagnosed as QtSvg being broken. Diagnosis: if `QImageReader::supportedImageFormats()` doesn't contain `"svg"`, the plugin isn't loaded. To verify, use a QML OHOS demo that displays an SVG.

> **⚠️ `libqsqlite.so` is the same, and even easier to misdiagnose** — it's a **SQL driver plugin** (`QSQLiteDriverPlugin`, a `MODULE IMPORTED` dynamic plugin) that `QFactoryLoader` dlopens at runtime from the `sqldrivers/` subdirectory, and it **can't be deployed via `target_link_libraries`** (linking `Qt5::Sql` only deploys the main `libQt5Sql.so`; the driver plugin is a separate runtime dlopen plugin, not a NEEDED dependency, so HVigor doesn't package it automatically). **If you forget it**: `QSqlDatabase::addDatabase("QSQLITE")` gives a null driver, and `db->open()` **returns false immediately when it finds `d->driver` empty (never calling `sqlite3_open` or touching the filesystem)**, with `lastError()` = `"Driver not loaded"`. Note that in the OHOS SDK the driver file is named **`libqsqlite.so`** (not desktop's `libqsqlsqlite.so`). Diagnosis: after `addDatabase`, check whether `db->lastError().text()` contains "Driver not loaded", or run `hdc shell find /data/storage/el1/bundle -name 'libqsqlite*'` on the device and get no hits. See [runtime-fail-sqlite-open-database](../problems/runtime-fail-sqlite-open-database.md).

## 7. Special configuration for QML applications

### 7.1 Where the QML files go

The QML files live in the `cpp/` directory and are compiled into the application library through `qml.qrc`:

```
entry/src/main/cpp/
├── main.cpp       # QML engine initialization
├── main.qml       # The QML UI (compiled in via qrc)
└── qml.qrc        # The resource mapping
```

### 7.2 The qml.qrc configuration

```xml
<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource prefix="/">
        <file>main.qml</file>
    </qresource>
</RCC>
```

**The path correspondence**: `qml.qrc`'s prefix `/` + the file `main.qml` → the resource path `:/main.qml` → `main.cpp` loads `qrc:/main.qml`

### 7.3 QML caveats

- The Qt SDK for HarmonyOS is a trimmed build and **doesn't include QtQuick.Controls**
- Use `Rectangle` + `MouseArea` instead of the Button control
- `Window` has no `focus` property, so keyboard events need to go in an inner `Item` or `FocusScope`:
  ```qml
  Window {
      Item {
          anchors.fill: parent
          focus: true
          Keys.onPressed: { console.log("Key:", event.key) }
      }
  }
  ```

### 7.4 Deploying QML modules to resfile/qml (required for runtime imports)

If a QML application `import`s a QML module that ships with the Qt SDK (Qt3D / QtQuick.Controls / QtQuick.Layouts / QtDataVisualization / QtQuick.Scene3D and so on), build-time `find_package` + `target_link_libraries` only deploys the Qt C++ libraries into the HAP's `libs/` — it **doesn't deploy the QML type plugins** (the .so files + qmldir under `qml/<Module>/`). At runtime, QQmlEngine can't find the module → hilog reports `module "Qt3D"/"QtQuick" is not installed` → the QML tree fails to load → a black screen (with the process alive and not crashing).

**The mechanism** (source: `qtbase/src/plugins/platforms/ohos/qohosjsmain.cpp`):
- At startup, the QPA sets the environment variable `QML2_IMPORT_PATH = resourceDir + "/qml"` (:1784)
- `resourceDir` defaults to `bundleCodeDir + "/entry/resources/resfile"` (:1731-1733)

So the QPA expects the QML modules at the HAP's `entry/src/main/resources/resfile/qml/` (on device: `bundle/entry/resources/resfile/qml/`).

**Deployment**: copy the Qt OHOS SDK's entire `qml/` directory into the project's `entry/src/main/resources/resfile/qml/`:

```bash
mkdir -p "<project>/entry/src/main/resources/resfile/qml"
cp -r "<QT_OHOS_SDK>/qml/." "<project>/entry/src/main/resources/resfile/qml/"
```

- hvigor automatically packages everything under `entry/src/main/resources/resfile/` into the HAP as resfile resources
- resfile is an OHOS **read-only** resource directory where dlopen is allowed (iron rule P3 says dlopen rejects writable paths; resfile is read-only, so it's fine), and the QML plugin `.so` files load correctly
- Copying everything is simplest (the SDK's `qml/` is ~15 MB across 866 files); trimming it means covering every module subdirectory the application `import`s plus their transitive dependencies (such as Qt3D/Core|Render|Input|Extras|Logic|Animation, QtQuick, QtQuick.2, QtQml, Qt, builtins.qmltypes)
- Rebuild the HAP, install, and launch: hilog no longer reports "not installed" and the QML tree loads and renders normally

> **Note**: resfile ≠ rawfile. Qt6 OHOS (per the qtcreator postmortem) once deployed to `rawfile/` while reading the resfile path at runtime; but in Qt 5.12 the QPA's `resourceDir` defaults directly to `resfile`, so on Qt5 things belong in `resfile/qml/`. If `appStartupObj.resourceDir` is set explicitly, that value is used instead.

See the error quick-reference table in problems/_lookup.md.

## 8. Configuring the application bundle name

Edit `AppScope/app.json5`:

```json5
{
  "app": {
    "bundleName": "com.example.<AppName>",  // ★ the globally unique identifier
    "vendor": {"name": "YourName", "code": "000"},
    "version": {"code": 1000000, "name": "1.0.0"}
  }
}
```

**bundleName conventions**: the format `com.<company>.<app>` or `org.<organization>.<app>`; no non-ASCII characters, spaces, or special characters.

## 9. The iron-rule checklist

### Forbidden

- Modifying any file inside the DevEco SDK or the Qt SDK directories
- Setting `compileSdkVersion` or `targetSdkVersion`
- Modifying `OhosExportModules.ts`
- Using the user's prompt text directly as a file/directory name

### Mandatory

- Set `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` when cross-compiling in CMakeLists.txt
- Link `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin` (the platform plugin)
- Copy `libqohosstyle.so` manually into `libs/${ABI_DIR}/styles/`
- `APP_LIBRARY_NAME` must match the built library name **exactly** (including the `lib` prefix and `.so` suffix)
- `runtimeOS` must be `"HarmonyOS"`
- Scenario two: the `path` in `build-profile.json5` must be an **absolute path**

## 10. Common problems quick reference

| Problem | Solution |
|---------|----------|
| `find_package(Qt5)` fails | Set `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` when cross-compiling |
| Schema validate failed | Don't set `compileSdkVersion` |
| dlopen failed / cannot locate symbol | Link `Qt5::QOhosPlatformIntegrationPlugin` |
| The platform plugin fails to load | Confirm `libqohos.so` is in `libs/${ABI_DIR}/` |
| The style plugin fails to load | Confirm `libqohosstyle.so` is in `libs/${ABI_DIR}/styles/` |
| QML Image / QImageReader silently fails to load an SVG (`Image.status=Error`, `sourceSize=0x0`) while `QSvgRenderer`/`QSvgWidget` work | Deploy `libqsvg.so` into `libs/${ABI_DIR}/imageformats/` (see §6.2) |
| `QSqlDatabase: QSQLITE driver not loaded` / `db->open()` returns false / "cannot create the local database" | Deploy `libqsqlite.so` into `libs/${ABI_DIR}/sqldrivers/` (see §6.2; on OHOS the file is `libqsqlite.so`); also give `setDatabaseName` an absolute path from `QStandardPaths::writableLocation(AppLocalDataLocation)` (the OHOS CWD isn't writable) |
| A library name mismatch | After building, check the actual filename with `ls libs/arm64-v8a/*.so` |
| QML module not installed | Check the `CMAKE_PREFIX_PATH` configuration |
| A QML application shows a black screen | Check the Qt module links and `CMAKE_PREFIX_PATH` |
| A QML Window has no focus property | Put keyboard events in an inner `Item` |
| Scenario two's build can't find the source files | `path` must be an absolute path pointing at the root CMakeLists.txt |
| A lazy import syntax error (`OhosExportModules.ts` reports `does not support using lazy import`) | Add `"compatibleSdkVersionStage": "beta3"` to the product in the project-level `build-profile.json5` (**don't** edit `OhosExportModules.ts` — §9's iron rules forbid it; switching to beta3 makes API 12 support the syntax) |
| `spawn java ENOENT` (during the PackageHap stage) | A command-line build needs `export PATH="<DevEco>/jbr/bin:$PATH"` (the IDE bundles JBR; see pitfall 6 in `episodic/postmortems/coin3d-quarter-ohos.md`) |

## References

- [The Qt for HarmonyOS CMake cross-compilation guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development/deveco_cmake_guide_cross_compile)
- [The QML application deployment guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_deply_qml_app_zh)
- [The Qt for HarmonyOS user development guide](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide)
- The internal skill: `<INTERNAL_SKILL>`
- The internal document: `<INTERNAL_DOC>`
