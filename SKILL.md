---
name: ohos-qt-skills
description: |
  Qt 应用 HarmonyOS 迁移工程仓的总入口：把"能不能迁、怎么迁、迁完算不算成功"变成可判定的流程。
  当用户要求把 Qt/C++ 应用迁移、移植或鸿蒙化到 HarmonyOS/OpenHarmony；评估某个 Qt 应用或
  三方依赖在鸿蒙上的可行性；排查 Qt 鸿蒙的编译、打包、签名、部署、运行（dlopen/崩溃/白屏）问题；
  查询 Qt API / Qt 模块 / 平台限制在鸿蒙的支持情况；判断一个问题是 Qt 框架缺陷、鸿蒙规格限制
  还是应用使用问题；编译或维护本地 Qt OHOS SDK；或需要把这些过程沉淀回知识库时，使用本 skill。
  核心能力：① 可行性三态判定（portable/blocked/uncertain）与依赖角色分析、依赖闭包下载；
  ② 自动迁移流水线（扫描→计划→受追踪修改→编译→打 HAP→装机→启动→G0-G12 门禁）；
  ③ 知识层（35 条黄金铁律、42 条 QOH 错误模式机器诊断、47 个实战踩坑、症状→根因→临时方案故障图）；
  ④ SDK 工程平面（编译、补丁溯源、SV0-SV8 发版门禁）。
  触发词：鸿蒙化、移植 Qt、porting、HarmonyOS、Qt OHOS、QtOhosExtras、三方依赖、交叉编译、
  bottle、HAP、hvigor、devecocli、dlopen、白屏、闪退、构建报错、QOH。
metadata:
  author: OpenHarmony PC Developer · ohos_qt-skills maintainers
  category: software-development
  version: 3.0.0
---

# ohos-qt-skills：Qt 应用鸿蒙化工程入口

本 skill 是仓库的总入口，另外 5 个子 skill 各自负责一段流水线（见末节"技能分工"）。
**所有命令都在仓库根目录执行**；知识页里出现的路径变量（如 `QT5_15_OHOS_SDK`、
`OHOS_SDK_NATIVE`）均由 `ENV.local.md` 提供，不要在回答里硬编码本机路径。

铁律：**LLM 负责推理，tool 负责事实。** 迁移是否成功只看 `qt-ohos-run.py verify` 的
G0–G12 门禁结论（SDK 侧是 SV0–SV8）；`TIMEOUT`、`启动后 3 秒内未崩溃`、"看起来编译过了"
都不是 PASS。

## Instructions

1. **判断任务属于哪一条路径**。先读 `_index/_task-routing.md` 的路由表（15 类任务，A–S），
   确定任务类型；不要凭印象直接开干。若无 `ENV.local.md` 且任务需要本地工具链，先执行
   `skills/kb-init/SKILL.md` 完成环境初始化。

2. **先做可行性评估，再谈迁移**。接到"迁移/移植/鸿蒙化某应用"的请求，第 0 步必须跑
   `python portgraph/portgraph.py analyze <app>`，得到 `portable` / `blocked` / `uncertain`
   三态结论；再跑 `deps` 看依赖角色与版本范围，必要时 `fetch-deps --dry-run` 预览闭包。
   依赖 ≥3 个三方库时**禁止**人工逐个判断可行性，一律以闭包输出为准。

3. **把结论讲成用户能决策的话**。`blocked` 要给出具体阻断项与守卫证据（无条件的
   `ohos-active` 命中且在核心路径才算硬阻塞，可选分支可放行）；`uncertain` 要把
   "无 bottle、需源码交叉编译"的缺口逐项列出，不要笼统说"有风险"。

4. **要动手迁移就走执行层**：`python tools/qt-ohos-run.py scan → plan → patch → build →
   package → install → launch → smoke → verify`。每一步都在目标项目的 `.qt-ohos/` 落状态，
   中断后可用 `status` / `resume` 续跑；不要靠对话记忆维持进度。

