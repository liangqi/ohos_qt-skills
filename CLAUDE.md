# AGENTS.md

本文件是 Agent 在本仓工作的**行为契约**（`CLAUDE.md` 为逐字副本，`_scripts/verify.sh` 强校验两者一致）。

> **本仓是 Qt → HarmonyOS 迁移工程仓**：知识层（人读的事实）+ 机器层（工具读的判据）+
> 执行层（能跑的 CLI 与门禁）+ 治理层（契约与自检）。它不是一个只读文档集，
> 每次任务都可能同时产出代码改动、状态落盘与知识沉淀。

---

## 首次使用（Agent 必读）

若用户是第一次使用本仓，或 `ENV.local.md` 不存在，且任务需要本地工具链（构建 / 装机 /
签名 / SDK 编译），**必须**先执行 `skills/kb-init/SKILL.md`：检测 DevEco Studio、HarmonyOS
SDK、Qt 源码/SDK，引导安装缺失依赖，生成 `ENV.local.md` 并验证可用。

**触发关键词**：初始化、配置环境、第一次使用、setup、install、`ENV.local.md` 不存在。

纯查询类任务（读知识页、看 API 支持情况）**不需要**初始化。

---

## 仓库结构

```
kb.yaml          仓库契约：入口 / 地图 / 自检命令 / 分层必需路径
SKILL.md         Agent 总入口（frontmatter + Instructions）
AGENTS.md/.md    Agent 行为契约（两份一致）
_scripts/        门禁与发版：ci.py / verify.py / gen-manifest.py（ci.sh 为薄壳）
_index/          索引层（_map 地图、_tags 标签、_dashboard 仪表盘、_task-routing 路由）
semantic/        语义知识：概念、API 映射、模块状态、平台限制、构建与窗口模型
procedural/      程序知识：迁移、排障、构建运行、发版、Demo 生成
episodic/        情景知识：真实项目复盘（postmortems/）
problems/        错误知识库：实际编译/部署/运行报错与解法（_lookup.md 为检索入口）
ohos-common-kb-public/  内嵌 HarmonyOS 平台通用知识（ArkTS/ArkUI/NAPI/Stage/工具链）
knowledge/       机器层：errors（QOH 错误模式）、rules（R 预扫描规则）、adaptation
faults/          故障图：_data 真源 + C 根因页 → _graph.yaml / _registry.md 派生物
tools/           执行层：qt-ohos-run.py / qt-sdk-run.py / faults-build.py / kb-verify-qt.py
templates/       鸿蒙壳工程模板（qt-ohos-app）
portgraph/       可移植性图谱子项目（可行性三态 + 依赖分析）
tests/           仓库一致性与引擎自测
skills/          Agent Skills（6 个，按写权限切边界）
```

## 加载协议（接到任务先做这三件）

```
① _index/_task-routing.md               → 匹配 15 类任务之一，确定必读页与工作流
② semantic/qt-harmonyos-golden-rules.md → 扫 35 条铁律，避开已知陷阱
③ _index/_map.md                        → 按 summary 判断相关性，只读相关页
   沿 refs 追交叉引用；需要本地工具时先确认 ENV.local.md 与工具可用性
```

## 真源与写权限

| 层 | 谁可以写 | 规则 |
|----|---------|------|
| 知识真源（`semantic/` `procedural/` `episodic/` `problems/` `faults/` `knowledge/`） | 仅 `kb-iterator` | 业务 agent 只能投草稿；改 `knowledge/` 与 `faults/` 后必须重建派生物 |
| 执行层（`tools/` `portgraph/` `templates/`） | 代码贡献者 | 改动必须带测试，且不得放宽门禁判据 |
| 目标项目（用户的应用） | `qt-app-porting` / `qt-sdk-forge` | 只做受追踪修改，写入 `.qt-ohos/changes.json` 与 patches |
| 索引（`_index/`）、README、SKILL、AGENTS | 维护者 | 数量变化必须同步，`tests/test_kb_consistency.py` 会拦 |

