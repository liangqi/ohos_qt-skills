# TEST-REPORT：portgraph 依赖分析 × corpus-a（e2e 语料 tier C）实测与优化

> 分支 `worker1-deps-test`（基线 f98a2e7，44 单测全过）｜工作区 `~/harmony-workspace/worker1`
> 测试对象：`portgraph deps` / `fetch-deps` / e2e 对账 harness（`portgraph/tests/e2e/run_e2e.py`）
> 语料：corpus-a（corpus-a，tier C，真实项目，浅克隆 HEAD 2026-09-19）+ 全语料回归（corpus-c / corpus-b / corpus-d）
> 约束遵守：未改动 e2e 对账口径（recall/precision 公式、oracle 文件、BUG_CLASSES 定义均未动）；所有修复以构建文件取证定位根因，不以"凑指标"为目的。

---

## 1. 指标前后对比

### 1.1 corpus-a（本轮目标项目）

| 指标 | 修复前基线¹ | 修复后 | 变化 |
|---|---|---|---|
| 检出召回率 | 24%（4/17） | **53%（9/17）** | +29pp |
| 检出精确率² | 80% | 60% | −20pp（见说明） |
| Bug 候选 | 9（missed-dep 7 + resolution-gap 2） | **2（missed-dep 2，均为残留盲区）** | −7 |
| 误报（false-positive） | 0 | 0 | — |
| 直接依赖（depth-1 非 Qt 模块） | 6（4 包 + 2 幽灵） | 19（12 包 + 7 幽灵） | 检出面扩大 |
| deps 报告 link 分类 | 10 项 | 26 项 | +16 |
| fetch-deps 闭包 | 38（need_port 2） | 61（need_port 7） | 更完整 |

¹ 修复前基线为本轮在**新克隆**（corpus-a HEAD 已前移：新增 lib_fido2/fido2 支持、Python3 网格 codegen 等）上重跑的结果：recall 24% / precision 80% / bug 9。仓库里上一轮提交的旧报告（recall 24% / precision 100% / bug 7）基于更早的克隆与主库 DB，不可直接对比。

² 精确率口径（既有公式，未改动）：`matched / (matched + readme-omitted + false-positive)`。下降原因不是误报（false-positive 始终为 0），而是**新检出的 6 个真实依赖 README 未列**（boost、cmark-gfm、glib、libfido2、libiconv、minizip，全部有 target_link_libraries 取证，归类 readme-omitted=portgraph 正确）进入了分母。即：精确率下降是"检出面扩大且全部为真"的口径性结果，非质量退化。

### 1.2 全语料回归（4 项目全部重跑，报告基线已更新提交）

| 项目 | 旧基线³ | 新基线 | 说明 |
|---|---|---|---|
| corpus-a | 24% / 100% / 7 | **53% / 60% / 2** | 见上 |
| corpus-c | 100% / 23% / 0 | 100% / 23% / 0 | 逐类计数完全一致，零回归 |
| corpus-b | 50% / 46% / 11 | **38% / 27% / 0** | bug 11→0；recall 变化主因上游 corpus-b-deps 重构（§3.2），非本轮代码回归 |
| corpus-d | 80% / 100% / 1 | **100% / 100% / 0** | libtorrent-rasterbar 漏检修复（版本后缀/lib 前缀解析统一） |

³ 旧基线取自上一轮提交的报告文件（旧克隆 + 旧主库 DB 状态）。

单元测试：44 → **56 全过**（新增 12 个，每项修复均有对应测试）。

---

## 2. 修复清单（根因 → 修复 → 测试）

### 2.1 工具侧（port_graph）

