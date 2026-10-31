# portgraph 依赖分析：语料外泛化测试与性能验证报告

> 分支 `worker4-deps-test`（基线 f98a2e7，44 单测全过）
> 测试时间：2026-09-19 | 工作区：`portgraph/`
> 结论先行：**泛化测试在 3 个语料外真实项目上暴露 9 类问题，全部修复根因并补 12 个回归单测（44→56 全过）；gen-a deps 全流程 12.4s → 3.1s（4.0x）；e2e 基线语料回归无真实退化**。提交：`c04060a`（修复）、`d6a2877`（e2e 回归刷新）。

---

## 一、测试设置

### 数据源（ingest all）

| 源 | 规模 | 说明 |
|---|---|---|
| Harmonybrew hb-core | 4758 formula（全 ported），9395 依赖边 | 手动 sparse clone（`workspace/hb-core`，基线遗留问题：`ingest harmonybrew` 缺自动获取，仍残留） |
| cmd-pkgs | 1248 包 | 自动 clone |
| KB Qt 模块 | 63 | — |
| 合计 | **6069 节点 / 9395 边** | `python portgraph.py ingest all` |

### 语料外项目（e2e 语料 corpus-a/corpus-b/corpus-c/corpus-d 之外）

| 项目 | 构建系统 | 源文件 | 选择理由 |
|---|---|---|---|
| gen-f | cmake+qmake | 751 | 双构建系统；`src/libraries/` vendored 布局 + submodule 混合 |
| gen-e | cmake | 1185 | GStreamer/GLib/GIO 组件型依赖；CI 安装清单丰富 |
| gen-a | cmake+qmake | 22769（35MB 文本） | 自定义 CMake 宏（kis_add_library）；依赖变体名最多；性能压测样本 |

人工对照信源：各项目 CMakeLists/Find 模块原文、`.gitmodules`、CI workflow、README/INSTALL，以及 hb/cmd-pkgs 产物 tarball 内容抽查（`tar tzf` 核对 .pc/.so 归属，glib/gstreamer/openexr 实测）。

---

## 二、泛化结论：哪些问题跨项目复现

### 跨项目复现（≥2 个项目命中）

| # | 问题 | 复现项目 | 根因 | 修复 |
|---|------|---------|------|------|
| 1 | **hb formula 版本提取失败 → bottle 直链缺失** | 全局（419/4758 formula，boost/antlr/ant/aom/action-validator…，gen-e/gen-a 的 Boost 产物显示 `brew install boost`） | `_URL_VER_RE` 只认"版本后紧跟扩展名"，不认 `-bin`/`-b2-nodocs` 等后缀段、`.crate`、`V1.30` 大写前缀、`2.4j` 字母尾缀、版本独立路径段 | 扩展正则 + 路径段兜底；227 个恢复版本（0 回归），直链 HTTP 200 抽验通过 |
| 2 | **扫描期与报告期解析口径分裂** | gen-e（libsparsehash：fetch-deps 报 need_port 而 deps 报告有产物）、gen-a（gstreamer-1.0/fftw3 幽灵） | `project_scanner` 只做"精确名 + PKG_ALIASES"，不做 lib 前缀剥离/版本后缀剥离；`deps_report._resolve` 有完整阶梯 | 抽取共享 `kb_seed.resolve_pkg_name`（别名优先→原名→lib 前缀变体→版本后缀→构建形态后缀），两处共用 |
| 3 | **同库异名不归并 → 重复条目/重复下载** | gen-a（fftw 24 条、webp 7 条、lcms 7 条、jpeg 6 条）、gen-e（sqlite3+sqlite 双产物下载）、gen-f（botan-2/botan-3/Botan3 三条） | PKG_ALIASES 缺组件/变体名；别名不作用于去 lib 前缀后的候选；cmd-pkgs `sqlite3` 与 hb `sqlite` 跨源同名异库 | 别名表扩充（均经 tarball 内容实测：glib 组件、gstreamer 核心 3 模块、fftw 12 变体、webp/openjpeg/openexr/gsl/lcms2 家族等）+ 阶梯对候选展开别名 + 别名优先消除 sqlite3/sqlite 双产物 + find_package 名别名改写（KDcrawQt6→kdcraw）+ 幽灵节点用规范名 |
| 4 | **项目内目标被当外部依赖（need_port 误报）** | gen-a（gen-a* 45 个内部目标 + WIN32_DEBUG_POSTFIX/d 垃圾名）、gen-f（fakevim：`set(bin fakevim)` + `add_library(${bin})` 变量间接） | `_ADD_TARGET_RE` 不认宏包装（`macro(kis_add_library)` 内 `add_library(${ARGS})`）与 `${VAR}` 目标名；find_library 参数表里 CMake 变量名/单字符值被当库名 | 宏包装检测（body 含 add_library 的 macro/function 调用首参计为目标）+ `${VAR}` 经 set() 表解析 + find_library 过滤全大写下划线 token 与单字符 token |
| 5 | **CI 清单解析噪声** | gen-e（`apt install -y` 的 `-y` 被截断成包名 `y`） | token 正则首字符必须是字母数字，前导 `-` 被丢弃，`startswith("-")` 永不生效 | token 正则含前导 `-` 后统一过滤；skip 集合补 upgrade/dist-upgrade |
| 6 | **测试框架/编译器运行时库误报 need_port** | gen-f（gtest_main、gcov） | raw 链接名路径不查 TEST_FRAMEWORKS；atomic/gcov/intl 不在系统库清单 | 6b 段接 TEST_FRAMEWORKS → test 角色；OHOS_SYSTEM_LIBS 补 atomic/gcov/intl（键统一小写） |

