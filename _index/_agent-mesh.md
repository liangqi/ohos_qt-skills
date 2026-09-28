---
id: agent-mesh
type: meta
domain: workflow
tags: [agent, multi-agent, protocol, handoff, flow-log, human-in-the-loop, task-ledger]
created: 2026-09-23
updated: 2026-09-23
status: active
refs: [agent-task-routing, faults-index, qt-app-porting, qt-sdk-forge, framework-issue-analysis, qt-ohos-run-test, framework-fix-verification]
summary: >
  多 Agent 协作总协议（单一真源）：知识库拆分为 7 个核心 agent + 2 个可选 agent 的接口卡
  （触发 / CLI / 门禁 / 状态平面 / 入站出站交付件 / 人工接入点）、任务台账与流转日志格式
  （task.yaml + flow.jsonl + ho-*.yaml 移交信封）、三条任务链、人工接入三级分类（H1 阻断决策 /
  H2 人工执行 / H3 复核确认）与通用红线、并发契约。任何拆分 agent 的通信契约以本页为准，
  各 SKILL.md 只引用不复制（避免双写漂移）。
---

# Agent Mesh — 多 Agent 协作总协议

> 一句话定位：知识库拆成多个独立 agent 协作后，**谁接什么任务、产出什么交付件、
> 什么门禁算成功、什么情况必须叫人、日志怎么留痕**，以本页为唯一契约源。
> 单 agent 场景不需要本页——直接按 [_task-routing](_task-routing.md) 执行即可。

## 一、协作原则（五条，全 agent 一致）

1. **LLM 负责推理，tool 负责事实**：门禁结论（G0-G12 / SV0-SV8 / check）只抄机器输出，
   agent 不得代填或升格——PARTIAL 不能说成 PASS，TIMEOUT 永远不是 PASS。
2. **无 refs 不流转**：任何跨 agent 移交必须带 refs（`fault-C-xxxx` / `QOHxxx` / `TSK-xxx`），
   收件方对无 refs 的移交直接退回（对齐 sdk-forge patch-import 的机器强制纪律）。
3. **单一真源，信封只存指针**：任务台账在 `workspace/tasks/`，知识真源在库内
   （`faults/_data/`、`knowledge/`、各知识页）、构建状态在各自状态平面
   （`.qt-ohos/`、`.qtsdk/`）；移交信封记录指针，不复制内容。
4. **只投草稿，不改真源**：业务 agent 的知识产出只能走 drafts
   （`faults/_drafts/draft-*.md` 或 `knowledge/drafts/`）；真源写入权限唯一归
   kb-iterator（主编门禁），与 faults 协作草稿模式同构。
5. **人工接入必留痕**：每一次停下等人的动作都写 flow.jsonl 的 `human-required` 事件
   （含 reason 与 options）；人的决策由后续事件自然记录。

## 二、Agent 接口卡

### 2.1 Roster（一览）

| # | Agent（skill 名） | 职责 | 执行平面 | 成功判据 | 状态平面 | 定义文件 |
|---|------|------|---------|---------|---------|---------|
| 1 | task-dispatcher | 任务台账、路由派单、流转日志、关单 | — | 台账完整、路由正确 | `workspace/tasks/` | [skills/task-dispatcher](../skills/task-dispatcher/SKILL.md) |
| 2 | port-assessor | 可行性评估与依赖闭包（**第 0 步**） | `portgraph/portgraph.py` | analyze 判定 + 闭包校验 | portgraph SQLite + 评估报告 | 本页 §2.2 + [portgraph/README](../portgraph/README.md) |
| 3 | app-porter（qt-app-porting） | 应用迁移端到端 | `tools/qt-ohos-run.py` | verify **G0-G12** | 目标项目 `.qt-ohos/` | [skills/qt-app-porting](../skills/qt-app-porting/SKILL.md) |
| 4 | sdk-forge（qt-sdk-forge）★已拆 | Qt SDK 编译/补丁/版本管理 | `tools/qt-sdk-run.py` | verify **SV0-SV8** | `workspace/qt-sdk/.qtsdk/` | [skills/qt-sdk-forge](../skills/qt-sdk-forge/SKILL.md) |
| 5 | framework-analyst | 框架问题四阶段分析 | 复用 porter CLI（demo/日志） | 证据门禁 `evidence_type` | 分析工作区 + 工单 | 本页 §2.2 + [framework-issue-analysis](../procedural/framework-issue-analysis.md) |
| 6 | test-verifier | 运行测试 / 修复回归 / 用例闭环 | 复用 porter CLI build/smoke | 用例全 pass / 回归通过 | 测试工作区 | 本页 §2.2 + [qt-ohos-run-test](../procedural/qt-ohos-run-test.md) |
| 7 | kb-iterator | 知识主编合入、索引再生、演进复核 | `tools/faults-build.py` 等 | check ERROR=0 + 主编六步 | `faults/_drafts/` + `knowledge/drafts/` | [skills/kb-iterator](../skills/kb-iterator/SKILL.md) |
| 8（可选） | demo-builder | 独立 demo 六步闭环 | — | 编译 + 运行验证 | demo 工程目录 | [demo-generation](../procedural/demo-generation.md) |
| 9（可选） | bug-reporter | 上游 bug report form A/B | — | 可复现性 HARD 闸门 | 报告交付件 | [qt-bug-report-generation](../procedural/qt-bug-report-generation.md) |

