# DEPS-OPT-REPORT — portgraph 依赖分析（deps / fetch-deps）优化报告

> 分支：`worker1-deps-opt`（单提交 `0501a99`）
> 范围：`portgraph/port_graph/{deps_report,deps_fetch,kb_seed,project_scanner}.py`、
> `portgraph/portgraph.py`、`portgraph/tests/`、`portgraph/docs/`
> 验证环境：Python 3.10，主库 4758 个 Harmonybrew formula + 1248 个 cmd-pkgs 已入库；
> 真实语料 corpus-c（884 源文件，e2e corpus tier B）；合成样例工程 deps-sample。

---

## 一、现状梳理与问题定位方法

### 工具链现状

- `deps <path|app>`：`qt_scanner` 19 类信号扫描 → `deps_report.analyze_dependencies`
  五角色分类（link/build-tool/runtime/test/vendored/provided/env）+ 多源版本约束校验
  + hb/cmd-pkgs 产物解析 → 文本/JSON 报告
- `fetch-deps <app>`：`deps_fetch.dependency_closure`（runtime/uses-module 边 BFS）→
  逐节点分类下载（bottle sha256 校验 / cmd-pkgs tar.gz）→ manifest（role/status/toolchain）
- 扫描入库（`project_scanner.scan_project`）把 find_package/pkg_check_modules 等名字
  连边到包节点，未解析的建 `pkg-unknown:*` 幽灵节点

### 问题定位

实际执行了完整链路：`ingest all`（hb-core sparse clone 4758 formula）→ 合成样例工程
`deps`/`fetch-deps` → 真实项目 corpus-c `deps`/`fetch-deps --dry-run` → e2e 对账
harness（`tests/e2e/run_e2e.py run --project corpus-c`），从准确性、去重一致性、
分类语义、输出可读性、CLI 易用性五个角度取证。

---

## 二、改动清单（4 个改进点）

### 1. 版本校验口径修正：消除跨名别名的虚假 conflict（准确性 ★）

**问题**：`pkg_check_modules(FF REQUIRED "libavcodec >= 58")` 经别名归并为 ffmpeg 后，
`_check_req` 把库主版本 58 与 ffmpeg 包版本 9.0.2 直接数值比较 → 误报
`✗版本冲突`+`鸿蒙版本 9.0.2（低于要求）`，会诱导 agent 评估"降级或源码编译新版"。
（libavcodec 的 pkg-config Version 是 61.x.x 式 ABI 版本，与 ffmpeg 发行版本是两套口径。）

**改动**（`deps_report.py`）：
- pkg_check_modules 别名归并且带版本约束时，条目记录 `version_req_from`（约束来源库名）
- `_version_check`：存在 `version_req_from` 时该约束判 `unknown`（口径不可比），
  不产生 conflict；新增 info 级警告说明"库版本口径 vs 包版本，需人工确认"
- JSON 报告结构相应增加 `version_req_from` 字段（docs/deps-report.md 已更新）

### 2. 同库异名去重：deps 矛盾条目合并 + fetch-deps 重复下载（去重 ★）

**问题**（corpus-c 实测）：
- deps 报告中 qrencode 库出现 **3 条**（`QREncode`→hb:qrencode 有 bottle、
  `libqrencode`→cmdpkgs:libqrencode 有直链、`qrencoded` 幽灵），同一库一条说"有产物"
  一条说"无产物"
- fetch-deps 中 `qrencode` 与 `libqrencode` **各下载一次**（两个安装根、两份 .so）；
  `xkbcommon` 幽灵显示"需自行移植"而同闭包里 `libxkbcommon` bottle 正常下载——
  同一依赖两种矛盾结论

**改动**：
- `kb_seed.PKG_ALIASES`（新共享表，原 deps_report.LIB_NAME_ALIASES 迁移扩充）：
  补 e2e 复核确认的缺口 `xkbcommon→libxkbcommon`、`x11→libx11`、
  `pcsc/libpcsclite/pcsclite→pcsc-lite`
- `project_scanner._link_third_party`：直接名未解析时按别名表重试（消幽灵，
  analyze/fetch-deps/deps 三命令解析口径一致）
