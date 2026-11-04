---
id: problem-platform-layer-two-dispatch-modes
type: problem
domain: build
tags: [平台层, 头文件分发, 源文件分发, 托盘, 通知管理器, undefined symbol, no-op 实现]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: high
audience: public
summary: "平台层有两种分发机制（头内 #ifdef / 构建按路径选 .cpp），只改 #ifdef 会永久漏掉一半"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  ld.lld: error: undefined symbol: Platform::Tray::Tray()
  ld.lld: error: undefined symbol: Ui::CreateNotificationManager()
  fatal error: 'gio/gio.h' file not found
  fatal error: 'xcb/xcb.h' file not found
  error: 'glibmm.h' file not found
error_code: ""
keywords: [平台层, 头文件分发, 源文件分发, platform_tray.h, platform_webauthn.h, undefined symbol, no-op, 托盘]
symptoms: "补完 #ifdef 后链接期集中爆平台符号；或把 Linux 实现当'其他平台'编进来"
# ====== 问题详情 ======
environment: "Qt 6.13.0-dev OHOS kit；桌面应用平台层共 11 个分发头 + 18 个实现文件"
refs: [problem-platform-guard-needs-both-ohos-macros, problem-runtime-tray-must-exist-noop, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-platform-guard-needs-both-ohos-macros, problem-runtime-tray-must-exist-noop]
---

# 平台层有两种分发机制，只改 `#ifdef` 会漏掉一半

## 根因

桌面应用的平台层不是一套机制，而是**两套并存**：

| 机制 | 判定位置 | 头文件形态 | 改哪里 |
|------|---------|-----------|--------|
| **头文件分发** | 头内的 `#ifdef` 链 | `#ifdef Q_OS_WIN / #elif Q_OS_MAC / #elif Q_OS_OHOS / #else`（else = Linux） | 改链（且必须双宏，见 [[platform-guard-needs-both-ohos-macros]]） |
| **源文件分发** | 构建系统按路径选 `.cpp` | 头内**没有** `#ifdef` | 新增 `ohos/xxx_ohos.cpp` 并让构建选中它 |

典型分布是 9 个头分发 + 5 个源分发。只审计 `#ifdef` 的覆盖率上限就是 9/14。
源分发那一类的头**一个字都不用改**：`platform_webauthn.h` 只是 `#include "webauthn.h"`，
真实现在哪个 `.cpp` 由构建决定——漏掉时表现为链接期 `undefined symbol`。

## 第二个坑：能力为 false ≠ 可以不提供类

领域对象（托盘、通知管理器）是**成员变量**，由构造链无条件创建：

```cpp
// SourceFiles/tray.cpp
Platform::Tray _tray;   // 无条件构造，跟 TrayIconSupported() 无关
```

`TrayIconSupported()` 只阻止"创建图标"，不阻止"构造对象"。所以"鸿蒙没有托盘"的正确落地是
**给一个完整 no-op 实现**，不是删掉类——删了就是链接期 undefined。

## 验证方法

1. 分类清点（脚本）：`python tools/ohos-platform-audit.py <app>/SourceFiles/platform`
   —— 头分发文件必须同时命名两个 OHOS 宏；源分发文件单列，要求 `ohos/` 下有对应实现。
2. 链接期收敛：把链接日志喂给 `--undefined`，脚本会把"没有任何 `ohos/` 实现提到过"的符号列出来：
   `python tools/ohos-platform-audit.py <platform-dir> --undefined link.log`
3. 设备侧证明"空实现也够用但必须存在"：装机后日志里应看到能力查询返回 false、但对象存在：
   `platform appdata "..." icon "..." autostart false tray false permission true`。

## 解决方案

1. 先分类：`#ifdef` 链的头 → 补双宏分支；无 `#ifdef` 的头 → 补 `ohos/xxx_ohos.cpp` 并确认构建选中。
2. 再补实现：能力查询返回 false，行为函数给 no-op；**保留完整公开面**（托盘尤其，见
   [[runtime-tray-must-exist-noop]]）。
3. 用脚本断言覆盖率，不要靠链接器 `undefined symbol` 反推——那是最后一环，前面每一环都得先过。
