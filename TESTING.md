# 测试与验证

本仓的"测试"分三层：**门禁（自动）→ 冒烟（半自动）→ 真机端到端（人工驱动 + 门禁判定）**。
任何一层没跑，就不能说"这个版本可用"。

---

## 一、自动化门禁（每次提交必跑）

```bash
python _scripts/verify.py                   # 契约 / 结构 / 引用 / 索引 / 发版清单 / 卫生（10 类检查）
python -m unittest discover -s tests -v     # 一致性 + 引擎 + 扫描（124 用例）
python tools/faults-build.py check          # 故障库真源 ↔ 派生物（error 必须为 0）
```

（`bash _scripts/verify.sh` 是同一套检查的 bash 薄壳；Windows 上直接用 `python` 形式。）

一条命令跑完全部四条（CI 用这个，退出码即结论）：

```bash
python _scripts/ci.py       # 纯 Python，Windows 无 bash 也能跑
bash _scripts/ci.sh         # 等价薄壳
```

Windows 上没有 bash 时，用 `python _scripts/verify.py` 等价执行第一条。

### 当前状态（2026-11-02，macOS 14 / Python 3.13）

| 门禁 | 结果 | 说明 |
|------|------|------|
| `verify.py` | **PASS** | 0 error / 0 warning（模板目录里 178 个历史构建产物已清理） |
| `unittest` | **OK（124 tests）** | 引擎 88 + 一致性 27 + cpp20 扫描 9 = 124（另有 portgraph 127 单测：图谱 123 + 预取 4，不在默认 discover 范围） |
| `faults-build check` | **PASS** | error=0 / warn=0 / info=7（7 条缺失跟踪单已排期到 T-0008…T-0013） |
| CLI 契约 | **PASS** | `qt-ohos-run` 24 / `qt-sdk-run` 24 / `portgraph` 10 子命令，由测试锁定 |
| 相对链接门禁 | **PASS** | `verify` C10：`](path.md)` 指向不存在的文件即 ERROR（C7 只查 wikilink） |
| 索引可达性门禁 | **PASS** | `verify` C11：每个知识页至少要出现在 `_map`/`_tags`/`_task-routing`/`_lookup`/内嵌库索引之一 |
| 仪表盘派生 | **PASS** | `_index/_dashboard.md` 由 `_scripts/gen-dashboard.py` 生成；`verify` C9 比对生成结果，手改数字即 ERROR |
| 计数收敛 | **PASS** | 数字只写在 README + `RELEASE-MANIFEST.yaml`（+ `_dashboard` 派生物视图）；SKILL/AGENTS/路由用不含数字的表述，测试反向守卫 |
| `verify` 退出码 | **PASS** | `0` PASS / `3` PARTIAL（编译链过、设备侧未完成）/ `1` FAIL；`--json` 时 stdout 是纯 JSON |
| 三档判定 | **PASS** | 编译+链接过、打包未做 → `PARTIAL`（阶段性成果）；打包失败 → `FAIL`；G0–G8 全过 → `PASS` |
| G4 产物校验 | **PASS** | `build.json` 里列的产物必须在磁盘上存在且非空；全缺 → FAIL，部分缺 → PARTIAL |
| G2 证据链 | **PASS** | `mark-risk` 必须带 `--evidence`；无证据的标记不算已处理（G2 仍 FAIL） |
| 外部构建登记 | **PASS** | `build --record-only --artifacts` / `package --record-only --hap`：不重跑，只登记并校验产物 |
| 全局参数位置 | **PASS** | `--project` 写在子命令前后等价（写在后面会打印一行说明） |
| 门禁诚实性 | **PASS** | `G2` 没跑 risk_scan 判 NOT_RUN（不因"没发现 critical"判 PASS）；`G5` 打包自称成功但无 `.hap` 判 FAIL；`G8` 未配 `bundle_name` 时最高 PARTIAL |
| `smoke` 退出码 | **PASS** | `0` 通过 / `1` 崩溃或抓取失败 / `2` 未测（install·launch 未 PASS 或日志无本应用记录） |
| CLI 冒烟 | **PASS** | 7 个 CLI 的 `--help` 全部 exit 0（含 `ohos-platform-audit.py`；Windows 下子进程强制 UTF-8，见 `_scripts/ci.py`） |
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
| 引擎 / 一致性 / 扫描用例 | 12 / 20 / 9 | 19 / 20 / 9 | **+7**（Qt 主版本识别、`.cmake` 检测、未知版本告警） |
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
| 1. 扫描 | `qt-ohos-run.py --project <工程> scan` | `build system: cmake \| qt: 5 (find_package(Qt5)) \| modules: core, gui, network, widgets \| sources: N`，随后 `Qt HarmonyOS Porting Risk Report` 按等级分组列风险（R009 `qprocess_usage`、R012 `system_tray_usage` 等，带 `文件:行号`）。判不出 Qt 主版本时这里显示 `qt: 未判定` 并打 WARNING |
| 2. 计划 | `qt-ohos-run.py --project <工程> plan` | `plan: 6 steps (auto=1 assisted=3 manual=2)`，S001…S006 逐条标注 auto/assisted/manual |
| 3. 状态 | `qt-ohos-run.py --project <工程> status` | `stage: plan` / `next: {"action": "patch"}` / `completed:` / `remaining:` 四行 |
| 4. 自动修 | `qt-ohos-run.py --project <工程> patch` | `no automatic fixes applicable`（无命中）或 `applied N fixes`，`已改动全部记入 .qt-ohos/changes.json` |
| 5. 门禁 | `qt-ohos-run.py --project <工程> verify` | `G0 Environment FAIL missing: qt_sdk_prefix or build_command`，G1 FAIL（未 scan 时没有 build files/plan），G2 NOT_RUN（没跑 risk_scan 就不能说"无 critical 风险"），G3–G12 NOT_RUN，`Result: FAIL`——未配 SDK 且未扫描时的正确结论 |
| 6. 日志诊断 | `qt-ohos-run.py analyze-log <日志>` | `Hits:` 列出命中模式与置信度，`Top hit: QOH001 (qpa_plugin_not_found)`，随后给出 cause / diagnose / fix / read |
| 7. 清单对账 | `python _scripts/gen-manifest.py --check` | `gen-manifest: 计数一致（132 页 / 124 用例）…`；普通提交上摘要会显示为"旧快照"，发版前用同脚本刷新后再 `--check --strict` |

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

