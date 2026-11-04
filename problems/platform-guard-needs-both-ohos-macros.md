---
id: problem-platform-guard-needs-both-ohos-macros
type: problem
domain: build
tags: [平台守卫, Q_OS_OHOS, Q_OS_HARMONY, 双宏, qsystemdetection, 分支判定, 假修复]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: high
audience: public
summary: "平台守卫只写 Q_OS_OHOS —— Qt 6.x kit 只定义 Q_OS_HARMONY，分支静默落到 Linux 实现"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  构建不报错，但运行期走的仍是 Linux 实现；
  若 Linux 实现真被编进来，则报：
  fatal error: 'gio/gio.h' file not found
  fatal error: 'xcb/xcb.h' file not found
error_code: ""
keywords: [Q_OS_OHOS, Q_OS_HARMONY, qsystemdetection, 双宏守卫, platform_specific.h, -DQ_OS_OHOS, 假修复, --target, -H]
symptoms: "平台分发头写了 #elif defined Q_OS_OHOS 却永不成立；编译通过、行为是 Linux 的"
# ====== 问题详情 ======
environment: "Qt 6.13.0-dev（HarmonyOS PC 原生构建）与厂商 Qt 5.15.16 OHOS kit 对照；OHOS clang 15"
refs: [problem-build-qt612-qos-harmony-macro, problem-platform-layer-two-dispatch-modes, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-build-qt612-qos-harmony-macro]
---

# 平台守卫只写 `Q_OS_OHOS` 时不生效 —— Qt 6.x kit 只定义 `Q_OS_HARMONY`

## 根因

`qsystemdetection.h` 在 Qt 5 与 Qt 6 的 OHOS 分支上**宏名不一致**：

```c
// Qt 6.12+ / 6.13.0-dev：<kit>/include/QtCore/qsystemdetection.h
#elif defined(__OHOS__)
#  define Q_OS_HARMONY          // 只此一个，不定义 Q_OS_OHOS
```

厂商 Qt 5.15.16 OHOS kit 则**同时**定义 `Q_OS_OHOS` 与 `Q_OS_HARMONY`。
于是「只写一个宏」的守卫总在另一侧 kit 上是死代码：

```cpp
// platform/platform_specific.h（改前）
#ifdef Q_OS_WIN
#  include "platform/win/specific_win.h"
#elif defined Q_OS_MAC
#  include "platform/mac/specific_mac.h"
#elif defined Q_OS_OHOS          // ← Qt 6 kit 上永不成立
#  include "platform/ohos/specific_ohos.h"
#else
#  include "platform/linux/specific_linux.h"   // ← 实际落到这里
#endif
```

## 为什么"手动 `-DQ_OS_OHOS`"是假修复

补一个编译宏看起来立刻好，但它把 **kit 事实**换成了**构建脚本约定**：

1. 换一个 kit 就复发，且复发时没有任何提示；
2. `Q_OS_WIN` 在分发链**首位**。手工拼旗标在宿主 triple 上跑时 `Q_OS_WIN` 先命中，
   `-DQ_OS_OHOS` 完全救不了——你会得到 `specific_win.h` 这种自相矛盾的结论。

正确做法：**守卫同时接受两个宏**，并删掉构建脚本里的 `-DQ_OS_OHOS`：

```cpp
#elif defined Q_OS_OHOS || defined Q_OS_HARMONY
#  include "platform/ohos/specific_ohos.h"
```

## 怎么判定"到底编的是哪个分支"

必须用**完整编译命令**探测，`flags.make` 里的旗标不足以复现——交叉 toolchain 把
`--target=aarch64-linux-ohos` 放在编译器命令行上，手拼旗标会退回宿主 triple：

```bash
# 正确：带 toolchain 的 --target
clang++ --target=aarch64-linux-ohos -H -fsyntax-only $DEFS $INCS $FLAGS probe.cpp \
  | grep 'specific_.*\.h'
# .. <src>/platform/ohos/specific_ohos.h      ← 双宏守卫：命中正确

# 错误：丢掉 --target
clang++ -H -fsyntax-only $DEFS $INCS $FLAGS probe.cpp \
  | grep 'specific_.*\.h'
# .. <src>/platform/win/specific_win.h        ← 宿主 triple，结论完全相反
```

## 验证方法

1. 审计所有平台分发头是否同时命名两个宏：
   `python tools/ohos-platform-audit.py <app>/SourceFiles/platform`（退出码 0 = 全通过）。
2. 上面那条 `clang++ -H` 对照：同一份代码，带 `--target` 与不带 `--target` 应给出不同平台头，
   证明旗标确实到达了编译器。
3. 运行期复核：改动后重编并装机，日志里平台路径、数据目录、托盘能力查询应是鸿蒙值
   （如 `platform appdata "/data/storage/el2/base/files/"`），不是 Linux 路径。

## 适用范围

- 任何用 `#ifdef` 链做平台分发的 Qt 应用（不止 tdesktop）。
- Qt 6.12 / 6.13 系 kit 上，**`Q_OS_OHOS` 一律不存在**；5.15 系 kit 两个都在。
  跨 kit 的代码只能写 `defined Q_OS_OHOS || defined Q_OS_HARMONY`。
