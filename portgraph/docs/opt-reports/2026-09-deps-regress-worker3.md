# REGRESS-REPORT — portgraph 依赖分析回归 + 泛化测试

> 分支：`worker3-deps-regress` | 基线：`416ef8d`（含全部集成修复，87 单测全过）
> 日期：2026-09-19 | 工作区：`~/harmony-workspace/worker3`
> 阶段 1 语料：corpus-d + corpus-c（e2e corpus tier B，回归）
> 阶段 2 泛化：**gen-b**（KDE/Qt 文档查看器，master 8662e426，500 源文件）
> + **gen-c**（KDE/Qt 终端，master a6ef17f7，382 源文件）——
> 避开 e2e 语料四项目（corpus-a/corpus-b/corpus-c/corpus-d）与他人选择
> （gen-a/gen-e/gen-f）

## 1. 执行摘要

- **阶段 1 回归：一次分析正确性 100% 通过**。fresh DB → scan → deps --json →
  fetch-deps --dry-run 全流程在基线代码上**零人工修饰**跑出与
  `tests/e2e/reports/` 基线逐项一致的结果（闭包构成、would_download 名单、
  d1 清单、need_port 定性、analyze verdict 全部精确一致；e2e harness 重生成
  报告与提交基线**字节级一致**，diff 仅时间戳与 workspace 路径）。
- **阶段 2 泛化：gen-b + gen-c 暴露 9 类问题**（6 工具 bug + 2 数据源
  别名缺口 + 1 启发式限制），**全部修复根因**并补 14 个回归单测
  （87 → 101 全过）；阶段 1 在回归中发现 3 类报告级缺陷（与基线口径无关，
  e2e 对账不经过 deps --json）亦一并修复。
- 语料回归：corpus-d / corpus-c / corpus-b 基线字节级不变；corpus-a
  precision 60%→64%（平台块修复移除 APPLE-only 假边 libiconv，**预期改善**，
  基线随本轮更新）。性能与上轮可比数字同量级，无回归。

## 2. 阶段 1：回归（corpus-d + corpus-c @ 416ef8d）

### 2.1 方法

每项目独立 fresh DB（`rm portgraph.db && ingest all --offline`：hb 4758
formula + cmd-pkgs 1248，gate PASS）→ `scan` → `deps --json` →
`fetch-deps --dry-run` → `analyze`，与 `tests/e2e/reports/*.report.{md,json}`
基线逐项核对；另跑 e2e harness（`run --project X --fresh-db --no-clone`）
重生成报告与提交基线 diff。全部命令用 `/usr/bin/time` 计时。

### 2.2 一次分析正确性核对（全部通过，零人工修饰）

| 核对项 | corpus-d | corpus-c |
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

| 步骤 | corpus-d（710 源文件） | corpus-c（884 源文件） |
|---|---|---|
| ingest all --offline | 2.04s / 1.17s（第二次） | 1.17s |
| scan | 0.63s | 0.64s |
| deps --json | 0.57s | 0.72s |
| fetch-deps --dry-run | 0.05s | 0.06s |
| analyze | 0.07s | 0.06s |
| e2e harness 全流程 | 0.57s | 0.72s |

**与上轮对比**：归档报告（`portgraph/docs/opt-reports/`）未记录
corpus-d/corpus-c 的 deps 计时；最接近的可比数字为 worker4 泛化轮的
gen-f 0.81s（规模相当）→ corpus-c 0.72s 同量级，**无性能回归**。
本轮全部修复后复测：corpus-d deps 0.57s、corpus-c 0.73s（持平）。

### 2.4 回归中发现的报告级缺陷（不影响 e2e 对账口径，随本轮修复）

基线的对账口径是 DB 节点/闭包，`deps --json` 的 link 表存在 3 类与项目
事实不符的表现（详见 §4 修复 F3/F4/F5）：

- corpus-d `Systemd` 条目 required=True + "直连平台栈" 警告（实际位于
  SYSTEMD 默认 OFF 选项守卫内）；
- corpus-d `LibtorrentRasterbar` + `libtorrent-rasterbar` 双条目、双
  "需源码交叉编译" 警告（DB 侧已归并，报告侧未归并）；
- corpus-c `qrencoded`（FindQREncode.cmake 的 WIN32 AND NOT MINGW 块内
  Windows debug 变体名）、`network`（if(HAIKU) 块）误报 required=True。

## 3. 阶段 2：GitHub 热门 Qt 项目泛化（gen-b + gen-c）