**机器层是知识层的投影，不是第二真源**：`knowledge/errors/*.yaml` 的 `refs.problems` 必须指向
存在的 `problems/` 页；`faults/_graph.yaml` 与 `_registry.md` 由 `tools/faults-build.py build`
生成，禁止手改。

## 场景入口

| 我想做... | 走哪里 |
|----------|--------|
| 移植 Qt 应用到鸿蒙 | 第 0 步 `python portgraph/portgraph.py analyze <app>` + `deps` → `procedural/qt-app-harmonyos-migration` + `semantic/qt-harmonyos-porting-workflow` |
| 查 API 替换 | `semantic/qt-harmonyos-api-mapping` + `qt-harmonyos-code-patterns` |
| 查模块是否支持鸿蒙 | `semantic/qt-harmonyos-modules` |
| 查平台限制 | `semantic/qt-harmonyos-platform-limits` |
| 编译/打包/部署报错 | 先 `python tools/qt-ohos-run.py analyze-log <日志>`，再查 `problems/_lookup.md` |
| 窗口/对话框/生命周期异常 | `semantic/qt-harmonyos-window-model` + `qt-harmonyos-lifecycle` + 铁律对应章节 |
| 判断问题归谁（Qt 缺陷 / 鸿蒙限制 / 应用问题） | `faults/_registry.md` 症状索引 → C 页定性、责任领域、临时方案、跟踪单 |
| 三方库与交叉编译 | `semantic/qt-harmonyos-third-party-libs` + `portgraph deps` / `fetch-deps` |
| 编 SDK / 打 Qt 补丁 | `skills/qt-sdk-forge/SKILL.md` + `tools/qt-sdk-run.py` |
| 社区版迁移到官方版 | `skills/qt-community-to-official/SKILL.md` |
| 写 demo / 验证工程 | `procedural/demo-generation` + `templates/qt-ohos-app` |

## Skills（Agent 自动化能力）

| Skill | 用途 | 触发 |
|-------|------|------|
| `kb-init` | 环境初始化：检测依赖、安装缺失组件、生成 `ENV.local.md`、验证环境 | "初始化""配置环境""ENV.local.md 不存在" |
| `qt-app-porting` | 应用迁移主流水线（`tools/qt-ohos-run.py`）：扫描→计划→受追踪修改→构建→装机→门禁→报告→沉淀 | "迁移/移植/鸿蒙化这个项目""验证迁移结果""分析这些日志" |
| `qt-sdk-forge` | Qt 本地 SDK 工程平面（`tools/qt-sdk-run.py`）：编译、补丁导入/应用/溯源、SV0–SV8 发版、上游演进跟踪 | "编译/重编 Qt""给 Qt 打补丁""出 SDK 版本""看上游更新" |
| `qt-community-to-official` | 社区版（QtOhExtras）→ 官方版（QtOhosExtras）代码迁移、patch 生成、编译修复、签名 HAP | "从社区版迁到官方版""QtOhExtras/QOhAppContext 迁移" |
| `task-dispatcher` | 多 Agent 协作调度：任务台账（task.yaml）、移交信封（ho-\*.yaml）、流转日志（flow.jsonl） | 多 agent 模式下发起任务、查状态、续跑、关单 |
| `kb-iterator` | 知识库唯一真源写入门：草稿主编门禁、QOH/R promote、索引再生、事实复核、复盘蒸馏 | "合入草稿""复核 faults""重建索引""检查上游演进影响" |
| `portgraph`（仓库工具，非 skill） | 可行性三态判定 + 依赖角色分类 + 依赖闭包 | 任何移植/评估任务的第 0 步 |

## 执行纪律（强制）

- **成功判据唯一**：应用迁移以 `python tools/qt-ohos-run.py verify` 的 G0–G12 为准，SDK 以
  `qt-sdk-run.py verify` 的 SV0–SV8 为准。编译通过 ≠ 迁移成功；`TIMEOUT` 永远不是 PASS。