### 0.1 Windows 专用预检（做错会浪费几小时）

```powershell
python --version                             # 3.10+
git config --global core.longpaths true      # tdesktop 的路径深度会超 260 字符
# 含子模块的工程（tdesktop 的 Qt 配置就在 cmake 子模块里）必须递归拉：
git clone --recursive <url> <dir>
```

- 门禁不需要 bash：用 `python _scripts/ci.py`（`ci.sh` 只是它的薄壳）。
- 工程路径里可以有空格和中文，`--project "C:\Users\张三\我的 项目"` 能直接用。
- 判不出 Qt 主版本时（Qt 配置写在未拉取的子模块里），先 `config set qt_version 6` 再 scan，
  否则会按 5.15 的模块矩阵评估。

### 1. 取代码并先跑门禁（不装环境也能跑）

```powershell
git clone -b trunk https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills
python _scripts/ci.py                       # 期望「CI: 全部通过」（124 用例）
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

#### 用 tdesktop 这类 Qt6 重型工程试跑时的预期（2026-11-02 本机实测）

| 指标 | 实测值 | 含义 |
|------|--------|------|
| 仓库规模 | 6920 文件 / 3298 个 C/C++ 源 | `scan` 在 macOS 上 12.3 秒；Windows 会慢一些 |
| Qt 主版本 | 需 Qt6（`find_package(QT NAMES Qt6 …)` 优先） | 只有 Qt5 OHOS SDK 时**在 Qt 版本前置就断了**，别急着排别的错 |
| 版本识别 | 配置写在 `cmake` 子模块里 | 非递归 clone 会显示 `qt: 未判定`，按 5.15 评估（保守）；`config set qt_version 6` 可修正 |
| 三态结论 | `UNCERTAIN` | 不是 `blocked`：模块矩阵上 Qt6 的 core/gui/network/widgets 可用 |
| 第三方 | 代码级抓到 ffmpeg、openssl、zlib；`portgraph deps` 另报 rnnoise、tde2e、wallet_engine 需源码交叉编译 | 这几个是本工程的主要工作量 |
| 平台绑定代码 | 161 critical（`win32_api` 为主） | 这些是 Windows 专用实现，移植时要按 OHOS API 重写，不是"改个宏" |
| 现实目标 | 走通 `scan → assess → plan`，再挑**一个**库（如 `lib_tl` 或 `lib_base`）编出 `.so` | 整包上真机不现实，别把"跑不完"当成工具坏了 |

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

## 五、回归触发条件

出现以下改动时，除自动化门禁外必须补跑对应验证：

| 改动 | 追加验证 |
|------|---------|
| `tools/qt_ohos/`（引擎、门禁判据） | 用一个已知可迁移的小应用跑 `verify`，确认判据未被放宽 |
| `knowledge/errors/`、`knowledge/rules/` | `analyze-log` 抽样匹配 + `faults-build check` |
| `faults/_data/`、C 页 | `faults-build build` + `check` + `review` |
| `templates/qt-ohos-app/` | 新建工程 → `qt-ohos-run.py build` 全流程 |
| `portgraph/` | `portgraph` 自带 127 单测 + 一次 `analyze` 抽样 |
| README / SKILL / AGENTS 数字 | `tests/test_kb_consistency.py`（会自动拦） |
