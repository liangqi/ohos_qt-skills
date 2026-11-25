---
id: problem-build-uninitialized-submodule-same-name-header
type: problem
domain: build
tags: [git submodule, same-name-header, include-path, pragma once, self-inclusion, translate_provider]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "With the submodule uninitialized, an angle-bracket include resolves to the file itself and is swallowed by pragma once → the type doesn't exist"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  error: no member named 'TranslateProvider' in namespace 'Ui'
  error: unknown type name 'TranslateProviderRequest'
error_code: ""
keywords: [submodule, git submodule update --init, same-name header, angle-bracket include, pragma once, include path, self-inclusion]
symptoms: "A type that clearly exists is reported as undeclared; the error points at business code, but actually the submodule wasn't pulled"
# ====== Problem details ======
environment: "CMake cross build; the repository manages the Telegram/lib_* submodules with git submodule"
refs: [problem-build-app-layer-out-of-tree-prerequisites]
related_problems: [problem-build-app-layer-out-of-tree-prerequisites]
---

# Submodule not initialized → a same-name header resolves to itself

## Root cause

The application sources have an angle-bracket include:

```cpp
// SourceFiles/lang/translate_provider.h
#include <translate_provider.h>     // points at Telegram/lib_translate/translate_provider.h
```

Angle brackets mean "search the include path". When the submodule `Telegram/lib_translate` is **uninitialized** (an empty directory)
and `SourceFiles/lang` is also on the include path, this line resolves to **the file itself**:

1. `SourceFiles/lang/translate_provider.h` includes itself;
2. the `#pragma once` at the top of the file decides it's "already included", and the entire content is skipped;
3. so `Ui::TranslateProvider` and `TranslateProviderRequest` all "don't exist".

The error points at business code (`no member named 'TranslateProvider' in namespace 'Ui'`),
and looks nothing like "the submodule wasn't pulled".

## Solution

```bash
git submodule update --init Telegram/lib_translate
# or pull them all at once
git submodule update --init --recursive
```

Don't work around it by "changing the include order" or "adding -I": once you've worked around it, the real implementation is still missing, and the link blows up again.

## How to verify

1. `git submodule status | grep '^-'`: a leading `-` means uninitialized.
2. Once it compiles, confirm where the header comes from: `clang++ -H ... | grep translate_provider` should show
   `Telegram/lib_translate/translate_provider.h`, not `SourceFiles/lang/translate_provider.h`.

## Related

Build errors of this "the error doesn't point at the real cause" kind come as a group in this repository (C++20 gaps, the precompiled header, API credentials, code generation,
Qt modules, same-name headers); for the troubleshooting order see [[build-app-layer-out-of-tree-prerequisites]].
