---
id: semantic-qt-harmonyos-window-model
type: semantic
domain: tech
tags: [qt, harmonyos, window, mainwindow, subwindow, tagging, floating, embedded, activateWindow, shiftAppWindowFocus, focus, highlight, transientParent]
created: 2026-06-02
updated: 2026-08-14
status: active
audience: public
refs: [fault-C-0009, fault-C-0014, semantic-qt-harmonyos-api, semantic-qt-ohos-extras, semantic-qt-harmonyos-code-patterns, episodic-ohostemplate-blockedbymodal-patch, problem-runtime-blocked-by-modal-window-no-parent]
summary: >
  The Qt QPA adapter for ArkUI Window/XComponent: MainWindow (has a Dock/task icon and an independent lifecycle) vs.
  Subwindow (no Dock icon, belongs to the main window, and closes/minimizes/restores with it). The core rules:
  the first window binds automatically, later windows default to new main windows, and tagging must happen before show/winId.
  Covers the QOhosFunctions API, 6 code patterns, floating windows, fullscreen rules, embedded subwindows, and cross-process embedding.
  Includes [the QPA layer] where visible comes from (QWindowPrivate::visible), the OHOS system callback chain
  (window.on('windowEvent') → WINDOW_SHOWN/HIDDEN/ACTIVE/INACTIVE),
  all 7 places that modify visible, the QOhosFloatingWindow naming trap, and the floating window hide-destroy chain (setOrResetWindowProxy → destroyWindow).
  Includes [activation semantics] activateWindow() → @ohos.window.shiftAppWindowFocus (not showWindow!), asynchronous at ~94 ms,
  the D1 no-op gap (silently does nothing when there is no focus_window), and focus state ≠ activation state (a greyed title ⇒ no focus ⇒ Tab doesn't respond).
  For details see the postmortems under episodic/postmortems/ (internal documents).
---

# The Qt QPA adapter for the ArkUI window model

> See also the window-related API differences in [[semantic-qt-harmonyos-api]], the QtOhosExtras module in [[semantic-qt-ohos-extras]], and the complete code patterns in [[semantic-qt-harmonyos-code-patterns]].
> For the platform boundaries of WindowStage/main/subwindow, XComponent/native surface, focus, and the visible and drawable states, the common library's [[ohos-common-kb/semantic/arkui-window-xcomponent-model|ArkUI window and XComponent hosting model]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/arkui-window-xcomponent-model.md)) is authoritative. This page covers QPA tagging, `QWindowPrivate::visible`, Qt exposure/activation, the floating window destruction chain, and the Qt API patterns.

## Qt QPA mapping concepts

Qt QPA maps the platform's window relationships onto a **Main Window** and a **Subwindow**, and adds tagging, transient parents, and fallback behavior on top. The platform concepts themselves are defined in the common library; what follows only describes the observable behavior after the Qt mapping.

### Main Window

- Represents an independent **task**, corresponding to a "task window" at the HarmonyOS Ability level
- **Has a Dock icon** — visible in the system Dock
- **Has a task icon** — appears separately in the Alt+Tab switcher
- **Has an independent lifecycle** — it isn't attached to any other window
- Supports the full set of window operations: maximize, minimize, restore (windowed)
- Typical uses: an application's main interface window, an independent multi-document editor window

### Subwindow

- An **independent top-level window** hosting a sub-feature — note: this is not a Qt "child widget" but a genuinely independent window
- **Has no Dock icon** — it doesn't appear in the system Dock
- **Has no task icon** — it isn't visible in the Alt+Tab switcher
- **Must belong to a main window** — associated through tagging or a transient parent
- Its lifecycle is controlled by the main window:
  - The main window closes → the subwindow **closes automatically**
  - The main window minimizes → the subwindow **hides automatically**
  - The main window restores → the subwindow **shows automatically**
- Typical uses: dialogs, tool panels, popup menus, hint overlays

> **The key insight**: "sub" in Subwindow refers to an ownership relationship at the system level, not to a parent-child relationship in the Qt widget hierarchy. A `QWidget` can become a subwindow through tagging even if it has no Qt parent.

## Core rules

### The first window rule (the first window binds automatically)

The **first** `QWindow` (or parentless `QWidget`) created in the process **binds automatically** to the first main window the system allocates — no extra work required.

```cpp
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    MainWindow w;
    w.show(); // the first window, bound automatically to the system-allocated main window
    return app.exec();
}
```

This is both the most common and the simplest case — the vast majority of single-window applications only need `show()`.

### The subsequent windows rule (later windows default to new main windows)

Any `QWindow`/`QWidget` created after the first one that has **no parent** and **hasn't been tagged as a subwindow** automatically becomes a **new main window** (with its own Dock icon and task icon).

```cpp
void MainWindow::openNewMainWindow() {
    MainWindow *newWin = new MainWindow();
    newWin->show(); // not tagged → automatically becomes a new main window
}
```

If you want a later window to exist as a subwindow, you **must** tag it manually before `show()`.

### The tagging function

```cpp
#include <QtPlatformHeaders/QOhosFunctions>

QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(
    QObject *windowOrWidgetToTag,  // the window or widget to tag as a subwindow
    QWindow *mainWindow            // the main window it belongs to
);
```

**Strict ordering requirements**:

1. **It must be called after the main window is created** — the `mainWindow` argument must be an already-created `QWindow`
2. **It must be called before the subwindow's `show()`** — once the window is shown, the tag no longer takes effect
3. **It must be called before the subwindow's `winId()`** — `winId()` forces creation of the native handle, at which point the window's properties are already fixed

```cpp
// The right order
QWidget *panel = new QWidget();
QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(panel, mainWindow->windowHandle());
panel->show();  // tagging before show ✓

// The wrong order
QWidget *panel = new QWidget();
panel->show();  // already shown
QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(panel, mainWindow->windowHandle()); // ✗ no effect!
```

If the `mainWindow` argument is invalid (for example already destroyed), certain window types trigger an automatic fallback (see below).

### Transient parent (automatic binding)

For controls that natively support a transient parent (such as `QDialog`), if you pass a parent widget at construction time, Qt **automatically** makes the parent's main window the subwindow's owner — **no manual tagging needed**.

```cpp
// The recommended approach: pass a parent and it binds automatically
QDialog *dlg = new QDialog(this); // 'this' is the main window or one of its child widgets
dlg->exec(); // no tagging needed
```

This is the recommended way to use dialogs — both concise and safe.

### Auto-fallback

When the `mainWindow` given to tagging is invalid, an automatic fallback kicks in for these window types:

- `Qt::Popup`
- `Qt::ToolTip`
- `Qt::Dialog`
- `Qt::Tool`

The fallback strategy:
1. **Prefer the currently focused window** as the owning main window
2. If there is no focused window, use the **first available top-level window**
3. This ensures every window finds an owner and avoids "orphan" main windows

> **Note**: a plain `Qt::Window` **does not** trigger the auto-fallback. If `mainWindow` is invalid and the window type is `Qt::Window`, that window becomes a new main window.

### Known gap: the QPA doesn't write syntheticParent back to transientParent

The OHOS QPA's `determineViewTypeAndLogicalParent()` uses the syntheticParent fallback to classify parentless Dialog/Tool/Popup/ToolTip windows
as SubWindows, and establishes the ownership at the ArkUI layer through `createSubWindow()`. **But the OHOS QPA never calls `QWindow::setTransientParent()` to write
the syntheticParent back to the Qt layer** (grepping qohosview.cpp confirms zero calls).

The consequences:
- `transientParent()` is still null at the Qt layer
- `isWindowBlocked()`'s `isAncestorOf(IncludeTransients)` check fails
- `blockedByModalWindow = 1` → blocks `close()` and `processWheelEvent()`

**Impact**: any parentless `QDialog()` can't be closed and won't scroll while a modal sibling window exists.
**Fix**: a Qt source patch writes the transientParent back in `showImmediate()` — see [[episodic-ohostemplate-blockedbymodal-patch]].

> **Compared with Win32**: Windows' `CreateWindowEx(parent=NULL)` automatically sets owner=GetActiveWindow(), a safety net at the system level.
> OHOS has no equivalent safety net, so Qt has to maintain that relationship itself at the QPA layer. The blockedByModalWindow logic chain is the same on both sides; the only difference is that safety net.

## API reference

All the window-related APIs live in the `QOhosFunctions` class:

```cpp
#include <QtPlatformHeaders/QOhosFunctions>
```

| API | Description |
|-----|-------------|
| `tagWindowOrWidgetAsSubWindowOf(QObject *windowOrWidget, QWindow *mainWindow)` | Tags a window as a subwindow of the given main window. Must be called before `show()`/`winId()` |
| `tagWindowOrWidgetAsMainWindow(QObject *windowOrWidget, bool forceMainWindow = true)` | Explicitly tags a window as a main window. With `forceMainWindow=true` it overrides any existing tag |
| `getWindowOrWidgetAsSubWindowOfTagValue(QObject *target)` | Queries which main window the given window is currently tagged as a subwindow of, returning the owning `QWindow*` |
| `setInAppOnlyPasteboardShareOption(QObject *windowOrWidget, bool inAppOnly)` | Sets the clipboard sharing scope: `true` for in-app sharing, `false` for cross-application sharing |

## 6 common code patterns

### Pattern 1: a single-main-window application

The most common case. The first window binds automatically to the system main window.

```cpp
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    MainWindow w;
    w.show(); // the first window binds automatically → a main window
    return app.exec();
}
```

**The point**: no tagging and no extra API calls needed.

### Pattern 2: a dialog with a parent (no tagging needed)

Pass a parent widget when constructing the `QDialog` and Qt handles the transient parent binding automatically.

```cpp
void MainWindow::showAboutDialog() {
    QDialog *dlg = new QDialog(this); // this = the main window widget
    dlg->exec(); // binds automatically to the main window this belongs to
}
```

**The point**: this is the recommended way to pop up a dialog.

### Pattern 3: a parentless dialog (needs manual tagging)

When a dialog has no parent you must tag it manually to make it a subwindow.

```cpp
void MainWindow::showSettingsDialog() {
    QDialog *dlg = new QDialog(); // no parent
    QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(
        dlg, this->windowHandle());
    dlg->exec(); // tagging before exec
}
```

**The point**: tagging must be done before `exec()` (which calls `show()` internally).

### Pattern 4: a multi-main-window application

When you need several independent top-level windows, just `show()` without tagging to create a new main window.

```cpp
void MainWindow::openNewMainWindow() {
    MainWindow *newWin = new MainWindow();
    newWin->show(); // no tagging → a new main window (with its own Dock icon)
}
```

**The point**: every new main window gets its own Dock icon and Alt+Tab entry.

### Pattern 5: a tool panel subwindow

Create a tool panel as a subwindow of the current main window.

```cpp
void MainWindow::openToolPanel() {
    QWidget *panel = new QWidget();
    panel->setWindowTitle("Tools");
    QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(
        panel, this->windowHandle());
    panel->resize(400, 300);
    panel->show(); // shown as a subwindow
}
```

**The point**: the tool panel follows the main window automatically when it closes or minimizes.

### Pattern 6: a floating window

Create a floating window that sits on top of other applications.

```cpp
void MainWindow::openFloatingTool() {
    QWidget *tool = new QWidget();
    QtOhosExtras::setShowWindowAsFloatWindowHint(tool, true);
    tool->setAttribute(Qt::WA_DeleteOnClose);
    tool->resize(300, 300);
    tool->show();
}
```

**The point**: `setShowWindowAsFloatWindowHint` must be called before `show()`. See the "Floating windows" section below.

## Floating windows

A floating window is a special window type that can be displayed on top of other applications and isn't affected by minimizing.

### How to use it

```cpp
#include <QtOhosExtras>

QWidget *tool = new QWidget();
// the floating window hint must be set before show()
QtOhosExtras::setShowWindowAsFloatWindowHint(tool, true);
tool->setAttribute(Qt::WA_DeleteOnClose);
tool->resize(300, 300);
tool->show();
```

### Constraints and caveats

- **Requires a permission**: the application must request the `ohos.permission.SYSTEM_FLOAT_WINDOW` floating window permission, or creating the floating window fails
- **Supports subwindows**: modal and modeless subwindows can pop up on top of a floating window
- **An independent display layer**: a floating window is unaffected by the main window minimizing and always stays on top
- **Ordering requirement**: `setShowWindowAsFloatWindowHint()` must be called before `show()`; it can't be changed once the window is displayed
- **`hide()` destroys the native window**: calling `hide()` on a floating window synchronously destroys the native OHOS Window (`Window.destroyWindow()`), yet `isVisible()` is still `true` while `isExposed()` becomes `false`, and calling `show()` again rebuilds it. This differs from a main window's `hide()` (which goes through `hideMainWindow()` to minimize and doesn't destroy anything). See §"The floating window hide-destroy chain" in the QPA layer section below

