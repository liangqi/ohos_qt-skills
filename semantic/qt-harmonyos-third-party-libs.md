---
id: semantic-qt-harmonyos-third-party-libs
type: semantic
domain: tech
tags: [qt, harmonyos, third-party, cross-compile, cmake, vcpkg, dependency]
created: 2026-06-03
updated: 2026-08-15
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-platform-limits, semantic-qt-ohos-project-analyzer-workflow]
summary: >
  The adapter for consuming OHOS third-party libraries from Qt applications: Qt find_package/CMake, Qt module and plugin deployment,
  choosing between static and dynamic linking, migration checks for Qt projects, and a tested compatibility list; the platform-level NDK, ABI, sysroot,
  HAP native deployment, and loader contracts are maintained in the common knowledge base.
---

# Guide to porting third-party libraries to HarmonyOS

> When porting a Qt application to HarmonyOS, besides adapting the Qt modules themselves, you also need to deal with the third-party C/C++ libraries the application depends on.
> For the platform-general NDK/toolchain, ABI, sysroot, artifact inspection, HAP native deployment, and loader contracts, the authority is the common knowledge base's [[ohos-common-kb/semantic/ohos-native-third-party-libraries|Contract for integrating native third-party libraries on OHOS]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/ohos-native-third-party-libraries.md)). This page covers only Qt package discovery, target linking, Qt plugin/module deployment, and Qt application verification.

---

## 1. Overall strategy

| Strategy | When it applies | Complexity |
|----------|-----------------|------------|
| **Header-only libraries** | Eigen, nlohmann/json, spdlog (in header-only mode), and so on | 🟢 Low — just include the headers |
| **Cross-compiling from source** | C/C++ libraries with a CMake/autotools build system | 🟡 Medium — you must configure the OHOS toolchain |
| **Integrating prebuilt .so files** | The vendor provides prebuilt arm64 binaries | 🟡 Medium — confirm ABI compatibility and deploy correctly |
| **Static linking** | Libraries where you want to avoid .so deployment issues | 🟡 Medium — linked at build time, no extra .so at runtime |
| **Linking system libraries directly** | Libraries OHOS ships (such as libz, libcrypto) | 🟢 Low — link directly, nothing to deploy |
| **Replacing/downgrading** | Incompatible libraries that can't be patched | 🔴 High — you need to find an alternative |

---

> **📦 Prebuilt arm64 OHOS bottles come from Harmonybrew**: if a third-party library already has an arm64_ohos prebuilt package, you can download the .so and skip the cross-compilation in this section — see the one-command fetch script in [[fetch-ohos-third-party-lib]] (with recursive dependencies, sha256 verification, and qmake/CMake link snippets). Without a bottle, continue with cross-compiling from source below.

## 2. The platform input contract Qt consumes

First produce and accept the target-ABI headers, static libraries, or shared libraries plus their full `NEEDED` closure, per the common knowledge base. The Qt adapter doesn't dictate the NDK, sysroot, autotools/Meson options, or system library availability — it only consumes artifacts that have already passed platform acceptance.

When deploying shared libraries with a Qt HAP, also confirm that the Qt runtime, the QPA/style plugins, and the third-party dependencies all make it into the final package — don't check only your business target's direct dependencies.

---

## 3. Integrating third-party libraries with CMake

### 3.1 Linking a third-party library in the application's CMakeLists.txt

> **Iron rule**: just as with Qt application cross-compilation, a third-party library's CMake build also needs `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`, or `find_package` won't find the dependencies. For the full save/restore code pattern, see [[qt-harmonyos-project-structure]] §4.2.

```cmake
# 1. Apply the cross-compilation find_package fix (same as for Qt; see project-structure §4.2)
if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()

# 2. Find the third-party library (if it ships a CMake config)
find_package(ZLIB REQUIRED)

# 3. Or specify it manually (if the library has no CMake config)
set(THIRD_PARTY_PREFIX "$ENV{HOME}/ohos-libs")
include_directories(${THIRD_PARTY_PREFIX}/zlib/include)
link_directories(${THIRD_PARTY_PREFIX}/zlib/lib)

# 4. Link it into the target
target_link_libraries(QtHarmonyApp PRIVATE z ssl crypto)
```

### 3.2 Using CMAKE_PREFIX_PATH

If the third-party library was installed with a standard directory layout (`lib/`, `include/`, `lib/cmake/`), you can let `find_package` find it automatically through `CMAKE_PREFIX_PATH`:

```cmake
# Set this in DevEco's build-profile.json5:
# "arguments": "-DCMAKE_PREFIX_PATH=<Qt_SDK>;$ENV{HOME}/ohos-libs/zlib;$ENV{HOME}/ohos-libs/openssl"
```

### 3.3 Linking a third-party library statically

If the third-party library is built as a static library (`.a`), just link it — there's no `.so` to deploy:

```cmake
target_link_libraries(QtHarmonyApp PRIVATE
    ${THIRD_PARTY_PREFIX}/zlib/lib/libz.a    # static linking
)
```

**Advantages**: avoids .so deployment problems and reduces runtime dependencies.
**Disadvantages**: increases the application's .so size, and can cause symbol conflicts when several modules use the same static library.

---

## 4. Checkpoints for platform limitations in a Qt project

Platform limitations and error codes aren't maintained on this page. A Qt project only records the consumption points affected:

- Whether `QPluginLoader` or a plugin framework can resolve the full dependency set from the final HAP's native libraries
- Whether third-party code wrapped by `QFile`/`QFileInfo` depends on permission, linking, or system-path behavior listed on the common limitations page
- Whether third-party workers running on a `QThread` depend on cancellation semantics the target libc doesn't provide
- Whether `QTimeZone` or a library's own time-zone logic needs Qt's ICU backend
- Whether static linking introduces duplicate symbols, PIC, or licensing problems

