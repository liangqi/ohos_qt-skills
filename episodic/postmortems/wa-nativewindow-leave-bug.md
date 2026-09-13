---
id: episodic-wa-nativewindow-leave-bug
type: episodic
domain: debug
tags: [qt, harmonyos, ohos, qpa, leave-event, wa-nativewindow, mouse, hover, xcomponent]
created: 2026-06-04
updated: 2026-06-09
status: active
audience: public
refs: [semantic-qt-harmonyos-window-model, semantic-qt-harmonyos-api]
summary: >
  A complete analysis of the unresponsive WA_NativeWindow Leave event bug: the dual-blind-spot root cause (the Qt widget layer's
  internalWinId() skip + unreliable OHOS QPA hover callbacks), a full call chain trace,
  an evaluation of fix strategies (3 options compared), a 10-scenario risk matrix, and sequence diagrams. Qt 5.12 OHOS.
  ✅ Manually verified; the deliverables are in <WORK_DIR>/leave-event-fix/ (final tidy-up 2026-06-09).
---

# The Qt WA_NativeWindow unresponsive Leave event bug — a complete analysis

> **Affected version**: the Qt 5.12.12 OHOS branch (`tqtc/harmonyos-5.12.12`, commit `613336de`)
> **Also affected**: the Qt 5.15.16 OHOS branch (the `qohoshovereventsgenerator.cpp` code is identical in both versions)
> **Analysis date**: 2026-06-04
> **Analyst**: <original-author> (a Qt for HarmonyOS developer)

---

## 1. Problem overview

### 1.1 In one sentence

Once `centralWidget` has the `Qt::WA_NativeWindow` attribute set, moving the mouse out of that widget into an adjacent `QDockWidget` either doesn't fire `QEvent::Leave` at all or fires it after a long delay.

### 1.2 Trigger conditions

| Condition | Notes |
|-----------|-------|
| The target widget has `setAttribute(Qt::WA_NativeWindow)` | Which gives it its own `internalWinId()` |
| That widget has `setMouseTracking(true)` | It relies on hover/Leave events for UI feedback |
| The mouse crosses the boundary between that widget and an adjacent one | Especially crossing into another independent XComponent region |

### 1.3 Expected vs. actual behavior

| | Description |
|---|-------------|
| **Expected** | When the mouse leaves `centralWidget`, `QEvent::Leave` fires immediately and `leaveEvent()` is called |
| **Actual** | The Leave event is lost or badly delayed — the widget's hover state, cursor tracking and tooltip timers all linger |

### 1.4 Reproduction steps

1. Build the demo (`<INTERNAL_DEMO>`) and deploy it to a HarmonyOS device
2. Put the mouse in the dark central region (`CentralWidget`, which has `WA_NativeWindow` + `setMouseTracking(true)`)
3. Slowly move the mouse towards the `QDockWidget` docked on the left and watch for `QtDemoLog:Leave` in hilog

**The control experiment**: comment out `setAttribute(Qt::WA_NativeWindow)` in `centralwidget.h` → Leave events work again, confirming `WA_NativeWindow` is the direct trigger.

---

## 2. Complete source analysis

### 2.1 The Leave event dispatch path in the Qt widget layer

#### The full call chain

```
The QPA plugin calls handleLeaveEvent(QWindow*)
    │
    ▼
① QWindowSystemInterface::handleLeaveEvent<QWindowSystemInterface::DefaultDelivery>()
    │  qwindowsysteminterface.cpp:227-231
    │  creates a LeaveEvent and queues it
    │
    ▼
② QGuiApplicationPrivate::processWindowSystemEvent()
    │  qguiapplication.cpp:1915-1917
    │  switch(e->type) case Leave → processLeaveEvent()
    │
    ▼
③ QGuiApplicationPrivate::processLeaveEvent()
    │  qguiapplication.cpp:2324-2337
    │  checks for modal blocking → sends QEvent::Leave to the QWindow
    │
    ▼
④ QWidgetWindow::event()
    │  qwidgetwindow.cpp:262-288
    │  case QEvent::Leave → handleEnterLeaveEvent(event)
    │
    ▼
⑤ QWidgetWindow::handleEnterLeaveEvent()
    │  qwidgetwindow.cpp:426-487
    │  ★ the critical skip point: lines 467-469
    │
    ▼
⑥ QApplicationPrivate::dispatchEnterLeave(enter, leave, globalPosF)
    │  qapplication.cpp:2207
    │  builds leaveList / enterList and sends QEvent::Leave / QEvent::Enter to each
    │
    ▼
⑦ QWidget::leaveEvent() / QWidget::enterEvent()
    │  finally reaching user code
```

#### The key source locations

**The QPA entry point** — `qwindowsysteminterface.cpp:227-231`:

```cpp
QT_DEFINE_QPA_EVENT_HANDLER(void, handleLeaveEvent, QWindow *window)
{
    QWindowSystemInterfacePrivate::LeaveEvent *e =
        new QWindowSystemInterfacePrivate::LeaveEvent(window);
    QWindowSystemInterfacePrivate::handleWindowSystemEvent<Delivery>(e);
}
```

The `QT_DEFINE_QPA_EVENT_HANDLER` macro (lines 200-204) expands to 3 explicit template instantiations: `DefaultDelivery`, `SynchronousDelivery` and `AsynchronousDelivery`.

**Event dispatch** — `qguiapplication.cpp:2324-2337`:

```cpp
void QGuiApplicationPrivate::processLeaveEvent(
    QWindowSystemInterfacePrivate::LeaveEvent *e)
{
    if (!e->leave)
        return;
    if (e->leave.data()->d_func()->blockedByModalWindow)
        return;  // blocked by a modal window

    currentMouseWindow = 0;

    QEvent event(QEvent::Leave);
    QCoreApplication::sendSpontaneousEvent(e->leave.data(), &event);
}
```

The Leave event is sent as a spontaneous event to the **QWindow** `e->leave` points at. For a widget window, that QWindow is the `QWidgetWindow`.

