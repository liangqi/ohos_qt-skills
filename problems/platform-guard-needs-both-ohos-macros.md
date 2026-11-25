---
id: problem-platform-guard-needs-both-ohos-macros
type: problem
domain: build
tags: [platform-guard, Q_OS_OHOS, Q_OS_HARMONY, dual-macro, qsystemdetection, branch-detection, false-fix]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: high
audience: public
summary: "A platform guard written with only Q_OS_OHOS: the Qt 6.x kit only defines Q_OS_HARMONY, so the branch silently falls through to the Linux implementation"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  The build reports no errors, but at runtime the Linux implementation is still used;
  if the Linux implementation actually gets compiled in, you get:
  fatal error: 'gio/gio.h' file not found
  fatal error: 'xcb/xcb.h' file not found
error_code: ""
keywords: [Q_OS_OHOS, Q_OS_HARMONY, qsystemdetection, dual-macro guard, platform_specific.h, -DQ_OS_OHOS, false fix, --target, -H]
symptoms: "The platform dispatch header has #elif defined Q_OS_OHOS, but it's never true; it compiles, and the behavior is Linux's"
# ====== Problem details ======
environment: "Qt 6.13.0-dev (native build on a HarmonyOS PC) compared against the vendor Qt 5.15.16 OHOS kit; OHOS clang 15"
refs: [problem-build-qt612-qos-harmony-macro, problem-platform-layer-two-dispatch-modes, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-build-qt612-qos-harmony-macro]
---

# A platform guard written with only `Q_OS_OHOS` doesn't work: the Qt 6.x kit only defines `Q_OS_HARMONY`

## Root cause

`qsystemdetection.h` uses **inconsistent macro names** on the OHOS branches of Qt 5 and Qt 6:

```c
// Qt 6.12+ / 6.13.0-dev: <kit>/include/QtCore/qsystemdetection.h
#elif defined(__OHOS__)
#  define Q_OS_HARMONY          // only this one; Q_OS_OHOS isn't defined
```

The vendor Qt 5.15.16 OHOS kit, by contrast, defines **both** `Q_OS_OHOS` and `Q_OS_HARMONY`.
So a guard that "names only one macro" is always dead code on the other kit:

```cpp
// platform/platform_specific.h (before the change)
#ifdef Q_OS_WIN
#  include "platform/win/specific_win.h"
#elif defined Q_OS_MAC
#  include "platform/mac/specific_mac.h"
#elif defined Q_OS_OHOS          // ← never true on the Qt 6 kit
#  include "platform/ohos/specific_ohos.h"
#else
#  include "platform/linux/specific_linux.h"   // ← it actually lands here
#endif
```

## Why "manually adding `-DQ_OS_OHOS`" is a false fix

Adding a compile macro looks like it fixes things immediately, but it replaces a **kit fact** with a **build-script convention**:

1. It recurs as soon as you switch kits, with no warning when it does;
2. `Q_OS_WIN` is **first** in the dispatch chain. When you run hand-assembled flags against the host triple, `Q_OS_WIN` matches first,
   and `-DQ_OS_OHOS` can't save you at all: you'll get a self-contradictory conclusion like `specific_win.h`.

The right approach: **make the guard accept both macros**, and remove `-DQ_OS_OHOS` from the build scripts:

```cpp
#elif defined Q_OS_OHOS || defined Q_OS_HARMONY
#  include "platform/ohos/specific_ohos.h"
```

## How to tell "which branch is actually being compiled"

You must probe with the **complete compile command**; the flags in `flags.make` aren't enough to reproduce it. The cross toolchain puts
`--target=aarch64-linux-ohos` on the compiler command line, and hand-assembled flags fall back to the host triple:

```bash
# Correct: with the toolchain's --target
clang++ --target=aarch64-linux-ohos -H -fsyntax-only $DEFS $INCS $FLAGS probe.cpp \
  | grep 'specific_.*\.h'
# .. <src>/platform/ohos/specific_ohos.h      ← dual-macro guard: correct hit

# Wrong: --target dropped
clang++ -H -fsyntax-only $DEFS $INCS $FLAGS probe.cpp \
  | grep 'specific_.*\.h'
# .. <src>/platform/win/specific_win.h        ← host triple: the opposite conclusion
```

## How to verify

1. Audit whether every platform dispatch header names both macros:
   `python tools/ohos-platform-audit.py <app>/SourceFiles/platform` (exit code 0 = all pass).
2. The `clang++ -H` comparison above: for the same code, with `--target` and without `--target` should give different platform headers,
   proving the flags really reach the compiler.
3. Runtime double-check: after the change, rebuild and install; the platform paths, data directory, and tray capability queries in the logs should be HarmonyOS values
   (such as `platform appdata "/data/storage/el2/base/files/"`), not Linux paths.

## Scope

- Any Qt application that dispatches by platform with `#ifdef` chains (not just tdesktop).
- On Qt 6.12 / 6.13-series kits, **`Q_OS_OHOS` never exists**; on 5.15-series kits both exist.
  Cross-kit code can only write `defined Q_OS_OHOS || defined Q_OS_HARMONY`.
