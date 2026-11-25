---
id: problem-build-qt612-ohos-plugin-rebuild
type: problem
domain: build
tags: [qt612, libqohos, platform-plugin, cmake, BUILD_SUBMODULES, node-addon-api, fontconfig, FIND_ROOT_PATH, kit-replacement]
created: 2026-09-12
updated: 2026-09-12
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-build]
summary: >
  Patching the ohos platform plugin (libqohos.so) of the Qt 6.12-beta3 harmonyos kit can't go through the usual
  qt-cmake; it needs cmake + BUILD_SUBMODULES=src/plugins/platforms. Five pitfalls in a row at configure time:
  qt-cmake refuses to build qtbase itself; NODE_ADDON_API_ROOT is missing; the cross toolchain's
  FIND_ROOT_PATH_MODE_INCLUDE=ONLY re-rooting makes find_path always fail; OHOS_SDK_ROOT/OHOS_NDK_ROOT
  is missing; the QT_FEATURE_fontconfig condition scope can't see
  Fontconfig_FOUND. The rebuilt output must replace the original file inside the kit (harmonydeployqt deploys from the kit).
leader_summary: >
  Established the rebuild workflow for the Qt 6.12 OHOS platform plugin: cmake BUILD_SUBMODULES + pre-filled find cache +
  relaxed gui CMakeLists condition + deploying by replacing the kit's copy + filling in SONAME differences
impact: [Build system, Platform backend]
deliverables: [problem record]
evidence: []

error_message: >
  ① qt-cmake: "Call Stack ... qt_auto_detect_cyclic_toolchain ... configure qtbase
  with 'cmake' instead of 'qt-cmake'"
  ② ERROR: Qt for OHOS requires node-api-addon. Set NODE_ADDON_API_ROOT to point to its location.
  ③ CMake Error at cmake/QtPriHelpers.cmake:908 (file): file FILE([TO_CMAKE_PATH|TO_NATIVE_PATH]
  path result) must be called with exactly three arguments.
  ④ Target "QOhosPlatformIntegrationPlugin" links to: Fontconfig::Fontconfig ... the target was not found.
  ⑤ fatal error: 'QtGui/private/qfontconfigdatabase_p.h' file not found
error_code: ""
keywords: [libqohos, BUILD_SUBMODULES, NODE_ADDON_API_ROOT, node-addon-api, OHOS_SDK_ROOT, OHOS_NDK_ROOT, Fontconfig, CMAKE_FIND_ROOT_PATH_MODE_INCLUDE, QT_FEATURE_fontconfig, harmonydeployqt]
symptoms: "You need to rebuild the ohos platform plugin on the Qt 6.12 harmonyos kit (to fix a QPA bug/add probes), and configure fails one error after another; or the newly built plugin doesn't take effect/fails to load after installing"
environment: "Windows + Qt 6.12-beta3 harmonyos_arm64_v8a kit + OHOS SDK (ohos.toolchain.cmake) + Ninja"
---

# Five pitfalls rebuilding the Qt 6.12 OHOS platform plugin (libqohos.so), and deployment

## Scenario

The ohos platform plugin of the Qt 6.12-beta3 harmonyos kit has a bug (such as the IME reset problem), or you need to add
diagnostic probes, so you must rebuild `libqohos.so` and make the application on the device actually use it.

## Pitfall 1: qt-cmake refuses to build qtbase itself

`qt-cmake` triggers the `qt_auto_detect_cyclic_toolchain` guard and reports
"configure qtbase with 'cmake' instead of 'qt-cmake'".

**The right way**: use the SDK's cmake + submodule trimming:

```powershell
& '<sdk>/native/build-tools/cmake/bin/cmake.exe' `
  -S '<Qt>/6.12.0/Src/qtbase' `
  -B '<build-dir>' -G Ninja -DCMAKE_BUILD_TYPE=Release `
  '-DCMAKE_TOOLCHAIN_FILE=<sdk>/native/build/cmake/ohos.toolchain.cmake' `
  -DOHOS_ARCH=arm64-v8a `
  '-DOHOS_SDK_ROOT=<sdk>/default/openharmony' `      # pitfall 4
  '-DQT_HOST_PATH=<Qt>/6.12.0/mingw_64' `
  '-DNodeAddonApi_INCLUDE_DIR=<node-addon-api directory>' `  # pitfalls 2+3
  '-DFontconfig_INCLUDE_DIR=<ohos fontconfig>/include' `
  '-DFontconfig_LIBRARY=<ohos fontconfig>/lib/libfontconfig.so' `
  -DBUILD_SUBMODULES=src/plugins/platforms `
  -DFEATURE_egl=ON -DFEATURE_opengl=ON