**★ The skip point** — `qwidgetwindow.cpp:464-472`:

```cpp
if (!enter || !QWidget::mouseGrabber()) {
    // Preferred leave target is the last mouse receiver, unless it has native window,
    // in which case it is assumed to receive it's own leave event when relevant.
    QWidget *leave = m_widget;                                              // line 467
    if (qt_last_mouse_receiver && !qt_last_mouse_receiver->internalWinId()) // line 468 ★
        leave = qt_last_mouse_receiver.data();                               // line 469
    QApplicationPrivate::dispatchEnterLeave(enter, leave, globalPosF);       // line 470
    qt_last_mouse_receiver = enter;
}
```

#### What the `internalWinId()` check does

| The state of `qt_last_mouse_receiver` | The `leave` target | Qt's design intent |
|----------------------------------------|--------------------|--------------------|
| `nullptr` (no tracking information) | `m_widget` (the top-level window widget) | A fallback: leave the whole top-level window |
| `internalWinId() != 0` (a native widget) | `m_widget` (the top-level window widget) | **Skip**: assume the QPA will deliver a Leave to that native child window separately |
| `internalWinId() == 0` (an alien widget) | `qt_last_mouse_receiver` | Correct: alien widgets don't exist to the QPA, so the Leave has to be synthesized |

**The core assumption**: Qt's widget layer assumes that a native child widget with an `internalWinId()` will receive its **own separate Leave event** through the QPA (targeting that child's `QWidgetWindow`). That's true on X11, Windows and macOS — the OS delivers a Leave for every native window boundary crossing.

**On OHOS that assumption doesn't hold** — the QPA never delivers that separate Leave.

---

### 2.2 The OHOS QPA mouse event path

#### The full call chain

```
The ArkUI NODE_ON_MOUSE callback (on the JS thread)
    │
    ▼
① The lambda registered by QEmbeddedWindowNode::setMouseEventsHandler()
    │  qembeddedwindownode.cpp:555-563
    │  ArkUI_UIInputEvent → NativeNodeMouseEvent
    │
    ▼
② QOhosNativeNodeMouseInputHandler::handleMouseEvent()
    │  qohosnativemouseeventshandler.cpp:102-144
    │  parses the event → calls hoverEventsGenerator (an empty implementation) → adds it to the batch
    │
    ▼
③ The batching handler (asynchronously dispatched to the Qt thread)
    │  qohosnativemouseeventshandler.cpp:128-143
    │  makeQtOhosBatchingQtRequestsHandler → visitInQtThreadIfAlive
    │
    ▼
④ processMouseEventsInQtThread()                    ★ the Qt thread entry point
    │  qohosnativemouseeventshandler.cpp:146-207
    │  iterates the batch → filters with mayDropMouseEvent
    │  → [FIX] the s_lastMouseWindow cross-window compensation
    │  → eventHandler->onMouseEvent()
    │
    ▼
⑤ QOhosInputMethodEventHandler::onMouseEvent()
    │  → handleMouseEvent()
    │  → QWindowSystemInterface::handleMouseEvent()
    │
    ▼
⑥ Into Qt's standard event dispatch (③-⑦ from 2.1)
```

#### The batching mechanism + `mayDropMouseEvent`

**The point of batching**: collect the high-frequency mouse events on the JS thread in batches and dispatch them to the Qt thread in one go, reducing cross-thread overhead.

**The event-dropping logic** — `qohosnativemouseeventshandler.cpp:209-216`:

```cpp
bool QOhosNativeNodeMouseInputHandler::mayDropMouseEvent(
    ch::steady_clock::time_point now,
    const MouseEvent &event,
    const MouseEvent &nextEvent)
{
    return
        now - event.timestamp >= mouseMotionEventMinAgeForDrop  // the event's age >= the threshold
        && event.mouseEvent.eventType == QEvent::MouseMove       // this one is a Move
        && nextEvent.mouseEvent.eventType == QEvent::MouseMove;  // and so is the next
}
```

**The effect**: among consecutive `MouseMove` events, intermediate ones older than the threshold are dropped and only the newest is kept. That means some intermediate positions never reach Qt during fast movement — but **the last event is always kept**, so cross-window detection never misses.

#### `processMouseEventsInQtThread` is the real Qt thread entry point

This is the **one and only** place mouse events are handled on the Qt main thread. Putting the compensation code here guarantees:
- It runs synchronously on the Qt thread, with no cross-thread race
- It runs before `onMouseEvent()`, so Leave/Enter arrive before the MouseMove
- All handler instances share the `static s_lastMouseWindow`, so tracking works across XComponents

---

### 2.3 The OHOS QPA hover event path

#### What `QOhosHoverEventsGenerator` does

It was originally designed as a **coordinate synchronization bridge**: ArkUI NativeNode hover events have a system-level limitation — the pointer coordinates are always `(0, 0)`. `QOhosHoverEventsGenerator` "compensates" for that by using the correct coordinates from the mouse events, while also taking on the job of generating Enter/Leave events.

```
                    ┌──────────────────────────────────┐
                    │   QOhosHoverEventsGenerator       │
                    │                                    │
mouse events ──────→│ handleQOhosMouseEvent()           │
(correct coords)    │   → caches the local/global coords│
                    │   → if !m_hovered:                 │
                    │       sendQtHoverEvent(true)       │──→ handleEnterEvent(correct coords)
                    │       m_hovered = true              │
                    │                                     │
the ArkUI hover ───→│ handleQOhosHoverEvent(hovered)     │
callback            │   → if !hovered && m_hovered:      │
                    │       sendQtHoverEvent(false)       │──→ handleLeaveEvent(cached coords)
                    │       m_hovered = false             │
                    └──────────────────────────────────┘
```

#### The current state: both paths are disabled

**The file** — `qohoshovereventsgenerator.cpp:34-48`:

