<<<<<<< HEAD
# TEST-REPORT：portgraph 依赖分析 × tdesktop（e2e 语料 tier C）实测与优化

> 分支 `worker1-deps-test`（基线 f98a2e7，44 单测全过）｜工作区 `/root/harmony-workspace/worker1`
> 测试对象：`portgraph deps` / `fetch-deps` / e2e 对账 harness（`portgraph/tests/e2e/run_e2e.py`）
> 语料：tdesktop（Telegram Desktop，tier C，真实项目，浅克隆 HEAD 2026-09-19）+ 全语料回归（keepassxc / musescore / qbittorrent）
> 约束遵守：未改动 e2e 对账口径（recall/precision 公式、oracle 文件、BUG_CLASSES 定义均未动）；所有修复以构建文件取证定位根因，不以"凑指标"为目的。

---

## 1. 指标前后对比

### 1.1 tdesktop（本轮目标项目）

| 指标 | 修复前基线¹ | 修复后 | 变化 |
|---|---|---|---|
| 检出召回率 | 24%（4/17） | **53%（9/17）** | +29pp |
| 检出精确率² | 80% | 60% | −20pp（见说明） |
| Bug 候选 | 9（missed-dep 7 + resolution-gap 2） | **2（missed-dep 2，均为残留盲区）** | −7 |
| 误报（false-positive） | 0 | 0 | — |
| 直接依赖（depth-1 非 Qt 模块） | 6（4 包 + 2 幽灵） | 19（12 包 + 7 幽灵） | 检出面扩大 |
| deps 报告 link 分类 | 10 项 | 26 项 | +16 |
| fetch-deps 闭包 | 38（need_port 2） | 61（need_port 7） | 更完整 |

¹ 修复前基线为本轮在**新克隆**（tdesktop HEAD 已前移：新增 lib_fido2/fido2 支持、Python3 网格 codegen 等）上重跑的结果：recall 24% / precision 80% / bug 9。仓库里上一轮提交的旧报告（recall 24% / precision 100% / bug 7）基于更早的克隆与主库 DB，不可直接对比。

² 精确率口径（既有公式，未改动）：`matched / (matched + readme-omitted + false-positive)`。下降原因不是误报（false-positive 始终为 0），而是**新检出的 6 个真实依赖 README 未列**（boost、cmark-gfm、glib、libfido2、libiconv、minizip，全部有 target_link_libraries 取证，归类 readme-omitted=portgraph 正确）进入了分母。即：精确率下降是"检出面扩大且全部为真"的口径性结果，非质量退化。

### 1.2 全语料回归（4 项目全部重跑，报告基线已更新提交）

| 项目 | 旧基线³ | 新基线 | 说明 |
|---|---|---|---|
| tdesktop | 24% / 100% / 7 | **53% / 60% / 2** | 见上 |
| keepassxc | 100% / 23% / 0 | 100% / 23% / 0 | 逐类计数完全一致，零回归 |
| musescore | 50% / 46% / 11 | **38% / 27% / 0** | bug 11→0；recall 变化主因上游 muse_deps 重构（§3.2），非本轮代码回归 |
| qbittorrent | 80% / 100% / 1 | **100% / 100% / 0** | libtorrent-rasterbar 漏检修复（版本后缀/lib 前缀解析统一） |

³ 旧基线取自上一轮提交的报告文件（旧克隆 + 旧主库 DB 状态）。

单元测试：44 → **56 全过**（新增 12 个，每项修复均有对应测试）。

---

## 2. 修复清单（根因 → 修复 → 测试）

### 2.1 工具侧（port_graph）