5. **只做白名单内的自动修改**。所有自动改动都进 `.qt-ohos/changes.json` 与 patches 目录；
   禁止盲目扩写 `Q_OS_LINUX` 守卫（鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`），禁止为了让
   编译过而注释掉功能代码。需要人工判断的改动写进迁移计划的 assisted/manual 段。

6. **报错先机器匹配，再读知识页**。执行 `python tools/qt-ohos-run.py analyze-log <日志>`，
   命中的 42 条 QOH 错误模式会带出知识页引用；按引用读 `problems/` 或
   `semantic/qt-harmonyos-golden-rules.md`（35 条黄金铁律，先扫一遍再改代码）。

7. **判定"这个问题归谁"要查故障图，不要猜**。查 `faults/_registry.md` 的症状索引或
   `faults/_graph.yaml`：C 页写明定性（defect 会修 / limitation 规格限制→替代方案）、
   责任领域、临时方案与跟踪单状态。要给上游提单时，必须有 demo 或日志+栈级证据。

8. **工具不可用就停下报告，不要假装成功**。构建/装机/签名前先确认 `devecocli`、`hdc`、
   Qt OHOS SDK 可用（`devecocli` 定位顺序：`ENV.local.md` 的 `DEVECO_CLI` → PATH →
   npm 全局 → DevEco 捆绑；它**不一定**随 DevEco Studio 安装）。缺失时输出安装命令并停止。

9. **需要重编 Qt 或给 Qt 打补丁时切换到 SDK 平面**：`tools/qt-sdk-run.py`（`patch-import`
   → `patch-apply` → `build` → `install` → `verify` → `release`）。所有补丁必须可溯源
   （manifest 记录来源与适用版本），临时测试版本走 `release --temp`，不要手工改 SDK 目录。

10. **收尾必须给机器结论**：交付时给出 `verify` 的门禁结果（PASS/PARTIAL/FAIL + 失败项
    编号），而不是"应该可以了"。部分通过就明确列出未过的门禁与原因。

11. **沉淀是流程的一部分，不是可选项**。新踩的坑先进 `faults/_drafts/`（附复现 demo 或
    日志+栈），再走 `skills/kb-iterator/SKILL.md` 的主编门禁合入；改了 `faults/_data/`
    或 C 页后必须跑 `python tools/faults-build.py build` 重建派生物，并保证 `check` 零 ERROR。

12. **改完仓库自己先过门禁**：`bash _scripts/verify.sh`（契约/结构/引用/卫生）与
    `python -m unittest discover -s tests`（一致性/引擎/扫描）。文档里写的数字受测试约束，
    数量变化时要同步更新 README、SKILL.md、AGENTS.md 与 `_index/` 下的索引页。

## 成功判据

| 场景 | 唯一判据 | 常见误判 |
|------|---------|---------|
| 应用迁移 | `qt-ohos-run.py verify` 的 G0–G12 全过 | "编译通过"、"装上去了" |
| SDK 构建 | `qt-sdk-run.py verify` 的 SV0–SV8 全过 | "install 完成" |
| 故障定性 | C 页有证据类型（demo / 日志+栈 / 静态可判定）+ 闭环无缺口 | 凭现象猜根因 |
| 知识库健康 | `verify.sh` PASS 且 `faults-build check` 零 ERROR | 页面能打开 |

## 禁止事项

- 禁止在未跑 `analyze` 的情况下承诺"这个应用可以迁移"。
- 禁止把 `TIMEOUT`、超时重试成功、日志无输出当作通过。
- 禁止为了通过门禁而改门禁判据、删测试、注释功能代码。
- 禁止把内部路径、凭据、真实姓名写进知识页（`verify.sh` 会拦本机绝对路径）。
- 禁止绕过 `kb-iterator` 直接改知识真源（多人各写一份会让事实分叉）。

## 技能分工

| 场景 | Skill |
|------|-------|
| 环境初始化 | `skills/kb-init/SKILL.md` |
| 应用迁移主流水线 | `skills/qt-app-porting/SKILL.md` |
| Qt SDK 编译与补丁 | `skills/qt-sdk-forge/SKILL.md` |
| 社区版 → 官方版（QtOhosExtras）迁移 | `skills/qt-community-to-official/SKILL.md` |
| 多 Agent 任务调度 | `skills/task-dispatcher/SKILL.md` |
| 知识沉淀与索引再生 | `skills/kb-iterator/SKILL.md` |
| 可行性图谱（仓库工具） | `portgraph/README.md` |

## 参考入口

- 仓库总览与架构：[README.md](README.md)
- Agent 行为契约与执行纪律：[AGENTS.md](AGENTS.md)
- 任务路由（15 类）：[_index/_task-routing.md](_index/_task-routing.md)
- 知识地图：[_index/_map.md](_index/_map.md) ｜ 仪表盘：[_index/_dashboard.md](_index/_dashboard.md)
- 错误速查：`problems/_lookup.md` ｜ 故障总表：`faults/_registry.md`
