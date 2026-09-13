---
id: problem-build-fail-duplicate-so
type: problem
domain: build
tags: [hvigor, duplicate-so, ProcessLibs, abiFilters, x86_64]
created: 2026-06-04
updated: 2026-06-04
status: solved
audience: public
summary: "The hvigor ProcessLibs stage reports \"Duplicated files found\" (the same .so exists in both obj/ and libs/)"
severity: medium

# ====== Search keywords ======
error_message: >
  Duplicated files found in module entry. This may cause unexpected errors at runtime.
  entry/build/default/intermediates/cmake/default/obj/arm64-v8a/libXxx.so
  entry/libs/arm64-v8a/libXxx.so
error_code: "00306049"
keywords: [Duplicated files, ProcessLibs, pickFirsts, duplicate so]
symptoms: "The hvigor build fails at the ProcessLibs stage with \"Duplicated files found\""

# ====== Problem details ======
environment: "DevEco Studio 5.x / hvigor CLI / Qt 5.12.12 OHOS SDK"
refs: [semantic-qt-harmonyos-project-structure]
related_problems: [problem-cmake-findpackage-ohosextras-fail]
---

# hvigor build reports duplicated .so files at the ProcessLibs stage

## Error message

```
ERROR: Failed :entry:default@ProcessLibs...
Error Code: 00306049 Specification Limit Violation
Error Message: Duplicated files found in module entry. This may cause unexpected errors at runtime.
 - entry/build/default/intermediates/cmake/default/obj/arm64-v8a/libNativeWinLeaveEvt.so
 - entry/libs/arm64-v8a/libNativeWinLeaveEvt.so
```

## Scenario

When CMakeLists.txt is integrated into the build through hvigor's `externalNativeOptions.path`,
manually placing a `.so` of the same name in `entry/libs/arm64-v8a/` as well
makes hvigor find two libraries with the same name and error out.

## Cause

hvigor's CMake integration automatically compiles the C++ code and puts the output in `entry/build/`,
while the `.so` files in `entry/libs/` are also packaged. Two files with the same name collide.

## Solution

1. **Don't manually place application libraries (.so) in `entry/libs/`.** hvigor's CMake integration builds and packages them automatically.
2. **Only place the Qt runtime libraries manually** (libQt5Core.so, libQt5Gui.so, and so on) — those are not build outputs of your project.
3. If you already placed one there, just delete it:

```bash
rm entry/libs/arm64-v8a/libYourApp.so
```

## Additional problem: abiFilters including x86_64 causes a link failure

### Error message

```
ld.lld: error: <LOCAL_PATH> is incompatible with elf_x86_64
```

### Cause

The template bundled with the source defaults `abiFilters` to `["x86_64", "arm64-v8a"]`,
but the Qt SDK only ships prebuilt arm64-v8a libraries.

### Solution

Edit `entry/build-profile.json5`:

```json5
"abiFilters": [
  "arm64-v8a"    // keep only arm64-v8a
]
```

## Notes

- The Qt runtime libraries (libQt5Core.so and friends) still need to be placed manually in `entry/libs/arm64-v8a/`
- libqohosstyle.so goes in the `entry/libs/arm64-v8a/styles/` subdirectory
- Your application's own `.so` is built automatically by hvigor's CMake integration and does not need to be placed manually

## Related

- [[qt-harmonyos-project-structure]] — §6 Deploying the Qt runtime libraries
- [[qt-harmonyos-golden-rules]] — B1 library naming rule

### Related problems

- [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) — also a CMake build configuration problem

> 📋 Back to the [error quick-reference table](_lookup.md)
