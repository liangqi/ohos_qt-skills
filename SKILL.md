---
name: ohos-qt-skills
description: |
  Qt for HarmonyOS 一站式知识库与自动迁移工具集。当用户要求把 Qt 应用
  迁移、移植或鸿蒙化到 HarmonyOS/OpenHarmony，评估 Qt 应用在鸿蒙上能否
  运行，分析 Qt 项目三方依赖并下载鸿蒙 arm64 交叉编译产物，排查 Qt 鸿蒙
  编译/打包/部署/运行报错，或查询 Qt API/模块/平台限制在鸿蒙的支持情况
  时，使用本 skill。
  核心能力：① portgraph 可移植性图谱——analyze 可行性判定（portable/
  blocked/uncertain）+ deps 依赖角色分类（link/build-tool/runtime/test/
  vendored 等）+ fetch-deps 依赖闭包一键下载约 6000 个鸿蒙预编译 bottle；
  ② qt-ohos-run.py 自动迁移流水线——扫描→计划→受追踪修改→编译→打 HAP→
  装机→启动→G0-G12 验证门禁；③ 知识层——35 条黄金铁律、41 条 QOH 错误
  模式机器诊断、故障库症状→根因→临时方案检索。
  触发词：鸿蒙化、移植 Qt、porting、HarmonyOS、Qt OHOS、三方依赖分析、
  交叉编译、bottle、HAP、构建报错、dlopen、QOH。
---

# ohos-qt-skills：Qt 应用鸿蒙化知识与工具集

> 设计原则：**LLM 负责推理，tool 负责事实。** 迁移成功与否不靠"看起来
> 编译过了"判断，只以机器门禁结果为准（应用迁移 G0-G12，SDK 构建
> SV0-SV8）。

本 skill 是 [ohos_qt-skills](README.md) 知识库的总入口，覆盖 Qt 应用
鸿蒙化的完整闭环：**可行性评估 → 依赖分析与下载 → 自动迁移 → 编译打包
装机 → 验证门禁 → 知识回流**。以下命令均在知识库根目录执行。

## 触发场景

- 把某个 Qt 项目**迁移 / 移植 / 鸿蒙化**到 HarmonyOS（评估或执行）
- 分析 Qt 项目的**三方依赖**，或下载鸿蒙 arm64 **交叉编译产物**
- Qt 鸿蒙**编译 / 打包 / 部署 / 运行报错**排查
- 查询 Qt **API / 模块 / 平台限制**在鸿蒙的支持情况
- 查某问题**修没修 / 归谁 / 怎么绕**（故障库）

## 使用前提

首次使用或 `ENV.local.md` 不存在时，先执行 `skills/kb-init/SKILL.md`
完成环境初始化（DevEco Studio / HarmonyOS SDK / Qt OHOS SDK / 工具链
检测、安装引导、路径配置、验证）。知识页中的路径变量（如
`QT5_15_OHOS_SDK`、`OHOS_SDK_NATIVE`）均定义在 `ENV.local.md`。

## 工作流一：Qt 应用鸿蒙化（主流程）

### Step 0 可行性评估与依赖闭包分析（portgraph，强制第 0 步）

```bash
# 首次使用：构建图数据（自动拉取 Harmonybrew 4741 formula +
# cmd-pkgs 1248 预编译包数据源，一次性）
python portgraph/portgraph.py ingest all

python portgraph/portgraph.py scan <本地工程路径>         # 或 clone <git-url>
python portgraph/portgraph.py analyze <app> --summary     # 可移植性判定
python portgraph/portgraph.py deps <app或路径>            # 依赖角色分析
python portgraph/portgraph.py fetch-deps <app> --dry-run  # 依赖闭包预览
```

判定结论：`portable`（可直接鸿蒙化）/ `blocked`（存在硬阻塞：不支持的
平台接口 / Qt 模块 / 依赖）/ `uncertain`（有未知依赖，即源码编译缺口）。

**纪律**：

- 依赖 ≥3 个三方库时**禁止**人工逐个判断可行性，以闭包分析输出为准；
- `unknowns`（无 bottle 的依赖）必须**逐项明确告知用户**——这是需要
  源码交叉编译的缺口清单；
- blocked 结论需研判 blockers 的守卫证据（无条件 `ohos-active` 命中且
  在核心路径才是硬阻塞，可选分支可放行）。

详见 `portgraph/README.md`、`portgraph/docs/deps-report.md`、
`portgraph/docs/fetch-deps.md`。

### Step 1 自动迁移流水线（tools/qt-ohos-run.py）

```bash
python tools/qt-ohos-run.py scan <项目目录>   # 预扫描 + 18 条规则风险报告
python tools/qt-ohos-run.py plan              # 迁移计划（auto/assisted/manual）
python tools/qt-ohos-run.py patch             # 白名单自动修复（受追踪）
python tools/qt-ohos-run.py config set qt_sdk_prefix <Qt OHOS SDK 路径>
python tools/qt-ohos-run.py build             # G3 编译
python tools/qt-ohos-run.py package           # G5 打 HAP
python tools/qt-ohos-run.py install           # G6 hdc 装机
python tools/qt-ohos-run.py launch            # G7 启动
python tools/qt-ohos-run.py smoke             # G8 崩溃窗口检查
python tools/qt-ohos-run.py verify            # G0-G12 门禁（唯一成功判据）
```

