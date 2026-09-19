# TEST-REPORT：portgraph 依赖分析 × 真实项目 musescore（e2e 语料 tier C）

> 日期：2026-09-19 ｜ 分支：`worker2-deps-test`（基线 f98a2e7 → 本次 4 个提交）
> 语料：`portgraph/tests/e2e/corpus.json#musescore`，克隆 master **2b540fe**（2026-09-18）
> 工具代码：`portgraph/port_graph/`（qt_scanner / project_scanner / deps_report / deps_fetch / kb_seed / cloner）
> 单测：**54/54 通过**（基线 44 + 新增 10）；e2e 对账口径（差异归类类与指标定义）未改动。

---

## 0. 重要背景：上游依赖模型变更

MuseScore master 已从「CI setup.sh apt 清单 + `MUE_COMPILE_USE_SYSTEM_*` 系统库开关」（4.x 时代，
旧 oracle 即按此整理）迁移到 **muse_deps 自定义依赖引擎**：

- 依赖清单声明：`require_dep(<name> [STATIC|SYSTEM|REBUILD])` / `require_source_dep(<name>)`
  （源码自带）/ `require_tool(<name>)`（主机构建工具），位于
  `buildscripts/cmake/DependencyManifest.cmake`（应用）与 `muse/buildscripts/cmake/ExtDepsManifest.cmake`
  （muse 框架 submodule），由 `muse_deps` submodule（recipes + prebuilt.lock）解析；
- Qt 组件：`set(qt_components ...)` + `list(APPEND ...)` + `find_package(Qt6 6.8 REQUIRED
  COMPONENTS ${qt_components})`（变量形式）；
- 旧 oracle 的 pulseaudio / openssl / tinyxml / ffmpeg 在 master 已不存在。

因此本轮除修复 portgraph 外，按 e2e 设计流程（oracle 由 agent 复核修正）**重写了
`tests/e2e/oracle/musescore.json`**（依仓库内清单文件 + `MuseDeclareOptions.cmake` 默认值定
可选性）。为诚实呈现「代码修复」本身的贡献，指标对比同时给出
**旧代码 × 新 oracle** 的实测（checkout f98a2e7 代码重跑）。

另注意：首次 e2e 运行发生在 submodule 未初始化状态（muse/、muse_deps/ 为空目录），扫描结果
严重失真（deps_linked=1）。已修复 cloner 自动初始化 submodule（见 §2.7），保证可复现。

---

## 1. 指标前后对比

### 1.1 主对比（同一 oracle：本轮重写的新 oracle）

| 指标 | 修复前代码（f98a2e7）× 新 oracle | 修复后（HEAD） | 变化 |
|---|---|---|---|
| 检出召回率（oracle 运行时依赖） | **38%**（6/16） | **100%**（16/16） | +62pp |
| 检出精确率 | **53%** | **100%** | +47pp |
| Bug 候选总数 | **22**（missed-dep 4 / resolution-gap 17 / false-positive 1） | **0** | −22 |
| depth-1 幽灵节点（pkg-unknown） | 24 | 5（均确无 bottle） | −19 |
| vendored 依赖正确分流 | 0（全部混入 need_port） | 10（status/role=vendored） | — |
| fetch-deps 闭包 need_port | 22 | 5 | −17 |
| 闭包总览 | 41 项（would_download 10，无 vendored 分类） | 84 项（would_download 49 / vendored 10 / cmd_only 3 / provided 16） | hb-core 数据源补齐后传递闭包更完整 |

### 1.2 参照：会话起点状态（旧代码 × 旧 oracle，即上一轮基线报告）

recall 50% / precision 36% / bug 候选 10（全部 resolution-gap，agent 复核为 10 个别名缺口 +
13 个 unknown-ok）。该组数字依赖已过时的 oracle，仅作历史参照；其中暴露的结构性问题
（内嵌 thirdparty 污染、注释行误匹配、.cmake 扫描缺失）本轮全部定位到根因并修复。

### 1.3 残留的 bug 候选 = 0 的真实性说明

5 个幽灵节点（mnxdom / msdfgen / opusenc / pipewire / json_schema_validator）均经逐一核对
hb-core（4758 formula，本轮 ingest 补齐）与 cmd-pkgs（1248 包）确认**确无 bottle**，portgraph
标 need_port / unknown 是正确结论，非解析缺口——已写入 `overrides/musescore.json` 的 agent
终判。matched 项中 14 个解析到真实 bottle（alsa-lib、libogg、libvorbis、libsndfile、
nlohmann-json、flac、opus、lame、fdk-aac、freetype、harfbuzz、libpng、zlib、jack）。

