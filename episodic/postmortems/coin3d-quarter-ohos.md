---
id: episodic-projects-coin3d-quarter-ohos
type: episodic
domain: project
tags: [coin3d, quarter, harmonyos, cross-compile, 3d, opengl-es]
created: 2026-06-08
updated: 2026-06-08
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-modules, semantic-qt-harmonyos-build]
summary: >
  Complete Coin3D Quarter HarmonyOS migration: cross-compiling libQuarter.so (ARM aarch64) + building the demo application (37 MB HAP)
  + 3D rendering verified. Key findings: OHOS Qt5 doesn't include the UiTools module, FindOpenGL needs customizing (OHOS uses GLES/EGL),
  CMAKE_FIND_ROOT_PATH_MODE ONLY needs absolute paths to work around, and hvigor needs DEVECO_SDK_HOME.
  Reusable: an OHOS cross-compilation CMake template + a FindOpenGL mapping pattern + a prebuilt-library integration pattern.
---

# Cross-compiling Coin3D Quarter for HarmonyOS — lessons learned

## Project overview

| Field | Content |
|-------|---------|
| Date | 2026-06-08 |
| Role | Qt for HarmonyOS developer |
| Tech stack | Coin3D 4.0 + Quarter 1.2.3 + Qt 5.12 + CMake + OHOS SDK clang 15 |
| Scale | Cross-compiling a single .so library + demo integration |
| Status | ✅ Complete (cross-compiled + demo built + 3D rendering verified) |

## Background and goals

