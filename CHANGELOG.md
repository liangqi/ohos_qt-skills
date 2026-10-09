# 变更日志

> 外部知识库（开发者版）发版记录。版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
> 版本对象 = 外部仓整包（Qt 公开子集 + 内嵌 ohos-common-kb + kb-init skill + 根文档）。
>
> - **MAJOR** — 破坏性：删/移走用户依赖的页、`audience` 由 public→internal、目录重排致旧链接断、铁律/API 映射被证伪并反转
> - **MINOR** — 内容新增：新页/新节/新 API 映射条目/新 task 类型/内嵌新 KB 或 skill
> - **PATCH** — 内容修正：typo/措辞修正、错误解决方案更新、Qt 参考版本 bump
>
> 发版流程见内部 `procedural/release-external-edition.md`。每版的 `RELEASE-MANIFEST.yaml` 记录源端 KB git SHA + content_tree_sha256，可复现。

---

## v2.3.0 — 未发布

- **MINOR** 新增执行层（Execution Plane）：`tools/qt-ohos-run.py` 统一 CLI + `tools/qt_ohos/` 引擎（纯标准库实现），把迁移知识变成可执行、可恢复、可验证、可沉淀的工程闭环
  - `scan`：项目识别 + Qt 能力扫描 + 三方依赖扫描 + `knowledge/rules/` 18 条机器规则风险报告
  - `analyze-log`：`knowledge/errors/` 41 条 QOH 错误模式自动诊断（与 `problems/` 一一对应；36 条原有 + 5 条 Linux 源码编译沉淀，见下）
  - 状态机 + checkpoint/resume：目标项目 `.qt-ohos/`（state/scan/plan/changes/logs/patches）
  - Verification Gate G0-G12（`verify`）：成功由工具判定，TIMEOUT 永远不是 PASS
  - Source tracking：白名单自动修复（B9 `:!ohos` 作用域、B10 AUTORCC）+ patch 固化/可回滚
  - 知识蒸馏：`draft` / `promote`；`recipes` 检索 episodic 相似迁移案例
  - 任务预算：`QT_OHOS_TASK_BUDGET_SEC` / `QT_OHOS_TASK_DEADLINE`