```cpp
void QOhosHoverEventsGeneratorImpl::handleQOhosMouseEvent(
    const QOhosMouseEvent &mouseEvent)
{
    // [FIX] Removed sendQtHoverEvent(true) — async Enter/Leave interferes with
    // the synchronous Leave compensation in processMouseEventsInQtThread.
    Q_UNUSED(mouseEvent);  // an empty implementation
}

void QOhosHoverEventsGeneratorImpl::handleQOhosHoverEvent(bool hovered)
{
    // [FIX] Removed sendQtHoverEvent(false) — ArkUI hover callbacks are unreliable
    // at XComponent boundaries.
    Q_UNUSED(hovered);     // an empty implementation
}
```

#### The two parallel paths compared

| Path | Entry point | Current state |
|------|-------------|---------------|
| **Path 1**: the XComponent `DispatchHoverEvent` | `CallbackReceiver::onHoverEvent()` → `QOhosNativeXComponentInputHandler::handleHoverEvent()` | Only registered when `isNativeNodeApiMouseEventsEnabled()=false` (not the default) |
| **Path 2**: the ArkUI NativeNode `NODE_ON_HOVER_EVENT` | → `hoverEventsGenerator->handleQOhosHoverEvent()` | Registered but an empty implementation (in the default configuration) |
| **Path 3**: cross-window compensation on mouse movement (new) | `processMouseEventsInQtThread` → `s_lastMouseWindow` detection | **The only source of Enter/Leave** |

#### `sendQtHoverEvent`'s asynchronous `visitInQtThreadIfAlive` dispatch

The original `sendQtHoverEvent()` dispatched the event to the Qt thread through `m_qWindowRef.visitInQtThreadIfAlive(...)`. That's an **asynchronous** operation — the event is queued on the Qt thread and processed in some future event loop iteration. That races with the **synchronous** compensation in `processMouseEventsInQtThread` (see §4.2).

---

### 2.4 A cross-platform comparison

| Platform | Where Leave events come from | Reliability |
|----------|------------------------------|-------------|
| **X11** | `LeaveNotify` (a native X Server event) | ✅ Guaranteed at the OS level for every window boundary |
| **Windows** | `WM_MOUSELEAVE` (registered via `TrackMouseEvent`) | ✅ Guaranteed at the OS level |
| **macOS** | `mouseExited:` (NSTrackingArea) | ✅ Guaranteed at the OS level |
| **Wayland** | `wl_pointer.leave` | ✅ Guaranteed at the protocol level |
| **OHOS** | The ArkUI `NODE_ON_HOVER_EVENT` with hover=false | ❌ **Unreliable** — it gets lost at XComponent boundaries |

**OHOS is the only platform with no OS-level Leave event support.** That's the fundamental platform difference behind this bug:

- On other platforms the OS automatically delivers a Leave whenever the mouse leaves a native window
- On OHOS, ArkUI only delivers a hover callback at XComponent boundaries, and unreliably
- Qt's widget layer (`qwidgetwindow.cpp:468`) assumes the QPA will deliver the Leave, but the OHOS QPA can't

---

## 3. Assessing the impact of the change

### 3.1 The list of changes in the current fix

| File | What changed | Lines |
|------|--------------|-------|
| `qohoshovereventsgenerator.cpp` | `handleQOhosMouseEvent()` and `handleQOhosHoverEvent()` became empty (no-ops), and the original `sendQtHoverEvent()` function and its state were deleted | :34-48 |
| `qohosnativemouseeventshandler.cpp` | Added `static QPointer<QWindow> s_lastMouseWindow`; in `processMouseEventsInQtThread`'s for loop, detect a window change and synchronously call `handleLeaveEvent` + `handleEnterEvent` | :85-90, :174-203 |
| `qohosnativemouseeventshandler.h` | Added the `s_lastMouseWindow` static member declaration | :87 |
| `qohosinputmethodeventhandler.cpp` | Removed the round-one compensation code from `handleMouseEvent`; kept the `m_lastWindowLeft` defensive mechanism | — |

### 3.2 Scenario-by-scenario risk assessment

| # | Scenario | Risk level | Notes |
|---|----------|:----------:|-------|
| 1 | Normal cross-window movement (centralWidget → DockWidget) | **NONE** | The compensation works; Leave + Enter are sent synchronously |
| 2 | A drag operation (dragging a QDockWidget across windows) | **LOW** | `isMouseGrabbed()` skips the compensation; on release `stopAnyMouseGrab()` sends Enter, but the old window's Leave is missing |
| 3 | Multiple top-level windows (MainWindow ↔ QDialog) | **NONE** | `s_lastMouseWindow` is static and shared across instances, so detection is correct |
| 4 | The mouse leaves every Qt window ⚠️ | **MEDIUM** | No new mouse event triggers the compensation, `s_lastMouseWindow` lingers, and the last window never gets a Leave |
| 5 | The mouse sits still in one window | **NONE** | No window change, so no spurious events |
| 6 | The window is destroyed while still hovered | **NONE** | `QPointer` nulls itself out, so the next mouse movement is handled safely |
| 7 | Touchscreen hover (a finger hovering without touching) | **LOW** | It produces no mouse events so the compensation doesn't fire; but HarmonyOS touchscreen scenarios usually don't need hover |
| 8 | Stylus hover | **LOW** | Same as scenario 7 |
| 9 | Flicking the mouse quickly across several windows | **NONE** | `mayDropMouseEvent` drops the intermediate events but keeps the last one, and the compensation runs correctly on that last event |
| 10 | A Leave while a popup menu is open | **NONE** | Qt's popup mode has its own Enter/Leave handling (`qwidgetwindow.cpp:428-434`) |

#### Scenario 4 in detail (the only MEDIUM risk)

```
The mouse moves out of window A → leaving every Qt window region

① No new mouse event reaches any Qt window
② processMouseEventsInQtThread is never called
③ s_lastMouseWindow still points at A
④ A never receives a Leave

Knock-on effects:
- The mouse re-enters A → s_lastMouseWindow == A → no Enter is generated → A's underMouse state was already stale
- The mouse enters another window B → Leave(A) + Enter(B) are generated → A's stale state is cleared late
```