| # | 根因（构建文件取证） | 修复 | 测试 |
|---|---|---|---|
| T1 | **`target_link_libraries` 一律跳过 `::` 导入目标**（qt_scanner 旧逻辑 `or "::" in t: continue`）。corpus-a 全部三方库以 `desktop-app::external_zlib/external_openal/external_webrtc/...` 链接，真正的 find_package 位于未初始化的 `cmake/`（cmake_helpers）子模块——扫描器对此类工程接近失明，openssl/zlib/ffmpeg 仅靠 include 启发式侥幸检出 | 解析 `ns::external_<name>`：剥 `external_` 前缀入 raw_libs 并标 `ext_target=True`（高置信外部声明）；`PkgConfig::`（已由 pkg_check_modules 覆盖）、`Qt*::`/`kf` 前缀、项目内 add_library 定义的目标仍排除 | `TestExternalTargetLinks`（2 个） |
| T2 | **find_package(Python3) 建了运行时边** → 幽灵 `pkg-unknown:python3`（corpus-a cmake/generate_models.cmake:22 构建期网格烘焙，deps_report 侧早已归类 build-tool，图侧口径不一致） | `BUILD_TOOL_FINDPKG` 表移入 qt_scanner，project_scanner 过滤，两侧共享 | `TestBuildToolFindpkgFilter` |
| T3 | **win32 系统库误连边**：lib_fido2.cmake Windows 段的 `bcrypt` 会命中 cmdpkgs:bcrypt（OpenBSD 密码哈希库，无关库） | `WIN32_SYSTEM_LIBS` 表移入 qt_scanner 并扩充（bcrypt/hid/winusb/cfgmgr32），project_scanner 扫描期过滤 | `TestWin32LibNoFalseEdge` |
| T4 | **别名缺口**（external_* 裸名 → 鸿蒙包）：openal→cmdpkgs:openal-soft（OpenAL Soft，kcat）、iconv→hb:libiconv、boost_regex→hb:boost、cmark_gfm→hb:cmark-gfm（分隔符差异）、qr_code_generator→cmdpkgs:libqrcodegen（nayuki QR-Code-generator，cmd-pkgs 1.8.0 版本序列同源，已核实） | kb_seed.PKG_ALIASES 新增 5 条（均经 DB 包节点身份核实） | `TestPkgAliasescorpus-a` |
| T5 | **pkg-config 版本后缀名图侧不解析**：corpus-b corpus-b-deps `pkg_check_modules(... lilv-0 suil-0 zix-0 lv2)`，hb:lilv/hb:zix 存在但图侧产生幽灵（deps_report._resolve 早已支持该近似，两侧口径不一致） | kb_seed.resolve_package 增加 lib 前缀/去 lib 前缀/版本后缀剥离近似（与 deps_report._resolve 对齐） | `TestPkgConfigVersionSuffixResolve` |
| T6 | vendored 子模块（.gitmodules 声明，随项目编译）与外部包无区分：external_cmark_gfm 可解析包但 external_microtex/external_kcoreaddons 会产生误导性 need_port 幽灵 | project_scanner：external_target 未解析时先查 .gitmodules 折叠名（name/path 末段/url 末段），vendored 命中不建幽灵 | `TestExternalTargetLinks.test_graph_links_and_ghosts` |

### 2.2 harness 侧（run_e2e.py，证据/归因准确性，对账口径不变）

| # | 根因 | 修复 | 测试 |
|---|---|---|---|
| H1 | **取证 grep 逐行匹配**：corpus-a 的 target_link_libraries 每个链接项独占一行，逐行匹配漏掉全部多行语句证据（曾致 boost/glib/minizip/cmark-gfm 被误判 false-positive） | 强证据改全文 finditer + 行号回溯 | `test_grep_multiline_tll` |
| H2 | **`\b` 词界匹配不到下划线连写**：`external_xxhash`/`lib_zlib` 中 xxhash/zlib 前后是 `_`（word 字符），`\b` 不成立——上一轮曾因此把 zlib 误判误报（agent 笔记已记录） | 环视断言词界（字母数字外均算边界），并验证不误伤（zlib ⊄ zlibng） | `test_grep_boundary_matches_prefixed_target` |
| H3 | **幽灵节点一律报 resolution-gap（bug 候选）**：libudev（鸿蒙无 udev，HDF 驱动框架替代）、webrtc/ada/rnnoise 等真实外部依赖且库里确无对应包——幽灵是**正确检出**（fetch-deps 报 need_port 正确），不是 bug | 新增 `ghost_plausible_package()`：仅当库中存在形近已知包（别名命中 / 折叠名相等 / 子串且共享完整分隔分量，udev⊄uudeview）时报 resolution-gap，否则归 unknown-ok（该类已在 BY_DESIGN_CLASSES 预留，本轮首次启用） | `test_ghost_plausible_package` |
| H4 | **oracle 侧 vendored 无证据归类**：gsl/range-v3/hunspell 为 .gitmodules 子模块（corpus-a/ThirdParty/GSL 等），归 README过时 语义失真 | `vendored_submodule_match()`：按 .gitmodules 证据归 vendored（by-design 新类） | `test_vendored_submodule_match` |
| H5 | 名字匹配分隔符差异：`crash_reports` vs `crash-reports` 不匹配 | pg_canon `_`→`-` 折叠；README_ALIASES 增 qr-code-generator→libqrcodegen | `test_names_match_underscore_folding` 等 |

