---
id: problem-runtime-tray-must-exist-noop
type: problem
domain: runtime
tags: [托盘, Tray, no-op, 链接期, 成员变量, 完整公开面, PSNI, HasMonochromeSetting]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: high
audience: public
summary: "鸿蒙没有托盘 API，但 Platform::Tray 是成员变量必须可构造 —— 要完整 no-op 面而不是删类"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  ld.lld: error: undefined symbol: Platform::Tray::Tray()
  ld.lld: error: undefined symbol: Platform::Tray::HasMonochromeSetting() const
  ld.lld: error: undefined symbol: Platform::Tray::setIcon(...)
error_code: ""
keywords: [托盘, Tray, no-op, undefined symbol, 成员变量, TrayIconSupported, HasMonochromeSetting, 完整公开面]
symptoms: "为鸿蒙删掉托盘实现后链接失败；或只实现了部分方法，运行到图标相关路径才崩"
# ====== 问题详情 ======
environment: "Qt 6.13.0-dev OHOS kit；桌面应用平台层 tray 抽象（Linux 侧基于 PSNI/StatusNotifier）"
refs: [problem-platform-layer-two-dispatch-modes, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-platform-layer-two-dispatch-modes]
---

# 鸿蒙的托盘：能力为 false，类必须存在且完整

## 根因

桌面应用的托盘抽象在 Linux 上走 PSNI（StatusNotifierItem）/ D-Bus，鸿蒙两样都没有。
但**"没有能力"不等于"可以没有类"**：

```cpp
// SourceFiles/tray.cpp
Platform::Tray _tray;                                  // 无条件构造
void InitTray() { if (!Platform::TrayIconSupported()) return; ... }
```

`TrayIconSupported()` 只挡住"创建图标"，对象构造在它之前。所以：

- **删掉类** → 链接期 `undefined symbol: Platform::Tray::Tray()`；
- **只实现一部分方法** → 链接通过，但走到图标/菜单路径时 `undefined symbol`
  （典型遗漏：`HasMonochromeSetting()`，它在构造链里被 `std::optional` 相关代码引用）。

## 最小完整公开面（14 个方法 + 1 个查询）

实现要点：所有行为函数 no-op，能力查询返回 `false`，返回值给"空/安全默认"，不返回空指针。

| 类别 | 方法 |
|------|------|
| 生命周期 | `Tray()`、`~Tray()` |
| 能力查询 | `TrayIconSupported()` → false、`TrayIconRegenerated()`、`HasMonochromeSetting()` → false |
| 图标 | `setIcon(...)`、`SetIcon(...)`、`destroyIcon()` |
| 菜单/激活 | `setMenu(...)`、`showMenu()`、`updateMenu()`、`activate(...)` |
| 提示 | `setToolTip(...)`、`updateToolTip()`、`showMessage(...)` |
| 扩展 | `setAdaptiveIconColor(...)` 等（按上游公开头逐一补齐） |

**判据**：以父类/公开头为准逐个方法给出实现；用
`llvm-nm -C <tray_ohos.cpp.o> | grep ' T '` 对照公开头方法清单，缺一个就会在某个调用点爆。

## 验证方法

1. 链接期零 `undefined symbol: Platform::Tray`；
2. 运行期：`hilog` 里能力查询返回 false，应用正常启动且无图标（符合"鸿蒙无托盘"预期）；
3. 反向验证：临时把某个方法删掉，链接**必须**失败——否则说明该方法根本没被引用，
   可以从公开面里移除（保持"最小但完整"）。

## 教训

"平台没有某能力"时，正确动作是**给出完整 no-op 实现 + 能力查询 false**，
而不是删除抽象。删除会把缺失推到链接期，而链接期报错只给符号名，不给"这是哪个平台能力"。
