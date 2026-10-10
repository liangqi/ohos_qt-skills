# QtOhosExtras 转发头文件缺失导致 file not found

> 编号：build-fix-05
> 日期：2026-09-28（基于实测构建）
> 涉及文件：`entry/src/main/cpp/pages/s9_base_equals_window.cpp`
> 工程根：`QtBugDemo-official/`
> 当前状态：未修复

## 1. 报错

```
FAILED: CMakeFiles/qtbugdemo.dir/pages/s9_base_equals_window.cpp.o
s9_base_equals_window.cpp:25:10: fatal error: 'QtOhosExtras/QOhosAbilityContext' file not found
#include <QtOhosExtras/QOhosAbilityContext>
         ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```

## 2. 根因

`#include <QtOhosExtras/QOhosAbilityContext>` 期望名为 `QOhosAbilityContext`
（**无 `.h` 扩展名**）的转发头文件。

实测 `include/QtOhosExtras/` 目录：

| 文件 | 类型 | 存在? |
|------|------|-------|
| `qohosabilitycontext.h` | 实现头 | ✓ |
| `QOhosAbilityContext` | 转发头（无扩展名） | ✗ **缺失** |

对比 `include/QtCore/`：`QObject`（转发头）✓ + `qobject.h`（实现头）✓。

QtCore 有转发头，QtOhosExtras **只有实现头，缺转发头**。

该 include 未被使用——全文件无 `QOhosAbilityContext::` 实际调用，属迁移残留。

## 3. 修复

移除未使用的 include：

```diff
  #include "demopage.h"
- #include <QtOhosExtras/QOhosAbilityContext>
```

## Auto-fix

```yaml
match: "QtOhosExtras/.*file not found"
files:
  - entry/src/main/cpp/pages/s9_base_equals_window.cpp
actions:
  - type: remove_include
    include: "#include <QtOhosExtras/QOhosAbilityContext>"
```
