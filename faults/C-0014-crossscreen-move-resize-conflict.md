---
id: fault-C-0014
cid: C-0014
type: cause
title: The ohos window APIs moveWindowToGlobalDisplay × resizeAsync have no rendering atomicity during cross-screen migration (a redundant resize becomes the flicker trigger)
nature: defect
domain: render
fault_type: bug
responsible: ohos-runtime
co_responsible: []
component: "HarmonyOS window APIs moveWindowToGlobalDisplay × resizeAsync (cross-screen drag scenario)"
severity: medium
evidence_type: both
status: diagnosed
fix_route: "The system side guarantees rendering atomicity of move+resize during cross-screen migration (or provides an atomic window geometry update API), arriving with a system OTA / new API version; no route until a ticket is filed"
review_note: "Calibrate severity (commercial Qt feedback, always reproduces on multi-screen); file a ticket with Huawei (no ticket number yet; the demo+log material is ready); system version improvements to cross-screen move+resize atomicity; whether W-0012 gets promoted"
depends_on: []
affects_qt: ["not recorded (the source page only records collecting logs from an instrumented libqohos.so rebuild; kit version not recorded)"]
affects_ohos: ["not recorded (evidenced on a HUAWEI MateBook Fold dual-screen real device; system version not recorded)"]
qoh: []
first_seen: 2026-06-05
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [qt, harmonyos, window, cross-screen, flicker, toolwindow, moveWindowToGlobalDisplay, resizeAsync, multi-display, system-defect]
audience: public
refs: [episodic-toolwindow-crossscreen-flicker, semantic-qt-harmonyos-window-model]
summary: >
  During a cross-screen drag, the two asynchronous HarmonyOS operations moveWindowToGlobalDisplay (which triggers the screen migration) and resizeAsync
  can't complete in the same frame, and rendering the intermediate state makes the Qt::Tool child window flicker; Qt setGeometry's redundant
  resize (resizeAsync called even when the size hasn't changed) is the trigger. defect/ohos-runtime (a system API behavior
  defect, diagnosed; a pure ArkTS real-device repro rules out Qt, evidence=both); workaround
  W-0012 (remove the redundant resize) proposed; no tracking ticket yet (the source page records no ticket number).
---

# C-0014 moveWindowToGlobalDisplay × resizeAsync have no rendering atomicity during cross-screen migration

> nature: defect | responsible: ohos-runtime | status: diagnosed | symptoms: S-0013 | workarounds: W-0012 (proposed) | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0013 Qt::Tool child windows flicker when dragging the MainWindow across screens in a multi-screen setup

Commercial Qt issue report: on a multi-screen device, when the MainWindow title bar is dragged across screens, the Qt::Tool child window
(ToolWidget) keeps flickering. Trigger conditions: multiple screens + dragging the title bar + a Qt::Tool child window. For the full
analysis see the postmortem [toolwindow-crossscreen-flicker](../episodic/postmortems/toolwindow-crossscreen-flicker.md).

## Root cause / classification basis

The full Qt-side call chain (source page, with file:line):

```
MainWindow::moveEvent() → updateToolWidget()
  → m_toolWidget->setGeometry(rect)
    → QOhosFloatingWindow::setGeometry(rect)        [qohosfloatingwindow.cpp:44]
      → view->setPosition(topLeft)                  [line 68]
          → flush → updateWindowPosition()          [qohosview.cpp:810]
            → m_ohosWindowProxy->moveWindowToGlobalOrGlobalDisplay()  [qohoswindowproxy.cpp:372]
              → "moveWindowToGlobalDisplay(x, y)"   [line 434, Promise]
      → view->setSize(size)                         [line 70]
          → flush → updateWindowSize()              [qohosview.cpp:801]
            → m_ohosWindowProxy->setSize()          [qohoswindowproxy.cpp:442]
              → "resizeAsync(w, h)"                 [line 452, Promise]
```

Log evidence (captured after instrumenting a rebuilt libqohos.so, on every moveEvent):

```
JS-CALL: resizeAsync(476,203)                    ← called every time, even when the size hasn't changed
JS-CALL: moveWindowToGlobalDisplay(1888,743)      ← always after the resize
```

Key facts:
1. The window size 476×203 **never changes** during the whole drag, yet every moveEvent triggers
   `resizeAsync` (10+ redundant calls), always in the order resizeAsync → moveWindowToGlobalDisplay;
