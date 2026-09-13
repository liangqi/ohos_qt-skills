---
id: ohos-native-third-party-libraries
title: Contract for integrating native third-party libraries on OHOS
status: active
confidence: 0.7
sources:
  - type: experience
    name: "Qt OHOS LLVM, GStreamer, and third-party library cross-compilation practice"
    date: 2026-08-05
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-05
review_by: null
superseded_by: null
tags: [ohos, ndk, native, cmake, sysroot, musl, shared-library]
refs: [ohos-cross-compile-pitfalls, application-sandbox-paths]
summary: "Platform contract for OHOS NDK third-party libraries: toolchain/sysroot, ABI, artifact validation, HAP deployment, and dynamic loading."
audience: public
---

# Contract for integrating native third-party libraries on OHOS

This page describes only the native platform seam that holds across frameworks. How Qt's `find_package`, a Tauri Cargo build script, JVM JNI, or .NET P/Invoke performs the integration is maintained by each framework's repository.

## Build inputs

- Use the OHOS NDK, Clang, and CMake toolchain that ship with the target HarmonyOS/OpenHarmony SDK; don't mix a host compiler or the Android NDK into the target build.
- The target ABI, API level, sysroot, and C/C++ runtime must all come from the same SDK version.
- When cross-compiling, keep host tools and target libraries distinct; build-time generators generally must run on the host.
- Don't assume glibc internal symbols, Linux desktop libraries, or complete POSIX behavior are available in the OHOS MUSL environment.

A common CMake entry point looks like the following; defer to the target SDK's toolchain documentation for the exact variables:

```bash
cmake -S . -B build-ohos \
  -DCMAKE_TOOLCHAIN_FILE=<OHOS_NDK>/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-ohos
```

## Artifact inspection

Before integrating with a framework, confirm at minimum that:

1. The ELF machine/ABI matches the target device.
2. Every `NEEDED` dependency actually exists on the system or in the HAP.
3. No host absolute paths, RPATHs, or host libraries leaked in.
4. The exported symbols satisfy the consumer's ABI.
5. Stripped/unstripped handling meets the target loader's and your debugging requirements.
6. A fresh clone can rebuild it from the declared source, patches, and build entry point.

## HAP deployment and loading

Native `.so` files normally go into the module's `libs/arm64-v8a/` by ABI, and the build system packages them into the HAP. An application should not copy executable code into an arbitrary writable directory and then `dlopen` it; the bundle, the application data, and what the shell sees are also affected by mount namespaces — see [[application-sandbox-paths]].

An ordinary shared library is not the same as an executable binary. An ELF that needs `execve` must use the platform's supported executable packaging, permissions, and signing chain; the specific runtime integration is maintained by the corresponding framework adapter and a controlled delivery process.

## System libraries and third-party dependencies

- Start by checking the target SDK's headers, stub libraries, and public symbols — don't extrapolate from other Unix platforms.
- When a system library is missing, prefer disabling the inapplicable feature or building an auditable third-party implementation; don't link against glibc private symbols.
- Static linking reduces the number of runtime deployment items, but you must re-check licenses, duplicate symbols, PIC, and the final package size.
- Dynamic linking makes replacement and sharing easier, but requires deploying the full dependency closure and checking loader restrictions.

## Adapter boundary

This common knowledge base maintains the NDK, ABI, sysroot, MUSL, HAP native deployment, and loader invariants. Framework repositories maintain their own package discovery, module/plugin directories, build-parameter passing, API wrappers, and regression tasks.