**A mitigating factor**: HarmonyOS applications usually run fullscreen, so the mouse leaving every Qt window is rare.

### 3.3 The impact of removing `sendQtHoverEvent(true)`

#### What it originally solved

Reconstructed precisely from the git history (commit `96728a820e`, Adam Krzykala, 2025-11-07, QTFOROH-1835):

> "pointer position for [native node hover events] is always 0,0 (system limitation)"

The pointer coordinates ArkUI NativeNode's `NODE_ON_HOVER_EVENT` callback provides are **always `{0, 0}`**. When the first mouse event arrived, `sendQtHoverEvent(true)` used the mouse event's correct coordinates to generate the Enter event, solving the "the Enter event's coordinates are 0,0" problem.

#### Why it isn't needed now

The current compensation code in `processMouseEventsInQtThread` calls `handleEnterEvent()` with the `localPosition` and `globalPosition` carried by the mouse event directly:

```cpp
QWindowSystemInterface::handleEnterEvent(
    targetWindow, mouseEvent.localPosition, mouseEvent.globalPosition);
// qohosnativemouseeventshandler.cpp:200-201
```

Those coordinates come from ArkUI's `NODE_ON_MOUSE` callback and are correct pixel coordinates (there's no 0,0 problem).

#### Is it safe?

**Yes.** The Enter event the compensation generates carries correct coordinates and runs synchronously (no timing race). `sendQtHoverEvent(true)`'s asynchronous Enter is not only redundant — it would produce a duplicate Enter alongside the synchronous compensation.

### 3.4 The impact of removing `sendQtHoverEvent(false)`

#### What it originally solved

When the mouse leaves the XComponent's hover region, ArkUI fires a `hovered=false` callback. `sendQtHoverEvent(false)` turned that into Qt's `QEvent::Leave`. It was the only mechanism that could generate a Leave when the mouse **left every Qt window**.

#### Why removing it is risky

With it gone, the "the mouse leaves every Qt window" scenario (§3.2 scenario 4) loses its only source of Leave events. The compensation mechanism depends on a new mouse event to trigger it, and there won't be one once the mouse has left every window.

#### The fact that the direct hover path is still live

Note that the `NODE_ON_HOVER_EVENT` callback is still registered at the ArkUI layer (`qnativenode.cpp:239-241`); only the receiving end (`hoverEventsGenerator->handleQOhosHoverEvent()`) is empty. If you restore that function, you can use ArkUI's hover-leave as a defensive layer without changing the registration logic.

---

## 4. The root cause

### 4.1 The dual blind spot

The Leave event goes missing because **two independent layers each assume the other will deliver it**, and neither does.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          The dual blind spot                                 │
│                                                                             │
│   ┌─────────────────────────┐         ┌──────────────────────────────┐     │
│   │  Blind spot #1:          │         │  Blind spot #2:               │     │
│   │  the Qt widget layer     │         │  the OHOS QPA layer           │     │
│   │                          │         │                               │     │
│   │  qwidgetwindow.cpp:468   │         │  qohoshovereventsgenerator   │     │
│   │                          │         │  .cpp:42-48                   │     │
│   │  internalWinId() != 0    │ assumes │                               │     │
│   │  → skip synthesizing     │───────→│  the hover callback is the    │     │
│   │    Leave                 │ the QPA │  only source of Leave         │     │
│   │  → assume the QPA will   │  will   │  → but ArkUI hover is         │     │
│   │    deliver it            │ handle  │    unreliable at boundaries   │     │
│   │                          │   it    │  → and the hover implementation│    │
│   │                          │         │    has been disabled           │     │
│   └─────────────────────────┘         └──────────────────────────────┘     │
│                                                                             │
│   The result: the event falls through the gap between the two layers        │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Blind spot \#1: the Qt widget layer skips synthesizing because of `internalWinId()`

**Location**: `qwidgetwindow.cpp:467-469`

When the top-level window's Leave event reaches `handleEnterLeaveEvent()`, the code checks `qt_last_mouse_receiver->internalWinId()`. If the last mouse receiver is a native widget (`WA_NativeWindow`), it **skips** it and sends the Leave to the top-level window widget (`m_widget`) rather than to the actual native child.

Qt's design intent (the comment on lines 465-466):

> "Preferred leave target is the last mouse receiver, **unless it has native window**, in which case it is assumed to receive it's own leave event when relevant."

#### Blind spot \#2: in the OHOS QPA, Leave depends entirely on the ArkUI hover callback

**Location**: `qohoshovereventsgenerator.cpp:42-48`

In the entire OHOS QPA plugin, the only call site of `QWindowSystemInterface::handleLeaveEvent()` was inside `QOhosHoverEventsGenerator`'s `sendQtHoverEvent(false)` (now deleted). That function depends on ArkUI's `NODE_ON_HOVER_EVENT` callback — and ArkUI's hover callback is **unreliable** at XComponent boundaries (fast swipes, no pixel gap, sibling node scheduling skips).

#### The two blind spots combine to lose the event

```
The mouse moves from WA_NativeWindow child A → child B

Step 1: ArkUI fires a mouse event on B's XComponent
        (it doesn't generate a Leave for A — ArkUI doesn't know about Qt window boundaries)
        ↓
Step 2: The OHOS QPA delivers the mouse movement to B's QWindow
        (with no Leave for A — ArkUI doesn't provide one)
        ↓
Step 3: The Qt widget layer handles B's QWindow-level event
        QWidgetWindow::handleEnterLeaveEvent() runs
        ↓
Step 4: Blind spot #1 kicks in
        qt_last_mouse_receiver = A's widget (which has WA_NativeWindow)
        internalWinId() != 0 → skip
        leave = m_widget (the top-level widget), not A
        dispatchEnterLeave sends the Leave to the top-level widget, not to A
        ↓
Step 5: A never receives QEvent::Leave
        Its hover state, cursor tracking and tooltip timers all linger
```

### 4.2 The conflict between asynchronous dispatch and synchronous handling

