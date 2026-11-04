---
name: ohos-qt-skills
description: |
  Qt 应用 HarmonyOS 迁移工程仓的总入口：把"能不能迁、怎么迁、迁完算不算成功"变成可判定的流程。
  当用户要求把 Qt/C++ 应用迁移、移植或鸿蒙化到 HarmonyOS/OpenHarmony；评估某个 Qt 应用或三方依赖
  在鸿蒙上的可行性；分析依赖角色并下载鸿蒙 arm64 预编译产物（bottle）；排查 Qt 鸿蒙的编译、打包、
  签名、部署、运行（dlopen/崩溃/白屏）问题；查询 Qt API / Qt 模块 / 平台限制在鸿蒙的支持情况；
  判断一个问题是 Qt 框架缺陷、鸿蒙规格限制还是应用使用问题；编译或维护本地 Qt OHOS SDK；
  或需要把这些过程沉淀回知识库时，使用本 skill。
  核心能力：① 可行性三态判定（portable/blocked/uncertain）+ 依赖角色分类（link/build-tool/
  runtime/test/vendored/env）+ 应用级依赖闭包下载与交叉编译集成片段；② 自动迁移流水线（扫描→
  计划→受追踪修改→编译→打 HAP→装机→启动→G0-G12 门禁，可 checkpoint/resume）；③ 知识层
  （38 条黄金铁律、43 条 QOH 错误模式机器诊断、56 个实战踩坑、S→C→W→T 故障图）；④ SDK 工程平面
  （编译、补丁溯源、SV0-SV8 发版门禁）。目标平台：HarmonyOS/OpenHarmony arm64。
  触发词：鸿蒙化、移植 Qt、porting、HarmonyOS、Qt OHOS、QtOhosExtras、三方依赖、交叉编译、
  bottle、HAP、hvigor、devecocli、hdc、dlopen、白屏、闪退、构建报错、QOH。
metadata:
  author: OpenHarmony PC Developer · ohos_qt-skills maintainers
  category: software-development
  version: 2.3.0
---

# ohos-qt-skills：Qt 应用鸿蒙化工程入口

本 skill 是本仓的总入口，另外 5 个子 skill 各管一段流水线（见 §G）。
**以下所有命令都在仓库根目录执行**；知识页里出现的路径变量（`QT5_15_OHOS_SDK`、
`OHOS_SDK_NATIVE` 等）都由 `ENV.local.md` 提供，不要在回答里硬编码本机路径。

判断标准只有一条：**LLM 负责推理，tool 负责事实。** 迁移是否成功只看 `qt-ohos-run.py verify`
的 G0–G12 门禁（SDK 侧是 SV0–SV8）；"编译过了"、"装上去了"、`TIMEOUT`、"启动后 3 秒没崩"
都不是 PASS。

知识层里有两样东西每次任务都值得先扫：**38 条黄金铁律**（已知陷阱，改代码前过一遍）和
**43 条 QOH 错误模式**（`analyze-log` 机器匹配，命中即带根因与知识页引用）。

## 触发场景

- 把某个 Qt 项目**迁移 / 移植 / 鸿蒙化**到 HarmonyOS（评估或执行）
- 分析 Qt 项目的**三方依赖**，或下载鸿蒙 arm64 **交叉编译产物 / bottle**
- Qt 鸿蒙**编译 / 打包 / 签名 / 部署 / 运行报错**排查
- 查询 Qt **API / 模块 / 平台限制**在鸿蒙的支持情况
- 查某问题**修没修 / 归谁 / 怎么绕**（故障图）
- 编译、打补丁、维护本地 **Qt OHOS SDK**

---

## 使用前提

首次使用或 `ENV.local.md` 不存在时，先执行 `skills/kb-init/SKILL.md` 完成环境初始化
（DevEco Studio / HarmonyOS SDK / Qt OHOS SDK / 工具链检测、安装引导、路径配置、验证）。
知识页里的路径变量（如 `QT5_15_OHOS_SDK`、`OHOS_SDK_NATIVE`）都定义在 `ENV.local.md`。

纯查询类任务（读知识页、查 API 支持情况）不需要初始化，也不需要本地工具链。

## Instructions

1. **先判定任务属于哪条路径**。读 `_index/_task-routing.md` 的路由表（15 类任务 A–S），
   不要凭印象直接开干。纯查询类任务不需要本地工具链；要动构建/装机/签名，先按 §使用前提
   确认 `ENV.local.md` 与工具可用性。

