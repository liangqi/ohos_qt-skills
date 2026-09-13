---
id: problem-cmake-findpackage-ohosextras-fail
type: problem
domain: build
tags: [cmake, ohosextras, find_package, qmake, build-failure]
created: 2026-06-03
updated: 2026-06-03
status: solved
audience: public
summary: "CMake configure reports that find_package can't find the OhosExtras/Qt5OhosExtras package (FindOhosExtras.cmake is missing)"
severity: high

# ====== Search keywords (for fast agent matching) ======
error_message: >
  CMake Error: By not providing "FindOhosExtras.cmake" in CMAKE_MODULE_PATH
  this project has asked CMake to find a package configuration file provided by
  "OhosExtras", but CMake did not find one.
  Could not find a package configuration file provided by "Qt5OhosExtras"
error_code: ""
keywords: [find_package, OhosExtras, Qt5OhosExtras, CMake, CONFIG-=create_cmake]
symptoms: "The CMake configure stage errors out because find_package can't find the OhosExtras package"

# ====== Problem details ======
environment: "Qt 5.12/5.15 for HarmonyOS, CMake cross-compilation"
refs: [semantic-qt-ohos-extras, semantic-qt-harmonyos-build, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-runtime-qpa-plugin-not-found]
---

# CMake find_package(OhosExtras) fails

## Error message

```
CMake Error at CMakeLists.txt:XX (find_package):
  By not providing "FindOhosExtras.cmake" in CMAKE_MODULE_PATH this project
  has asked CMake to find a package configuration file provided by
  "OhosExtras", but CMake did not find one.

  Could not find a package configuration file provided by "Qt5OhosExtras"
  with any of the following names:

    Qt5OhosExtrasConfig.cmake
    qt5ohosextras-config.cmake
```

## Scenario

You wrote `find_package(Qt5 COMPONENTS OhosExtras REQUIRED)` in CMakeLists.txt expecting CMake to find the QtOhosExtras module automatically, and the CMake configure stage errors out immediately.

## Cause

The QtOhosExtras module's `.pro` file contains `CONFIG -= create_cmake`, which means the Qt build system **does not** generate CMake config files (`Qt5OhosExtrasConfig.cmake`) for OhosExtras. As a result, `find_package` cannot locate the module.

This is a known limitation of Qt for HarmonyOS: **QtOhosExtras only supports qmake**.

## Solution

### Option A: use qmake instead (recommended)

In the `.pro` file:
```qmake
ohos {
    QT += ohosextras
}
```

### Option B: link manually from CMake (workaround)

Skip `find_package` and specify the library name directly:
```cmake
if(OHOS)
    # Link QtOhosExtras manually (no find_package support)
    # Note: confirm the library name against your actual Qt for OHOS build output
    target_link_libraries(${PROJECT_NAME} PRIVATE Qt5OhosExtras)
endif()
```

> ⚠️ The library name `Qt5OhosExtras` in option B has not been verified against a real build; it may need to be `Qt5OhosExtrasd` (debug) or something else.

## Notes

- This was a **knowledge inconsistency** found during an audit: `porting-workflow.md` used to recommend the CMake `find_package` approach, while `ohos-extras.md` explicitly marked it qmake-only
- `porting-workflow.md` has been corrected and the CMake `find_package` recommendation removed
- Golden rule B6: **the QtOhosExtras module only supports qmake**

## Related

- [[qt-ohos-extras]] — the qmake-only note
- [[qt-harmonyos-golden-rules]] — rule B6
- [[qt-harmonyos-build]] — CMake build configuration

### Related problems

- [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) — part of the same build/deploy chain: CMake misconfiguration → libqohos.so isn't deployed → runtime crash

> 📋 Back to the [error quick-reference table](_lookup.md)
