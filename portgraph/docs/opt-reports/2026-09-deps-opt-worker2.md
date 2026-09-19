# portgraph 依赖分析功能（deps / fetch-deps）优化报告

- 分支：`worker2-deps-opt`（commit `8d4f446`）
- 范围：`portgraph/portgraph.py`、`portgraph/port_graph/deps_report.py`、
  `portgraph/port_graph/deps_fetch.py`、`portgraph/tests/test_port_graph.py`、
  `portgraph/docs/{deps-report,fetch-deps}.md`
- 验证基准：`python -m unittest discover -s tests`（35 → 38 用例，全过，
  1 skip 为缺 hb-core sparse checkout 的环境跳过）；样例工程 + 真实 DB
  （cmdpkgs 1248 包，`ingest all` 在线采集）端到端跑通 `deps` 与
  `fetch-deps`（dry-run / 真实下载 / 幂等重跑）。

---

## 一、现状梳理（优化前）

| 命令 | 设计意图 | 实测表现 |
|---|---|---|
| `deps <path\|app>` | 依赖全景画像：五类角色 + 多源版本约束 + 产物获取途径 | 功能完整；但 runtime 闭包有 O(D×(V+E)) 的重复查库，文本报告计数/分组有误导，libav 版本量纲错误，路径报错误导 |
| `fetch-deps <app>` | 应用依赖闭包的鸿蒙产物一键获取（bottle 直下 + manifest） | 下载/校验/原子落位/幂等健壮；但测试框架被误报 need_port |

## 二、改动清单（4 个改进点）

### 1. 性能：deps 报告共享图缓存（`deps_report.py`）

- **问题**：`analyze_dependencies` 对**每个** link 依赖独立执行
  `_runtime_closure` BFS，每个节点都走 `db.get_node`/`db.out_edges` 查库。
  合成压测（200 个 find_package × 500 节点深链图）实测 **24.1 万次 SQL
  查询、1.85s**，profile 显示 `_runtime_closure` 占 89% 耗时。真实场景
  （hb 全量入库后的深层闭包）会线性放大。
- **改动**：新增 `_GraphCache`（节点/出边两级 dict 缓存），`_runtime_closure`
  增加 `cache` 参数，分析内所有闭包 BFS 共用一份；`_resolve` 增加解析
  结果缓存（含 None 未命中），dynamic_loads / env_deps 复用同一缓存。
- **效果**：同一压测 **0.16s（约 11.6x）**，link=200 / runtime=499 输出
  与优化前完全一致；环图、共享传递依赖（needed_by 多来源合并）行为不变
  （新增单测覆盖）。

### 2. 准确性：libav* 版本约束不再误报 conflict（`deps_report.py`）

- **问题**：`pkg_check_modules(FF REQUIRED "libavcodec >= 58")` 经
  `LIB_NAME_ALIASES` 归并为 ffmpeg 条目后，`>= 58` 会与 ffmpeg 发布版本
  （如 cmdpkgs 的 8.1.1）直接比较 → 误报 `version_check=conflict` +
  "ffmpeg 版本冲突：要求 >= 58，鸿蒙产物为 7.1" 警告。实际上 58 是
  **libavcodec 库主版本号**（58 ≈ ffmpeg 4.x），8.1.1 完全满足要求。
  ffmpeg 是媒体类 Qt 应用的高频依赖，虚假冲突会误导 agent 去评估
  "降版本/源码编译"。
- **改动**：新增 `LIBAV_LIB_NAMES` 集合；pkg_check_modules 归并时若源名
  （去 lib 前缀）命中 libav 系列，给条目打 `version_req_scope=libav-major`
  并附 ohos_note 说明量纲差异；`_version_check` 对该类约束记 `unknown`
  而非比较。**其他来源的版本约束（find_package 最低版本、conan 范围）
  仍正常校验**。
- **效果**：`deps` 文本/JSON 中 ffmpeg 显示 `version_check=unknown` +
  量纲说明，不再出现虚假冲突警告；`version_req` 原样保留（`>= 58`）。

### 3. 准确性：fetch-deps 测试框架不再误报 need_port（`deps_fetch.py` + `portgraph.py`）

- **问题**：扫描器对 `find_package(GTest)` 也建 runtime 边，fetch-deps
  闭包里 gtest（pkg-unknown 幽灵节点）被分类为 `need_port`，输出
  "gtest 需自行移植（源码: ?）"——测试框架不进发行包，这是对 agent 的
  误导（deps 报告自己就把它归为 test 类，两命令口径不一致）。
- **改动**：`deps_fetch` 新增 `TEST_FRAMEWORKS` 集合；闭包内命中者
  `status=test` / `role=test` + 说明（"测试框架，不进发行包；如需在鸿蒙
  设备跑测试才处理"）。CLI 进度输出与汇总顺序同步支持 `test` 状态；
  `docs/fetch-deps.md` 状态表新增 `test` 行。
