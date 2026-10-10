# QWidget::screen() API 版本不匹配（Qt 5.14+ on Qt 5.12 SDK）

> 编号：build-fix-06
> 日期：2026-09-28（基于实测构建）
> 涉及文件：`pages/s11_dialog_dock_center.cpp`、`pages/c3_dialog_dock.cpp`、
> `pages/c7_dialog_upperhalf.cpp`
> 工程根：`QtBugDemo-official/`
> 当前状态：未修复

## 1. 报错

```
FAILED: CMakeFiles/qtbugdemo.dir/pages/s11_dialog_dock_center.cpp.o
s11_dialog_dock_center.cpp:37:38: error: no member named 'screen' in 'QWidget'
s11_dialog_dock_center.cpp:37:57: error: no member named 'screen' in 'QWidget'

FAILED: CMakeFiles/qtbugdemo.dir/pages/c3_dialog_dock.cpp.o
c3_dialog_dock.cpp:41:24: error: no member named 'screen' in 'QDialog'
c3_dialog_dock.cpp:88:28: error: no member named 'screen' in 'QPushButton'
```

`c7_dialog_upperhalf.cpp:56` 有 `dlg->screen()`，ninja 在 16/30 步停止
未编译到，但错误相同。

## 2. 根因

`QWidget::screen()` 在 **Qt 5.14** 引入。仓内 SDK 为 **Qt 5.12.12**
（`strings libQt5Core.so` → `5.12.12`），该成员函数不存在。

5 处调用点：

| 文件:行 | 调用 |
|---------|------|
| `s11_dialog_dock_center.cpp:37` | `parent->screen()` (×2) |
| `c3_dialog_dock.cpp:41` | `dlg.screen()` |
| `c3_dialog_dock.cpp:88` | `anchor->screen()` |
| `c7_dialog_upperhalf.cpp:56` | `dlg->screen()` |

## 3. 修复

`windowHandle()->screen()`（Qt 5.12 即有）等价替代，`windowHandle()`
在窗口未 show 时返回 `nullptr`，回退 `primaryScreen()`：

```cpp
// 替换前
QScreen *scr = parent->screen();

// 替换后
QScreen *scr = (parent && parent->windowHandle())
    ? parent->windowHandle()->screen()
    : QGuiApplication::primaryScreen();
```

需补 `#include <QWindow>`（`QWindow` 在多数文件中仅前向声明）。

| 文件 | 改动 |
|------|------|
| `s11_dialog_dock_center.cpp` | 补 `#include <QWindow>`；行 37 替换 |
| `c3_dialog_dock.cpp` | 补 `#include <QWindow>`；行 41、88 替换 |
| `c7_dialog_upperhalf.cpp` | 补 `#include <QWindow>`；行 56 替换 |

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
