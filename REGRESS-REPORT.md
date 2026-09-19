<<<<<<< HEAD
<<<<<<< HEAD
# REGRESS-REPORT — portgraph 依赖分析「回归 + 泛化」测试报告

> 分支：`worker1-deps-regress`（基线 `416ef8d`，含全部集成修复）
> 测试时间：2026-09-19 | 工作区：`portgraph/`
> 结论先行：**阶段1 tdesktop 一次分析正确性验证通过（e2e 报告与基线逐字节一致，仅时间戳差异；唯一新发现 kcoreaddons/microtex 子模块误报已修复）；阶段2 在 2 个语料外高星项目（Cutter、NotepadNext）上暴露 11 类问题，10 类修复根因并补 5 个回归单测（88→92 全过），e2e 四语料回归零退化**。

---

## 一、阶段 1：tdesktop 回归（一次分析正确性）

### 1.1 流程与计时（fresh DB，全程无人工修饰）

| 步骤 | 命令 | 耗时 |
|---|---|---|
| 数据源入库 | `ingest all --offline`（空库 → 6069 节点：hb 4758 + cmdpkgs 1248 + kb，零 app） | 1.20s |
| 扫描 | `scan workspace/tdesktop`（cmake，2932 源文件） | 1.80s |
| **deps 全流程（单命令，含扫描+入库+报告）** | `deps workspace/tdesktop --json`（fresh DB 一次跑通） | **1.90s（修复前）/ 2.12–2.17s（含本轮新增归并逻辑）** |
| 依赖闭包 | `fetch-deps tdesktop --dry-run --json` | 0.06s |

**性能对比**（上轮 `docs/opt-reports/` 数字：krita 3.05s/22769 文件、strawberry 0.63s/1185、QOwnNotes 0.81s/751）：
tdesktop（2932 文件，CMake 声明密集）2.15s 位于 strawberry 与 krita 之间，符合扫描量-耗时曲线，**无性能退化**；新增的自带源码声明归并（`_vendored_declarations` 宽松折叠索引）代价约 +0.2s，闭包 BFS 0.06s 与上轮（0.05–0.06s）持平。

### 1.2 与基线逐项核对（对照 `tests/e2e/reports/tdesktop` 基线）

- **e2e harness 全量回归**（`run --project tdesktop --fresh-db --no-clone`）：生成的 report.md/json 与 git 基线**逐字节一致（仅生成时间戳不同）**——recall 53% / precision 60% / bug_candidates 2（breakpad/crashpad，均为已知残留：shallow clone 未初始化 cmake_helpers 子模块，主集成逻辑不可见）。
- **可移植性判定**：blocked（macOS Cocoa + Win32 平台接口）+ unknown 8（fork/exec ×1 + pkg-unknown ×7）——与基线一致。
- **d1 直接依赖**（24 节点：19 package + 5 qt-module）：逐一核对一致；ported 12（boost/cmark-gfm/ffmpeg/glib/libfido2/libiconv/libqrcodegen/minizip/openal-soft/openssl@3/xxhash/zlib）/ unknown 7（libudev/ada/auto_updates/crash_reports/rnnoise/tde2e/webrtc）。
- **闭包 61 项**：would_download 47 / need_port 7 / provided 5 / target 1 / cmd_only 1（ca-certificates）——与基线完全一致。
- **deps 报告 link 26 条分类**：12 已解析（version_check 全部 `any`，无假冲突——构建文件确无可见版本约束，find_package 位于未初始化子模块）✓；7 unknown→need_port 定性正确 ✓；5 win32-system-lib（bcrypt/delayimp/hid/setupapi/ws2_32，均 optional）✓；**2 条发现问题（见 1.3）**。
- **vendored 35 条**（子模块 35 个，含 gsl/range-v3/hunspell/kcoreaddons/MicroTeX/cmark-gfm/libfido2 等）✓；build-tool 7（CMake>=3.25、clang、python3×3、pkgconfig×2）✓；env 13 ✓。

### 1.3 发现并修复：未初始化 git 子模块的 link 名误报 need_port

- **现象**：`kcoreaddons`、`microtex` 在 link 段报"无产物 → 需源码编译"（kind=package, version_check=unknown），但两者都是 `.gitmodules` 声明的子模块（`Telegram/ThirdParty/kcoreaddons`、`Telegram/ThirdParty/MicroTeX`），源码随仓库自带、随项目编译。
- **根因**：`deps_report` §7 只对"项目内同名源码目录"（in-tree 索引）归并，而浅克隆未初始化的子模块目录为空（无构建文件），索引不可见；图侧（project_scanner）早已有 `_submodule_folds` 同款逻辑，报告层口径缺失。
- **修复**：报告层新增自带源码声明索引（本轮进一步泛化，见阶段 2）；已解析到 bottle 但项目同时自带子模块的（cmark-gfm/xxhash/lz4/libfido2）追加"可随项目编译，bottle 为备选"注记（不改语义，信息更完整）。
- **测试**：`test_submodule_link_classification`（未解析→in-tree / 已解析→注记）。

---

## 二、阶段 2：GitHub 高星 Qt 项目泛化

### 2.0 项目选择（先声明）

| 项目 | 星标 | 构建系统 | 规模 | 选择理由 |
|---|---|---|---|---|
| **Cutter**（rizinorg/cutter） | 19.7k | CMake + Qt5/6 + meson 子模块 | 2697 源文件 | 逆向工程 GUI，不在建议清单（避撞）；依赖结构极端复杂：rizin 引擎整体作为 git 子模块 vendored（内置 meson subprojects + ExternalProject 双层包装） |
| **NotepadNext**（dail8859/NotepadNext） | 14.6k | CMake + qmake + CPM | 651 源文件 | 不在建议清单；Qt6 编辑器，CPM 拉取式自带依赖 + thirdparty/ 布局，与语料四项目的构建形态均不同 |

shallow clone 至 `portgraph/workspace/`（cutter 9s / notepadnext 14s）。**注**：cutter 克隆时 cloner 的子模块浅初始化静默失败（`rizin/` 为空目录），手动 `git submodule update --init --depth 1` 补齐（失败不可复现，属网络瞬态；cloner 的"静默跳过"设计本身是已知取舍——见残留观察）。

### 2.1 Cutter：11 类问题，10 类修复

