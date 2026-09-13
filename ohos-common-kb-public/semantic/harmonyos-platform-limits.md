---
id: harmonyos-platform-limits
title: HarmonyOS platform limitations
status: active
confidence: 0.7
sources: [{type: experience, name: "Qt, Tauri, AWT/Swing cross-framework on-device verification", date: 2026-08-06}]
created: 2026-08-13
updated: 2026-08-14
last_confirmed: 2026-08-06
review_by: null
superseded_by: null
tags: [ohos, platform-limits, sandbox, musl, permissions]
refs: [application-sandbox-paths, ohos-native-third-party-libraries]
summary: "Entry point for cross-framework-verified platform limitations: bundle writes/permissions, dynamic code loading, MUSL/SDK, and the boundary of privileged capabilities."
audience: public
---

# HarmonyOS platform limitations

This page collects only conclusions that hold independently of any single framework. The device form factor, system version, SDK/API, and the date of the evidence are part of each conclusion; framework errors, API wrappers, and workarounds stay in the corresponding framework repository.

## Confirmed limitations

| Area | Platform constraint | Severity | Evidence boundary |
|---|---|---|---|
| Bundle paths | Installed content is generally read-only; an ordinary application cannot turn a packaged file into an executable via `chmod` | Blocking | Verified on device across multiple runtimes/HAPs; see [[application-sandbox-paths]] |
| Code loading | An ordinary writable data path does not automatically become a location from which `dlopen`/`execve` is permitted | Blocking | Verified with Qt plugin/runtime embedding; see problems |
| Mount namespace | The application and the hdc shell may observe the same installed content under different prefixes | High | Verified with API24 PC/2-in-1 runtime embedding |
| Writable executable memory | Dynamic code generation such as JIT requires a platform permission, and the profile ACL must grant it | Blocking | Verified for JVM/V8 across both repositories |
| MUSL/SDK | You cannot assume glibc private symbols, Linux desktop libraries, or complete POSIX behavior are present | High | Verified with native/Rust/Qt cross-compilation |
| System privilege | Privileged system capabilities cannot be obtained by manifest declaration alone; they are constrained by certificate/profile/application type | Blocking | Verified via signing and runtime testing |

## How to use this page

1. First determine whether the error comes from a platform invariant rather than a framework adapter.
2. Record the device, system/API, SDK, application type, and signing profile.
3. Confirm with a minimal native case or evidence from a second framework before promoting it to a conclusion on this page.
4. Re-confirm after version upgrades; don't enshrine old device behavior permanently.

## Out of scope for this page

Behavior that holds only for a framework/runtime — the Qt/QML platform name, QPA, GStreamer plugins, Rust crate cfg, the JVM stack, .NET TFMs, and so on — does not belong in the body of the platform limitations; those pages can link here to explain the platform-level trigger conditions.