**选择声明**：gen-b（~2.6k star，KDE 旗舰文档查看器，CMake/ECM/KF6，
poppler 等多媒体格式依赖面广）+ gen-c（KDE 默认终端，CMake/KF6）。
shallow clone 到 `portgraph/workspace/`，跑 `deps --json` +
`fetch-deps --dry-run`，逐项人工对照 `CMakeLists.txt`、`cmake/modules/Find*.cmake`
与 README/BUILD.md。

### 3.1 gen-b（before → after 修复）

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
Android 专属 NSS 链接被正确识别为平台块。gen-b README 无依赖段（构建文件
为唯一真源），无漏检。**hb:markdown 错配曾把 daringfireball 的 Perl/PHP
Markdown 1.0.1 bottle 拉进闭包**（gen-b 链接的 libmarkdown 实为 discount
的库名）——修复后消除。

### 3.2 gen-c（before → after 修复）

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
- **need_port 定性**：gen-b 30 项、gen-c 26 项 need_port 全部经
  hb-core/cmd-pkgs 核实确无对应包（大头是 KF6 全家——需源码交叉编译，
  定性正确；根治需向 Harmonybrew 提 KF formula，属数据源缺口）。

## 4. 问题清单与定性（全部修复 + 补测试）

| # | 问题 | 实证 | 定性 | 修复 |
|---|---|---|---|---|
| F1 | find_package **引号版本**未解析 | gen-b `Poppler "24.08.0"`、`DjVuLibre "3.5.28"`、`QMobipocket6 "2"` | 工具 bug | `qt_scanner._parse_findpkg_args` 去 token 引号 |
| F2 | **无 COMPONENTS 关键字的尾随组件**漏检；组件名与关键字同形（Config↔CONFIG）被吞 | gen-c Qt6/KF6 主声明（4 个 Qt 模块 + 3 个 KF 组件漏检） | 工具 bug（CMake 合法语法未覆盖） | `_orphan_components` 区域状态机（版本/关键字后的裸名即组件；组件区开始后不再按关键字解释）+ KF/Qt 检测器接入 + `_parse_findpkg_args` 同口径 |
| F3 | INTERFACE_BOUND（platform-iface）条目忽略 optional 守卫 | corpus-d systemd（SYSTEMD 默认 OFF）required=True + 误警 | 工具 bug | `deps_report` §1/§2 平台接口分支透传 optional |
| F4 | deps link 表**同库去分隔符重复** | corpus-d LibtorrentRasterbar×libtorrent-rasterbar 双警告 | 工具 bug（扫描期已归并、报告期未对齐） | `deps_report` §7b 去分隔符合并键（单词名 + 键长 ≥6，KF 节点名含空格不参与） |
| F5 | **平台块上下文缺失**：if(APPLE)/if(WIN32)/if(HAIKU)/if(ANDROID)/STREQUAL "Darwin"/"Windows" 等块内的 tll/-l/find_library/pkg_check_modules 误报必需、误入闭包 | corpus-d AppKit/Carbon/IOKit/objc（Darwin）、iphlpapi（Windows）；gen-c util（FreeBSD）、network（Haiku）；gen-b nss/softokn3/freebl3/nssckbi（ANDROID）；corpus-c qrencoded（WIN32 AND NOT MINGW）；corpus-a external_iconv（APPLE） | 工具 bug（worker1 轮已记录的建议，本轮实现） | `qt_scanner._cmake_platform_line_map`（与选项守卫行映射同构；UNIX/LINUX/POSIX 视为 OHOS 活跃不降级；NOT X 否定条件不降级；elseif 按自身条件评估、else 保守）→ raw_libs/pkg 检测标注 `platform_block` → deps_report required=False+注记、project_scanner 不连边 |
| F6 | **KF 组件走包名解析阶梯**：KF Archive≠libarchive、KF Config≠libconfig | gen-b/gen-c（报告展示 ready bottle 与闭包 need_port 矛盾） | 工具 bug | `deps_report` §7 framework 条目解析到 `kf:<comp>` 节点 |
| F7 | **in-tree 误判功能分组目录**：`generators/` 父目录 ≥5 子目录集合启发式把格式生成器插件目录当自带库 | gen-b generators/poppler、generators/epub（掩盖真实 need_port） | 工具启发式限制（KDE generators 布局触发） | `_in_tree_dir_index` 依赖集合父目录白名单（libraries/libs）；README 仅作容器内佐证。gen-f fakevim/litehtml 复测无回归 |
| F8 | **ddjvuapi 别名缺口**：djvulibre 的 pkg-config 名与 find_package 名双幽灵、双 need_port | gen-b（FindDjVuLibre.cmake 用 pkg_check_modules(ddjvuapi) 探测同库） | 数据源缺口（别名知识） | `kb_seed.PKG_ALIASES["ddjvuapi"]="djvulibre"` + `_link_third_party` 分组键别名规范化 |
| F9 | **libmarkdown 同名异义**：discount 的库名解析到 hb:markdown（daringfireball 的 Perl/PHP 版），错瓶入闭包 | gen-b（FindDiscount.cmake `pkg_check_modules(Discount "libmarkdown")`） | 数据源缺口（别名知识，同名异义风险的实例） | `PKG_ALIASES["libmarkdown"]="discount"` |

