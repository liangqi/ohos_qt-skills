# Missing QtOhosExtras forwarding header causes file not found

> ID: build-fix-05
> Date: 2026-09-28 (based on actual build)
> Files involved: `entry/src/main/cpp/pages/s9_base_equals_window.cpp`
> Project root: `QtBugDemo-official/`
> Status: Not fixed

## 1. Error

```
FAILED: CMakeFiles/qtbugdemo.dir/pages/s9_base_equals_window.cpp.o
s9_base_equals_window.cpp:25:10: fatal error: 'QtOhosExtras/QOhosAbilityContext' file not found
#include <QtOhosExtras/QOhosAbilityContext>
         ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```

## 2. Root cause

`#include <QtOhosExtras/QOhosAbilityContext>` expects a forwarding header named `QOhosAbilityContext`
(**without a `.h` extension**).

The measured contents of the `include/QtOhosExtras/` directory:

| File | Type | Present? |
|------|------|----------|
| `qohosabilitycontext.h` | Implementation header | ✓ |
| `QOhosAbilityContext` | Forwarding header (no extension) | ✗ **missing** |

Compare `include/QtCore/`: `QObject` (forwarding header) ✓ + `qobject.h` (implementation header) ✓.

QtCore has forwarding headers; QtOhosExtras **has only implementation headers and lacks forwarding headers**.

The include is unused — the file makes no actual `QOhosAbilityContext::` call anywhere; it is a leftover from the migration.

## 3. Fix

Remove the unused include:

```diff
  #include "demopage.h"
- #include <QtOhosExtras/QOhosAbilityContext>
```

## Auto-fix

```yaml
match: "QtOhosExtras/.*file not found"
files:
  - entry/src/main/cpp/pages/s9_base_equals_window.cpp
actions:
  - type: remove_include
    include: "#include <QtOhosExtras/QOhosAbilityContext>"
```
