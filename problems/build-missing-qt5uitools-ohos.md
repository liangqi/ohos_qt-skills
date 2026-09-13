---
id: problem-ohos-missing-qt5uitools
type: problem
domain: build
tags: [qt5, ohos, cmake, uitools, missing-module]
created: 2026-06-08
updated: 2026-06-08
status: workaround
audience: public
severity: medium
error_message: "CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) fails (the OHOS Qt5 SDK lacks the Qt5UiTools module)"
refs: [semantic-qt-harmonyos-modules]
summary: >
  The OHOS Qt5 SDK doesn't include the Qt5UiTools module, so find_package(Qt5 COMPONENTS UiTools) fails.
  You must either remove UiTools from the find_package list or build the module from the Qt source.
---

# The OHOS Qt5 SDK is missing the Qt5UiTools module

## Error message

```
CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) failed
```

Or, when it falls back to Qt4:

```
CMake Error at FindQt4.cmake:1314 (message):
  Found unsuitable Qt version "5.12.12" from
  <LOCAL_PATH>, this code requires Qt 4.x
```

## When it happens

- Cross-compiling a third-party Qt library that depends on `Qt5::UiTools` (such as Coin3D Quarter)
- Both the OHOS Qt 5.12 and 5.15 SDKs lack this module

## Root cause

The OHOS Qt SDKs (`<LOCAL_PATH>` and `<LOCAL_PATH>`) don't contain a `Qt5UiTools` cmake configuration directory.

Qt5UiTools provides `QUiLoader` (loading .ui files at runtime); in most projects only the examples use it, and the core libraries generally don't depend on it.

> **⚠️ Root cause correction (confirmed 2026-07-08 by lzh)**: the wiki marks QtHelp/QtUiTools/QtDesigner as **Completed** (ported to HarmonyOS), but **the qttools module's dependencies can only be built as a host build on a HarmonyOS PC — cross-compiling from Windows doesn't work**. So an OHOS Qt5 SDK cross-compiled from Windows (such as `<QT5_15_OHOS_SDK>` or `<QT5_15_OHOS_SDK_FULL>`) inherently lacks Qt5UiTools/Qt5Help. This isn't an SDK packaging oversight — it's a **build-method limitation**. Filling the gap requires a host build of qttools on a HarmonyOS PC, then deploying the result.

## Qt5 modules available in the OHOS SDK

Confirmed via `ls lib/cmake/`:

| Qt 5.12 | Qt 5.15 |
|---------|---------|
| Qt5Concurrent | Qt5Concurrent |
| Qt5Core | Qt5Core |
| Qt5DocGallery | - |
| Qt5Gui | Qt5Gui |
| Qt5Network | Qt5Network |
| Qt5OhosExtras | Qt5OhosExtras |
| Qt5OpenGL | Qt5OpenGL |
| Qt5OpenGLExtensions | Qt5OpenGLExtensions |
| Qt5PrintSupport | Qt5PrintSupport |
| Qt5Qml | Qt5Qml |
| Qt5Quick | Qt5Quick |
| Qt5QuickCompiler | Qt5QuickCompiler |
| Qt5QuickTest | Qt5QuickTest |
| Qt5QuickWidgets | Qt5QuickWidgets |
| Qt5Sql | Qt5Sql |
| Qt5Svg | Qt5Svg |
| Qt5Test | Qt5Test |
| Qt5Widgets | Qt5Widgets |
| Qt5Xml | Qt5Xml |
| **Qt5UiTools ❌** | **Qt5UiTools ❌** |

## Solution

1. **Remove UiTools from find_package** (recommended):
   ```cmake
   # Before:
   find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET)
   # After:
   find_package(Qt5 COMPONENTS Widgets OpenGL QUIET)
   ```

2. **Remove it from the link targets**:
   ```cmake
   # Before:
   set(QUARTER_QT_TARGETS Qt5::Widgets Qt5::UiTools Qt5::OpenGL)
   # After:
   set(QUARTER_QT_TARGETS Qt5::Widgets Qt5::OpenGL)
   ```

3. **If you really need UiTools**: you **can only do a host build of qttools on a HarmonyOS PC** and deploy the output into the SDK. **Cross-compiling from Windows doesn't work** (dictated by qttools' dependencies; confirmed 2026-07-08 by lzh) — don't try to cross-compile `qttools/src/assistant` or `src/designer/src/uitools` by targeting them with qmake from Windows.

## Lessons learned

Before cross-compiling a third-party Qt library, scan the available modules with `ls <QT_SDK>/lib/cmake/` to spot missing dependencies early.

## Content source

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | Found while cross-compiling Coin3D Quarter; confirmed on both the 5.12 and 5.15 SDKs |