---

## 2. 修复清单（逐项根因 → 修复 → 单测）

| # | 根因（构建文件取证） | 修复 | 单测 |
|---|---|---|---|
| 1 | **`build*` 前缀误排除**（最大漏检源）：`_walk` 把 `buildscripts/`、`buildtools/` 当构建输出目录排除，muse 的 `ExtDepsManifest.cmake` / `DependencyManifest.cmake` / `SetupQt6.cmake` / `FindJack.cmake` 整树未扫描 | 改为 `_BUILD_DIR_RE`（`build` / `build-Debug` / `build123` 等输出目录形态），`buildscripts` / `buildtools` 正常扫描 | `TestBuildscriptsDirNotExcluded` |
| 2 | **vendored / 依赖引擎目录污染**（误报主源）：`muse/framework/audio/thirdparty/fluidsynth/fluidsynth-2.3.3/CMakeLists.txt`、`.../dockwindow/thirdparty/KDDockWidgets/python/CMakeLists.txt`、`muse_deps/recipes/lv2sdk/meta.cmake` 里内嵌三方/引擎自己的 `find_package`/`pkg_check_modules`（glib2/dbus1/lash/midishare/oboe/openmp/opensles/pulseaudio/pyside/python3/shiboken/portaudio/readline/SDL2/curl/lv2/lilv-0/suil-0/zix-0…）被算作应用 depth-1 依赖 | 新增 `_is_vendored_path()`（`thirdparty`/`3rdparty`/`third_party`/`vendor`/`external`/`extern`/`deps`/`dependencies`/`subprojects` 段 + `*_deps` 后缀），find_package / pkg_check / find_package_details / raw_links / fetched_deps / wrapper / include 提示 全部过滤；函数定义收集不过滤（引擎在 vendored 路径内定义 require_dep） | `TestVendoredCmakeSkip` |
| 3 | **CMake 注释行误匹配**：`fluidsynth-2.3.3/CMakeLists.txt:851` 的 `# Exported targets for cmake: find_package(FluidSynth)` 产出 `pkg-unknown:fluidsynth` | `_detect_cmake_packages` / `_detect_find_package_details` / `_detect_cmake_raw_links` / `_detect_fetched_deps` 匹配前统一 `_strip_cmake_comments` | 同上 |
| 4 | **require_dep 依赖清单函数完全未识别**（漏检主源）：muse_deps 引擎的 `require_dep`/`require_source_dep`/`require_tool` 调用（ogg/vorbis/flac/opus/libsndfile/zlib/freetype/harfbuzz/libpng/fdk-aac/lame/opusenc/pipewire/msdfgen/nlohmann_json/json_schema_validator + 10 个源码自带依赖）全部漏检 | 新增 `_detect_manifest_deps()`：函数名匹配 `require*dep/tool/package` 且在扫描 CMake 中有 `function/macro` 定义；首参为依赖名，mode 分 link/source/tool；轻量 if/endif 栈标注 conditional（不求值）。图侧：link → runtime 边，source → **vendored 边**（fetch-deps status/role=vendored，不下载不下钻），tool 不连边；deps 报告并入 link/vendored/工具链三段 | `TestRequireDepManifest`（3 个）、`TestFetchVendoredRole` |
| 5 | **Qt 组件列表变量不展开**：`find_package(Qt6 6.8 REQUIRED COMPONENTS ${qt_components})` 组件为 0，qt_modules 仅 7 个（靠 include 启发式）；且 `_walk` 的 LIFO 顺序使 `sandbox/web_sandbox` 的同名 `set(qt_components ...)` 遮蔽主声明 | `_collect_list_vars()`：`set()`（跨行）/ `list(APPEND)` 累积，纯标识符 token；**跨文件并集**（与遍历顺序无关）；`_detect_qt` 对 Qt find_package 参数做 `${var}` 替换。qt_modules 7→19（补 network/svg/xml/quickwidgets/shadertools/concurrent 等） | `TestQtComponentsListVar` |
| 6 | **别名缺口**（上一轮已定位、本轮入库）：alsa→alsa-lib、sndfile→libsndfile、tinyxml→tinyxml2、glib2→glib、dbus1→dbus、ogg→libogg、vorbis→libvorbis、png→libpng、brotlidec→brotli、intl→gettext、utfcpp→utf8cpp、nlohmann_json→nlohmann-json（目标包在 hb-core/cmd-pkgs 均验证存在）；另 `find_package(Git/OpenMP/iconv/dl 等)` 按构建工具/CMake 内置模块跳过（与 deps_report BUILD_TOOL_FINDPKG / CMAKE_BUILTIN_PACKAGES 对齐） | `PKG_ALIASES` + `kb_seed.ALIASES` 补条目；`_FINDPKG_SKIP` 扩充 | `TestMusescoreAliasResolution` |
| 7 | **e2e 不可复现**：`git clone --depth 1` 不初始化 submodule，muse_deps/muse 为空 → 依赖清单全部不可见 | `cloner.clone_repo` 克隆/复用时浅层初始化 submodule（`--depth 1 --recursive`，失败静默降级） | `TestClonerSubmodules`（2 个） |
| 8 | **e2e 匹配器分隔符不对称**：oracle 侧 `norm_name` 把 `_` 归一为 `-`，`pg_canon` 不做 → `json_schema_validator`（require_dep 下划线名）永远匹配不上 | `pg_canon` 应用相同分隔符归一（匹配对称性修复；归类类与指标定义未动） | e2e 实测（该用例由本轮语料覆盖，harness 无单测框架） |

