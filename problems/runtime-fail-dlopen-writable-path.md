---
id: problem-runtime-dlopen-writable-path
type: problem
domain: runtime
tags: [runtime, dlopen, sandbox, writable-path, el2, plugin-loading]
created: 2026-06-03
updated: 2026-08-14
status: solved
audience: public
summary: "Runtime dlopen of a .so fails with EINVAL (the path is in the el2 sandbox's writable area)"
severity: high

# ====== Search keywords (for fast agent matching) ======
error_message: >
  dlopen failed: cannot open shared object file
  dlopen: errno=22 (EINVAL)
  library not found in writable path
error_code: "errno=22 (EINVAL)"
keywords: [dlopen, writable, el2, sandbox, plugin, dynamic-loading, EINVAL]
symptoms: "Loading a .so plugin at runtime fails, dlopen returns EINVAL, and the path is under /data/storage/el2/"

# ====== Problem details ======
environment: "Qt 5.12/5.15 for HarmonyOS, real device"
refs: [fault-C-0012, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-third-party-libs, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-runtime-qpa-plugin-not-found]
---

# dlopen from a writable path is rejected

> For diagnosing the platform loader's treatment of ordinary writable code paths, the authority is the common knowledge base's [[ohos-common-kb/problems/dlopen-rejects-writable-path|Shared library fails to load: the code lives on an ordinary writable path]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/problems/dlopen-rejects-writable-path.md)). This page keeps the searchable `QPluginLoader`/Qt plugin symptoms, the deployment location, and the regression method.

## Error message

```
dlopen failed: library "/data/storage/el2/100/base/files/plugins/libMyPlugin.so"
cannot open shared object file: errno=22 (EINVAL)
```

Or, at the Qt level:

```
QPluginLoader: Could not load plugin: dlopen failed
```

## Scenario

The application tries to dynamically load a plugin `.so` from the path returned by `QStandardPaths::writableLocation()` (typically under `/data/storage/el2/`), and `dlopen()` returns EINVAL.

Common cases:
- Plugin systems (downloading a plugin `.so` to a writable directory and then loading it)
- JIT compilers (generating code at runtime, writing it to a file, and loading it)
- Hot-update mechanisms (replacing a `.so` and reloading it)

## Solution

This is HarmonyOS platform limitation P3. For the root cause and workarounds (place it in the application's lib directory / static linking / the Qt plugin mechanism), see the platform limitations page:

→ [[qt-harmonyos-platform-limits]] §dlopen() rejects writable paths

> If you need to download and execute code at runtime, consider ArkTS/JS scripts instead of `.so` plugins. Third-party libraries (including Qt's own plugin loading) are subject to the same limitation, so make sure every `.so` is deployed into the lib directory at packaging time.

## Related

- [[qt-harmonyos-platform-limits]] — §dlopen limitation details
- [[qt-harmonyos-third-party-libs]] — §3 .so deployment rules
- [[qt-harmonyos-golden-rules]] — Rule P3

### Related problems

- [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) — the same kind of dlopen failure, but caused by a missing .so rather than path permissions

> 📋 Back to the [error quick-reference table](_lookup.md)
