---
name: qt-app-porting
description: |
  Qt 应用 HarmonyOS 自动迁移。通过 tools/qt-ohos-run.py 统一 CLI 把知识库的
  迁移知识变成可执行、可恢复、可验证、可沉淀的工程闭环：
  扫描 → 风险报告 → 迁移计划 → 受追踪的自动修改 → 编译 → 打包 → 安装 →
  启动 → 崩溃检查 → 验证门禁（G0-G12）→ 报告 → 知识蒸馏。
  当用户说"把这个 Qt 项目迁移/移植/鸿蒙化到 HarmonyOS"、"自动迁移"、
  "跑一遍迁移"、"验证迁移结果"、"分析这个构建/运行日志"时触发此 skill。
---

# qt-app-porting: Qt 应用 HarmonyOS 自动迁移

> 设计原则（与知识库一致）：**LLM 负责推理，tool 负责事实。**
> Agent 不能因为"看起来编译成功了"就宣布迁移成功——成功与否只以
> `qt-ohos-run verify` 的门禁结果（G0-G12）为准。

## 何时触发

- 用户给出一个 Qt 项目目录，要求迁移 / 移植 / 鸿蒙化

- 用户要求对已迁移项目做验证（"凭什么说迁移成功了？"）

- 用户给出构建 / 运行日志要求定位错误（也可走 \[E] 构建排障，本 skill 提供机器匹配）

## 工作流（Agent 按顺序执行）

### Step 0 环境检测（G0 前置）

确认知识库环境可用（`ENV.local.md` 存在；不存在先跑 `skills/kb-init`）。

### Step 1 初始化 + 预扫描

```bash
python tools/qt-ohos-run.py scan <项目目录>
```

产出 `.qt-ohos/scan.json`：构建系统、Qt 版本/模块、源码清单、三方依赖、
**Qt HarmonyOS Porting Risk Report**（knowledge/rules/R\*.yaml 机器规则命中）。

把 Critical/High 风险读给用户，并沿每条发现的 `kb` 字段加载知识页。

### Step 2 生成迁移计划

```bash
python tools/qt-ohos-run.py plan
```

产出 `.qt-ohos/migration-plan.json`：auto / assisted / manual 三类步骤。
**manual 步骤必须由 Agent 逐条执行**，每条都带知识库引用（refs）。

### Step 3 受追踪的自动修改

```bash
python tools/qt-ohos-run.py patch
```

只做白名单修复（如 qmake `:!ohos` 作用域 B9、`CMAKE_AUTORCC` B10）。
每次修改都被追踪：`.qt-ohos/changes.json` + `originals/`（可回滚）+
`patches/000x-*.patch`（可固化、可评审）。

⚠️ **禁止盲目扩写平台守卫**：Qt 鸿蒙分支中 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`，
`#ifdef Q_OS_LINUX` 分支在鸿蒙上本来就会被编译。此类位置只能人工评审，
参考 `semantic/qt-harmonyos-api.md` 的宏顺序说明。

### Step 4 配置构建环境并执行

```bash
python tools/qt-ohos-run.py config set qt_sdk_prefix <Qt OHOS SDK 路径>
python tools/qt-ohos-run.py config set build_command "<可选：自定义构建命令>"
python tools/qt-ohos-run.py build      # G3 编译
python tools/qt-ohos-run.py package    # G5 打 HAP
python tools/qt-ohos-run.py install    # G6 hdc install
python tools/qt-ohos-run.py launch     # G7 aa start
python tools/qt-ohos-run.py smoke      # G8 崩溃窗口检查
```

每一步都有 timeout、退出码和 `.qt-ohos/logs/` 证据；**TIMEOUT 永远不是 PASS**。
构建失败时立刻分析日志：

```bash
python tools/qt-ohos-run.py analyze-log <日志文件>
```

错误模式引擎（knowledge/errors/QOH\*.yaml）给出命中的 QOH 条目、根因、
诊断步骤和对应知识页，Agent 沿 `refs` 读页修复后重新执行对应步骤。

