---
id: fault-C-0009
cid: C-0009
type: cause
title: The OHOS QPA syntheticParent fallback doesn't write back transientParent, so a QDialog without a parent is wrongly blocked by blockedByModalWindow
nature: defect
domain: runtime
fault_type: bug
responsible: qt-port
co_responsible: []
component: "Qt 5.15.16 OHOS QPA qohosview.cpp (determineViewTypeAndLogicalParent / syntheticParentForQWindowOrNull / showImmediate) × qguiapplication.cpp isWindowBlocked()"
severity: high
evidence_type: logs
status: workaround
fix_route: "Upstream merges the qohosview.cpp patch in which showImmediate() writes back setTransientParent() (about 8 lines); arrives with the harmonyos-5.15.16 branch / the next Qt OHOS SDK"
review_note: "Check whether the harmonyos-5.15.16 branch has merged the transientParent write-back; if not, file a ticket per qt-bug-report-generation (first add a single-file main.cpp minimal demo: a QDialog without a parent + a modal sibling window); W-0007 must be reapplied on kit updates"
depends_on: []
affects_qt: ["Qt 5.15.16 (tqtc/harmonyos-5.15.16, patch baseline commit not recorded)"]
affects_ohos: ["real device (system version not recorded)"]
qoh: [QOH029]
first_seen: 2026-08-04
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [qt, harmonyos, qpa, blockedByModalWindow, QDialog, transientParent, syntheticParent, window, close-blocked, scroll-blocked, matplotlib, workaround, bug]
audience: public
refs: [problem-runtime-blocked-by-modal-window-no-parent, episodic-ohostemplate-blockedbymodal-patch, semantic-qt-harmonyos-window-model]
summary: >
  The OHOS QPA uses a syntheticParent fallback to classify a Dialog without a parent as a SubWindow and establishes ownership at the ArkUI
  layer, but never calls setTransientParent() to write it back to the Qt layer, so the isAncestorOf() check in isWindowBlocked()
  fails and blockedByModalWindow=1 intercepts both close() and the mouse wheel. defect/
  qt-port; a local patch (write-back in showImmediate, about 8 lines) is verified on a real device (W-0007); no tracking ticket yet.
---

# C-0009 OHOS QPA syntheticParent doesn't write back transientParent

> nature: defect | responsible: qt-port | status: workaround | symptoms: S-0008 | workarounds: W-0007 | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0008 A QDialog without a parent cannot be closed and ignores the mouse wheel

- `processCloseEvent: blockedByModal=1` → close() doesn't run and the window can't be closed (a ghost window remains);
- wheel events are intercepted by the same blocked flag (`processWheelEvent if (blocked) return`), so it can't scroll -- **close and scroll failing together** is the distinguishing feature of this symptom;
- typical scenario: the third-level `QDialog()` created by matplotlib NavigationToolbar → Configure subplots → SubplotToolQt → Export values (`_export_values()` has no parent); any "QDialog without a parent + an existing modal sibling window" scenario can trigger it.

## Root cause / classification basis (source-level + device hilog, confirmed)

The root cause chain:

```
QDialog() without a parent
  → at the Qt layer, QWindow::transientParent() == nullptr
  → the OHOS QPA determineViewTypeAndLogicalParent() classifies it as SubWindow via the syntheticParent fallback
  → syntheticParent is passed to createSubWindow (ownership established at the ArkUI layer)
  → the OHOS QPA never calls QWindow::setTransientParent() to write it back to the Qt layer (zero calls in qohosview.cpp)
  → the Qt layer's transientParent stays null
  → the isAncestorOf() check in isWindowBlocked() fails
  → blockedByModalWindow = 1
  → processCloseEvent() if (blocked) return → close doesn't run (the wheel is intercepted by the same flag)
```

Key source locations: `qohosview.cpp:252-261` (`syntheticParentForQWindowOrNull()`), `qohosview.cpp:390-471` (`tryCreateWindowProxyIfNeeded()`), `qguiapplication.cpp:899-958` (`isWindowBlocked()`).

Device verification (hilog, before/after the patch):

- before the patch: `processCloseEvent: blockedByModal=1`, close() unreachable, the window remains;
- after the patch (the 17:39 verification chain): `blockedByModal=0` → `closeEvent sent, accepted=1` → `close() returned=1 proxyAfter=0`, the window is destroyed correctly.

Platform comparison: on Win32 the blockedByModalWindow logic chain is the same, but the window manager's `GetActiveWindow()` owner mechanism masks the problem as a fallback at the system layer; OHOS has no such fallback, so Qt must maintain the transientParent relationship itself in the QPA layer.

