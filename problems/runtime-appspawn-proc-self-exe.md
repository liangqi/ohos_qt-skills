---
id: problem-runtime-appspawn-proc-self-exe
type: problem
domain: runtime
tags: [appspawn, /proc/self/exe, readlink, 沙箱, ELF 解析, 立即退出, 无日志]
created: 2026-11-04
updated: 2026-11-04
status: open
severity: high
audience: public
summary: "应用启动即退出且无日志 —— 现代 appspawn 给应用重新 exec 自己，/proc/self/exe 不是 ELF"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  （应用启动后立即退出，hilog 无本进程行，faultlog 无 cppcrash）
  readlink("/proc/self/exe") 返回的不是可执行 ELF，读取 e_ident 失败
error_code: ""
keywords: [appspawn, proc/self/exe, readlink, ELF, exec, 沙箱, 启动即退出, 无日志, 重启风暴]
symptoms: "hdc 启动应用后瞬间回到桌面；没有崩溃栈、没有应用日志，像被系统直接杀掉"
# ====== 问题详情 ======
environment: "HarmonyOS 5.x PC（appspawn 新版启动链）；Qt 6.13.0-dev OHOS kit 交叉构建的自绘 UI 应用"
refs: [problem-runtime-tray-must-exist-noop, problem-platform-guard-needs-both-ohos-macros]
related_problems: [problem-runtime-tray-must-exist-noop]
---

# appspawn 把应用"再 exec 一次自己"——`/proc/self/exe` 不再是 ELF

## 现象

- `hdc shell aa start` 返回成功，应用随即消失（回到桌面）；
- `hilog` 里没有任何本进程日志，`/data/log/faultlog/faultlogger/` 没有 cppcrash；
- 反复启动形成"重启风暴"，从外部看像"应用被系统直接杀掉"。

## 根因

新版 appspawn 的启动链会在沙箱里对应用**再 exec 一次自己**。此时进程的
`/proc/self/exe` 指向的不是磁盘上的可执行 ELF（而是一个沙箱内的中间态/已删除节点），
传统桌面写法依赖它做自检或解析自身 ELF 头：

```cpp
char buf[PATH_MAX];
ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
// 打开 buf 读 ELF e_ident → 不是 0x7f 'E' 'L' 'F'
```

一旦这段代码在启动早期跑（静态初始化、`QApplication` 之前），解析失败 → 进程在产生
任何日志之前就退出，于是"没有日志"。

## 判定方法

1. 先确认"到底有没有起来过"：`hdc shell "ps -ef | grep <bundle>"` 在启动后 1 秒内轮询，
   若进程出现又消失，说明进入了 exec 链而不是参数错误。
2. 打印 `readlink("/proc/self/exe")` 的返回值与 `e_ident` 前 4 字节：不是 `\x7fELF` 即命中本问题。
3. 交叉验证：同一份二进制在旧版 appspawn 设备上正常 → 差异在启动链，不在代码逻辑。

## 解决方案

去掉对 `/proc/self/exe` 的依赖：

- 需要"自身路径"时用 `QCoreApplication::applicationFilePath()`（QPA 已处理沙箱语义），
  或直接用 `argv[0]`；
- 需要 ELF 信息（版本、构建号）时改为**编译期注入**（`-DAPP_BUILD_ID=...`）或读随包资源；
- 启动早期不要做"自检式"文件解析，把它移到 `QApplication` 构造之后并加失败兜底。

## 边界

本页状态为 `open`：已在真实设备上观测到该现象并定位到 exec 链，但**尚未**用最小 demo
在不同 appspawn 版本上对照复现。按 `faults/_index.md` §六的证据标准，它目前只能作为
problems 页的经验记录，不能升格为 C 页定性。