- **MINOR** 新增 `skills/qt-app-porting/` skill + 任务路由码 [P]；`templates/qt-ohos-app/` CMake 胶水模板（内嵌铁律 B1/B2/B10）
- **MINOR** 新增 `tests/`（引擎自测：YAML 解析、规则匹配、错误匹配、状态机、CLI 冒烟）
- **MINOR** 新增故障库 `faults/`（四实体图模型：症状 S × 根因 C × 临时方案 W × 跟踪单 T）——真源 `faults/_data/*.yaml`（S/W/T 记录+causes/targets/tracks 边）+ `C-*.md` 根因页（frontmatter+depends_on 边）；`tools/faults-build.py` 实现自动演进（`build` 重建派生物 `_graph.yaml` 机读全量图 + `_registry.md` 登记总表；`check` 一致性门禁：ID/枚举/边/日期/refs/limitation 证据；`review` 复核到期扫描+状态推进 lint）；根因定性 defect 会修 vs limitation 规格限制→替代方案，W 含验证与退役条件，T 承载 QTBUG/华为单号与 fix_version 修复版本号；种子 8 根因（5 defect + 2 limitation + 1 undetermined）+ 7 症状 + 6 方案 + 4 跟踪单（迁移自 problems/episodic/semantic 既有知识）；任务路由新增 [R] 故障跟踪
- **MINOR** 故障库新增协作提交与合入流程：`faults/_drafts/`（`_template.md` 协作者提交清单——现象原文/环境三件套/复现 demo·defect 类必附·limitation 类用官方文档链接替代/查重声明）+ 主编合入门禁六步（查重→**复现 demo 必测**·未复现不合入→人工核验·证据链/定性/归层/事实/脱敏→复现留痕登记 C 页验证记录→promote 拆分合入→build 门禁）；草稿状态机 draft/in-review/returned/rejected；`review` 子命令列出待审草稿
- **MINOR** 故障库新增问题确认证据标准与复现 demo 编写原则：C 页必填 `evidence_type`（demo 复现工程 / logs 调试日志+栈 / both / source 源码 file:line·仅静态可判定类 / docs·limitation 专用），`check` 机器强制——defect 禁仅凭 docs 定性、Qt 框架侧 defect 仅 source 收 WARN（提上游前补动态证据）、**在跟上游单（qt-bug/ohos-issue/partner）的 defect/undetermined 必须 demo/logs/both**（对齐 `qt-bug-report-generation` 可复现性 HARD 闸门）；复现 demo 编写七原则（最小化/自包含可构建/确定性/对照性/纯净根因/携带诊断输出/版本留痕）与无 demo 降级通道（日志+栈+采集环境三件套）；**Qt 框架侧问题 demo 硬性要求：复现逻辑集中在单个 main.cpp（ohos 工程仅胶水壳）+ 复现步骤编号到操作级（无步骤视为未完成）**
- **MINOR** 故障库新增**处置分类**派生视图（`faults-build.py` 从 nature×responsible 自动计算，不入真源）：鸿蒙必须适配（limitation）/ Qt 问题（defect+qt 侧）/ 系统问题（defect+ohos 侧）/ 应用使用问题（responsible=app，配套放宽为允许薄 C 页）/ 三方库问题 / 待定性；登记表新增 §按处置分类，`_graph.yaml` 增 disposition 字段
- **MINOR** 故障库**历史问题导入批次 1**（10 个问题，3 个并行子 agent 分析 + 主编审核合入）：QDialog blockedByModal（C-0009+patch）、@ohos.deviceInfo 裸 eval 模板崩溃（C-0010）、mainthread Q_ASSERT（C-0011，undetermined）、dlopen 可写路径（C-0012+QTBUG-146624）、沙箱只读写崩溃（C-0013）、跨屏闪烁（C-0014）、hvigor CLI/IDE 打包分歧（C-0015，undetermined）、QFileDialog 误加守卫（C-0016，应用使用问题首例）、curl 中文乱码（C-0017）、ZINK RGBA8 mipmap 黑纹理（C-0018，三方库首例）；图规模 S 7→17 / C 8→18 / W 6→15 / T 4→5，14 处源页 refs 回填
- **MINOR** 故障库新增**链路完备性（闭环规则）**：defect（外部责任）的"临时解决"必须同时具备采用中方案（W adopted）与在跟单（T）——缺一即未闭环（missing-ticket/missing-workaround/both-missing，`faults-build.py` 派生 `chain_state`/`gaps`）；limitation 与应用问题必须有采用中方案；**缺口向上传播**（S 的了结宣称受 causes 聚合约束：S=resolved 而链有缺 → ERROR，S=mitigated 无 adopted W → ERROR，C=workaround 未闭环 → WARN）；`_registry.md` 新增 §未闭环清单（缺单/缺方案/双缺分组）+ 症状索引闭环列 + 统计"链路闭环"行，`_graph.yaml` S/C 节点增 chain_state/gaps，`review` 增"未闭环（待补齐）"段；数据修正 W-0004 targets 扩至 C-0005+C-0006（换构建组合同时绕开两根因）
- **MINOR** qt-sdk-forge **Linux 全链路支持 + 实测验证**（Ubuntu 22.04 x86_64：Qt 5.12.12 GLES release + OpenHarmony SDK 6.1.0.35 → SV0-SV6/SV8 PASS，2026-09-19）。沉淀自一次完整 Linux 编译实战，五坑全部转为机器级预防（错误发生前拦截）：
  - **QOH037 源码快照缺陷**：GitCode 开源镜像初始导入丢全部执行位（620 个 shebang 脚本）、`main`/`5.12.12` 快照带 CRLF、且无 `tqtc/*` 商业分支名——`src-clone --method opensource` 现默认检出 POSIX 构建分支 `build/macos-arm64-qt5.12.12`（新增 `OPENSOURCE_BRANCHES` 映射 + `--branch` 覆盖），克隆后自动恢复执行位并以 git 提交固化，CRLF 树直接拒绝
  - **QOH038 python 别名缺失**：qtdeclarative 调 `python` 而 Linux 只有 `python3`——`build_env()` 自动创建 `.qtsdk/pyshim/python`（不污染宿主）；SV0 新增 `python3`/`python_alias` 检查
  - **QOH039 QtDBus 编不过**：clang 15 的 `-Wdeprecated-copy` × mkspec `-Werror`；且鸿蒙运行时无 DBus（QOH002）——CLI configure 内置 `-no-dbus`（对齐官方预构建与 semantic 页）
  - **QOH040 脏构建目录（增量第四坑）**：改配置/换 SDK 后旧 `qt_lib_dbus.pri` 残留使 `qtHaveModule(dbus)` 误真、ibus 插件照常构建——configure 新增指纹防护（configure 参数 + OHOS SDK 版本指纹），变化即自动清构建目录
  - **QOH041 SDK API 过旧**：qarkui QPA 编译期取 ArkUI NDK 符号地址，需 apiVersion ≥ 23（OpenHarmony ≥ 6.1；官方构建 API 24）——`build-matrix.md` 新增 §2.1「Linux 获取 OHOS SDK」：OpenHarmony 公开镜像 URL 规律、版本选择表、解压登记步骤、低内存 jobs 建议
  - 配套：`problems/` 新增 5 页（事实源）、`knowledge/errors/` 36→41 条、`_lookup.md` 重建、kb-init `qt-src-acquisition.md` 修正开源分支说明（同 QOH037 根因）
