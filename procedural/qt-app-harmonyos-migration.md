---
id: procedural-qt-app-harmonyos-migration
type: procedural
domain: workflow
tags: [workflow, qt, harmonyos, porting, migration, ohos]
created: 2026-06-02
updated: 2026-06-08
status: active
audience: public
refs: [semantic-qt-harmonyos-api-mapping,semantic-qt-harmonyos-build-run-workflow,semantic-qt-harmonyos-code-patterns,semantic-qt-harmonyos-lifecycle,semantic-qt-harmonyos-porting-workflow,semantic-qt-harmonyos-project-structure,semantic-qt-harmonyos-window-model]
summary: >
  Qt应用鸿蒙化迁移工作流：评估可行性→创建工程结构→按8步决策树逐步迁移→编译验证→知识积累。
  将其他平台的Qt应用迁移到HarmonyOS平台的端到端流程。
---

# Qt 应用鸿蒙化迁移

> 将其他平台（Windows/Linux/macOS/Android/iOS）的 Qt 应用迁移到 HarmonyOS 平台的端到端流程。

---

## 触发条件

- 收到新的 Qt 应用鸿蒙化迁移任务
- 需要将已有 Qt 项目移植到鸿蒙平台
- 评估某个 Qt 应用的鸿蒙化可行性

---

## 阶段一：评估与准备

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` 中该任务的「进展」列 → `阶段一完成：可行性评估已通过，项目目录和工程已创建`

### 1.1 可行性评估

| 评估项 | 检查内容 | 参考 |
|--------|----------|------|
| Qt 版本 | 应用使用的 Qt 版本（5.12 / 5.15） | [[qt-harmonyos-modules]] |
| 模块依赖 | 检查使用的 Qt 模块是否在鸿蒙支持 | [[qt-harmonyos-modules]] |
| 平台 API | 是否有深度平台绑定（如 D-Bus, Win32 API） | [[qt-harmonyos-api-mapping]] |
| UI 复杂度 | 窗口数量、模态对话框、全屏需求 | [[qt-harmonyos-window-model]] |
| 子进程 | 是否依赖 QProcess 或 system() | [[qt-harmonyos-api-mapping]] 第1节 |
| 三方库 | 是否依赖需要交叉编译的 C/C++ 库 | [[qt-harmonyos-third-party-libs]] |

**输出**：可行性报告（可迁移 / 有风险项 / 不可迁移）

### 1.2 创建项目目录

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` 中该任务的「进展」列 → `阶段一进行中：项目目录已创建，模板解压中`

**每个迁移项目在 `<WORK_ROOT>/project` 下独立建文件夹**（路径见 `ENV.md`）：

```bash
# 创建项目目录（以原始应用名 + -ohos 命名）
mkdir -p "<MIGRATION_PROJECT_ROOT>/<app-name>-ohos"
```

**目录命名规范**：
- 格式：`<原始应用名>-ohos`（如 `calculator-ohos`、`notepad-ohos`）
- 全部小写，空格替换为短横线
- 项目文件夹内即为完整的鸿蒙工程结构

### 1.3 准备工程结构（解压胶水代码模板）

> **⚠️ 核心原则：鸿蒙工程必须从官方胶水代码模板 ZIP 解压生成，禁止手动创建目录结构。**
> 模板 ZIP 包含完整的 ArkTS 胶水代码、build-profile 配置、qEmbeddedUiExtensionHost 模块等，
> 手动创建极易遗漏关键文件或配置错误。

**获取模板**（模板 ZIP 路径见 `ENV.md` 的 `<TEMPLATE_ZIP>`），解压到项目目录 `<WORK_ROOT>/project/<app-name>-ohos/`：

```bash
# 方式一：从本地已有 ZIP 解压到项目目录
python3 -c "import zipfile; zipfile.ZipFile('ohostemplateforqtapplication_*.zip').extractall('<MIGRATION_PROJECT_ROOT>/<app-name>-ohos')"

# 方式二：从内部 Gerrit 下载最新版
curl -s "http://<QT_INTERNAL_GERRIT>/template/" \
  | grep -o 'ohostemplateforqtapplication_[0-9]*\.zip' \
  | sort -r | head -1
curl -O "http://<QT_INTERNAL_GERRIT>/template/ohostemplateforqtapplication_YYYYMMDD.zip"
```

**解压后得到的工程结构**（场景一：从零创建）：

```
<解压后的工程根目录>/
├── entry/
│   ├── src/main/
│   │   ├── cpp/                      # ★ 在此编写 Qt C++ 代码和 CMakeLists.txt
│   │   └── ets/
│   │       ├── entryability/         # ArkTS 胶水代码（模板已生成，勿动）
│   │       ├── pages/                # ArkTS 页面
│   │       └── common/
│   │           └── QtAppConstants.ets # ★ 配置 APP_LIBRARY_NAME
│   ├── build-profile.json5           # 模块级构建配置
│   └── libs/arm64-v8a/               # Qt 运行时库（需填充）
├── qEmbeddedUiExtensionHost/         # 跨进程嵌入模块（模板已生成）
├── build-profile.json5               # 项目级构建配置
├── AppScope/app.json5                # 应用包名 bundleName
└── local.properties                  # SDK 路径
```

