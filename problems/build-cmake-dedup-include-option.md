---
id: problem-build-cmake-dedup-include-option
type: problem
domain: build
tags: [cmake, -include, precompiled-header, deduplication, clang, toolchain, misleading-error]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "CMake de-duplicates the -include option, merging two headers into -include A B, and clang treats B as an input file"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  clang++: warning: treating 'c-header' input as 'c++-header' when in use
  clang++: error: cannot specify -o when generating multiple output files
error_code: ""
keywords: [-include, CMAKE_CXX_FLAGS, deduplication, precompiled header, stdafx.h, libcxx_compat.h, toolchain, cannot specify -o]
symptoms: "After adding -include stdafx.h, the build reports 'cannot specify -o when generating multiple output files'"
# ====== Problem details ======
environment: "CMake 3.x + OHOS clang 15 cross toolchain; Windows host"
refs: [problem-build-app-layer-out-of-tree-prerequisites]
related_problems: [problem-build-app-layer-out-of-tree-prerequisites]
---

# CMake de-duplicates `-include` into `-include A B`

## Root cause

The cross toolchain itself injects a precompiled header on the compiler command line, typically:

```
-include /path/to/libcxx_compat.h
```

To compile the app layer, you add another one:

```cmake
target_compile_options(<t> PRIVATE -include ${SRC}/SourceFiles/stdafx.h)
```

CMake treats this as **a duplicate instance of the same option** and, after de-duplication, merges it into one argument:

```
-include libcxx_compat.h SourceFiles/stdafx.h
```

clang's `-include` accepts only **one** file name, so it treats the second token as an **input file**:

```
clang++: warning: treating 'c-header' input as 'c++-header' when in use
clang++: error: cannot specify -o when generating multiple output files
```

The error **doesn't mention `-include` at all**, so it's easy to go looking at build configuration related to "multiple output files", which is entirely the wrong direction.

## Solution

Write the option and its value as a single token:

```cmake
target_compile_options(<t> PRIVATE "-include${SRC}/SourceFiles/stdafx.h")
```

That way it's an independent string that doesn't take part in `-include` de-duplication; the toolchain's one stays unchanged,
and both precompiled headers take effect (`libcxx_compat.h` first, `stdafx.h` second, with the order preserved by the command line).

## How to verify

1. Look at the actual command line: `ninja -t commands <target> | head -1`, and confirm it has
   two independent tokens, `-includeA -includeB`, rather than `-include A B`.
2. Once it compiles, confirm the precompiled header really takes effect: remove any type definition `stdafx.h` depends on, and the error should be
   "undeclared identifier", not "header file not found".

## Scope

- Any cross build where "the toolchain already injects `-include` and the application wants to add another".
- A trap from the same source: `-isystem` injected by the toolchain gets normalized too; writing a single token is the safest option.