## Full-screen main windows

HarmonyOS imposes different fullscreen restrictions on the first window and on later windows.

### The first window: can't go fullscreen directly

```cpp
// The first window has to do it in two steps
MainWindow w;
w.show();             // step one: show it in standard mode first
w.showFullScreen();   // step two: then switch to fullscreen
```

**Why**: HarmonyOS requires the first window to complete the Ability's initialization flow (including window creation and the first render) before the display mode can be switched.

### The second and later windows: can go fullscreen directly

```cpp
void MainWindow::openFullScreenWindow() {
    QWidget *fs = new QWidget();
    // tagging is required, or it becomes a new main window
    QOhosFunctions::tagWindowOrWidgetAsSubWindowOf(
        fs, this->windowHandle());
    fs->showFullScreen(); // straight to fullscreen, no need to show() first
}
```

## Window geometry persistence

Used to persist the main window's position and size on 2-in-1 devices (tablet/laptop hybrids).

```cpp
#include <QtOhosExtras>

// must be called before the first main window's show()
QtOhosExtras::setMainWindowGeometryPersistenceHint(...);

MainWindow w;
w.show(); // the window restores the geometry saved last time
```

**Limitations**:
- Only takes effect on **2-in-1 devices**
- Must be set **before the first main window's `show()`**
- The API has no effect on ordinary phones

