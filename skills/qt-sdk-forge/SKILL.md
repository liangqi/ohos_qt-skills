---
name: qt-sdk-forge
description: |
  Qt for HarmonyOS 本地 SDK 工程平面：编译 Qt 源码（全量/增量）、应用与追踪修改补丁、
  管理和发布维护本地 SDK 版本、定期跟踪上游版本演进并更新知识库。
  通过 tools/qt-sdk-run.py 统一 CLI（Python，Windows/macOS/Linux 原生可跑）把
  SDK 工程知识变成可执行、可恢复、可溯源、可验证的闭环：
  修改方案导入 → 补丁评审应用 → 编译 install → SV0-SV8 门禁 → 版本发布 → ENV 同步 →
  上游演进跟踪 → 补丁退役 → 知识回流。
  当用户说"编译 Qt / 重编 Qt"、"给 Qt 打补丁 / 应用这个修改方案"、
  "出一个 SDK 版本 / 出一个临时测试版本"、"切换 / 回滚 SDK 版本"、
  "看看上游有没有更新（要走编译验证时）"、"维护本地 Qt SDK"时触发此 skill。
  所有 Qt SDK 编译（不论版本）与临时测试版本产出统一由本 agent 承担。
---

# qt-sdk-forge: Qt OHOS SDK 编译·补丁·版本管理

> 设计原则（与知识库一致）：**LLM 负责推理，tool 负责事实。**
> Agent 不能因为"make 没报错"就宣布 SDK 可用——成功与否只以 SV 门禁结果为准。
> 同样，"补丁打上了"不等于"补丁被理解了"——每个导入的修改方案必须先评审再应用。

## 定位与边界

- 本 skill 是 **SDK 工程师侧的执行平面**。`qt-app-porting`（应用迁移）明确不重编 Qt
  框架——那正是本 skill 的职责：源码 + 补丁 → 可溯源的本地 SDK 版本。
- **职责入口（唯一）**：任何"编译 Qt SDK（5.12/5.15 源码编译，6.12 预构建登记）"、
  "针对一个修改出临时测试版本"的需求都路由到本 skill，由 `tools/qt-sdk-run.py` 执行。
- 上游输入：其他 agent / 人的修改方案（框架修复、诊断日志、上游 backport）。
- 下游输出：本地多版本 SDK（5.12 / 5.15 × debug/release × gl/gles 变体）、
  版本清单、知识库演进更新。
- 本 skill **不做**应用迁移、不做问题定位（那是 `framework-issue-analysis` 的事）——
  但它接收两者的产出（修改方案 / 修复验证需求）并反馈结果。

## 何时触发

- 用户要求编译 / 重编 Qt（全量或增量 install），不论版本
- 用户给出修改方案 / patch 文件，要求应用到 Qt 源码并出版本（含临时测试版本）
- 用户要求查看、切换、回滚、发布本地 SDK 版本
- 用户要求检查上游演进、验证"新版本是否修复了某问题"（需要重编验证时）
- 定期维护任务（上游跟踪、补丁栈复核、faults review 联动）

## 前置依赖

1. `ENV.local.md` 存在（不存在先跑 `skills/kb-init`）
2. 首次使用执行 `python tools/qt-sdk-run.py init`（创建 `workspace/qt-sdk/.qtsdk/`
   状态并自动桥接 ENV.local.md 的路径变量）
3. 必读知识页：
   - `semantic/qt-harmonyos-build.md`（configure 参数、skip 列表、增量编译三坑）
   - `procedural/framework-issue-analysis.md` §4.3-4.5（patch 生成与清理铁律）
   - 按需：`procedural/framework-fix-verification.md`（修复验证）、
     `problems/_lookup.md`（编译报错先查）、`faults/_registry.md`（补丁关联根因）
4. **平台/版本/源码获取问题**（在哪个平台编、编哪个版本、源码从哪来、
   无 license 怎么办、要不要预构建）：先查本 skill 的
   `references/build-matrix.md`——版本×渠道决策表、平台×工具链矩阵、
   CLI 参数与 configure 差异对照、CLI 不可用时的各平台手动等价命令都在该页
