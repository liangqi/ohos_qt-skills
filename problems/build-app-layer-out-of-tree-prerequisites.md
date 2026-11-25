---
id: problem-build-app-layer-out-of-tree-prerequisites
type: problem
domain: build
tags: [out-of-tree-build, precompiled-header, stdafx, cxx_std_20, code-generation, codegen_style, scheme, TDESKTOP_API_ID, cross-compilation]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "A large Qt desktop application's app layer can't be cross-compiled directly: it gets stuck on the precompiled header, two code generators, and 5 implicit prerequisites"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  error: 'auto' not allowed in friend declaration
  error: no type named 'strong_ordering' in namespace 'std'
  error: use of undeclared identifier 'rpl'
  error: no template named 'flat_set' in namespace 'base'
  error: "You are required to provide API_ID and API_HASH"
  fatal error: 'styles/style_window.h' file not found
  fatal error: 'scheme.h' file not found
  fatal error: 'QOpenGLWidget' file not found
error_code: ""
keywords: [precompiled header, stdafx.h, -include, cxx_std_20, codegen_style, codegen_scheme, scheme.h, TDESKTOP_API_ID, out-of-tree build, OBJECT library]
symptoms: "After adding the app-layer sources directly to a cross-compilation project, 6 kinds of errors appear one after another; fixing each kind only exposes the next"
# ====== Problem details ======
environment: "Qt 6.13.0-dev OHOS kit (with OpenGL/OpenGLWidgets, no Svg); OHOS clang 15; Windows host"
refs: [problem-build-clang15-libcpp15-cpp20-gaps, problem-build-cmake-dedup-include-option, semantic-qt-harmonyos-porting-workflow]
related_problems: [problem-build-cmake-dedup-include-option]
---

# A large Qt desktop application's app layer: 5 implicit prerequisites + 2 traps

## Symptom chain (in the order actually encountered)

When you add `SourceFiles/` to a cross-compilation project as an ordinary source directory to **check that it compiles** (the dependencies aren't all there yet, and you want to verify first that the platform layer builds),
errors show up one kind after another, and **none of them points at the real cause**:

```
# 1) C++20 not enabled
error: 'auto' not allowed in friend declaration
error: no type named 'strong_ordering' in namespace 'std'
# 2) precompiled header not force-included (40+ errors at once, all pointing the wrong way)
error: use of undeclared identifier 'rpl'
error: no template named 'flat_set' in namespace 'base'
# 3) missing API credentials (a hard #error in config.h)
error: "You are required to provide API_ID and API_HASH"
# 4) missing generated files (styles / MTP scheme)
fatal error: 'styles/style_window.h' file not found
fatal error: 'scheme.h' file not found
# 5) missing Qt module
fatal error: 'QOpenGLWidget' file not found
```

## Root cause: 5 implicit prerequisites, all required

| # | Prerequisite | What happens when it's missing |
|---|--------------|--------------------------------|
| 1 | `cxx_std_20` | `friend auto operator<=>(...) = default` reports `auto not allowed` |
| 2 | `-include SourceFiles/stdafx.h` | Every header hits "undeclared identifier" (the headers don't include their own dependencies) |
| 3 | `API_ID` / `API_HASH` macros | A hard `#error` in `config.h` |
| 4 | Two sets of generated files | 147 style header files + the MTP `scheme.h` (several MB) |
| 5 | The right third-party includes (GSL / range-v3 / expected) + Qt modules | `range/v3/all.hpp` / `QOpenGLWidget` not found |

Item 4 has another layer: **the code generators must be able to run on the host**. In a tree being cross-compiled, `codegen_style`
gets built as a target-architecture ELF, and invoking it during the build fails right away with `Error 127` (exec format error).
Upstream tdesktop's Android/iOS cross builds also solve this with a separate host codegen build.

## How to produce each set of generated files without a full configure

```bash
# Styles: 73 .style files -> 147 files
codegen_style -I<SourceFiles> -I<lib_ui> -I<Resources> \
  -o<gen>/styles -t<gen>/styles/td_ui_style -w<Telegram> <73 files>

# MTP scheme: pure Python, no host binary needed
python <SourceFiles>/codegen/scheme/codegen_scheme.py -o<gen>/scheme \
  <scheme>/api.tl <scheme>/mtproto.tl
```

## Two extra traps

1. **`-include` must be written as a single token** (`"-include<path>"`): CMake **de-duplicates** repeated `-include` options,
   and the cross toolchain already injects one of its own (such as `-include libcxx_compat.h`); after de-duplication it becomes `-include A B`,
   and clang treats `B` as an **input file**: `error: cannot specify -o when generating multiple output files`
   — the error doesn't mention `-include` at all. See [[build-cmake-dedup-include-option]].
2. **Uninitialized submodules** need `git submodule update --init <lib>` first: `#include <translate_provider.h>`
   resolves to the file itself and is swallowed by `#pragma once`, which shows up as "the type doesn't exist". See
   [[build-uninitialized-submodule-same-name-header]].

## How to verify

A minimal cross-compilation project (an OBJECT library, not linked) can get the app layer compiling first:

```cmake
target_compile_features(<t> PRIVATE cxx_std_20)
target_compile_definitions(<t> PRIVATE API_ID=... API_HASH=... CRL_USE_QT)
target_compile_options(<t> PRIVATE "-include${SRC}/SourceFiles/stdafx.h")
target_include_directories(<t> PRIVATE
  <src>/SourceFiles <lib_ui> <lib_base> <gen>/styles <gen>/scheme)
target_link_libraries(<t> PRIVATE desktop-app::external_qt)
```

Once it compiles, use `clang++ -H` to confirm the include tree contains `platform/ohos/specific_ohos.h` (not `win/` or `linux/`).

## Boundaries

- This route only **checks that it compiles**: while the dependencies are incomplete you can't link a complete application; `verify`'s G3 will PASS and G4 only reaches PARTIAL.
- Record library-level progress with `qt-ohos-run libcheck <lib> --level built|probed`, so the whole-package gate no longer swallows intermediate results.
