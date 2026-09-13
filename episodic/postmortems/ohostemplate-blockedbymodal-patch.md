---
id: episodic-ohostemplate-blockedbymodal-patch
type: episodic
domain: postmortem
tags: [bug, blockedByModalWindow, QDialog, transientParent, qpa, syntheticParent, three-level-window, ohostemplate, matplotlib, qt515, patch, qt, harmonyos]
created: 2026-08-06
updated: 2026-08-06
status: active
audience: public
refs: [semantic-qt-harmonyos-window-model, problem-runtime-blocked-by-modal-window-no-parent]
summary: >
  In ohostemplate, matplotlib's third-level window (Configure subplots -> Export values) can't be closed. Root cause: a parentless QDialog is
  classified as a SubWindow through the syntheticParent fallback, but the OHOS QPA never calls setTransientParent() to write that back to the Qt layer,
  so blockedByModalWindow=1 blocks close(). Qt source fix: showImmediate() writes the transientParent back after the fallback
  (about 8 lines in qohosview.cpp); device logs confirm blockedByModalWindow=0 and close()=1.
  Also found and fixed the ArkTS template version mismatch crash (modules -> modulesFactories).
leader_summary: >
  Fixed the "third-level window won't close" problem (blockedByModalWindow) at the Qt source level; the patch passed on-device verification and produced a source patch that can be submitted to tqtc
impact: [Framework support, Commercial response]
deliverables: [patch, source analysis report, risk assessment, delivery directory]
evidence: [ohos-qt-patch-delivery, the 17:39 hilog verification chain]
---

# ohostemplate blockedByModalWindow — a Qt source fix

> In ohostemplate, matplotlib's third-level window (Configure subplots -> SubplotToolQt -> Export values) can't be closed.
> The root cause of `blockedByModalWindow` was fixed at the Qt source level and verified with device logs.

## 1. Background

Analysis on 08-04 found that matplotlib's `_export_values()` creates a `QDialog()` with no parent, which goes through the syntheticParent fallback and is classified as a SubWindow.
Line 43844 of the hilog confirmed that when closing the third-level window, the chain breaks at `onSubWindowCloseHandler: calling close()`.

On 08-06 we moved to the Qt source level and found that the real root cause isn't "close isn't executed" but that **the Qt layer's blockedByModalWindow mechanism blocks close outright**.

## 2. The root cause chain (evidenced in the source)

```
QDialog() with no parent
  -> at the Qt layer, QWindow::transientParent() == nullptr
  -> the OHOS QPA's determineViewTypeAndLogicalParent() classifies it as a SubWindow via the syntheticParent fallback
  -> syntheticParent is passed to createSubWindow (establishing ownership at the ArkUI layer)
  -> the OHOS QPA never calls QWindow::setTransientParent() to write it back to the Qt layer
  -> at the Qt layer, transientParent is still null
  -> the isAncestorOf() check in isWindowBlocked() fails
  -> blockedByModalWindow = 1
  -> processCloseEvent() does if (blocked) return -> close isn't executed
```

### Key source locations

| File | Lines | Code | Role |
|------|-------|------|------|
| qohosview.cpp | 252-261 | `syntheticParentForQWindowOrNull()` | The fallback that finds a syntheticParent |
| qohosview.cpp | 390-471 | `tryCreateWindowProxyIfNeeded()` | Creates the ArkUI subWindow using syntheticParent |
| qguiapplication.cpp | 899-958 | `isWindowBlocked()` | Walks the parent chain to decide whether it's blocked |

### Win vs. OHOS comparison (correcting the 08-04 misunderstanding)

The earlier 08-04 analysis claimed "Win32 matches the parent automatically", which is **wrong**. In reality:
- Win32's `CreateWindowEx(parent=NULL)` sets owner=GetActiveWindow() automatically, but the owner doesn't enter Qt's parent chain
- The blockedByModalWindow logic chain is **identical** on both sides
- The only real difference: the Win32 window manager has a safety net, and OHOS doesn't

