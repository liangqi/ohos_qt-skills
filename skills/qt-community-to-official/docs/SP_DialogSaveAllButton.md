
## 1. 修复方案（源码层：SP_DialogSaveAllButton）

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