可选 agent 未拆出前，能力分别内嵌在 app-porter（[Q] 路由）与 framework-analyst
（四阶段工作流的阶段四）。拆出时机：demo 直发需求高频 → 拆 8；对 Qt/华为提单频繁 → 拆 9。

### 2.2 无独立 SKILL.md 的三个 agent 接口卡

**port-assessor**（portgraph agent）

- 触发：任何"移植/迁移/评估可行性"任务的**第 0 步**（路由 [A]/[P] 前置；[M] 三方库咨询）
- 入站：`task-order`（app 路径）
- 出站：`assessment.json` + deps-report + fetch-deps 闭包 manifest（type=`assessment` / `deps-manifest`）
- 边界：只分析不改动目标工程；**依赖 ≥3 个三方库时禁止人工逐个判断**，以闭包分析输出为准
  （tdesktop 实证：68 依赖闭包分析一次给出 59 bottle + 9 源码编译的解）

**framework-analyst**（框架问题分析 agent）

- 触发：porter 的 `analyze-log` 未命中已知模式且疑似框架层问题；用户直报"应用行为异常要定位
  根因"（[E]/[F]/[G] 深挖、[R] 新根因）
- 入站：`task-order` + 日志 / demo 线索
- 出站：修改方案工单（`proposal.yaml` + `patches/` + `notes.md`，投 `.qtsdk/inbox/`，
  type=`proposal`）；faults C 草稿（投 `faults/_drafts/`，type=`kb-draft`）；上游报告草稿
- 边界：不重编 Qt（forge 的事）、不迁移应用（porter 的事）；demo 硬性要求：
  **单文件 main.cpp + 复现步骤编号到操作级**（无步骤视为未完成）

**test-verifier**（测试验证 agent）

- 触发：porter 的 build/smoke 之后需要运行测试；forge 出新版本后的修复回归（faults review
  联动）；应用功能用例闭环（[qt-app-harmonyos-completion](../procedural/qt-app-harmonyos-completion.md)）
- 入站：`sdk-release` + 验证清单（C 页复现步骤 / 用例集）
- 出站：验证结论（C 页"版本验证记录"行，type=`test-verdict`）
- 边界：只测不修——修复动作回到 porter / analyst / forge

> 这三个 agent 拆独立实例时：复制本页接口卡 + 对应知识页要点为各自 SKILL.md，
> 并在 roster 表回填定义文件链接。

### 2.3 交付件矩阵

| from → to | type | 载体（格式） | 状态 |
|-----------|------|-------------|------|
| dispatcher → 首个 agent | `task-order` | ho 信封 + 路由码 | 新增 |
| port-assessor → dispatcher/porter | `assessment` | `assessment.json` + deps-report.md | ✅ portgraph 已有 |
| port-assessor → porter | `deps-manifest` | fetch-deps manifest + 源码缺口清单 | ✅ 已有 |
| framework-analyst → sdk-forge | `proposal` | `proposal.yaml` + `patches/` + `notes.md`（inbox 协议） | ✅ 已有 |
| sdk-forge → porter/verifier | `sdk-release` | `manifest-<ver>.yaml` + ENV 指针 | ✅ 已有 |
| test-verifier → analyst/forge | `test-verdict` | C 页"版本验证记录"行 | ✅ 已有 |
| 任意 → kb-iterator | `kb-draft` | `faults/_drafts/draft-*.md` 或 QOH/R 草稿 | ✅ 已有 |
| 业务 agent → dispatcher | `task-report` | qt-ohos-run report / 各自报告 | ✅ 已有 |
| dispatcher → kb-iterator | 关单移交 | flow.jsonl 全文 + 草稿清单 | 新增 |