| # | 根因（构建文件取证） | 修复 | 测试 |
|---|---|---|---|
| T1 | **`target_link_libraries` 一律跳过 `::` 导入目标**（qt_scanner 旧逻辑 `or "::" in t: continue`）。tdesktop 全部三方库以 `desktop-app::external_zlib/external_openal/external_webrtc/...` 链接，真正的 find_package 位于未初始化的 `cmake/`（cmake_helpers）子模块——扫描器对此类工程接近失明，openssl/zlib/ffmpeg 仅靠 include 启发式侥幸检出 | 解析 `ns::external_<name>`：剥 `external_` 前缀入 raw_libs 并标 `ext_target=True`（高置信外部声明）；`PkgConfig::`（已由 pkg_check_modules 覆盖）、`Qt*::`/`kf` 前缀、项目内 add_library 定义的目标仍排除 | `TestExternalTargetLinks`（2 个） |
| T2 | **find_package(Python3) 建了运行时边** → 幽灵 `pkg-unknown:python3`（tdesktop cmake/generate_models.cmake:22 构建期网格烘焙，deps_report 侧早已归类 build-tool，图侧口径不一致） | `BUILD_TOOL_FINDPKG` 表移入 qt_scanner，project_scanner 过滤，两侧共享 | `TestBuildToolFindpkgFilter` |
| T3 | **win32 系统库误连边**：lib_fido2.cmake Windows 段的 `bcrypt` 会命中 cmdpkgs:bcrypt（OpenBSD 密码哈希库，无关库） | `WIN32_SYSTEM_LIBS` 表移入 qt_scanner 并扩充（bcrypt/hid/winusb/cfgmgr32），project_scanner 扫描期过滤 | `TestWin32LibNoFalseEdge` |
| T4 | **别名缺口**（external_* 裸名 → 鸿蒙包）：openal→cmdpkgs:openal-soft（OpenAL Soft，kcat）、iconv→hb:libiconv、boost_regex→hb:boost、cmark_gfm→hb:cmark-gfm（分隔符差异）、qr_code_generator→cmdpkgs:libqrcodegen（nayuki QR-Code-generator，cmd-pkgs 1.8.0 版本序列同源，已核实） | kb_seed.PKG_ALIASES 新增 5 条（均经 DB 包节点身份核实） | `TestPkgAliasesTdesktop` |
| T5 | **pkg-config 版本后缀名图侧不解析**：musescore muse_deps `pkg_check_modules(... lilv-0 suil-0 zix-0 lv2)`，hb:lilv/hb:zix 存在但图侧产生幽灵（deps_report._resolve 早已支持该近似，两侧口径不一致） | kb_seed.resolve_package 增加 lib 前缀/去 lib 前缀/版本后缀剥离近似（与 deps_report._resolve 对齐） | `TestPkgConfigVersionSuffixResolve` |
| T6 | vendored 子模块（.gitmodules 声明，随项目编译）与外部包无区分：external_cmark_gfm 可解析包但 external_microtex/external_kcoreaddons 会产生误导性 need_port 幽灵 | project_scanner：external_target 未解析时先查 .gitmodules 折叠名（name/path 末段/url 末段），vendored 命中不建幽灵 | `TestExternalTargetLinks.test_graph_links_and_ghosts` |

### 2.2 harness 侧（run_e2e.py，证据/归因准确性，对账口径不变）

| # | 根因 | 修复 | 测试 |
|---|---|---|---|
| H1 | **取证 grep 逐行匹配**：tdesktop 的 target_link_libraries 每个链接项独占一行，逐行匹配漏掉全部多行语句证据（曾致 boost/glib/minizip/cmark-gfm 被误判 false-positive） | 强证据改全文 finditer + 行号回溯 | `test_grep_multiline_tll` |
| H2 | **`\b` 词界匹配不到下划线连写**：`external_xxhash`/`lib_zlib` 中 xxhash/zlib 前后是 `_`（word 字符），`\b` 不成立——上一轮曾因此把 zlib 误判误报（agent 笔记已记录） | 环视断言词界（字母数字外均算边界），并验证不误伤（zlib ⊄ zlibng） | `test_grep_boundary_matches_prefixed_target` |
| H3 | **幽灵节点一律报 resolution-gap（bug 候选）**：libudev（鸿蒙无 udev，HDF 驱动框架替代）、webrtc/ada/rnnoise 等真实外部依赖且库里确无对应包——幽灵是**正确检出**（fetch-deps 报 need_port 正确），不是 bug | 新增 `ghost_plausible_package()`：仅当库中存在形近已知包（别名命中 / 折叠名相等 / 子串且共享完整分隔分量，udev⊄uudeview）时报 resolution-gap，否则归 unknown-ok（该类已在 BY_DESIGN_CLASSES 预留，本轮首次启用） | `test_ghost_plausible_package` |
| H4 | **oracle 侧 vendored 无证据归类**：gsl/range-v3/hunspell 为 .gitmodules 子模块（Telegram/ThirdParty/GSL 等），归 README过时 语义失真 | `vendored_submodule_match()`：按 .gitmodules 证据归 vendored（by-design 新类） | `test_vendored_submodule_match` |
| H5 | 名字匹配分隔符差异：`crash_reports` vs `crash-reports` 不匹配 | pg_canon `_`→`-` 折叠；README_ALIASES 增 qr-code-generator→libqrcodegen | `test_names_match_underscore_folding` 等 |

