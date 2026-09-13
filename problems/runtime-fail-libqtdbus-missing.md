---
id: problem-runtime-fail-libqtdbus-missing
type: problem
domain: runtime
tags: [qt, harmonyos, dbus, dlopen, libqohos, runtime, missing-so]
created: 2026-07-08
updated: 2026-07-08
status: solved
severity: critical
audience: public
refs: [semantic-qt-harmonyos-build-run-workflow, procedural-qt-ohos-run-test]
summary: >
  libqohos.so depends on libQt5DBus.so at runtime, but CMakeLists.txt doesn't link Qt5::DBus, so the library never gets deployed into the HAP;
  dlopen fails on the device → the QPA plugin fails to load → JSCrash. Fix: add Qt5::DBus in CMake.
leader_summary: >
  Fixed a startup crash in Qt HarmonyOS applications caused by a missing DBus library, and captured it as a reusable CMake configuration check.
impact: [Migration efficiency, Framework support]
deliverables: [problem record, CMake fix]
evidence: [RedisView on-device verification commit, crash log]
error_message: >
  W MUSL-LDSO: load libQt5DBus.so failed, namespace=ndk no inherits, errno=2
  W MUSL-LDSO: load libQt5DBus.so failed, namespace=moduleNs_default, errno=2
  W MUSL-LDSO: Error loading shared library libQt5DBus.so: (needed by /data/storage/el1/bundle/libs/arm64/libqohos.so)
  E ArkCompiler: [ecmascript] export objects of native so is undefined, so name is @app:<bundleName>/entry/qohos
  TypeError: Cannot read property handleAbilityStageOnCreate of undefined
error_code: ""
keywords: [libQt5DBus, libqohos, dlopen, MUSL-LDSO, QPA, Qt5::DBus, find_package]
symptoms: "The application crashes immediately after launch (JSCrash TypeError), with logs showing libQt5DBus.so failing to load"
environment: "Qt 5.15.16 OHOS / HarmonyOS 6.0 / HUAWEI MateBook 14"
---

# libQt5DBus.so isn't deployed, so the QPA plugin fails to load

## Error message

```
W C03F07/MUSL-LDSO: load libQt5DBus.so failed, namespace=ndk no inherits, errno=2
W C03F07/MUSL-LDSO: load libQt5DBus.so failed, namespace=moduleNs_default, errno=2
W C03F07/MUSL-LDSO: Error loading shared library libQt5DBus.so: (needed by /data/storage/el1/bundle/libs/arm64/libqohos.so)
W C03F04/com.xxx/MMG: [NMM:1377]key:default/qohos First: failed Error loading shared library libQt5DBus.so
E C03F00/com.xxx/ArkCompiler: [ecmascript] export objects of native so is undefined, so name is @app:xxx/entry/qohos
E C03F00/com.xxx/ArkCompiler: TypeError: Cannot read property handleAbilityStageOnCreate of undefined
    at onCreate entry (entry/src/main/ets/qabilitystage/QAbilityStage.ets:47:9)
```

## Scenario

The Qt HarmonyOS port builds and installs successfully, but crashes immediately after launch. The crash is a JSCrash (TypeError), not a C++ crash.

## Cause

`libqohos.so` (the Qt OHOS QPA platform plugin) was linked against `libQt5DBus.so` when it was built, but the application's `CMakeLists.txt` doesn't include the `DBus` module in `find_package` or `target_link_libraries`.

The build system only deploys the `.so` files for Qt modules explicitly declared in `target_link_libraries` into the HAP, so `libQt5DBus.so` was never copied into `entry/build/default/intermediates/cmake/default/obj/arm64-v8a/` and therefore isn't in the final HAP's `libs/arm64/` directory.

When the device runs `dlopen("libqohos.so")`, the dynamic linker fails to resolve the `libQt5DBus.so` dependency, so the whole of `libqohos.so` fails to load. The native module `qohos` is exported as `undefined` on the ArkTS side, and the subsequent call to `handleAbilityStageOnCreate` raises a TypeError.

## Solution

Add the `DBus` module in `OhosExampleApp/CMakeLists.txt`:

```cmake
# Before
find_package(Qt5 5.15 REQUIRED COMPONENTS Core Gui Widgets Network Sql Xml)

# After
find_package(Qt5 5.15 REQUIRED COMPONENTS Core Gui Widgets Network Sql Xml DBus)
```

```cmake
# Before
target_link_libraries(OhosRedisView PRIVATE
    Qt5::Core Qt5::Gui Qt5::Widgets Qt5::Network
    Qt5::Sql Qt5::Xml
    Qt5::QOhosPlatformIntegrationPlugin
)

# After
target_link_libraries(OhosRedisView PRIVATE
    Qt5::Core Qt5::Gui Qt5::Widgets Qt5::Network
    Qt5::Sql Qt5::Xml Qt5::DBus
    Qt5::QOhosPlatformIntegrationPlugin
)
```

## How to verify

After building, check the native library directory:

```powershell
Get-ChildItem "entry\build\default\intermediates\cmake\default\obj\arm64-v8a" -Filter "*.so" | Select-Object Name
# Confirm libQt5DBus.so is present
```

## Notes

- `libqohos.so`'s DT_NEEDED list depends on how Qt was configured at build time; different Qt versions may depend on different module sets
- A general approach: run `readelf -d libqohos.so | grep NEEDED` to check every runtime dependency and make sure each one is in `target_link_libraries`
- This problem produces no build error (since `libqohos.so` is prebuilt and doesn't participate in the current CMake link check) — it only shows up when running on a device

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Fixed a startup crash in Qt HarmonyOS applications caused by a missing DBus library, producing a general method for checking .so dependencies |
| Scope of impact | Every Qt HarmonyOS application built with Playbook A |
| Deliverables | problem record + CMake fix |
| Evidence | RedisView on-device verification commit |
| How to reuse | Apply directly when you hit `Error loading shared library libQt5DBus.so` |

## Related

- [[runtime-fail-qpa-plugin-not-found]] — a similar QPA plugin load failure
- [[qt-harmonyos-build-run-workflow]] — The build-and-run workflow