See the window-related API documentation in [[semantic-qt-ohos-extras]].

## Embedded subwindows

When you need to embed a third-party renderer (CEF/Chromium Embedded Framework, SDL, etc.) in a Qt window, you need the native window handle.

### Getting the native handle with `winId()`

```cpp
class NativeRendererHost : public QWidget {
public:
    void bindRenderer() {
        WId wid = winId(); // force creation of the native window handle
        // pass wid to the third-party renderer to bind
        // third_party_renderer_bind(wid);
    }
};
```

### HarmonyOS caveats

> **Note**: on HarmonyOS the value returned by `winId()` is **not** a real native window handle (unlike Windows/Linux). To get the real native handle, use `QtOhosExtras::tryGetNativeWindowId()`.

See the platform differences in [[semantic-qt-harmonyos-api]].

## Cross-process embedding

A Qt application can act as a **provider** and be embedded for display by another host application through the UIExtension mechanism. This is a HarmonyOS-specific cross-process UI embedding capability.

### Basic usage: single-instance mode

```cpp
// The provider side (the embedded Qt application)
#include <QEmbeddedUiExtensionAbility>

// Declare it as a UIExtension in the Ability configuration
// configure extensionAbilities in module.json5
```

### Multi-instance mode: using a binding key

When the same Qt application needs to provide different UI instances to different hosts, distinguish them with a binding key:

```cpp
#include <QtOhosExtras>

// Create window A, bound to key "A"
auto *windowA = createWindowA();
QtOhosExtras::setBundledAbilityAndQWindowBindingKeyForQWindow(
    windowA->windowHandle(), "A");
windowA->show();

// Create window B, bound to key "B"
auto *windowB = createWindowB();
QtOhosExtras::setBundledAbilityAndQWindowBindingKeyForQWindow(
    windowB->windowHandle(), "B");
windowB->show();
```

**The points**:
- `setBundledAbilityAndQWindowBindingKeyForQWindow()` must be called before `show()`
- The binding key must match the UIExtension's `metadata` configuration in `module.json5`
- Each binding key corresponds to one independent window instance

## Decision quick reference

| Scenario | What to do | Tagging needed? |
|----------|------------|-----------------|
| The application's first window | `w.show()`, bound automatically | No |
| A dialog with a parent | `new QDialog(this)` | No |
| A parentless dialog | `tagWindowOrWidgetAsSubWindowOf()` then `exec()` | **Yes** |
| A new independent main window | Don't tag; just `show()` | No (deliberately a main window) |
| A tool panel subwindow | `tagWindowOrWidgetAsSubWindowOf()` then `show()` | **Yes** |
| A floating window | `setShowWindowAsFloatWindowHint()` then `show()` | No (uses the floating window hint) |
| A fullscreen window (the first one) | `show()` → `showFullScreen()`, two steps | No |
| A fullscreen window (a later one) | Tag, then `showFullScreen()` directly | **Yes** |
| Embedding a third-party renderer | `winId()` to get the handle | Depends |
| Being embedded by another application | UIExtension + a binding key | No |

## The QPA layer: where visible comes from and the system callback chain

