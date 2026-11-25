# QWidget::screen() API version mismatch (Qt 5.14+ on a Qt 5.12 SDK)

> ID: build-fix-06
> Date: 2026-09-28 (based on actual build)
> Files involved: `pages/s11_dialog_dock_center.cpp`, `pages/c3_dialog_dock.cpp`,
> `pages/c7_dialog_upperhalf.cpp`
> Project root: `QtBugDemo-official/`
> Status: Not fixed

## 1. Error

```
FAILED: CMakeFiles/qtbugdemo.dir/pages/s11_dialog_dock_center.cpp.o
s11_dialog_dock_center.cpp:37:38: error: no member named 'screen' in 'QWidget'
s11_dialog_dock_center.cpp:37:57: error: no member named 'screen' in 'QWidget'

FAILED: CMakeFiles/qtbugdemo.dir/pages/c3_dialog_dock.cpp.o
c3_dialog_dock.cpp:41:24: error: no member named 'screen' in 'QDialog'
c3_dialog_dock.cpp:88:28: error: no member named 'screen' in 'QPushButton'
```

`c7_dialog_upperhalf.cpp:56` has `dlg->screen()`; ninja stopped at step 16/30
before compiling it, but the error is the same.

## 2. Root cause

`QWidget::screen()` was introduced in **Qt 5.14**. The in-repo SDK is **Qt 5.12.12**
(`strings libQt5Core.so` → `5.12.12`), where this member function does not exist.

5 call sites:

| File:line | Call |
|-----------|------|
| `s11_dialog_dock_center.cpp:37` | `parent->screen()` (×2) |
| `c3_dialog_dock.cpp:41` | `dlg.screen()` |
| `c3_dialog_dock.cpp:88` | `anchor->screen()` |
| `c7_dialog_upperhalf.cpp:56` | `dlg->screen()` |

## 3. Fix

Use the equivalent `windowHandle()->screen()` (available since Qt 5.12); `windowHandle()`
returns `nullptr` while the window has not been shown, so fall back to `primaryScreen()`:

```cpp
// Before
QScreen *scr = parent->screen();

// After
QScreen *scr = (parent && parent->windowHandle())
    ? parent->windowHandle()->screen()
    : QGuiApplication::primaryScreen();
```

Add `#include <QWindow>` (in most files `QWindow` is only forward-declared).

| File | Change |
|------|--------|
| `s11_dialog_dock_center.cpp` | Add `#include <QWindow>`; replace line 37 |
| `c3_dialog_dock.cpp` | Add `#include <QWindow>`; replace lines 41 and 88 |
| `c7_dialog_upperhalf.cpp` | Add `#include <QWindow>`; replace line 56 |

## Auto-fix

```yaml
match: "no member named 'screen' in 'QWidget'|no member named 'screen' in 'QDialog'|no member named 'screen' in 'QPushButton'"
files:
  - entry/src/main/cpp/pages/s11_dialog_dock_center.cpp
  - entry/src/main/cpp/pages/c3_dialog_dock.cpp
  - entry/src/main/cpp/pages/c7_dialog_upperhalf.cpp
actions:
  - type: add_include
    include: "#include <QWindow>"
  - type: replace_regex
    from: '(parent\s*&&\s*)?parent->screen\(\)'
    to: '(parent && parent->windowHandle()) ? parent->windowHandle()->screen()'
  - type: replace_regex
    from: '(\w+)\.screen\(\)'
    to: '\1.windowHandle() ? \1.windowHandle()->screen() : QGuiApplication::primaryScreen()'
  - type: replace_regex
    from: '(\w+)->screen\(\)'
    to: '\1->windowHandle() ? \1->windowHandle()->screen() : QGuiApplication::primaryScreen()'
```
