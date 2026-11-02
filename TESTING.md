# 测试与验证

本仓的"测试"分三层：**门禁（自动）→ 冒烟（半自动）→ 真机端到端（人工驱动 + 门禁判定）**。
任何一层没跑，就不能说"这个版本可用"。

---

## 一、自动化门禁（每次提交必跑）

```bash
bash _scripts/verify.sh                     # 契约 / 结构 / 引用 / 索引 / 发版清单 / 卫生（10 类检查）
python -m unittest discover -s tests -v     # 一致性 + 引擎 + 扫描（41 用例）
python tools/faults-build.py check          # 故障库真源 ↔ 派生物（error 必须为 0）
```

一条命令跑完全部四条（CI 用这个，退出码即结论）：

```bash
bash _scripts/ci.sh
```

Windows 上没有 bash 时，用 `python _scripts/verify.py` 等价执行第一条。

### 当前状态（2026-11-02，macOS 14 / Python 3.13）

| 门禁 | 结果 | 说明 |
|------|------|------|
| `verify.sh` | **PASS** | 0 error / 0 warning（模板目录里 178 个历史构建产物已清理） |
| `unittest` | **OK（41 tests）** | 引擎 12 + 一致性 20 + cpp20 扫描 9 = 41（另有 portgraph 123 单测：图谱 119 + 预取 4，不在默认 discover 范围） |
| `faults-build check` | **PASS** | error=0 / warn=0 / info=7（7 条缺失跟踪单已排期到 T-0008…T-0013） |
| CLI 契约 | **PASS** | `qt-ohos-run` 24 / `qt-sdk-run` 24 / `portgraph` 10 子命令，由测试锁定 |
| CLI 冒烟 | **PASS** | 6 个 CLI 的 `--help` 全部 exit 0（`faults-build --help` 此前返回 2，已修） |
| 知识事实复核 | **SKIP** | `kb-verify-qt.py` 需要 `ENV.local.md` 里的 SDK 路径，当前环境未配置 |

---

## 二、与 `bitfun-release` 的能力对照

`trunk` 的能力来自 `main` + `bitfun-release` 的合并，且在此之上补齐治理层。逐项对账（数值为实测）：

| 能力 | `bitfun-release` | `trunk` | 结论 |
|------|------------------|---------|------|
| Qt 侧知识页 | 93 | 94 | **+1**（恢复 229 应用调研页） |
| 内嵌平台知识 | 27 | 27 | 持平 |
| 机器层：QOH 错误模式 | 42 | 42 | 持平 |
| 机器层：R 预扫描规则 | 18 | 18 | 持平 |
| 机器层：adaptation（阻断分类/检查清单/模块） | 3 | 3 | 持平 |
| 故障图 S/C/W/T | 17/18/15/5 | 17/18/15/11 | **+**（6 张排期占位单） |
| 故障闭环检查 | 有 | 有 | 持平 |
| 迁移 CLI 子命令 | 24 | 24 | 持平（契约测试锁定） |
| SDK CLI 子命令 | 24 | 24 | 持平（契约测试锁定） |
| portgraph 子命令 | 10 | 10 | 持平（契约测试锁定） |
| 模板文件 | 71 | 71 | 持平 |
| 引擎 / 一致性 / 扫描用例 | 12 / 20 / 9 | 12 / 20 / 9 | 持平（原记 22 是 grep 误数） |
| portgraph 单测 | 123 | 123 | 持平（图谱 119 + 预取 4） |
| 仓库契约（`kb.yaml`） | 无 | **有** | **+** |
| 自检门禁（`verify.sh`） | 无 | **有**（10 类检查，含发版清单对账） | **+** |
| 根 `SKILL.md` 形态 | 自定义 | 标准 Agent Skill（frontmatter + Instructions） | **+** |
| `CLAUDE.md` | 已删除 | 携带且与 `AGENTS.md` 强一致 | **+** |
| 分支模型 / 贡献流程 | 无 | trunk / dev / release 三段式 | **+** |
| 结构性缺陷（frontmatter 破损、断链、个人路径） | 5 类 | 已修 | **+** |

结论：**功能面不减**（所有能力项 ≥ bitfun-release），治理与文档面新增。唯一未验证项是
Windows 真机端到端——见下节。

