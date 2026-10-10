
## 1. 修复方案（迁移残留未使用 include）

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
