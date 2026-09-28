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
- note: `RELEASE-MANIFEST.yaml` 的 `content_tree_sha256` 将在下次发版时由发版脚本重新生成

## v2.2.1 — 2026-08-29

- fix(procedural+semantic): 修复 skills 自嵌套与 manifest 幽灵 skill

- copy_skills 在持久化/复用 OUT（如 dist/dev-edition 二次构建）下 cp -r src dst 会把 src 拷进已存在的 dst → 产出 skills/skills/ 双层嵌套；改 rm -rf + /. 拷内容防嵌套。
- gen-release-manifest skills 枚举盲目收所有子目录，把自嵌套的 skills/ 登记成幽灵 skill（manifest 出现 skills: ["kb-init","skills"]）；加 SKILL.md 校验 + 跳过自嵌套目录兜底。
- PR#9 曾手动清理外部仓 skills/skills/ 产物，本次在源端两层加固固化，避免复发。

## v2.2.0 — 2026-08-27

- Qt5+CEF 鸿蒙开发指导 + issue 模板（.gitcode/ISSUE_TEMPLATE/）+ xsy-letos/xsy-pyqt 迁移经验 + 版本化发版机制（kb-publish.py 固定脚本从 main 发版）

## v2.1.0 — 2026-08-25

- Qt6.12 beta3 模块状态更新（QtHarmonyExtras 重新独立成模块 + 文件权限接口修正）；新增 QCTools/xi-qt OHOS 迁移经验；修正公开页硬编码 Qt 路径脱敏；新增版本化发版机制（README 能力规格节 + RELEASE-MANIFEST + CHANGELOG）

## v2.0.0 — 2026-08-19

- **MINOR** 内嵌 `ohos-common-kb` 公开子集（ArkTS/ArkUI/NAPI/Stage 模型/DevEco 工具链基础）到 `ohos-common-kb-public/`
- **MINOR** 新增 `skills/kb-init/` 初始化 skill：环境探测 → 引导安装缺失依赖 → 生成 `ENV.local.md` → 校验环境
- **MINOR** 多渠道 Qt 源码获取（商业 license `codereview.qt-project.org` / 开源镜像 `ohos-qt/qt-harmonyos-src` / 预编译 SDK releases）
- **MINOR** 新增根文档 `SETUP.md` / `CONTRIBUTING.md` / `SECURITY.md`
- **MINOR** `RELEASE-MANIFEST.yaml` 记录多源 SHA + `content_tree_sha256` + 页数计数（builder v2, schema v1）

> v2.0.0 之前的旧 5-skill 仓库历史见 `legacy/pre-rewrite-*` tag（已快照至内部 `raw/imports/ohos_qt-skills-legacy/` 供未来继承）。未回填 v1.0.0。