- **PATCH** qt-sdk-forge CLI 修复：`env` 子命令现尊重 `config set qt_src/ohos_sdk_native`（原先只读 ENV.local.md，配置 apparent 失效）；`building.py` configure 失败路径 `key` 未赋值崩溃；`run_git()` 调用签名错误 7 处（releasing/srctree/patching，`release`/`upstream-check` 必崩）；`-no-dbus` 加入内置 configure 参数
- **MINOR** 新增多 Agent 协作协议 `_index/_agent-mesh.md`（单一真源）：知识库拆分为 7 核心 + 2 可选 agent 的接口卡（触发/CLI/门禁/状态平面/入站出站交付件，port-assessor / framework-analyst / test-verifier 以接口卡为定义）；新增 **Task Ledger 平面**（`workspace/tasks/`，gitignored）——`task.yaml` 任务台账 + `flow.jsonl` 流转日志（七类固定写点：task-created / handoff-in·out / gate / anomaly / budget-exhausted / human-required / draft-produced / task-closed，追加不可改写、每条带 refs）+ `ho-*.yaml` 移交信封（泛化 qt-sdk-forge inbox 协议，8 种 type）；三条任务链（移植 / 问题 / 演进）；**人工接入点三级分类**（H1 阻断决策 / H2 人工执行 / H3 复核确认）逐 agent 明确 + 5 条通用红线（凭据·账号·付费·对外提交一律人工、发布·删除·ENV 切换须确认、门禁语义不得升格、无证据不定性、human-required 必留痕）；并发契约沿用 `.qtsdk/` 文件锁 + 原子替换。配套新增 `skills/task-dispatcher/`（调度中枢：建档→路由→监控→关单移交）与 `skills/kb-iterator/`（工程迭代主编：合入门禁 / 索引再生 / kb-verify 事实校验 / flow.jsonl 复盘蒸馏 / 演进复核——唯一真源写入门）；qt-app-porting 与 qt-sdk-forge SKILL.md 补"接口与人工接入"节；AGENTS 技能表注册、_task-routing 挂接
- **PATCH** 发布分支裁剪（bitfun-release）：`CLAUDE.md` 移出版本管理（`AGENTS.md` 同内容保留为入库真源，本地可复制生成，README/AGENTS 多工具表同步修正）；`HANDOVER.md` 交接文档与内部工作草稿不入库（.gitignore 防回滑）；`_agent-mesh.md` §八内部调度平台 ID 脱敏（协议与编排语义保留）
- **MINOR** 新增根级 `SKILL.md`：知识库 skill 化总入口——frontmatter 触发词覆盖"鸿蒙化/移植 Qt/三方依赖分析/构建报错"等场景（鸿蒙化 Qt 应用时自动加载），正文固化主工作流（Step 0 portgraph 可行性评估与依赖闭包 → qt-ohos-run 流水线 → G0-G12 门禁）、三方依赖分析与下载（deps 角色分类 + fetch/fetch-deps bottle 一键获取）、知识检索入口与纪律红线
- **PATCH** README 全面重写并与知识库实际对齐（多路一致性校验）：任务路由 13→15 类（补 [S] SDK 工程）、QOH 错误模式 36→41、API 映射 12→13 类、目录树补 knowledge/tools/portgraph/templates/tests/.gitcode 与 5 个 skills、Skills 表补全（SKILL.md 总入口 + qt-sdk-forge/task-dispatcher/kb-iterator + portgraph 仓库工具）、移除对外失效的 `_scripts/kb-dev-edition.sh` 引用；结构按开源最佳实践重构（徽章行 + 核心能力表 + 30 秒上手 + AI 接入矩阵 + CLI 折叠子命令清单 + FAQ + 已知限制 + 版本 v2.3.0）
- **MINOR** 新增知识库一致性自测 `tests/test_kb_consistency.py`（20 用例，纯标准库，`python -m unittest discover -s tests -v` 与引擎测试同跑）：**L1** Skill 清单规范（根级+5 子级 SKILL.md frontmatter name/description、AGENTS 技能表登记完整性）；**L2** 文档计数一致性——文档声称 == 实际值（QOH 41 / R 规则 18 / 铁律 35 / 任务路由 15 / API 映射 13 / problems 46 / faults 图 17-18-15-5 / 测试用例数），数字漂移在提交前被拦截（keep numbers real）；**L3** 交叉引用完整性（QOH refs → problems 页、README/SKILL/AGENTS/_task-routing 行内路径解析——支持 `qt-`/`qt-harmonyos-`/`qt-ohos-` 简写前缀约定、README 相对链接与锚点）；**L4** CLI 契约（qt-ohos-run 24 / qt-sdk-run 24 / portgraph 10 子命令集合，增删命令须显式更新测试）；**L5** faults-build check 集成门禁（exit 0 = ERROR 清零）
- **PATCH** 一致性测试落地即修复一批同源过时项与规范缺陷：AGENTS.md（36→41 QOH、`_scripts/kb-dev-edition.sh` 失效引用移除、H1 标题 CLAUDE.md→AGENTS.md）；_task-routing.md（[H] ~36→145+ API、"33 条铁律"→35、B1-B11→B1-B12、W1-W5→W1-W6、"36 条错误模式"→41、决策树补 [P] 自动迁移条目）；portgraph/README.md（接口白名单 19→22、单测 35→119）；_dashboard.md（semantic 24→26 补 blocking-taxonomy/dev-guide 两页、problems 41→46、合计活跃 47→48）；skills/qt-app-porting/SKILL.md frontmatter 规范化（`***`/长横线围栏→`---`，描述体补缩进）、kb-iterator 与 task-dispatcher 的长横线闭合围栏→`---`；portgraph 测试删除 1 个同类遮蔽的死用例（test_build_tools_count_matches_display，120 定义→119 实跑）；README [N] 路由 deveco-mcp-capabilities 补全 ohos-common-kb-public/ 前缀、单测数 120→119
- **PATCH** 知识库应用名脱敏（内容策略：知识库不携带特定应用名的鸿蒙化信息，防止 agent 锚定具体案例走捷径）：删除 episodic 应用复盘 2 页（某 IM 客户端全量移植复盘、229 应用普查页），通用经验蒸馏保留——"同文件多处修改必须串行"入 qt-app-harmonyos-migration 陷阱节、bottle 缺口镜像源/静态转共享技巧入 third-party-libs §3.4、三大阻断模块统计（D-Bus/QtMultimedia/QtWebEngine）入 modules 快速查找；路由/协议/procedural 层实证引用改"某大型应用"式表述并移除内部协作过程细节；problems/semantic 证据性提及泛化（批次编译清单、参考实现等）；portgraph 文档示例换 sample-app 虚构样例（e2e corpus.json 测试基础设施真实 URL 豁免；SARibbon/Coin3D 等三方库名按 [M] 路向知识保留）；faults 真源 W-0008 标题同步脱敏并重建派生物（build OK / check 0 ERROR）。计数联动：episodic 8→6、合计活跃 48→46。注：远端历史提交仍含应用名，未改写公开历史
- **FIX** devecocli 工具可用性预检（干净环境测试实证：agent 无法一次定位 devecocli）。根因：三处文档三个说法且全不符事实——kb-init 称"DevEco Studio 自带于 `<DEVECO>/tools/devecocli`"（实测不存在）、usage-rules 让装 `@deveco-test/deveco-cli`（测试通道）、deveco-install 让装 `deveco-cli`（裸包名在 npm 上不存在）；实际来源为 npm 包 `@deveco/deveco-cli`（二进制 `devecocli`，PATH 可用）。修复：① deveco-cli-usage-rules 新增"工具可用性预检（开工前必做）"——四级定位顺序（ENV.local.md `DEVECO_CLI` → PATH → npm 全局 → DevEco 捆绑）+ `--version` 验证 + 失败即停报告纪律；② detect-env.sh 定位优先级改为 PATH → npm 全局 → 捆绑兜底，新增 `DEVECO_CLI_VERSION` 输出，OSS 检测改为 npm 包探测；③ generate-env-local.sh 新增 `--deveco-cli` 参数写入 `DEVECO_CLI` 变量；④ install-deveco-cli.sh / install-deps-harmonyos.sh 包名与二进制名全部修正（`npm i -g @deveco/deveco-cli`）；⑤ kb-init SKILL 检查段与故障排查表重写（双 shell 命令）；⑥ env-variables/deveco-install 补 `DEVECO_CLI` 变量与"常见误认"表；⑦ 根 SKILL.md 纪律红线与 AGENTS.md 执行纪律新增"工具可用性预检"条目。顺带：usage-rules 中 NeoHtop/open-pencil 应用名泛化（脱敏策略补漏）
- **NEW** `tools/cpp20-gap-scan.py`——OHOS clang15/libc++15 的 C++20 缺口**编译前预检与机械修复**（干净环境实测驱动：大工程全量编译一轮数十分钟，"撞错→定位→修复"逐轮迭代代价高，预检一次出全部命中点）。8 条规则对齐 problems/build-clang15-libcpp15-cpp20-gaps.md：GAP-01 结构化绑定 lambda 捕获（P1091）/ GAP-02 make_unique_for_overwrite（唯一自动修复项，幂等）/ GAP-03 stop_token·jthread / GAP-04 atomic_ref / GAP-05 std::ranges / GAP-06 defaulted `<=>` 含 shared_ptr / GAP-07 纯 init-capture lambda / GAP-08 pthread_setaffinity_np；P0634·P0960·construct_at·variant best_match 编译期才能发现，文档注明不在扫描范围。scan 模式 CI 友好（有缺口 exit 1，支持 --json），fix 默认 dry-run。接入：迁移工作流阶段零预检第 8 项 + SKILL.md Step 1 构建前步骤 + problems 页"预检工具"节；problems 页"其他同类坑"补实战新缺口 2 条（make_unique_for_overwrite、init-capture+this）。单测 9 例（tests/test_cpp20_gap_scan.py）
- **NEW** QOH042（harmonydeployqt 设备侧部署缺口，5 类系统性问题）——来源：干净环境全流程鸿蒙化测试的 agent 自沉淀草稿（人工核验后合入，应用痕迹已泛化）：①QPA 插件非 Qt 依赖（fontconfig 链）不部署（copyPlatformPlugin 只认 libQt6* 前缀）；②无 SONAME 的 bottle .so 产生绝对路径 DT_NEEDED，readElfDependencies 遇盘符 `:` 截断整个依赖清单；③libz.so.1 按 Android 惯例被跳过但不在鸿蒙应用 linker namespace；④设备系统库在 chipset-sdk-sp/ndk/platformsdk 非标路径；⑤bottle 缺无版本化文件名。附 readelf 闭包检查方法与 5 条部署前检查清单 + hvigor 环境三件套（DEVECO_SDK_HOME/JAVA_HOME/反斜杠 PATH）。新增 problems/runtime-harmonydeployqt-deploy-gaps.md（与 runtime-hap-missing-so-closure 互为部署侧/运行时侧姊妹篇）+ knowledge/errors/QOH042.yaml + _lookup 索引行；计数联动 41→42（index.yaml/README/SKILL/AGENTS/_task-routing/build-matrix）。本轮实测该部署缺口类问题耗 时约占全程 1/4（单步最长 3h），入 QOH 后 analyze-log 可机器直达
- **FIX（测试驱动）** 回合收尾纪律（SKILL.md 纪律红线 #7 + AGENTS.md 执行纪律）——干净环境全流程测试第二轮实测死因：非交互 CLI 会话中主 agent 输出"进行中"总结后结束回合（回合结束=会话退出），3 个脱管子进程完成各自 stub 后就地解散，无人接管构建阶段，流水线断链。新纪律：未达 verify 终态或人工确认点禁止收尾，后台任务必须 wait 至完成；确需中止时状态落盘 .qt-ohos/ 并写明续跑方式
- **NEW（测试驱动）** libc++15 实验性开关 `-D_LIBCPP_ENABLE_EXPERIMENTAL`（problems/build-clang15-libcpp15-cpp20-gaps.md §9 + cpp20-gap-scan GAP-05 建议前置）——实测默认缺 16 项 ranges 算法、加开关后全部可用且 <format> 同步解锁，可省逐算法改写；jthread/expected/source_location/clock_cast 仍缺按原章节处理
- **NEW（测试驱动）** 大仓库获取韧性（SKILL.md Step 0）——弱网下 clone 大 pack 被掐断（curl 56 early EOF）重试仍失败时，改 codeload tarball 断点续传（github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>），解压入 portgraph workspace 后 scan 照常
- **FIX（测试驱动）** 回合收尾纪律升级为操作级（SKILL.md 红线 #7 + AGENTS.md）——第三轮测试 42 分钟即死于同一模式（拉到纪律版 KB 仍"委派 3 个后台代理后收尾"），纯"禁止收尾"表述不足以纠正模型行为；升级为操作级禁令：**禁止"委派后台代理后收尾等待"**（该模式在此环境=任务中断），长任务必须回合内同步等待或顺序自己执行，确要并行只能会话内阻塞式等待；并强调"没有任何机制会唤醒你"
- **PERF（测试驱动）** portgraph `fetch-deps` 并行下载——第四轮测试实测死因：弱网下串行下载 57KB/s 拖垮全流程（单步 90 分钟超时 + 最终 manifest 30 分钟，agent 被迫自研 4 批并行下载脚本 471 秒拿下 33 包）。修复：`fetch_bottle` 拆出 `prefetch_bottles`（ThreadPoolExecutor 并行预取 tar 到 .cache，默认 8 线程，缓存命中/已安装自动跳过，单包失败不阻断）；`_download` 加缓存命中跳过（sha 匹配不重下，天然支持重跑只补缺）；解压保持串行（规避 Windows 杀软文件锁竞态）。CLI 新增 `--jobs`（默认 8，0/1 关闭）。单测 4 例（tests/test_prefetch.py：并行+缓存命中 mtime 验证 / 已安装跳过 / 坏 sha 失败清理 / 无 sha 信任已有文件）
- note: `RELEASE-MANIFEST.yaml` 的 `content_tree_sha256` 将在下次发版时由发版脚本重新生成

