---
id: problem-build-qt612-qos-harmony-macro
type: problem
domain: build
tags: [qt612, qsystemdetection, Q_OS_HARMONY, Q_OS_OHOS, cmake_helpers, nice_target_sources, macro-not-defined]
created: 2026-09-11
updated: 2026-11-04
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-build]
summary: >
  The platform macro of the Qt 6.12+ (including 6.13.0-dev) harmonyos kit is Q_OS_HARMONY (not Q_OS_OHOS),
  and if the OHOS branch marks the not_linux set in nice_target_sources, it also excludes the files with the ohos suffix
  that hold the implementations: all of platform/ohos is silently not compiled, and the link blows up with a flood of undefined symbols.
leader_summary: >
  Corrected the understanding of the Q_OS_HARMONY macro and the set semantics of nice_target_sources, eliminating the trap where the ohos implementations are silently excluded
impact: [Build system, Platform backend]
deliverables: [problem record]
evidence: []

error_message: >
  ld.lld: error: undefined symbol: Platform::IsWayland()
  ld.lld: error: undefined symbol: base::Platform::Haptic()
  ld.lld: error: undefined symbol: Ui::Platform::TranslucentWindowsSupported()
  (every platform/ohos implementation symbol is missing, with zero errors at compile time)
error_code: ""
keywords: [Q_OS_HARMONY, Q_OS_OHOS, __OHOS__, nice_target_sources, not_linux, HEADER_FILE_ONLY, undefined symbol]
symptoms: "The OHOS cross-compilation passes completely, but the link reports a flood of undefined platform-layer symbols; the dispatch headers always fall into the linux branch"

environment: "Windows + Qt 6.12-beta3 / 6.13.0-dev harmonyos_arm64_v8a kit + OHOS NDK clang15 (verified on both versions)"
---

# The Qt 6.12 OHOS kit's platform macro is Q_OS_HARMONY + ohos source files are silently excluded

## Error message

```
ld.lld: error: undefined symbol: Platform::IsWayland()
ld.lld: error: undefined symbol: Platform::NewVersionLaunched(int)
ld.lld: error: undefined symbol: base::Platform::Haptic()
ld.lld: error: undefined symbol: Ui::Platform::TranslucentWindowsSupported()
```

## Scenario

Porting a large project with 2000+ build targets to OHOS: following the knowledge base's convention, we wrote `#if defined Q_OS_OHOS` dispatch guards
and added an ohos-tag branch in cmake_helpers' `nice_target_sources`. All targets compiled
successfully, and then the final link of the main business .so blew up with 20+ undefined platform symbols.

## Cause (two stacked traps)

1. **Qt 6.12-beta3's qsystemdetection.h defines `Q_OS_HARMONY`, not `Q_OS_OHOS`**
   (**version range: 6.12+; verified to hold for 6.13.0-dev too**: 6.13.0-dev's
   `qsystemdetection.h` is still `#elif defined(__OHOS__) → #define Q_OS_HARMONY`, and doesn't define `Q_OS_OHOS`):
   `__OHOS__` (predefined by the compiler) → `Q_OS_HARMONY + Q_OS_LINUX`. Only the Qt 5.15/5.12 harmonyos
   branches use `Q_OS_OHOS`. Every `#ifdef Q_OS_OHOS` guard is dead code under the 6.12 kit,
   and all dispatch headers fall into the linux branch.

2. **The nice_target_sources set semantics are backwards**: if files with the ohos suffix are added to `not_linux_sources`
   (to exclude them on Linux), and the OHOS branch happens to mark `not_linux` (reusing the LINUX branch's logic),
   then in the OHOS build `set_source_files_properties(... HEADER_FILE_ONLY TRUE)` marks
   **every ohos implementation file as header-only and silently skips compiling it**, with zero errors at compile time.

## Fix

- Write guards that work with both major Qt versions:

```cpp
#if defined Q_OS_HARMONY || defined Q_OS_OHOS   // both kits: 6.12+ / 5.15
#include "platform/ohos/xxx_ohos.h"
#else
#include "platform/linux/xxx_linux.h"
#endif
```

- The correct nice_target_sources sets:

```cmake
# win files   -> not_mac, not_linux, not_ohos
# mac files   -> not_win, not_linux, not_ohos
# linux files -> not_win, not_mac
# ohos files  -> not_win, not_mac, not_linux
# posix files -> not_win
# The OHOS branch marks only not_ohos_sources (= win+mac); linux/posix/ohos are all kept
```

## Verification

Use `llvm-nm -C <specific_ohos.cpp.o>` to confirm the implementation symbols really are in the object file (we once saw
a definition in the source file but nothing in the .o: the header declared it `inline`, so the definition was weakened and dropped).

## Troubleshooting commands

```
clang -dM -E -x c++ nul | findstr OHOS     # confirm __OHOS__ is predefined
grep Q_OS_HARMONY <kit>/include/QtCore/qsystemdetection.h
```