#### The essence of the problem

| Mechanism | Where it runs | Timing characteristics |
|-----------|---------------|------------------------|
| `visitInQtThreadIfAlive` (the old `sendQtHoverEvent`) | The ArkUI thread → asynchronously dispatched to the Qt thread | The event is queued and handled in **some future event loop iteration** |
| `processMouseEventsInQtThread` (the current compensation) | The Qt thread | **Synchronous**, handled immediately within the current call stack |

#### The race in detail

```
Time ──────────────────────────────────────────────────────────────→

The JS thread (ArkUI):
  T0: hover=false on XComponent_A
      → sendQtHoverEvent(false)
      → visitInQtThreadIfAlive(LeaveEvent_A)    ← asynchronous dispatch

  T1: mouse move on XComponent_B
      → queued into a batch → visitInQtThreadIfAlive(batch_B)  ← asynchronous dispatch

The Qt thread:
  T2: handles LeaveEvent_A (from T0)
      → QEvent::Leave sent to A ✓

  T3: handles batch_B (from T1)
      → processMouseEventsInQtThread
      → s_lastMouseWindow = null (A was just Left)
      → detects a window change → sends Leave(A) + Enter(B) again
      → ★ a duplicate Leave(A)!

  or:

  T2: handles batch_B (from T1, which arrives first)
      → s_lastMouseWindow = A
      → detects a window change → Leave(A) + Enter(B) ✓

  T3: handles LeaveEvent_A (from T0, arriving later)
      → ★ another Leave(A)! A has already Left!
```

**The conclusion**: the timing between the asynchronous hover callback and the synchronous compensation is unpredictable, producing duplicate Leave events that corrupt Qt's internal state machine. That's the fundamental reason round 2 disabled `sendQtHoverEvent`.

### 4.3 Why the first round of fixes failed

#### Failure reason 1: the compensation code sat in `handleMouseEvent` and never fired

Round one put the compensation in `QOhosInputMethodEventHandler::handleMouseEvent()`. But mouse events actually arrive through the asynchronous batching path in `qohosnativemouseeventshandler.cpp` — `handleMouseEvent()` is the `onMouseEvent()` call inside the batching callback, by which point it's too late, and each call only handles a single event, so it can't see a cross-window transition.

#### Failure reason 2: batching swallows the intermediate events

`mayDropMouseEvent` drops intermediate `MouseMove` events older than the threshold while building the batch. If the compensation code relied on every event to detect a window change, the dropped events would cause misses.

#### Failure reason 3: instance members can't share state across XComponents

Each XComponent has its own `QOhosNativeNodeMouseInputHandler` instance. When the mouse moves from XComponent A to XComponent B:

- Instance A's `m_lastWindow` = A (but A no longer receives events)
- Instance B's `m_lastWindow` = null (it's receiving its first event and doesn't know A came before)

**The window change can't be detected.** A `static` variable is required to share state across instances.

---

## 5. How the problem unfolds

### 5.1 Sequence diagram A: without `WA_NativeWindow` (working)

Every child widget is alien (no `internalWinId()`). One QWindow, one XComponent.

```
The mouse is in centralWidget ─────────────────────→ the mouse moves into the dockWidget region
(the same QWindow_Main, the same XComponent)          (still the same QWindow_Main)

══════════════════════════════════════════════════════════════════════

[The JS thread — ArkUI]

T0  XComponent_Main: NODE_ON_MOUSE fires (MouseMove)
    │
    ├─ qnativenode.cpp:235 → mouseEventsHandler(NativeNodeMouseEvent)
    ├─ qohosnativemouseeventshandler.cpp:102 → handleMouseEvent()
    ├─ hoverEventsGenerator->handleQOhosMouseEvent() → [an empty implementation]
    └─ batch.push_back({now, mouseEvent})

══════════════════════════════════════════════════════════════════════

[The Qt thread — the event dispatcher]

T1  processMouseEventsInQtThread(batch)
    │  qohosnativemouseeventshandler.cpp:146
    │
    ├─ the s_lastMouseWindow check: the same window → no compensation
    └─ eventHandler->onMouseEvent(mouseEvent)
         → QWindowSystemInterface::handleMouseEvent(QWindow_Main, ..., MouseMove)

T2  QWidgetWindow_Main::handleMouseEvent()
    │  qwidgetwindow.cpp:681
    │
    ├─ widget = m_widget->childAt(pos) → dockWidget
    └─ QApplicationPrivate::sendMouseEvent(dockWidget, ..., qt_last_mouse_receiver)

T3  sendMouseEvent() — Enter/Leave dispatch between alien widgets
    │  qapplication.cpp:2615-2629
    │
    │  lastMouseReceiver = centralWidget (the previous mouse movement's receiver)
    │  receiver = dockWidget
    │  alienWidget = dockWidget (alien, no internalWinId)
    │
    ├─ condition: alienWidget && alienWidget != lastMouseReceiver
    │   → dockWidget != centralWidget → TRUE ✓
    │
    └─ dispatchEnterLeave(dockWidget, centralWidget, ...)
         │  qapplication.cpp:2207
         ├─ QEvent::Leave  → centralWidget  ✓ delivered
         └─ QEvent::Enter  → dockWidget     ✓ delivered

══════════════════════════════════════════════════════════════════════

Result: ✓ Leave + Enter are delivered correctly through sendMouseEvent's alien widget tracking.
        No QPA-level Leave/Enter is needed.
```

### 5.2 Sequence diagram B: with `WA_NativeWindow` (the original bug)

The DockWidget has `WA_NativeWindow` → its own `QWindow_Dock` and `XComponent_Dock`.