5. **Linux 支持状态**：✅ 已实测验证（Ubuntu 22.04 x86_64，2026-09-19，
   Qt 5.12.12 GLES release → SV0-SV6/SV8 PASS）。CLI 已内置全部 Linux 适配：
   - `src-clone --method opensource` 默认检出 POSIX 构建分支并自动恢复
     执行位（QOH037）；CRLF 快照会被拒绝
   - OHOS SDK 从 OpenHarmony 公开镜像获取（无需华为账号登录），需
     apiVersion ≥ 23，见 `references/build-matrix.md` §2.1（QOH041）
   - configure 内置 `-no-dbus`（QOH039）与脏构建目录指纹防护（QOH040）
   - `python` 别名由 `.qtsdk/pyshim` 自动提供（QOH038），SV0 检查
     `python3` / `python_alias`
   - 低内存机器（≤ 8GB）用 `config set jobs <N>` 限并发

## 状态平面（State Plane）

状态目录：`workspace/qt-sdk/.qtsdk/`（可用 `--home` 或 `QT_SDK_HOME` 覆盖）

```
workspace/qt-sdk/
├── .qtsdk/
│   ├── state.json        # 构建上下文：源码路径/分支/commit/变体/阶段 checkpoint
│   ├── env.json          # config set 管理（qt_src/build_root/sdk_root/jobs...）
│   ├── patches/          # 补丁库（P0001-*.patch，git diff 格式）
│   ├── registry.yaml     # 补丁登记簿（见下）
│   ├── inbox/            # ★ 外部修改方案工单（其他 agent 的输入接口）
│   │   └── <proposal-id>/
│   │       ├── proposal.yaml
│   │       ├── patches/0001-*.patch
│   │       └── notes.md
│   ├── builds/           # 每次构建：日志 + config.summary 快照
│   ├── releases/         # 发布清单：manifest-<ver>.yaml + RELEASES.md 索引
│   └── logs/             # 完整命令日志（state.json 只存尾部证据）
└── sdk/                  # SDK 输出根（目录名沿用现有惯例）
```

### 补丁登记簿 registry.yaml（每补丁一条）

| 字段 | 说明 |
|------|------|
| `id` | `P0001` 递增编号 |
| `type` | `diagnostic`（诊断日志）/ `fix`（框架修复）/ `backport`（上游回移） |
| `status` | `imported → applied → built → released → superseded / reverted` |
| `origin` | 来源工单 `proposal-id` 或 `manual` |
| `refs` | 关联 `faults/C-xxxx` / `QOHxxx` / `problems/` 页 / `QTBUG-xxxxx` |
| `base_commit` | 应用时的 qtbase commit（溯源） |
| `files` | 涉及文件清单 |
| `upstream` | 是否已提上游、单号、状态 |
| `retire_when` | 退役条件（通常是上游 fix_version 发布） |

### 外部修改方案工单（proposal.yaml，其他 agent 的输入协议）

```yaml
id: prop-20260915-001
source: framework-issue-analysis        # 或 faults-C0002 / human
type: fix                               # diagnostic | fix | backport
motivation: 修复输入法 focus 切换竞态
refs: [faults/C-0003, QTBUG-xxxxx]      # 关联知识页与跟踪单
base: tqtc/harmonyos-5.15.16@962aa625   # 基准分支与 commit
retire_when: 上游 5.15.17 发布后复核
expected_verification:                   # 预期验证方式（对应 SV7）
  demo: <复现 demo 路径>
  steps: 按 C-0003 复现步骤回归
```

> **纪律**：无 `refs` 的方案 `patch-import` 会直接拒绝（机器强制）——不可溯源的
> 补丁是未来版本管理的债务。Agent 收到无 refs 的方案时，先补全关联（问来源
> agent 或查 `faults/_registry.md`）再导入。

## 工作流（Agent 按顺序执行）

### Step 0 环境检测（SV0）

```bash
python tools/qt-sdk-run.py env
```

检查：Qt 源码树有效（`qtbase/` + `qtohosextras/`）、`OHOS_SDK_NATIVE`（含
`llvm/bin/`）、Windows 需 MinGW（`mingw32-make`）+ Strawberry Perl、cmake。
任一 FAIL 先修复（参考 `skills/kb-init/references/qt-compile-guide.md` 故障排除）。
路径不对时用 `config set` 修正（注意 Windows 侧要用 Windows 路径，
`/mnt/c/...` 是 WSL 路径）：

```bash
python tools/qt-sdk-run.py config set qt_src <Qt源码根>
python tools/qt-sdk-run.py config set ohos_sdk_native <OHOS SDK native>
```

源码缺失时获取（商业版凭据只进内存不落盘，clone 后自动从 remote 清除；
**渠道选择——版本可用性、license 要求、预构建选项——见
`references/build-matrix.md` §1 决策表**）：