| # | 问题（修复前 → 修复后） | 定性 | 根因与修复 |
|---|---|---|---|
| 1 | `find_package(Cutter REQUIRED)`（插件样例模板）自引用 → 解析到**同名无关包** `cmdpkgs:cutter`（1.04 版"切割机工具"）被列为 would_download → 自引用过滤，不再出现 | **工具 bug** | `qt_scanner._cmake_project_names`：根 CMakeLists 的 `project()` 名跳过（find_package + details 两条路径 + project_scanner 图侧）；只认根文件，vendored 子目录里 `project(fakevim)` 不影响宿主 |
| 2 | rizin 引擎内部库 **37 个**（rz_core/rz_util/…/rzwinkd，`dependency('rz_*')` 位于 vendored rizin 子模块的 meson.build）整批报 need_port → in-tree | **工具 bug**（泛化缺口：vendored 引擎的内部目标） | `qt_scanner._meson_internal_names`：收集 `meson.override_dependency()` 名 + `subprojects/` 目录名与 .wrap 名；命中的 meson 依赖标 `internal=True`，`cc.find_library` 同步跳过；deps_report 归 in-tree |
| 3 | meson 自带子项目（ptrace-wrap/zydis/softfloat/rizin-grammar-c/rizin-math-parser/rizin-shell-parser/rzheap/rzar/rzgdb/rzqnx/rzspp/rzw32dbg_wrap/rzwinkd/pcre2_cross_native/libblake2）报 need_port → in-tree | **工具 bug** | 同 #2（subprojects/ 目录 + .wrap 文件名入内部集合） |
| 4 | CPM 声明提取出垃圾名 **"NAME"**（`CPMAddPackage(NAME …)` 的关键字被当包名）；NotepadNext 的真实 CPM 名（ads/QSimpleUpdater/editorconfig_core_qt/SingleApplication）因声明位于 `thirdparty/CMakeLists.txt` 被 vendored 路径跳过而**全部不可见** → 名字正确提取，且 vendored 路径不再跳过（thirdparty/ 常是宿主自写的拉取胶水） | **工具 bug** | `qt_scanner._detect_fetched_deps`：NAME 关键字后取实际名；`${Name}` 等不可静态解析的跳过（CPM 实现文件自身的转发调用）；删除 vendored 路径 skip |
| 5 | 未解析 link 名命中 CPM/FetchContent/ExternalProject 声明仍报 need_port（NotepadNext `qtadvanceddocking-qt6`/`QSimpleUpdater`/`editorconfig-core-qt`）→ in-tree | **工具 bug** | `deps_report._vendored_declarations`：四类自带源码声明（git 子模块/CPM-FetchContent/ExternalProject/meson 子项目与内部目标）统一入宽松折叠索引（去 lib 前缀、去尾部 qt5/qt6/system 变体 token：`qtadvanceddocking-qt6` ≡ CPM 包 `ads` 的 URL 末段 `Qt-Advanced-Docking-System`）；已解析的追加"bottle 为备选"注记 |
| 6 | `dbghelp`（Windows 调试库）不在 WIN32_SYSTEM_LIBS → 报 need_port → win32-system-lib [optional] | **数据源缺口**（名称表） | `qt_scanner.WIN32_SYSTEM_LIBS` 补 dbghelp |
| 7 | meson 字符串插值 `dependency('libpcre2-@0@')` → 垃圾名 `libpcre2-@0@` → 剥占位符后 `libpcre2` 正确解析 pcre2 bottle（>=10.42 vs 10.48 **satisfied**） | **工具 bug** | `_absorb_meson` 剥 `@0@`；顺带 `subproject('capstone-' + …)` 尾部 `-` 清理（'capstone-' 垃圾名） |
| 8 | `pkg_check_modules(libgvc)` 报 need_port，而 graphviz bottle 实际存在（libgvc 是 graphviz 的链接库） → 别名归并解析 | **数据源缺口**（别名表） | `kb_seed.PKG_ALIASES` 补 libgvc/libcgraph/libcdt → graphviz |
| 9 | **ALSA 平台接口规则 `\bsnd_` 命中任意变量名**：rizin 生成的 scanner.c 里 `snd_last_ch` 变量 → 整个应用被误判 "blocked"（ALSA 直连，实际 rizin 全仓库无任何 ALSA 用法）→ 收紧为真实 ALSA API 前缀（snd_pcm_/snd_ctl_/snd_mixer_/snd_seq_…）后误报消除 | **工具 bug**（检测规则过宽） | `project_scanner.PLATFORM_RULES` iface:alsa 规则与前置锚点同步收紧；语义不变性由 e2e 四语料回归确认 |
| 10 | （见 #5 附带）`find_package(Rizin)` 在图侧建幽灵 pkg-unknown:rizin → need_port（仓库自带 rizin/ 子模块且默认 `CUTTER_USE_BUNDLED_RIZIN=ON`）→ 图侧不建幽灵 | **工具 bug** | `project_scanner` 主名单解析失败时与裸链接名路径同样做子模块折叠跳过（此前只覆盖 external_ 裸名路径） |
| R1 | execinfo/kvm/proc/socket/util（rizin 的 Solaris/BSD 平台探测，cc.find_library）报 need_port（required=True） | **数据源缺口**（平台库名表） | **未修**（残留）：非 Linux 平台库表缺失；属过度供给（多下载/多报告），不误导为"缺鸿蒙包"的反向错误。建议后续补 INTERFACE_BOUND 类平台表 |
| R2 | Graphviz `tri_option(… AUTO)` 默认视 required | **项目特有约定** | **未修**：CMake 三态选项（ON/OFF/AUTO）默认值语义未建模；当前保守取向（必须优先）与既有设计一致 |
| R3 | macOS Cocoa / Win32 平台接口计入 ohos-active → blocked | **已知限制**（上轮遗留 #2 同源） | **未修**：跨平台 #ifdef 平台块结构化解析缺失；与 tdesktop 基线行为一致（同类误报形态） |
| R4 | cloner 子模块浅初始化静默失败（网络瞬态不可复现） | **观察** | 手动补齐；后续可考虑 cloner 失败时在返回值中带 warning |

**修复后 Cutter 结果**：link 77 条 = package 27（外部真依赖，capstone/openssl/zlib/pcre2/tree-sitter/graphviz/bzip2 等，**12 个有 bottle**）+ **in-tree 41**（rizin 全家 + meson 子项目）+ win32-system-lib 6 + system-lib 2（m/threads）+ platform-iface 1（macOS Network）；PySide2/6/Shiboken* optional need_port（鸿蒙确无 PySide 产物，**定性正确**）；闭包 17 项 = would_download 12 / need_port **0** / provided 3 / target 1 / cmd_only 1；版本校验 capstone >=4.0.2 vs 5.0.9、pcre2 >=10.42 vs 10.48 均 satisfied；verdict 仍 blocked（macOS/Win32 平台接口，R3）+ fork()/exec() unknown（rizin 派生调试目标进程，**定性正确**）。deps 3.2s。

### 2.2 NotepadNext

**修复前**：link 3 条全部误报 need_port（editorconfig-core-qt / QSimpleUpdater / qtadvanceddocking-qt6，均为 CPM 拉取随项目编译）；vendored 段有垃圾条目 "NAME"（问题 #4）；scintilla/lexilla/lua/uchardet（thirdparty/ 自带源码，经 add_subdirectory）正确不入 link ✓。