## 三、任务台账与流转日志

`workspace/tasks/`（gitignored 运行时状态，首次由 task-dispatcher 创建）：

```
workspace/tasks/
└── TSK-YYYYMMDD-NNN/
    ├── task.yaml          # 台账：dispatcher 建/维护
    ├── flow.jsonl         # 流转日志：追加式，谁执行谁写
    ├── handoffs/
    │   └── ho-NNN.yaml    # 移交信封（每次跨 agent 交付一个）
    └── reports/           # 面向用户的任务报告（可选）
```

### task.yaml（台账）

```yaml
id: TSK-20260923-001
title: tdesktop v7.0.2 鸿蒙化迁移
status: in-progress      # created | in-progress | waiting-human | blocked | closed
created: 2026-09-23
route: "[A]+[P]"         # 命中的 _task-routing 路由码
agents: [port-assessor, app-porter, framework-analyst, sdk-forge, test-verifier]
handoffs: [TSK-20260923-001/handoffs/ho-001.yaml]
deliverables: []         # 关键交付件指针（各状态平面路径，不复制内容）
kb_distilled: []         # 关单时 kb-iterator 回填：C-xxxx / QOHxxx / episodic 页 id
```

### flow.jsonl（流转日志）

每行一条 JSON，**追加不可改写**。事件枚举与七类固定写点：

| event | 写点 | 必带字段 |
|-------|------|---------|
| `task-created` | dispatcher 建档 | task |
| `handoff-in` / `handoff-out` | 接单 / 移交 | to / from + artifact + refs |
| `gate` | 机器门禁判定 | gate + verdict（只抄机器输出） |
| `anomaly` | 异常、未预期行为 | reason |
| `budget-exhausted` | 任务预算耗尽（checkpoint 已写） | budget |
| `human-required` | **人工接入**（见 §五） | reason + options |
| `draft-produced` | 产生知识草稿 | artifact + refs |
| `task-closed` | 关单 | distilled |

示例：

```jsonl
{"ts":"2026-09-23T10:05:00+08:00","agent":"port-assessor","event":"gate","gate":"analyze","verdict":"portable","artifact":"assessment.json","refs":["TSK-20260923-001"]}
{"ts":"2026-09-23T13:10:00+08:00","agent":"framework-analyst","event":"handoff-out","to":"sdk-forge","artifact":"handoffs/ho-001.yaml","refs":["C-0003","QOH012"]}
{"ts":"2026-09-23T13:30:00+08:00","agent":"app-porter","event":"human-required","reason":"签名证书与密码（H2）","options":["提供证书路径","跳过装机止步 G5"],"refs":["TSK-20260923-001"]}
```

### ho-NNN.yaml（移交信封，泛化自 sdk-forge 的 inbox 协议）

```yaml
id: ho-001
task: TSK-20260923-001
from: framework-analyst
to: sdk-forge
type: proposal      # task-order | assessment | deps-manifest | proposal | sdk-release | test-verdict | task-report | kb-draft
artifact: workspace/qt-sdk/.qtsdk/inbox/prop-20260923-001/proposal.yaml
refs: [fault-C-0003, QOH012, TSK-20260923-001]
verdict: null       # pass | fail | partial（机器门禁结论，有则必填）
next: sdk-forge.forge
```

## 四、任务流转（三条链）

**移植链**（主链）：
dispatcher 建档 → port-assessor 第 0 步（**blocked 即止出报告**，H1 裁决）→ app-porter
（壳工程 + 适配 + 受追踪修改；build 失败先 `analyze-log`，命中已知自修）→ 未命中且疑似框架
问题 → framework-analyst（复现 demo → 根因 → 定性）→ 需重编验证 → sdk-forge（proposal →
SV 门禁 → test 版）→ test-verifier 回归 → app-porter 复验 → G0-G12 PASS → task-report +
草稿 → dispatcher 关单移交 kb-iterator。