```bash
python tools/qt-sdk-run.py src-clone --method commercial --version 5.15 \
  --dest workspace/qt-src/qt5.15 --user <QT_USER> --pass <QT_PASS>
# 无 license：--method opensource（GitCode 开源镜像）
```

### Step 1 源码与补丁栈盘点（SV1）

```bash
python tools/qt-sdk-run.py status
```

- `verify` 的 SV1 会机器校验：**qtbase 工作树改动 = registry 已登记补丁的文件并集**，
  发现未登记改动即 FAIL；`status` 展示补丁栈健康度
- 子模块完整性（QtOhosExtras 在子模块中）由 SV1 检查，未初始化会报
  `git submodule update --init --recursive` 提示

### Step 2 导入修改方案（外部 agent 接口）

```bash
python tools/qt-sdk-run.py patch-import <proposal-dir>
```

Agent 必须先**理解再导入**（评审清单，机器强制项已内置于 import）：

1. 读 proposal.yaml 的 `refs`，加载关联知识页（faults C 页 / problems 页），
   确认方案与根因定性一致
2. patch 文件范围：import 只解析 `+++ b/` 文件清单；**Agent 必须人工核对 patch
   仅含方案相关文件**（framework-issue-analysis §4.5 铁律——排除其他 bug 的追踪
   日志、实验代码），超范围 hunk 要求来源拆分
3. 冲突检测由 `patch-apply` 的 `git apply --check` 先行保证

```bash
python tools/qt-sdk-run.py patch-apply P0001     # 应用 + 状态推到 applied
python tools/qt-sdk-run.py patch-list            # 补丁栈总览
python tools/qt-sdk-run.py patch-revert P0001    # 回滚
python tools/qt-sdk-run.py patch-export P0001 --dest <dir>   # 导出供上游提交
python tools/qt-sdk-run.py patch-mark P0001 superseded       # 上游已修，退役
```

> **禁止盲目扩写平台守卫**：鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`，
> `#ifdef Q_OS_LINUX` 分支本来就会被编译——评审时按 `semantic/qt-harmonyos-api.md` 宏顺序说明人工确认。

### Step 3 编译（全量或增量）

**全量**（新源码树 / 换变体；configure 参数与 skip 列表按
`semantic/qt-harmonyos-build.md` 内置于 building.py，5.12 与 5.15.16 各有清单）：

```bash
python tools/qt-sdk-run.py configure --qt 5.15 --render gl --build-type release
python tools/qt-sdk-run.py build        # 超时默认 4h，--timeout 覆盖
python tools/qt-sdk-run.py install
```

**增量 + install**（日常高频：补丁后重编；直接复用上次 configure 的变体上下文）：

```bash
python tools/qt-sdk-run.py build
python tools/qt-sdk-run.py install
```

**多变体并行维护**（build 上下文按变体多槽存储：`<qt>-<render>-<build_type>`
各一槽，`active` 指针决定 build/install/verify/release 作用对象）：

```bash
python tools/qt-sdk-run.py status                          # 列出全部变体槽（* = active）
python tools/qt-sdk-run.py build --qt 5.12 --render gles --build-type debug
python tools/qt-sdk-run.py verify --qt 5.15                 # 切回 5.15 再验
```

> 未 configure 的变体切换会被拒绝并列出可用槽；旧单槽状态自动迁移为多槽。
> 注意：一个 home 仍只对应**一棵 Qt 源码树**（`qt_src` 单值 + 补丁栈共享）——
> 同时维护 5.12 和 5.15 两棵树请用 `QT_SDK_HOME` / `--home` 开两个 forge home。

> Windows 编译差距已闭合：CLI 直接 spawn `mingw32-make.exe SHELL=cmd.exe`，
> 任何宿主 shell 下都安全（bash 会吞反斜杠路径——这是知识库三坑之一，
> SHELL=cmd.exe 强制用 cmd.exe 执行 recipes）。
> 路径环境（NATIVE_OHOS_SDK / OHOS_SDK_SYSROOT / LLVM_INSTALL_DIR、
> MINGW_ROOT / PERL_ROOT 进 PATH）由 CLI 自动注入。

三坑内置（违反即门禁 FAIL）：
1. **只 build 不 install** → SV4 检查关键 so（libqohos 等）mtime 必须晚于
   install 开始时间；build 子命令完成时会显式提示
