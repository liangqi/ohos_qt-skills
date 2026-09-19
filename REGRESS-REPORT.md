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

## 五、复现命令

```bash
cd portgraph
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