**解压后还需要做的事情**：
1. 在 `entry/src/main/cpp/` 中编写 Qt C++ 源码和 `CMakeLists.txt`
2. 配置 `QtAppConstants.ets` 的 `APP_LIBRARY_NAME`（必须与编译产物库名一致）
3. 配置 `entry/build-profile.json5` 的 `CMAKE_PREFIX_PATH`（指向 Qt SDK）
4. 将 Qt 运行时库（`libqohos.so` 等）填充到 `entry/libs/arm64-v8a/`
5. 手动复制 `libqohosstyle.so` 到 `libs/arm64-v8a/styles/`

**场景二（已有工程鸿蒙化）**：将解压后的模板放入 `HarmonyOS/` 子目录，`entry/build-profile.json5` 的 `path` 用**绝对路径**指向根目录 CMakeLists.txt。

> 详细目录结构和配置说明见 [[qt-harmonyos-project-structure]]。

### 1.4 关键 CMake 配置

```cmake
# 1. 交叉编译搜索路径
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)

# 2. 链接 Qt 模块
find_package(Qt5 REQUIRED COMPONENTS Core Gui Widgets)

# 3. 生成共享库（鸿蒙要求）
add_library(myapp SHARED ${SOURCES})

# 4. 链接 QPA 插件
target_link_libraries(myapp PRIVATE Qt5::QOhosPlatformIntegrationPlugin)
```

---

## 阶段二：逐步迁移（8 步决策树）

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` 中该任务的「进展」列 → `阶段二进行中：8步迁移第N步`（每完成一步更新一次）

按 [[qt-harmonyos-porting-workflow]] 的 8 步决策树逐项处理：

### Step 1：平台 API 扫描

```bash
# 扫描源码中的平台绑定 API
grep -rn "QProcess\|QDesktopServices\|system(\|exec(" src/
grep -rn "chmod\|symlink\|dlopen" src/
grep -rn "winId\|setMask\|showFullScreen" src/
```

对扫描结果进行分类，确定每个 API 的替换方案。

### Step 2：API 映射替换

按 [[qt-harmonyos-api-mapping]] 的 12 大类逐一替换：

1. **进程管理**：`QProcess` → `QtOhosExtras::startNoUiChildProcess` / `startAbility`
2. **应用间通信**：`QDesktopServices::openUrl` → `startAbility(want)`
3. **窗口管理**：独立 QDialog → 设置 parent 或 tagSubWindow
4. **文件系统**：移除 `setPermissions`、`symlink` 调用
5. ... 逐项处理

### Step 3：窗口适配

- 所有独立 QDialog 设置 transientParent
- 检查模态对话框使用方式
- 处理全屏/浮窗/最小化等特殊需求
- 参考 [[qt-harmonyos-window-model]]

### Step 4：生命周期适配

- 实现 `closeEvent()` 的 3 级关闭拦截
- 处理 Ability 前后台切换
- 实现状态保存/恢复（如需要接续）
- 参考 [[qt-harmonyos-lifecycle]]

### Step 5：平台限制处理

检查 [[qt-harmonyos-platform-limits]]，确保代码不触碰：
- chmod / fchmod（用 `#ifndef Q_OS_OHOS` 守卫）
- symlink（用文件拷贝替代）
- pthread_cancel（改用协作式终止）
- 系统路径访问（沙箱限制）

### Step 6：构建系统适配（配置已解压模板）

> 工程模板已在阶段 1.2 解压生成，本步骤聚焦于**配置**而非创建。

- 编写 `entry/src/main/cpp/CMakeLists.txt`（交叉编译配置、Qt 模块链接、QPA 插件）
- 配置 `entry/build-profile.json5` 的 `CMAKE_PREFIX_PATH`（指向 Qt SDK）
- 配置 `QtAppConstants.ets` 的 `APP_LIBRARY_NAME`（与 CMake `add_library` 目标名对应）
- 填充 Qt 运行时库到 `entry/libs/arm64-v8a/`（`libqohos.so` + `libqohosstyle.so`）
- 配置 `AppScope/app.json5` 的 `bundleName`
- 参考 [[qt-harmonyos-project-structure]]

### Step 7：鸿蒙增强功能（可选）

- 深色模式适配：`setColorThemeMode(FollowSystemSetting)`
- 分享功能：`ShareKit::shareDataWithShareKit()`
- 应用接续：`continueRequestReceived` 信号
- Want 交互：处理外部传入的 URI/参数

### Step 8：模块级验证

- 逐模块编译验证
- 逐功能运行验证
- 参考 [[qt-ohos-project-analyzer-workflow]]

---

