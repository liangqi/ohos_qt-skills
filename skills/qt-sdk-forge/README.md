# qt-sdk-forge — Qt OHOS SDK 编译·补丁·版本管理

Qt for HarmonyOS 本地 SDK 的工程平面：**所有 Qt SDK 编译（不论版本、不论平台）
与临时测试版本产出的统一入口**。其他 agent 给出修改方案，本 agent 负责把它变成
可溯源、可验证、可切换的 SDK 版本。

```
其他 agent（问题分析/故障库）──修改方案工单──▶ qt-sdk-forge ──SDK 版本──▶ 应用开发者
                                              │
                     ┌────────────────────────┤
                     ▼                        ▼
              上游 tqtc/harmonyos-* 分支    faults/ 知识回流
              （演进跟踪、补丁退役）        （版本验证记录、review 推进）
```

## 功能

| 职责 | 说明 |
|------|------|
| **编译** | 全量（configure→build→install）与增量 install；变体参数化：Qt 5.12/5.15 × release/debug × gl/gles；Windows/macOS/Linux/HarmonyOS 原生可跑 |
| **补丁管理** | 接收外部修改方案工单（proposal），先评审再应用；登记簿溯源（refs 关联 faults/QOH/QTBUG）；apply/revert/export/supersede 全生命周期 |
| **版本发布** | 版本号 `<qtver>+p<N>.<yyyymmdd>`（p=补丁代数，版本即溯源）；manifest（补丁集+SHA256+关键 so 快照）；`use` 切换并同步 ENV.local.md |
| **演进跟踪** | `upstream-check`：上游新 commit 报告（watch 目录标注）+ 补丁重叠比对（superseded 候选）+ faults review 联动 |

**核心纪律（机器强制）**：无 refs 的修改方案拒绝导入；diagnostic 补丁禁入
release 版本（`--type test` 放行）；发布前 qtbase 工作树必须与补丁栈登记完全
一致；成功与否只以 SV0-SV8 门禁结果为准——LLM 负责推理，tool 负责事实。

## 版本获取与许可

**有商业 license 才能拿到的源码**：Qt **5.15.16**（鸿蒙主力线，仅商业渠道）
和 Qt **5.12.12**（商业分支，快照最新）。渠道均为
`https://codereview.qt-project.org/qt/tqtc-qt5`（分支 `tqtc/harmonyos-5.15.16`
/ `tqtc/harmonyos-5.12.12`），需先在 codereview 生成 HTTP Credentials。

**无商业 license 用户可获取的开源版本**（GitCode 公开仓
`https://gitcode.com/ohos-qt/qt-harmonyos-src`，无需任何凭据）：
- Qt **5.12.12 源码**（开源快照 `qt-harmonyos-src-5.12.12-20260625`）
- Qt **5.12.12 预构建 SDK**（releases 页：Windows/macOS × Desktop GL/GLES、
  HarmonyOS × GLES）
- ⚠️ 5.15 **没有开源版本**——无 license 且需要 5.15 时无法通过开源渠道获取

| 目标 | license 要求 | agent 可自动获取？ | 命令/方式 |
|------|-------------|------------------|----------|
| 5.15.16 源码 | **商业必须** | ✅ | `src-clone --method commercial --version 5.15 --user --pass` |
| 5.12.12 源码 | 无（开源可） | ✅ | `src-clone --method opensource --version 5.12` |
| 5.12.12 预构建 SDK | 无 | ✅ | releases 下载（`skills/kb-init/scripts/download-qt-sdk.sh`） |
| 6.12 预构建 kit | 无（Qt 账号） | ❌ **必须用户手动安装** | 见下方接入流程 |

**Qt 6.12 无法由 agent 自动下载**：官方在线安装器需要登录 Qt 账号并交互式
勾选 **HarmonyOS** target，agent 不能代操作。接到 6.12 需求时，agent 必须
明确提示用户手动接入，流程：

1. 用户从 Qt 官网下载在线安装器，登录 Qt 账号
2. 自定义安装勾选 **HarmonyOS** target（装好后 kit 路径形如
   `C:\Qt\Qt6.12-beta3\6.12.0\harmonyos_arm64_v8a`，另记 host 工具链如 `mingw_64`）
3. 用户安装完成后，agent 登记接入：`config set sdk_root <kit路径>`，`use` 切换
   ENV.local.md（`QT6_OHOS_SDK` / `QT6_HOST_SDK`）

## 快速开始

```bash
# 0) 前置：知识库 ENV.local.md 已就绪（没有先跑 skills/kb-init）
python tools/qt-sdk-run.py init     # 创建 workspace/qt-sdk/.qtsdk 并桥接路径

# 1) 指路（Windows 侧用 Windows 路径，/mnt/c/... 是 WSL 路径）
python tools/qt-sdk-run.py config set qt_src <Qt源码根>
python tools/qt-sdk-run.py config set ohos_sdk_native <OHOS SDK native>

# 2) 编译一个版本（平台无关；源码获取见 references/build-matrix.md §1）
python tools/qt-sdk-run.py configure --qt 5.15 --render gl --build-type release
python tools/qt-sdk-run.py build && python tools/qt-sdk-run.py install
python tools/qt-sdk-run.py verify          # SV0-SV8 门禁
python tools/qt-sdk-run.py release --note "首次 5.15.16"
python tools/qt-sdk-run.py use <version>   # 同步 ENV.local.md
```

