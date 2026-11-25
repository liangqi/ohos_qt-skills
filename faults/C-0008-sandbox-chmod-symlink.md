---
id: fault-C-0008
cid: C-0008
type: cause
title: The application sandbox forbids runtime chmod/symlink (file permissions and links are part of the packaging contract, not a runtime capability)
nature: limitation
domain: filesystem
fault_type: gap
responsible: ohos-runtime
co_responsible: []
component: "HarmonyOS application sandbox filesystem specification × QFile::setPermissions / QFile::link"
severity: medium
evidence_type: docs
status: wontfix
evidence: "Application sandbox specification: file permissions and links are part of the packaging contract (QTBUG-146619/146621 record the platform behavior)"
evolution: "— (the specification is stable, no evolution direction; if the platform opens up the capability in the future, reclassify at review)"
fix_route: ""
review_note: "Whether the sandbox specification has changed (reclassify if chmod/symlink become available)"
depends_on: []
affects_qt: []
affects_ohos: ["all versions (sandbox specification)"]
qoh: []
first_seen: 2026-06-02
review_due: 2026-12-14
created: 2026-09-14
updated: 2026-09-14
tags: [harmonyos, sandbox, chmod, symlink, qfile, filesystem, limitation, workaround]
audience: public
refs: [semantic-qt-harmonyos-platform-limits]
summary: >
  The application sandbox forbids chmod and symlink creation at runtime: QFile::setPermissions returns failure for existing files,
  and QFile::link can't create the links the application needs. limitation/ohos-runtime (by specification, it won't be "fixed";
  wontfix); alternatives W-0005 (expand real files at build time) / W-0006 (hand permissions to the packaging contract) are adopted.
---

# C-0008 The sandbox forbids runtime chmod/symlink

> nature: limitation | responsible: ohos-runtime | status: wontfix | symptoms: S-0007 | review: 2026-12-14

## Symptoms

### S-0007 chmod / symlink fails at runtime

- `QFile::setPermissions()` returns failure for existing files;
- `QFile::link()` can't create the links the application needs.

Desktop-style code that relies on changing permissions/creating links at runtime takes the error branch on HarmonyOS (if the return value is treated as a business success
condition, it misjudges failure or even crashes -- see the sandbox-related entries in problems).

## Root cause / classification basis

HarmonyOS application sandbox specification: file permissions and links are part of the **packaging contract** (decided at build/HAP packaging time),
not a runtime capability -- the runtime filesystem doesn't offer chmod/symlink semantics. Tracked by Qt:
QTBUG-146619 (setPermissions, T-0003), QTBUG-146621 (link, T-0004).
This is a **platform limitation**, not a defect -- there is no path to "fixing chmod".

## Responsibility

`ohos-runtime` (sandbox specification). Qt won't fix it (the API keeps its cross-platform semantics; returning failure faithfully reflects the platform behavior).

## Alternatives and evolution (limitation)

- **W-0005 (adopted)**: expand real files at build/packaging time -- where a "link" effect is needed,
  expand it into a real file copy at build/packaging time, avoiding runtime link creation;
- **W-0006 (adopted)**: hand permissions to the packaging contract -- don't use the result of `setPermissions()` as a business success
  condition; declare the permissions the application needs in module.json5 / the packaging configuration;
- **Evolution**: none (the specification is stable; if the platform opens up the capability in the future, reclassify at review).

## Workarounds

These are the alternatives W-0005 / W-0006 (see above). **Not expected to retire** (wontfix: long-term reliance on the alternatives).

## Tickets

- **T-0003 (qt-bug, QTBUG-146619, submitted)**: records the QFile::setPermissions platform behavior;
- **T-0004 (qt-bug, QTBUG-146621, submitted)**: records the QFile::link platform behavior;
- both are registrations on the Qt side (not fix requests); see
  [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)
  §Mapping platform limitations to Qt APIs.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-02 | — | Recorded with the platform-limits page (Qt official wiki platform limitations + QTBUG) | Classification holds; alternatives work | → wontfix |

## Related

- Symptoms (S): S-0007
- Workarounds (W): W-0005, W-0006
- Tickets (T): T-0003, T-0004
- semantic: [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)