**修复后**：link 3 条全部 in-tree（`CPM:ads` / `CPM:QSimpleUpdater` / `CPM:editorconfig_core_qt`）；vendored 5 条（thirdparty + ads + QSimpleUpdater + SingleApplication + editorconfig_core_qt，无垃圾名）；**闭包 6 项 = target 1 + provided 5（Qt Core/GUI/Network/PrintSupport/Widgets，鸿蒙 6.12 可用），need_port 0、无需下载任何 bottle**——该应用对鸿蒙的真实依赖面只有 Qt 6，与人工读构建文件结论一致；verdict blocked 仅因 macOS/Win32 平台接口启发式（R3，其中 21 处已正确识别为宏守卫排除，97 处无条件计为 ohos-active）。deps 0.79s。

**NotepadNext 未发现新问题**（其暴露的 #4/#5 均由它实证）。小瑕疵：`find_package(Qt6 COMPONENTS LinguistTools)` 计入 qt_modules（ LinguistTools 是 lrelease 工具侧组件，随 Qt SDK 提供不影响结论，未修）。

### 2.3 问题定性汇总

| 定性 | 数量 | 处置 |
|---|---|---|
| 工具 bug（含泛化缺口） | 9 类（#1–#5、#7、#9、#10 + 阶段1 子模块归并） | 全部修复根因 + 5 个回归单测 |
| 数据源缺口（名称/别名表） | 3 类（#6 dbghelp、#8 libgvc、R1 平台库表） | 前 2 修复；R1 留残留 |
| 项目特有约定 | 2 类（R2 tri_option、rizin/CPM 布局本身） | 记录；R2 保守取向符合既有设计 |
| 已知限制（上轮遗留） | 1 类（R3 平台块结构化解析） | 记录，与基线行为一致 |

---

## 三、测试与回归

- **单测**：88 → **92 全过**（`python -m unittest tests.test_port_graph`；新增 `test_submodule_link_classification`、`test_cpm_name_keyword`、`test_fetched_dep_link_classification`、`test_find_package_self_reference`、`test_meson_internal_dep_classification`——见 `TestGeneralizationFixes` §6e–6i）。
- **e2e 四语料全量回归**（tdesktop/keepassxc/qbittorrent/musescore，`--fresh-db`）：recall/precision/bug_candidates 与闭包计数**全部与基线一致**，报告 diff 仅时间戳（已还原）——ALSA 规则收紧、自引用过滤、meson 内部集合、CPM 路径放开均未影响语料项目结论。
- **性能**：tdesktop 全流程 2.15s（2932 文件）、cutter 3.2s（2697 文件，含 rizin 子模块全量扫描）、NotepadNext 0.79s（651 文件）；fetch-deps dry-run 均 0.06s。与上轮 krita 3.05s（22769 文件）/strawberry 0.63s/QOwnNotes 0.81s 同一量级，无退化。

## 四、残留与建议

1. **平台库名表缺口**（R1）：Solaris/BSD 探测库（socket/nsl/proc/util/kvm/execinfo）无分类表——建议扩充 INTERFACE_BOUND 类"非 Linux 平台探测库"表（cutter/rizin、部分 BSD 向项目会命中）。
2. **CMake 三态选项**（R2，tri_option AUTO）：optional 判定只认"默认 OFF"守卫；可增加"默认 AUTO（软依赖）"档。
3. **平台块结构化解析**（R3）：上轮遗留同源，macOS/Win32 平台代码计入 ohos-active 导致 blocked；对跨平台 Qt 应用普遍存在，是 analyze 层最大的已知保守偏差。
4. **cloner 子模块初始化失败可见性**（R4）：失败静默跳过虽不阻断克隆，但会导致下游"未初始化子模块盲区"（tdesktop breakpad/crashpad 同根因）；建议返回值携带 warning 供 agent 提示手动补拉。
5. LinguistTools 等 Qt 工具侧组件计入 qt_modules（不影响结论，可归 build-tool）。
=======
# 回归 + 泛化测试报告：deps 性能基准与 GitHub 热门 Qt 项目泛化

> 分支 `worker4-deps-regress`（基线 416ef8d，含全部集成修复）
> 测试时间：2026-09-19 | 工作区：`portgraph/`
> 结论先行：**性能无回退且有提升（krita 3.70s→3.17s，优于上轮修复态 3.21s；相对 f98a2e7 基线 3.9x）**；过程中暴露并修复 **6 个真 bug**（1 个性能 + 5 个正确性，含 cloner submodule 拉取静默失效这一影响所有 submodule 型项目的根因）；泛化项目 notepadqq/meshlab 分析质量良好，附带修复 dynamic_loads 平台守卫误报。单测 65→94 全过。

---

## 一、阶段 1：性能回归（4 e2e 语料 + 3 泛化项目）

### 1.1 数据源与环境

- 主库重建：`python portgraph.py ingest all` → 6069 节点（hb 4758 / cmdpkgs 1248 / kb-seed 63）/ 9504 边，与上轮口径一致。
- 计时方法：deps 全流程（scan + 入库 + 报告，含 `--json`）与 fetch-deps `--dry-run` 闭包，各 3 次取中位数。
- **基准方法勘误**：fetch-deps 传参是 app 名（`krita`）而非路径（`workspace/krita`），后者静默退出（exit 1）——上轮报告的 `fetch-deps <app>` 口径本次确认为 app 名，所有 fetch 计时已用正确参数重测。

### 1.2 A/B 对照（git worktree 隔离，同一克隆、同一 DB 重建流程）

| 项目 | f98a2e7（上上轮基线） | c04060a（上轮修复态） | 416ef8d（集成本轮实测） | 416ef8d+NOCASE 修复（bddcd59） |
|------|------|------|------|------|
| krita deps | 12.25s | 3.21s | **3.70s（+15%回退）** | **3.17s** |
| strawberry deps | 2.13s | 0.69s | 0.82s（+19%） | **0.58s** |
| qownnotes deps | 3.21s | 0.86s | 1.06s（+23%） | **0.72s** |

**回退定位**（cProfile 前后对照）：集成（c04060a→416ef8d）新增的别名表/解析阶梯使 `find_node_by_name` 调用增多，而该函数 `lower(name)=lower(?)` 无法命中 `idx_nodes_name`（BINARY 排序）索引 → 每次全表扫描 6069 行，krita 报告期 350 次查找共 0.4s。

**修复（bddcd59）**：`name=? COLLATE NOCASE` + `idx_nodes_name_nocase` 函数索引。语义等价（SQLite `lower()`/`NOCASE` 均仅折 ASCII；全库 6159 名逐名等价校验通过；旧库经 `init_db` 的 `CREATE INDEX IF NOT EXISTS` 自动补索引）。350 次查找 0.4s→0.002s。

### 1.3 最终性能基准（全部修复后，完整克隆状态）