2. **任何"迁移/移植/鸿蒙化/可行性评估"请求，第 0 步必须是可行性评估**（§A）。跑
   `portgraph analyze` 拿 `portable` / `blocked` / `uncertain` 三态结论，再跑 `deps` 看
   依赖角色与版本范围，必要时 `fetch-deps --dry-run` 预览闭包。**依赖 ≥3 个三方库时禁止
   人工逐个判断可行性**，一律以闭包输出为准。

3. **把结论讲成用户能决策的话**。`blocked` 要给出具体阻断项与守卫证据（无条件的
   `ohos-active` 命中且在核心路径才算硬阻塞，可选分支可放行）；`uncertain` 要把
   "无 bottle、需源码交叉编译"的缺口**逐项列出**，不要笼统说"有风险"。

4. **要动手迁移就走执行层**（§B）：`scan → plan → patch → config → build → package →
   install → launch → smoke → verify`。每步都在目标项目的 `.qt-ohos/` 落状态，
   中断用 `status` / `resume` 续跑，**不要靠对话记忆维持进度**。

5. **只做白名单内的自动修改**。所有自动改动进 `.qt-ohos/changes.json` 与 patches 目录，
   可回滚可评审；禁止盲目扩写 `Q_OS_LINUX` 守卫（鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`），
   禁止为了让编译过而注释功能代码。需要人判断的改动写进迁移计划的 assisted/manual 段。

6. **报错先机器匹配，再读知识页**（§B）。执行
   `python tools/qt-ohos-run.py analyze-log <日志>`，命中的 43 条 QOH 模式会带出根因与
   知识页引用；按引用读 `problems/`，或先扫 `semantic/qt-harmonyos-golden-rules.md`
   的 38 条黄金铁律。大型 C++ 工程编译前先跑 `cpp20-gap-scan`，别逐轮撞错。

7. **判定"这个问题归谁"要查故障图，不要猜**（§D）。查 `faults/_registry.md` 症状索引或
   `faults/_graph.yaml`：C 页写明定性（defect 会修 / limitation 规格限制→替代方案）、
   责任领域、临时方案与在跟单状态。要给上游提单，必须有 demo 或日志+栈级证据。

8. **工具不可用就停下报告，不要假装成功**（§F-7）。构建/装机/签名/取日志前先验证
   `devecocli`、`hdc`、Qt kit 可用；`devecocli` 定位顺序：`ENV.local.md` 的 `DEVECO_CLI`
   → PATH → npm 全局 → DevEco 捆绑（**它不一定随 DevEco Studio 安装**）。缺失就输出安装
   命令并停止，禁止用猜测路径继续。

9. **需要重编 Qt 或给 Qt 打补丁时切到 SDK 平面**：`tools/qt-sdk-run.py`
   （`patch-import` → `patch-apply` → `build` → `install` → `verify` → `release`）。
   补丁必须可溯源（manifest 记录来源与适用版本），临时测试版本走 `release --temp`，
   不要手工改 SDK 目录。

10. **收尾必须给机器结论**（§E）。交付时给 `verify` 的门禁结果（PASS/PARTIAL/FAIL +
    失败项编号），而不是"应该可以了"；部分通过就明确列出未过的门禁与原因。

11. **沉淀是流程的一部分，不是可选项**。新坑先进 `faults/_drafts/`（附复现 demo 或
    日志+栈），再走 `skills/kb-iterator/SKILL.md` 的主编门禁合入；改了 `faults/_data/`
    或 C 页必须 `python tools/faults-build.py build` 重建派生物，`check` 零 ERROR，
    `review` 扫到期与未闭环项。

12. **改完仓库自己先过用例**：`python -m unittest discover -s tests`（一致性/引擎/扫描）
    与 `python tools/faults-build.py check`。文档里的数字受一致性用例约束，数量变化时同步
    更新 `README.md`、`SKILL.md`、`AGENTS.md` 与 `_index/` 下的索引页。

---

## A. 可行性评估与依赖闭包（portgraph，强制第 0 步）

```bash
# 首次使用：构建图数据（自动拉取 Harmonybrew 4741 formula + cmd-pkgs 1248
# 预编译包数据源，一次性，需联网）
python portgraph/portgraph.py ingest all

