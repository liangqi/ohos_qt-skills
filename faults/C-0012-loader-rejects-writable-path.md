---
id: fault-C-0012
cid: C-0012
type: cause
title: The application loader refuses to load dynamic libraries from writable paths (code loading is limited to the HAP lib directory; dlopen from the el2 writable area returns EINVAL)
nature: limitation
domain: runtime
fault_type: gap
responsible: ohos-runtime
co_responsible: []
component: "HarmonyOS application sandbox loader specification × dlopen / QPluginLoader"
severity: high
evidence_type: logs
status: wontfix
evidence: "Loader security specification: dynamic libraries can only be loaded from the native library directory packaged in the HAP; dlopen from ordinary writable paths (the files area under /data/storage/el2/) returns errno=22 (EINVAL). QTBUG-146624 records the platform behavior; ohos-common-kb diagnostic page dlopen-rejects-writable-path (holds across frameworks)"
evolution: "— (the specification is stable, no evolution direction; if the platform opens a controlled runtime code loading mechanism in the future, reclassify at review)"
fix_route: ""
review_note: "Whether the loader's writable-path restriction has loosened (reclassify if controlled runtime loading opens up); replies on T-0007 (QTBUG-146624)"
depends_on: []
affects_qt: []
affects_ohos: ["all versions (loader specification; the source page records evidence on real devices with Qt 5.12/5.15)"]
qoh: []
first_seen: 2026-06-03
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [harmonyos, sandbox, loader, dlopen, qpluginloader, el2, plugin, hot-update, limitation, workaround]
audience: public
refs: [problem-runtime-dlopen-writable-path, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-third-party-libs]
summary: >
  The application loader only allows loading dynamic libraries from the HAP native library directory; dlopen from writable paths (the el2 sandbox
  files area) returns EINVAL -- runtime-downloaded .so plugins / hot updates / loading JIT output
  are not possible. limitation/ohos-runtime (loader specification, wontfix); alternative W-0010
  (ship .so files in the HAP lib directory / statically link a fixed set) is adopted; the Qt-side platform behavior record is
  T-0007 (QTBUG-146624).
---

# C-0012 The application loader refuses to load dynamic libraries from writable paths

> nature: limitation | responsible: ohos-runtime | status: wontfix | symptoms: S-0011 | workarounds: W-0010 | tickets: T-0007 | review: 2026-12-15

## Symptoms

### S-0011 Runtime dlopen of a .so from a writable path fails (errno=22 EINVAL)

The verbatim error (source page [runtime-fail-dlopen-writable-path](../problems/runtime-fail-dlopen-writable-path.md)):

```
dlopen failed: library "/data/storage/el2/100/base/files/plugins/libMyPlugin.so"
cannot open shared object file: errno=22 (EINVAL)
```

Or at the Qt level: `QPluginLoader: Could not load plugin: dlopen failed`.

Trigger scenarios: plugin systems (a .so downloaded to a writable directory and then loaded), JIT compilers (code generated at runtime,
written to a file and then loaded), hot update mechanisms (reloading after replacing a .so). The path comes from
`QStandardPaths::writableLocation()` (usually under `/data/storage/el2/`).

## Root cause / classification basis

HarmonyOS application sandbox loader specification: **dynamic library code can only be loaded from the native library
directory packaged in the HAP**; ordinary writable paths (the el2 sandbox files area) are not valid code loading paths, and `dlopen()`
returns EINVAL. This is a **platform limitation**, not a defect -- there is no fix path of "allowing loads from writable paths",
only deploying the code as specified.

- Specification evidence: the official Qt platform limitations page registers QTBUG-146624 (the `QPluginLoader` / runtime
  `.so` row, see [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)
  §Mapping platform limitations to Qt APIs; golden-rules rule P3);
- symptom evidence: the verbatim dlopen EINVAL error (source page, Qt 5.12/5.15 real devices);
- for general diagnosis, ohos-common-kb `dlopen-rejects-writable-path` is authoritative (holds across frameworks).

## Responsibility

`ohos-runtime` (loader security specification). Qt won't fix it -- QPluginLoader/dlopen keep their cross-platform
semantics, and returning failure faithfully reflects the platform behavior (registered on the Qt side as T-0007, not a fix request). Applications must adapt
to the specification (disposition: Must adapt for HarmonyOS).

## Alternatives and evolution (limitation)

- **W-0010 (adopted)**: ship plugin .so files as part of the final HAP's native library closure (deployed to the lib directory
  at packaging time); when the plugin set is fixed, link it statically into the main binary; dynamic logic that really must be delivered at runtime
  moves to ArkTS/JS scripts (see §Workarounds).
- **Evolution**: none (the specification is stable). Watch points: whether the platform opens a controlled runtime code loading mechanism
  (e.g. signature-verified dynamic modules); replies on T-0007.

## Workarounds

- **W-0010 (adopted, official adapter)**:
  1. deploy plugin .so files into the HAP's native library directory (the lib directory) at packaging time and ship them with the
     app -- no runtime download/replacement;
  2. fixed plugin set → static linking (removes the runtime loading step);
  3. logic that really must be delivered at runtime → use ArkTS/JS scripts instead of .so plugins.

  Cost: adding/updating a plugin requires repackaging and a new release, with no hot update capability; dynamic code forms are restricted.
  Retirement condition: not expected to retire (wontfix: the loader specification is stable); if the platform opens up code
  loading from writable areas, switch back to runtime download.

## Tickets

- **T-0007 (qt-bug, QTBUG-146624, submitted)**: Qt-side platform behavior record
  (the QPluginLoader / runtime .so dynamic plugin loading limitation; not a fix request); the ticket number comes from the official
  platform limitations page ([qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-03 | Qt 5.12/5.15 for HarmonyOS / real device | Recorded with the problems page: verbatim dlopen EINVAL error + platform limitation P3 classification (source page status: solved) | Classification holds; shipping in the lib directory works | → wontfix |

## Related

- Symptoms (S): S-0011
- Workarounds (W): W-0010
- Tickets (T): T-0007
- problems: [runtime-fail-dlopen-writable-path](../problems/runtime-fail-dlopen-writable-path.md) (searchable QPluginLoader symptoms, deployment location, regression method)
- semantic: [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md) (§Mapping platform limitations to Qt APIs), [qt-harmonyos-third-party-libs](../semantic/qt-harmonyos-third-party-libs.md) (§3 .so deployment rules), [qt-harmonyos-golden-rules](../semantic/qt-harmonyos-golden-rules.md) (rule P3)
- Related causes (C, including depends_on notes): C-0008 (the same application sandbox specification family -- C-0008 is about permissions/links being part of the packaging contract, this one is about the code loading path specification; parallel rules, no depends_on dependency)