2. **blocking resizeAsync → the flicker disappears completely** (verified by the user on the Qt side);
3. the `QOhosView` batching mechanism works correctly (position/size go out in the same flush), and
   `QOhosFloatingWindow::setGeometry` unconditionally calling setPosition + setSize is a reasonable
   framework design (it keeps the window state in sync with the system).

**Root cause**: in the cross-screen drag scenario, `moveWindowToGlobalDisplay` triggers the window's screen migration, and
`resizeAsync` runs while the migration is in progress -- the rendering of the two asynchronous operations on the system side can't complete in the same frame
(no atomicity guarantee), and rendering the intermediate state is the flicker.

**Pure HarmonyOS real-device repro (ruling out Qt)**: on a HUAWEI MateBook Fold dual-screen real device, pure ArkTS
code (`setInterval(50ms)` polling the main window position → calling `subWindow.moveWindowTo()` +
`subWindow.resize()` together) reproduces exactly the same flicker; calling only `moveWindowTo` without `resize` doesn't flicker.
→ The problem is at the HarmonyOS system level, unrelated to the Qt framework.

## Responsibility

`ohos-runtime` -- the system window APIs can't execute resize + move atomically during cross-screen migration
(a system API behavior defect; disposition: System issue). The Qt-side behavior is reasonable and necessary (skipping setSize may
leave the initial size wrong -- the source postmortem explicitly warns "don't rush to change the Qt framework").

## Permanent fix (defect)

System side: guarantee rendering atomicity of `moveWindowToGlobalDisplay` × `resizeAsync` during cross-screen migration,
or provide an atomic window geometry update API. No route until a ticket is filed (with a system OTA / new
API version; a T needs to be created to track it).

## Workarounds

- **W-0012 (proposed, verified by controlled experiment 2026-06-05 on a dual-screen real device)**: remove the redundant resize --
  don't trigger resizeAsync when the size hasn't changed:
  1. Qt adaptation layer: when `QOhosView` flushes a batch, compare the old and new size and skip
     `updateWindowSize()` if unchanged (changes qohosview.cpp / qohosfloatingwindow.cpp; requires rebuilding
     libqohos.so / the kit);
  2. application layer (self-managed ToolWindow scenario): compare with the old size before `setGeometry`; if the size hasn't changed, only
     move, don't resize.

  Cost: ① changing the framework requires rebuilding the kit and carefully assessing the impact (skipping setSize may leave the initial size
  wrong); ② the application-layer option only covers self-managed windows.
  Verification basis: the flicker disappears with resizeAsync blocked (2026-06-05, MateBook Fold dual-screen real device,
  verified by the user on the Qt side + a pure ArkTS control repro reaching the same conclusion); **the mechanism is verified but not adopted as a long-term solution**
  (the postmortem's conclusion: evaluate the system API behavior first, don't rush to change the framework).
  Retirement condition: once the system guarantees atomic rendering of cross-screen move+resize (or offers an atomic geometry update API),
  remove the patch that skips the redundant resize and rerun the cross-screen drag test.

## Tickets

None yet (the postmortem records no upstream ticket number; the original ticket number from the commercial Qt feedback channel wasn't kept with the source page). Placeholder
note: if an issue is later filed with Huawei, open it as ohos-issue and fill in this section --
evidence=both (pure ArkTS repro demo + call chain logs) already meets the ticket evidence gate.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-05 | Qt OHOS (instrumented libqohos.so rebuild) / multi-screen real device | Full call chain trace + log collection: fixed order resizeAsync → moveWindowToGlobalDisplay, resizeAsync triggered 10+ times with an unchanged size; blocking resizeAsync makes the flicker disappear | Pinned down the redundant resize as the trigger and the system API conflict as the root cause | → diagnosed |
| 2026-06-05 | HUAWEI MateBook Fold dual-screen real device (pure ArkTS, no Qt) | Calling moveWindowTo + resize together reproduces the flicker; only moveWindowTo without resize doesn't flicker | Reproduced without Qt, ruling out the Qt framework; attributed to the system API | (stays diagnosed) |

## Related

- Symptoms (S): S-0013
- Workarounds (W): W-0012
- Tickets (T): none yet (the source page has no ticket number; the ticket material is ready)
- episodic: [toolwindow-crossscreen-flicker](../episodic/postmortems/toolwindow-crossscreen-flicker.md) (full call chain, instrumentation logs, pure ArkTS repro, reusable lessons)
- semantic: [qt-harmonyos-window-model](../semantic/qt-harmonyos-window-model.md)
- Related causes (C, including depends_on notes): none (the observation that screenIdChanged fires late during the drag is recorded in the postmortem and not classified as a cause on its own)