Cross-compile [Coin3D Quarter](https://github.com/coin3d/quarter) (the glue library integrating Coin3D with Qt) for the HarmonyOS ARM64 platform. A prebuilt OHOS ARM64 Coin3D library already exists (from [coin3d_demo](https://gitcode.com/zhong-luping/coin3d_demo)).

## Key decisions

### Decision 1: choose Qt 5.12 rather than 5.15
- **Background**: OHOS builds exist for both versions
- **Options**: Qt 5.12 / Qt 5.15
- **Choice**: Qt 5.12 (`<LOCAL_PATH>`)
- **Rationale**: Quarter uses `QGLWidget` (from the QtOpenGL module) under Qt5, which is available in both versions, but 5.12 is the current primary branch
- **Result**: builds successfully with no compatibility issues

### Decision 2: drop the UiTools dependency
- **Background**: Quarter's CMakeLists.txt depends on `Qt5::UiTools`, but the OHOS Qt SDK doesn't include that module
- **Options**: ① build UiTools from the Qt source ② drop the dependency ③ build a static library to work around it
- **Choice**: drop the UiTools dependency (it's only used in the examples; the core library doesn't need it)
- **Rationale**: the principle of minimal change — the core library's src/Quarter/*.cpp doesn't use QUiLoader
- **Result**: builds successfully with no impact on core functionality

### Decision 3: a custom FindOpenGL.cmake
- **Background**: OHOS uses OpenGL ES (libGLESv2.so / libGLv4.so) + EGL rather than desktop OpenGL (libGL.so + libGLX.so)
- **Choice**: create a custom FindOpenGL.cmake that maps GLES/EGL onto the standard OpenGL CMake variables
- **Result**: libGLv4.so and libEGL.so are found successfully

### Decision 4: use absolute paths in CoinConfig.cmake
- **Background**: the OHOS toolchain sets `CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY`, so `find_library` only searches the sysroot
- **Choice**: use `EXISTS` + absolute paths in CoinConfig.cmake to bypass the search restriction
- **Result**: the prebuilt libCoin.so.80 is located successfully

## Pitfalls we hit

### Pitfall 1: Qt5UiTools is missing from the OHOS SDK
- **Symptom**: `find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET)` fails
- **Root cause**: neither the OHOS Qt SDK 5.12 nor 5.15 includes the Qt5UiTools cmake module
- **Fix**: remove UiTools from find_package and from QUARTER_QT_TARGETS
- **Lesson**: before cross-compiling a third-party Qt library, scan which Qt modules the OHOS SDK actually has (`ls lib/cmake/`)

### Pitfall 2: FindOpenGL can't find libGL.so on OHOS
- **Symptom**: `Could NOT find OpenGL (missing: OPENGL_opengl_LIBRARY OPENGL_glx_LIBRARY)`
- **Root cause**: the OHOS sysroot has no libGL.so or libGLX.so — only libGLESv2.so / libGLv4.so / libEGL.so
- **Fix**: a custom FindOpenGL.cmake using libGLv4.so in place of libGL.so and libEGL.so in place of libGLX.so
- **Lesson**: every library that depends on desktop OpenGL needs a custom FindOpenGL on OHOS

### Pitfall 3: CMAKE_FIND_ROOT_PATH_MODE ONLY blocks find_library/find_path
- **Symptom**: `find_library(Coin_LIBRARY PATHS ...)` in CoinConfig.cmake can't find the library
- **Root cause**: the OHOS toolchain sets `CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY`, restricting all find operations to the sysroot
- **Fix**: in CoinConfig.cmake, set the variables directly using `EXISTS` + absolute paths instead of find_library/find_path
- **Lesson**: when writing a FindXXX.cmake for OHOS cross-compilation, prefer absolute paths + EXISTS checks

### Pitfall 4: CMAKE_FIND_ROOT_PATH doesn't include the Qt SDK path
- **Symptom**: `find_package(Qt5 ...)` can't find Qt5 and falls back to Qt4 with an error
- **Root cause**: `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY` searches only CMAKE_FIND_ROOT_PATH, which doesn't include the Qt SDK
- **Fix**: add the Qt SDK path via `-DCMAKE_FIND_ROOT_PATH="<LOCAL_PATH>"`
- **Lesson**: when cross-compiling for OHOS, every external dependency (Qt, third-party libraries) must be added to CMAKE_FIND_ROOT_PATH

## Reusable takeaways

1. **An OHOS cross-compilation CMake template**:
   ```bash
   cmake -G Ninja \
     -DCMAKE_TOOLCHAIN_FILE="<OHOS_SDK>/native/build/cmake/ohos.toolchain.cmake" \
     -DOHOS_ARCH=arm64-v8a \
     -DCMAKE_FIND_ROOT_PATH="<Qt_SDK_path>" \
     -DCMAKE_MODULE_PATH="<path to your custom cmake modules>" \
     -DCoin_DIR="<directory containing CoinConfig.cmake>"
   ```

2. **The custom FindOpenGL.cmake pattern**: OHOS projects can reuse this, mapping libGLv4.so + libEGL.so onto the standard OpenGL variables

3. **The CoinConfig.cmake absolute-path pattern**: applies to any scenario using a prebuilt third-party library in OHOS cross-compilation

4. **Quarter's dependency chain on OHOS**: `libCoin.so.80` + `libGLv4.so` + `libQt5Core.so` + `libQt5Gui.so` + `libQt5OpenGL.so` + `libQt5Widgets.so`

## Build artifacts

| File | Size | Architecture | Path |
|------|------|--------------|------|
| libQuarter.so.20.2.3 | 400 KB | ARM aarch64 | `quarter-ohos/build-ohos/lib/` |
| libQuarter.so.20 | symlink | - | same |
| libQuarter.so | symlink | - | same |
| libquarterdemo.so | 57 KB | ARM aarch64 | inside the `quarter-ohos/quarter-demo-ohos/` HAP |
| quarter-demo-ohos-default-unsigned.app | 37 MB | - | `quarter-ohos/quarter-demo-ohos/build/<INTERNAL_OUTPUT>` |

## Lessons from building the demo application

### Decision 5: use the Qt OHOS template rather than a native XComponent
- **Background**: Quarter is fundamentally a Qt widget and needs QApplication + the Qt event loop
- **Choice**: use the Qt OHOS template (QAbility + the QPA plugin), which handles the XComponent ↔ Qt bridging automatically
- **Result**: you only write a standard Qt C++ main(); no manual EGL/GL context management

### Pitfall 5: hvigor silently skips the native build
- **Symptom**: `BuildNativeWithCmake... after 1 ms`, BUILD SUCCESSFUL but no .so artifacts
- **Root cause**: `DEVECO_SDK_HOME` isn't set, so hvigor can't find the OHOS SDK toolchain
- **Fix**: `export DEVECO_SDK_HOME="C:/Program Files/Huawei/DevEco Studio/sdk"`
- **Lesson**: a 1 ms BuildNativeWithCmake is the telltale sign of a silent skip; it should normally take >1 s

### Pitfall 6: PackageHap needs Java
- **Symptom**: `spawn java ENOENT`, HAP packaging fails
- **Root cause**: hvigor's PackageHap step calls `java -jar app_packing_tool.jar`, but the command-line environment has no Java
- **Fix**: `export PATH="/c/Program Files/Huawei/DevEco Studio/jbr/bin:$PATH"` (the whole jbr/bin directory is required; copying java.exe alone won't work)
- **Lesson**: the DevEco Studio IDE bundles JBR, but command-line builds need it configured manually

### Pitfall 7: the lazy import syntax in OhosExportModules.ts
- **Symptom**: `Current configuration does not support using lazy import`
- **Root cause**: the template uses the `import lazy` syntax, which requires API 12 beta3 or newer
- **Fix**: replace `import lazy { ... }` with `import { ... }`
- **Lesson**: the ArkTS glue code in Qt OHOS templates may need syntax adjustments depending on the SDK version

## 3D rendering verification (2026-06-08)

### Verification results

| Item | Status | Notes |
|------|:------:|-------|
| Application launch | ✅ | QApplication initializes correctly and the QPA plugin loads |
| QuarterWidget creation | ✅ | The QGLWidget subclass is created correctly and the EGL context is managed automatically |
| 3D scene rendering | ✅ | A red cube + a blue sphere + a green semi-transparent cube + directional light all render correctly |
| Touch interaction | ✅ | Drag to rotate / pinch to zoom / two-finger pan all respond correctly |
| Transparency rendering | ✅ | In SORTED_OBJECT_BLEND mode, the semi-transparent cube blends correctly |

### Verification conclusion

The Coin3D Quarter library has been ported end to end to HarmonyOS, verified from cross-compilation all the way through 3D rendering. Key technical paths verified:
1. The Coin3D scene graph works correctly on OHOS
2. The Quarter glue library successfully bridges Coin3D and Qt for OHOS
3. The OpenGL ES rendering pipeline is managed automatically by Qt's QPA
4. The Qt widget event loop passes touch gestures through to Coin3D correctly

### Migration report

The full migration report was written to the project root: `<MIGRATION_PROJECT_ROOT>/quarter-ohos\MIGRATION_REPORT.md`

## Related resources

- Quarter source: https://github.com/coin3d/quarter
- Coin3D demo: https://gitcode.com/zhong-luping/coin3d_demo
- Project directory: `<MIGRATION_PROJECT_ROOT>/quarter-ohos\`
- Migration report: `<MIGRATION_PROJECT_ROOT>/quarter-ohos\MIGRATION_REPORT.md`