**问题链**：用户现象 → dispatcher → framework-analyst（四阶段）→ C 草稿 + 上游单材料 →
kb-iterator 主编门禁 promote（需要重编验证走 sdk-forge，验证走 test-verifier）。

**演进链**（定期）：sdk-forge `upstream-check` 演进报告 → kb-iterator（`faults review`
到期复核 → 版本基准表 bump → 补丁 superseded 处置需 forge 出新版）。

## 五、人工接入点（HITL）

### 分级定义

| 级别 | 含义 | agent 行为 |
|------|------|-----------|
| **H1 阻断决策** | 必须停下等人裁决才能继续 | 写 `human-required` 日志；task.status → `waiting-human`；呈报选项 |
| **H2 人工执行** | agent 无法代做的物理/环境操作 | 说明所需动作，等人完成后登记结果继续 |
| **H3 复核确认** | agent 可先产出，产物经人确认才能进入下一跳 | 产出 + 复核要点一并呈报；未确认不流转 |

### 各 agent 人工接入点

**task-dispatcher**

| 级别 | 触发条件 |
|------|---------|
| H3 | 模糊请求无法唯一路由：给 3 个最可能选项让用户选（沿用 _task-routing 模糊请求纪律） |
| H1 | port-assessor 判 blocked 后的裁决：放弃 / 降级范围 / 投入源码移植 |
| H1 | `budget-exhausted` 后是否续跑（checkpoint 已写） |
| H1 | 资源冲突（同一 forge home 并发）：改独立 home 还是排队 |

**port-assessor**

| 级别 | 触发条件 |
|------|---------|
| H1 | analyze=blocked：blockers 研判（硬阻塞 vs 可裁剪分支）结论 + 选项交用户裁决 |
| H1 | unknowns 源码编译缺口：工作量逐项告知，用户确认接受后才进 porter |
| H3 | 版本要求 conflict / 跨名约束不可比：人工确认 |

**app-porter**

