---
id: fault-C-0001
cid: C-0001
type: cause
title: The #ifdef chain in qqmlplatform os() lacks a Q_OS_OHOS branch
nature: defect
domain: api
fault_type: bug
responsible: qt-port
co_responsible: []
component: "qtdeclarative/src/qml/qml/qqmlplatform.cpp:59 (os())"
severity: high
evidence_type: source
status: workaround
fix_route: "Add the branch in upstream qtdeclarative → cherry-pick to the harmonyos branches"
review_note: "Whether the harmonyos branch / qtdeclarative already has a Q_OS_OHOS branch"
depends_on: []
affects_qt: ["Qt 5.12.12 (613336de)", "Qt 5.15.16 (962aa625)", "Qt 6.12 (same os() implementation)"]
affects_ohos: ["all versions (independent of system/API version)"]
qoh: []
first_seen: 2026-08-06
review_due: 2026-12-14
created: 2026-09-14
updated: 2026-09-14
tags: [qt, harmonyos, qml, platform, qqmlplatform, pluginName, workaround, bug]
audience: public
refs: [semantic-qt-harmonyos-api, semantic-qt-harmonyos-platform-limits]
summary: >
  The #ifdef chain in qqmlplatform.cpp os() lacks a Q_OS_OHOS branch, while qsystemdetection.h defines both
  Q_OS_OHOS and Q_OS_LINUX, so Qt.platform.os returns "linux" on HarmonyOS. defect/qt-port;
  workaround W-0001 is verified (check pluginName/productType) and can be retired once the upstream fix lands.
---

# C-0001 qqmlplatform os() lacks a Q_OS_OHOS branch

> nature: defect | responsible: qt-port | status: workaround | symptoms: S-0001 | review: 2026-12-14

## Symptoms

### S-0001 QML platform guard silently fails (Qt.platform.os returns "linux")

```qml
Qt.platform.os === "ohos"    // false (on HarmonyOS, os returns "linux")
Qt.platform.os === "linux"   // true, but can't tell HarmonyOS apart from desktop Linux
```

QML code that uses `Qt.platform.os` as a HarmonyOS platform guard **silently has no effect** (no error at all).
On the same platform, `QSysInfo::productType()` returns `"ohos"` -- Qt contradicts itself internally.
Indirectly affected: the `QFileSelector` platform selectors that rely on the `os === "linux"` branch.

## Root cause / classification basis (source-level, confirmed)

- `qsystemdetection.h:115-117`: `__OHOS__` defines both `Q_OS_OHOS` **and** `Q_OS_LINUX`
  (the same pattern as Android);
- the `#ifdef` chain of `os()` in `qqmlplatform.cpp:59` **lacks a `Q_OS_OHOS` branch** → it hits
  `Q_OS_LINUX → "linux"`;
- for comparison: `productType()` in `qglobal.cpp:2718` has a `Q_OS_OHOS` branch → returns `"ohos"`.

## Responsibility

`qt-port` -- the platform macro combination introduced by the HarmonyOS port is not covered by qtdeclarative's platform enumeration. The fix must first go to
upstream qtdeclarative, then be cherry-picked with the harmonyos branches into each Qt OHOS version.

## Permanent fix (defect)

In `os()`, **before** the `Q_OS_LINUX` branch, add:

```cpp
#elif defined(Q_OS_OHOS)
    return QStringLiteral("ohos");
```

Behavior change ("linux"→"ohos"): it affects code relying on `os === "linux"` and QFileSelector,
so release notes must call it out; it applies to Qt6 as well (same `os()` implementation).

## Workarounds

- **W-0001 (adopted, verified 2026-08-06)**: in QML use
  `readonly property bool isHarmony: Qt.platform.pluginName === "ohos"` (the QPA plugin
  key); in C++ use `QSysInfo::productType() == "ohos"` or compile-time `#ifdef Q_OS_OHOS`
  (most reliable).

  ⚠️ `pluginName` depends on the QPA plugin loaded at runtime; the value changes in test environments such as `-platform offscreen`.

  Retirement condition: once the upstream fix lands in the Qt OHOS SDK in use, switch the `pluginName` check back to
  `Qt.platform.os === "ohos"`.

## Tickets

- None yet (not reported). The root cause and suggested patch material are complete (see
  [qt-harmonyos-api](../semantic/qt-harmonyos-api.md)); after filing per
  `procedural/qt-bug-report-generation.md`, register T-xxxx here.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-08-06 | Qt 5.15.16 (962aa625) | Source verification of qqmlplatform.cpp / qsystemdetection.h / qglobal.cpp | Missing branch confirmed; pluginName/productType alternatives work | → workaround |

## Related

- Symptoms (S): S-0001
- Workarounds (W): W-0001
- Tickets (T): none yet
- semantic: [qt-harmonyos-api](../semantic/qt-harmonyos-api.md) (full analysis of platform detection),
  [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)