- `deps_report._resolve`：同样按共享别名表兜底
- `deps_report` 7b 合并升级：除 resolved_node 外，按解析节点**规范化名**
  （去 lib 前缀/@变体）合并——hb:qrencode 与 cmdpkgs:libqrencode 归并为单条，
  多源证据保留，base 无产物时采用有产物一侧的解析结果
- `deps_fetch`：`downloadable`/`installed_by_name` 去重键规范化（`_norm_key`，
  去 lib 前缀）——同库只下载一次，另一个节点标 `covered`

### 3. fetch-deps 分类语义与输出（分类/可读性 ★）

**问题**：`openmp 需自行移植（源码: ?）`、`gtest 需自行移植（源码: ?）`——
OpenMP 是编译器特性（libomp 随 NDK）、GTest 是测试框架，都不该被引导去"移植"。

**改动**（`deps_fetch.py` 新增 `_classify_special`，与 deps 报告口径对齐）：
- CMake 内置（Threads/OpenMP/iconv/dl）→ `status=provided` + note（随 NDK/SDK 自带）
- 测试框架（GTest/Catch2/…）→ `role=test` + note（不进发行包；status 仍随产物
  可用性走，bottle 存在时保留下载信息）
- 主机构建工具幽灵（ECM 等无产物、depth=1）→ `role=build-tool`；有真实产物的
  （如 gettext 同时是运行时库）不重分类，避免误伤传递依赖场景
- need_port 无源码链接时输出改为"未入库，无源码链接：请确认依赖名是否正确…"
  （原来是`（源码: ?）`）；有 note 时优先展示 note
- manifest `roles` 计数新增 `test`/`build-tool`（docs/fetch-deps.md 已更新）

### 4. CLI 与报告可读性修正（易用性）

- **`--compact` 后置**：原全局旗标只接受 `portgraph.py --compact deps X`，写成人
  习惯的 `deps X --json --compact` 直接 argparse 报错。现为所有子命令补上该旗标，
  两个位置均可用（子解析器不覆盖主解析器已写命名空间值）
- **build-tools 计数修正**：原 `len(build_tools)+len(tools)` 把 find_package 构建
  工具双计，且固定项（CMake/C++/编译器）不在内——样例工程显示"0 个"下面却列 3 项。
  现改为与渲染展示项一致：`len(tools)+cmake+cxx+compiler`
- `_resolve_app` 未命中提示覆盖"传的是路径"场景；`network`（macOS Network 框架
  裸链接名）归 platform-iface；`winscard` 补入 Win32 系统库集合
- BFS 队列 `pop(0)` → `deque.popleft()`（O(n²)→O(n)）

### 附带修正（测试资产）

- `test_curl_formula` 版本断言 `8.21.0` 改为形态匹配 `^8\.\d+(\.\d+)?(_\d+)?$`：
  该用例此前因 hb-core 不在本地而 skip，本次补齐数据源后暴露上游 formula 已演进到
  8.22.0（与本次改动无关的既有数据漂移）
- e2e harness `name_variants` 补**反向别名**变体：别名归并后的节点名（libx11/
  pcsc-lite）能被构建文件 grep（`find_package(X11)`/`PCSC`）命中，否则误判 false-positive
- `overrides/corpus-c.json`：3 条"待补 ALIASES"resolution-gap 规则已落地，更新注记

---

## 三、优化前后对比

### 3.1 合成样例（deps-sample：CMake + Qt5 + zlib/openssl/sqlite/X11/libavcodec）

| 维度 | 优化前 | 优化后 |
|---|---|---|
| ffmpeg 版本校验 | `✗版本冲突`，`鸿蒙版本 9.0.2（低于要求）`（误导） | 无冲突标记 + info"版本约束 >= 58 来自 libavcodec 的库版本口径…需人工确认" |
| fetch-deps libavcodec | `需自行移植（源码: ?）`（幽灵节点，bottle 实际存在） | 解析为 `ffmpeg v9.0.2 需下载`，且正确展开 ffmpeg 的 24 个传递 runtime 依赖 |
| fetch-deps gtest | `需自行移植（源码: ?）` | `测试框架，不进发行包；仅当需要在鸿蒙设备上跑测试时才处理` |
| fetch-deps x11 | `需自行移植（源码: ?）` | `需自行移植（未入库，无源码链接：请确认依赖名是否正确…）` |