## 3. The fix

### Choosing an approach (1 of 3)

| Option | Change | Risk | Recommended |
|--------|--------|------|-------------|
| 1. Have the OHOS QPA's showImmediate write back transientParent | About 8 lines in qohosview.cpp | Low | **Recommended** |
| 2. Override isAncestorOf in the OHOS QPA | About 20 lines in qohosplatformwindow.cpp | Medium | No |
| 3. Add an OHOS condition to the Qt GUI kernel's processCloseEvent | About 10 lines in qguiapplication.cpp | High (touches shared code) | No |

### Option 1's code

```cpp
// [OHOS FIX] After syntheticParent fallback, reflect to Qt transientParent
if (currentViewTypeInfo.viewType == SubWindow
    && currentViewTypeInfo.syntheticParent
    && m_ownerWindow->transientParent() == nullptr) {
    auto *tpWindow = currentViewTypeInfo.syntheticParent->qWindow();
    if (tpWindow && tpWindow != m_ownerWindow)
        m_ownerWindow->setTransientParent(tpWindow);
}
```

### Option 1 risk assessment (10 scenarios)

| Scenario | Result | Notes |
|----------|--------|-------|
| QDialog(this) with a parent | Skipped | The condition doesn't hold (transientParent already set) |
| QDialog() with no parent | **The target case** | transientParent==null, so it gets set |
| ToolTip/Popup | Unaffected | popupType is excluded |
| An ordinary QWindow | Skipped | Not in the fallback list |
| The first window | Skipped | syntheticParent==null |
| A tag window | No downside | The write-back is consistent |
| showImmediate called multiple times | No downside | The condition doesn't hold the second time |
| lastWindowClosed | Safer | The behavior change only affects the anti-pattern |

## 4. On-device verification (the 17:39 logs)

### The key log evidence chain

```
17:39:37  Window WIID_4 - subWindowOf tag=0x0   <- the third-level window is created
17:39:39  onSubWindowCloseHandler: calling close()
17:39:39  processCloseEvent: blockedByModal=0    <- the patch is working
17:39:39  processCloseEvent: closeEvent sent, accepted=1
17:39:39  close() returned=1 proxyAfter=0        <- the window is destroyed correctly
```

### Before vs. after the patch

| Metric | Before | After |
|--------|--------|-------|
| blockedByModalWindow | 1 | 0 |
| processCloseEvent | if(blocked) return | Sends the CloseEvent |
| close() return value | Unreachable | 1 |
| Window destruction | Ghost window | The proxy is destroyed |

## 5. Additional findings during deployment

1. **ArkTS template mismatch**: the newly built libqohos.so reads the `modulesFactories` property while the old project passes `modules`, crashing at startup. Replacing 19 .ets/.ts files fixed it.
2. **hvigor CLI packaging crash**: a HAP packaged from the command line reports `Cannot read property handleAbilityStageOnCreate of undefined` on launch. Reverting to an unpatched `.so` crashes too, so it's not a patch problem — it's a difference between CLI and IDE packaging.
3. **The import lazy syntax**: requires adding `compatibleSdkVersionStage: "beta3"` to build-profile.json5.

## 6. Deliverables

- patch: `0001-OHOS-Reflect-syntheticParent-to-transientParent.patch`
- README.md (deployment guide)
- libs/ (libqohos.so + 57 Qt5 .so files)
- template/ (19 ArkTS template files)

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Fixed the "third-level window won't close" problem at the Qt source level; the patch passed on-device verification and can be submitted to tqtc |
| Scope of impact | Framework support (every parentless QDialog scenario), plus Python-embedding applications such as matplotlib |
| Deliverables | patch, source analysis report, risk assessment, delivery directory |
| Evidence | The hilog verification chain, and the ohos-qt-patch-delivery directory |
| How to reuse | Apply this patch directly when a QDialog won't close or won't scroll |