### 单项目特有

| # | 问题 | 项目 | 根因 | 修复 |
|---|------|------|------|------|
| 7 | **vendored 源码目录被报 need_port** | gen-f（`src/libraries/` 布局：fakevim/botan/litehtml/gumbo 源码在仓库内却报"无产物→需源码编译"） | `_detect_vendored_dirs` 只认 3rdparty/external 等目录名与一层深度 | 新增 in-tree 判定：未解析名命中项目内源码目录（vendored 路径段 / 依赖集合父目录≥5 个库子目录 / README 特征三重门槛）→ kind=in-tree；**反例验证**：gen-a `libs/flake/text/lager`（项目自身代码）与 `3rdparty/lcms`（iccjpeg 胶水，无构建文件）不误收 |
| 8 | **扫描期为构建工具/平台接口建幽灵节点** | corpus-a/corpus-d/corpus-b（pkg-unknown:python3、:systemd 进 need_port） | 扫描期不知 BUILD_TOOL_FINDPKG/INTERFACE_BOUND_PACKAGES 分类 | `_link_third_party` 跳过两类名单（函数内 import 避免循环依赖） |
| 9 | **macOS 框架裸链接名/大小写匹配** | gen-a（Foundation/Security 经 find_library 报 package GAP；GLESv3 因 `.lower()` 与大小写键不匹配） | OHOS_SYSTEM_LIBS 键大小写不一致；INTERFACE_BOUND_PACKAGES 缺 Foundation/Security 等 | 键统一小写；补 foundation/security/coreservices/corefoundation |

### 判为"正确行为"经人工核实（不修）

- gen-a gstreamer-app/audio/pbutils/tag `need_port`：cmd-pkgs gstreamer tarball 实测只含 base/controller/net/check，plugins-base 组件确无鸿蒙产物——**特意不加别名**，need_port 定性正确。
- gen-e getopt（if(WIN32) 块内）/Sparkle（if(APPLE)）：无结构化平台块解析是已知限制（worker2 遗留 #2 同源），条目可读、不误导 agent 决策。
- Mlt7/qca2/Poppler/PyQt5/6/KSeExpr/Lager/Immer/Zug/libunibreak/QUAZIP（gen-a）、libchromaprint/libgpod/libpulse/KDSingleApplication-qt（gen-e）、botan（corpus-c，e2e 已复核）：hb/cmd-pkgs 确无对应包，need_port 正确。

---

## 三、修复清单与验证