### 3.2 真实项目 corpus-c（884 源文件）

| 维度 | 优化前 | 优化后 |
|---|---|---|
| deps link 条目 | 32 条，qrencode 三条矛盾条目 | 29 条，同库归并（QREncode/libqrencode→1 条、PCSC/pcsclite→1 条有产物） |
| build-tools 计数 | 显示 `0 个`下面列 3 项（且双计） | `10 个` = 7 工具 + CMake + C++17 + 编译器，与展示一致 |
| fetch-deps 闭包 | 43 项：need_port **6**、covered 0 | 40 项：need_port **1**（仅 botan，经复核确无鸿蒙包，定性正确）、covered 1 |
| qrencode 下载 | qrencode + libqrencode **下载两次** | 下载一次，另一节点 covered |
| xkbcommon/x11 幽灵 | `需自行移植`（与 libxkbcommon/libx11 bottle 矛盾） | 幽灵节点被同库 bottle 补位（would_download），真实节点 covered |
| openmp | `需自行移植（源码: ?）` | provided（编译器特性随 NDK） |
| e2e 对账 | bug_candidates **4**（resolution-gap×4）、deps_unknown 6 | bug_candidates **0**、deps_unknown 2（openmp/botan 均经复核为正确 unknown）；recall 100% |
| `--compact` 后置 | argparse 报错退出 2 | 正常输出紧凑 JSON |

### 3.3 测试

- 35 → **42** 用例全过（新增 7：别名版本口径、跨源同库合并、规范化去重、
  特殊分类、扫描期别名解析、build-tools 计数、CLI --compact 后置）
- 真实下载链路验证：`fetch zlib` bottle 下载 + sha256 校验 + NTFS 链接补建正常

---

## 四、遗留问题与建议

1. **平台块内的 `target_link_libraries` 裸名**：corpus-c 的 `network`（macOS
   DARWIN 块内 tll）现归 platform-iface，但 `required` 标记仍为真——qt_scanner
   不感知 tll 调用处的平台块上下文。建议：qt_scanner 记录 tll 所在
   `if(APPLE)/if(WIN32)` 块，deps_report 将平台块内的裸名直接降为 optional。
2. **`qrencoded` 幽灵**：FindQREncode.cmake 中 find_library 探测的线程变体名，
   需库级别名知识（qrencoded→qrencode）。建议按需扩充 PKG_ALIASES。
3. **find_package 名与 hb 包名同名异义风险**（文档已声明）：PKG_ALIASES 扩充后
   错配面略增（如多精度库 MPC vs 播放器 mpc），产物 URL 落地前仍应人工核对；
   可考虑给别名表加"来源证据"字段供报告展示。
4. **fetch-deps 双次闭包计算**：`cmd_fetch_deps` 先算 total 再由
   `fetch_app_deps` 重算一次（当前规模 <0.1s，影响可忽略）；若闭包规模显著增长，
   可给 `fetch_app_deps` 加 `closure=` 复用参数。
5. **hb-core 版本漂移的测试策略**：`test_curl_formula` 已改为形态断言；其余依赖
   本地 sparse checkout 的用例（1 个）在无数据源环境中仍会 skip，属预期。
6. **e2e 其余语料**（corpus-a/corpus-b/corpus-d）未在本轮重跑（克隆体积大）；
   建议在具备网络的后续轮次执行 `run_e2e.py run --all` 验证别名改动对其他语料
   的 resolution-gap 消除效果。

---

## 五、复现命令

```bash
cd portgraph
python -m unittest discover -s tests            # 42 用例全过
python portgraph.py deps <项目路径> --json       # 综合依赖分析
python portgraph.py deps <项目路径> --json --compact   # --compact 后置（新）
python portgraph.py fetch-deps <app> --dry-run   # 依赖闭包分类预览
python tests/e2e/run_e2e.py run --project corpus-c --no-clone --fresh-db
# → recall=100% precision=23% bug_candidates=0（原 4）
```