2. **bash/git-bash 直接跑 mingw32-make** → CLI 已用 SHELL=cmd.exe 规避
3. **install 后 demo 没重编** → SV7 冒烟前必须重编 demo（CLI 会提示）

每步日志、退出码、config.summary 快照存 `.qtsdk/builds/`；**TIMEOUT 永远不是
PASS**。编译失败先跑错误匹配再读页修复：

```bash
python tools/qt-ohos-run.py analyze-log <日志>     # 复用 36 条 QOH 模式
```

### Step 4 验证门禁（唯一的成功判据）

```bash
python tools/qt-sdk-run.py verify
```

| 门禁 | 判据 |
|------|------|
| SV0 | 环境就绪（源码树 / OHOS SDK native / MinGW+Perl / cmake） |
| SV1 | 源码状态已知：分支+commit+submodule 登记，qtbase 工作树改动 = 补丁栈登记 |
| SV2 | configure 退出码 0，config.summary 快照落盘 |
| SV3 | make 退出码 0（TIMEOUT ≠ PASS） |
| SV4 | install 传播：关键 so 存在且 mtime 晚于 install 开始 |
| SV5 | SDK 完整性：bin/qmake、lib/、include/、mkspecs/ |
| SV6 | 溯源一致：manifest 补丁集 = 实际 git diff，版本号 p<N> = 补丁数 |
| SV7 | 冒烟（可选）：`smoke-mark` 人工登记，或用新 SDK 走 `qt-app-porting` 的 build/smoke |
| SV8 | 发布归档：manifest 落盘 + ENV.local.md 已切换 |

```bash
python tools/qt-sdk-run.py smoke-mark --result pass --note "C-0003 demo 回归通过"
```

- `Result: PASS`（SV0-SV6 + SV8，SV7 已登记）→ 才可宣布版本可用
- `Result: PARTIAL`（SV7 SKIP）→ 编译安装成功但未冒烟，**只能报告"编译级可用"**（退出码 3）
- `Result: FAIL` → 报告失败 + 剩余问题（门禁项；编译错误走 analyze-log）

### Step 5 发布版本

```bash
python tools/qt-sdk-run.py release --note "修复 C-0003 输入法竞态"
# 临时测试版本（可含 diagnostic 补丁）：
python tools/qt-sdk-run.py release --type test --note "C-0003 修复验证用"
```

- 版本号：`<qtver>+p<N>.<yyyymmdd>`（如 `5.15.16+p3.20260915`，p = 本地补丁代数；
  同日多次发布自动加序号后缀）
- 生成 `releases/manifest-<ver>.yaml`：补丁集（id+SHA256）、base commit、
  变体全参数、SDK 目录、关键 so 快照（大小/mtime/SHA256）
- **纪律（机器强制）**：`diagnostic` 类补丁在 `--type release` 下被拒绝，
  需先 revert 或改出 `--type test` / `--allow-diagnostic`
- release 前置检查：qtbase 存在未登记改动时拒绝发布（SV1 溯源一致性）

### Step 6 版本切换与 ENV 同步

```bash
python tools/qt-sdk-run.py release-list          # 版本清单（含补丁集摘要）
python tools/qt-sdk-run.py use 5.15.16+p3.20260915
python tools/qt-sdk-run.py diff <v1> <v2>        # 补丁集/commit/参数差异
```

`use` 更新 `ENV.local.md` 对应变量（`QT5_15_OHOS_SDK` / `QT5_12_OHOS_SDK` /
`QT6_OHOS_SDK`）并写入当前 release 标记。回滚 = `use` 旧版本（SDK 目录不动，
只切指针）。

## 定期演进维护（上游跟踪）

**触发**：用户说"检查上游 / 更新版本知识"，或定期任务（建议每周）。

### 7.1 上游演进检查

```bash
python tools/qt-sdk-run.py upstream-check
```

- fetch 上游分支，产出新 commit 清单 + **watch 目录标注**
  （`qtbase/src/plugins/platforms/ohos/`、`qtbase/src/harmonyos/`、`qtohosextras/`）
- **Agent 必须阅读并理解**（不是罗列）：按"新能力 / 修复 / 破坏性变更 / 与本地补丁
  冲突"四类输出《演进报告》，存 `.qtsdk/builds/upstream-<date>.md`

### 7.2 补丁栈复核（superseded 检测）

- upstream-check 自动做**文件重叠比对**（上游新 commit × 本地 applied 补丁），
  输出重叠清单作为 superseded 候选
