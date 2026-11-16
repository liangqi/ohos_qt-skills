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

⚠️ **禁止盲目扩写平台守卫**：鸿蒙分支上 `Q_OS_LINUX` **本来就是成立的**
（Qt 6.12+ 定义 `Q_OS_HARMONY` 并由它推出 `Q_OS_LINUX`，Qt 5.15 kit 另外还有
`Q_OS_OHOS`），`#ifdef Q_OS_LINUX` 分支在鸿蒙上会被编译。此类位置只能人工评审，
参考 `semantic/qt-harmonyos-golden-rules.md` G3 与宏顺序说明。

### Step 4 配置构建环境并执行

先体检，再配置——**不要**跳过 doctor 直接 `build`，Qt6 预构建 kit 缺任何一件
都会失败得看不出原因：

```bash
python tools/qt-ohos-run.py doctor     # cmake/make/Qt kit/OHOS native SDK/hvigor/JDK/hdc/设备
```

Qt 6 预构建 kit 与 Qt 5.15 套件是两套完全不同的构建配方：Qt6 必须给
`qt_host_sdk`（宿主 kit）+ `ohos_sdk_native`，`build` 会自动带
`CMAKE_TOOLCHAIN_FILE=<kit>/lib/cmake/Qt6/qt.toolchain.cmake`、
`QT_CHAINLOAD_TOOLCHAIN_FILE=<native>/build/cmake/ohos.toolchain.cmake`、
`QT_HOST_PATH`；`package` 会自己走 `_make_hap` / `harmonydeployqt6`，
不再要求你手写打包命令。完整配方与五个 hvigor 环境变量见
`procedural/qt6-ohos-windows-cli-deploy.md`。

```bash
python tools/qt-ohos-run.py config set qt_sdk_prefix  <kit>/harmonyos_arm64_v8a
python tools/qt-ohos-run.py config set qt_host_sdk    <kit>/mingw_64          # Qt6 必填
python tools/qt-ohos-run.py config set ohos_sdk_native <sdk>/native          # Qt6 必填
python tools/qt-ohos-run.py config set deveco_path    <DevEco Studio 安装目录> # hvigor/JDK/SDK 从这里推
python tools/qt-ohos-run.py config set bundle_name    com.example.app         # G8 日志过滤
python tools/qt-ohos-run.py config set compatible_sdk "5.0.0(12)"             # 与 build-profile 对齐
python tools/qt-ohos-run.py build      # G3：交叉配置 + cmake --build
python tools/qt-ohos-run.py package    # G5：自动 _make_hap / harmonydeployqt6 + HAP 依赖闭包校验
python tools/qt-ohos-run.py sign       # 可选：devecocli 生成签名材料并写 build-profile
python tools/qt-ohos-run.py install    # G6 hdc install（路径自动转本机原生写法）
python tools/qt-ohos-run.py launch     # G7 aa start（ability 从 module.json5 的 mainElement 读）
python tools/qt-ohos-run.py smoke      # G8 崩溃窗口检查
python tools/qt-ohos-run.py smoke-interact   # G10 机器取证：截图 → 点击 → 再截图比对
```

每一步都有 timeout、退出码和 `.qt-ohos/logs/` 证据；**TIMEOUT 永远不是 PASS**。

`.qt-ohos/env.json` 的键（全部可 `config set`，缺省值见括号）：

| 键 | 作用 | 缺省 |
|---|---|---|
| `qt_sdk_prefix` | Qt for OHOS SDK 前缀（Qt5 走 `-DCMAKE_PREFIX_PATH`，Qt6 从中发现 toolchain） | — |
| `qt_host_sdk` | Qt6 宿主 kit（`mingw_64`），转 `QT_HOST_PATH`；缺了 configure 直接 FAIL | — |
| `ohos_sdk_native` | OHOS native SDK，转 `OHOS_SDK_NATIVE` + `-DOHOS_ARCH` | — |
| `generator` / `make_program` | 生成器（Windows 默认 `MinGW Makefiles`，**Ninja 在沙箱里会空转**） | 按平台推 |
| `build_cwd` | 构建目录的父目录（CMake 工程在子目录时给它） | 工程根 |
| `build_command` | 整条自定义构建命令（给了就不用内置分支） | — |
| `cmake` / `build_dir` / `cmake_args` | cmake 分支的可调项；`cmake_args` 给一条命令行字符串，G3 按 shell 规则切分 | `cmake` / `build-ohos` / 空 |
| `package_target` | 打包目标名（缺省 `<target>_make_hap`） | 自动 |
| `harmonyos_build` / `package_dir` | 打包落点（Qt6 缺省 `<build_dir>/harmonyos-build`） | 自动探测 |
| `package_command` | 自定义打包命令（逃生舱，给了就不走内置两条路径） | 内置 |
| `hvigor` / `java_home` / `deveco_sdk_home` / `hvigor_home` / `npm_cache` | hvigor 五件套；前三个缺省从 `deveco_path` 推，后两个缺省落 `.qt-ohos/` 下的可写目录 | 自动 |
| `hap_glob` | HAP 产物匹配；`-signed` 优先 | `**/build/**/*.hap` |
| `hap_allowed_libs` | 允许不打包的 soname 前缀（默认系统库白名单之外的一切都必须进 HAP） | 空 |
| `bundle_name` | **G8 日志按它过滤**；不填则抓全设备缓冲，G8 最高只能 PARTIAL | 空 |
| `ability_name` | 启动的 ability；缺省从 `module.json5` 的 `mainElement` 读（Qt6 是 `QAbility`） | 自动 |
| `process_name` | G8 的第二个过滤词（鸿蒙进程名常是 bundle 最后一段，缺省就用那一段） | bundle 末段 |
| `compatible_sdk` | 与 `build-profile.json5` 的 `compatibleSdkVersion` 比对，打包前自动对齐并拦下不一致 | SDK 真值 |
| `crash_wait_sec` | 启动后观察崩溃的秒数 | 8 |
| `hdc` / `devecocli` | 工具路径（不在 PATH 时给绝对路径） | PATH 查找 |
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