> **When you need this**: debugging QPA internals such as "why doesn't isVisible() match what I expect on the main window" or "what happens to the Qt-side state after the system hides the window". Source baseline: Qt 5.12.12 OHOS (commit `613336de`).
>
> **The key conclusion**: `visible` is an **application-controlled** property, and there is only one place the system side can change it (and it's a HACK). When the system hides or minimizes a window it does **not** set `QWindow::isVisible()` to false — what it changes is `isExposed()`, `windowState`, and `ApplicationState`.

### Where visible is stored and the only function that writes it

| Item | Location |
|------|----------|
| The data member | `QWindowPrivate::visible` (a `bool` bitfield, `qwindow_p.h`) |
| Public read | `QWindow::isVisible()` → returns `d_func()->visible` |
| Q_PROPERTY | `qwindow.h:121` `READ isVisible WRITE setVisible NOTIFY visibleChanged` |
| **The only write** | `QWindowPrivate::setVisible(bool)` `qwindow.cpp:341` (`this->visible = visible` @346) |

`QWindow::setVisible()` (`qwindow.cpp:619`) is just a thin wrapper around `d->setVisible(visible)`; `show()`/`hide()`/`showFullScreen()` and friends all funnel through here.

### The system callback interface (OHOS → Qt)

The platform window class for a HarmonyOS main window is **`QOhosFloatingWindow`** (a misleading name — it hosts **all top-level windows**: main windows, subwindows and floating windows alike; see `qohosplatformintegration.cpp:334`). In `initialize()` (`qohosfloatingwindow.cpp:125`) it connects to the `QOhosView::windowEvent` signal, which originates in callbacks from the native OHOS `Window` object.

The handlers Qt registers on the native window from the JS side (`qohoswindowproxy.cpp:280-314`):

| The native OHOS callback | The handler | What it maps to in Qt |
|--------------------------|-------------|-----------------------|
| **`window.on('windowEvent')`** | `handleWindowEventCallback` | `WINDOW_SHOWN/HIDDEN/ACTIVE/INACTIVE/DESTROYED` (`qohoswindowproxy.h:38`) |
| `window.on('windowStatusChange')` | `handleWindowStatusCallback` | `windowState` — fullscreen/maximized/minimized etc. |
| `window.on('windowVisibilityChange')` | `handleWindowVisibilityCallback` | The visibility-changed signal |

> **"Which system callback interface"** = OHOS's `window.on('windowEvent')` (corresponding to the `WindowEventType` enum in ArkTS's `@ohos.window`).

### How the WINDOW_* events affect visible / exposure / state

The event dispatch in `QOhosFloatingWindow::initialize()` (`qohosfloatingwindow.cpp:162-214`):

| Event | Effect on visible | Effect on other state |
|-------|-------------------|-----------------------|
| `WINDOW_ACTIVE` | None | `handleWindowActivated()` + the input system activates |
| `WINDOW_INACTIVE` | None | Loses focus + the input system deactivates |
| `WINDOW_HIDDEN` | **None** (only `setExposedFromOhos(false)`) | `m_exposed=false`, the render surface is unusable |
| `WINDOW_SHOWN` | **Calls `setVisible(true)` only if "the previous event was HIDDEN and !isVisible() right now"** (a HACK that corrects the state) | `setExposedFromOhos(true)` |
| `WINDOW_DESTROYED` | None | `notifyWindowDestroyedFromOhos()` |

**The key point**: the `WINDOW_HIDDEN` branch (`qohosfloatingwindow.cpp:187-193`) never touches `visible`. When the system hides a window, `isVisible()` stays `true` — which is exactly why iron rule W5 holds (`hide()` degrades to minimizing).

The one HACK where the system side modifies visible (`qohosfloatingwindow.cpp:194-203`):
```cpp
case WINDOW_SHOWN:
    // Fix for the Qt side still being hidden after QWidget::hide() when the window is pulled back from the Dock
    if (previousWindowEventType == WINDOW_HIDDEN && !qWindow->isVisible())
        qWindow->setVisible(true);
```

> Aside: when a subwindow or floating window is `hide()`n, Qt **synthesizes** `WINDOW_HIDDEN` itself (`qohosview.cpp:1143-1156`), while main windows go through `hideMainWindow()`.

#### The floating window hide-destroy chain (setOrResetWindowProxy → destroyWindow)

> The `WINDOW_HIDDEN` branch above only covers the event dispatch side (`setExposed`). Hiding a floating window also destroys the native window **before** it synthesizes `WINDOW_HIDDEN` — that's the real reason "hide destroys the native window".

`QOhosView::hide()` (`qohosview.cpp:1143`) branches on viewType:

| viewType | The hide() path | Does it destroy the native window? |
|----------|-----------------|------------------------------------|
| MainWindow | `hideMainWindow()` (`qohosview.cpp:1147`) | No (minimized / hidden by the system) |
| **FloatWindow / SubWindow** | `setOrResetWindowProxy(nullptr, nullptr)` + synthesizing an emit of `WINDOW_HIDDEN` (`qohosview.cpp:1152-1156`) | **Yes** |

`setOrResetWindowProxy(nullptr,…)` (`qohosview.cpp:1669`) calls `m_ohosWindowProxy.reset()`. `QWindowProxyRegistry` only stores the `jsWindowId↔internalWindowId` mapping and doesn't hold a `QOhosWindowProxy` reference (it returns a `makeDestroyNotifier`, `qwindowproxyregistry.cpp:60`), so the proxy is **destroyed immediately** → `~QOhosWindowProxy` (`qohoswindowproxy.cpp:340`) → `m_jsScopeData.reset()` → `jsWindowRef->eval("destroyWindow()")` (`qohoswindowproxy.cpp:1436`) **destroys the native OHOS Window**.