## 阶段三：编译验证

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` 中该任务的「进展」列 → `阶段三完成：编译验证通过`

### 3.1 构建

参考 [[qt-harmonyos-build-run-workflow]]：

1. 通过 DevEco MCP 工具链构建
2. 解决编译错误（参考构建失败排查四步法）
3. 生成 .hap 包

### 3.2 部署运行

1. 部署到模拟器或真机
2. 功能逐项验证
3. 性能基本测试

### 3.3 常见问题

| 问题 | 排查方向 |
|------|----------|
| 编译找不到头文件 | CMAKE_FIND_ROOT_PATH_MODE_PACKAGE |
| 链接未定义符号 | 缺少 Qt 模块依赖 |
| 运行时黑屏 | XComponent 初始化 / 窗口 tagging |
| 崩溃 | 生命周期时序 / 空指针 |

---

## 阶段四：知识积累

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` — 将此任务从「📌 进行中」移至「✅ 已完成」，填写完成日期和迁移结果摘要

### 4.1 记录迁移经验

**每次迁移后**，总结以下内容：

1. **遇到的新问题**：知识库中没有覆盖的场景
2. **有效的解决方案**：验证有效的代码模式
3. **踩过的坑**：浪费时间的错误方向
4. **更新的映射关系**：新发现的 API 替换

### 4.2 更新知识库

- 新的 API 映射 → 更新 [[qt-harmonyos-api-mapping]]
- 新的代码模式 → 更新 [[qt-harmonyos-code-patterns]]
- 新的平台限制 → 更新 [[qt-harmonyos-platform-limits]]
- 执行错误 → 创建 `problems/` 条目
- 项目经验 → 创建 `episodic/` 条目

---

## 检查清单

- [ ] 可行性评估完成（模块依赖、平台 API、UI 复杂度）
- [ ] 项目目录已创建于 `<WORK_ROOT>/project/<app-name>-ohos/`
- [ ] 胶水代码模板 ZIP 已解压至项目目录
- [ ] 8 步决策树逐项处理
- [ ] 编译通过
- [ ] 部署运行验证通过
- [ ] 迁移经验已记录到知识库

---

## 供应链

> 详见 工作流供应链 §[A] 应用移植

| 维度 | 详情 |
|------|------|
| **上游来源** | ① 商业 Qt 客户的鸿蒙化迁移需求 ② 内部宣传 demo 需求 ③ 自驱动（评估新场景可行性） |
| **上游输入** | 原始 Qt 工程/源码、目标功能需求、Qt 版本信息 |
| **下游接收方** | **商业 Qt 客户** / 内部（宣传 demo） |
| **交付件** | 可行性评估报告 → 迁移后的鸿蒙工程 → 编译产物 (.hap) |
| **交付件路径** | `<WORK_ROOT>/project/<app-name>-ohos/`（见 `ENV.md`） |
| **分流规则** | 无；**知识积累**：每次迁移后更新 KB（API 映射 → `api-mapping.md`、代码模式 → `code-patterns.md`、问题经验 → `problems/`） |

---

## 相关上下文

- [[qt-harmonyos-porting-workflow]] — 8 步决策树详细版
- [[qt-harmonyos-api-mapping]] — 12 大类 API 映射表
- [[qt-harmonyos-code-patterns]] — Before/After 代码模式
- [[qt-harmonyos-lifecycle]] — 生命周期处理
- [[qt-harmonyos-window-model]] — 窗口模型
- [[qt-harmonyos-project-structure]] — 工程结构
- [[qt-harmonyos-build-run-workflow]] — 构建运行
- [[qt-harmonyos-platform-limits]] — 平台限制
- 工作流供应链 — 工作流供应链总览（上下游关系和对接人清单）

## 内容来源

| 来源类型 | 说明 |
|----------|------|
| 🛠️ 工作经验 | Workflow design, checklists, grep patterns, debugging table, knowledge accumulation process — all from practical Qt-for-HarmonyOS migration experience |
| 📖 Wiki | Qt Wiki pages (wiki.qt.io/Qt_for_HarmonyOS/*): module support lists, CMake cross-compile guide, user development guide, API compatibility notes — accessed indirectly through referenced semantic pages |
| 🔍 框架源码 | Qt framework internals: QOhosPlatformIntegrationPlugin CMake target, QPA plugin architecture, closeEvent root cause mechanism, QOhosAbilityContext signal names |
| 📦 导出接口 | QtOhosExtras public API surface: startNoUiChildProcess, startAbility, setColorThemeMode, ShareKit::shareDataWithShareKit, continueRequestReceived, tagWindowOrWidgetAsSubWindowOf |
| 📄 华为官方文档 | HarmonyOS platform concepts: Ability/Want model, sandbox constraints, ShareKit framework, application continuation — underlying platform context |

### Qt 框架版本（校验基准）

| 版本 | 分支 | Commit | 日期 |
|------|------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |
| QtOhosExtras 5.15 | tqtc/harmonyos-5.15.16 | b60937d5 | 2026-04-19 |
| QtOhosExtras 5.12 | tqtc/harmonyos-5.12.12 | a802177c | 2026-05-25 |

---

## 参考来源

- [Qt for HarmonyOS (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS) — 整体架构和模块状态
- [API Compatibility Notes (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS/api_inconsistencies_on_harmonyos) — API 差异详情
- [User Development Guide (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide) — 开发指南系列
- [Building Qt for HarmonyOS (Qt Wiki)](https://wiki.qt.io/Building_Qt_for_HarmonyOS) — 构建配置