## 5. 语料回归验证（修复后全量）

| 项目 | 结果 |
|---|---|
| corpus-d / corpus-c | e2e 报告与基线**字节级一致**（仅时间戳/路径）；closure/指标不变 |
| corpus-b | 同上（注意：workspace 克隆需 `git submodule update --init`，未初始化时源文件 3139 vs 5729、结果与基线不可比——本轮实证，运营注意项） |
| corpus-a（master 4d4da47，补克隆验证） | precision 60%→64%、closure 61→60：**APPLE 块内 `desktop-app::external_iconv` 假边（libiconv）被 F5 正确移除**，属预期改善，基线已随本轮重新生成；recall 53% / 2 个 missed-dep 为基线既有状态（上游 README 漂移，见 worker1 报告残留项），非本轮引入 |
| gen-f（抽查） | fakevim/litehtml 仍正确 in-tree（F7 收紧无回归） |
| 单元测试 | **101/101 全过**（87 → +14：引号版本/无关键字组件/Config 同形/平台块×3/optional 平台接口/报告去分隔符合并/KF 解析/in-tree×2/别名×2） |

## 6. 残留项（本轮不修，已记录）

1. **keyutils（corpus-c）**：位于 `if("${CMAKE_SYSTEM}" MATCHES "Linux")`
   块——LINUX 按 OHOS 活跃处理不降级（保守必需）。定性合理：OHOS musl 无
   keyutils.h，移植确需关注；工具无法静态判定 OHOS 工具链下 CMAKE_SYSTEM
   的取值。
2. **corpus-a 2 个 missed-dep**：基线既有（上游 README 与构建文件漂移），
   见 `docs/opt-reports/2026-09-deps-test-worker1.md` 残留项。
3. **Discount 合并后 required=True**：pkg_check_modules（必需语义）与
   find_package（无 REQUIRED）同库合并按必需（保守方向，_DepBook 既有
   合并规则），gen-b 侧 set_package_properties 实为 optional——极端精确
   需 Find 模块内调用点上下文，收益低。
4. **KF6 全家 need_port**（gen-b 24 / gen-c 26 项）：数据源缺口，根治
   需向 Harmonybrew 提交 KF6 formula 群。
5. **平台块内 find_package 的 Find<Name>.cmake 模块内容平台继承**未实现
   （保守按必需处理）。
6. **corpus-b 克隆 submodule 状态**影响可比性（§5），建议 e2e harness
   对未初始化 submodule 的克隆给出警告。

## 7. 复现

```bash
cd ~/harmony-workspace/worker3/portgraph
python -m unittest discover -s tests        # 101 tests OK
# 阶段 1 回归（fresh DB 流程）
rm workspace/portgraph.db && python portgraph.py ingest all --offline
time python portgraph.py scan workspace/corpus-d
time python portgraph.py deps workspace/corpus-d --json > /tmp/q.json
time python portgraph.py fetch-deps corpus-d --dry-run
python tests/e2e/run_e2e.py run --project corpus-d --fresh-db --no-clone
python tests/e2e/run_e2e.py run --project corpus-c  --fresh-db --no-clone
git diff tests/e2e/reports/                  # 仅时间戳/路径
# 阶段 2 泛化
git clone --depth 1 https://github.com/KDE/gen-b.git  workspace/gen-b
git clone --depth 1 https://github.com/KDE/gen-c.git workspace/gen-c
python portgraph.py deps workspace/gen-b --json | python -m json.tool | less
python portgraph.py fetch-deps gen-b --dry-run
```

改动文件：`port_graph/qt_scanner.py`（引号版本/无关键字组件/平台块行映射/
Config 同形）、`port_graph/deps_report.py`（optional 平台接口/去分隔符
合并/KF 解析/in-tree 容器白名单/平台块 required）、
`port_graph/project_scanner.py`（别名规范化分组键/平台块 raw lib 跳过）、
`port_graph/kb_seed.py`（PKG_ALIASES +2）、`tests/test_port_graph.py`（+14）、
`docs/deps-report.md`（平台块/KF 解析/in-tree 语义文档）、
`tests/e2e/reports/corpus-a.report.{md,json}`（平台块修复后基线更新）。