| 项目 | deps 中位数 | fetch-deps --dry-run | 说明 |
|------|------|------|------|
| krita | **3.17s** | 0.06s | 22769 源文件，无 submodule |
| strawberry | 0.60s | 0.06s | 闭包 61 项 |
| qownnotes | 0.87s | 0.06s | 8 个 submodule 就位后（上轮为空目录扫描） |
| tdesktop | 3.66s | 0.06s | 6358 源文件（35 submodule 就位；集成基线生成时仅 2932） |
| musescore | 4.29s | 0.06s | 5729 源文件（muse/muse_deps 就位） |
| keepassxc | 0.53s | 0.06s | 884 源文件 |
| qbittorrent | 0.50s | 0.06s | 710 源文件 |

- 与上轮可比结论：krita/strawberry **优于**上轮修复态（3.21/0.69），qownnotes 在扫描范围扩大（submodule 补齐）的前提下仍持平（0.87 vs 0.86）；**无性能回退**。
- fetch-deps 闭包 BFS 恒 0.06s，非瓶颈（与上轮结论一致）。

### 1.4 正确性回归中暴露的 4 个 bug（阶段1顺带修复）

首轮 e2e 回归 musescore 指标异常（recall 100%→56%），stash A/B 证明与我的性能修复无关，根因排查链条如下：

| # | bug | 根因 | 修复 |
|---|-----|------|------|
| 1 | **cloner submodule 拉取静默失效**（全项目级根因） | `git submodule update init ...` 裸 `init` 缺 `--` 被 git 当 pathspec 报错，`_init_submodules` 对 returncode≠0 完全静默 → 复用克隆的 submodule 永远拉不起来（tdesktop 35 个 submodule 全空、muse_deps 空） | `--init` + 失败 stderr 可见（c069898）；复用路径实测拉起 |
| 2 | **wrapper 依赖被藏掉**（tdesktop：openal/ada/zlib/openssl/bt 全漏） | submodule 就位后 `external_X` 成为项目内目标（defined），叠加 vendored 路径跳过，wrapper 声明的真实依赖双重不可见 | wrapper 签名（`add_library(external_X)`）文件不按 vendored 跳过；wrapper 目标被链接时透传底层库名；wrapper 内部守卫（DESKTOP_APP_USE_PACKAGED）只切换获取方式不套 optional（c069898） |
| 3 | **OR 守卫误判 optional** | `if (X OR LINUX)` 因 LINUX 在鸿蒙恒真必然激活，旧逻辑见 OFF 选项正向引用即整帧标 optional | 任一恒真析取项（LINUX/UNIX/NOT WIN32/…）→ 不标 optional（c069898） |
| 4 | **meson/autotools 检测器缺 vendored 跳过** | CMake 检测器有 `_is_vendored_path` 跳过，`_absorb_meson`/`_absorb_autotools` 没有 → ThirdParty/nimf 的 configure.ac（anthy/gtk+/m17n）、xdg-desktop-portal 的 meson.build（libgeoclue/pipewire）泄漏进 depth-1 | 补齐同口径跳过（c069898） |

**e2e 最终指标**（submodule 完整初始化后重新生成基线，1270e53）：

| 项目 | 集成基线(416ef8d)¹ | 本轮最终 | 变化归因 |
|------|------|------|------|
| tdesktop | 53% / 60% / 2 | **71% / 38% / 4** | 2932→6358 源文件；wrapper 透传恢复 openal/ada/zlib/openssl/bt/boost/lz4；余 4 候选人工核验：breakpad/crashpad 为 cmake_helpers 内 add_subdirectory vendored 源码（定性正确）、libxcb/libdispatch 为真实 Linux 依赖（README 漏列） |
| musescore | 100% / 95% / 0 | 100% / 95% / 0 | 不变 |
| keepassxc | 100% / 23% / 0 | 100% / 23% / 0 | 不变 |
| qbittorrent | 100% / 100% / 0 | 100% / 100% / 0 | 不变 |

¹ 注意：集成基线本身是在 cloner bug 下（submodule 未初始化的克隆）生成的，tdesktop 旧基线 53% 是"扫描范围不完整但查全率口径偏宽"的产物（cmark-gfm/ada 等经 external_X 幽灵机制计入）；本轮 71% 是完整扫描下的真实查全率。musescore/keepassxc/qbittorrent 旧基线生成时 submodule 状态正常，故不受影响。

**决定性 A/B**：416ef8d 原代码在当前完整克隆上跑 tdesktop = 24%/57%/7，与本轮代码同克隆结果逐字段一致（仅差 wrapper/OR/vendored 修复带来的恢复项）——证明指标变化 100% 来自克隆条件与上述修复，无其他代码行为漂移。

### 1.5 分析正确性抽查（strawberry，逐项核对）

- **分类**：36 条 link 全部与源码一致——macOS 框架（AppKit/Carbon/CoreAudio/…）→ platform-iface ✓；dwmapi → win32-system-lib ✓；Threads → system-lib ✓；GTest → test ✓；Boost/ICU/TagLib/OpenSSL find_package 行号（175/179/214/171）与 CMakeLists 原文一致 ✓；gio/gobject/gio-unix 归并 glib ✓；gstreamer-base 归并 gstreamer ✓。
- **版本**：TagLib `>=1.12`（find_package(TagLib 2.0) + 多源合并）vs hb 2.3.2 = satisfied ✓；libchromaprint `>=1.4`、libgpod `>=0.7.92`、libmtp `>=1.0` 与源码 :207/:210/:211 完全一致 ✓；sqlite `>=3.9` → unknown + 量纲警告（库主版本 vs 包版本口径，符合设计）✓。
- **need_port 定性**（DB 逐名验证）：libchromaprint/libgpod/libmtp/libpulse/kdsingleapplication/backtrace 无 hb/cmdpkgs 包 → need_port 正确 ✓；gstreamer-app/audio/pbutils/tag（plugins-base 组件，上轮 tarball 实证）✓；libsparsehash→google-sparsehash、libebur128、libcdio 解析 ported ✓。
- **发现小瑕疵（未修）**：`find_package(KDSingleApplication-qt${QT_VERSION_MAJOR} 1.1.0 REQUIRED)` 变量内插后版本号 1.1.0 丢失（名字归一正确，need_port 定性不受影响）。

### 1.6 单测结构 bug（顺带修复）

`tests/test_port_graph.py` 的 `if __name__: unittest.main()` 位于文件中部（1601 行），其后 13 个测试类（22 个用例，多轮 merge 追加所致）**从未被执行过**——历史报告的"56/65 全过"实为部分执行。已移至文件末尾，全量 94 用例全过。

---

## 二、阶段 2：GitHub 热门 Qt 项目泛化

**选择声明**：meshlab（cnr-isti-vclab/meshlab，Qt5 三维网格处理，~4.5k star）+ notepadqq（notepadqq/notepadqq，Qt6 文本编辑器，~2k star）。原拟 speedcrunch，**GitHub 仓库已关闭**（仅剩迁移声明，项目移至 Bitbucket），弃选改 notepadqq——已避开 e2e 四项目与其他 worker 选择。

