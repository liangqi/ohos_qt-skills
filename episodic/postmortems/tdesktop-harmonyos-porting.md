---
id: episodic-projects-tdesktop-harmonyos-porting
type: episodic
domain: project
tags: [tdesktop, telegram, qt6, harmonyos, portgraph, cross-compile, hap, signing, ime]
created: 2026-09-12
updated: 2026-09-12
status: active
audience: public
refs: [problem-build-qt612-qos-harmony-macro, problem-build-clang15-libcpp15-cpp20-gaps, problem-runtime-hap-missing-so-closure, problem-build-qt612-ohos-plugin-rebuild, problem-runtime-ohos-ime-reset-detach, semantic-qt-harmonyos-build]
summary: >
  Telegram Desktop (tdesktop v7.0.2) 不裁剪功能的全量鸿蒙化：portgraph fetch-deps
  59 bottle + 9 源码编译解决全部依赖，2088 目标适配（Q_OS_HARMONY 宏 / not_ohos
  集合 / clang15 C++20 缺口），harmonydeployqt + 签名注入 + hvigor 打包 550MB HAP，
  DT_NEEDED 闭包分析修复启动即死，Qt 6.12 平台插件重编部署链 + IME reset 修复。
  装机 60s smoke 零崩溃。可复用：五段式流水线 + 6 个工具脚本模式。
---

# tdesktop (Telegram Desktop) 鸿蒙化全量移植 — 复盘

## 项目概览

| 字段 | 内容 |
|------|------|
| 时间 | 2026-09-10 ~ 2026-09-12 |
| 技术栈 | tdesktop v7.0.2 (7002007) + Qt 6.12-beta3 harmonyos_arm64_v8a kit + OHOS NDK clang15/libc++15 (API 23) |
| 目标 | 不裁剪功能，在 HarmonyOS PC（HUAWEI MateBook Pro）上运行不崩溃 |
| 规模 | 2088 个编译目标 → 55 个 .so → 550MB 签名 HAP |
| 状态 | ✅ 装机运行，60s hilog smoke 零崩溃；IME reset bug 已修复并回归 |

## 总体流水线（可复用骨架）

```
portgraph fetch-deps（依赖闭包）      ← 阶段 1
  → ninja out-ohos（源码适配编译）    ← 阶段 2
  → harmonydeployqt --no-build        ← 阶段 3
  → 签名注入 + hvigorw assembleHap   ← 阶段 3
  → hdc install -r + hilog smoke     ← 阶段 4
  → 平台插件重编替换（可选）          ← 阶段 5
```

每一段独立可重入；任何一段失败不回滚其它段。

## 阶段 1：依赖解决（portgraph 主导）

```bash
python portgraph.py fetch-deps tdesktop --dry-run   # 先看闭包与缺口
python portgraph.py fetch-deps tdesktop             # 产物落 workspace/ohos-libs/（跨应用缓存）
python portgraph.py fetch-deps tdesktop --json      # manifest 拿 CMAKE_PREFIX_PATH 等集成参数
```

- **59 个依赖直接命中 bottle**（Harmonybrew/cmd-pkgs 预编译产物），集成参数从 manifest 读取。
- **9 个无 bottle 的源码编译**，两个特殊技巧：
  - **aom**：官方源无 bottle → 用 GitHub `m-ab-s` 镜像源码编译；
  - **dav1d**：只有静态库 → 静态转共享库：`clang -shared -Wl,--whole-archive libdav1d.a -o libdav1d.so.7 ...`。
- **bottle 在 Windows/NTFS 上的 symlink 损坏**：表现为 0 字节文件或不可访问的 reparse
  point（EACCES）→ 删除损坏链接后复制真实版本文件（本次修复 202 个）。
- 功能覆盖核查结论（未裁剪）：rlottie(→tlottie)、tg_owt+webrtc、tgcalls、cld3、
  libprisma、icu、libwebp 全部在包内可用。

## 阶段 2：源码适配（2088 目标）

三大类适配，前两类各自沉淀为独立 problem 页：

1. **平台宏与源集排除**：Qt 6.12 kit 宏是 `Q_OS_HARMONY`（非 5.15 的 `Q_OS_OHOS`）；
   `nice_target_sources` 的 ohos 分支若误标 `not_linux` 会把 ohos 实现静默变
   HEADER_FILE_ONLY → 详见
   [build-qt612-qos-harmony-macro](../../problems/build-qt612-qos-harmony-macro.md)。
2. **clang15/libc++15 的 C++20 缺口 8 类**（结构化绑定捕获/P0960/P0634/stop_token/
   atomic_ref/ranges/shared_ptr`<=>`/variant 构造）→ 详见
   [build-clang15-libcpp15-cpp20-gaps](../../problems/build-clang15-libcpp15-cpp20-gaps.md)。
3. **零散适配**（修改面小但必改）：

| 位置 | 修改 |
|------|------|
| `update_checker.cpp` | 6 处平台守卫 |
| `platform_*.h` 分发头 | 宏改为 `HARMONY \|\| OHOS` 双兼容 |
| `specific_ohos.h` | 去掉 `inline`（定义被弱化丢弃，用 `llvm-nm` 验证 .o 符号） |
| `tray_ohos / webauthn_ohos / file_utilities_ohos` | 新增/去外层重复定义 |
| `base_power_save_blocker_ohos` | QPointer 签名适配 |
| `lib_ui` | 新增 `ui/platform/ohos/` 3 个文件 |
| `delayed_activation.cpp` | XCB 路径排除 |
| TooManyCooks 若干头 | typename/atomic_ref/构造函数兼容写法 |