**口径说明**（为何不算"改对账口径"）：recall/precision 计算公式、oracle 文件内容、BUG_CLASSES（missed-dep/resolution-gap/false-positive）定义均未改动。本轮新增的 vendored/unknown-ok 归类只作用于**差异归因**（差异为什么存在），不改变"oracle 运行时依赖 × portgraph 直接依赖"的比对本身；vendored 项仍留在 recall 分母（保守口径，不因归类改善而抬高 recall）。

---

## 3. 定性为工具问题的残留项（未修复，已文档化）

### 3.1 tdesktop breakpad / crashpad 漏检（missed-dep ×2，唯一残留 bug 候选）

- **取证**：主仓库仅 macOS/macstore 平台守卫段有引用（CMakeLists.txt:2349 `find_program(CRASHPAD_HANDLER crashpad_handler)`、:2381 `target_link_frameworks(Telegram PRIVATE Breakpad)`）；Linux 侧集成统一走 `desktop-app::external_crash_reports`（:97），其内部 breakpad/crashpad 二选一逻辑位于 **cmake/ 子模块（desktop-app/cmake_helpers）内部，浅克隆未初始化该子模块，扫描范围外**。
- **定性**：工具问题（未初始化子模块盲区），保留 missed-dep 分类 + overrides 人工备注，不掩盖。
- **可选后续方案**：clone 时 `--recurse-submodules`（代价：tg_owt/webrtc 等子模块体积巨大）；或按 .gitmodules 提示对缺失路径做降级标注（"该子模块内的声明不可见"）。已记入 `docs/deps-report.md` §已知限制。

### 3.2 musescore recall 50%→38%（非本轮代码回归，定性为工具覆盖范围问题）

- **取证**：上游 muse_deps 子模块重构——旧提交以 find_package/pkg_check_modules 暴露系统依赖（alsa/jack/sndfile/tinyxml 等，旧报告 23 个 pg 侧节点由此而来）；新提交（6525edb）改为自定义 `set(DEP_LIBS sndfile)` / `DEP_TARGET` DSL，通用扫描器不可见。
- **定性**：工具覆盖范围问题（每项目自定义包装约定，通用工具只能覆盖 PACKAGE/LIBRARY 关键字类约定）。bug 候选从 11 → 0（旧 10 个 resolution-gap 中 lilv-0/zix-0 已由 T5 修复，其余随上游重构消失；旧 1 个 false-positive 为 util-linux，已不再出现）。

### 3.3 tdesktop lzma-sdk / liblzma / opus 归 readme-stale（盲区同 3.1）

- **取证**：主仓库构建文件确无任何引用（grep 为空）；liblzma/opus 由 cmake_helpers 的外部预编译 Libraries 目录或 tg_owt（WebRTC 栈）带入，README 声明粒度与主仓库可见声明天然错位。
- **定性**：与 3.1 同族的子模块/外部目录盲区，readme-stale 是当前扫描范围内的事实描述（overrides notes 已注明原因），非误分类。

### 3.4 语料漂移提示（非工具问题）