python portgraph/portgraph.py scan <本地工程路径>         # 或 clone <git-url>
python portgraph/portgraph.py analyze <app> --summary     # 可移植性判定
python portgraph/portgraph.py deps <app或路径>            # 依赖角色分析（见 §C）
python portgraph/portgraph.py fetch-deps <app> --dry-run  # 依赖闭包预览
```

判定结论：

- `portable` — 可直接鸿蒙化（无硬阻塞，依赖有预编译产物或可随工程交叉编译）；
- `blocked` — 存在硬阻塞：不支持的平台接口 / Qt 模块 / 必选依赖；
- `uncertain` — 有未知依赖，即需要源码交叉编译的缺口。

**纪律**：

- 依赖 ≥3 个三方库时**禁止**人工逐个判断可行性，以闭包分析输出为准；
- `unknowns`（无 bottle 的依赖）必须**逐项明确告知用户**——这是源码交叉编译的缺口清单；
- blocked 结论需研判 blockers 的守卫证据（无条件 `ohos-active` 命中且在核心路径才算硬阻塞，
  可选分支可放行）。

详见 `portgraph/README.md`、`portgraph/docs/deps-report.md`、`portgraph/docs/fetch-deps.md`。

**大仓库获取韧性**：`clone` 在弱网下大 pack 易被掐断（`curl 56` early EOF）——重试 2-3 次
仍失败就改 **codeload tarball 断点续传**（GitHub：`https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>`，
或 `.../tar.gz/<tag|sha>`），解压到 portgraph workspace 后 `scan` 入库照常。

## B. 迁移流水线全量命令

```bash
python tools/qt-ohos-run.py scan <项目目录>   # 预扫描 + 19 条规则风险报告
python tools/qt-ohos-run.py plan              # 迁移计划（auto/assisted/manual）
python tools/qt-ohos-run.py patch             # 白名单自动修复（受追踪）
python tools/qt-ohos-run.py config set qt_sdk_prefix <Qt OHOS SDK 路径>
python tools/qt-ohos-run.py build             # G3 编译
python tools/qt-ohos-run.py package           # G5 打 HAP
python tools/qt-ohos-run.py install           # G6 hdc 装机
python tools/qt-ohos-run.py launch            # G7 启动
python tools/qt-ohos-run.py smoke             # G8 崩溃窗口检查（install/launch 未过则 SKIP，不判 PASS）
python tools/qt-ohos-run.py verify            # G0-G12 门禁（唯一成功判据）
python tools/qt-ohos-run.py libcheck <lib> --level built|probed --evidence "..."
                                              # 库级进展：built=能编能链，probed=设备上调通
```

**平台层移植预检**（分层移植时先跑，比链接期报错早得多）：

```bash
python tools/ohos-platform-audit.py <app>/SourceFiles/platform
#   头分发文件必须同时命名 Q_OS_OHOS 与 Q_OS_HARMONY；退出码非 0 即拦下
python tools/ohos-platform-audit.py <platform-dir> --undefined link.log
#   把链接日志里"没有任何 ohos/ 实现提到过"的符号列出来
```

一键模式：`migrate <项目目录>`（自动串联，遇到需人工的壳工程生成会暂停并给指引，
模板见 `templates/qt-ohos-app/`）；跨会话恢复：`status` / `resume --run`。

**C++20 缺口预检（大型 C++ 工程编译前）**：OHOS clang15/libc++15 缺若干 C++20 特性，
编译期逐轮撞错代价高。先扫后编：

```bash
python tools/cpp20-gap-scan.py scan <src>          # 8 规则缺口报告
python tools/cpp20-gap-scan.py fix <src> --apply   # 机械项自动修复
```

（规则对齐 `problems/build-clang15-libcpp15-cpp20-gaps.md`）

**构建失败立刻机器诊断**（43 条 QOH 错误模式，命中条目带根因、诊断步骤与知识页引用）：

```bash
python tools/qt-ohos-run.py analyze-log <日志文件>
```

**收尾动作**：`finish` 出报告；遇到新问题用 `draft "<标题>"` 沉淀草稿、验证后
`promote QOHxxx` 转正；`recipes <项目>` 检索相似历史迁移案例（`episodic/` 相似度排序）。

## C. 依赖角色分析与预编译产物下载

### 依赖角色分析（deps）

```bash
python portgraph/portgraph.py deps <app或路径> [--json]
```

按角色回答"这个项目到底依赖什么"，每条依赖带 `文件:行号` 证据与版本范围校验
（satisfied / conflict）：

| 角色 | 含义 | 处置 |
|------|------|------|
| link | 需要编译产物（headers + libs） | 必须有鸿蒙交叉编译产物 |
| build-tool | 构建机工具（cmake/protoc…） | 不部署到设备 |
| runtime | 传递闭包 .so + dlopen | 设备侧缺了起不来，编译期无感知 |
| test | 仅测试用 | 可跳过 |
| vendored | 项目自带源码 | 随项目一起交叉编译 |
| env | CI 脚本声明的环境依赖 | 弱依赖 |

（另有 provided=Qt 模块提供、optional=默认 OFF 的选项守卫。）

### 下载鸿蒙预编译产物（fetch / fetch-deps）

```bash
# 单个/多个包（arm64-ohos bottle，含 include/ + lib/ + cmake 配置）
python portgraph/portgraph.py fetch "zlib,jsoncpp,openssl@3"

