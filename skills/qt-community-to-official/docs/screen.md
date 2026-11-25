
## 1. Fix (source level: QWidget::screen() → Qt 5.12 compatible)

`QWidget::screen()` was introduced in Qt 5.14. The Qt 5.12 equivalent: get the `QWindow` via `windowHandle()`,
then call `QWindow::screen()` (available since 5.12); `windowHandle()` is null while the window
has not been shown, so fall back to `QGuiApplication::primaryScreen()`.

```cpp
// Before (Qt 5.14+)
QScreen *scr = parent->screen();

// After (Qt 5.12 compatible)
QScreen *scr = (parent && parent->windowHandle())
    ? parent->windowHandle()->screen()
    : QGuiApplication::primaryScreen();
```

> In most source files `QWindow` is only forward-declared (`qwindowdefs.h`), so you need to add
> `#include <QWindow>` before you can call `windowHandle()->screen()`.

Applied to 3 files, 4 call sites in total:

| File:line | Original call | Notes |
|-----------|---------------|-------|
| `pages/s11_dialog_dock_center.cpp:37` | `parent->screen()` | Add `#include <QWindow>` |
| `pages/c3_dialog_dock.cpp:41` | `dlg.screen()` | Add `#include <QWindow>` |
| `pages/c3_dialog_dock.cpp:88` | `anchor->screen()` | Same as above |
| `pages/c7_dialog_upperhalf.cpp:56` | `dlg->screen()` | Add `#include <QWindow>` |

> `pages/s12_qlabel_hint_cache.cpp` already uses `windowHandle()->screen()`; no change needed.

## 2. Fix (source level: SP_DialogSaveAllButton)

`QStyle::SP_DialogSaveAllButton` was introduced in Qt 5.15 and does not exist in 5.12. The compiler suggests
`SP_DialogSaveButton` as the closest match. Here it is a toolbar demo icon, and both belong to the same "save" action
semantically, so the replacement loses no functionality:

```cpp
// Before (Qt 5.15+)
addAct(standard, QStyle::SP_DialogSaveAllButton, QStringLiteral("Save All"));

// After (Qt 5.12 compatible)
addAct(standard, QStyle::SP_DialogSaveButton, QStringLiteral("Save All"));
```

File: `pages/f19_qtoolbar.cpp:68`.

## 6. Fix (unused include left over from migration)

The `#include <QtOhosExtras/QOhosAbilityContext>` in `pages/s9_base_equals_window.cpp`
is a leftover from the migration: the file makes no actual `QOhosAbilityContext::` call anywhere; only the evidence
description text mentions `setColorMode()`. The trimmed SDK also has no `QtOhosExtras` header directory → `file not found`.
Simply remove the unused include:

```cpp
#include "demopage.h"
// Originally migrated from QtOhosExtras/QOhosAbilityContext, but this page only mentions
// setColorMode() in its evidence description text; the source never calls any symbol of that
// module, and the in-repo SDK has no QtOhosExtras headers, so the unused include is removed
// to drop the build dependency.
```