tdesktop 与 musescore 的克隆 HEAD 均已前移（tdesktop 新增 fido2/WebAuthn 栈与 Python3 构建期 codegen；muse_deps 重构），oracle（reviewed）仍是旧 HEAD 语义。本轮全部差异已逐条人工复核归类；后续跑 e2e 前建议校对 oracle 与克隆 HEAD 的一致性。

---

## 4. 交付物清单

- 代码修复：`port_graph/qt_scanner.py`、`project_scanner.py`、`kb_seed.py`、`deps_report.py`
- harness 修复：`tests/e2e/run_e2e.py`
- 单测：`tests/test_port_graph.py` 44→56 全过（`python -m unittest tests.test_port_graph`）
- e2e 基线更新：`tests/e2e/reports/{tdesktop,keepassxc,musescore,qbittorrent}.report.{md,json}`（4 项目全重跑，--fresh-db）
- overrides 更新：`tests/e2e/overrides/tdesktop.json`（移除 5 条已原生化的重分类，保留 breakpad/crashpad 残留备注）
- 文档：`docs/deps-report.md`（external_* 导入目标解析说明 + 未初始化子模块盲区已知限制）
- 提交：`worker1-deps-test` 分支（本报告与代码同批提交）
=======
# TEST-REPORT — portgraph 依赖分析真实项目测试与优化（qbittorrent，tier B）

> 分支：`worker3-deps-test` | 基线：`f98a2e7`（44 单测全过）| 本轮提交：`d8f32c3`（53 单测全过）
> 日期：2026-09-19 | 工作区：`/root/harmony-workspace/worker3`（全新 workspace）
> 语料：`portgraph/tests/e2e/corpus.json#qbittorrent`（e2e tier B，README/INSTALL 有依赖段）

## 1. 执行摘要

用真实项目 **qBittorrent**（shallow clone 上游 master）跑 portgraph 依赖分析 e2e 对账，
首轮在基线代码上得到 **2 个 resolution-gap bug 候选**（`libtorrentrasterbar`、`systemd`
幽灵节点）。逐条用构建文件取证定位根因后修复 **3 个根因 + 1 个 harness 取证缺陷**，
每项补单测（44→53，全过）。**bug_candidates 2→0，recall/precision 保持 100%**，
未改任何 e2e 对账口径（oracle / 归类逻辑 / 指标公式零改动）。

## 2. 指标前后对比（qbittorrent e2e）

| 指标 | 基线 f98a2e7 | 修复后 d8f32c3 | 变化 |
|---|---|---|---|
| 检出召回率（README 运行时依赖） | 100%（5/5） | 100%（5/5） | 保持 |
| 检出精确率 | 100% | 100% | 保持 |
| **Bug 候选** | **2**（resolution-gap×2） | **0** | **-2** |
| 可移植性 unknowns | 3 | 1 | -2 |
| 依赖闭包总数 | 21 | 19 | -2 |
| need_port（需自行移植） | 3（libtorrentrasterbar / libtorrent-rasterbar / systemd） | 1（libtorrent-rasterbar） | -2（去重 + 可选依赖出闭包） |
| d1 幽灵节点 | 3 | 1 | -2 |
| verdict | blocked（4 阻塞：Cocoa/D-Bus/Win32 接口 + Qt D-Bus 模块） | blocked（同） | 保持（真实阻塞） |

语料回归（防止修复误伤其他项目）：

| 项目 | 结果 |
|---|---|
| keepassxc（B，已复核 oracle） | **无回归**：指标/闭包/直接依赖与已提交基线完全一致（diff 仅时间戳与 repo_path） |
| musescore（C，已复核 oracle） | 指标变化（recall 50%→25%）**全部来自上游构建系统迁移**（新克隆已重构为 muse_deps/FetchContent manifest，find_package 声明大幅减少）。A/B 验证：基线代码扫同一新克隆结果与修复后代码一致（qt_modules=3、直接依赖 4~5 个）；且新机制把 `pkg_check_modules(mnxdom)`（`option(MSS_USE_SYSTEM_MNXDOM ... OFF)` 守卫）正确判为 optional——在第二个真实项目上验证了选项守卫分析 |