---

## 三、离线端到端（无需设备，已在本机跑通）

装上 HarmonyOS 工具链之前，先证明"执行层本身没坏"：拿一个合成 Qt 工程，跑
`scan → plan → status → patch → verify → analyze-log`。这段链路跑通，上真机才有意义；
跑不通的话，Windows 第一步就会卡在工具上，而不是卡在鸿蒙上。

**这条链路的每一步都不需要 SDK、不需要设备**（`verify` 会如实报 G0 FAIL，这是正确行为）。

| 步骤 | 命令（`--project` 指向样例工程） | 期望输出（2026-11-02 实测） |
|------|------------------------------|--------------------------|
| 1. 扫描 | `qt-ohos-run.py --project <工程> scan` | `build system: cmake \| qt modules: core, gui, network, widgets \| sources: N`，随后 `Qt HarmonyOS Porting Risk Report` 按 HIGH/MED/LOW 分组列风险（R009 `qprocess_usage`、R012 `system_tray_usage` 等，带 `文件:行号`） |
| 2. 计划 | `qt-ohos-run.py --project <工程> plan` | `plan: 6 steps (auto=1 assisted=3 manual=2)`，S001…S006 逐条标注 auto/assisted/manual |
| 3. 状态 | `qt-ohos-run.py --project <工程> status` | `stage: plan` / `next: {"action": "patch"}` / `completed:` / `remaining:` 四行 |
| 4. 自动修 | `qt-ohos-run.py --project <工程> patch` | `no automatic fixes applicable`（无命中）或 `applied N fixes`，`已改动全部记入 .qt-ohos/changes.json` |
| 5. 门禁 | `qt-ohos-run.py --project <工程> verify` | `G0 Environment FAIL missing: qt_sdk_prefix or build_command`，G1/G2 PASS，G3–G12 NOT_RUN，`Result: FAIL`——未配 SDK 时的正确结论 |
| 6. 日志诊断 | `qt-ohos-run.py analyze-log <日志>` | `Hits:` 列出命中模式与置信度，`Top hit: QOH001 (qpa_plugin_not_found)`，随后给出 cause / diagnose / fix / read |
| 7. 清单对账 | `python _scripts/gen-manifest.py --check` | `gen-manifest: 一致（121 页 / 164 用例 / <hash>…）` |

第 6 步最容易验证：往日志里塞一行 `dlopen failed: library "libqohos.so" not found`，
应当命中 QOH001，且顺着 `read:` 能打开对应的 `problems/` 页。

**已知的三个坑（本次已修）**：

- `scan <路径>` 把状态写进**目标工程**的 `.qt-ohos/`，而 `plan`/`patch` 默认读**当前目录**。
  在仓根跑 `scan ~/app` 后再跑 `plan` 会报"no migration state"。统一用
  `--project <工程>`（或在工程目录里跑），提示语已改为直接给出这个用法；
- `scan` 的位置参数此前是必填且与 `--project` 撞 dest，导致 `--project X scan` 直接
  argparse 报错——两种写法（`scan <dir>` / `--project <dir> scan`）现已等价；
- `analyze-log` 是纯日志分析，不需要工程状态；之前会先打一行"run `init` first"误导用户，
  现在只有显式传 `--project` 才尝试回写。

---

## 四、Windows 端到端实测（待执行）

目标：在一个**干净环境**上，用一个**此前没在本仓出现过的 Qt 应用**跑完整链路，
证明 `trunk` 不只是文档改造。

### 0. 环境准备（一次性）

| 项 | 要求 | 检查命令 |
|----|------|---------|
| OS | Windows 10/11 x64 | `winver` |
| Python | 3.10+ | `python --version` |
| Git | 任意近期版本 | `git --version` |
| DevEco Studio | 含 HarmonyOS SDK（API 12+） | DevEco → SDK Manager |
| hdc | 随 SDK，能连真机/模拟器 | `hdc list targets` |
| Qt OHOS SDK | 5.15（推荐）或 5.12 | 由 `qt-sdk-run.py` 编译或复用现成 |
| 磁盘 | ≥ 30 GB（Qt 源码 + 构建产物） | — |

### 1. 取代码并先跑门禁（不装环境也能跑）