```
The mouse is in centralWidget ───────────────────→ the mouse crosses into the DockWidget
(QWindow_Main, XComponent_Main)                     (QWindow_Dock, XComponent_Dock)
                                                     ↑ a different XComponent!

══════════════════════════════════════════════════════════════════════

[The JS thread — ArkUI]

T0  XComponent_Main: NODE_ON_MOUSE fires (MouseMove, in the centralWidget region)
    ├─ handleMouseEvent() → batch_A.push_back(...)

T1  The mouse crosses the XComponent boundary
    │
    │  In theory the ArkUI hover callbacks should fire:
    │    hover=false on XComponent_Main  →  sendQtHoverEvent(false)
    │    hover=true  on XComponent_Dock  →  sendQtHoverEvent(true)
    │
    │  ★ But ArkUI's hover callbacks are unreliable at XComponent boundaries ★
    │  → they may not fire, may fire late, or may carry (0,0) coordinates
    │
    ├─ XComponent_Dock: NODE_ON_MOUSE fires (MouseMove, in the dock region)
    ├─ handleMouseEvent() → batch_B.push_back(...)

══════════════════════════════════════════════════════════════════════

[The Qt thread — the original code, with no compensation]

T2  Handles batch_A (from XComponent_Main)
    ├─ eventHandler->onMouseEvent()
    │   → QWindowSystemInterface::handleMouseEvent(QWindow_Main, ..., MouseMove)
    └─ QWidgetWindow_Main::handleMouseEvent()
        → sendMouseEvent() → normal intra-window dispatch

T3  Handles batch_B (from XComponent_Dock)
    ├─ eventHandler->onMouseEvent()
    │   → QWindowSystemInterface::handleMouseEvent(QWindow_Dock, ..., MouseMove)
    └─ QWidgetWindow_Dock::handleMouseEvent()
        → this is QWindow_Dock's first mouse event
        → handleEnterLeaveEvent has no qt_last_mouse_receiver information
        → it won't generate a Leave for the centralWidget on QWindow_Main

    ★ Meanwhile QWindow_Main never received a QPA-level Leave event ★
    ★ QWidgetWindow_Main::handleEnterLeaveEvent(Leave) never ran ★
    ★ centralWidget never receives QEvent::Leave ★

══════════════════════════════════════════════════════════════════════

Result: ✗ The Leave event is lost.
        Blind spot #1: the Qt widget layer assumes the QPA will deliver a Leave for the native child window
        Blind spot #2: the OHOS QPA has no mechanism to generate that Leave
        The event falls through the gap between the two layers.
```

### 5.3 Sequence diagram C: with `WA_NativeWindow` + the current fix (after fixing)

```
The mouse is in centralWidget ───────────────────→ the mouse crosses into the DockWidget
(QWindow_Main, XComponent_Main)                     (QWindow_Dock, XComponent_Dock)

══════════════════════════════════════════════════════════════════════

[The JS thread — ArkUI]

T0  XComponent_Main: NODE_ON_MOUSE → batch_A
T1  XComponent_Dock: NODE_ON_MOUSE → batch_B

  (the hover callbacks are disabled and produce no events)

══════════════════════════════════════════════════════════════════════

[The Qt thread — the fixed code, with compensation]

T2  processMouseEventsInQtThread(batch_A)          [from handler instance A]
    │  qohosnativemouseeventshandler.cpp:146
    │
    ├─ targetWindow = QWindow_Main
    ├─ s_lastMouseWindow = nullptr (the first time)
    ├─ condition: s_lastMouseWindow && ... → FALSE (null) → no compensation
    ├─ s_lastMouseWindow = QWindow_Main             ← recorded
    └─ onMouseEvent() → normal mouse movement handling

T3  processMouseEventsInQtThread(batch_B)          [from handler instance B]
    │  qohosnativemouseeventshandler.cpp:146
    │
    ├─ targetWindow = QWindow_Dock
    ├─ s_lastMouseWindow = QWindow_Main (set at T2)
    ├─ condition: s_lastMouseWindow(Main) && Main != Dock → TRUE ✓
    │   │
    │   ├─ oldWindow = QWindow_Main
    │   ├─ QWindowSystemInterface::handleLeaveEvent(QWindow_Main)   ← dispatched synchronously
    │   ├─ QWindowSystemInterface::handleEnterEvent(QWindow_Dock,   ← dispatched synchronously
    │   │       localPos, globalPos)
    │   └─ qCDebug: "[MouseLeave] cross-window transition: old=Main new=Dock"
    │
    ├─ s_lastMouseWindow = QWindow_Dock             ← updated
    └─ onMouseEvent() → normal mouse movement handling

T4  The QPA event queue is processed:
    ├─ Leave(QWindow_Main) → QWidgetWindow_Main::handleEnterLeaveEvent(Leave)
    │   ├─ peeks the queue for an Enter → finds Enter(QWindow_Dock)
    │   ├─ thisParent(Main) == enterParent(Main) → TRUE (the same top-level hierarchy)
    │   ├─ enter = the DockWidget's top-level widget
    │   ├─ removeWindowSystemEvent(Enter)  ← removed from the queue and merged
    │   └─ dispatchEnterLeave(the DockWidget top-level, the Main top-level, globalPos)
    │        ├─ QEvent::Leave  → centralWidget  ✓ delivered
    │        └─ QEvent::Enter  → dockWidget     ✓ delivered
    │
    └─ Enter(QWindow_Dock) was merged away by T4's peek and isn't handled separately

══════════════════════════════════════════════════════════════════════

Result: ✓ Leave + Enter are delivered correctly through the static compensation + the QPA queue merge.
        It runs synchronously with no timing race.
```

---

## 6. Fix strategies

### 6.1 The three candidate strategies

#### Strategy A: the minimal change — remove only `sendQtHoverEvent(true)` and keep `(false)`

| Item | Notes |
|------|-------|
| **The idea** | Remove the source of asynchronous Enter interference (`true`) while keeping ArkUI's hover-leave as the source of Leave (`false`) |
| **Pros** | Keeps Leave delivery for the "the mouse leaves every window" scenario |
| **Cons** | ArkUI hover-leave is unreliable at XComponent boundaries (which is exactly what caused the original bug), and the race with the synchronous compensation remains |
| **Verdict** | ❌ Not viable — keeping `false` reintroduces the timing race |

#### Strategy B: the current implementation — remove both