**针对一个修改出临时测试版本**（其他 agent 的修改方案 → SDK）：

```bash
python tools/qt-sdk-run.py forge <proposal-dir> --qt 5.15 --release --type test
```

## 命令速查

| 领域 | 命令 |
|------|------|
| 环境 | `init` · `env`（SV0 检测）· `config set/get/show` · `src-clone --method commercial\|opensource --version 5.12\|5.15` |
| 补丁 | `patch-import <dir>` · `patch-apply/revert <id>` · `patch-list` · `patch-export <id> --dest` · `patch-mark <id> <status>` |
| 编译 | `configure --qt --render --build-type` · `build` · `install`（均可 `--qt` 切换变体槽） |
| 验证 | `verify`（SV0-SV8）· `smoke-mark --result pass\|fail` |
| 版本 | `release [--type release\|test]` · `release-list` · `use <ver>` · `diff <v1> <v2>` |
| 演进 | `upstream-check` |
| 流程 | `forge <dir> [--release]` · `status` · `resume --run` |

退出码：`0` PASS / `1` FAIL / `2` 预算耗尽 / `3` PARTIAL（编译级可用）。
任务预算：`QT_SDK_TASK_BUDGET_SEC`、`QT_SDK_TASK_DEADLINE`。
多变体：build 上下文按 `<qt>-<render>-<build_type>` 多槽存储，`status` 列出
（`*` = active）；同时维护 5.12/5.15 两棵源码树用 `QT_SDK_HOME`/`--home` 开
独立 home。

## 修改方案工单（其他 agent 的输入协议）

```
<proposal-dir>/
├── proposal.yaml   # id / source / type(diagnostic|fix|backport) / motivation /
│                   # refs(必填，关联 faults/C-xxxx、QOHxxx、QTBUG) / base / retire_when
├── patches/0001-*.patch   # unified diff，相对 qtbase 子仓根
└── notes.md        # 来源 agent 的推理说明
```

导入即机器校验：refs 缺失拒绝、patch 必须是合法 diff、`git apply --check`
先行防冲突。补丁状态机：`imported → applied → built → released → superseded/reverted`。

## 验证门禁 SV0-SV8

| 门禁 | 判据 |
|------|------|
| SV0 | 环境就绪（源码树 / OHOS SDK native / MinGW+Perl / cmake） |
| SV1 | 源码状态已知：qtbase 工作树改动 = 补丁栈登记 |
| SV2/SV3 | configure / make 退出码 0（TIMEOUT ≠ PASS） |
| SV4 | install 传播：关键 so（libqohos 等）mtime 晚于 install 开始 |
| SV5 | SDK 完整性：qmake / lib / include / mkspecs |
| SV6 | 溯源一致：manifest 补丁集 = git diff，版本号 p<N> = 补丁数 |
| SV7 | 冒烟（可选）：`smoke-mark` 或对接 qt-app-porting |
| SV8 | 发布归档：manifest + ENV.local.md 已切换 |

`PASS` 才可宣布版本可用；`PARTIAL`（SV7 SKIP）只能报告"编译级可用"。

## 状态目录

```
workspace/qt-sdk/.qtsdk/     # 可用 QT_SDK_HOME / --home 覆盖；写入门禁：文件锁+原子替换
├── state.json   env.json    # 状态机 / 本地配置
├── registry.yaml            # 补丁登记簿
├── patches/  inbox/         # 补丁库 / 外部工单
├── builds/  releases/  logs/  # 构建证据 / 版本清单 / 完整日志
```

并发契约：锁防文件损坏，不防读-改-写丢更新——**同一 home 同时一个 forge 进程**。

## 文档索引

| 文档 | 内容 |
|------|------|
| [SKILL.md](SKILL.md) | Agent 操作手册：工作流 Step 0-6、定期演进维护、纪律与边界 |
| [references/build-matrix.md](references/build-matrix.md) | 平台 × 版本 × 源码获取决策表（含商业/开源渠道、凭据流程、各平台工具链、configure 差异、手动等价命令） |
| `semantic/qt-harmonyos-build.md` | 编译知识页（configure 原文、skip 列表、增量编译三坑） |
| `procedural/framework-issue-analysis.md` | patch 生成与清理铁律（§4.3-4.5） |
| `skills/kb-init/` | 环境初始化（DevEco 安装、系统依赖、ENV.local.md 生成） |

## 边界

- 不做应用迁移（`qt-app-porting` 的领域）、不做问题定位（`framework-issue-analysis` 的领域）
- Qt 6.12 为官方预构建，**安装器需用户手动执行**（agent 不能代下载），本 agent 仅做登记/切换/跟踪；`configure --qt 6.12` 直接拒绝
- 一个 home 对应一棵 Qt 源码树（`qt_src` 单值 + 补丁栈共享）；多树用多 home
