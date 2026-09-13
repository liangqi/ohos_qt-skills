---
id: episodic-toolwindow-crossscreen-flicker
type: episodic
domain: postmortem
tags: [bug, window, cross-screen, flicker, system-issue, moveWindowToGlobalDisplay, resizeAsync, ohos-window]
created: 2026-06-05
updated: 2026-06-05
status: active
audience: public
refs: [semantic-qt-harmonyos-window-model]
summary: >
  Analysis of the ToolWindow cross-screen flicker system issue: moveWindowToGlobalDisplay conflicts with resizeAsync during cross-screen dragging,
  screenIdChanged only fires when the drag ends, and Qt traced the full call chain to the root cause and attributed it to the HarmonyOS system interface.
---

# ToolWindow cross-screen flicker — system issue analysis

> Commercial Qt report: dragging the MainWindow title bar across screens makes Qt::Tool child windows flicker.
> The system issue verification workflow was executed in full.

---

## Problem overview

| Item | Details |
|------|---------|
| Report source | A commercial Qt problem report |
| Symptom | The ToolWidget flickers while dragging the MainWindow across screens |
| Trigger conditions | A multi-screen device + dragging the title bar + a Qt::Tool child window |
| Attribution | **The HarmonyOS system interface** |
| Delivery path | `<WORK_DIR>/toolwindow-crossscreen-flicker/` |
| Reproduction demo | `<INTERNAL_DEMO>` |

## Full call chain

```
MainWindow::moveEvent()
  → updateToolWidget()
    → m_toolWidget->setGeometry(rect)
      → QOhosFloatingWindow::setGeometry(rect)        [qohosfloatingwindow.cpp:44]
        → view->setPosition(topLeft)                  [line 68]
          → QOhosView::setSystemUpdateProperty(position)  [batched]
          → flush → updateWindowPosition()            [qohosview.cpp:810]
            → m_ohosWindowProxy->moveWindowToGlobalOrGlobalDisplay()  [qohoswindowproxy.cpp:372]
              → "moveWindowToGlobalDisplay(x, y)"     [line 434, Promise]
        → view->setSize(size)                         [line 70]
          → QOhosView::setSystemUpdateProperty(size)  [batched]
          → flush → updateWindowSize()                [qohosview.cpp:801]
            → m_ohosWindowProxy->setSize()            [qohoswindowproxy.cpp:442]
              → "resizeAsync(w, h)"                   [line 452, Promise]
```

## Root cause

In `QOhosFloatingWindow::setGeometry`, Qt calls both `setPosition` and `setSize`, and QOhosView's batching mechanism (`setSystemUpdateProperty` + `flushSystemPropertyUpdatesImmediate`) flushes them to the system interface together.

In the cross-screen dragging scenario:
- `moveWindowToGlobalDisplay` triggers the window's migration to another screen
- `resizeAsync` executes while the window is migrating between screens
- The rendering of these two asynchronous operations conflicts in a cross-screen context → **flicker**

## Key evidence

1. **Suppressing resizeAsync makes the flicker disappear** (the window size never actually changes)
2. screenIdChanged only fires when the drag ends (Qt doesn't dispute this)
3. Qt confirmed that setPosition and setSize are batched at the QOhosView layer

## Log evidence (captured after building and installing libqohos.so)

**The full call sequence for each moveEvent**:
```
setGeometry: win=0x5a1f8f2b80 pos=(1888,743) size=476x203 isToolWindow=11
flush: updateWindowSize win=0x5a1f8f2b80 size=476x203
WindowProxy::setSize 476,203 proxyType=2
JS-CALL: resizeAsync(476,203)                    ← called every time, even when the size hasn't changed
flush: updateWindowPosition win=0x5a1f8f2b80 pos=(1888,743) hasDisplayId=0
WindowProxy::moveToGlobal 1888,743 displayId=-1.000000 proxyType=2
JS-CALL: moveWindowToGlobalDisplay(1888,743)      ← after the resize
```

**Key findings**:
- The window size 476×203 **never changes** throughout the drag
- Yet every moveEvent triggers `resizeAsync` (10+ redundant calls)
- The order is fixed: `resizeAsync` → `moveWindowToGlobalDisplay`
- User-verified: **the flicker disappears entirely when resizeAsync isn't called**

## Root cause confirmation

**A system interface problem**: HarmonyOS's `moveWindowToGlobalDisplay` and `resizeAsync` cannot guarantee rendering atomicity during cross-screen dragging.

Qt framework behavior:
1. The `QOhosView` batching mechanism works correctly — position and size are emitted in the same flush
2. `QOhosFloatingWindow::setGeometry` unconditionally calls `setPosition` + `setSize` every time
3. That is a reasonable framework design — it keeps the window state in sync with the system

System-side behavior:
1. Receiving `resizeAsync` triggers a window repaint/animation
2. `moveWindowToGlobalDisplay` immediately after triggers the cross-screen migration
3. The rendering of the two asynchronous operations can't complete within the same frame → **an intermediate state causes the flicker**

## Attribution

🔴 **A HarmonyOS system interface problem** (not a Qt framework bug)

Qt's `setSize` call is necessary (it keeps window state in sync) and shouldn't be skipped. The problem is that the system side can't execute resize + move atomically.

## Pure-HarmonyOS on-device verification (2026-06-05)

On a dual-screen **HUAWEI MateBook Fold | ULTIMATE DESIGN**, pure ArkTS code (with no Qt involved) reproduced exactly the same flicker.

**Implementation**: `setInterval(50ms)` polls the main window's position for changes → calls `subWindow.moveWindowTo()` and `subWindow.resize()` together

| Operation | Result |
|-----------|--------|
| `moveWindowTo` + `resize` called together | **The child window flickers** ✅ reproduced |
| Only `moveWindowTo`, without `resize` | **The child window doesn't flicker** |

**Conclusion**: the problem is at the HarmonyOS system level and unrelated to the Qt framework.

## Reusable lessons

1. **Batching is not atomicity**: Qt batches at the QOhosView layer (both operations flush together), but the system side doesn't guarantee atomicity across two asynchronous operations
2. **Redundant calls are the trigger**: even when the size hasn't changed, `setSize` still triggers `resizeAsync`; this "harmless" redundant call becomes the trigger in a cross-screen scenario
3. **Cross-screen scenarios are special**: many window operations behave fine on a single screen but become unpredictable across screens (while the window is migrating)
4. **screenIdChanged fires late**: it doesn't fire during the drag, which means Qt has no way of knowing which screen the window is currently on while dragging
5. **⚠️ Don't rush to modify the Qt framework**: when you suspect a system problem, first evaluate whether the system interface itself behaves correctly rather than changing Qt code first. Any framework change must have its blast radius carefully assessed (for example, skipping setSize could make the initial size wrong)

## Related context

- System issue verification — the workflow used for this problem
- [[qt-harmonyos-window-model]] — Understanding the window model
- The Qt framework analysis methodology
