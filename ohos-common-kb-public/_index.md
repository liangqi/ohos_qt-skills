---
updated: 2026-11-11
total_pages: 27
description: >
  The index entry point for the embedded general HarmonyOS platform knowledge base (ArkTS/ArkUI/NAPI/Stage/toolchain).
  These pages come from the upstream common library and are listed by domain; for Qt-side knowledge see ../_index/_map.md.
---

# Embedded platform knowledge index (ohos-common-kb-public)

> Qt-side porting knowledge is in [`_index/_map.md`](../_index/_map.md); this index only collects general platform facts.
> The directory layout matches upstream (semantic / procedural / problems), so files can be compared one by one when syncing.

## Semantic: platform model and specifications

- [`application-sandbox-paths`](semantic/application-sandbox-paths.md) — Distinguishing bundle paths from data paths and the application namespace from the hdc shell namespace, and the rules governing writes, chmod, dlopen, and execve.
- [`arkui-window-xcomponent-model`](semantic/arkui-window-xcomponent-model.md) — Distinguishing WindowStage/main/subwindow, XComponent nodes, the native surface, focus/visible/drawable states, and the old-vs-new API seam.
- [`deveco-mcp-capabilities`](semantic/deveco-mcp-capabilities.md) — Installing deveco-mcp, configuring clients, its check/restart capabilities, and its boundaries; build, run, UI, and log operations belong to devecocli or to explicit low-level diagnosis.
- [`document-picker-uri-access`](semantic/document-picker-uri-access.md) — A picker returns a URI carrying grant semantics; the URI, the converted path, and the temporary/persistent read-write grant must each be handled separately.
- [`hap-application-identity`](semantic/hap-application-identity.md) — The role bundleName plays in platform identity, its syntax/uniqueness checks, and how it relates to profiles, installation, and framework-generated configuration.
- [`hap-native-project-structure`](semantic/hap-native-project-structure.md) — The platform-level relationships between AppScope, module.json5, build-profile, native libs, products, and signingConfig.
- [`harmonyos-development-fundamentals`](semantic/harmonyos-development-fundamentals.md) — A framework-neutral entry point to HarmonyOS application development: HarmonyOS vs. OpenHarmony, and the responsibility boundaries of Stage, ArkTS, ArkUI, Node-API, and DevEco/hdc.
- [`harmonyos-platform-limits`](semantic/harmonyos-platform-limits.md) — Entry point for cross-framework-verified platform limitations: bundle writes/permissions, dynamic code loading, MUSL/SDK, and the boundary of privileged capabilities.
- [`native-runtime-embedding`](semantic/native-runtime-embedding.md) — The three runtime integration models — hap-bin, in-process shared library, and HNP — and their path, signing, JIT, and verification contracts.
- [`ohos-cross-compile-pitfalls`](semantic/ohos-cross-compile-pitfalls.md) — OHOS target cfg, c_char signedness, signing for system permissions, and fresh-clone reproducibility are the four most frequent cross-framework porting pitfalls.
- [`ohos-native-third-party-libraries`](semantic/ohos-native-third-party-libraries.md) — Platform contract for OHOS NDK third-party libraries: toolchain/sysroot, ABI, artifact validation, HAP deployment, and dynamic loading.
- [`privileged-system-capabilities`](semantic/privileged-system-capabilities.md) — API visibility, manifest permissions, profile ACLs, application type, and product type together determine privileged capabilities; ordinary applications must design a degraded path.
- [`stage-uiability-lifecycle`](semantic/stage-uiability-lifecycle.md) — Platform semantics of UIAbility creation, WindowStage, Want routing, launchType, skills, and save/restore in the Stage model.
- [`system-information-access-limits`](semantic/system-information-access-limits.md) — An ordinary application cannot assume all of Linux procfs is readable; use platform APIs per metric, and distinguish unsupported, permission-denied, and genuine zero values.

## Procedural: toolchain and cross-compilation

- [`cpython-dynamic-embedding-ohos`](procedural/cpython-dynamic-embedding-ohos.md) — Embedding CPython in-process on HarmonyOS via libpython + the C API, deploying the stdlib/dependencies, and verifying initialization, threading, and paths.
- [`deveco-cli-usage-rules`](procedural/deveco-cli-usage-rules.md) — devecocli as the preferred entry point, the capability boundaries of the low-level DevEco CLI, and headless diagnosis; minimal auditable low-level calls are allowed when the wrapper doesn't cover something or you're diagnosing the wrapper itself.
- [`ohos-gstreamer-cross-compile`](procedural/ohos-gstreamer-cross-compile.md) — Cross-compiling GStreamer core/plugins for OHOS, trimming features, deploying dependencies, and verifying a minimal pipeline.
- [`ohos-llvm-cross-compile`](procedural/ohos-llvm-cross-compile.md) — Building LLVM-style native CMake projects with the OHOS NDK toolchain, and verifying the target artifacts and dependency closure.

## Problems: platform-side pitfalls and solutions

- [`dlopen-rejects-writable-path`](problems/dlopen-rejects-writable-path.md) — The loader/security policy rejects an application's dlopen of code from an ordinary writable data/cache path; package it with the HAP in a compliant way and check the dependency closure.
- [`document-picker-uri-access-failure`](problems/document-picker-uri-access-failure.md) — The picker URI is treated as an ordinary path, or the converted path lacks the required read/write grant, producing not-found / permission-denied errors.
- [`executable-binary-eacces`](problems/executable-binary-eacces.md) — An ELF binary inside a HAP hits execve EACCES because executableBinaryPaths wasn't declared, the signing/permission/profile is incomplete, or the path is viewed from the wrong namespace.
- [`executable-memory-permission-denied`](problems/executable-memory-permission-denied.md) — JITs such as V8/HotSpot hit ENOMEM/SIGABRT because writable-executable-memory permission or the profile ACL isn't in place; declare the permission and verify the signing grant.
- [`hap-device-sdk-version-mismatch`](problems/hap-device-sdk-version-mismatch.md) — When the device API is lower than the HAP's compatibleSdkVersion, installation returns 9568297/older sdk version; pick a compatible version based on the real minimum capability required.
- [`ohpm-install-timeout`](problems/ohpm-install-timeout.md) — An ohpm install that hangs or times out is usually a registry, proxy, or network reachability problem; diagnose the current configuration first, then switch to a registry that is organization-approved and reachable.
- [`procfs-system-information-unavailable`](problems/procfs-system-information-unavailable.md) — After a library selects the Linux backend, reads of /proc/stat, mounts, or diskstats are denied, so CPU/disk metrics come back empty or zero.
- [`programmatic-hotspot-unavailable`](problems/programmatic-hotspot-unavailable.md) — enableHotspot is deprecated and restricted to non-general-purpose products, so an ordinary application's automatic hotspot feature must degrade or switch to a supported network mode.
- [`runtime-write-to-readonly-bundle-path`](problems/runtime-write-to-readonly-bundle-path.md) — The application writes a database, cache, configuration, or generated file into the packaged resource/installation directory and hits EACCES/EROFS; copy it to a platform-writable data directory.
