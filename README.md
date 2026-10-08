<div align="center">

# ohos_qt-skills

**Qt for HarmonyOS 移植知识库与自动迁移工具链**

可行性评估 → 三方依赖分析与下载 → 自动迁移 → 编译打包装机 → 门禁验证，
一个仓库覆盖 Qt 应用鸿蒙化全流程。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Qt](https://img.shields.io/badge/Qt-5.12%20%7C%205.15%20%7C%206.12-green.svg)](#qt-源码获取渠道)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](#30-秒上手)
[![Platform](https://img.shields.io/badge/平台-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#本地环境配置)
[![Pages](https://img.shields.io/badge/知识页-115%2B-orange.svg)](_index/_map.md)

**当前版本 v2.3.0** ｜ [变更日志](CHANGELOG.md) ｜ [能力规格](#能力规格) ｜ [任务路由](#按任务找入口)

</div>

> **这是一份面向应用开发者的 Qt for HarmonyOS 移植参考知识库**：把 Qt/C++ 应用搬到鸿蒙时少踩坑、快定位。
> 由一个更大的内部工作流知识库裁剪、脱敏后生成（开发者版）。
>
> 设计原则：**LLM 负责推理，tool 负责事实**——迁移成功与否不由"看起来编译过了"决定，只以机器门禁结果（G0-G12）为准。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🔍 可行性评估（第 0 步） | `portgraph` 扫描应用的 Qt 模块、三方依赖与平台接口（Win32/Cocoa/X11/ALSA…）使用，递归推导 **portable / blocked / uncertain** 判定 |
| 📦 三方依赖分析与下载 | `deps` 按 link / build-tool / runtime / test / vendored 角色分类并校验版本范围；`fetch-deps` 一键下载约 6000 个鸿蒙 arm64 预编译 bottle（Harmonybrew + cmd-pkgs 双源），附 sha256 校验与 CMake/qmake 集成片段 |
| 🤖 自动迁移流水线 | `qt-ohos-run.py` 24 个子命令：扫描 → 计划 → 受追踪修改 → 编译 → 打 HAP → 装机 → 启动 → 冒烟，全程 checkpoint 可恢复 |
| 🚦 机器验证门禁 | 应用迁移 **G0-G12**、SDK 构建 **SV0-SV8** 门禁；TIMEOUT 永远不是 PASS |
| 📚 蒸馏知识库 | 35 条铁律 ｜ 42 条 QOH 错误模式 ｜ 13 类 API 映射 ｜ 145+ QtOhosExtras API ｜ 47 个实战踩坑 ｜ S→C→W→T 故障图（17/18/15/5） |
| 🧩 AI 原生接入 | 根级 [SKILL.md](SKILL.md) 总入口 + 5 个 Agent skills + `AGENTS.md`，Claude Code / Codex / Cursor / Trae 开箱即用 |

## 30 秒上手

前提：Python 3.10+ 与 Git（评估类功能零第三方依赖）。完整迁移另需 DevEco Studio + HarmonyOS SDK + Qt OHOS SDK——`kb-init` skill 会交互式引导配置。

```bash
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills

# ① 第 0 步：可行性评估（无需完整环境）
python portgraph/portgraph.py ingest all            # 首次：构建图数据（自动拉取数据源，一次性）
python portgraph/portgraph.py scan <你的Qt工程路径>  # 或 clone <git-url>
python portgraph/portgraph.py analyze <app> --summary
python portgraph/portgraph.py deps <app>            # 依赖角色分析（每条带 文件:行号 证据）
python portgraph/portgraph.py fetch-deps <app> --dry-run

# ② 执行迁移：在 AI 编程助手打开本仓库，说"把这个 Qt 项目鸿蒙化"
python tools/qt-ohos-run.py scan <项目目录>          # 也可直接驱动 CLI
python tools/qt-ohos-run.py verify                  # G0-G12 门禁——唯一的成功判据
```

不写代码也能用：人类直接浏览，从 [_index/_dashboard.md](_index/_dashboard.md)（仪表盘）或 [_index/_map.md](_index/_map.md)（知识地图，每页一句话摘要）开始；Obsidian 用户可直接作为 Vault 打开。

## 接入 AI 编程助手

| 工具 | 接入方式 |
|------|----------|
| Claude Code | 复制 `AGENTS.md` 为本地 `CLAUDE.md` 后自动加载（本仓不携带 CLAUDE.md） |
| Codex / OpenCode | 仓库根目录打开，自动读 `AGENTS.md` |
| Cursor | 建 `.cursorrules`：`请阅读并遵循 _index/_map.md 中定义的知识库结构` |
| Windsurf | 建 `.windsurfrules`，同上 |
| Trae / Agent Skills 兼容端 | 加载根级 [SKILL.md](SKILL.md)（触发词覆盖"鸿蒙化 / 移植 Qt / 三方依赖分析 / 构建报错"） |
| ChatGPT / 其它 | 手动上传 `_index/_map.md` + 相关知识页，或把 `AGENTS.md` 复制进系统提示 |

接入后直接用自然语言提问，AI 按 **任务路由 → 扫铁律 → 按需加载知识页 → 给方案** 处理。首次使用（或 `ENV.local.md` 不存在）时，Agent 会自动执行 `skills/kb-init/` 完成环境初始化。

### Skills 一览

| Skill / 入口 | 用途 | 触发方式 |
|--------------|------|----------|
| [SKILL.md](SKILL.md)（根级总入口） | 整库作为一个 skill 加载：主工作流 + 依赖分析下载 + 知识检索 | "鸿蒙化 / 移植 Qt 应用 / 分析下载三方依赖"时自动加载 |
| `skills/kb-init` | 环境初始化：检测依赖、安装引导、生成 `ENV.local.md`、验证就绪 | "初始化 / 配置环境 / 第一次使用" |
| `skills/qt-app-porting` | 自动迁移（统一 CLI `tools/qt-ohos-run.py`，G0-G12 门禁） | "迁移 / 鸿蒙化这个项目（要执行）/ 验证迁移结果 / 分析构建运行日志" |
| `skills/qt-sdk-forge` | Qt SDK 工程：编译、补丁应用与追踪、多版本发布（`tools/qt-sdk-run.py`，SV0-SV8） | "编译 / 重编 Qt / 打补丁 / 出 SDK 版本 / 检查上游更新" |
| `skills/task-dispatcher` | 多 Agent 协作调度中枢：任务台账 + 流转日志 + 移交信封 | 多 agent 模式下建档路由；"查任务状态 / 续跑 / 关单" |
| `skills/kb-iterator` | 知识库唯一真源写入门：草稿合入门禁、索引再生、事实校验、复盘蒸馏 | "合入草稿 / 复核 faults / 重建索引 / 检查上游演进影响" |
| `portgraph/`（仓库工具，非 skills/） | 可行性评估与依赖解决：`analyze` / `deps` / `fetch-deps` | 移植任务的**强制第 0 步**；依赖 ≥3 个三方库时禁止人工逐个判断 |

多 Agent 协作契约（接口卡 / 移交信封 / 人工接入点分级）见 [_index/_agent-mesh.md](_index/_agent-mesh.md)。

## 按任务找入口

知识库覆盖 **15 类任务**（路由码详见 [_index/_task-routing.md](_index/_task-routing.md)）：

| 路由 | 任务 | 入口 |
|------|------|------|
| [A] | 应用移植到鸿蒙 | **第 0 步 portgraph 评估**（`analyze` + `deps` + `fetch-deps --dry-run`）→ `procedural/qt-app-harmonyos-migration` + `semantic/qt-harmonyos-porting-workflow`（8 步决策树） |
| [B] | API 替换查询 | `semantic/qt-harmonyos-api-mapping`（13 类映射）+ `qt-harmonyos-code-patterns`（Before/After） |
| [C] | Qt 模块支持查询 | `semantic/qt-harmonyos-modules`（是否支持 + 5.12/5.15 版本 + 替代方案） |
| [D] | 平台限制查询 | `semantic/qt-harmonyos-platform-limits`（限制 + QTBUG 编号 + Workaround） |
| [E] | 构建排障 | `semantic/qt-harmonyos-build-run-workflow` §四步法 + `problems/_lookup` |
| [F] | 窗口问题 | `semantic/qt-harmonyos-golden-rules` §二 + `qt-harmonyos-window-model` |
| [G] | 生命周期 | `semantic/qt-harmonyos-lifecycle`（行为 + 代码 + 枚举路径） |
| [H] | QtOhosExtras API | `semantic/qt-ohos-extras`（145+ API 签名与示例） |
| [L] | Qt6 状态 | `semantic/qt-harmonyos-qt6-status` |
| [M] | 三方库 | `semantic/qt-harmonyos-third-party-libs` + `portgraph deps` / `fetch-deps` |
| [N] | 工具链 | `ohos-common-kb-public/procedural/deveco-cli-usage-rules` + `ohos-common-kb-public/semantic/deveco-mcp-capabilities` |
| [P] | 自动迁移（执行层） | `skills/qt-app-porting` + `tools/qt-ohos-run.py`（assess 为第 0 步，blocked 即止并出报告） |
| [Q] | Demo 生成 | `procedural/demo-generation`（六步闭环；Qt+CEF / WebEngine 迁移见 `procedural/qt-cef-ohos-dev-guide`） |
| [R] | 故障跟踪 | `faults/_registry` §症状索引 → 根因页（定性 / 责任 / 临时方案 / 跟踪单）；`tools/faults-build.py` |
| [S] | SDK 工程（执行层） | `skills/qt-sdk-forge` + `tools/qt-sdk-run.py`（SV0-SV8 门禁 + 补丁溯源 manifest） |

遇到报错：**第一步读 [problems/_lookup.md](problems/_lookup.md)**——按错误码 / 错误信息关键字 / 症状检索，47 个实战踩坑一错一文件。

## CLI 工具

| CLI | 定位 | 最小示例 |
|-----|------|----------|
| `tools/qt-ohos-run.py` | 应用迁移执行引擎（24 子命令，G0-G12 门禁，状态平面 `.qt-ohos/`） | `python tools/qt-ohos-run.py migrate <项目>` |
| `tools/qt-sdk-run.py` | Qt SDK 构建工程（24 子命令，SV0-SV8 门禁，补丁栈溯源） | `python tools/qt-sdk-run.py forge <proposal-dir>` |
| `portgraph/portgraph.py` | 可移植性图谱与依赖解决（10 子命令 + Web 图谱 + REST API） | `python portgraph/portgraph.py analyze <app> --summary` |
| `tools/faults-build.py` | 故障库派生物重建与一致性门禁（build / check / review） | `python tools/faults-build.py check` |
| `tools/kb-verify-qt.py` | 知识事实校验：模块矩阵 vs 本地 SDK 实物、QOH refs 存在性 | `python tools/kb-verify-qt.py` |
| `tools/cpp20-gap-scan.py` | clang15/libc++15 的 C++20 缺口**编译前**预检与机械修复（8 规则，scan/fix） | `python tools/cpp20-gap-scan.py scan <src>` |

<details>
<summary><b>三个主 CLI 的完整子命令清单</b></summary>

**`tools/qt-ohos-run.py`（应用迁移，24 个）**

```text
init · scan · plan · patch · build · package · install · launch · smoke ·
verify · analyze-log · status · resume · migrate · finish · assess ·
rollback · mark-gate · mark-ui · mark-risk · draft · promote · recipes · config
```

**`tools/qt-sdk-run.py`（SDK 工程，24 个）**

```text
init · env · config · src-clone · status ·
patch-import · patch-apply · patch-list · patch-revert · patch-export · patch-mark ·
configure · build · install · verify · smoke-mark ·
release · release-list · modules · use · diff · upstream-check · forge · resume
```

**`portgraph/portgraph.py`（可移植性图谱，10 个）**

```text
ingest · clone · scan · analyze · deps · fetch · fetch-deps · stats · export · serve
```

</details>

## 目录结构

```
ohos_qt-skills/
├── SKILL.md                # ★ skill 化总入口（AI 工具直接加载整个知识库）
├── AGENTS.md               # Agent 操作规范（CLAUDE.md 为本地等价文件，不入库）
├── README.md / CHANGELOG.md / SETUP.md / CONTRIBUTING.md / SECURITY.md / LICENSE / TODO.md
├── ENV.md                  # 本地路径变量模板（kb-init 生成 ENV.local.md）
├── RELEASE-MANIFEST.yaml   # 版本可复现清单（源端 SHA + content_tree_sha256）
├── .gitcode/               # Issue 模板（知识纠错 / 能力请求 / 跨平台差异 / 文档不一致）
├── _index/                 # 索引层：_map 知识地图 · _tags · _dashboard · _task-routing · _agent-mesh
├── semantic/               # 语义知识 26 页：API 映射、窗口模型、平台限制、模块状态、35 条铁律
├── procedural/             # 程序知识 14 页：迁移工作流、Demo 生成、编译配方、Qt+CEF 指南
├── episodic/               # 情景知识 6 篇：三方库移植与 bug 复盘（SARibbon / Coin3D / 退出死锁…）
├── problems/               # 错误库 47 页：实战踩坑一错一文件，速查入口 _lookup.md
├── faults/                 # 故障库：症状 S × 根因 C × 方案 W × 跟踪单 T 图模型（17/18/15/5）
│                           #   真源 _data/*.yaml + C 页；_graph.yaml/_registry.md 自动重建
├── ohos-common-kb-public/  # 内嵌 HarmonyOS 平台通用知识 27 页（ArkTS / ArkUI / NAPI / Stage 模型…）
├── knowledge/              # 机器知识层：rules/ 18 条预扫描规则 · errors/ 42 条 QOH 模式 · adaptation/ 可行性三库
├── tools/                  # 执行层：qt-ohos-run.py · qt-sdk-run.py · faults-build.py · kb-verify-qt.py
│                           #   + qt_ohos/ qt_sdk/ 纯标准库引擎包
├── portgraph/              # 可移植性图谱子项目：CLI + port_graph/ 包 + Web 图谱 + 测试 + 文档
├── templates/              # qt-ohos-app/ 鸿蒙应用壳模板（CMake 胶水内嵌铁律 B1/B2/B10）
├── tests/                  # 引擎自测 12 用例（portgraph/ 另有 119 单测 + e2e 对账）
├── skills/                 # 5 个 Agent skills：kb-init · qt-app-porting · qt-sdk-forge · task-dispatcher · kb-iterator
└── preference/             # 预留域
```

| 目录 | 回答什么问题 |
|------|--------------|
| `semantic/` | 我知道什么？（API 映射 / 窗口模型 / 平台限制 / 铁律） |
| `procedural/` | 我怎么做？（迁移工作流 / 编译配方 / Demo 生成） |
| `episodic/` | 发生过什么？（真实迁移复盘、bug 根因记录） |
| `problems/` | 遇到这个报错怎么办？（速查优先，一错一文件） |
| `faults/` | 这个问题修了吗？归谁？怎么绕？（症状→根因→方案→跟踪单） |
| `knowledge/` | 机器读什么？（18 条规则 / 42 条错误模式 / 可行性三库） |
| `tools/` + `portgraph/` | 谁来执行？（三个 CLI + 引擎包 + 图谱工具） |
| `skills/` + `SKILL.md` | AI 怎么自动用？（skill 定义与触发词） |
| `ohos-common-kb-public/` | HarmonyOS 平台通用知识（非 Qt 特定问题优先查这里） |

## 知识库怎么用

**AI 的处理顺序是固定的**（你不用记）：

```
你的请求
  → _index/_task-routing.md              匹配任务类型，确定工作流和必读页
  → semantic/qt-harmonyos-golden-rules   扫 35 条铁律（避免已知陷阱）
  → _index/_map.md                       按 summary 判断相关性，只读需要的页
  → 沿 refs 字段追踪交叉引用              获取深度上下文
```

- **遇到报错**：先查 [problems/_lookup.md](problems/_lookup.md)，或让 AI 跑 `qt-ohos-run.py analyze-log <日志>` 做机器匹配（42 条 QOH 模式，命中条目带根因与修复指引）。
- **查某问题修没修 / 归谁 / 怎么绕**：[faults/_registry.md](faults/_registry.md) §症状索引（表现→根因）；根因分 `defect` 会修 / `limitation` 规格限制→替代方案。升级 Qt/OHOS 版本前用"按版本基线"视图做方案退役检查。
- **知识沉淀**：新问题走草稿通道（`qt-ohos-run.py draft` → `promote`；faults 走 `faults/_drafts/` + 主编六步门禁）——**未复现不合入**。

## 能力规格

> 本节是外部知识库（开发者版）的正式功能规格：能做什么、输入输出契约、版本与兼容策略。

### 输入 / 输出契约

| 输入 | 处理 | 输出 |
|------|------|------|
| 自然语言请求（喂 AI 工具） | 任务路由 → 扫铁律 → 按需加载页 → 综合 | 替换方案 + 代码 / 模块状态 / 限制 + QTBUG / 错误解决方案 / 编译配方 |
| Qt 工程目录 | portgraph 评估（第 0 步）→ qt-ohos-run 流水线 → 门禁 | 可行性判定 / 依赖角色清单与 bottle 直链 / HAP / G0-G12 门禁报告 / 知识草稿 |
| 直接浏览（人类 / Obsidian） | `_dashboard` 看全貌 → `_map` 看摘要 → 点开自包含页 | 结构化技术参考 |

### 版本与兼容策略

- **版本号**：[SemVer](https://semver.org/lang/zh-CN/) `vMAJOR.MINOR.PATCH`，版本对象 = 外部仓整包。基线 `v2.0.0`（2026-08-19），不回填 v1。
- **MAJOR**（破坏性）：删/移走用户依赖的页、目录重排致旧链接断、铁律/API 映射被证伪并反转。
- **MINOR**（内容新增）：新页/新节/新 API 映射条目/新任务类型/内嵌新 KB 或 skill。
- **PATCH**（内容修正）：typo、错误解决方案更新、Qt 参考版本 bump。
- **Pin 某版**：`git clone --branch vX.Y.Z <本仓库>`。
- **可复现性**：每版生成 [RELEASE-MANIFEST.yaml](RELEASE-MANIFEST.yaml)（源端 git SHA + `content_tree_sha256` + 页数计数）。
- **Qt 框架版本校验基准**：Qt 5.15.16（tqtc/harmonyos-5.15.16, 962aa625）/ Qt 5.12.12（tqtc/harmonyos-5.12.12, 613336de）；Qt 6.12 为官方预构建安装器。

## 本地环境配置

知识页以变量名（如 `QT5_15_OHOS_SDK`、`OHOS_SDK_NATIVE`）引用本地路径，不硬编码。运行 `skills/kb-init/` 初始化 skill 会自动生成 `ENV.local.md`（或手动把 `ENV.md` 的 `<PLACEHOLDER_*>` 替换为本机路径）。需要的东西：

- **DevEco Studio + HarmonyOS SDK**——提供 OHOS clang、sysroot、hvigorw、模拟器
- 一个已编译的 **Qt OHOS SDK**（作为应用链接的 `CMAKE_PREFIX_PATH`）
- 只有要自己重编 Qt 库时才需要：Qt 5.12/5.15 鸿蒙源码 + MinGW + Strawberry Perl（Windows）

### Qt 源码获取渠道

| 场景 | 获取方式 | 说明 |
|------|----------|------|
| **有 Qt 商业 license** | `git clone https://codereview.qt-project.org/qt/tqtc-qt5` | 最新补丁与完整历史 |
| **无 license（开源）** | https://gitcode.com/ohos-qt/qt-harmonyos-src | Qt 5.12.12 开源镜像 |
| **只需预编译 SDK** | https://gitcode.com/ohos-qt/qt-harmonyos-src/releases | Windows / macOS / HarmonyOS 多平台 SDK |
| **Qt 6.12** | Qt 官方在线安装器（勾选 HarmonyOS target） | 预构建 kit 含 libqohos QPA |

预编译 SDK 发布页包含：Windows（Desktop GL / GLES）、macOS（Desktop GL / GLES）、HarmonyOS（GLES，设备端运行）。

## FAQ

**凭什么说迁移成功了？**
成功只以 `python tools/qt-ohos-run.py verify` 的门禁结果为准：`PASS`（G0-G8 全过）才可报告成功；`PARTIAL` 只能说编译级可用；TIMEOUT 永远不是 PASS。编译通过 ≠ 迁移成功。

**我的 Qt 应用能不能移植到鸿蒙？**
先跑 portgraph 三连：`analyze`（portable / blocked / uncertain）+ `deps`（依赖角色与版本校验）+ `fetch-deps --dry-run`（bottle 直下 vs 源码编译缺口清单）。依赖 ≥3 个三方库时**禁止**人工逐个判断，以闭包分析输出为准。

**没有 Qt 商业 license 能用吗？**
能。Qt 5.12.12 有开源镜像与预编译 SDK；Qt 6.12 有官方预构建安装器（含 HarmonyOS 组件）；仅 Qt 5.15 源码线需要商业 license。

**QtWebEngine 支持吗？**
不支持。鸿蒙上用 CEF for OpenHarmony 完整平替——WebEngine→CEF API 映射、迁移方案与组件包用法见 `procedural/qt-cef-ohos-dev-guide.md`；轻量展示可先用 Qt WebView 原生桥。

## 已知限制

- portgraph 平台接口检测为正则匹配，注释中的 API 名（如 `// DestroyWindow(...)`）与同名自定义函数可能误报、虚高风险等级。
- 42 条 QOH 机器模式是 problems/ 47 页实战错误的常见子集索引；未命中的新错误走 `draft → promote` 沉淀为新模式。
- 三方库源码交叉编译不在本库内置（可对接外部 `build_in_harmonyos`，设置 `OHC_RUN` 环境变量）；本库负责依赖检测、bottle 直下与集成指引。
- Windows 上 `.so` 只能链接不能运行，须部署到 `entry/libs/arm64-v8a/` 后上设备。

## 设计理念

- **编译而非检索**——借鉴 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，把原始经验蒸馏成结构化知识页
- **分层加载**——索引层常驻，知识页按需；README 做路由，细节下沉知识页
- **文件即数据**——纯 Markdown + Git，零基础设施依赖
- **类型化记忆**——semantic / procedural / episodic / problems 四类知识 + faults 故障图
- **LLM 推理，tool 事实**——所有"成功"结论由机器门禁判定

本仓库由更大的内部工作流知识库单向裁剪生成（`audience: public` 子集），能力边界与裁剪规则见 [能力规格](#能力规格)。

## 反馈与贡献

- 发现内容错误或想补充知识：提 Issue（模板见 [`.gitcode/ISSUE_TEMPLATE/`](.gitcode/ISSUE_TEMPLATE/)，指南见 [CONTRIBUTING.md](CONTRIBUTING.md)）
- 安全问题：见 [SECURITY.md](SECURITY.md)
- 本仓库是只读派生视图，不接受直接修改内容文件的 PR

## License

[MIT](LICENSE) ｜ Copyright (c) 2026 OpenHarmony PC Developer