| Object | After a floating window's `hide()` | After `show()` again |
|--------|-----------------------------------|----------------------|
| The native OHOS Window | **Destroyed** (destroyWindow) | Rebuilt |
| QOhosWindowProxy | **Destroyed** (the shared_ptr is reset) | Rebuilt (setOrResetWindowProxy with a non-null value) |
| The QOhosFloatingWindow platform window | Kept (it doesn't go through `QWindowPrivate::destroy`) | Reused |
| The QWindow/QWidget object | Kept (`isVisible()` is still true) | — |

> **Practical impact**: hiding a floating window isn't a "cheap stow away" — it costs a native window destruction plus a rebuild, so it's unsuitable for frequent show/hide cycles. After hiding, `isVisible()` is still true but the native window is gone, so touching `winId()` at that point triggers a rebuild (iron rule W1). There is no ready-made API for a genuinely cheap "keep the native window, just make it invisible" stow away (`showMinimized()` on a main window isn't supported for subwindows or floating windows).

### The 7 places that can modify visible

| # | Call site | Origin | When it fires |
|---|-----------|--------|---------------|
| 1 | `QWindow::setVisible()` `qwindow.cpp:619` | **The application layer (the main entry point)** | `show()/hide()/showFullScreen()/QWidget::setVisible` |
| 2 | `QWindowPrivate::setTopLevelScreen` `qwindow.cpp:510` | kernel | Restoring visibility after a screen change/rebuild |
| 3 | `QWindowPrivate::create` `qwindow.cpp:552` | kernel | Showing a lazily-created subwindow |
| 4 | `QWindow::setParent` `qwindow.cpp:733` | kernel | Reapplying visibility after the parent window changes |
| 5 | `QWindowPrivate::destroy` `qwindow.cpp:1909` | kernel | `close()`/destruction → `setVisible(false)` |
| 6 | **The `WINDOW_SHOWN` HACK** `qohosfloatingwindow.cpp:202` | **The OHOS system → Qt (the only system path)** | The system pulls the window back up after a hide; corrects the state |
| 7 | `QOhosView` subwindow creation `qohosview.cpp:429` | QPA-driven | When creating a subwindow, if the parent window is hidden it is automatically `setVisible(true)` |

### WMS and Qt's visibility state machines are independent (added 2026-07-16)

> **⚠️ Important**: HarmonyOS's window visibility management (WMS) and Qt's visibility state (WA_WState_Hidden) are **two independent state machines**.

The system can change a window's visibility directly through WMS (e.g. GoForeground, or file acceleration pushing a window to the foreground) **without going through Qt's show()/setVisible(true) path**, leaving Qt's Hidden flag out of sync with the system's actual state.

```
┌─────────────┐     ┌──────────────┐
│ System WMS  │     │  The Qt side │
│             │     │              │
│ Window shown│     │ Hidden=1     │
│(GoForeground)│    │ (thinks it's │
│             │     │  hidden)     │
│             │     │ Not rendering│
└─────────────┘     └──────────────┘
       │                   │
       └── out of sync ────┘
              → a white screen
```

**Where this bites**:
- File acceleration (task_manager_service pre-launches the application in the background, and after the application calls hide() the system pushes the window to the foreground)
- Restoring from the system Dock (under certain timings)

**Troubleshooting advice**: when you hit a white screen, first check whether the application side correctly called `show()`/`setVisible(true)`, and only then consider a Qt QPA-layer fix. See the white-screen postmortem for details.

### Scenarios where the WINDOW_HIDDEN/SHOWN events are unreliable (added 2026-07-16)

> **⚠️ Important**: the `WINDOW_HIDDEN`/`WINDOW_SHOWN` events **do not fire** in these scenarios:
> - File acceleration (task_manager_service pre-launching in the background)
> - When the system manages window visibility directly through WMS

**Don't rely on these events as the only trigger for state synchronization.**

Device log evidence (the Wondershare file acceleration scenario, 32 files, ~160 MB of hilog):
- `WINDOW_HIDDEN` occurrences: **0**
- `WINDOW_SHOWN` occurrences: **0**
- `OHOS-HIDE-DEBUG` (QWidget instrumentation): **780+** (proving the patched libqohos.so was deployed)

See the white-screen postmortem and the Wondershare white-screen postmortem.

### Easily confused concepts (visible / visibility / exposed / appState)

When troubleshooting window visibility problems, first separate these four independent concepts and don't conflate them:

| Concept | Meaning | What happens when the system hides the window |
|---------|---------|-----------------------------------------------|
| `isVisible()` (the `visible` bool) | Whether the application "wants to show" this window | **Unchanged, stays true** |
| `visibility` (the enum) | Derived from `visible` + `windowState`: Hidden/Windowed/Minimized/FullScreen | May become Minimized |
| `isExposed()` (`m_exposed`) | Whether the render surface is drawable | → false |
| `ApplicationState` | Whether the application as a whole is in the foreground (Active/Inactive/Hidden) | → Inactive/Hidden in the background |

---

## Activation semantics (activateWindow → shiftAppWindowFocus, asynchronous + the D1 no-op gap)

> **When you need this**: debugging "the window title is still grey after `activateWindow()` / Tab doesn't respond / Qt's isActiveWindow doesn't match the OS". Source baseline: Qt 5.12.12 OHOS (commit `613336de`). For the device evidence and the full retrospective see the postmortems under episodic/postmortems/ (internal documents).
>
> **The key correction**: on OHOS, `QWidget::activateWindow()` does **not** call `showWindow()` — it calls `@ohos.window.shiftAppWindowFocus(srcWindowId, targetWindowId)`.

### The call chain (verified line by line)

```
QWidget::activateWindow()           qwidget.cpp:12908-12914   → wnd->requestActivate()
QWindow::requestActivate()           qwindow.cpp:1124-1133     → platformWindow->requestActivateWindow()
QOhosFloatingWindow::requestActivateWindow()   qohosfloatingwindow.cpp:258-266
QOhosPlatformWindow::requestActivateWindow()   qohosplatformwindow.cpp:486-494  → view->requestActivate()
QOhosView::requestActivate()        qohosview.cpp:1025-1044    ← ★ the D1 no-op gap
QOhosWindowProxy::shiftAppWindowFocus()   qohoswindowproxy.cpp:1835-1852
  → JS eval "@ohos.window.shiftAppWindowFocus(srcWindowId, targetWindowId)"  (qohoswindowproxy.cpp:1846-1847)
```

`showWindow(*)` (qohoswindowproxy.cpp:656) belongs to the `raise(MainWindow)`/`lower`/`show` path (called from qohosview.cpp:734) and **has no call relationship with activateWindow**. OHOS splits "activation" into two independent primitives — "shifting focus" (`shiftAppWindowFocus`) and "showing/raising" (`showWindow`/`raiseToAppTop`) — with no combined activeWindow equivalent; but `shiftAppWindowFocus` is the equivalent interface for "moving focus between windows of the same application".

### Key characteristic 1: asynchronous (~94 ms, not synchronous)

`shiftAppWindowFocus` is a JS Promise. After `activateWindow()` returns synchronously, `isActiveWindow()` is **still false**; ~94 ms later OHOS sends back `WINDOW_ACTIVE` → `QOhosFloatingWindow::handleWindowEvent` (qohosfloatingwindow.cpp:277) → `QWindowSystemInterface::handleWindowActivated` (qohosfloatingwindow.cpp:292), and only then does Qt mark it active.

Device evidence (in the foreground, clicking the main window to grey out the dialog and then calling activateWindow):
```
before-activate:    dialog isActiveWindow=false  focusWindow="MainWindow"   ← before the synchronous call
after-activate(sync):  dialog isActiveWindow=false  focusWindow="MainWindow"   ← ★ still false synchronously
(+94ms) dialog(widget) eventFilter type=WindowActivate                    ← the asynchronous WINDOW_ACTIVE round trip
after-activate(150ms): dialog isActiveWindow=true  focusWindow="Child Dialog"  ← ★ only true after 150 ms
```

→ **Don't check `isActiveWindow()` synchronously after `activateWindow()`**; wait for the `WindowActivate` event or delay ~150 ms.

### Key characteristic 2: the D1 no-op gap (silently does nothing when there's no focus_window)

`QOhosView::requestActivate()` (qohosview.cpp:1025-1044) **does nothing at all** when `m_ohosWindowProxy!=null` and `QGuiApplicationPrivate::focus_window==null` (the if at :1028 is false and the branch has no else) → `shiftAppWindowFocus` is never sent (the source window must have focus, and without one nothing is sent).

→ **When the app is in the background or unfocused (focus_window=null), `activateWindow()` is a silent no-op**, the dialog never becomes active, and Tab can't reach it. This is the real reproduction scenario for "Tab doesn't respond" (see scenario 2 of the retrospective). It's a genuine OHOS QPA defect.

**Fixed on 2026-08-12 (the option A hotfix)**: the `focus_window==null` branch of `requestActivate` gained an else that tries `shiftAppWindowFocus` from the logical parent (using main as the source, which may silently fail in onCatch) plus a `sendAsyncSyntheticWindowActiveEvent()` synthetic-event fallback that sets the Qt-side focus_window=dialog. Verified against D1 in the background (isActiveWindow false→true, with the synthetic event triggering WindowActivate). The patch is in the postmortems under episodic/postmortems/ (internal). The alternative, option D, was a synthetic event + a deferred shiftAppWindowFocus once the main window's WINDOW_ACTIVE arrives, which would fix focus transfer at the WMS level properly.

### Key characteristic 3: focus state ≠ activation state (per the official window-focus-guide)

| Concept | Meaning | What you see |
|---------|---------|--------------|
| Focus state | WINDOW_ACTIVE/INACTIVE — whether it can receive keyboard events | Tab not responding = not focused |
| Activation (highlight) state | Visual highlighting (the title bar color) | **A grey title = activation state false** |

**The iron rule**: "a window being in the activation state doesn't mean it has focus; but a focused window is always in the activation state." The contrapositive: **a grey title (not activated) ⇒ definitely not focused ⇒ Tab doesn't respond** (all three symptoms share a cause). To make the title bright the window must be **focused** (`shiftAppWindowFocus`), not `setExclusivelyHighlighted` (which only changes the appearance).

### Key characteristic 4: touch vs. mouse (NODE_FOCUS_ON_TOUCH, a structural difference)

> Measured on a device: touching a button and calling `activateWindow()` activates the dialog **on the first try**; clicking the button with a mouse **fails the first time and succeeds the second**. The root cause is structural, not an occasional timing fluke.

- XComponent has 3 independent callbacks: Touch (`DispatchTouchEvent`, qqtembeddedwindownode.cpp:66-71) / Mouse (`DispatchMouseEvent`, :73-76) / Focus-Blur (`handleOnFocusEvent`, :86-87).
- **`NODE_FOCUS_ON_TOUCH`** (qnativenode.cpp:169 `focusOnTouch=true`, setAttributeOrFail :271): on a **finger touch**, ArkUI makes the node request focus → `handleOnFocusEvent` (qqtembeddedwindownode.cpp:181) → `qohosinputmethodeventhandler.cpp:333 handleWindowActivated(main)` → **focus_window=main is set before touch→clicked()** → activateWindow() sees focus_window=main → shiftAppWindowFocus succeeds.
- **A mouse doesn't trigger NODE_FOCUS_ON_TOUCH** (in ArkUI "touch" means a finger specifically) → no focus callback → focus_window stays null → **you hit characteristic 2's D1 no-op** → the first click fails; by the second click the WMS `WINDOW_ACTIVE` (asynchronous; the docs say "the state after the click event has been processed") has arrived → focus_window=main → it succeeds.

→ **Touch naturally sidesteps D1 (NODE_FOCUS_ON_TOUCH presets focus_window) while the mouse walks right into it (it has no such bypass)**. That's the structural root cause of the touch/mouse activation asymmetry in the OHOS QPA. After the option A fix, the first mouse click falls back to the synthetic event (equivalent to the touch path).

### `shiftAppWindowFocus` constraints (per the official arkts-apis-window-f)

1. Only between the main window and subwindows of the same application (you can't actively activate across applications or processes)
2. **The source window srcWindowId must be focused** (→ the documented root cause of the D1 no-op)
3. The target must have `setWindowFocusable(true)` and a `showWindow()` that succeeded and completed
4. `ShowWindowOptions.focusOnShow` **has no effect on main windows, modal windows or dialog windows** (only subwindows, system windows and floating windows get focus by default)

### A modeless child dialog doesn't hit the isWindowBlocked redirect

The guard at `qohosfloatingwindow.cpp:280-284` (inside the `WINDOW_ACTIVE` branch) only redirects activation back to the modal window when qWindow is blocked by some **modal** window. A modeless child dialog has no modal blocker → `isWindowBlocked=false` → the guard doesn't fire → normal activation. (You only hit it in modal scenarios — see the modalraise retrospective (internal).)

### Workarounds

- **Make sure the app is in the foreground** (focus_window is non-null) before calling `activateWindow()`; in the background it's a no-op, so use `startAbility` to bring it to the foreground first and then activate.
- `activateWindow()` is asynchronous, so `isActiveWindow()` is necessarily false synchronously; wait for `WindowActivate` or delay ~150 ms.
- A grey title ⇒ no focus; to brighten the title the window must gain focus (`shiftAppWindowFocus`), not `setExclusivelyHighlighted`.
- There is no application-side API for cross-application activation; you can only use `startAbility` or rely on the user clicking.

---

## References

| Source type | Notes |
|-------------|-------|
| 🛠️ Qt source verification | The QPA plugin `qtohosextras`/ohos: `qohosfloatingwindow.cpp`, `qohoswindowproxy.cpp`, `qohosview.cpp`, `qohosplatformintegration.cpp`; Qt GUI `qwindow.cpp`/`qwindow_p.h` (the visible chain, commit `613336de`) |
| 💼 Working experience | Accumulated from day-to-day Qt for HarmonyOS development |