# 应用级依赖闭包一键下载（推荐，先 --dry-run 预览）
python portgraph/portgraph.py fetch-deps <app> --dry-run
python portgraph/portgraph.py fetch-deps <app>            # 下载 + manifest
```

`fetch-deps` 自动完成：查库取直链 → 下载 → sha256 校验 → 解压到 `workspace/ohos-libs/`
→ Windows/NTFS 补建 `.so` 符号链接 → 输出 CMake/qmake 集成片段。manifest 每项带 status
决策表（downloaded / already_local / covered / provided / cmd_only / need_port / test /
failed），只有 `need_port` / `failed` 需要转人工源码交叉编译。

### 交叉编译集成要点

- **CMake**：`-DCMAKE_PREFIX_PATH=<bottle路径> -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`（铁律）
- **qmake**：`LIBS += -L<bottle>/lib -lfoo`（`-l` 列表由 fetch 输出）
- `.so` 在 Windows 上只能链接不能运行；部署到 `entry/libs/arm64-v8a/` 才能上设备
- 运行时依赖必须递归拉全（fetch-deps 已处理），漏拉会在设备 `dlopen` 失败

## D. 知识检索入口

| 想做什么 | 入口 |
|----------|------|
| 任务路由（接到请求先看） | `_index/_task-routing.md` |
| 扫 38 条铁律避已知陷阱 | `semantic/qt-harmonyos-golden-rules.md` |
| 遇到报错（第一步） | `problems/_lookup.md`（或 `analyze-log` 机器匹配） |
| 某问题修了吗 / 归谁 / 怎么绕 | `faults/_registry.md` §症状索引 |
| API 替换 | `semantic/qt-harmonyos-api-mapping.md` + `qt-harmonyos-code-patterns.md` |
| 模块支持状态 | `semantic/qt-harmonyos-modules.md` |
| 平台限制 | `semantic/qt-harmonyos-platform-limits.md` |
| 知识全貌 | `_index/_map.md`（每页一句话摘要） |

固定加载链：`_task-routing → golden-rules → _map → 按需读页 → 沿 refs 深追`。

## E. 成功判据

| 场景 | 唯一判据 | 常见误判 |
|------|---------|---------|
| 应用迁移 | `qt-ohos-run.py verify` 的 G0–G12 全过（PASS） | "编译通过"、"装上去了" |
| 部分完成 | `PARTIAL`：编译/打包过但设备侧未验证，须逐项列出未过门禁 | 当成 PASS 报告 |
| SDK 构建 | `qt-sdk-run.py verify` 的 SV0–SV8 全过 | "install 完成" |
| 故障定性 | C 页有 `evidence_type`（demo / 日志+栈 / 静态可判定）+ 闭环无缺口 | 凭现象猜根因 |
| 知识库健康 | 一致性用例全绿 + `faults-build check` 零 ERROR | 页面能打开 |

**TIMEOUT 永远不是 PASS。** `FAIL` 必须报告失败 + 剩余问题（QOH 编号）。

## F. 纪律红线

1. **成功只由工具判定**：应用迁移看 `verify`（G0–G12），SDK 构建看 SV0–SV8；
   TIMEOUT 永远不是 PASS。
2. **禁止盲目扩写 `Q_OS_LINUX` 守卫**：鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`，
   `#ifdef Q_OS_LINUX` 分支在鸿蒙本来就会编译——此类修改必须人工评审
   （参考 `semantic/qt-harmonyos-api.md`）。
