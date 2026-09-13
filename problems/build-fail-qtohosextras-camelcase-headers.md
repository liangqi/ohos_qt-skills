---
id: build-fail-qtohosextras-camelcase-headers
type: problem
domain: build
tags: [cmake, qtohosextras, include, qt5.12, camelcase, harmonyos]
created: 2026-06-03
updated: 2026-06-03
status: solved
audience: public
summary: "Building against the Qt 5.12 SDK reports that QtOhosExtras CamelCase headers don't exist (e.g. QOhosAppContext)"
severity: medium
error_code: N/A
error_message: "fatal error: 'QtOhosExtras/QOhosAppContext' file not found"
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-project-structure]
---

# QtOhosExtras CamelCase headers don't exist (Qt 5.12 SDK)

## Error message

```
mainwindow.cpp:12:10: fatal error: 'QtOhosExtras/QOhosAppContext' file not found
#include <QtOhosExtras/QOhosAppContext>
         ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```

## Scenario

When building a Qt for HarmonyOS project in the DevEco Studio build environment, using CamelCase-style `#include` paths (such as `<QtOhosExtras/QOhosAppContext>`) causes the header not to be found.

## Root cause

**The DevEco build system uses the Qt 5.12.12 SDK** (not the Qt 5.15.16 specified by `CMAKE_PREFIX_PATH` in `entry/build-profile.json5`).

In the Qt 5.12 SDK, the QtOhosExtras module **has no CamelCase forwarding headers** (such as `QOhosAppContext` or `QOhosWindowUtils`) — only lowercase `.h` files:

| CamelCase (Qt 5.15+) | Lowercase (Qt 5.12) |
|----------------------|---------------------|
| `<QtOhosExtras/QOhosAppContext>` | `<QtOhosExtras/qohosappcontext.h>` |
| `<QtOhosExtras/QOhosWindowUtils>` | `<QtOhosExtras/qohoswindowutils.h>` |
| `<QtOhosExtras/QOhosUiAbilityContext>` | `<QtOhosExtras/qohosuiabilitycontext.h>` |
| `<QtPlatformHeaders/QOhosFunctions>` | `<QtPlatformHeaders/QOhosFunctions>` ✅ present in both |

**Note**: the namespace is unchanged — both Qt 5.12 and Qt 5.15 use the `QtOhosExtras::` namespace.

## Solution

### Option 1: use the lowercase header paths (works with both Qt 5.12 and Qt 5.15)

```cpp
#ifdef Q_OS_OHOS
#include <QtOhosExtras/qohosappcontext.h>
#include <QtOhosExtras/qohoswindowutils.h>
#include <QtPlatformHeaders/QOhosFunctions>
#endif
```

### Option 2: make sure the Qt 5.15 SDK is used

If you must use the CamelCase paths, make sure the DevEco build system uses the Qt 5.15 SDK (this may require updating DevEco Studio or configuring the SDK path manually).

## Files changed

- `entry/src/main/cpp/mainwindow.cpp` — changed the `#include` paths to lowercase
- `entry/src/main/cpp/CMakeLists.txt` — added `find_package(Qt5 COMPONENTS OhosExtras)` + a fallback

## Additional findings

1. **The DevEco build system overrides CMAKE_PREFIX_PATH**: the `-DCMAKE_PREFIX_PATH=<LOCAL_PATH>` set in `entry/build-profile.json5` is overridden by the DevEco build system, which actually uses the Qt 5.12.12 SDK
2. **`compatibleSdkVersion` needs upgrading**: the `import lazy` syntax in the template requires `"compatibleSdkVersion": "5.0.5(17)"`; the original `"5.0.0(12)"` doesn't support it

## Verification

After the change, `hvigorw assembleHap` builds successfully and produces `entry-default-unsigned.hap`.