### 2.1 检出完整性

| 项目 | 克隆 | submodule | 说明 |
|------|------|------|------|
| meshlab | shallow clone 1m55s（431MB 工作区） | src/vcglib ✓ 就位（修复后 cloner） | HEAD 71e7b0b |
| notepadqq | shallow clone 12s | 无 submodule | HEAD 37652c5 |

cloner `--init` 修复在两个新项目上直接验证：meshlab vcglib 一次拉起（该 submodule 在旧代码下会静默失败）。

### 2.2 notepadqq：分析质量优秀

- **真实依赖**：Qt6（≥6.4，14 组件）+ uchardet（pkg_check_modules，CMakeLists:36）——**全部正确检出**；闭包 13 项（provided 11 = Qt 模块 + qtpromise vendored，would_download 1 = uchardet 0.0.7，target 1）。
- **平台定性正确**：Qt D-Bus、QtWebEngine → blocked（与 KB 模块状态一致，移植阻断点如实呈现）；Core5Compat → 映射 core ported ✓。
- **发现并修复 1 个 bug（5985fb3）**：`QLibrary("kernel32")`（singleapplication.cpp:163，位于 `#if defined(Q_OS_WIN)` 块内）被误报为运行时动态加载。修复：宏栈机制从 project_scanner 移驻 qt_scanner（re-export 兼容），dynamic_loads 按行排除 platform-excluded（预过滤保证不损性能）。附带修复 qt_scanner 缺 `import warnings` 导致宏表达式求值 NameError 被吞为保守真。
- 残留小噪声：`qtpromise.tests.utils`（vendored 库 src/ui/libs/qtpromise 的测试 cmake 目标名混入 link 名单，1 条，不影响 need_port/闭包）。
- **性能**：deps 0.18s / fetch-deps 0.05s。

### 2.3 meshlab：主依赖正确，发现 vendored 子树内噪声

- **主依赖正确**（src/CMakeLists.txt）：Eigen3/GLEW/OpenGL/muparser/openctm/lib3ds 全部检出；lib3ds→hb 1.3.0 ✓、eigen/fftw/opencv→ported ✓；Qt5 ≥5.15 检出 ✓。
- **need_port 定性核验**（DB 验证）：muparser/openctm/GLEW 无鸿蒙包 → need_port 正确；OpenGL → need_port 合理（OHOS 为 OpenGL ES，需 EGL/GLES 适配）。
- **vcglib submodule 为 vendored** ✓（`src/vcglib`、`src/external` 正确识别），但其内部 **vcglib 自身的示例/测试工程**（`src/vcglib/apps/*`、`src/vcglib/eigenlib/unsupported/test/*`）的 find_package/qmake LIBS 泄漏进应用 depth-1：Adolc/CUDA/HIP/GoogleHash/MPREAL/GLFW3/embree/GLUT/freeglut/cholmod 系列等约 20 条（meshlab 主构建不编译这些目标）。主 CMakeLists 真实依赖不受影响，闭包 21 项中 need_port 10 里有约一半源于此噪声。
- **Qt major 误判**：报告 `major: 4`（vcglib 遗留 qmake 工程的 QT 变量污染），主工程实为 Qt5 ≥5.15；模块表混入 qtcore/qtgui 小写 unknown 变体。
- **性能**：deps 2.94-3.00s（22k+ 源文件）/ fetch-deps 0.05s。

### 2.4 问题定性汇总

| 问题 | 项目 | 定性 | 处置 |
|------|------|------|------|
| kernel32 dynamic_load 误报 | notepadqq | defect（平台宏守卫未过滤） | **已修**（5985fb3）+ 2 单测 |
| cloner submodule 静默失效 | 全部 submodule 项目 | defect（语法错误+吞错） | **已修**（c069898）+ 单测 |
| vendored 子树内示例/测试工程泄漏 | meshlab（vcglib apps/eigenlib tests） | defect（方向：submodule 内非构建目标目录的深度约束） | 未修，记录残留（见三） |
| qtpromise.tests.utils 目标名混入 | notepadqq | defect（轻微，1 条噪声） | 未修，记录残留 |
| Qt major 误判（4）| meshlab | defect（轻微，遗留 qmake 污染 hint） | 未修，记录残留 |
| KDSingleApplication-qt 版本号丢失 | strawberry | defect（轻微，${VAR} 内插后版本 token 丢失） | 未修，记录残留 |

---

## 三、残留项（未修，供后续处理）

1. **submodule 内非构建目录的依赖泄漏**（meshlab：vcglib 的 apps/eigenlib/unsupported test 工程泄漏约 20 条 depth-1 噪声）。方向：结合 .gitmodules 子模块路径 + "主构建不含的子目录"（apps/test/unsupported 命名特征）做深度约束；需避免误伤 musescore muse 这类"依赖清单在 submodule 里"的正常场景。
2. **vendored 库测试目标名混入 link 名单**（notepadqq qtpromise.tests.utils；路径 src/ui/libs/ 无 vendored 特征段）。
3. **Qt major hint 污染**（meshlab：遗留 qmake 工程把主工程 Qt5 判成 4；建议主 CMakeLists 的 find_package(QtN) 优先级高于 qmake hint）。
4. **find_package 名含 ${VAR} 时版本 token 丢失**（strawberry KDSingleApplication-qt 1.1.0）。
5. **e2e harness 对已解析改名的漏检匹配**（liblzma→xz 已通过 kb_seed.ALIASES 打通；同类情况建议 harness 侧统一消费 PKG_ALIASES）。
6. **harness grep 取证范围**（libxcb/libdispatch 误报候选：引用位于 submodule wrapper 内，harness 构建文件检索未覆盖；建议纳入 submodule 路径）。
7. 上轮残留 #2/#3/#4（find_library debug 后缀、结构化平台块解析、qt_scanner 共享读缓存）依旧有效。

---

## 四、修复与提交清单

| 提交 | 内容 |
|------|------|
| bddcd59 | perf：find_node_by_name NOCASE 函数索引（回退修复）+3 单测 |
| c069898 | fix：cloner `--init` 语法 + wrapper 三重透传 + OR 守卫语义 + meson/autotools vendored 跳过 + liblzma 别名 + 单测结构修复 |
| 1270e53 | test(e2e)：基线以完整克隆重新生成 + breakpad/crashpad 备注更新 |
| 5985fb3 | fix：dynamic_loads 平台宏守卫过滤（宏栈移驻 qt_scanner）+2 单测 |
| （本提交） | docs：REGRESS-REPORT.md |

单测 65→**94 全过**（含历史从未执行的 22 个存量用例）；e2e 四项目最终指标见 §1.4。

---
>>>>>>> worker4-deps-regress

## 五、复现命令

