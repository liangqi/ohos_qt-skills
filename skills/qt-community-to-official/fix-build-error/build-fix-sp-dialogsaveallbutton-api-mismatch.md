# QStyle::SP_DialogSaveAllButton API version mismatch (Qt 5.15+ on a Qt 5.12 SDK)

> ID: build-fix-07
> Date: 2026-09-28 (based on actual build)
> Files involved: `entry/src/main/cpp/pages/f19_qtoolbar.cpp`
> Project root: `QtBugDemo-official/`
> Status: Not fixed

## 1. Error

```
FAILED: CMakeFiles/qtbugdemo.dir/pages/f19_qtoolbar.cpp.o
f19_qtoolbar.cpp:68:30: error: no member named 'SP_DialogSaveAllButton' in 'QStyle';
did you mean 'SP_DialogSaveButton'?
    addAct(standard, QStyle::SP_DialogSaveAllButton, QStringLiteral("Save All"));
```

## 2. Root cause

`QStyle::SP_DialogSaveAllButton` was introduced in **Qt 5.15**. The in-repo SDK is
**Qt 5.12.12**, where this enum value does not exist.

## 3. Fix

```cpp
// Before (Qt 5.15+)
addAct(standard, QStyle::SP_DialogSaveAllButton, QStringLiteral("Save All"));

// After (Qt 5.12 compatible)
addAct(standard, QStyle::SP_DialogSaveButton, QStringLiteral("Save All"));
```

File: `pages/f19_qtoolbar.cpp:68`.

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