| 修复 | 文件 | 验证 |
|------|------|------|
| URL 版本提取 | `port_graph/harmonybrew.py` | 11 个 URL 形态单测；重 ingest 全库 diff：227 gained / 0 lost / 0 changed；boost-1.92.0_1 / antlr-4.13.2_1 / action-validator-0.9.0 直链 HTTP 200 |
| 宏包装+变量目标识别 | `port_graph/qt_scanner.py` | gen-a 内部目标 45→0；fakevim 排除；单测 2 个 |
| find_library 垃圾 token | 同上 | WIN32_DEBUG_POSTFIX/d 消失，quazip 保留；单测 |
| env -y | 同上 | gen-e env 清单 `y` 消失；单测 |
| 共享解析阶梯 | `port_graph/kb_seed.py`（新增 `resolve_pkg_name`）、`deps_report.py`、`project_scanner.py` | libfftw3f_omp→fftw、gio-2.0→glib、jpeg-static→jpeg-turbo 等单测；gen-a link 177→65 |
| PKG_ALIASES 扩充 | `port_graph/kb_seed.py` | 全部经 tarball/bottle 内容实测（glib/gstreamer/openexr tar 抽查） |
| in-tree 判定 | `port_graph/deps_report.py` | gen-f 6 项转 in-tree；gen-a lager/lcms 反例不误收；单测 2 个 |
| test/system-lib/platform-iface 分类 | 同上 | gtest_main→test；atomic/gcov/intl→system-lib；Foundation/Security→platform-iface；单测 |
| 扫描期跳过构建工具/接口名 | `port_graph/project_scanner.py` | corpus-a python3、corpus-d/corpus-b systemd 幽灵消除 |
| 文档 | `docs/deps-report.md` | 解析阶梯与性能口径描述更新 |

**单测：44 → 56，全过**（`python tests/test_port_graph.py`，新增 `TestGeneralizationFixes` 12 个用例）。

### 修复效果（人工对照前后）

| 项目 | link 条目 | fetch-deps 闭包 | need_port |
|------|----------|----------------|-----------|
| gen-f | 17（含 8 条误报）→ **16**（in-tree 6 / test 1 / system-lib 2 归位） | 28 → **47**（真实依赖如 aspell/hunspell 产物随解析补全进入闭包） | 6 → **4**（botan 家族合一） |
| gen-e | 40 → **36**（gio/gobject/gio-unix 并入 glib，fftw3→fftw 有产物，gstreamer-base 并入 gstreamer） | 52 → **55** | 21 → **11** |
| gen-a | **177 → 65（-63%）**（45 个内部目标 + 24 个 fftw 变体 + webp/lcms/jpeg 家族归并） | 143 → **112** | 38 → **16**（余 16 中 14 为真缺口） |

版本校验结论抽查：gen-e TagLib `>= 2.0`（find_package）与 `>= 1.12`（多源合并）对 hb 2.3.2 = satisfied ✓；sqlite `>= 3.9` 经别名归并标 unknown + 量纲警告（库主版本 vs 包版本口径）✓ 符合设计。

---

## 四、性能基准

### deps 全流程（scan + 入库 + 报告，含 `--json`）

| 项目 | 基线 | 修复后 | 加速 |
|------|------|--------|------|
| gen-a（最大闭包，35MB 源码） | **12.4s** | **3.05s** | **4.1x** |
| gen-e | 1.7s | 0.63s | 2.7x |
| gen-f | 2.6s | 0.81s | 3.2x |

### fetch-deps 闭包（--dry-run）

gen-a 112 项闭包 **0.06s**、gen-e 55 项 0.05s、gen-f 47 项 0.05s——闭包 BFS 非瓶颈。

### _GraphCache 缓存效果确认（gen-a 实测）

- node 查询 384 次调用 / 64 次未命中 → **命中率 83%**；out_edges 261 / 93 未命中；
- `analyze_dependencies` 阶段仅 **0.13s**（禁用缓存对照 0.129s，输出一致）——**缓存有效但 analyze 已非瓶颈**（gen-a 各 link 闭包重叠度低；worker2 合成压测的 11.6x 场景是高重复深链，缓存对该场景仍关键）。

### 剩余热点（3.05s 的构成，cProfile）

1. `_detect_platform_interfaces` ≈1.9s：字面量锚点 `any(a in text …)` 扫描自身（win32 规则 29 个锚点）+ 6293 个文件读取。后续可做：锚点合并为单遍扫描、或按首字符分桶。
2. `qt_scanner.scan_project` ≈1.7s：third_party(0.39s)/wrapper_deps(0.34s)/dynamic_loads 各自独立读全部源文件（29064 次 read_text）——**共享读缓存**可再省约 1/3 IO。
3. DB 写入与 pathlib 开销 ≈0.3s。