## v2.2.1 — 2026-08-29

- fix(procedural+semantic): 修复 skills 自嵌套与 manifest 幽灵 skill

- copy_skills 在持久化/复用 OUT（如 dist/dev-edition 二次构建）下 cp -r src dst 会把 src 拷进已存在的 dst → 产出 skills/skills/ 双层嵌套；改 rm -rf + /. 拷内容防嵌套。
- gen-release-manifest skills 枚举盲目收所有子目录，把自嵌套的 skills/ 登记成幽灵 skill（manifest 出现 skills: ["kb-init","skills"]）；加 SKILL.md 校验 + 跳过自嵌套目录兜底。
- PR#9 曾手动清理外部仓 skills/skills/ 产物，本次在源端两层加固固化，避免复发。

## v2.2.0 — 2026-08-27

- Qt5+CEF 鸿蒙开发指导 + issue 模板（.gitcode/ISSUE_TEMPLATE/）+ xsy-letos/xsy-pyqt 迁移经验 + 版本化发版机制（kb-publish.py 固定脚本从 main 发版）

## v2.1.0 — 2026-08-25

- Qt6.12 beta3 模块状态更新（QtHarmonyExtras 重新独立成模块 + 文件权限接口修正）；新增若干 Qt 应用 OHOS 迁移编译经验；修正公开页硬编码 Qt 路径脱敏；新增版本化发版机制（README 能力规格节 + RELEASE-MANIFEST + CHANGELOG）

## v2.0.0 — 2026-08-19

- **MINOR** 内嵌 `ohos-common-kb` 公开子集（ArkTS/ArkUI/NAPI/Stage 模型/DevEco 工具链基础）到 `ohos-common-kb-public/`
- **MINOR** 新增 `skills/kb-init/` 初始化 skill：环境探测 → 引导安装缺失依赖 → 生成 `ENV.local.md` → 校验环境
- **MINOR** 多渠道 Qt 源码获取（商业 license `codereview.qt-project.org` / 开源镜像 `ohos-qt/qt-harmonyos-src` / 预编译 SDK releases）
- **MINOR** 新增根文档 `SETUP.md` / `CONTRIBUTING.md` / `SECURITY.md`
- **MINOR** `RELEASE-MANIFEST.yaml` 记录多源 SHA + `content_tree_sha256` + 页数计数（builder v2, schema v1）

> v2.0.0 之前的旧 5-skill 仓库历史见 `legacy/pre-rewrite-*` tag（已快照至内部 `raw/imports/ohos_qt-skills-legacy/` 供未来继承）。未回填 v1.0.0。
