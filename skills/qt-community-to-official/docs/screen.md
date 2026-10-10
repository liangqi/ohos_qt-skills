
## 1. 修复方案（源码层：QWidget::screen() → Qt 5.12 兼容）

`QWidget::screen()` 在 Qt 5.14 引入。Qt 5.12 下等价写法：经 `windowHandle()`
取 `QWindow`，再 `QWindow::screen()`（5.12 即有）；`windowHandle()` 在窗口
未 show 时为空，回退 `QGuiApplication::primaryScreen()`。

```cpp
// 替换前（Qt 5.14+）
QScreen *scr = parent->screen();

// 替换后（Qt 5.12 兼容）
QScreen *scr = (parent && parent->windowHandle())
    ? parent->windowHandle()->screen()
    : QGuiApplication::primaryScreen();
```

> `QWindow` 在多数源文件里只是前向声明（`qwindowdefs.h`），需补
> `#include <QWindow>` 才能调用 `windowHandle()->screen()`。

应用到的 3 个文件、共 4 处调用点：

| 文件:行 | 原调用 | 备注 |
|---------|--------|------|
| `pages/s11_dialog_dock_center.cpp:37` | `parent->screen()` | 补 `#include <QWindow>` |
| `pages/c3_dialog_dock.cpp:41` | `dlg.screen()` | 补 `#include <QWindow>` |
| `pages/c3_dialog_dock.cpp:88` | `anchor->screen()` | 同上 |
| `pages/c7_dialog_upperhalf.cpp:56` | `dlg->screen()` | 补 `#include <QWindow>` |

> `pages/s12_qlabel_hint_cache.cpp` 已是 `windowHandle()->screen()` 写法，无需改。

## 2. 修复方案（源码层：SP_DialogSaveAllButton）

`QStyle::SP_DialogSaveAllButton` 在 Qt 5.15 引入，5.12 不存在。编译器提示最
接近项为 `SP_DialogSaveButton`。本处为工具栏 demo 图标，语义同属「保存」动作，
替换无功能损失：

```cpp
// 替换前（Qt 5.15+）
addAct(standard, QStyle::SP_DialogSaveAllButton, QStringLiteral("全部保存"));

// 替换后（Qt 5.12 兼容）
addAct(standard, QStyle::SP_DialogSaveButton, QStringLiteral("全部保存"));
```

文件：`pages/f19_qtoolbar.cpp:68`。

## 6. 修复方案（迁移残留未使用 include）

`pages/s9_base_equals_window.cpp` 的 `#include <QtOhosExtras/QOhosAbilityContext>`
为迁移残留：全文件无任何 `QOhosAbilityContext::` 实际调用，仅证据说明文本提及
`setColorMode()`。精简 SDK 又无 `QtOhosExtras` 头文件目录 → `file not found`。
直接移除该未使用 include：

```cpp
#include "demopage.h"
// 原迁移自 QtOhosExtras/QOhosAbilityContext，但本页仅在其证据说明文本中提及
// setColorMode()，源码未实际调用该模块任何符号；仓内 SDK 亦不含 QtOhosExtras
// 头文件，故移除该未使用 include 以消除编译依赖。
```