| Item | Notes |
|------|-------|
| **The idea** | Disable the hover generator entirely and rely on the static compensation in `processMouseEventsInQtThread` for all Enter/Leave |
| **Pros** | No timing race; cross-window Leave is synchronous and reliable |
| **Cons** | No Leave in the "the mouse leaves every window" scenario (§3.2 scenario 4, MEDIUM risk) |
| **Verdict** | ✅ The current approach; it covers the main scenarios well |

#### Strategy C: the combined approach — keep `(false)` as a defensive layer + deduplication

| Item | Notes |
|------|-------|
| **The idea** | Keep `handleQOhosHoverEvent(false)` to handle the "leaves every window" scenario, using `s_lastMouseWindow` to deduplicate and avoid conflicting with the synchronous compensation |
| **Pros** | Covers scenario 4's blind spot while avoiding the timing race |
| **Cons** | `s_lastMouseWindow` has to be made public, increasing coupling; ArkUI hover-leave is still unreliable (it may be missed, but at least it won't be sent spuriously) |
| **Verdict** | ✅ Recommended — the most complete coverage |

### 6.2 The recommended strategy

**Pick strategy C**, because:

1. **It eliminates a known blind spot**: scenario 4 (the mouse leaves every window) is the only remaining MEDIUM risk, and strategy C covers it directly
2. **The deduplication is reliable**: checking `s_lastMouseWindow == the current window` tells you whether the compensation already ran, preventing a duplicate Leave
3. **An unreliable ArkUI hover-leave does no harm**: the worst case is a missed event (the same as strategy B), never a spurious one (the deduplication prevents it)
4. **The change is small**: just restore `handleQOhosHoverEvent(false)` and add the deduplication logic

### 6.3 The code changes required

See §7.

### 6.4 The test case list

| # | Test scenario | What to verify | Expected result |
|---|---------------|----------------|-----------------|
| 1 | centralWidget → DockWidget | Whether the Leave event fires | `leaveEvent()` is called |
| 2 | DockWidget → centralWidget (the reverse) | Whether the Leave event fires | `leaveEvent()` is called |
| 3 | Flicking quickly across windows | Intermediate events may be dropped, but the final Leave must arrive | No lingering hover state |
| 4 | The mouse moves out of the application window into the system area | The last Qt window receives a Leave | `underMouse()` returns false |
| 5 | Dragging a QDockWidget across windows | No compensation Leave fires during the drag | The state is correct after release |
| 6 | The mouse leaves after opening a popup menu | Leave works normally in popup mode | The menu item highlight is cleared correctly |
| 7 | The window is destroyed with the mouse over it | No crash and no spurious events | The application stays stable |
| 8 | Switching between multiple top-level windows | Leave/Enter between MainWindow ↔ Dialog | Both windows end up in the right state |
| 9 | Touchscreen operation (no hover) | No spurious Leave | Touch behaves normally |
| 10 | With `WA_NativeWindow` turned off | Behavior matches the no-`WA_NativeWindow` case | Leave is delivered normally through the alien path |

### 6.5 The rollout plan

1. **Local verification**: implement strategy C on the Qt 5.12 branch and verify all 10 test cases with the demo
2. **Regression testing**: cherry-pick the same change onto the Qt 5.15 branch and verify consistency
3. **Code review**: submit to Gerrit and ask the Qt OHOS team to review
4. **Merge**: once approved, merge into `tqtc/harmonyos-5.12.12` and `tqtc/harmonyos-5.15.16`

---

## 7. The list of key code changes (the recommended strategy C)

### 7.1 `qohosnativemouseeventshandler.h` — expose the static member

**The change**: move `s_lastMouseWindow` from private to public so `QOhosHoverEventsGenerator` can access it.

```cpp
// Before:
private:
    static QPointer<QWindow> s_lastMouseWindow;

// After:
public:
    // Accessed by QOhosHoverEventsGenerator's deduplication logic
    static QPointer<QWindow> s_lastMouseWindow;
```

### 7.2 `qohoshovereventsgenerator.cpp` — restore `handleQOhosHoverEvent(false)` and add deduplication

**Before** (the current code):

```cpp
void QOhosHoverEventsGeneratorImpl::handleQOhosHoverEvent(bool hovered)
{
    // [FIX] Removed sendQtHoverEvent(false)
    Q_UNUSED(hovered);
}
```

**After**:

```cpp
void QOhosHoverEventsGeneratorImpl::handleQOhosHoverEvent(bool hovered)
{
    if (!hovered) {
        // A defensive layer: when the mouse leaves the XComponent, check whether
        // processMouseEventsInQtThread already handled the Leave. If s_lastMouseWindow still
        // points at this window, no cross-window mouse movement triggered the compensation
        // (for example the mouse left every Qt window).
        m_qWindowRef.visitInQtThreadIfAlive(
            [](QWindow &window) {
                if (QOhosNativeNodeMouseInputHandler::s_lastMouseWindow.data()
                    == &window) {
                    qCDebug(QtForOhos)
                        << "[HoverGen] hover-leave compensation: window=" << &window;
                    QWindowSystemInterface::handleLeaveEvent(&window);
                    QOhosNativeNodeMouseInputHandler::s_lastMouseWindow = nullptr;
                }
                // else: the compensation already ran in processMouseEventsInQtThread, so skip
            });
    }
    // hovered=true isn't handled — Enter is compensated synchronously by processMouseEventsInQtThread
}
```

**The key design decisions**:

| Decision | Rationale |
|----------|-----------|
| Restore only `hovered=false`, not `hovered=true` | Enter is handled by the synchronous compensation; restoring the asynchronous Enter would reintroduce the timing race |
| Deduplicate using `s_lastMouseWindow` | If the compensation already ran, `s_lastMouseWindow` has been set to the new window or to nullptr |
| Use `visitInQtThreadIfAlive` | The hover callback runs on the ArkUI thread, so it must be dispatched to the Qt thread |
| Set `s_lastMouseWindow = nullptr` after deduplicating | To prevent a subsequent duplicate hover-leave callback from firing again |

### 7.3 `qohoshovereventsgenerator.h` — add the header reference

You need to forward-declare `QOhosNativeNodeMouseInputHandler` or include its header:

```cpp
#include <render/qohosnativemouseeventshandler.h>  // for access to s_lastMouseWindow
```

### 7.4 `qohosnativemouseeventshandler.cpp` — no changes

The current compensation logic stays as it is:

```cpp
// qohosnativemouseeventshandler.cpp:194-203 (no changes needed)
if (!eventHandler->isMouseGrabbed()
    && s_lastMouseWindow && s_lastMouseWindow.data() != targetWindow) {
    QWindow *oldWindow = s_lastMouseWindow.data();
    QWindowSystemInterface::handleLeaveEvent(oldWindow);
    QWindowSystemInterface::handleEnterEvent(
        targetWindow, mouseEvent.localPosition, mouseEvent.globalPosition);
}
s_lastMouseWindow = targetWindow;
```

### 7.5 `qohosinputmethodeventhandler.cpp` — no changes

Keep the existing `m_lastWindowLeft` defensive mechanism and don't add compensation code in this file.

---

## 8. Reusable lessons

### 8.1 The 5 lessons from this debugging session

**Lesson 1: cross-layer assumptions breed bugs**

The Qt widget layer assumes the QPA will deliver the Leave; the OHOS QPA assumes ArkUI will fire the hover callback. Two "the other one will do it" assumptions add up to "nobody does it".

> **The principle**: when an event is "skipped" in layer A in the expectation that layer B will deliver it, you must verify layer B can actually do so in every scenario.

**Lesson 2: asynchronous dispatch racing with synchronous handling**

`visitInQtThreadIfAlive`'s asynchronous dispatch races unpredictably with `processMouseEventsInQtThread`'s synchronous handling. In an event state machine, a duplicate Leave is more destructive than a missing one.

> **The principle**: if the same event has two sources (one asynchronous, one synchronous), either eliminate one source or add a reliable deduplication mechanism.

**Lesson 3: static variables are the last resort for sharing state across instances**

Each XComponent has its own handler instance, and instance members can't observe state changes across XComponents. A `static` variable does add global coupling, but it's safe under the constraint that only the Qt thread touches it.

> **The principle**: when several instances need shared state, prefer designing a singleton or a centralized tracker; if that isn't possible, `static` + a thread-safety constraint is a workable fallback.

**Lesson 4: the fix must go at the event's convergence point**

Round one put the code in `handleMouseEvent` (handling each event individually), where it couldn't see a cross-window transition. Round two put it in `processMouseEventsInQtThread` (the convergence point for all events), where it can see the whole batch and the window-level state.

> **The principle**: compensation code belongs where it can observe **all the relevant events**, not at some intermediate node in the event chain.

**Lesson 5: an empty implementation ≠ no effect**

Making `handleQOhosMouseEvent` and `handleQOhosHoverEvent` empty looks like "removing a feature", but it actually changed the topology of the whole Enter/Leave event flow. Every empty implementation should carry a comment explaining "why it's empty" and "who took over this responsibility".

> **The principle**: when you disable a mechanism, confirm the replacement covers every scenario the original did, including the edge cases.

### 8.2 Advice for future OHOS QPA maintainers

1. **OHOS is the only platform with no OS-level Leave** — any new window type or widget that needs Leave events has to be handled manually in the QPA layer
2. **ArkUI's hover callbacks are unreliable** — don't make them the only source of Leave events; always pair them with window-change detection on the mouse events
3. **The batching system drops old events** — compensation code can't depend on every event arriving; base it on the final state
4. **`s_lastMouseWindow` is global state** — when you modify it, consider every reader (currently two: `processMouseEventsInQtThread` and the restored `handleQOhosHoverEvent`)
5. **Testing must cover "the mouse leaves every window"** — that's the known weakest point of the current architecture

---

> **References**:
> - The Qt 5.12.12 source: `<LOCAL_PATH>`
> - The OHOS QPA plugin: `<LOCAL_PATH>`
> - Key commits in the git history: `96728a820e` (the original hover generator implementation), `26023a439c` (binding the hover generator to the mouse handler)
> - Related JIRA issues: QTFOROH-1835 (native node mouse/hover events), QTFOROH-501 (the initial Enter/Leave implementation)

---

## 9. Verification and deliverables (2026-06-09)

### 9.1 Manual verification results

| Status | Notes |
|--------|-------|
| ✅ **Passed** | Option 4 (static tracking + disabling the asynchronous dispatch + a defensive-layer Leave) was manually verified on an OHOS device |

### 9.2 Upstream deliverables

| Deliverable | Path | Notes |
|-------------|------|-------|
| ISSUE.md | `<WORK_DIR>/leave-event-fix/ISSUE.md` | A bilingual (Chinese/English) issue write-up (315 lines) |
| The clean patch | `<WORK_DIR>/leave-event-fix/patches/` | Only the 5 Leave event fix files, with the unrelated MDI trace / OHOS-BUG-TRIAGE changes excluded |
| A pure Qt demo | `<INTERNAL_DEMO>` | Works with Qt5/Qt6 and builds on the desktop |
| An OHOS project demo | `<INTERNAL_DEMO>` | A complete HarmonyOS project with the HAP already built |

### 9.3 Workflow closure

- [x] Phase one: the minimal reproduction demo builds and reproduces reliably
- [x] Phase two: the call chain has been traced to qwidgetwindow.cpp:468 + qohoshovereventsgenerator.cpp
- [x] Phase three: the root cause is localized (the dual blind spot + the asynchronous vs. synchronous conflict) and attributed to the Qt OHOS QPA plugin
- [x] Phase four: the deliverables are in `<WORK_DIR>/leave-event-fix/`
- [x] Knowledge captured: the retrospective is written up in this file
- [x] Workflow reinforced: phase four of the framework issue analysis methodology gained a patch cleanup and workflow closure checklist