| 级别 | 触发条件 |
|------|---------|
| H2 | 签名证书与密码：人不离机提供，不落盘不代管 |
| H3 | 非白名单修改（尤其 `Q_OS_LINUX` 守卫类——鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`）：人工评审后才 patch |
| H1 | verify=FAIL 且错误未命中已知模式：是否转 framework-analyst 走问题链 |
| H2 | 一键模式 `project_generation`（壳工程创建）暂停并给指引 |

**sdk-forge**

| 级别 | 触发条件 |
|------|---------|
| H2 | Qt 6.12 预构建安装器（需登录交互安装，agent 不代下载）：提示用户手动安装后 `config set` 登记 |
| H2 | 商业源码 clone 凭据：用户提供，只进内存不落盘 |
| H1 | 正式版发布（`--type release`，ENV 指针切换影响全部下游） |
| H1 | diagnostic 补丁被 release 门禁拒绝后的处置：revert / 改出 test 版 |
| H1 | superseded 复核通过后的补丁退役 + 出无该补丁的新版本 |
| H2 | SV7 冒烟的人工验证结果（`smoke-mark` 登记的是人为结论） |
| H1 | 上游 patch 提交（本 skill 不代办；`patch-export` 后由人提交） |

**framework-analyst**

| 级别 | 触发条件 |
|------|---------|
| H3 | 定性与归层（nature / responsible）：人工核验后才建 C 草稿（终审在 kb-iterator 主编门禁） |
| H1 | 修改方案工单（proposal）发出前：人工评审方案 |
| H1 | 上游 issue 提交：qt-bug report form A/B 生成后由人提交，agent 不代提 |
| H2 | 偶发/特定环境问题：用户提供触发场景、硬件、账号 |
| H3 | 日志与 demo 材料脱敏（公开化前） |

**test-verifier**

| 级别 | 触发条件 |
|------|---------|
| H2 | 真机 UI 行为人工验证（framework-fix-verification 的"人工手动验证"环节；smoke 只查崩溃窗口，行为观察需人） |
| H3 | AI 生成的测试用例须人工 review 后才执行（对齐 qt-app-harmonyos-completion"AI 扫源码 + 人工 review"） |
| H3 | 验证结论登记进 C 页"版本验证记录"前人工确认 |

**kb-iterator**（人工接入最密集的 agent）

| 级别 | 触发条件 |
|------|---------|
| H3 | 主编门禁第 3 步**人工核验**（硬性）：证据链 / 定性 / 归层 / severity 校准 / 版本单号事实（宁缺勿造）/ 脱敏 |
| H1 | promote（删草稿、写入真源）与 rejected / returned 裁决 |
| H1 | 定性改判（undetermined → defect / limitation，CID 不变） |
| H1 | 版本基准表 bump（AGENTS.md / CLAUDE.md 尾表） |
| H2 | 复现 demo 必测中需要真机人工观察的场景 |

**demo-builder（可选）**：H2 真机看效果；
**bug-reporter（可选）**：H1 提交动作一律人工（可复现性 HARD 闸门自检通过后）。

### 通用红线（全 agent 一致，优先级最高）

1. **凭据 / 账号 / 付费 / 对外提交**（QTBUG、华为 issue、伙伴交付件）→ 一律人工；agent 只准备材料。
2. **正式发布、删除 / 回滚**（promote 删草稿、patch revert）、**ENV 指针切换** → 人工确认后执行。
3. **门禁语义不得升格**：PARTIAL ≠ PASS、TIMEOUT ≠ PASS、SV7 SKIP 只能报"编译级可用"。
4. **无证据不定性**（证据门禁 `evidence_type`）；公开化内容（`audience: public`）脱敏人工把关。
5. 每次人工接入写 `human-required` 留痕；人决策后由接续事件（gate / handoff-out）自然记录结果。

## 六、并发契约

- 沿用 `.qtsdk/` 已验证契约：**文件锁**（`<file>.lock`）+ **原子替换**（tmp + `os.replace`）。
- `flow.jsonl` 追加写（行级 append）天然并发安全；`task.yaml` / `ho-*.yaml` 修改走锁。
- 同一 forge home 同时只跑一个 forge 进程；并行用独立 home（`QT_SDK_HOME` / `--home`）。
- `workspace/` 整体 gitignored——任务台账是运行时状态，沉淀物走 drafts 进库。

## 七、与知识库平面的关系

| 平面 | 载体 | 本协议的增量 |
|------|------|-------------|
| Task Router | `_index/_task-routing.md` | dispatcher 的路由核心（无增量） |
| Knowledge | `semantic/` `procedural/` `episodic/` `problems/` `faults/` | 无增量 |
| Execution | `tools/qt-ohos-run.py` `tools/qt-sdk-run.py` `portgraph/` | 无增量（CLI 不改） |
| State | `.qt-ohos/` `.qtsdk/` | 无增量 |
| Verification | G0-G12 / SV0-SV8 / faults check | 无增量 |
| Learning | `knowledge/drafts/` `faults/_drafts/` | 无增量 |
| **Task Ledger（新增）** | `workspace/tasks/` | task.yaml + flow.jsonl + ho 信封；dispatcher 建档、各 agent 追写、kb-iterator 消费 |

## 八、落地状态（2026-09-23）

- [x] `_index/_agent-mesh.md`（本页）：契约单一真源
- [x] `skills/task-dispatcher/SKILL.md`、`skills/kb-iterator/SKILL.md`：两个新 agent 的定义
- [x] `qt-app-porting` / `qt-sdk-forge` SKILL.md：补接口与人工接入节
- [x] AGENTS.md 技能表注册；_task-routing.md 挂接指针
- [x] **内部调度平台接入（冒烟验证通过）**：7 个 agent 注册到内部 Multica 平台并建立
  "应用鸿蒙化" squad（队长 task-dispatcher + 6 队员）。issue 可直接派给小队，队长被唤醒后
  按移植链建 **stage 子任务**编排（同 stage 全部完成才唤醒队长——stage 屏障语义原生映射
  §四 移植链）：stage1 评估（port-assessor）→ stage2 迁移（app-porter）→ stage3 验证
  （test-verifier）；条件支线（framework-analyst → sdk-forge → 回归）；收尾 stage
  知识蒸馏（kb-iterator）。squad 级 instructions 已写入同一协作约定。
  （平台 / runtime / agent / squad 的具体 ID 属内部部署信息，不入库）
- [ ] port-assessor / framework-analyst / test-verifier 拆独立实例时，从 §2.2 接口卡生成各自 SKILL.md
- [ ] 可选 demo-builder / bug-reporter 未拆（能力内嵌，见 §2.1）