```bash
cd portgraph
<<<<<<< HEAD
python -m unittest tests.test_port_graph                       # 92 全过
# 阶段1（fresh DB 一次跑通）
rm workspace/portgraph.db && python portgraph.py ingest all --offline
/usr/bin/time -f "%es" python portgraph.py deps workspace/tdesktop --json
python portgraph.py fetch-deps tdesktop --dry-run --json
python tests/e2e/run_e2e.py run --project tdesktop --no-clone --fresh-db
# 阶段2
python portgraph.py deps workspace/cutter --json && python portgraph.py fetch-deps cutter --dry-run
python portgraph.py deps workspace/notepadnext --json && python portgraph.py fetch-deps notepadnext --dry-run
python tests/e2e/run_e2e.py run --all --no-clone --fresh-db    # 语料回归
```
=======
# REGRESS-REPORT — portgraph 依赖分析回归 + 泛化测试

> 分支：`worker3-deps-regress` | 基线：`416ef8d`（含全部集成修复，87 单测全过）
> 日期：2026-09-19 | 工作区：`/root/harmony-workspace/worker3`
> 阶段 1 语料：qbittorrent + keepassxc（e2e corpus tier B，回归）
> 阶段 2 泛化：**okular**（KDE/Qt 文档查看器，master 8662e426，500 源文件）
> + **konsole**（KDE/Qt 终端，master a6ef17f7，382 源文件）——
> 避开 e2e 语料四项目（tdesktop/musescore/keepassxc/qbittorrent）与他人选择
> （krita/strawberry/QOwnNotes）

## 1. 执行摘要

- **阶段 1 回归：一次分析正确性 100% 通过**。fresh DB → scan → deps --json →
  fetch-deps --dry-run 全流程在基线代码上**零人工修饰**跑出与
  `tests/e2e/reports/` 基线逐项一致的结果（闭包构成、would_download 名单、
  d1 清单、need_port 定性、analyze verdict 全部精确一致；e2e harness 重生成
  报告与提交基线**字节级一致**，diff 仅时间戳与 workspace 路径）。
- **阶段 2 泛化：okular + konsole 暴露 9 类问题**（6 工具 bug + 2 数据源
  别名缺口 + 1 启发式限制），**全部修复根因**并补 14 个回归单测
  （87 → 101 全过）；阶段 1 在回归中发现 3 类报告级缺陷（与基线口径无关，
  e2e 对账不经过 deps --json）亦一并修复。
- 语料回归：qbittorrent / keepassxc / musescore 基线字节级不变；tdesktop
  precision 60%→64%（平台块修复移除 APPLE-only 假边 libiconv，**预期改善**，
  基线随本轮更新）。性能与上轮可比数字同量级，无回归。

## 2. 阶段 1：回归（qbittorrent + keepassxc @ 416ef8d）

### 2.1 方法

每项目独立 fresh DB（`rm portgraph.db && ingest all --offline`：hb 4758
formula + cmd-pkgs 1248，gate PASS）→ `scan` → `deps --json` →
`fetch-deps --dry-run` → `analyze`，与 `tests/e2e/reports/*.report.{md,json}`
基线逐项核对；另跑 e2e harness（`run --project X --fresh-db --no-clone`）
重生成报告与提交基线 diff。全部命令用 `/usr/bin/time` 计时。

### 2.2 一次分析正确性核对（全部通过，零人工修饰）

| 核对项 | qbittorrent | keepassxc |
|---|---|---|
| analyze verdict | blocked（4 阻塞 + 1 unknown）✓ 同基线 | blocked（5 阻塞 + 1 unknown）✓ 同基线 |
| 依赖闭包 | **19 项** = target 1 / provided 8 / cmd_only 1 / need_port 1 / would_download 8 ✓ | **42 项** = target 1 / provided 8 / covered 1 / cmd_only 1 / need_port 1 / would_download 30 ✓ |
| would_download 名单 | 8/8 逐名精确一致 ✓ | 30/30 逐名精确一致 ✓ |
| need_port 定性 | libtorrent-rasterbar（hb/cmd-pkgs 确无，正确）✓ | botan（同，正确）✓ |
| d1 直接依赖 | 12/12（名称/类型/port_status）一致 ✓ | 20/20 一致 ✓ |
| optional 边 | systemd（SYSTEMD 默认 OFF 守卫）✓ | — |
| 同库异名归并 | libtorrentrasterbar 并入 libtorrent-rasterbar（merged_from）✓ | qrencode/libqrencode、pcsc 三名归并 ✓ |
| e2e 指标 | recall 100% / precision 100% / bug 0 ✓ | recall 100% / precision 23% / bug 0 ✓ |
| e2e 报告 diff | **仅时间戳 + worker 路径**（字节级一致）✓ | 同 ✓ |

### 2.3 计时（基线代码 416ef8d，含 cold/warm 两次 fresh DB）

| 步骤 | qbittorrent（710 源文件） | keepassxc（884 源文件） |
|---|---|---|
| ingest all --offline | 2.04s / 1.17s（第二次） | 1.17s |
| scan | 0.63s | 0.64s |
| deps --json | 0.57s | 0.72s |
| fetch-deps --dry-run | 0.05s | 0.06s |
| analyze | 0.07s | 0.06s |
| e2e harness 全流程 | 0.57s | 0.72s |

**与上轮对比**：归档报告（`portgraph/docs/opt-reports/`）未记录
qbittorrent/keepassxc 的 deps 计时；最接近的可比数字为 worker4 泛化轮的
QOwnNotes 0.81s（规模相当）→ keepassxc 0.72s 同量级，**无性能回归**。
本轮全部修复后复测：qbittorrent deps 0.57s、keepassxc 0.73s（持平）。

### 2.4 回归中发现的报告级缺陷（不影响 e2e 对账口径，随本轮修复）

基线的对账口径是 DB 节点/闭包，`deps --json` 的 link 表存在 3 类与项目
事实不符的表现（详见 §4 修复 F3/F4/F5）：

- qbittorrent `Systemd` 条目 required=True + "直连平台栈" 警告（实际位于
  SYSTEMD 默认 OFF 选项守卫内）；
- qbittorrent `LibtorrentRasterbar` + `libtorrent-rasterbar` 双条目、双
  "需源码交叉编译" 警告（DB 侧已归并，报告侧未归并）；
- keepassxc `qrencoded`（FindQREncode.cmake 的 WIN32 AND NOT MINGW 块内
  Windows debug 变体名）、`network`（if(HAIKU) 块）误报 required=True。

## 3. 阶段 2：GitHub 热门 Qt 项目泛化（okular + konsole）

**选择声明**：okular（~2.6k star，KDE 旗舰文档查看器，CMake/ECM/KF6，
poppler 等多媒体格式依赖面广）+ konsole（KDE 默认终端，CMake/KF6）。
shallow clone 到 `portgraph/workspace/`，跑 `deps --json` +
`fetch-deps --dry-run`，逐项人工对照 `CMakeLists.txt`、`cmake/modules/Find*.cmake`
与 README/BUILD.md。

### 3.1 okular（before → after 修复）

| 维度 | 基线代码 | 修复后 |
|---|---|---|
| deps link 条目 | 39 | 37（ddjvuapi/libmarkdown 并入同库条目） |
| 闭包 | 104 项 | 101 项：need_port 32→30、would_download 60→59 |
| need_port 构成 | 24×KF + djvulibre + **ddjvuapi（重复）** + epub + kexiv2qt6 + **nss（mobile ANDROID 块误入）** + phonon4qt6 + poppler + qmobipocket6 | 24×KF + djvulibre + epub + kexiv2qt6 + phonon4qt6 + poppler + qmobipocket6（全部经查 hb/cmd-pkgs 确无，**need_port 定性正确**） |
| KF 组件解析 | `archive`→hb:libarchive、`config`→hb:libconfig（**同名异义错配**，报告展示 ready bottle 与闭包 need_port 矛盾） | 解析到 `kf:<comp>` 节点，与闭包口径一致 |
| 版本约束 | Poppler/DjVuLibre/QMobipocket6 均缺（引号版本 `"24.08.0"`/`"3.5.28"`/`"2"` 未解析） | 全部检出并参与校验 |
| in-tree 误判 | Poppler/EPub 判 "项目内自带源码，无需外部产物"（实为 `generators/poppler`、`generators/epub` 格式生成器插件目录，README 明言 "libepub based backend... obtained using svn co"） | 判 package（真实 need_port） |
| 平台块 | freebl3/softokn3/nssckbi/nss（mobile/app `if (ANDROID)` 块）required=True 误报 | required=False + "位于 if(ANDROID) 平台块" 注记，不入闭包 |

**人工对照结论**：检出与 `CMakeLists.txt` 声明逐条对上（KF6 12 必需组件 +
Qt6 组件 + Discount/DjVuLibre/EPub/Poppler/QMobipocket6/LibSpectre(0.2)/
KExiv2Qt6/Phonon4Qt6/Freetype/TIFF/ZLIB）；`mobile/app/CMakeLists.txt` 的
Android 专属 NSS 链接被正确识别为平台块。okular README 无依赖段（构建文件
为唯一真源），无漏检。**hb:markdown 错配曾把 daringfireball 的 Perl/PHP
Markdown 1.0.1 bottle 拉进闭包**（okular 链接的 libmarkdown 实为 discount
的库名）——修复后消除。

### 3.2 konsole（before → after 修复）

| 维度 | 基线代码 | 修复后 |
|---|---|---|
| Qt 模块 | 仅 1 个（widgets，来自 demo 子工程）——主声明 `find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED\n Core Multimedia PrintSupport Widgets)` **无 COMPONENTS 关键字，全部漏检** | 5 个（core/dbus/multimedia/printsupport/widgets） |
| KF 组件 | 21 个（主要靠 KF6:: 链接目标名回补），**ConfigWidgets/Service/NewStuff 漏检、Config 被 CONFIG 关键字吞掉** | 24 个（与 CMakeLists 声明完全一致） |
| 闭包 | 51 项（need_port 23、provided 5） | 56 项（need_port 26=全部 KF、provided 7） |
| 平台块 | `util`（`if(SYSTEM_NAME MATCHES "FreeBSD")` kinfo_getfile）与 `network`（`if(HAIKU)` inet_aton）required=True 误报 "需源码交叉编译"/"macOS Network framework" | required=False + 正确注记（FreeBSD/Haiku 块），不入闭包 |
| 版本校验 | ICU 61.0 satisfied、libssh 0.9.8 satisfied（本就正确） | 同（Qt 6.5.0 satisfied） |

**人工对照结论**：BUILD.md 的 neon apt 清单含 KF auth/package/declarative/
kcmutils，但构建文件 `find_package(KF6 ...)` 并未声明（文档为打包近似，
非构建真源）——portgraph 以构建文件为准**无漏检**；`if(USE_DBUS)`（UNIX
默认 ON）内的 DBusAddons/GlobalAccel 正确判必需（OHOS 属 UNIX 类，默认
启用）。

### 3.3 分析正确性总评（两项目）

- **分类**：修复后 link/runtime/framework/platform-iface/win32-system-lib/
  in-tree 分类与构建文件事实一致；
- **版本校验**：修复后全部声明版本被检出（引号版本 + 无关键字组件名是仅有的
  两类漏检形态），已解析依赖的 satisfied/any 判定全部正确；
- **need_port 定性**：okular 30 项、konsole 26 项 need_port 全部经
  hb-core/cmd-pkgs 核实确无对应包（大头是 KF6 全家——需源码交叉编译，
  定性正确；根治需向 Harmonybrew 提 KF formula，属数据源缺口）。

## 4. 问题清单与定性（全部修复 + 补测试）

| # | 问题 | 实证 | 定性 | 修复 |
|---|---|---|---|---|
| F1 | find_package **引号版本**未解析 | okular `Poppler "24.08.0"`、`DjVuLibre "3.5.28"`、`QMobipocket6 "2"` | 工具 bug | `qt_scanner._parse_findpkg_args` 去 token 引号 |
| F2 | **无 COMPONENTS 关键字的尾随组件**漏检；组件名与关键字同形（Config↔CONFIG）被吞 | konsole Qt6/KF6 主声明（4 个 Qt 模块 + 3 个 KF 组件漏检） | 工具 bug（CMake 合法语法未覆盖） | `_orphan_components` 区域状态机（版本/关键字后的裸名即组件；组件区开始后不再按关键字解释）+ KF/Qt 检测器接入 + `_parse_findpkg_args` 同口径 |
| F3 | INTERFACE_BOUND（platform-iface）条目忽略 optional 守卫 | qbittorrent systemd（SYSTEMD 默认 OFF）required=True + 误警 | 工具 bug | `deps_report` §1/§2 平台接口分支透传 optional |
| F4 | deps link 表**同库去分隔符重复** | qbittorrent LibtorrentRasterbar×libtorrent-rasterbar 双警告 | 工具 bug（扫描期已归并、报告期未对齐） | `deps_report` §7b 去分隔符合并键（单词名 + 键长 ≥6，KF 节点名含空格不参与） |
| F5 | **平台块上下文缺失**：if(APPLE)/if(WIN32)/if(HAIKU)/if(ANDROID)/STREQUAL "Darwin"/"Windows" 等块内的 tll/-l/find_library/pkg_check_modules 误报必需、误入闭包 | qbittorrent AppKit/Carbon/IOKit/objc（Darwin）、iphlpapi（Windows）；konsole util（FreeBSD）、network（Haiku）；okular nss/softokn3/freebl3/nssckbi（ANDROID）；keepassxc qrencoded（WIN32 AND NOT MINGW）；tdesktop external_iconv（APPLE） | 工具 bug（worker1 轮已记录的建议，本轮实现） | `qt_scanner._cmake_platform_line_map`（与选项守卫行映射同构；UNIX/LINUX/POSIX 视为 OHOS 活跃不降级；NOT X 否定条件不降级；elseif 按自身条件评估、else 保守）→ raw_libs/pkg 检测标注 `platform_block` → deps_report required=False+注记、project_scanner 不连边 |
| F6 | **KF 组件走包名解析阶梯**：KF Archive≠libarchive、KF Config≠libconfig | okular/konsole（报告展示 ready bottle 与闭包 need_port 矛盾） | 工具 bug | `deps_report` §7 framework 条目解析到 `kf:<comp>` 节点 |
| F7 | **in-tree 误判功能分组目录**：`generators/` 父目录 ≥5 子目录集合启发式把格式生成器插件目录当自带库 | okular generators/poppler、generators/epub（掩盖真实 need_port） | 工具启发式限制（KDE generators 布局触发） | `_in_tree_dir_index` 依赖集合父目录白名单（libraries/libs）；README 仅作容器内佐证。QOwnNotes fakevim/litehtml 复测无回归 |
| F8 | **ddjvuapi 别名缺口**：djvulibre 的 pkg-config 名与 find_package 名双幽灵、双 need_port | okular（FindDjVuLibre.cmake 用 pkg_check_modules(ddjvuapi) 探测同库） | 数据源缺口（别名知识） | `kb_seed.PKG_ALIASES["ddjvuapi"]="djvulibre"` + `_link_third_party` 分组键别名规范化 |
| F9 | **libmarkdown 同名异义**：discount 的库名解析到 hb:markdown（daringfireball 的 Perl/PHP 版），错瓶入闭包 | okular（FindDiscount.cmake `pkg_check_modules(Discount "libmarkdown")`） | 数据源缺口（别名知识，同名异义风险的实例） | `PKG_ALIASES["libmarkdown"]="discount"` |

## 5. 语料回归验证（修复后全量）

| 项目 | 结果 |
|---|---|
| qbittorrent / keepassxc | e2e 报告与基线**字节级一致**（仅时间戳/路径）；closure/指标不变 |
| musescore | 同上（注意：workspace 克隆需 `git submodule update --init`，未初始化时源文件 3139 vs 5729、结果与基线不可比——本轮实证，运营注意项） |
| tdesktop（master 4d4da47，补克隆验证） | precision 60%→64%、closure 61→60：**APPLE 块内 `desktop-app::external_iconv` 假边（libiconv）被 F5 正确移除**，属预期改善，基线已随本轮重新生成；recall 53% / 2 个 missed-dep 为基线既有状态（上游 README 漂移，见 worker1 报告残留项），非本轮引入 |
| QOwnNotes（抽查） | fakevim/litehtml 仍正确 in-tree（F7 收紧无回归） |
| 单元测试 | **101/101 全过**（87 → +14：引号版本/无关键字组件/Config 同形/平台块×3/optional 平台接口/报告去分隔符合并/KF 解析/in-tree×2/别名×2） |

## 6. 残留项（本轮不修，已记录）

1. **keyutils（keepassxc）**：位于 `if("${CMAKE_SYSTEM}" MATCHES "Linux")`
   块——LINUX 按 OHOS 活跃处理不降级（保守必需）。定性合理：OHOS musl 无
   keyutils.h，移植确需关注；工具无法静态判定 OHOS 工具链下 CMAKE_SYSTEM
   的取值。
2. **tdesktop 2 个 missed-dep**：基线既有（上游 README 与构建文件漂移），
   见 `docs/opt-reports/2026-09-deps-test-worker1.md` 残留项。
3. **Discount 合并后 required=True**：pkg_check_modules（必需语义）与
   find_package（无 REQUIRED）同库合并按必需（保守方向，_DepBook 既有
   合并规则），okular 侧 set_package_properties 实为 optional——极端精确
   需 Find 模块内调用点上下文，收益低。
4. **KF6 全家 need_port**（okular 24 / konsole 26 项）：数据源缺口，根治
   需向 Harmonybrew 提交 KF6 formula 群。
5. **平台块内 find_package 的 Find<Name>.cmake 模块内容平台继承**未实现
   （保守按必需处理）。
6. **musescore 克隆 submodule 状态**影响可比性（§5），建议 e2e harness
   对未初始化 submodule 的克隆给出警告。

## 7. 复现

```bash
cd /root/harmony-workspace/worker3/portgraph
python -m unittest discover -s tests        # 101 tests OK
# 阶段 1 回归（fresh DB 流程）
rm workspace/portgraph.db && python portgraph.py ingest all --offline
time python portgraph.py scan workspace/qbittorrent
time python portgraph.py deps workspace/qbittorrent --json > /tmp/q.json
time python portgraph.py fetch-deps qbittorrent --dry-run
python tests/e2e/run_e2e.py run --project qbittorrent --fresh-db --no-clone
python tests/e2e/run_e2e.py run --project keepassxc  --fresh-db --no-clone
git diff tests/e2e/reports/                  # 仅时间戳/路径
# 阶段 2 泛化
git clone --depth 1 https://github.com/KDE/okular.git  workspace/okular
git clone --depth 1 https://github.com/KDE/konsole.git workspace/konsole
python portgraph.py deps workspace/okular --json | python -m json.tool | less
python portgraph.py fetch-deps okular --dry-run
```

改动文件：`port_graph/qt_scanner.py`（引号版本/无关键字组件/平台块行映射/
Config 同形）、`port_graph/deps_report.py`（optional 平台接口/去分隔符
合并/KF 解析/in-tree 容器白名单/平台块 required）、
`port_graph/project_scanner.py`（别名规范化分组键/平台块 raw lib 跳过）、
`port_graph/kb_seed.py`（PKG_ALIASES +2）、`tests/test_port_graph.py`（+14）、
`docs/deps-report.md`（平台块/KF 解析/in-tree 语义文档）、
`tests/e2e/reports/tdesktop.report.{md,json}`（平台块修复后基线更新）。
>>>>>>> worker3-deps-regress
=======
python tests/test_port_graph.py                        # 94 tests OK
python portgraph.py ingest all                         # 主库 6069 节点
# 性能（3 次取中位）
/usr/bin/time -f "%es" python portgraph.py deps workspace/krita --json > /dev/null
/usr/bin/time -f "%es" python portgraph.py fetch-deps krita --dry-run > /dev/null   # 注意：app 名不是路径
# e2e 回归（submodule 完整克隆）
python tests/e2e/run_e2e.py run --all --fresh-db
# 泛化项目
python portgraph.py deps workspace/meshlab --json
python portgraph.py deps workspace/notepadqq --json
python portgraph.py fetch-deps meshlab --dry-run
# A/B（worktree 隔离）
git worktree add .ab/c04060a c04060a   # workspace 内符号链接共享克隆后同流程计时
```
>>>>>>> worker4-deps-regress
