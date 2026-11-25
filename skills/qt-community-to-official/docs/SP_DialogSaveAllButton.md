
## 1. Fix (source level: SP_DialogSaveAllButton)

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