附带：`ingest all` 补齐 hb-core 数据源（workspace/hb-core sparse clone，4758 formula 入库），
此前主库 hb 节点为 0（旧报告中的 hb 证据全部来自上一轮环境）。

---

## 3. 残留项（未在本轮修复，已记录）

1. **require_dep 条件块不求值**：msdfgen（`NOT MUSE_MODULE_DRAW_USE_QTTEXTDRAW`，默认不启用）、
   pipewire（`MUSE_MODULE_AUDIO_PIPEWIRE` 默认 OFF）、asiosdk（Windows）等默认关闭的声明仍进
   闭包 → fetch-deps 概览偏保守（deps 报告已标注 conditional + required=False）。可评估沿
   `MuseDeclareOptions.cmake` 的 `option(... ON/OFF)` 默认值求值常见条件。
2. **deps 报告 raw_libs 噪音**：muse 用 `declare_module` 等自定义函数创建 target
   （engraving/global/muse_audio_* 等），`add_library` 扫描不可见 → 内部 target 名进入 link 列表，
   个别与 hb 包名巧合解析（如 `global` → hb:global）。可扩展 target 定义识别
   （`function` 包装的 `add_library`/自定义 declare 函数）。
3. **need_port 幽灵节点无源码链接**（`source_url: ?`）：pkg-unknown 节点不带 repo 信息；
   可从 muse_deps `recipes/*/spec.cmake` 的源码 pin 补充（引擎特定，通用性待议）。
4. **`muse` submodule 在 deps 报告 vendored 段误列**：`_detect_gitmodules` 把所有 submodule 列为
   vendored，但 muse 是应用框架本体（非三方库）。语义边界待定（不影响 e2e 对账）。
5. **其它语料项目报告未重跑**：tdesktop/keepassxc/qbittorrent 的 e2e 报告仍是旧扫描器产物；
   本轮修复（尤其 vendored 跳过、buildscripts 扫描、注释剥离）预期会改变其 depth-1 清单
   （tdesktop 的 `ThirdParty/` 目录同样会被正确跳过），建议后续 `run --all` 刷新基线。
6. **iconv 别名决策**：上一轮建议 iconv→libiconv，但 deps_report 语义中 iconv 为 musl libc
   内置（CMAKE_BUILTIN_PACKAGES system-lib），本轮按工具自身语义跳过而非别名，未采纳该建议。

---

## 4. 提交记录

| commit | 内容 |
|---|---|
| `fix(deps): musescore e2e 复核驱动的 6 项扫描/解析根因修复` | qt_scanner/project_scanner/deps_report/deps_fetch/kb_seed + 8 个单测 + 文档 |
| `test(e2e): musescore 对账基线更新（master 2b540fe）+ cloner submodule 初始化` | oracle/overrides 重写、cloner、corpus、pg_canon、2 个单测、基线报告 |
| `test(e2e): musescore 报告基线（最终，含时间戳）` | 前后对照实验后的最终报告 |

最终验证：`python -m unittest tests.test_port_graph` → **54/54 OK**；
`python tests/e2e/run_e2e.py run --project musescore --fresh-db` →
recall=100% / precision=100% / bug_candidates=0（报告见
`portgraph/tests/e2e/reports/musescore.report.md`）。