3. **每次自动修改都被追踪**：目标项目 `.qt-ohos/changes.json` + `patches/`，
   可回滚、可评审；禁止无追踪的手改。
4. **知识回流**：新问题走 `draft` → `promote`；修改故障库真源后必须跑
   `python tools/faults-build.py build` 重建派生物；草稿合入走主编门禁（复现 demo 必测 +
   人工核验）。
5. **依赖判断不靠人肉**：≥3 个三方库的可行性以 portgraph 闭包分析输出为准（§A）。
6. **证据标准**：定性 Qt 框架侧问题必须有复现 demo 或调试日志+栈（纯转述/猜测不受理）；
   提上游单的缺陷必须 demo/logs 级证据；Qt 侧复现逻辑集中在单个 `main.cpp` 并写编号复现步骤。
7. **工具可用性预检**：开始任何构建/装机/签名/取日志工作前，先定位并验证工具链
   （`devecocli --version`、`hdc version`、Qt kit 存在性）。`devecocli` 定位顺序：
   `ENV.local.md` 的 `DEVECO_CLI` → PATH → npm 全局 → DevEco 捆绑（详见
   `ohos-common-kb-public/procedural/deveco-cli-usage-rules.md` §工具可用性预检）。
   解析失败立即向用户报告缺什么与安装命令，禁止用猜测的路径继续。
8. **回合收尾纪律（操作级）**：非交互 CLI 会话（`opencode run` / `claude -p` 等）中
   **回合结束 = 会话退出，没有任何机制会唤醒你**。
   - **禁止"委派后台代理后收尾等待"**——主回合退出后子进程失去协调者，干完各自的活就
     地解散（两轮实测死因）。
   - 长任务（克隆/编译/子代理）必须**在当前回合内同步等待完成**，或改为顺序自己执行；
     确实要并行，只能用会话内阻塞式等待（shell 前台跑、`Wait-Process`）。
   - 流水线未到 `verify` 终态或明确的人工确认点，禁止输出总结并停止；确需中止时把状态
     落盘到 `.qt-ohos/` 并写明续跑方式。
9. **不写本机绝对路径与凭据**：知识页只用 `ENV.local.md` 的变量名。

## G. 子技能

| Skill | 用途 |
|-------|------|
| `skills/kb-init/SKILL.md` | 环境初始化（检测依赖、安装引导、生成 `ENV.local.md`） |
| `skills/qt-app-porting/SKILL.md` | 自动迁移详情（工作流 / 门禁语义 / 人工接入点） |
| `skills/qt-sdk-forge/SKILL.md` | Qt SDK 编译、补丁应用与版本管理（SV0–SV8 门禁） |
| `skills/task-dispatcher/SKILL.md` | 多 Agent 协作调度（任务台账 / 移交信封 / 流转日志） |
| `skills/kb-iterator/SKILL.md` | 知识库迭代（草稿合入门禁 / 索引再生 / 事实校验） |

多 Agent 协作契约（接口卡 / 移交信封 / 人工接入点分级）见 `_index/_agent-mesh.md`。

## H. 版本基线

- 文档版本：v2.3.0（变更记录见 [CHANGELOG.md](CHANGELOG.md)）
- Qt 框架校验基准：Qt 5.15.16（tqtc/harmonyos-5.15.16）/ Qt 5.12.12
  （tqtc/harmonyos-5.12.12），详见 [AGENTS.md](AGENTS.md) 尾表
- 环境变量清单：`ENV.md`；真实值写 `ENV.local.md`（不入库）

## I. 参考入口

- 仓库总览、架构与能力：[README.md](README.md)
- 环境依赖与首次配置：[SETUP.md](SETUP.md)
- Agent 行为契约与执行纪律：[AGENTS.md](AGENTS.md)
- 任务路由（15 类）：[_index/_task-routing.md](_index/_task-routing.md)
- 知识地图：[_index/_map.md](_index/_map.md) ｜ 仪表盘：[_index/_dashboard.md](_index/_dashboard.md)
- 错误速查：`problems/_lookup.md` ｜ 故障总表：`faults/_registry.md`
- 可行性图谱：`portgraph/README.md`
