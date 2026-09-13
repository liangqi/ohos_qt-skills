---
id: problem-runtime-qpa-plugin-not-found
type: problem
domain: runtime
tags: [runtime, QPA, libqohos, dlopen, platform-plugin]
created: 2026-06-03
updated: 2026-06-03
status: solved
audience: public
summary: "The application crashes immediately at startup with dlopen libqohos.so not found / failure to load the qohos QPA plugin"
severity: critical

# ====== Search keywords (for fast agent matching) ======
error_message: >
  dlopen failed: library "libqohos.so" not found
  Cannot load Qt platform plugin "qohos"
  This application failed to start because it could not find or load the Qt platform plugin "qohos"
error_code: ""
keywords: [libqohos, QPA, platform plugin, dlopen, QOhosPlatformIntegrationPlugin]
symptoms: "The application crashes immediately after launch, with logs reporting dlopen failed or platform plugin not found"

# ====== Problem details ======
environment: "Qt 5.12/5.15 for HarmonyOS, real device or emulator"
refs: [semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-build, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-cmake-findpackage-ohosextras-fail, problem-runtime-dlopen-writable-path]
---

# Startup crash because the QPA platform plugin wasn't deployed

## Error message

```
E Qt      : dlopen failed: library "libqohos.so" not found
F Qt      : Cannot load Qt platform plugin "qohos"
F Qt      : This application failed to start because it could not find or load the Qt platform plugin "qohos"
```

Or, viewed through the hdc logs:

```
$ hdc shell hilog | grep -i "qohos\|platform"
E Qt: dlopen failed: library "libqohos.so" not found
```

## Scenario

The application builds successfully, but after the HAP is installed on a device/emulator it crashes immediately on launch (a black screen, then it disappears). The logs show that `libqohos.so` can't be found.

## Cause

`libqohos.so` is Qt for HarmonyOS's QPA (Qt Platform Abstraction) platform plugin, responsible for bridging the Qt window system to HarmonyOS's ArkUI framework. If CMakeLists.txt doesn't link `QOhosPlatformIntegrationPlugin`, the build system won't copy `libqohos.so` into the application's `entry/libs/arm64-v8a/` directory.

At runtime, the Qt core libraries try to `dlopen("libqohos.so")` to load the platform plugin, can't find it in the application's lib directory, and crash.

## Solution

### 1. Link the QPA plugin in CMakeLists.txt

```cmake
target_link_libraries(QtHarmonyApp PRIVATE
    Qt${QT_VERSION_MAJOR}::Core
    Qt${QT_VERSION_MAJOR}::Widgets
    # ★ You must link the QPA platform plugin
    Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin
)
```

### 2. Verify the .so was deployed

```bash
ls entry/libs/arm64-v8a/libqohos.so
# should print the file path
```

### 3. Check the style plugin too

`libqohosstyle.so` must be copied into a subdirectory manually:

```bash
mkdir -p entry/libs/arm64-v8a/styles/
cp <Qt_SDK>/lib/styles/libqohosstyle.so entry/libs/arm64-v8a/styles/
```

## Notes

- This is golden rule B2: **you must link QOhosPlatformIntegrationPlugin**
- Deploying `libqohos.so` is **automatic** (via CMake's target_link_libraries), but `libqohosstyle.so` must be copied **manually** into the `styles/` subdirectory
- If you also see `dlopen failed: library "libQt5Core.so" not found`, the Qt core libraries weren't deployed correctly either — check your `find_package` and `target_link_libraries` configuration
- `dlopen()` can only load a `.so` from the application's (read-only) lib directory, not from a writable path (platform limitation P3)

## Related

- [[qt-harmonyos-project-structure]] — §6 Deploying the Qt runtime libraries
- [[qt-harmonyos-build]] — Build configuration
- [[qt-harmonyos-golden-rules]] — Rules B2/B7
- [[qt-harmonyos-platform-limits]] — The dlopen limitation

### Related problems

- [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) — an upstream cause: a CMake misconfiguration can leave the QPA plugin unlinked
- [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) — the same kind of dlopen failure, but caused by a writable path rather than a missing file

> 📋 Back to the [error quick-reference table](_lookup.md)
