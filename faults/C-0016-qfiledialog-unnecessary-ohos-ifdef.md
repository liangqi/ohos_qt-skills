---
id: fault-C-0016
cid: C-0016
type: cause
title: "The app wrongly assumes QFileDialog has no native OHOS support and adds an #ifdef alternative branch (QOhosPlatformIntegrationPlugin actually has it built in)"
nature: defect
domain: api
fault_type: caveat
responsible: app
co_responsible: []
component: "QOhosPlatformIntegrationPlugin (libqohos.so, registers fileManagerService via OhosExportModules.ts) × application-side QFileDialog guard code"
severity: low
evidence_type: source
status: closed
fix_route: "Change the usage: use the standard QFileDialog API directly and delete the #ifdef Q_OS_OHOS alternative branch"
review_note: "Thin C page (app usage issue): check that the FRequest fix conclusion and the two boundaries (saves inside the sandbox are invisible to the system file manager; file:// is not supported by QDesktopServices::openUrl) are still maintained in the problems page; the source page records no Qt/OHOS version, no version tracking needed"
depends_on: []
affects_qt: []
affects_ohos: []
qoh: []
first_seen: 2026-07-29
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [qfiledialog, file-dialog, native-support, qohosplatformplugin, ifdef, anti-pattern, app-usage, qt515]
audience: public
refs: [problem-ohos-qfiledialog-native-support, semantic-qt-harmonyos-api-mapping]
summary: >
  The developer wrongly assumed QFileDialog is unavailable on OHOS and added
  Q_OS_OHOS guards and alternative branches for Save/Load/Download; in fact the platform plugin has a built-in native file dialog and the standard API
  can be used directly. defect/app (Application usage issue); FRequest fixed it by changing the usage, closed,
  no W/T.
---

# C-0016 Wrongly assuming QFileDialog has no native OHOS support (application misuse)

> nature: defect | responsible: app | status: closed | symptoms: S-0015 | workarounds: none (changing the usage is the permanent fix) | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0015 Mistakenly adding a Q_OS_OHOS alternative branch for QFileDialog (the guard conflicts with the built-in native support)

When porting a Qt app to OHOS, the developer wrongly assumed OHOS doesn't support `QFileDialog` and added
`#ifdef Q_OS_OHOS` alternative branches for the Save/Load/Download features (a `QInputDialog`
to enter the file name, hard-coded paths, etc.), creating unnecessary maintenance burden and conflicting with the platform plugin's built-in native
support. In fact the standard `QFileDialog` API can be used directly on OHOS.

## Root cause / classification basis

`QOhosPlatformIntegrationPlugin` (libqohos.so) has built-in native file dialog support:
internally it calls the OHOS native file manager API through
`@kit.FileManagerServiceKit.fileManagerService`, registered via `OhosExportModules.ts`,
completely transparent to the Qt Widgets code above. This is **application misuse** (the API semantics are statically decidable;
source-level evidence), not a missing framework feature -- no defect on the Qt side and no specification gap on the platform side.

## Responsibility

`app`: the platform capability exists but the application didn't use it (it built its own alternative branch after a wrong assumption); the fix route =
change your own code. The in-depth content (verification method, wrong-vs-right comparison, sandbox visibility boundaries) stays in
[ohos-qfiledialog-native-support](../problems/ohos-qfiledialog-native-support.md);
this page only records the conclusion that "this is not a framework problem".

## Permanent fix (defect)

Change the usage: delete the `#ifdef Q_OS_OHOS` guard and use the standard QFileDialog API directly
(`getSaveFileName` / `getOpenFileName`); the `FILE_ACCESS_PERSIST` permission in module.json5
is preset by the Qt template; no ArkTS bridge and no NAPI layer are needed.

| Wrong approach | Right approach |
|----------|----------|
| `#ifdef Q_OS_OHOS` + QInputDialog to enter the file name | Use QFileDialog directly |
| `#ifdef Q_OS_OHOS` + hard-coding to getAppPath() | Use QFileDialog directly |
| `#ifdef Q_OS_OHOS` + QStandardPaths::DocumentsLocation | Use QFileDialog directly (DocumentsLocation doesn't exist on OHOS) |

## Workarounds

None -- changing the usage is the permanent fix; no bypass is needed.

## Tickets

None yet (not a framework problem; nothing to track upstream).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-09-15 | Not recorded | Transcribed when recording the problems page (source page created 2026-07-29 / updated 2026-08-03): ModbusDebuger verified using the standard API directly; FRequest (com.ohosqt.FRequest) removed all unnecessary QFileDialog OHOS guards | Classification holds; the problem is gone after changing the usage | → closed |

## Related

- Symptoms (S): S-0015
- Workarounds (W): none
- Tickets (T): none yet
- problems: [ohos-qfiledialog-native-support](../problems/ohos-qfiledialog-native-support.md)
- semantic: [qt-harmonyos-api-mapping](../semantic/qt-harmonyos-api-mapping.md)
- Related causes (C): none