**口径说明**（为何不算"改对账口径"）：recall/precision 计算公式、oracle 文件内容、BUG_CLASSES（missed-dep/resolution-gap/false-positive）定义均未改动。本轮新增的 vendored/unknown-ok 归类只作用于**差异归因**（差异为什么存在），不改变"oracle 运行时依赖 × portgraph 直接依赖"的比对本身；vendored 项仍留在 recall 分母（保守口径，不因归类改善而抬高 recall）。

---

## 3. 定性为工具问题的残留项（未修复，已文档化）

### 3.1 corpus-a breakpad / crashpad 漏检（missed-dep ×2，唯一残留 bug 候选）

- **取证**：主仓库仅 macOS/macstore 平台守卫段有引用（CMakeLists.txt:2349 `find_program(CRASHPAD_HANDLER crashpad_handler)`、:2381 `target_link_frameworks(corpus-a PRIVATE Breakpad)`）；Linux 侧集成统一走 `desktop-app::external_crash_reports`（:97），其内部 breakpad/crashpad 二选一逻辑位于 **cmake/ 子模块（desktop-app/cmake_helpers）内部，浅克隆未初始化该子模块，扫描范围外**。
- **定性**：工具问题（未初始化子模块盲区），保留 missed-dep 分类 + overrides 人工备注，不掩盖。
- **可选后续方案**：clone 时 `--recurse-submodules`（代价：tg_owt/webrtc 等子模块体积巨大）；或按 .gitmodules 提示对缺失路径做降级标注（"该子模块内的声明不可见"）。已记入 `docs/deps-report.md` §已知限制。

### 3.2 corpus-b recall 50%→38%（非本轮代码回归，定性为工具覆盖范围问题）

- **取证**：上游 corpus-b-deps 子模块重构——旧提交以 find_package/pkg_check_modules 暴露系统依赖（alsa/jack/sndfile/tinyxml 等，旧报告 23 个 pg 侧节点由此而来）；新提交（6525edb）改为自定义 `set(DEP_LIBS sndfile)` / `DEP_TARGET` DSL，通用扫描器不可见。
- **定性**：工具覆盖范围问题（每项目自定义包装约定，通用工具只能覆盖 PACKAGE/LIBRARY 关键字类约定）。bug 候选从 11 → 0（旧 10 个 resolution-gap 中 lilv-0/zix-0 已由 T5 修复，其余随上游重构消失；旧 1 个 false-positive 为 util-linux，已不再出现）。

### 3.3 corpus-a lzma-sdk / liblzma / opus 归 readme-stale（盲区同 3.1）

- **取证**：主仓库构建文件确无任何引用（grep 为空）；liblzma/opus 由 cmake_helpers 的外部预编译 Libraries 目录或 tg_owt（WebRTC 栈）带入，README 声明粒度与主仓库可见声明天然错位。
- **定性**：与 3.1 同族的子模块/外部目录盲区，readme-stale 是当前扫描范围内的事实描述（overrides notes 已注明原因），非误分类。

### 3.4 语料漂移提示（非工具问题）

corpus-a 与 corpus-b 的克隆 HEAD 均已前移（corpus-a 新增 fido2/WebAuthn 栈与 Python3 构建期 codegen；corpus-b-deps 重构），oracle（reviewed）仍是旧 HEAD 语义。本轮全部差异已逐条人工复核归类；后续跑 e2e 前建议校对 oracle 与克隆 HEAD 的一致性。

---

## 4. 交付物清单

- 代码修复：`port_graph/qt_scanner.py`、`project_scanner.py`、`kb_seed.py`、`deps_report.py`
- harness 修复：`tests/e2e/run_e2e.py`
- 单测：`tests/test_port_graph.py` 44→56 全过（`python -m unittest tests.test_port_graph`）
- e2e 基线更新：`tests/e2e/reports/{corpus-a,corpus-c,corpus-b,corpus-d}.report.{md,json}`（4 项目全重跑，--fresh-db）
- overrides 更新：`tests/e2e/overrides/corpus-a.json`（移除 5 条已原生化的重分类，保留 breakpad/crashpad 残留备注）
- 文档：`docs/deps-report.md`（external_* 导入目标解析说明 + 未初始化子模块盲区已知限制）
- 提交：`worker1-deps-test` 分支（本报告与代码同批提交）