- **日志先机器匹配**：`analyze-log` 命中 42 条 QOH 模式后再读知识页，不要跳过匹配直接猜。
- **改动受追踪**：所有自动修改进 `.qt-ohos/changes.json` 与 patches；禁止盲目扩写
  `Q_OS_LINUX` 守卫（鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`），禁止注释功能代码换编译通过。
- **工具可用性预检**：构建/装机/签名/日志前先定位并验证 `devecocli`、`hdc`、Qt OHOS SDK
  （`devecocli` 顺序：`ENV.local.md` 的 `DEVECO_CLI` → PATH → npm 全局 → DevEco 捆绑；
  它不一定随 DevEco Studio 安装）。不可用即停下报告并给安装命令，禁止用猜测路径继续。
- **回合收尾纪律**：非交互会话（`opencode run` / `claude -p` 等）中回合结束即会话退出，
  没有任何机制会唤醒你。禁止"派后台代理后收尾等待"；长任务必须在本回合内同步等待或顺序执行；
  未到 `verify` 终态或人工确认点禁止输出总结停止；中止需把状态落盘 `.qt-ohos/` 并写明续跑方式。
- **故障库真源改动后必须重建**：跑 `python tools/faults-build.py build`，`check` 零 ERROR；
  复核用 `review` 扫到期与状态推进。
- **草稿合入走主编门禁**（`faults/_index.md` §六）：defect/undetermined 类必须**复现 demo 必测**，
  人工核验（证据链/定性/归层/事实/脱敏），复现结果登记进 C 页"版本验证记录"首行，才可 promote。
- **证据标准**：定性 Qt 框架侧问题必须有复现 demo 或调试日志+栈（C 页 `evidence_type`，
  静态可判定类可用 source 例外并标警告）；纯转述/猜测不受理。Qt 侧 demo 要求复现逻辑集中在
  单个 `main.cpp`（ohos 工程仅胶水壳）且写明编号复现步骤。
- **链路闭环**（`faults/_index.md` §四）：defect 的"临时解决"必须同时有采用中方案（W adopted）
  与在跟单（T）；limitation 与应用问题必须有采用中方案；缺口向上传播，S 宣称 resolved 而链有缺 → ERROR。
- **收工自检**：`python _scripts/ci.py` 必须通过（等价 `bash _scripts/ci.sh`；Windows 无 bash 用前者）；
  改了文档数字却没改事实，门禁会红。

## 分支与交付

- `trunk` 是主干与稳定版本来源；开发在自己的开发分支上做，合并回 `trunk` 前必须过门禁。
- 旧分支（`main`、`bitfun-release` 等）**冻结不动**，不要在其上提交。
- 提交信息写清"改了什么事实/判据"，不要只写"update"。

## 待办与进度

- `TODO.md`：入库的待办模板（结构规范，不含实际条目）。
- `TODO.local.md`：个人实际待办与进度（已 gitignore，不入库）。
- 多步骤任务在阶段转换时更新 `TODO.local.md`；纯查询任务无需同步。

## 多工具兼容

| 工具 | 集成方式 |
|------|---------|
| Claude Code | 本仓同时携带 `CLAUDE.md`（`AGENTS.md` 的逐字副本，`verify` 校验一致） |
| Codex | `AGENTS.md` 自动加载 |
| Cursor / Windsurf | 在 `.cursorrules` / `.windsurfrules` 中引用 `_index/_map.md` |
| Obsidian | 直接作为 Vault 打开，利用引用图 |

## 内容来源与版本基准

| 来源 | 说明 |
|------|------|
| Qt 官方文档 | wiki.qt.io、doc.qt.io（API 映射、模块状态） |
| HarmonyOS 官方文档 | developer.huawei.com（生命周期、窗口模型、平台限制） |
| Qt 源码验证 | QtOhosExtras、QPA 插件源码（签名、枚举路径） |
| 实践经验 | 真实迁移复盘、故障分析、实际报错积累 |

| 版本 | 分支 | Commit | 日期 |
|------|------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |
