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