## 3. 修复清单（根因 → 修复 → 证据 → 测试）

### 3.1 同库异名未归并 → libtorrentrasterbar 幽灵节点（resolution-gap #1）

- **取证**：`cmake/Modules/CheckPackages.cmake` L6 `find_package(LibtorrentRasterbar QUIET ...)`（CamelCase 压平名 → `libtorrentrasterbar`）与 L9 `pkg_check_modules(... "libtorrent-rasterbar>=...")`（连字符名）指同一库，扫描产生两个 `pkg-unknown` 幽灵节点、闭包重复计 need_port。
- **修复**：
  - `project_scanner._link_third_party`：按去分隔符键（`kb_seed._dashless_key`）分组归并，组内代表名 = 能解析到已知包的 > 带分隔符的（pkg-config/hb 命名口径）> 首个；`merged_from` 记录被归并名。
  - `kb_seed.build_dashless_index` / `resolve_package_dashless`：解析失败兜底——压平名匹配已知连字符包名（仅收 hb:/cmdpkgs: 源、键长 ≥6 防碰撞、**排除 pkg-unknown 幽灵**避免"上次扫描的幽灵被下次扫描当已知包"的自满足闭环，此问题在自测中发现并修复）。
  - 验证不误映射：cmd-pkgs 的 `libtorrent-rakshasa`（rTorrent 用异库）dashless 键不同，不会错配。
- **测试**：`TestDashlessSameLibMerge`（4 例：不可解析时合并为单幽灵、包库有包时兜底解析、仅压平名时 alias=dashless、短名/幽灵不入索引）。

### 3.2 systemd 误入 runtime 依赖（resolution-gap #2）

- **取证**：`dist/unix/CMakeLists.txt` L3 `find_package(Systemd)` 位于 `if (SYSTEMD)` 内；根 `CMakeLists.txt` L39 `feature_option_dependent(SYSTEMD ... OFF "NOT GUI" OFF)`——SYSTEMD 默认 OFF（GUI 默认 ON），且该 find_package 仅探测服务文件安装目录（不链接）。
- **修复**：
  - `qt_scanner` 新增 CMake 选项守卫分析：收集 `option` / `feature_option` / `feature_option_dependent` / `cmake_dependent_option` 默认值（跨文件合并）→ if 栈逐行追踪 → OFF 默认选项**正向**守卫（未被 NOT 修饰）内的 `find_package`/`pkg_check_modules` 标 optional；`Find<Name>.cmake` 模块文件继承 `find_package(Name)` 调用处守卫（模块仅在调用时执行）；`else`/`elseif` 分支与 function/macro 体内保守不判定；同一包必需声明点与可选声明点并存时按必需。
  - `project_scanner`：optional 名单连 **optional 边**（新边类型），不进入 runtime 闭包 / 可移植性分析 / fetch-deps / e2e 对账的 d1 口径（所有消费方按 `("runtime","uses-module")` 过滤，自动排除）；扫描摘要新增 `deps_optional`。
  - `deps_report`：optional 守卫条目 `required=false` + 注记"默认构建不含此依赖"。
- **测试**：`TestCmakeOptionGuard`（2 例：OFF/ON 默认值、if 守卫、Find 模块继承、macro 体内不判定、find_package_details 带 optional 标志）、`TestOptionalEdgeExcludedFromClosure`（optional 边语义：不入 analyze unknowns / 不入闭包 / 摘要区分）。

### 3.3 前置根因：dist 目录被排除，守卫上下文丢失

- **取证**：`qt_scanner.EXCLUDE_DIRS` 含 `dist`，导致 `dist/unix/CMakeLists.txt`（qBittorrent `add_subdirectory(dist)` 的真实构建子目录）不被扫描——首轮 systemd 的 if 守卫上下文完全不可见。
- **修复**：从 `EXCLUDE_DIRS` 移除 `dist`（C++/CMake 项目中 dist 多为源控打包/安装目录而非构建产物；JS 生态语义不适用于本工具域），注释记录依据。
- **测试**：`TestCmakeOptionGuard` fixture 即放在 `dist/unix/CMakeLists.txt`，同时覆盖该回归。