ninja -C <build-dir> QOhosPlatformIntegrationPlugin
# Output: <build-dir>/plugins/platforms/libqohos.so
```

## Pitfall 2: Qt for OHOS requires node-addon-api

qtbase's OHOS port uses a NAPI bridge (corelib depends on NodeAddonApi), and the Qt 6.12 source tree **no longer
bundles** `src/3rdparty/node-addon-api`. The error:

```
ERROR: Qt for OHOS requires node-api-addon. Set NODE_ADDON_API_ROOT to point to its location.
```

Get a copy of node-addon-api (7.x works; the Qt 5.15 harmonyos source tree has a ready-made copy you can reuse),
and set the `NODE_ADDON_API_ROOT` environment variable or `-DNodeAddonApi_INCLUDE_DIR=<dir>`.

## Pitfall 3: the cross toolchain re-roots find_path's HINTS (environment variables don't help)

`ohos.toolchain.cmake` sets `CMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY`, so all of find_path's
HINTS pointing at host paths get re-rooted into the sysroot → **even with the `NODE_ADDON_API_ROOT` environment variable set, it still
can't be found**.

**The right way**: pre-fill the find module's **cache variables** directly; find_path uses a value as soon as it sees one and skips the search:

```
-DNodeAddonApi_INCLUDE_DIR=...
-DFontconfig_INCLUDE_DIR=...
-DFontconfig_LIBRARY=...
```

(The OHOS sysroot doesn't have Linux-family libraries such as fontconfig; use the prebuilt versions in portgraph/workspace/ohos-libs.)

## Pitfall 4: OHOS_NDK_ROOT is empty → QtPriHelpers reports an argument error

Passing `CMAKE_TOOLCHAIN_FILE` directly skips Qt's auto-detect, so `OHOS_NDK_ROOT` is undefined, and
`file(TO_CMAKE_PATH ${OHOS_NDK_ROOT} ...)` at `QtPriHelpers.cmake:908` expands to empty →
"must be called with exactly three arguments".

**Fix**: add `-DOHOS_SDK_ROOT=<sdk>/default/openharmony`, and Qt derives
`OHOS_NDK_ROOT=<...>/native` automatically.

## Pitfall 5: QT_FEATURE_fontconfig is forced OFF by the condition scope (-D can't turn it on)

The ohos plugin's `qohosplatformfontdatabase_p.h` includes
`QtGui/private/qfontconfigdatabase_p.h`, a forwarding header that Gui generates only when the fontconfig feature is ON.
The symptom chain:

```
Fontconfig::Fontconfig target not found (first add pitfall 3's cache variables)
→ fatal error: 'QtGui/private/qfontconfigdatabase_p.h' file not found
```

**Root cause**: a Qt feature's CONDITION is evaluated in a **nested function scope**
(`qt_evaluate_config_expression` → `qt_internal_evaluate_config_expression`), and the **plain variable**
`Fontconfig_FOUND` set by `qt_find_package(Fontconfig)` isn't visible in that scope
→ the condition is always false. Tested: neither `-DQT_FEATURE_fontconfig=ON` nor `-DFontconfig_FOUND=TRUE`
works (overridden by the INTERNAL computed value / unset).

**Fix** (patch the qtbase sources locally to relax Gui's source-set condition):

```cmake
# src/gui/CMakeLists.txt
qt_internal_extend_target(Gui CONDITION OHOS OR (QT_FEATURE_fontconfig AND QT_FEATURE_freetype AND UNIX AND NOT APPLE)
    SOURCES
        text/unix/qfontconfigdatabase.cpp text/unix/qfontconfigdatabase_p.h
        ...
)
```

## Deployment: you must replace the kit's copy, not just the deployment directory

`harmonydeployqt` copies the plugin from the **kit** into the HAP project every time; editing the project's libs directory directly gets
overwritten with the old file on the next deploy.

```
① Back up: <kit>/plugins/platforms/libqohos.so → libqohos.so.kit-orig
② Overwrite: copy <build-dir>/plugins/platforms/libqohos.so <kit>/plugins/platforms/
③ Repackage: make_hap (deploy picks up the new plugin)
```

**The SONAME-difference pitfall**: if your self-built libqohos.so links portgraph's fontconfig, its NEEDED becomes
`libfontconfig.so.1` (the kit's original is `libfontconfig.so`) → the HAP's libs directory needs an extra copy named
`libfontconfig.so.1`, otherwise the plugin's dlopen fails. Use
`llvm-readobj --needed-libs` to compare the old and new plugins and confirm the dependency closure.

## Verification

```
ninja QOhosPlatformIntegrationPlugin          # [N/N] Linking ... libqohos.so
llvm-readobj --needed-libs <new libqohos.so>     # compare NEEDED against the kit's original
hdc install -r <signed.hap> && hdc shell pidof <bundle>   # survives after installing
```