- Agent 对候选做语义判断（是否已被上游修复）→ 命中则用关联复现 demo 验证 →
  `patch-mark <id> superseded` → revert 补丁 → 出无该补丁的新版本
  （新版本 p 代数自动下降，SV6 保证一致）

### 7.3 faults review 联动（知识库更新闭环）

```bash
python tools/faults-build.py review
```

- 对 fix_version 到期的 T 跟踪单：用新 SDK + 该 C 页关联复现 demo，走
  `procedural/framework-fix-verification.md` 验证
- 结果登记进 C 页"版本验证记录"第一行（知识库证据门禁要求）
- 修改 `faults/_data/*.yaml` 或 C 页后必须 `python tools/faults-build.py build`
  重建派生物，ERROR 清零

### 7.4 版本基准表更新

上游基准变化时（新分支 / 新 commit / Qt6 状态推进）：
- 更新 `AGENTS.md` + `CLAUDE.md` 尾部"Qt 框架版本（校验基准）"表
- 更新相关页尾部的校验基准表（`semantic/qt-harmonyos-build.md`、
  `semantic/qt-harmonyos-qt6-status.md` 等按涉及范围）
- 有新知识沉淀时走 `draft → promote`（对齐 `qt-app-porting` 的知识回流）

## 一键模式与恢复

```bash
# 评审 → 应用 → 编译 → install → 门禁 →（--release 时）出版本
python tools/qt-sdk-run.py forge <proposal-dir> --qt 5.15 --release --type test

python tools/qt-sdk-run.py status                 # 停在哪个阶段
python tools/qt-sdk-run.py resume --run           # 从 checkpoint 继续
```

任务预算：`QT_SDK_TASK_BUDGET_SEC`、`QT_SDK_TASK_DEADLINE`（超限写 checkpoint
以退出码 2 结束，对齐 qt-app-porting 的防失控设计）。

**退出码**：0 = PASS，1 = FAIL，2 = 预算耗尽，3 = PARTIAL（编译级可用）。

**并发契约**：state.json / env.json / registry.yaml / RELEASES.md 写入经
文件锁（`<file>.lock`）+ 原子替换（tmp + os.replace），多进程并发不会损坏
文件；但读-改-写序列（如补丁 apply）不跨锁——**同一 home 同时只跑一个
forge 进程**，需要并行就用独立 home。

## 与其它知识库部分的关系

| 层 | 载体 |
|----|------|
| Task Router | `_index/_task-routing.md`（路由码 [S]） |
| Knowledge Plane | `semantic/qt-harmonyos-build`、`procedural/framework-issue-analysis`、`procedural/framework-fix-verification`、`problems/`、`faults/` |
| Execution Plane | `tools/qt-sdk-run.py` + `tools/qt_sdk/`（state / envcheck / srctree / patching / building / releasing / verify） |
| State Plane | `workspace/qt-sdk/.qtsdk/`（state/registry/inbox/builds/releases） |
| Verification Plane | SV0-SV8 门禁 |
| Learning Plane | `knowledge/drafts/`（draft/promote）、faults C 页版本验证记录、版本基准表 |

**上游协作 agent**：`framework-issue-analysis`（产出修改方案工单进 inbox）、
faults 库维护（C 页修复建议 → 工单）；**下游协作 agent**：`qt-app-porting`
（消费 SDK 版本做应用迁移与冒烟，`qt_sdk_prefix` 指向本平面产出）、
`kb-init`（ENV.local.md 同步方）。

## 边界

- 不做应用迁移（`qt-app-porting` 的领域）
- 不做问题定位与根因分析（`framework-issue-analysis` 的领域）——本 skill 只消费其结论
- 不代用户向上游提交 patch（提交包的整理走 framework-issue-analysis 阶段四；
  `patch-export` 只负责导出已清理的补丁）
- Qt 6.12 官方预构建 kit 无需编译——**安装器需登录 Qt 账号交互式安装，agent
  不能代下载**：接到 6.12 需求时必须提示用户手动安装并告知接入流程
  （安装器勾选 HarmonyOS target → `config set sdk_root <kit路径>` 登记 →
  `use` 切换；详见 README §版本获取与许可）。本 skill 对 6.12 仅做"版本登记
  + ENV 同步 + 上游状态跟踪"（`semantic/qt-harmonyos-qt6-status.md`）；
  configure 对 6.12 直接拒绝（source-buildable 版本仅 5.12 / 5.15）
