---
id: ohos-llvm-cross-compile
title: Cross-compiling LLVM-style native projects for OHOS
status: active
confidence: 0.5
sources: [{type: experience, name: "Qt KB LLVM OHOS cross-compilation process", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-05
review_by: null
superseded_by: null
tags: [ohos, llvm, cross-compile, cmake, ndk]
refs: [ohos-native-third-party-libraries, ohos-cross-compile-pitfalls]
summary: "Building LLVM-style native CMake projects with the OHOS NDK toolchain, and verifying the target artifacts and dependency closure."
audience: public
---

# Cross-compiling LLVM-style native projects for OHOS

## Why:

LLVM and similar large CMake projects often build host generators and target libraries in the same run. Setting only `CC/CXX` makes it easy for CMake to mix in the host sysroot, try to run target tools, or produce artifacts with the wrong ABI.

## How to apply:

1. Pin the target SDK/NDK, API level, ABI, and source version.
2. Clean out old host build directories, and use separate build directories for host tools and target artifacts.
3. Configure the target build with the OHOS toolchain file; explicitly disable components the target system doesn't support or that your task doesn't need.
4. If the project needs tablegen or another code generator, build the host version first and pass it in through the variable the project supports — never run an OHOS target binary on the host.
5. After the build, check the ELF, its `NEEDED` entries, exported symbols, RPATH, and for leaked host paths.
6. Deploy the `.so` files into the HAP's ABI directories and verify loading and the core APIs with a minimal native consumer.
7. Only then wire in the Qt, Rust, JVM, or .NET adapter, and verify that in the corresponding framework repository.

Minimal configuration skeleton:

```bash
cmake -S <source> -B <target-build> \
  -DCMAKE_TOOLCHAIN_FILE=<OHOS_NDK>/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_BUILD_TYPE=Release \
  <project-specific-feature-flags>
cmake --build <target-build> --parallel
```

## Failure taxonomy

| Stage | Common cause | Check first |
|---|---|---|
| configure | Mixed toolchain/sysroot, missing host tool | CMake cache, compiler target, try_compile logs |
| compile | POSIX/glibc assumptions, SDK header/API differences | The first target compile error — don't start by editing framework code |
| link | Missing system library, symbol visibility, dependency order | The link line, undefined symbols, target SDK stubs |
| load | Dependency not packaged, ABI/RPATH, loader policy | The ELF dynamic section, HAP contents, system logs |

## Acceptance

A successful build is not the same as a reusable one: you must record the versions/flags/patch provenance, and complete the target artifact inspection, the minimal load verification, and a fresh-clone rebuild.
