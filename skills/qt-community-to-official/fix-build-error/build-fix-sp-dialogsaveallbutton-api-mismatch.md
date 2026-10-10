# QStyle::SP_DialogSaveAllButton API 版本不匹配（Qt 5.15+ on Qt 5.12 SDK）

> 编号：build-fix-07
> 日期：2026-09-28（基于实测构建）
> 涉及文件：`entry/src/main/cpp/pages/f19_qtoolbar.cpp`
> 工程根：`QtBugDemo-official/`
> 当前状态：未修复

## 1. 报错

```
FAILED: CMakeFiles/qtbugdemo.dir/pages/f19_qtoolbar.cpp.o
f19_qtoolbar.cpp:68:30: error: no member named 'SP_DialogSaveAllButton' in 'QStyle';
did you mean 'SP_DialogSaveButton'?
    addAct(standard, QStyle::SP_DialogSaveAllButton, QStringLiteral("全部保存"));
```

## 2. 根因

`QStyle::SP_DialogSaveAllButton` 在 **Qt 5.15** 引入。仓内 SDK 为
**Qt 5.12.12**，该枚举值不存在。

## 3. 修复

```cpp
// 替换前（Qt 5.15+）
addAct(standard, QStyle::SP_DialogSaveAllButton, QStringLiteral("全部保存"));

// 替换后（Qt 5.12 兼容）
addAct(standard, QStyle::SP_DialogSaveButton, QStringLiteral("全部保存"));
```

文件：`pages/f19_qtoolbar.cpp:68`。

## Auto-fix

```yaml
match: "no member named 'SP_DialogSaveAllButton'"
files:
  - entry/src/main/cpp/pages/f19_qtoolbar.cpp
actions:
  - type: replace
    from: "QStyle::SP_DialogSaveAllButton"
    to: "QStyle::SP_DialogSaveButton"
```
