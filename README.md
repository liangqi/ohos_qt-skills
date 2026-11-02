<div align="center">

# ohos_qt-skills

**Qt → HarmonyOS 迁移工程仓：知识 · 机器规则 · 可执行流水线**

评估 → 迁移 → 编译 → 装机 → 验证 → 沉淀，每一步都有机器可判定的结果。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Qt](https://img.shields.io/badge/Qt-5.12%20%7C%205.15%20%7C%206.12-green.svg)](#能力规格)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](#30-秒上手)
[![Platform](https://img.shields.io/badge/平台-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#质量保障)
[![Pages](https://img.shields.io/badge/知识页-120-orange.svg)](_index/_map.md)

**版本 v2.3.0** ｜ [变更日志](CHANGELOG.md) ｜ [贡献指南](CONTRIBUTING.md) ｜ [任务路由](_index/_task-routing.md)

</div>

> Qt 应用鸿蒙化需要的三样东西装在同一棵树里：**事实**（知识页）、**判据**（机器规则与错误模式）、
> **动作**（可执行的 CLI 与门禁）。人和 Agent 沿同一条路径把应用搬到 HarmonyOS 上，
> 每一步的结果由工具判定，不由"看起来没问题"判定。
>
> 设计原则：**LLM 负责推理，tool 负责事实**。编译通过不等于迁移成功，
> `TIMEOUT` 永远不是 `PASS`。

---

## 这个仓库解决什么问题

Qt/C++ 桌面应用要跑在 HarmonyOS 上，难点集中在这些地方：

| 场景 | 常见做法 | 本仓做法 |
|------|---------|-----------|
| 不知道能不能迁 | 逐个模块翻 wiki、试编译 | `portgraph analyze` 出三态结论（portable / blocked / uncertain）+ 阻断根因归类 |
| 迁完编译过了，装到机器上白屏/闪退 | 靠人盯着日志猜 | 门禁 G0–G12 逐条判定，缺 so 闭包、签名、部署缺口都会被点出来 |
| 同样的报错反复踩 | 翻聊天记录 | 42 条 QOH 错误模式机器匹配 + 47 个实战踩坑页 + 故障图定位"归谁、修没修、怎么绕" |
| 三方依赖下载/交叉编译耗掉几天 | 手工找 bottle、手工编 | `portgraph deps` / `fetch-deps` 出依赖角色分类与闭包清单 |
| 换个人接手就断了 | 口口相传 | 状态机落盘（`.qt-ohos/`）+ 任务台账 + 知识沉淀协议 |

一句话：**把"能跑通一次"变成"可重复跑通、能被别人接手、能被机器验收"**。

---

## 架构：四层一体，闭环回流

```
┌───────────────────────────────────────────────────────────────┐
│  入口层   SKILL.md · AGENTS.md · README.md · SETUP.md         │
│           → 人从这里进入：定位、能力、上手、Agent 契约        │
├───────────────────────────────────────────────────────────────┤
│  知识层   semantic/ procedural/ episodic/ problems/           │
│           ohos-common-kb-public/                              │
│           → 人读的真源：事实、流程、复盘、错误解法、平台知识  │
├───────────────────────────────────────────────────────────────┤
│  机器层   knowledge/errors(42 条 QOH) · rules(18 条 R)        │
│           knowledge/adaptation · faults/(故障图)              │
│           → 工具读的索引：从知识层提炼的可匹配模式            │
├───────────────────────────────────────────────────────────────┤
│  执行层   tools/qt-ohos-run.py · qt-sdk-run.py                │
│           faults-build.py · kb-verify-qt.py · portgraph/      │
│           templates/qt-ohos-app/                              │
│           → 真正干活并给出 PASS/FAIL 的部分                   │
└───────────────────────────────────────────────────────────────┘
        ↑ 门禁结果、跑通的配方、踩到的新坑 ——— 回流沉淀 ↓
```

四条硬约束：

- **知识层是人在读的唯一真源**，机器层只是它的**投影**，不另造一份事实——所以两边永远对得上；
- **执行层的结论必须可复现**：门禁判断基于文件存在性、二进制符号、日志模式，而不是模型自述；
- **回流是强制的**：新问题先落草稿，走主编门禁后才进真源，写进去的每条都要能被事实复核工具检查。

---

## 核心能力

| 能力 | 入口 | 现状 |
|------|------|------|
| 🔍 可行性评估 | `portgraph/portgraph.py analyze / deps / fetch-deps` | 可 ingest 4741 个 Harmonybrew formula + 1248 个 cmd-pkg 索引（首次联网），出三态判定 |
| 🚚 自动迁移流水线 | `tools/qt-ohos-run.py`（24 个子命令） | 扫描（18 条预扫描规则出风险报告）→计划→受追踪修改→构建→打包→装机→启动→冒烟→门禁，可 checkpoint/resume |
| 🚦 成功判定 | `qt-ohos-run.py verify`（G0–G12） | 门禁级 PASS / PARTIAL / FAIL，`TIMEOUT` 不计通过 |
| 🧠 日志诊断 | `qt-ohos-run.py analyze-log` | 42 条 QOH 错误模式自动匹配，命中即给知识页引用 |
| 🧰 Qt SDK 工程平面 | `tools/qt-sdk-run.py`（24 个子命令） | 编译 / 增量 install / 补丁溯源 / SV0–SV8 发版门禁 / 上游演进跟踪 |
| 🗺️ 故障跟踪 | `faults/` + `tools/faults-build.py` | S→C→W→T 故障图（17/18/15/11）：定性、责任领域、临时方案、在跟单、闭环缺口 |
| 📚 知识底座 | `semantic/` `procedural/` `problems/` | 122 页（Qt 侧 95 + 内嵌平台 27），35 条铁律，13 类 API 映射，47 个实战踩坑 |
| 🏗️ 工程模板 | `templates/qt-ohos-app/` | 71 个文件的干净鸿蒙壳工程（替代历史上带构建产物的脏模板） |
| ✅ 自检用例 | `tests/` | 引擎 12 + 一致性 20 + 扫描 9 = 41 用例（另有图谱 123 单测） |

---

## 30 秒上手

### 只想查知识（零依赖）

```bash
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills
cat _index/_task-routing.md     # 你在做什么 → 读哪几页
cat _index/_map.md              # 每页一句话摘要
```

不需要 Python，不需要装任何东西。Obsidian 直接当 Vault 打开可以看到引用关系图。
要固定某个版本：`git clone --branch vX.Y.Z <仓库地址>`（tag 与 `CHANGELOG.md` 一一对应）。

### 第 0 步：可行性评估（第一次要先建图数据）

接手一个陌生项目，先判断"能不能迁"比直接改代码省几天：

```bash
python portgraph/portgraph.py ingest all            # 首次：拉取 Harmonybrew + cmd-pkgs 数据源建图
python portgraph/portgraph.py scan <你的Qt工程路径>  # 或 clone <git-url>
python portgraph/portgraph.py analyze <app> --summary     # 三态判定
python portgraph/portgraph.py deps <app>                  # 依赖角色分析（每条带 文件:行号 证据）
python portgraph/portgraph.py fetch-deps <app> --dry-run  # 依赖闭包预览
```

结论是 `portable` / `blocked` / `uncertain` 之一：`blocked` 给出具体阻断项，
`uncertain` 列出"需要源码交叉编译"的缺口清单——这份清单才是排期的依据。

### 想让 Agent 干活

在支持 `SKILL.md` / `AGENTS.md` 的 Agent（Claude Code / Codex / Cursor 等）里打开本仓，直接说需求：

- "把这个 Qt 项目迁移到鸿蒙" → 走 `qt-app-porting`（执行流水线）
- "这堆编译日志什么毛病" → 走 `analyze-log` + `problems/`
- "帮我编一个 Qt 5.15 的鸿蒙 SDK" → 走 `qt-sdk-forge`
- "这个问题到底是 Qt 的 bug 还是鸿蒙限制" → 走故障图 `faults/`

Agent 的加载顺序、执行纪律、禁止事项写在 [AGENTS.md](AGENTS.md)。环境依赖与首次配置见 [SETUP.md](SETUP.md)。

### 想自己在本地跑工具

驱动一次完整迁移（每一步都会在目标项目 `.qt-ohos/` 下留状态，中断可 `resume`）：

```bash
python tools/qt-ohos-run.py scan <项目目录>   # 预扫描 + 18 条规则风险报告
python tools/qt-ohos-run.py plan              # 迁移计划（auto / assisted / manual）
python tools/qt-ohos-run.py patch             # 白名单自动修复（受追踪）
python tools/qt-ohos-run.py build             # G3 编译
python tools/qt-ohos-run.py package           # G5 打 HAP
python tools/qt-ohos-run.py install           # G6 hdc 装机
python tools/qt-ohos-run.py launch            # G7 启动
python tools/qt-ohos-run.py smoke             # G8 崩溃窗口检查
python tools/qt-ohos-run.py verify            # G0-G12 门禁 —— 唯一的成功判据
```

想一步到位就用一键模式 `python tools/qt-ohos-run.py migrate <项目>`（自动串联全流程，
遇到需要人判断的壳工程生成会停下给指引）；跨会话恢复用 `status` / `resume --run`。

快速自检与环境相关工具：

```bash
python tools/faults-build.py check         # 故障库真源 ↔ 派生物一致性
python tools/cpp20-gap-scan.py scan <src>  # 大工程编译前先扫 C++20 缺口
python tools/kb-verify-qt.py               # 知识页事实复核（需 ENV.local.md 指向本地 SDK）
python -m unittest discover -s tests -v    # 用例全量
```

单步 `--help` 可查任意子命令：`python tools/qt-ohos-run.py --help`、`python tools/qt-sdk-run.py --help`。

工具层**只用 Python 标准库**（3.10+），Windows / macOS / Linux 均可跑；`portgraph` 的 `serve` 子命令
额外需要 FastAPI（可选）。

---

## Skills 一览

`skills/` 下每个目录都是一个独立 Agent Skill，边界按"谁能写真源"划分，不是按功能随便切的：

| Skill | 定位 | 写权限 |
|-------|------|--------|
| [`kb-init`](skills/kb-init/SKILL.md) | 环境初始化：检测 DevEco / OHOS SDK / Qt 源码，装缺失依赖，生成 `ENV.local.md` | 只写本地 `ENV.local.md` |
| [`qt-app-porting`](skills/qt-app-porting/SKILL.md) | 应用迁移主流水线（调用 `qt-ohos-run.py`），产出报告与知识草稿 | 只写目标项目 + `.qt-ohos/` + 草稿 |
| [`qt-sdk-forge`](skills/qt-sdk-forge/SKILL.md) | Qt SDK 编译、补丁应用与溯源、本地多版本发布（SV0–SV8） | 只写本地 SDK 目录 |
| [`task-dispatcher`](skills/task-dispatcher/SKILL.md) | 多 Agent 协作的任务台账 / 移交信封 / 流转日志 | 只写任务台账 |
| [`kb-iterator`](skills/kb-iterator/SKILL.md) | **唯一真源写入门**：合草稿、promote、索引再生、事实复核、复盘蒸馏 | 唯一可写知识真源 |

外加一个不在 `skills/` 下的仓库工具 `portgraph`（可行性图谱），作为移植任务的第 0 步。

---

## CLI 工具

| 工具 | 子命令 | 干什么 |
|------|-------|--------|
| `tools/qt-ohos-run.py` | 24 | `scan` `plan` `patch` `build` `package` `install` `launch` `smoke` `verify` `analyze-log` `assess` `migrate` `finish` `status` `resume` `rollback` `mark-gate` `mark-ui` `mark-risk` `draft` `promote` `recipes` `config` `init` |
| `tools/qt-sdk-run.py` | 24 | `init` `env` `config` `src-clone` `status` `patch-import` `patch-apply` `patch-list` `patch-revert` `patch-export` `patch-mark` `configure` `build` `install` `verify` `smoke-mark` `release` `release-list` `modules` `use` `diff` `upstream-check` `forge` `resume` |
| `tools/faults-build.py` | 4 | `build` `check` `review` `all`：真源 → 派生物，闭环缺口检查 |
| `tools/kb-verify-qt.py` | — | 知识页事实复核（版本、符号、路径） |
| `tools/cpp20-gap-scan.py` | — | C++20 在鸿蒙工具链上的缺口扫描 |
| `tools/kb-cef-graft.py` | — | 把 CEF 嫁接到 Qt OHOS 模板工程（`--run` 含签名+装机+崩溃检查） |
| `portgraph/portgraph.py` | 10 | `ingest` `clone` `scan` `analyze` `deps` `stats` `fetch` `fetch-deps` `export` `serve` |

`qt-sdk-run.py forge <proposal-dir>` 把一次修改方案打成可追溯的补丁提案（含 manifest），
再由 `patch-import` / `patch-apply` 落到源码树——这样"谁为什么改了 Qt 哪一行"永远查得到。

---

## 按场景找页面

| 我要做什么 | 先读这些 |
|-----------|---------|
| 移植 Qt 应用到鸿蒙 | 上面「第 0 步」评估 → `procedural/qt-app-harmonyos-migration.md` + `semantic/qt-harmonyos-porting-workflow.md` |
| 查 API 替换 | `semantic/qt-harmonyos-api-mapping.md` + `semantic/qt-harmonyos-code-patterns.md` |
| 查某个 Qt 模块是否支持鸿蒙 | `semantic/qt-harmonyos-modules.md` |
| 查鸿蒙平台限制 | `semantic/qt-harmonyos-platform-limits.md` |
| 编译失败 / 打包 / 部署不了 | 先 `analyze-log` → `problems/_lookup.md` + `semantic/qt-harmonyos-build-run-workflow.md` |
| 窗口 / 对话框 / 生命周期异常 | `semantic/qt-harmonyos-window-model.md` + `semantic/qt-harmonyos-lifecycle.md` |
| QtOhosExtras 怎么用 | `semantic/qt-ohos-extras.md` + `semantic/qt-ohos-extras-examples.md` |
| 判断问题归谁（Qt 缺陷 / 鸿蒙限制 / 应用问题） | `faults/_registry.md` §症状索引 |
| 三方库 / 交叉编译 | `semantic/qt-harmonyos-third-party-libs.md` + `portgraph deps` / `fetch-deps` |
| Qt6 适配现状 | `semantic/qt-harmonyos-qt6-status.md` |
| 写 demo / 验证工程 | `procedural/demo-generation.md` + `templates/qt-ohos-app/` |
| Qt + CEF 应用 | `procedural/qt-cef-ohos-dev-guide.md` |
| 想通读全貌 | `_index/_map.md`（每页一句话摘要） |
| DevEco 工具链 / MCP 能力边界 | `ohos-common-kb-public/procedural/deveco-cli-usage-rules.md` + `ohos-common-kb-public/semantic/deveco-mcp-capabilities.md` |

**故障库怎么用**：S 是应用层表现，C 是根因，且 C 一定分了**定性**——`defect`（Qt/鸿蒙确实
有缺陷，会修，需在跟单与临时方案）或 `limitation`（规格限制，给替代方案而非等待修复），
W 是临时方案、T 是上游跟踪单。新问题先进 `faults/_drafts/` 走草稿 → 主编门禁 → promote
转正，避免直接把猜测写进真源。

## 交叉编译与依赖集成要点

- **CMake**：`-DCMAKE_PREFIX_PATH=<bottle路径> -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`
- **qmake**：`LIBS += -L<bottle>/lib -lfoo`（`-l` 列表由 `fetch` 输出）
- `.so` 在 Windows 上**只能链接不能运行**；必须部署到 `entry/libs/arm64-v8a/` 才能上设备
- 运行时依赖要递归拉全（`fetch-deps` 已处理），漏拉会在设备 `dlopen` 时失败，编译期无感知

## 目录结构

```
ohos_qt-skills/
├── SKILL.md                    # Agent Skill 入口（frontmatter + Instructions）
├── AGENTS.md                   # Agent 行为契约（Claude Code 用本地副本即可）
├── README.md  SETUP.md  SECURITY.md  CHANGELOG.md  CONTRIBUTING.md
├── ENV.md                      # 环境变量名清单（真实值写 ENV.local.md，不入库）
├── _index/                     # 索引：_map 地图 / _tags 标签 / _dashboard 仪表盘 / _task-routing 路由
├── semantic/                   # 语义知识（26 页）：模块状态、API 映射、平台限制、窗口/生命周期
├── procedural/                 # 程序知识（15 页）：迁移、排障、构建、发版、Demo 生成
├── episodic/                   # 情景知识（7 页，postmortems/）：真实项目复盘
├── problems/                   # 错误知识库（47 页）：编译/部署/运行时实报错与解法
├── ohos-common-kb-public/      # 内嵌 HarmonyOS 平台通用知识（27 页，ArkTS/ArkUI/NAPI/Stage）
├── knowledge/                  # 机器层：errors(QOH) / rules(R) / adaptation
├── faults/                     # 故障图：_data 真源 + C 页 + 派生物 _graph/_registry
├── tools/                      # 执行层：CLI + qt_ohos / qt_sdk 引擎包
├── templates/qt-ohos-app/      # 干净鸿蒙壳工程模板（71 文件）
├── portgraph/                  # 可移植性图谱子项目（CLI + 包 + Web 图谱 + 自测）
├── tests/                      # 仓库一致性 / 引擎 / 扫描自测
├── kb.yaml                     # 仓库契约：入口 / 地图 / 自检命令 / 必需路径
├── _scripts/                   # 门禁与发版：verify.sh / verify.py / ci.sh / gen-manifest.py
├── TESTING.md                  # 测试分层、与旧分支的能力对照、Windows 端到端步骤
├── LINEAGE.md                  # 分支收敛记录：每条旧分支的并入状态与有意不并入的内容
├── CLAUDE.md                   # AGENTS.md 的逐字副本（verify 强校验一致）
└── skills/                     # 6 个 Agent Skill
```

---

## 分支模型

本仓用三段式分支，**旧分支一律冻结不动**，避免影响仍在用旧分支的人：

| 分支 | 角色 | 规则 |
|------|------|------|
| `trunk` | 主干，稳定版本 | 只接受来自开发分支的合并；每次合并必须 `ci.sh` 全绿；打 `vX.Y.Z` tag 锚定 |
| 开发分支 | 开发与合入 | 从 `trunk` 拉出，供外部 PR 合入；允许不稳定，合并前必须过门禁 |
| `release/vX.Y.Z` | 归档 | 从 `trunk` 在发版点拉出，只修致命缺陷，不再进新功能 |

```
trunk ──●────────●────────●────────●──→  稳定、可发版
         \      / \      / \      /
  dev/*   ●────●   ●────●   ●────●        开发、可合入
                   \
  release/vX.Y.Z     ●────●               归档、只修致命
```

细节、提交流程与发版步骤见 [贡献指南](CONTRIBUTING.md)；各历史分支的内容并入情况见 [分支收敛记录](LINEAGE.md)。

---

## 质量保障

"文档里写的数字"在本仓是**可测断言**，由 `tests/test_kb_consistency.py` 守住：它把
README、`SKILL.md`、`AGENTS.md`、索引页里的声称与仓库实际状态绑定：

| 层次 | 手段 | 拦截什么 |
|------|------|---------|
| 契约 | `kb.yaml` + `_scripts/verify.py` | 入口/地图/必需路径缺失、`AGENTS.md` 与 `CLAUDE.md` 漂移 |
| 结构 | verify 的 frontmatter / id 唯一 / wikilink 可解析检查 | 页面字段缺失、重复 id、断链 |
| 卫生 | verify 的产物目录与本机路径检查 | 提交构建产物（`.cxx`/`.hvigor`/`.idea`）、泄露个人路径 |
| 发版清单 | verify 的 M1 检查 + `_scripts/gen-manifest.py` | 清单里的页数/用例数/skills 与实际不符；发版提交上内容树摘要对不上 |
| 数字 | `tests/test_kb_consistency.py`（20 个） | 页数、QOH、规则数、铁律、任务路由、API 映射、故障图规模、用例数与实际不符 |
| 引用 | 同上（路径与锚点校验） | 文档里指的页面/小节不存在 |
| 清单 | 同上（Skill 清单规范） | 根级/子级 `SKILL.md` frontmatter 非法、`AGENTS.md` 漏登记 skill |
| 契约 | 同上（CLI 契约） | 三个 CLI 的子命令集合被悄悄改动 |
| 闭环 | `tools/faults-build.py check` | 故障库真源与派生物不一致、链路未闭环 |
| 引擎 | `tests/test_qt_ohos.py` | 状态机、门禁、错误匹配的行为回归 |
| 图谱 | `portgraph/tests/` | 可移植性判定、依赖分类、bottle 解析 |

当前状态：用例全绿（引擎 12 + 一致性 20 + 扫描 9 = 41，另有图谱 123 单测），`faults-build check` 零 ERROR（info 7 为已排期的缺单）。
一条命令跑完全部门禁：`bash _scripts/ci.sh`（退出码即结论，可直接接到流水线）。

---

## 能力规格

按"你要做什么"查，共 15 类任务：

| 码 | 任务类型 | 起点 |
|----|---------|------|
| A | 应用移植（全流程） | `_index/_task-routing.md` → 迁移工作流 |
| B | API 替换查询 | 13 类 API 映射 + 代码模式 |
| C | 模块支持查询 | 模块适配状态矩阵 |
| D | 平台限制查询 | 平台限制页 + 铁律 |
| E | 构建排障 | 构建/运行工作流 + `problems/_lookup.md` |
| F | 窗口/对话框行为 | 窗口模型 + 铁律 |
| G | 生命周期 | 生命周期页（closeEvent/接续/分享） |
| H | QtOhosExtras API | 145+ QtOhosExtras 扩展接口 |
| L | Qt6 状态 | Qt6 适配现状与缺口 |
| M | 三方库/依赖 | 三方库页 + `portgraph deps` |
| N | 工具链 | devecocli / hvigor / hdc 用法与边界 |
| P | 自动迁移（执行层） | `qt-ohos-run.py` |
| Q | Demo 生成 | 示例工程生成流程 |
| R | 故障跟踪 | 故障图 S→C→W→T |
| S | SDK 工程 | `qt-sdk-run.py` |

---

## 已知限制

- **平台**：端到端实测以 Windows + DevEco Studio 为主；macOS/Linux 的工具链路径已覆盖但真机装机流程验证较少。
- **CI**：仓库自带 `_scripts/ci.sh`（一条命令四条门禁、退出码即结论），托管 CI 尚未接入，合并前靠本地执行与维护者把关。
- **portgraph**：数据来自外部索引（Harmonybrew / cmd-pkgs），首次 `ingest` 需要联网；离线只能读已入库的 `portgraph/data`。
- **知识时效**：Qt/鸿蒙都在动，页面里的"已完成/已修复"以 `updated` 与 `last_confirmed` 字段为准，超过复核期的内容由 `faults-build review` 标出。
- **内嵌平台知识**：`ohos-common-kb-public/` 由上游平台知识库裁剪而来，若与官方文档冲突，以官方文档为准。
- **可行性判定的边界**：`portgraph` 的平台接口检测是正则匹配——注释里的 API 名（如 `// DestroyWindow(...)`）
  或同名自定义函数可能误报、虚高风险等级，硬阻塞结论要人工复核守卫证据。
- **三方库源码交叉编译不在本库内置**：可对接外部 `build_in_harmonyos` 工具链（设置 `OHC_RUN`
  环境变量），本库负责依赖检测、bottle 直下与集成指引。

---

## 设计理念

1. **真源唯一**：同一件事只写一次，机器层是投影不是副本；`kb-iterator` 是唯一写入口，防止多人各写一份。
2. **结论可判定**：能写成断言的不写成建议——门禁用文件、符号、日志模式判断，不用模型自述。
3. **失败要留痕**：每次自动修改进 `.qt-ohos/changes.json` + patch 目录，中断可续跑，事后可复盘。
4. **知识要能被反驳**：每条故障都带证据类型（demo / 日志+栈 / 静态可判定），纯转述不予受理。
5. **数字要真**：文档里的数量由用例守着，改文档不改事实会让用例红。

---

## 环境变量与多工具兼容

知识页不写死本机路径，统一用变量名引用：`QT5_15_OHOS_SDK`、`QT5_15_SRC`、`OHOS_SDK_NATIVE`、
`DEVECO_CLI`、`HDC` 等。变量清单见 [ENV.md](ENV.md)，真实值写 `ENV.local.md`（已 gitignore、
不入库），由 `kb-init` 交互式生成。

| 工具 | 接入方式 |
|------|---------|
| Claude Code | 仓库自带 `CLAUDE.md`（`AGENTS.md` 的逐字副本，`verify` 强校验一致），开箱即用 |
| Codex | 直接读 `AGENTS.md` |
| Cursor / Windsurf | 在 `.cursorrules` / `.windsurfrules` 里引用 `_index/_map.md` |
| Obsidian | 直接当 Vault 打开，看引用关系图 |

## 版本与发布

- 版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)：**MAJOR** 破坏性（删页/移页/目录重排致链接断）、**MINOR** 新增（新页/新 CLI 子命令/新 skill）、**PATCH** 修正。
- 每个版本的 [RELEASE-MANIFEST.yaml](RELEASE-MANIFEST.yaml) 记录源端 SHA、页面计数与
  `content_tree_sha256`（内容树摘要），由 `_scripts/gen-manifest.py` 机算，`verify` 的 M1 检查对账。
  发版步骤（刷新清单 → 置 released → 打 tag → 拉归档线）见 [CONTRIBUTING.md](CONTRIBUTING.md) §发版流程。

**Qt 源码获取渠道**（按许可与网络条件选一条）：

- 商业 license：`git clone https://codereview.qt-project.org/qt/tqtc-qt5`（分支如 `tqtc/harmonyos-5.15.16`）
- 开源镜像：`ohos-qt/qt-harmonyos-src`（部分快照丢执行位、带 CRLF，`src-clone` 会自动处理）
- 预编译 SDK：上游 releases 直接取，或用 `qt-sdk-run.py` 本地编译（SV0–SV8 门禁）

---

## 参与

内容勘误、报错补充、迁移复盘、故障情报、工具改进都欢迎，入口见 [贡献指南](CONTRIBUTING.md)；
Issue 模板在 `.gitcode/ISSUE_TEMPLATE/`。内容只收 `audience: public` 的页面，frontmatter 必填
`id` / `type` / `summary` / `status`，交叉引用用 `refs` 或 wikilink，不留断链。
License: MIT（见 [LICENSE](LICENSE)）。