### 3.4 e2e harness 取证缺陷：@version 节点名 grep 不到（上轮遗留建议）

- **取证**：`name_variants` 对 `openssl@3` 不生成去 `@3` 变体，grep 不到 `find_package(OpenSSL)`（CheckPackages.cmake:47），会误判 false-positive（首轮已由 oracle 复核绕过，本轮补修）。
- **修复**：`tests/e2e/run_e2e.py name_variants` 对含 `@` 的节点名/节点 id 追加剥离变体（仅影响取证 grep，不影响对账归类口径）。
- **测试**：`TestE2ENameVariants`。

## 4. 残留项（不构成本轮 bug，已记录）

1. **libtorrent-rasterbar 不在 hb-core / cmd-pkgs**（数据源缺口，非解析缺陷）：保留单个 `pkg-unknown:libtorrent-rasterbar` 幽灵节点 / need_port=1 是**正确结论**（INSTALL 原文也警告勿装成 rakshasa 异库）。根治需向 Harmonybrew 提交 libtorrent-rasterbar formula（上游 https://github.com/arvidn/libtorrent）。
2. **libtorrent 版本约束无法静态解析**：`pkg_check_modules(... "libtorrent-rasterbar>=${version}")` 的 `${version}` 是 CMake 宏参（`macro(find_libtorrent version)`），`set()` 变量表无法代入 → deps 报告缺 `>= 2.0.10`。改进方向：宏参字面量调用点回填（`find_libtorrent(2.0)` 之类），收益低暂不做。
3. **musescore 语料漂移**：上游 master 已迁移构建系统（muse_deps/FetchContent manifest），旧 oracle（18 条）对新克隆 recall 只有 25%。需按新布局重建 oracle（本轮不动，避免误改对账口径；A/B 已证明非代码回归）。
4. **"matched 到幽灵节点"的 ⚠ 通用提示**保留：harness 无法区分"数据源真缺口"与"解析缺口"，人工复核说明已在 `tests/e2e/overrides/qbittorrent.json` notes 阐明（libtorrent-rasterbar 属前者）。
5. **optional 边的展示**：目前 API node detail 出边可见（type=optional），web 图谱/CLI summary 尚无专门分组展示（后续增强项）。
6. **dashless 兜底理论碰撞风险**：两个不同库去分隔符后同键会错配；已用"仅已知包源 + 键长 ≥6 + 键冲突 hb/ported 优先"收窄，未发现实际碰撞案例（qbittorrent/musescore/keepassxc 语料验证）。

## 5. 环境与复现

```bash
cd /root/harmony-workspace/worker3/portgraph
git clone --filter=blob:none --sparse https://atomgit.com/Harmonybrew/homebrew-core.git workspace/hb-core
(cd workspace/hb-core && git sparse-checkout set Formula)
python portgraph.py ingest all          # hb 4758 formula + cmd-pkgs 1248
python -m unittest discover -s tests    # 53 tests OK
python tests/e2e/run_e2e.py run --project qbittorrent --fresh-db
# → recall=100% precision=100% bug_candidates=0 closure=19 need_port=1
```

改动文件：`port_graph/qt_scanner.py`（选项守卫 + optional 标注 + dist 排除移除）、
`port_graph/project_scanner.py`（同库归并 + optional 边）、`port_graph/kb_seed.py`
（dashless 索引/解析）、`port_graph/deps_report.py`（optional 语义）、
`tests/e2e/run_e2e.py`（name_variants @ 剥离）、`tests/test_port_graph.py`（+9 测试）、
`tests/e2e/overrides/qbittorrent.json`（复核说明更新）、
`tests/e2e/reports/*.report.{md,json}`（qbittorrent 新基线 + keepassxc/musescore 重跑）、
`docs/deps-report.md`（语义文档）。
>>>>>>> worker3-deps-test