For the specific Qt symptoms and workarounds, see [[qt-harmonyos-platform-limits]]; the platform causes and status come from the common knowledge base.

---

## 5. Known compatibility list for Qt applications

> This list accumulates with practice. Update the table each time you port a new third-party library.

| Library | Version | How it's integrated | OHOS compatibility | Notes |
|---------|---------|---------------------|--------------------|-------|
| zlib | Ships with the system | System library `-lz` | 🟢 Works | Ships with the system |
| OpenSSL (crypto/ssl) | Ships with the system | System libraries `-lcrypto -lssl` | 🟢 Works | Ships with the system; building Qt needs extra header configuration |
| Eigen | Any | Header-only | 🟢 Works | Headers only |
| nlohmann/json | Any | Header-only | 🟢 Works | Headers only |
| SQLite | 3.x | Built from source / system | 🟡 Needs a patch | It may call `chmod()` internally, which needs a `#ifndef __OHOS__` guard |
| ICU | Ships with the system | System library | 🟢 Works | Qt's time zone backend depends on it |
| Boost (header-only) | Any | Header-only | 🟢 Works | The header-only parts |
| Boost.Filesystem | Any | Built from source | ⚠️ Confirmed risky | Uses `chmod()`/`symlink()`, both restricted on OHOS (see [[qt-harmonyos-platform-limits]]) |
| protobuf | Any | Built from source | 🟡 Needs verification | The basics should work (no OHOS-specific restrictions), but it hasn't actually been built and tested |
| libcurl | Any | Built from source | 🟡 Needs verification | Depends on OpenSSL (which OHOS ships); the networking APIs should be compatible, but it hasn't actually been built and tested |
| freetype | — | Bundled with Qt | 🟢 Nothing to do | Qt 6 bundles freetype in `src/3rdparty/freetype` and builds it with Qt GUI |
| Coin3D 4.0 | — | Prebuilt .so | ✅ Verified | `libCoin.so.80` (ARM aarch64) integrates directly; needs `-DCOIN_DLL` + linking `libGLv4.so` + `libEGL.so`. See [[coin3d-quarter-ohos]] |
| Quarter 1.2.3 | — | Built from source | ✅ Verified | Depends on Coin3D + Qt5::Widgets/OpenGL; requires removing UiTools and a custom FindOpenGL.cmake. See [[coin3d-quarter-ohos]] |
| QScintilla | 2.11.6 | Built from source (qmake) | ✅ Verified | A code editor component (with syntax highlighting) depending only on QtCore/Gui/Widgets/PrintSupport; OHOS cross-compilation needs a custom mkspec (ohos-clang-win) and short paths. No source changes needed |
| QtMqtt | 6.12.0 (v6.12.0-beta2) | Built from source (qt-cmake cross-build) | ✅ Verified | Qt's official MQTT add-on (an MQTT 3.1/3.1.1/5.0 client). A **source-only add-on module**, not in the prebuilt installer (the open-source edition has no component to tick), and GPLv3 (not LGPL — closed-source distribution needs a commercial license, or switch to Paho/mosquitto). The process: clone `qt/qtmqtt`, check out the matching tag → cross-compile with `qt-cmake.bat` + `ohos.toolchain.cmake` → `CMAKE_INSTALL_PREFIX=<QT6_OHOS_KIT>` to **install it into the OHOS kit** (the key trick: libQt6Mqtt.so goes into the kit's `lib/`, the cmake config into `lib/cmake/Qt6Mqtt/`, and the headers into `include/QtMqtt/`, so both the demo's `find_package(Qt6 Mqtt)` and harmonydeployqt6's library copying work). The prebuilt OHOS kit ships `Qt6BuildInternalsConfig.cmake`, which supports building Qt add-ons. Verified output: libQt6Mqtt.so (395 KB) + libsimplemqttclient.so + a HAP (36 MB), with all NEEDED entries as bare names (libQt6Mqtt.so's NEEDED includes libQt6WebSockets.so, and harmonydeployqt6 pulls dependencies recursively and correctly). See [[qt-harmonyos-qt6-status]] \#21 |

---

## 6. Migration assessment checklist

When porting a Qt application, build on [[qt-ohos-project-analyzer-workflow]] §3.4 and confirm each item for every third-party library:

- [ ] **List every third-party library**: name, version, purpose, how it's integrated
- [ ] **Classify each one**: header-only / built from source / prebuilt / system library
- [ ] **For libraries built from source**: does it use CMake? Can it be configured for the OHOS toolchain?
- [ ] **Check platform limitations**: does the source use `chmod()`/`symlink()`/`dlopen()`/`pthread_cancel()`?
- [ ] **Cross-compile**: does it build with the OHOS NDK toolchain?
- [ ] **.so deployment**: has the resulting .so been copied into `entry/libs/arm64-v8a/`?
- [ ] **CMake integration**: is `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` set?
- [ ] **System libraries**: can you just use the system version instead of bundling your own?
- [ ] **Static linking**: can static linking avoid the .so deployment problem?
- [ ] **Verification**: does it build + does the .so load at runtime + does the feature work?

---

## References

- [Building Qt for HarmonyOS](https://wiki.qt.io/Building_Qt_for_HarmonyOS) — Qt cross-compilation toolchain configuration (reusable for third-party libraries)
- [Building C/C++ libraries for HarmonyOS with vcpkg (Qt Blog)](https://www.qt.io/blog/building-libraries-for-harmonyos-with-vcpkg) — A reference for building third-party libraries with vcpkg
- [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations) — Platform limitations in detail (which affect third-party library compatibility)
- [Qt for HarmonyOS Project Structure](../semantic/qt-harmonyos-project-structure.md) — .so deployment directories and CMake configuration
