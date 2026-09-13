---
id: build-fail-qt515-icu-detection
type: problem
domain: build
severity: high
tags: [build, icu, qt515, configure, ohos]
status: open
created: 2026-08-06
updated: 2026-08-09
summary: >
  ICU detection fails during the Qt 5.15 OHOS configure stage (ICU=no, ures.h not found, UCNV_FROM_U_CALLBACK_SUBSTITUTE undeclared) because the sysroot only contains a stub libicu.so and lacks the full ICU trio (libicui18n/libicuuc/libicudata). Fix: upgrade the SDK to 26.0.0.32+, or patch qtbase's configure.json to add an OHOS-specific ICU source.
error_message: "unable to find library -licui18n / ICU=no / ures.h not found / UCNV_FROM_U_CALLBACK_SUBSTITUTE undeclared"
related_problems: [problem-build-fail-qtnetwork-no-ssl]
audience: public
---

# Qt 5.15 OHOS ICU detection failure

## Symptoms

During the configure stage of building the Qt 5.15.16 OHOS source, ICU detection fails:

```
Checking for ICU...
  Trying source 0 (type inline) of library icu ...
    + cd /tmp/config-test-icu && /path/to/qmake ...
    + ...
    => source produced no result
  test config.libraries.icu FAILED

ICU .................................... no
```

The subsequent build then reports:
```
error: 'ures.h' file not found
error: use of undeclared identifier 'UCNV_FROM_U_CALLBACK_SUBSTITUTE'
```

## Cause

The OHOS sysroot only merges in a stub `libicu.so` (a single file, without the `libicui18n` / `libicuuc` / `libicudata` trio), so Qt 5's configure ICU detection script can't find the ICU libraries.

At the same time, `ures.h` (the ICU resource-file header) and `UCNV_FROM_U_CALLBACK_SUBSTITUTE` (an ICU converter callback) are missing from the sysroot, so even force-enabling ICU produces build errors.

## Solution

### Option A: upgrade the OHOS SDK (recommended)

Upgrade the SDK to 26.0.0.32 or newer; the newer sysroot contains the complete ICU trio.

### Option B: patch configure.json

Edit `qtbase/src/corelib/configure.json` to add an OHOS-specific source to the ICU detection:

```json
{
  "libraries": {
    "icu": {
      "label": "ICU",
      "test": {
        "main": "...(ICU test code)..."
      },
      "sources": [
        { "type": "pkgConfig", "args": "icu-uc icu-i18n" },
        { "type": "inline", "libs": ["-licuuc", "-licui18n", "-licudata"] },
        { "type": "inline", "libs": ["-licu"], "condition": "config.ohos" }
      ]
    }
  }
}
```

### Option C: guard ures.h in qcollator

In `qtbase/src/corelib/text/qcollator_icu.cpp`, guard `ures.h` and `UCNV_FROM_U_CALLBACK_SUBSTITUTE`:

```cpp
#if defined(Q_OS_OHOS)
// OHOS sysroot may lack ures.h; skip resource bundle loading
#else
#include <unicode/ures.h>
#endif
```

## Scope of impact

- Building the Qt 5.15.16 OHOS source (the prebuilt Qt 5.12 SDK is unaffected)
- Affects `QCollator` (locale-aware string collation) and `QTimeZone` (time zone data)
- If ICU=no, both of those fall back to non-ICU implementations

## Lessons learned

- The OHOS sysroot's ICU stub is a **merged stub** (a single .so), not the standard trio (icui18n/icuuc/icudata)
- Upgrading the SDK version may introduce new enum discrepancies (see `build-fail-ohos-sdk-enum-werror`), which need to be handled at the same time
- A configure detection failure doesn't necessarily mean the library is absent — the sysroot layout may just differ from standard Linux