```powershell
git clone -b trunk https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills
python -m unittest discover -s tests -v     # 期望 41 OK
python _scripts/verify.py                   # 期望 PASS（0 error / 0 warning）
python tools/faults-build.py check          # 期望 error=0
```

> 这一步就验证了"仓库自身健康"，与是否装了 HarmonyOS 工具链无关。

### 2. 初始化环境并生成 `ENV.local.md`

```powershell
python tools/qt-sdk-run.py init             # 或直接在 Agent 里说"初始化"
# 编辑 ENV.local.md，至少填：DEVECO_CLI / OHOS_SDK_NATIVE / QT5_15_OHOS_SDK
python tools/qt-sdk-run.py envcheck         # 或 qt-ohos-run.py verify 的前置检查
```

### 3. 选应用并做可行性评估（第 0 步，不可跳）

建议选 **Qt Widgets + 少量三方库** 的中等应用（避开 Qt WebEngine / Qt6-only / 重度 D-Bus），
例如带 SQLite、zlib、libpng 依赖的桌面工具。

```powershell
python portgraph/portgraph.py ingest all            # 首次，需联网
python portgraph/portgraph.py scan <应用路径>
python portgraph/portgraph.py analyze <app> --summary
python portgraph/portgraph.py deps <app>
python portgraph/portgraph.py fetch-deps <app> --dry-run
```

记录：**三态结论、blockers、unknowns（需源码编译的依赖）**。若结论 `blocked` 且阻断项
是硬阻塞（Qt WebEngine、必须的 D-Bus 服务等），换应用——这本身就是评估能力的一次验证。

### 4. 走迁移流水线

```powershell
python tools/qt-ohos-run.py --project <项目目录> init
python tools/qt-ohos-run.py --project <项目目录> scan
python tools/qt-ohos-run.py --project <项目目录> plan
python tools/qt-ohos-run.py --project <项目目录> patch
python tools/qt-ohos-run.py --project <项目目录> build
python tools/qt-ohos-run.py --project <项目目录> package
python tools/qt-ohos-run.py --project <项目目录> install
python tools/qt-ohos-run.py --project <项目目录> launch
python tools/qt-ohos-run.py --project <项目目录> smoke
python tools/qt-ohos-run.py --project <项目目录> verify   # ← 唯一成功判据
```

也可以直接在项目目录里执行（省略 `--project`），或一步到位 `migrate <项目目录>`。

中断就用 `status` / `resume` 续跑；每步状态都在目标项目 `.qt-ohos/` 下。

### 5. 失败时

```powershell
python tools/qt-ohos-run.py analyze-log <日志文件>
```

命中 QOH 模式后按引用读 `problems/`；若是**本仓没记录过的新问题**，走草稿流程
（`faults/_drafts/_template.md`，附复现 demo 或日志+栈），交给 `kb-iterator` 合入。

### 6. 记录结果（回填到本节下方表格）

```markdown
| 日期 | 应用 | Qt 版本 | 设备 | 可行性结论 | 门禁结果 | 耗时 | 新沉淀 |
|------|------|---------|------|-----------|---------|------|--------|
|      |      |         |      |           |         |      |        |
```

**通过标准**：`verify` 输出 G0–G12 全 PASS；或 PARTIAL 且每条未过门禁都有明确原因
（环境缺件 / 应用侧已知限制），不得有"超时/没输出"类模糊项。

---

## 四、回归触发条件

出现以下改动时，除自动化门禁外必须补跑对应验证：

| 改动 | 追加验证 |
|------|---------|
| `tools/qt_ohos/`（引擎、门禁判据） | 用一个已知可迁移的小应用跑 `verify`，确认判据未被放宽 |
| `knowledge/errors/`、`knowledge/rules/` | `analyze-log` 抽样匹配 + `faults-build check` |
| `faults/_data/`、C 页 | `faults-build build` + `check` + `review` |
| `templates/qt-ohos-app/` | 新建工程 → `qt-ohos-run.py build` 全流程 |
| `portgraph/` | `portgraph` 自带 123 单测 + 一次 `analyze` 抽样 |
| README / SKILL / AGENTS 数字 | `tests/test_kb_consistency.py`（会自动拦） |