### 性能修复明细

- `_detect_platform_interfaces` 10.7s → 1.9s：① 无接口规则命中的文件跳过逐行宏栈追踪（`_macro_stack_status` 调用 6293→23 次）；② 12 条平台规则加字面量锚点前置过滤——每条正则分支均含必要子串，无锚点必无匹配，**语义不变（gen-a 全量对照 54 命中，0 漏检）**。
- `_detect_dynamic_loads` 1.4s → 0.1s：dlopen/QLibrary/QPluginLoader 子串预过滤。

---

## 五、e2e 基线语料回归（4 项目，修复后重跑）

| 项目 | recall | precision | bug 候选 | 变化归因 |
|------|--------|-----------|----------|----------|
| corpus-a | 24% | 100%→80% | 7→**8** | python3 幽灵消除（-1）；libfido2 为上游新增 webauthn submodule（readme-omitted，portgraph 正确检出，README 未更新）；libudev 确无鸿蒙包（need_port 正确）；missed-dep 7 条为基线已知（缺子模块的 desktop-app::external_* 目标） |
| corpus-b | 50%→25% | 46%→**100%** | 11→**1** | **10 个 resolution-gap 幽灵全部解析**（alsa/sndfile/tinyxml/brotlidec/dbus1/glib2/iconv/intl/ogg/png → 真实包）；recall 下降系**上游重构**：fresh clone 中 `src/framework/` 内嵌 freetype/fluidsynth 三方树已删除（语料漂移，非回归），oracle 旧依赖转 readme-stale |
| corpus-c | 100% | 23%→25% | **0** | 指标稳定；precision 提升来自多余幽灵消除 |
| corpus-d | 80% | 100% | 1→**2** | systemd 幽灵消除；LibtorrentRasterbar 幽灵名规范化后 harness 归类变化——libtorrent 确无鸿蒙包，need_port 定性不变（残留说明见下） |

**结论：无真实准确率退化；所有指标变化均可归因于（a）幽灵消除（b）上游语料漂移。**

---

## 六、残留项（未修，供后续处理）

1. **hb-core 数据源缺自动获取**（基线遗留）：`ingest harmonybrew` 在 `workspace/hb-core` 缺失时静默返回 `files: 0`。建议仿照 cmdpkgs 的自动 sparse clone（本次为手动建立，4758 formula 已就位）。
2. **find_library 的 debug 后缀变体**（cblasd/gsld/gslcblasd/vpxmd，gen-a 4 条）：`-d` 后缀剥离会误伤真库名（如 `libd`），未做通用规则。
3. **结构化平台块解析缺失**（if(WIN32)/if(APPLE) 内的 find_package/getopt/Sparkle）——名称级分类已覆盖主要场景，块级判定需 CMake 语义分析，收益/成本比待评估（worker2 遗留 #2 同源）。
4. **qt_scanner 各检测器重复读文件**（29064 次 read_text）：共享读缓存预计再省 ~1s，涉及多函数签名调整，本次未动。
5. **e2e harness 的 LibtorrentRasterbar 幽灵名匹配**：幽灵名规范化（libtorrent-rasterbar vs libtorrentrasterbar）后 harness 同时报 missed-dep + resolution-gap，建议 harness 侧对 pkg-unknown 名做归一化匹配。
6. **内嵌三方代码的 include 污染**（corpus-a util-linux/openssl，基线已知）：vendored 目录内的 #include 启发式把宿主库计入应用 depth-1，可结合本次 in-tree 索引把 vendored 路径下的 include 排除——留待后续。
7. corpus-b e2e oracle 需按新上游结构（src/framework 删除）重新复核定稿。

---

## 七、复现命令

```bash
cd portgraph
python portgraph.py ingest all                     # hb-core 需先手动 sparse clone（见残留 #1）
python tests/test_port_graph.py                    # 56 tests OK
python portgraph.py deps workspace/<gen-f|gen-e|gen-a> --json
python portgraph.py fetch-deps <app> --dry-run
python tests/e2e/run_e2e.py run --all              # 语料回归
# 性能
/usr/bin/time -f "%es" python portgraph.py deps workspace/gen-a --json > /dev/null
```
