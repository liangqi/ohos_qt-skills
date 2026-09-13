---
id: hap-native-project-structure
title: HAP native project structure and its relationship to signing
status: active
confidence: 0.7
sources:
  - type: experience
    name: "Qt, Tauri, and AWT/Swing HAP project practice"
    date: 2026-08-06
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-06
review_by: null
superseded_by: null
tags: [hap, appscope, module-json5, build-profile, signing, native-libs]
refs: [hap-application-identity, ohos-native-third-party-libraries]
summary: "The platform-level relationships between AppScope, module.json5, build-profile, native libs, products, and signingConfig."
audience: public
---

# HAP native project structure and its relationship to signing

## Configuration layers

| File/directory | Platform responsibility |
|---|---|
| `AppScope/app.json5` | Application-level identity and display metadata, e.g. bundleName |
| `build-profile.json5` | products, modules, build modes, SDK, and signingConfigs |
| `<module>/src/main/module.json5` | module/Ability, device types, permissions, skills, and native/executable declarations |
| `<module>/libs/<abi>/` | Target-ABI native libraries/binaries packaged with the module |
| `<module>/src/main/ets/` | Abilities, pages, and ArkTS glue |
| `<module>/src/main/cpp/` | Node-API/native modules and the CMake project |
| resources/rawfile/resfile | Packaged resources; whether they are writable/executable at runtime is governed by the sandbox contract |

A framework template may add its own constants, generation scripts, and glue, but it cannot change the ownership of these platform layers.

## Native artifact contract

- The directory ABI must match the build target and the device.
- The library name inside the HAP must match the ArkTS `libraryname`, the Node-API module, the framework loader, or the CMake output.
- A `.so`'s dependency closure must either be packaged with it or provided by the target system; a successful host build does not prove the device loader can resolve it.
- Binaries that need `execve` use different declarations, permissions, and signature checks than ordinary `.so` files; the specific runtime integration is maintained by the corresponding framework adapter and a controlled delivery process.

## Products and signing

Defining `signingConfigs` does not by itself make a product use a signature. The target product must reference the corresponding `signingConfig`, and the profile must additionally match the bundleName, device, and permission grants.

Signing material must never be committed. Shared pages record only field relationships, how things are generated, and verification steps — never certificate paths, passwords, device identities, or reusable profiles.

## Verification order

1. Schema/configuration checks
2. product/module/SDK/ABI alignment
3. Native artifacts and dependency closure
4. signingConfig references and application identity
5. The target files actually present in the build output
6. Installation, launch, and system logs
7. A fresh-clone / fresh-package rebuild
