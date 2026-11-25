---
id: fault-C-0005
cid: C-0005
type: cause
title: Qt cmake injects -isystem sysroot/usr/include into every CXX command (musl shadows the clang builtins)
nature: defect
domain: build
fault_type: build-blocker
responsible: qt-port
co_responsible: []
component: "qtbase/cmake/QtTargetHelpers.cmake:189 (target_include_directories ... SYSTEM)"
severity: blocker
evidence_type: logs
status: workaround
fix_route: "Locate and remove Qt's SYSTEM include injection of sysroot/usr/include; or the SDK side fixes C-0006 (a fix on either side clears it)"
review_note: "Whether the new OHOS SDK / Qt 6.12 still injects -isystem; whether libcxx-ohos cmath adds the include (C-0006)"
depends_on: []
affects_qt: ["Qt 6.12.0 (c7581743)"]
affects_ohos: ["API 22 (Release 6.0.2.130)", "API 24 Beta1 (DevEco 6.1.1.268)"]
qoh: []
first_seen: 2026-06-25
review_due: 2026-10-15
created: 2026-09-14
updated: 2026-09-14
tags: [qt6, ohos, build, cmake, isystem, musl, nullptr_t, blocker, workaround]
audience: public
refs: [problem-build-fail-qt6-libcpp-musl-isystem, semantic-qt-harmonyos-qt6-status, fault-C-0006]
summary: >
  Qt's build logic injects -isystem sysroot/usr/include into every CXX compile command (904 places in build.ninja),
  letting musl's C headers shadow the clang builtins; combined with C-0006 (libcxx-ohos cmath missing an include) this produces a cascading build
  failure (S-0005, all_of). defect/qt-port (the injecting side); workaround W-0004 (switch the build combination)
  is verified but not a permanent fix; the source of the injected value has not been located.
---

# C-0005 Qt cmake injects -isystem sysroot/usr/include

> nature: defect | responsible: qt-port | status: workaround | symptoms: S-0005 (combined with C-0006) | review: 2026-10-15

## Symptoms

### S-0005 Qt6 OHOS target build fails in a cascade (nullptr_t / __promote / hypot)

Building Qt6 6.12 (commit c7581743) for OHOS per the wiki: the host build succeeds and the target configure
succeeds, but when compiling QtGui (any file that does `#include <algorithm>`/`<memory>`) the libc++ headers fail in a cascade:

```
error: no member named 'nullptr_t' in the global namespace   (cstddef:50 using ::nullptr_t)
error: use of undeclared identifier '__promote'              (cmath:544)
error: call to 'hypot' is ambiguous                          (cmath:552)
```

**Failure structure**: this cause (the injection changes the header search order) + [C-0006](C-0006-libcxx-ohos-cmath-promote.md)
(a libcxx-ohos header defect) only produce the full symptom **in combination** (S-0005's cause_relation = all_of);
a fix on either side clears it.

## Root cause / classification basis (partially located)

- CMake/Qt injects `-isystem <OHOS_SDK>/native/sysroot/usr/include` into every CXX compile command
  (the INCLUDES lines of build.ninja, 904 places). Isolation tests show the OHOS toolchain itself doesn't inject it
  (standalone: 0 places); it is injected by Qt's build logic;
- the injection point is `qtbase/cmake/QtTargetHelpers.cmake:189`
  `target_include_directories("${target}" SYSTEM ... ${arg_SYSTEM_INCLUDE_DIRECTORIES})`,
  but the **source of the value** of `arg_SYSTEM_INCLUDE_DIRECTORIES` has not been located -- not Qt cmake/, not the src
  CMakeLists, not the wrapper, not CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES, not the OHOS toolchain;
- this `-isystem` puts musl's `<stddef.h>`/`<math.h>` (C headers) ahead of the clang
  builtin resource dir in the search order → shadowing: musl's `<stddef.h>` doesn't define `nullptr_t` (glibc does) →
  libc++ `<cstddef>`'s `using ::nullptr_t;` breaks (the nullptr_t part);
- the `__promote`/`hypot` part is determined by C-0006.

## Responsibility

`qt-port` (the injecting side). Shares combined responsibility with this symptom's other cause C-0006 (ohos-ndk);
**a fix on either side clears it**.

## Permanent fix (defect)

Locate and remove Qt's SYSTEM include injection of `sysroot/usr/include` (check whether
`qt_internal_add_module`/the Platform targets add a default SYSTEM include for OHOS).

## Workarounds

- **W-0004 (adopted, verified 2026-07-13 with a build + demo on a real device; not a permanent fix)**: switch the build combination --
  **MinGW g++ 13.1.0 host + API 23 SDK + `configure.bat -submodules` superbuild** →
  it compiles, and the gallery demo runs on a real device.

  ⚠️ Three variables changed at once (host compiler / SDK version / build path); **it was not isolated which one fixed it**;
  the original failing combination (llvm-mingw clang 22 + API 24 + per-module qt-cmake) still fails every time.

  Isolation evidence: `--sysroot` only (no `-isystem`) → `<memory>`+`<cmath>` compile cleanly.
  Retirement condition: once an official release confirms the injection is removed or the SDK fixes C-0006, return to the standard build combination and rerun the isolation tests.

## Tickets

- None yet (the injection source is not fully located; once located, file on the Qt side per `procedural/qt-bug-report-generation.md`;
  full material in
  [build-fail-qt6-libcpp-musl-isystem](../problems/build-fail-qt6-libcpp-musl-isystem.md)).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-25 | Qt 6.12.0 c7581743 + llvm-mingw clang 22 + API 24 Beta1 | per-module qt-cmake build | 904 places of -isystem, cascading failure | → open (blocker) |
| 2026-06-25 | Same as above | Isolation test: drop `-isystem`, keep only `--sysroot` | `<memory>`/`<cmath>` compile cleanly | → diagnosed |
| 2026-07-13 | Qt 6.12.0 + MinGW g++ 13.1.0 + API 23 + superbuild | Full build + gallery demo on a real device | Compiles, demo runs fine | → workaround |

## Related

- Symptoms (S): S-0005 (combined with C-0006, all_of)
- Workarounds (W): W-0004
- Tickets (T): none yet
- problems: [build-fail-qt6-libcpp-musl-isystem](../problems/build-fail-qt6-libcpp-musl-isystem.md)
- semantic: [qt-harmonyos-qt6-status](../semantic/qt-harmonyos-qt6-status.md) §Strategy B
- Related causes (C): [C-0006](C-0006-libcxx-ohos-cmath-promote.md) (ohos-ndk, combined responsibility)