一键模式：`migrate <项目目录>`（自动串联，遇到需人工的壳工程生成会
暂停并给指引，模板见 `templates/qt-ohos-app/`）；跨会话恢复：
`status` / `resume --run`。

构建失败立刻机器诊断（41 条 QOH 错误模式，命中条目带根因、诊断步骤
与知识页引用）：

```bash
python tools/qt-ohos-run.py analyze-log <日志文件>
```

### Step 2 成功判据（verify 门禁）

- `PASS`（G0-G8 全过）→ 才可以报告迁移成功
- `PARTIAL` → 只能报告部分完成（编译/打包成功但未完成设备侧验证）
- `FAIL` → 报告失败 + 剩余问题（QOH 编号）
- **TIMEOUT 永远不是 PASS**

任务结束执行 `finish` 出报告；遇到新问题用 `draft "<标题>"` 沉淀草稿、
验证后 `promote QOHxxx` 转正；`recipes <项目>` 检索相似历史迁移案例
（episodic/ 相似度排序）。

## 工作流二：三方依赖分析与下载（portgraph）

### 依赖角色分析（deps）

```bash
python portgraph/portgraph.py deps <app或路径> [--json]
```

按角色回答"这个项目到底依赖什么"，每条依赖带 `文件:行号` 证据与
版本范围校验（satisfied / conflict）：

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

`fetch-deps` 自动完成：查库取直链 → 下载 → sha256 校验 → 解压到
`workspace/ohos-libs/` → Windows/NTFS 补建 `.so` 符号链接 → 输出
CMake/qmake 集成片段。manifest 每项带 status 决策表（downloaded /
already_local / covered / provided / cmd_only / need_port / test /
failed），`need_port` / `failed` 才转人工源码交叉编译。

**交叉编译集成要点**：

- CMake：`-DCMAKE_PREFIX_PATH=<bottle路径>
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`（铁律）
- qmake：`LIBS += -L<bottle>/lib -lfoo`（-l 列表由 fetch 输出）
- `.so` 在 Windows 上只能链接不能运行；部署到 `entry/libs/arm64-v8a/`
  才能上设备
- 运行时依赖必须递归拉全（fetch-deps 已处理），漏拉会在设备 dlopen 失败

## 知识检索（排障与查询）

| 想做什么 | 入口 |
|----------|------|
| 任务路由（接到请求先看） | `_index/_task-routing.md` |
| 扫 35 条铁律避已知陷阱 | `semantic/qt-harmonyos-golden-rules.md` |
| 遇到报错（第一步） | `problems/_lookup.md`（或 `analyze-log` 机器匹配） |
| 某问题修了吗 / 归谁 / 怎么绕 | `faults/_registry.md` §症状索引 |
| API 替换 | `semantic/qt-harmonyos-api-mapping.md` + `qt-harmonyos-code-patterns.md` |
| 模块支持状态 | `semantic/qt-harmonyos-modules.md` |
| 平台限制 | `semantic/qt-harmonyos-platform-limits.md` |
| 知识全貌 | `_index/_map.md`（每页一句话摘要） |

固定加载链：`_task-routing → golden-rules → _map → 按需读页 → 沿 refs
深追`。

## 子技能（skills/）

| Skill | 用途 |
|-------|------|
| `kb-init` | 环境初始化（检测依赖、安装引导、生成 ENV.local.md） |
| `qt-app-porting` | 自动迁移详情（工作流 / 门禁语义 / 人工接入点） |
| `qt-sdk-forge` | Qt SDK 编译、补丁应用与版本管理（SV0-SV8 门禁） |
| `task-dispatcher` | 多 Agent 协作调度（任务台账 / 移交信封） |
| `kb-iterator` | 知识库迭代（草稿合入门禁 / 索引再生 / 事实校验） |

多 Agent 协作契约（接口卡 / 移交信封 / 人工接入点分级）见
`_index/_agent-mesh.md`。

## 纪律红线

1. **成功只由工具判定**：应用迁移看 `verify`（G0-G12），SDK 构建看
   SV0-SV8；TIMEOUT 永远不是 PASS。
2. **禁止盲目扩写 `Q_OS_LINUX` 守卫**：鸿蒙下 `Q_OS_OHOS` 隐含
   `Q_OS_LINUX`，`#ifdef Q_OS_LINUX` 分支在鸿蒙本来就会编译——此类
   修改必须人工评审（参考 `semantic/qt-harmonyos-api.md`）。
3. **每次自动修改都被追踪**：目标项目 `.qt-ohos/changes.json` +
   `patches/`，可回滚、可评审；禁止无追踪的手改。
4. **知识回流**：新问题走 `draft` → `promote`；修改 faults 真源后必须
   跑 `python tools/faults-build.py build` 重建派生物。
5. **依赖判断不靠人肉**：≥3 个三方库的可行性以 portgraph 闭包分析
   输出为准（见 Step 0 纪律）。

## 版本基线

- 知识库版本：v2.3.0（变更记录见 `CHANGELOG.md`）
- Qt 框架校验基准：Qt 5.15.16（tqtc/harmonyos-5.15.16）/ Qt 5.12.12
  （tqtc/harmonyos-5.12.12），详见 `AGENTS.md` 尾表