**教训**：同一文件多处修改必须**串行**编辑——并行 SearchReplace 同文件会互相覆盖
（本次竞态覆盖出现 3 次：sync.hpp / spawn_many.hpp / settings_notifications.cpp）。

## 阶段 3：打包与部署（make_hap.py 三步模式）

```
① harmonydeployqt --input <deployment-settings.json> --output <proj> --no-build
② 向 build-profile.json5 注入 signingConfigs（保留上次会话内容）
③ hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```

- 签名材料：华为云调试证书（certpath/keyAlias/storeFile + **加密密码 blob**）。
  bundle name 必须与 profile 绑定一致；hvigor 加密密码 blob 可直接从历史工程的
  build-profile.json5 复用，无需重新生成。
- 环境要求：`DEVECO_SDK_HOME=<sdk>`；PATH 前置 node + DevEco jbr/bin。
- hvigor 三连坑：① 未找到命令→必须传 `hvigorw.bat` 全路径；② 缺
  DEVECO_SDK_HOME→BuildNativeWithCmake 1ms skip 无产物；③ `spawn java ENOENT`→
  jbr/bin 不在 PATH。

## 阶段 4：运行验证与「启动即死」排查

- **60s hilog smoke**：装机启动后抓 60 秒日志，零 crash 即过门禁。
- **启动即死（64ms，exit 254）**：jscrash `TypeError: handleAbilityStageOnCreate of
  undefined` = libqohos.so 的传递依赖 .so 缺失 → 用 `llvm-readobj --needed-libs`
  从 libqohos.so + libTelegram.so 做 DT_NEEDED **BFS 闭包**，对照系统 so 与部署目录
  找缺口 → 补齐 libdav1d.so.7 / libaom.so.3 / libbz2.so.1.0 / libz.so → 详见
  [runtime-hap-missing-so-closure](../../problems/runtime-hap-missing-so-closure.md)。
- **应用层日志**：tdesktop 的 log.txt 在
  `/data/app/el2/100/base/<bundle>/preferences/log.txt`（与 tdata 同目录），
  `hdc file recv` 拉取，看 `RPC Error` 判断 MTP/网络层（区分客户端 bug 与服务器行为）。
- 网络：设备侧走本机 SOCKS 代理（trojan-go 127.0.0.1:1080），tdesktop 内置代理设置。

## 阶段 5：Qt 平台插件重编（libqohos.so 替换工作流）

修复 Qt 6.12-beta3 ohos 插件 IME reset bug 时建立的重编链路：
cmake + `BUILD_SUBMODULES=src/plugins/platforms` 五连坑（qt-cmake 拒绝构建 qtbase 本体 /
NODE_ADDON_API_ROOT / FIND_ROOT_PATH 重根化 / OHOS_NDK_ROOT / fontconfig feature
作用域）→ 产物替换 **kit** 的 plugins/platforms（harmonydeployqt 从 kit 部署，直接改
部署目录会被覆盖）→ 注意 SONAME 差异补齐 → 详见
[build-qt612-ohos-plugin-rebuild](../../problems/build-qt612-ohos-plugin-rebuild.md)。

## 阶段 6：IME 集成与「中文搜索搜不到」定性

- **修复**：`QOhosInputContext::reset()` 原 Detach/Attach 实现在组合中途收起软键盘 +
  commit 拼音字母污染文本 → 对齐 Android 行为只 finalize preedit → 详见
  [runtime-ohos-ime-reset-detach](../../problems/runtime-ohos-ime-reset-detach.md)。
- **IMEPROBE 探针法**（可复用）：插件 IMF 回调入口 + context 关键路径加
  `qOhosPrintfDebug` + 码点转义，hilog 抓 60-90s，直接证明提交链路干净与否。
- **「中文搜索无结果」定性（非移植 bug）**：三角验证（本地会话搜索 / 远端全局搜索 /
  官方客户端同账号对照）结论：
  - 本地 CJK 索引正常（搜「极」能命中已加入会话）；
  - 中文短词的**全局**搜索 Telegram 服务器本就不索引（官方客户端同样搜不到）；
  - tdesktop 本地索引只内置**俄语**转写（`translitRusEng`），无拼音——拉丁查询命中
    中文会话靠的是该会话的拉丁 @username。

## 可复用产出（本地工具脚本，模式可复述）

| 脚本 | 作用 |
|------|------|
| `build-tdesktop-ohos.ps1` | `ninja -C out-ohos -k 0` + Tee 完整日志（错误不截断） |
| `make_hap.py` | deploy → 签名注入 → hvigor 三步打包（本文阶段 3） |
| `check_closure.py` | DT_NEEDED BFS 闭包 vs 系统库/部署目录找缺口（阶段 4） |
| `build-libqohos.ps1` | cmake BUILD_SUBMODULES 重编平台插件（阶段 5） |
| `capture_ime.py` / `analyze_ime.py` | hilog IME 抓取与 UTF-8 码点分析（阶段 6） |

## 教训与原则

1. **portgraph 优先**：先 `--dry-run` 看闭包，bottle 能解决就不源码编译（工作量差两个数量级）。
2. **编译通过 ≠ 迁移成功**：以装机 + smoke 门禁为准；静默排除类 bug（HEADER_FILE_ONLY）
   编译期零报错，链接期集中爆符号才是信号。
3. **交叉编译 find 失败先怀疑 FIND_ROOT_PATH 重根化**，预填 cache 变量绕过。
4. **平台层与应用层分层排查**：Qt 插件 bug 用探针日志，应用 bug 用应用自身日志
   （tdesktop log.txt），网络/服务器问题用官方客户端对照。
5. **PowerShell 对无 BOM UTF-8 日志的中文匹配会失真**，跨编码分析一律用 Python。