- **效果**：demo 工程 fetch-deps 从 "need_port 2"（gtest+x11）变为
  "need_port 1（x11）/ test 1（gtest）"；e2e 对账口径不受影响（e2e 用
  `out_edges` 直接依赖对账，不看 manifest status）。

### 4. 可读性 / 错误处理（`deps_report.py` + `portgraph.py`）

- **build_tools 计数修复**：原 `counts["build_tools"] =
  len(build_tools) + len(tools)` ——但第 10 步已把 build_tools 条目并入
  tools，**重复计数**；且 CMake 最低版本 / C++ 标准 / 编译器三个固定
  展示行不计入（demo 工程显示 "build-tool 0 个" 却列出 3 条）。现改为
  与文本展示一致：`len(tools) + CMake?1 + C++?1 + 编译器1`。
- **link 依赖分组**：文本报告 `link_deps` 按 kind 分组排序
  （package → framework → system-lib → win32-system-lib →
  platform-iface），需要处理的"真外部包"优先呈现，系统库/平台接口垫底。
  JSON 的 `link_deps` 顺序保持不变（按名排序）。
- **deps 路径报错**：传不存在路径（`/no/such/dir`）或文件时，原报
  "app not found: /no/such/dir (先运行 scan)"——用户明明传的是路径。
  现识别路径形态（存在 / 含分隔符 / `.` 开头）报"项目路径不存在或不是
  目录…（若想按已扫描应用分析，请传应用名）"；纯应用名仍走原逻辑。

### 新增测试（`tests/test_port_graph.py`，35 → 38 用例）

| 用例 | 覆盖 |
|---|---|
| `test_libav_version_not_false_conflict` | libav-major 标记 / unknown 校验 / 无冲突警告 |
| `test_build_tools_count_matches_display` | 计数与 tools + 固定行一致（无重复计数） |
| `test_runtime_closure_cache_shared` | 共享缓存下闭包口径：needed_by 多来源合并、环图不死循环 |
| `test_dry_run_classification`（扩展） | fetch-deps 对 gtest 输出 status/role=test |

## 三、优化前后对比

| 维度 | 优化前 | 优化后 |
|---|---|---|
| deps 合成压测（200 依赖 × 500 节点深链） | 1.85s（24.1 万次 SQL） | **0.16s（~11.6x）**，输出一致 |
| ffmpeg（libavcodec >= 58 vs 8.1.1） | `conflict` + 虚假冲突警告 | `unknown` + 量纲说明 |
| fetch-deps 对 GTest | `need_port`（"需自行移植，源码: ?"） | `test`（"不进发行包，跳过"） |
| demo 工程 build-tool 计数 | "0 个"（实际展示 3 条） | "3 个"，与展示一致 |
| link 列表呈现 | 名称混排（X11 夹在包中间） | 按 kind 分组，外部包优先 |
| `deps /no/such/dir` | "app not found…先运行 scan"（误导） | "路径不存在或不是目录…" |

## 四、遗留问题与建议

1. **hb-core 数据源缺自动获取**：`ingest harmonybrew` 在
   `workspace/hb-core` 缺失时静默返回 `files: 0`（无 clone、无警告），
   本次测试环境因此只有 cmdpkgs 单源。建议仿照 cmdpkgs 的自动 clone +
   sparse checkout，或在输出中显式警告"数据源目录缺失"。
2. **同名异库归并仍可能错配**（已知限制）：`_resolve` 的 lib 前缀/后缀
   规则对 MPC（多精度库 vs 音乐播放器）这类同名异义无解，产物 URL 落地
   前仍需人工核对。可考虑在 deps 报告中对"仅经模糊规则命中"的条目加
   `match=approx` 标记。
3. **动态加载只识别字面量**：`QLibrary(name + ".so")` 静态不可见，缺报
   属设计限制；建议在 warnings 中按项目统计 `QLibrary(` 出现次数作
   提示（当前只对命中的字面量提示）。
4. **测试框架的 analyze 口径**：本次只修了 fetch-deps 的呈现；
   `engine.analyze` 仍会把 pkg-unknown:gtest 计入 unknowns（可能把
   verdict 拉成 uncertain）。更彻底的修法是在 project_scanner 对测试
   框架建 `test` 边而非 `runtime` 边，但会改变 analyze/e2e 行为，建议
   单独评估后做。
5. **deps 每次全量重扫**：`cmd_deps` 传路径时每次都重扫 + 重入库
   （幂等但重复）。可加扫描结果缓存（按 mtime/文件数指纹），对大工程
   的反复调用有收益。
6. **e2e harness 未纳入 CI**：`tests/e2e` 需要真实 clone 四个大项目，
   本次环境未执行；建议在文档中标注其网络/磁盘前提，或在有网环境定期
   跑 `run_e2e.py run --all` 作为回归门禁。

---

*报告生成于 worker2-deps-opt 分支优化任务，所有改动已随 commit `8d4f446`
提交，仅涉及 `/root/harmony-workspace/worker2` 目录。*