### Step 5 验证门禁（唯一的成功判据）

```bash
python tools/qt-ohos-run.py verify
```

输出 G0-G12 门禁表。判定规则：

- `Result: PASS` → G0-G8 全过，才可以报告迁移成功

- `Result: PARTIAL` → 编译/打包成功但未完成设备侧验证，**只能报告部分完成**

- `Result: FAIL` → 报告失败 + 剩余问题（QOH 编号）

### Step 6 报告 + 知识回流

```bash
python tools/qt-ohos-run.py finish
python tools/qt-ohos-run.py draft "<新问题标题>"   # 遇到新问题时
python tools/qt-ohos-run.py promote QOHxxx         # 草稿验证后转正
```

**成功标准**：迁移结束但没产生任何可复用知识时，主动提示用户沉淀草稿。
下一次迁移可以通过 `qt-ohos-run recipes <项目>` 检索相似历史案例
（episodic/ 相似度排序）。

## 一键模式

```bash
python tools/qt-ohos-run.py migrate <项目目录>
```

自动串联 Step 1-4 的可自动化部分；遇到需要人工的 `project_generation`
（创建鸿蒙壳工程，模板见 `templates/qt-ohos-app/` 与 Qt 源码内置模板
`qtbase/src/harmonyos/templates`）会暂停并给出指引。跨会话恢复：

```bash
python tools/qt-ohos-run.py status          # 看当前停在哪个阶段
python tools/qt-ohos-run.py resume --run    # 从 checkpoint 继续
```

任务预算（防止长任务失控）：`QT_OHOS_TASK_BUDGET_SEC`、
`QT_OHOS_TASK_DEADLINE`（HH:MM），超限自动写 checkpoint 并以退出码 2 结束。

## 与其它知识库部分的关系

| 层                  | 载体                                                         |
| ------------------ | ---------------------------------------------------------- |
| Task Router        | `_index/_task-routing.md`（路由码 \[P]）                        |
| Knowledge Plane    | `semantic/` `procedural/` `episodic/` `problems/`          |
| Execution Plane    | `tools/qt-ohos-run.py` + `tools/qt_ohos/`                  |
| State Plane        | 目标项目内 `.qt-ohos/`（state/manifest/changes/evidence）         |
| Verification Plane | `verify` 门禁 G0-G12                                         |
| Learning Plane     | `knowledge/rules/` `knowledge/errors/` `knowledge/drafts/` |

## 多 Agent 接口与人工接入

通信契约见 `_index/_agent-mesh.md`（单一真源，本节只摘要；agent 名 app-porter）。

- 入站：`task-order`（dispatcher）、`assessment` + `deps-manifest`（port-assessor）、
  `sdk-release`（sdk-forge，经 `config set qt_sdk_prefix` 消费）
- 出站：`task-report`（dispatcher）、疑似框架问题线索转 framework-analyst、
  `kb-draft`（`draft` / `promote`）
- 移交一律走 ho-\*.yaml 信封 + flow.jsonl 追写；无 refs 不受理

人工接入点：签名证书与密码（H2，不落盘）；非白名单修改——尤其 `Q_OS_LINUX` 守卫类
（鸿蒙下 `Q_OS_OHOS` 隐含 `Q_OS_LINUX`）——人工评审后才 patch（H3）；verify=FAIL 且
未命中已知错误模式时是否转问题链（H1）；一键模式 `project_generation` 暂停给指引（H2）。
完整清单与分级定义见 `_agent-mesh.md` §五。

## 边界

- 本 skill 不重编 Qt 框架本身（那是 `semantic/qt-harmonyos-build.md` 的领域）

- 三方库编译可对接外部 `build_in_harmonyos`（设置 `OHC_RUN` 环境变量），
  本知识库只负责检测依赖并给出 `semantic/qt-harmonyos-third-party-libs.md` 指引

<br />
