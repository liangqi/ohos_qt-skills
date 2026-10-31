<div align="center">

# ohos_qt-skills

**Qt → HarmonyOS 迁移工程仓：知识 · 机器规则 · 可执行流水线**

评估 → 迁移 → 编译 → 装机 → 验证 → 沉淀，每一步都有机器可判定的结果。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Qt](https://img.shields.io/badge/Qt-5.12%20%7C%205.15%20%7C%206.12-green.svg)](#能力规格)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](#30-秒上手)
[![Platform](https://img.shields.io/badge/平台-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#质量保障)
[![Pages](https://img.shields.io/badge/知识页-121-orange.svg)](_index/_map.md)

**主干分支 `trunk` ｜ v3.0.0** ｜ [变更日志](CHANGELOG.md) ｜ [贡献指南](CONTRIBUTING.md) ｜ [任务路由](_index/_task-routing.md)

</div>

> **这个仓不再是"一份移植参考文档"。** 它现在是一个工程仓：把 Qt 应用鸿蒙化过程中积累的**事实**（知识页）、
> **判据**（机器规则与错误模式）和**动作**（可执行的 CLI 与门禁）装在同一棵树里，让 Agent 和人
> 都能沿着同一条路径把应用搬到 HarmonyOS 上，并且**用工具而不是感觉**来判断是否成功。
>
> 设计原则只有一条：**LLM 负责推理，tool 负责事实**。编译通过不等于迁移成功，
> `TIMEOUT` 永远不是 `PASS`。

---

## 这个仓库解决什么问题

Qt/C++ 桌面应用要跑在 HarmonyOS 上，难点从来不是"写几行 ArkTS"，而是：

| 痛点 | 传统做法 | 本仓的做法 |
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
┌──────────────────────────────────────────────────────────────┐
│  入口层   SKILL.md · AGENTS.md · README.md · kb.yaml          │
│           → 人和 Agent 都从这里进入，kb.yaml 是仓库契约        │
├──────────────────────────────────────────────────────────────┤
│  知识层   semantic/ procedural/ episodic/ problems/          │
│           ohos-common-kb-public/                             │
│           → 人读的真源：事实、流程、复盘、错误解法、平台知识     │
├──────────────────────────────────────────────────────────────┤
│  机器层   knowledge/errors(42 条 QOH) · rules(18 条 R)        │
│           knowledge/adaptation · faults/(故障图)              │
│           → 工具读的索引：从知识层提炼的可匹配模式              │
├──────────────────────────────────────────────────────────────┤
│  执行层   tools/qt-ohos-run.py · qt-sdk-run.py               │
│           faults-build.py · kb-verify-qt.py · portgraph/     │
│           templates/qt-ohos-app/                             │
│           → 真正干活并给出 PASS/FAIL 的部分                    │
└──────────────────────────────────────────────────────────────┘
        ↑ 门禁结果、跑通的配方、踩到的新坑 ——— 回流沉淀 ↓
```

关键约束（也是本仓区别于"文档堆"的地方）：

- **知识层是人在读的唯一真源**，机器层只是它的**投影**，不另造一份事实——所以两边永远对得上；
- **执行层的结论必须可复现**：门禁判断基于文件存在性、二进制符号、日志模式，而不是模型自述；
- **回流是强制的**：新问题先落草稿，走主编门禁后才进真源，写进去的每条都要能被 `tools/kb-verify-qt.py` 复核。

---

## 核心能力

| 能力 | 入口 | 现状 |
|------|------|------|
| 🔍 可行性评估 | `portgraph/portgraph.py analyze / deps / fetch-deps` | 可 ingest 4741 个 Harmonybrew formula + 1248 个 cmd-pkg 索引（首次联网），出三态判定 |
| 🚚 自动迁移流水线 | `tools/qt-ohos-run.py`（24 个子命令） | 扫描（18 条预扫描规则出风险报告）→计划→受追踪修改→构建→打包→装机→启动→冒烟→门禁，可 checkpoint/resume |
| 🚦 成功判定 | `qt-ohos-run.py verify`（G0–G12） | 门禁级 PASS / PARTIAL / FAIL，`TIMEOUT` 不计通过 |
| 🧠 日志诊断 | `qt-ohos-run.py analyze-log` | 42 条 QOH 错误模式自动匹配，命中即给知识页引用 |
| 🧰 Qt SDK 工程平面 | `tools/qt-sdk-run.py`（24 个子命令） | 编译/增量 install/补丁溯源/SV0–SV8 发版门禁/上游演进跟踪 |
| 🗺️ 故障跟踪 | `faults/` + `tools/faults-build.py` | S→C→W→T 故障图（17/18/15/5）：定性、责任、临时方案、在跟单、闭环缺口 |
| 📚 知识底座 | `semantic/` `procedural/` `problems/` | 121 页（Qt 侧 94 + 内嵌平台 27），35 条铁律，13 类 API 映射，47 个实战踩坑 |
| 🏗️ 工程模板 | `templates/qt-ohos-app/` | 71 个文件的干净鸿蒙壳工程（替代历史上带构建产物的脏模板） |
| ✅ 自检门禁 | `_scripts/verify.sh` + `tests/` | 契约/结构/引用/卫生检查 + 引擎自测 12 用例 + 一致性 22 用例 |

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

### 想让 Agent 干活

在支持 `SKILL.md` / `AGENTS.md` 的 Agent（Claude Code / Codex / Cursor 等）里打开本仓，直接说需求：

- "把这个 Qt 项目迁移到鸿蒙" → 走 `qt-app-porting`（执行流水线）
- "这堆编译日志什么毛病" → 走 `analyze-log` + `problems/`
- "帮我编一个 Qt 5.15 的鸿蒙 SDK" → 走 `qt-sdk-forge`
- "这个问题到底是 Qt 的 bug 还是鸿蒙限制" → 走故障图 `faults/`

Agent 的加载顺序、执行纪律、禁止事项写在 [AGENTS.md](AGENTS.md)（`CLAUDE.md` 是它的逐字副本）。

### 想自己在本地跑工具

```bash
python3 tools/qt-ohos-run.py --help        # 迁移流水线
python3 tools/qt-sdk-run.py --help         # SDK 工程平面
python3 tools/faults-build.py check        # 故障库真源 ↔ 派生物一致性
python3 portgraph/portgraph.py analyze <应用名>   # 可行性三态
bash _scripts/verify.sh                    # 仓库自检（契约/结构/引用/卫生）
python3 -m unittest discover -s tests -v   # 用例全量
```

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
| [`qt-community-to-official`](skills/qt-community-to-official/SKILL.md) | 社区版（QtOhExtras）→ 官方版（QtOhosExtras）迁移：代码迁移、patch、编译修复、签名 HAP | 只写目标项目 |
| [`task-dispatcher`](skills/task-dispatcher/SKILL.md) | 多 Agent 协作的任务台账 / 移交信封 / 流转日志 | 只写任务台账 |
| [`kb-iterator`](skills/kb-iterator/SKILL.md) | **唯一真源写入门**：合草稿、promote、索引再生、事实复核、复盘蒸馏 | 唯一可写知识真源 |

外加一个不在 `skills/` 下的仓库工具 `portgraph`（可行性图谱），作为移植任务的第 0 步。

---

## CLI 工具

| 工具 | 子命令 | 干什么 |
|------|-------|--------|
| `tools/qt-ohos-run.py` | 24 | `scan` `plan` `patch` `build` `package` `install` `launch` `smoke` `verify` `analyze-log` `assess` `migrate` `finish` `status` `resume` `rollback` `mark-gate` `mark-ui` `mark-risk` `draft` `promote` `recipes` `config` `init` |
| `tools/qt-sdk-run.py` | 24 | `init` `env` `config` `src-clone` `status` `patch-import` `patch-apply` `patch-list` `patch-revert` `patch-export` `patch-mark` `configure` `build` `install` `verify` `smoke-mark` `release` `release-list` `modules` `use` `diff` `upstream-check` `forge` `resume` |
| `tools/faults-build.py` | 3 | `build` `check` `review`：真源 → 派生物，闭环缺口检查 |
| `tools/kb-verify-qt.py` | — | 知识页事实复核（版本、符号、路径） |
| `tools/cpp20-gap-scan.py` | — | C++20 在鸿蒙工具链上的缺口扫描 |
| `portgraph/portgraph.py` | 10 | `ingest` `clone` `scan` `analyze` `deps` `stats` `fetch` `fetch-deps` `export` `serve` |

---

## 目录结构

```
ohos_qt-skills/
├── SKILL.md                    # Agent Skill 入口（frontmatter + Instructions）
├── AGENTS.md / CLAUDE.md       # Agent 行为契约（两份逐字一致，verify 强校验）
├── kb.yaml                     # 仓库契约：入口/地图/自检命令/分层必需路径
├── README.md  CHANGELOG.md  CONTRIBUTING.md  TESTING.md
├── _scripts/                   # 门禁：verify.sh / verify.py
├── _index/                     # 索引：_map 地图 / _tags 标签 / _dashboard 仪表盘 / _task-routing 路由
├── semantic/                   # 语义知识（27 页）：模块状态、API 映射、平台限制、窗口/生命周期
├── procedural/                 # 程序知识（15 页）：迁移、排障、构建、发版、Demo 生成
├── episodic/                   # 情景知识（7 页）：真实项目复盘
├── problems/                   # 错误知识库（47 页）：编译/部署/运行时实报错与解法
├── ohos-common-kb-public/      # 内嵌 HarmonyOS 平台通用知识（27 页，ArkTS/ArkUI/NAPI/Stage）
├── knowledge/                  # 机器层：errors(QOH) / rules(R) / adaptation
├── faults/                     # 故障图：_data 真源 + C 页 + 派生物 _graph/_registry
├── tools/                      # 执行层：CLI + qt_ohos / qt_sdk 引擎包
├── templates/qt-ohos-app/      # 干净鸿蒙壳工程模板（71 文件）
├── portgraph/                  # 可移植性图谱子项目（CLI + 包 + Web 图谱 + 自测）
├── tests/                      # 仓库一致性 / 引擎 / 扫描自测
└── skills/                     # 6 个 Agent Skill
```

---

## 分支模型

本仓用三段式分支，**旧分支一律冻结不动**，避免影响仍在用旧分支的人：

| 分支 | 角色 | 规则 |
|------|------|------|
| `trunk` | 主干，稳定版本 | 只接受来自开发分支的合并；每次合并必须 `verify.sh` + 全量用例通过；打 `vX.Y.Z` tag 锚定 |
| 开发分支 | 开发与合入 | 从 `trunk` 拉出，供外部 PR 合入；允许不稳定，合并前必须过门禁 |
| `release/vX.Y.Z` | 归档 | 从 `trunk` 在发版点拉出，只修致命缺陷，不再进新功能 |

```
trunk ──●────────●────────●────────●──→  稳定、可发版
         \      / \      / \      /
  dev/*   ●────●   ●────●   ●────●        开发、可合入
                   \
  release/v2.1.0     ●────●               归档、只修致命
```

细节与提交流程见 [贡献指南](CONTRIBUTING.md)。

---

## 质量保障

本仓把"文档里写的数字"当作**可测断言**来维护，而不是靠人记得改：

| 层次 | 手段 | 拦截什么 |
|------|------|---------|
| 契约 | `kb.yaml` + `_scripts/verify.sh` | 入口/地图/必需路径缺失、`AGENTS.md` 与 `CLAUDE.md` 漂移 |
| 结构 | verify 的 frontmatter / id 唯一 / wikilink 可解析检查 | 页面字段缺失、重复 id、断链 |
| 卫生 | verify 的产物与本机路径检查 | 提交构建产物（`.cxx`/`.hvigor`/`.idea`）、泄露个人路径 |
| 数字 | `tests/test_kb_consistency.py` | README/SKILL/AGENTS/索引里的数量、路径、锚点与实际不符 |
| 引擎 | `tests/test_qt_ohos.py` | 状态机、门禁、错误匹配的行为回归 |
| 图谱 | `portgraph/tests/` | 可移植性判定、依赖分类、bottle 解析 |
| 闭环 | `tools/faults-build.py check` | 故障库真源与派生物不一致、未闭环链路 |

当前状态：`verify.sh` PASS，用例全绿（引擎 12 + 一致性 22 + 扫描 9 + 图谱 119 单测）。
测试分层、与 `bitfun-release` 的能力对照矩阵、Windows 端到端实测步骤见 [TESTING.md](TESTING.md)。
CI 尚未接入（见"已知限制"），门禁靠本地执行与维护者把关。

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
- **CI**：目前没有托管 CI，门禁靠本地执行与本仓自检脚本；接入 CI 是后续工作。
- **portgraph**：数据来自外部索引（Harmonybrew / cmd-pkgs），首次 `ingest` 需要联网；离线场景只能读已入库的 `portgraph/data`。
- **知识时效**：Qt/鸿蒙都在动，页面里的"已完成/已修复"以 `updated` 与 `last_confirmed` 字段为准，超过复核期的内容会由 `faults-build review` 标出来。
- **内嵌平台知识**：`ohos-common-kb-public/` 由上游平台知识库裁剪而来，若与官方文档冲突，以官方文档为准。

---

## 设计理念

1. **真源唯一**：同一件事只写一次，机器层是投影不是副本；`kb-iterator` 是唯一写入口，防止多人各写一份。
2. **结论可判定**：能写成断言的不写成建议——门禁用文件、符号、日志模式判断，不用模型自述。
3. **失败要留痕**：每次自动修改进 `.qt-ohos/changes.json` + patch 目录，中断可续跑，事后可复盘。
4. **知识要能被反驳**：每条故障都带证据类型（demo / 日志+栈 / 静态可判定），纯转述不予受理。
5. **数字要真**：文档里的数量由测试守着，改文档不改事实会让门禁红。

---

## 版本与发布

- 版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)：**MAJOR** 破坏性（删页/移页/目录重排致链接断）、**MINOR** 新增（新页/新 CLI 子命令/新 skill）、**PATCH** 修正。
- 发版点在 `trunk` 上打 tag，并从该 tag 拉 `release/vX.Y.Z` 归档。
- 每个版本的 [RELEASE-MANIFEST.yaml](RELEASE-MANIFEST.yaml) 记录页面计数与内容树摘要，可复现。
- 当前为 **v3.0.0**：由 `main`（v2.2.1 内容基线）与 `bitfun-release`（执行层/机器层/故障图/模板）合并，并补上仓库契约与门禁。旧分支 `main`、`bitfun-release` 保持冻结，仅作历史参考。

---

## 参与

内容勘误、报错补充、迁移复盘、故障情报、工具改进都欢迎，入口在 [贡献指南](CONTRIBUTING.md)：
**开发分支接受 PR，合并前必须过门禁；`trunk` 只接受来自开发分支的合并。**

License: MIT（见 [LICENSE](LICENSE)）。