Evidence form: `logs` (source location + hilog device verification chain); **no minimal repro demo** -- before filing upstream, add a single-file main.cpp per the seven demo principles (a QDialog without a parent + a modal sibling window + numbered repro steps).

## Responsibility

`qt-port` -- the defect is in the Qt OHOS platform plugin (libqohos QPA): the syntheticParent fallback only establishes ownership at the ArkUI layer and doesn't write back the Qt layer's transientParent, an incomplete implementation in the adaptation layer. Fix route: merged into the harmonyos-5.15.16 branch / the next Qt OHOS SDK.

## Permanent fix (defect)

In `qohosview.cpp`, have `showImmediate()` write back transientParent after the syntheticParent fallback (the smallest-change, lowest-risk of the three candidates, about 8 lines):

```cpp
if (currentViewTypeInfo.viewType == SubWindow
    && currentViewTypeInfo.syntheticParent
    && m_ownerWindow->transientParent() == nullptr) {
    auto *tpWindow = currentViewTypeInfo.syntheticParent->qWindow();
    if (tpWindow && tpWindow != m_ownerWindow)
        m_ownerWindow->setTransientParent(tpWindow);
}
```

The 10-scenario risk assessment passed (QDialogs with a parent are skipped, ToolTip/Popup are unaffected, repeated showImmediate calls have no negative effects, lastWindowClosed behavior is safer, etc.); the full assessment is in the episodic postmortem. The alternatives (rewriting isAncestorOf, about 20 lines / changing the shared Qt GUI kernel code, about 10 lines) are riskier and not recommended.

## Workarounds

- **W-0007 (adopted, verified 2026-08-06 on a real device)**: rebuild libqohos.so with the patch above and replace it in the kit / deploy it to the target project (the deliverable includes the patch, libs and template; see the episodic postmortem).
  Cost: every Qt kit update requires re-applying the patch and rebuilding.
  Retirement condition: once the upstream harmonyos branch merges the transientParent write-back, go back to the official kit, drop the local rebuild and rerun the three-level window close test.
- Application-layer alternative (no separate W, not verified): change `QDialog()` to `QDialog(self)` + `WA_DeleteOnClose` -- requires changing every dialog construction site, and can't reach QDialogs without a parent created inside third-party libraries (matplotlib, etc.); only applicable where you control the code.

## Tickets

- None yet (no evidenced ticket number). The patch exists and was assessed as submittable to tqtc, but there is no record of submission; before filing, add a minimal demo (single-file main.cpp + numbered repro steps) per the reproducibility HARD gate of `procedural/qt-bug-report-generation.md`.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-08-04 | Qt 5.15.16 / OHOS real device (ohostemplate, matplotlib three-level windows) | hilog (43844 lines) analysis: the three-level window close chain breaks at `onSubWindowCloseHandler: calling close()` | Confirmed close is intercepted at the Qt layer; moved on to source analysis | → open |
| 2026-08-06 | Qt 5.15.16 / OHOS real device (ohostemplate) | Rebuilt and deployed the `showImmediate()` transientParent write-back patch; hilog 17:39 verification chain | blockedByModalWindow 1→0, closeEvent accepted=1, close()=1, proxy destroyed | → workaround |

(Sources for the historical facts: the [ohostemplate-blockedbymodal-patch](../episodic/postmortems/ohostemplate-blockedbymodal-patch.md) postmortem and [runtime-blocked-by-modal-window-no-parent](../problems/runtime-blocked-by-modal-window-no-parent.md); when the editor merges, register the review reproduction in the first row of this table per the gate.)

## Related

- Symptoms (S): S-0008
- Workarounds (W): W-0007
- Tickets (T): none yet
- problems: [runtime-blocked-by-modal-window-no-parent](../problems/runtime-blocked-by-modal-window-no-parent.md)
- episodic: [ohostemplate-blockedbymodal-patch](../episodic/postmortems/ohostemplate-blockedbymodal-patch.md) (option comparison, 10-scenario risk assessment, deployment record)
- semantic: [qt-harmonyos-window-model](../semantic/qt-harmonyos-window-model.md) §Known Gap (QPA syntheticParent doesn't write back transientParent)
- QOH (machine layer): QOH029 (dialog_blocked_no_parent)
- Related causes (C): none (the "same root-cause family" ghost-window-dialog-close mentioned in the problem page has no page of its own in the KB; only that page mentions itself across the repo)
