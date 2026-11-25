---
id: problem-build-fail-qt6-libcpp-musl-isystem
title: The Qt6 OHOS target build is blocked by libc++/musl incompatibility (an injected -isystem sysroot/usr/include)
type: problem
tags: [qt6, ohos, build, libcxx, musl, cmake, isystem, nullptr_t]
created: 2026-06-25
updated: 2026-07-13
status: solved
audience: public
summary: "The Qt6 OHOS target build is blocked by libc++/musl incompatibility (an injected -isystem sysroot/usr/include makes musl shadow the clang builtins)"
severity: blocker
domain: build
error_message: "no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; the injected -isystem sysroot/usr/include makes musl shadow the clang builtins)"
refs: [fault-C-0005, fault-C-0006, semantic-qt-harmonyos-qt6-status]
---

# The Qt6 for OHOS target build is blocked by libc++/musl incompatibility

## Worked around (2026-07-13; root cause not identified)

> **Status update**: this BLOCKER **no longer reproduces** with the recommended build combination, but the root cause (Qt's cmake injecting `-isystem sysroot/usr/include` into the target CXX commands) is **unfixed** — merely worked around.

- **The original failing combination** (reproduced 2026-06-25): Qt 6.12.0 `c7581743` + **llvm-mingw clang 22** host + the **API 24** SDK + the per-module `qt-cmake -G Ninja -S qtbase` path → build.ninja contains 904 occurrences of `-isystem sysroot/usr/include` → musl's `<stddef.h>`/`<math.h>` shadow the clang builtins → `nullptr_t`/`__promote` errors.
- **The combination that now works** (verified 2026-07-13): the same `c7581743` + **MinGW g++ 13.1.0** host + the **API 23** SDK + the `qt5/configure.bat -submodules` **superbuild** path → builds, and the gallery demo runs on a real device. See [[qt-harmonyos-qt6-status]] §Strategy B.
- **Three variables changed at once** (host compiler / SDK version / build path), and **we didn't isolate which one fixed it**. If you build with the original failing combination, the "Root cause" and "Verified fix" sections below still apply.

## error_message

```
C:/ohos-sdk/native/llvm/bin/../include/libcxx-ohos/include/c++/v1/cstddef:50:9: error:
  no member named 'nullptr_t' in the global namespace
  using ::nullptr_t;
        ~~^
C:/ohos-sdk/native/llvm/bin/../include/libcxx-ohos/include/c++/v1/__memory/unique_ptr.h:173:3:
  error: non-static data member cannot be constexpr; did you intend to make it const?
  error: member 'nullptr_t' declared as a template
  error: unknown type name 'nullptr_t'
C:/ohos-sdk/native/llvm/bin/../include/libcxx-ohos/include/c++/v1/cmath:544:5:
  error: use of undeclared identifier '__promote'
C:/ohos-sdk/native/llvm/bin/../include/libcxx-ohos/include/c++/v1/cmath:552:12:
  error: call to 'hypot' is ambiguous
```

## Scenario

Following wiki.qt.io/Building_Qt6_for_HarmonyOS to build Qt6 6.12 (commit c7581743) for OHOS (arm64-v8a) on Windows, with the OHOS NDK from DevEco 6.1.1.268 / API 24 Beta1 (6.1.1.115). The host build succeeds; the target build configures successfully, but when building QtGui's qimage.cpp/qbitmap.cpp/removed_api.cpp (any file that `#include`s `<algorithm>`/`<memory>`), the libc++ headers fail in cascade.

## Root cause (traced to the source)

1. **CMake/Qt injects `-isystem <OHOS_SDK>/native/sysroot/usr/include` into every CXX compile command** (the INCLUDES lines in build.ninja — 904 occurrences). Isolated testing shows the OHOS toolchain itself doesn't inject it (0 occurrences standalone); Qt's build logic does (the injection point is `qt5/qtbase/cmake/QtTargetHelpers.cmake:189`, `target_include_directories("${target}" SYSTEM ... ${arg_SYSTEM_INCLUDE_DIRECTORIES})`, though where `arg_SYSTEM_INCLUDE_DIRECTORIES` gets its value was never fully traced — it's not Qt's cmake/, not src/*/CMakeLists.txt, not a wrapper, not CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES (which is empty), and not the OHOS toolchain).

2. That `-isystem` puts musl's `<stddef.h>`/`<math.h>` (the C headers) **ahead of** clang's builtin `<stddef.h>` (in the resource dir `llvm/lib/clang/15.0.4/include`) and libc++'s C++ wrapper headers in the search order, **shadowing** them:
   - **nullptr_t**: libc++'s `<cstddef>:50` does `using ::nullptr_t;`, expecting `::nullptr_t` in the global namespace. glibc's `<stddef.h>` defines it; **musl's `<stddef.h>` doesn't** (`grep -c nullptr_t musl/stddef.h` = 0); and clang's builtin `<stddef.h>` only defines it under `#if defined(_MSC_EXTENSIONS) && defined(_NATIVE_NULLPTR_SUPPORTED)` (OHOS isn't MSVC, so it doesn't). So `::nullptr_t` is missing and `using ::nullptr_t;` fails.
   - **cmath __promote**: libcxx-ohos's `<cmath>` uses `__promote` (line 544) but **doesn't `#include <__math/promote.h>`** (lines 307-318 only include math.h/type_traits/version/__undef_macros) — a libcxx-ohos bug that only surfaces when `-isystem` changes the include order and musl's `<math.h>` is selected.

3. **API 22 (Release 6.0.2.130) has the same problem** (musl's `<stddef.h>` likewise lacks nullptr_t, and libcxx-ohos likewise lacks `__math/promote.h`). The earlier successful build used **API 20** (the stable release, no longer on this machine).

## The verified fix (isolated testing)

Removing `-isystem sysroot/usr/include` (using only `--sysroot`) → `<memory>` + `<cmath>` compile cleanly (`--sysroot` puts sysroot/usr/include **after** the clang resource dir in the search order, so musl no longer shadows it).

```bash
# Fails (with -isystem injected; musl shadows)
clang++ --target=aarch64-linux-ohos --sysroot=$S -isystem $S/usr/include -std=gnu++17 -c test_mem.cpp  # 20 errors
# Succeeds (only --sysroot, no -isystem)
clang++ --target=aarch64-linux-ohos --sysroot=$S -std=gnu++17 -c test_mem.cpp                           # clean
```

Partial fixes (incomplete):
- `-include nullptr_t_fix.h` (`typedef decltype(nullptr) nullptr_t;`) → fixes nullptr_t (20 → 3 errors), but cmath's __promote still fails.
- `-I <clang resource>` (so clang's stddef.h is found first) → no effect (clang's builtin stddef.h doesn't define nullptr_t outside MSVC).

## Injection-based fixes that didn't work (none removed the -isystem from build.ninja)

| Attempt | Result |
|---------|--------|
| `CMAKE_PROJECT_INCLUDE` filtering `CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES` (in memory) | The filter worked (IMPLICIT went 4 → 2 directories), but build.ninja still had 904 `-isystem` occurrences (does the Qt build use the cached IMPLICIT? does the superproject reload it?) |
| Editing the cached `CMakeCXXCompiler.cmake` to filter IMPLICIT + re-configure | Re-configuring triggers compiler re-detection, overwriting the edit |
| `CMAKE_PROJECT_QTBASE_INCLUDE` (filtering after qtbase's project()) | That hook only fires for the top-level project(), not for sub-project project() calls |
| Removing `CMAKE_SYSROOT` (having QtOHOSToolchainFixes pass `--sysroot` via flags) | Irrelevant — the OHOS toolchain itself doesn't inject -isystem (0 standalone); Qt does |

## Solutions (pick one)

> **Already worked around in practice**: we switched to the superbuild + MinGW g++ + API 23 combination (see the "Worked around" section above). The 4 options below were the alternatives before the workaround, kept for reference.

1. **Install the stable API 20 OHOS SDK** (what the earlier successful build used; it doesn't have this libc++/musl problem) → install API 20 through the DevEco SDK Manager and re-run the target build.
2. **Trace where Qt gets the value for `arg_SYSTEM_INCLUDE_DIRECTORIES`** and remove sysroot/usr/include from it (look in Qt's cmake for whether `qt_internal_add_module` / a Platform target adds a default SYSTEM include for OHOS).
3. **Create `Platform/OHOS.cmake`** (as CMake's warning "System is unknown to cmake, create Platform/OHOS" suggests) to control how CMake handles includes for OHOS, which may prevent the -isystem injection.
4. **Patch libcxx-ohos's `<cmath>` to add `#include <__math/promote.h>` + patch musl's `<stddef.h>` to add `typedef decltype(nullptr) nullptr_t;`** (modifying SDK headers, which requires the user's authorization to change the SDK).

## Key paths

- OHOS NDK: `C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/native` (junction `C:/ohos-sdk`)
- libcxx-ohos: `<NDK>/llvm/bin/../include/libcxx-ohos/include/c++/v1/`
- clang builtin stddef.h: `<NDK>/llvm/lib/clang/15.0.4/include/stddef.h` (only defines nullptr_t for MSVC)
- musl stddef.h: `<NDK>/sysroot/usr/include/stddef.h` (no nullptr_t)
- Isolated test script: `<LOCAL_PATH>` (`#include <memory>`)

## refs

- [[semantic-qt-harmonyos-qt6-status]]
- [[build-fail-bash-path-escape]] (the PowerShell argument-splitting problem from the same build)
