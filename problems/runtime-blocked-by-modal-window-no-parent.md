---
id: problem-runtime-blocked-by-modal-window-no-parent
type: problem
domain: runtime
tags: [blockedByModalWindow, QDialog, transientParent, qpa, syntheticParent, close-blocked, scroll-blocked, qt515, patch, qt, harmonyos, three-level-window, ohostemplate]
created: 2026-08-06
updated: 2026-08-06
status: solved
severity: high
audience: public
refs: [episodic-ohostemplate-blockedbymodal-patch, semantic-qt-harmonyos-window-model]
summary: >
  A parentless QDialog() on OHOS has its close() and wheel events blocked by blockedByModalWindow=1.
  Root cause: the OHOS QPA's syntheticParent fallback classifies the window as a SubWindow but never calls setTransientParent() to write that back to the Qt layer,
  so the isAncestorOf() check in isWindowBlocked() fails. Fix: have the QPA's showImmediate() write the transientParent back after the fallback.
leader_summary: >
  Identified and fixed the blockedByModalWindow root cause in the Qt source; the patch passed on-device verification and affects every parentless QDialog scenario
impact: [Framework support, Commercial response, Runtime troubleshooting]
deliverables: [problem record, patch, source analysis report]
evidence: [ohos-qt-patch-delivery, hilog verification logs]

error_message: >
  processCloseEvent: blockedByModal=1 -> close is not executed
  The window is still visible after QDialog close()
  Wheel events are blocked by processWheelEvent (the same blocked flag)
error_code: ""
keywords: [blockedByModalWindow, QDialog, transientParent, syntheticParent, won't close, won't scroll, three-level window, isWindowBlocked]
symptoms: "A QDialog won't close and won't scroll (both at once), especially in the matplotlib three-level window scenario"

environment: "OHOS + Qt 5.15.16 + ohostemplateforqtapplication"
---

# A parentless QDialog is blocked by blockedByModalWindow

## Error message

```
processCloseEvent: blockedByModal=1  (before the patch)
-> close() isn't executed, so the window can't be closed
-> processWheelEvent does if(blocked) return, so the wheel doesn't respond
```

## Scenario

The third-level QDialog created by matplotlib's NavigationToolbar -> Configure subplots -> SubplotToolQt -> Export values.
In `_export_values()`, the `QDialog()` has no parent. Any scenario with "a parentless QDialog plus a modal sibling window" can trigger this.

## Cause

The OHOS QPA's `determineViewTypeAndLogicalParent()` classifies a parentless Dialog as a SubWindow via the syntheticParent fallback,
**but never calls `QWindow::setTransientParent()` to write that back to the Qt layer**. When the Qt layer's `isWindowBlocked()` walks the parent chain via `isAncestorOf()`,
it finds transientParent is null and decides the window is "blocked by a modal sibling" -> blockedByModalWindow=1.

This shares a root-cause family with `ghost-window-dialog-close` (syntheticParent not written back to transientParent).

## Solution

A Qt source patch: have `showImmediate()` in `qohosview.cpp` write back `setTransientParent()` after the syntheticParent fallback.
See `episodic-ohostemplate-blockedbymodal-patch.md` for details.

```cpp
if (currentViewTypeInfo.viewType == SubWindow
    && currentViewTypeInfo.syntheticParent
    && m_ownerWindow->transientParent() == nullptr) {
    auto *tpWindow = currentViewTypeInfo.syntheticParent->qWindow();
    if (tpWindow && tpWindow != m_ownerWindow)
        m_ownerWindow->setTransientParent(tpWindow);
}
```

Temporary application-level workaround: change `QDialog()` to `QDialog(self)` + `WA_DeleteOnClose`.

## Notes

- The same problem exists on Win32 (the logic chain is identical), but the Win32 window manager's `GetActiveWindow()` owner mechanism covers for it at the system level
- The patch only takes effect in the syntheticParent fallback scenario; a QDialog with a parent is unaffected
- The same blocked flag affects both close and scroll, so fixing it resolves both problems at once

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Identified the blockedByModalWindow root cause in the Qt source; the patch passed on-device verification |
| Scope of impact | Every parentless QDialog scenario (matplotlib, multi-window applications, and so on) |
| Deliverables | problem record, patch, source analysis report |
| Evidence | The hilog verification chain |
| How to reuse | When a QDialog won't close and won't scroll, apply this patch directly |
