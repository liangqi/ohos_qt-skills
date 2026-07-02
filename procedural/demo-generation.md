---
id: procedural-demo-generation
type: procedural
domain: workflow
tags: [workflow, demo, qt, rendering, testing, opengl, project-creation]
created: 2026-06-12
updated: 2026-06-12
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration,semantic-qt-harmonyos-build,semantic-qt-harmonyos-project-structure]
summary: >
  独立 Demo 生成工作流（六步闭环）：需求理解→技术设计→工程创建→代码编写→编译验证→文档沉淀。
  适用于用户直接要求"写一个 demo"/"生成测试工程"等独立 demo 创建场景。
  区别于框架问题分析 [I] 和系统问题验证 [P] 中嵌入的复现 demo 生成。
---

# Demo 生成工作流

> 当用户要求创建一个独立的 Qt demo / 测试工程时（非 bug 复现场景），按此流程执行。

---

## 触发条件

- 用户要求"写一个 demo"、"生成 demo"、"创建一个测试工程"
- 需要验证某个 Qt 功能/渲染效果/API 用法
- 需要展示某个技术特性的示例代码
- 宣传/演示用途的 Qt 工程

**不触发的场景**（属于其他工作流）：

- 作为 bug 分析的一部分创建复现 demo → 使用 [I] `framework-issue-analysis.md`
- 作为系统问题验证的一部分创建对照 demo → 使用 [P] `commercial-qt-harmonyos-bug-triage.md`
- 迁移整个应用到鸿蒙 → 使用 [A] `qt-app-harmonyos-migration.md`

---

## 阶段一：需求理解

> **📋 TODO 同步点**：`<LOCAL_TODO>` 添加「📌 进行中」条目 → `刚启动`

明确以下信息：

| 确认项 | 说明 |
|--------|------|
| Demo 目标 | 功能验证 / 渲染效果 / API 用法展示 / 性能测试 |
| 核心功能 | 需要展示/测试的具体功能点或 API |
| 目标平台 | 桌面（Windows/macOS/Linux）还是鸿蒙（OHOS） |
| Qt 版本 | 5.12 / 5.15 / 6.x / 跨版本兼容 |
| 特殊要求 | 性能指标、视觉效果、多层嵌套、原生窗口等 |

**如果用户已给出明确需求**（如"写一个渲染 demo"），无需逐项确认，直接根据需求推断。

---

## 阶段二：技术设计

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` → `阶段一完成：需求已明确`

梳理关键技术决策：

1. **Qt 模块选择**：确定需要哪些 Qt 模块（Widgets / Quick / OpenGL / Multimedia / ...）
2. **构建系统**：qmake（.pro）还是 CMake（CMakeLists.txt）
3. **工程结构**：单文件 vs 多文件、目录组织方式
4. **技术方案**：核心功能的实现方式（如 OpenGL 用 immediate mode 还是 shader pipeline）

### 构建系统选择

| 目标平台 | 构建系统 | 理由 |
|----------|----------|------|
| 桌面（Windows/macOS/Linux） | qmake (.pro) | 简单快速，适合独立 demo |
| 鸿蒙（OHOS） | CMake | OHOS 工程标准，与胶水代码模板一致 |
| 跨平台 | CMake | 统一构建，便于后续鸿蒙化 |

---

## 阶段三：工程创建

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` → `阶段二完成：技术方案已设计`

### 3.1 确定工程目录

```
<WORK_ROOT>/lzh-skill/<INTERNAL_DEMO><demo-name>/
```

`<demo-name>` 命名规范：简短描述性名称，用 `-` 分隔单词（如 `render-layers`、`mediaplayer-duration-test`）。

### 3.2 创建工程文件

根据目标平台选择：

**桌面平台（qmake）**：
```
<INTERNAL_DEMO><demo-name>/
├── <demo-name>.pro    ← QT += 所需模块
└── main.cpp           ← 完整代码
```

**鸿蒙平台（CMake + 模板 ZIP）**：
```
<INTERNAL_DEMO><demo-name>/
├── CMakeLists.txt
├── main.cpp / main.qml
├── qml.qrc            ← 如使用 QML
└── README.md
```

> 鸿蒙工程必须使用 OHOS 模板 ZIP 创建，路径见 `ENV.md` 的 `<TEMPLATE_ZIP>`。
> 详见 [[qt-app-harmonyos-migration]] 阶段 1.2 和 [[qt-harmonyos-project-structure]]。

---

## 阶段四：代码编写

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` → `阶段三完成：工程已创建`

### 编码规范

1. **单文件优先**：demo 应尽量放在单个 `main.cpp` 中，减少文件切换
2. **兼容性**：使用 Qt 5.12 兼容的 API（`QOpenGLWidget` 而非 `QOpenGLWindow`，除非明确要求）
3. **中文注释**：关键设计决策用中文注释说明
4. **文件头注释**：包含 demo 用途、结构图、兼容版本信息
5. **有意义的视觉输出**：demo 应有直观的视觉反馈，便于判断功能是否正常

### Demo 类型与侧重点

| 类型 | 侧重点 | 示例 |
|------|--------|------|
| **功能演示** | 突出单个 API/功能的用法 | QtOhosExtras startAbility 调用 |
| **渲染测试** | 视觉效果 + 性能指标（FPS） | 多层控件叠加 + OpenGL 渲染 |
| **API 对照** | Before/After 对比 | QProcess → posix_spawnp 替换 |
| **Bug 复现** | 最小化复现代码 + 复现步骤 | 嵌入 [I] 工作流，不走此流程 |
| **性能基准** | 计时 + 数据统计 | 大量控件创建/布局性能 |

### 文件头模板

```cpp
/*
 * <demo-name> — 一句话描述
 *
 * 结构（由外到内）:
 *   MainWindow (...)
 *    └─ Layer-1 ...
 *        └─ Layer-2 ...
 *            └─ ...
 *
 * 兼容: Qt 5.12 / 5.15 / 6.x
 * 用法: qmake && make && ./<demo-name>
 */
```

---

## 阶段五：编译验证

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` → `阶段四完成：代码已编写`

### 5.1 编译

```powershell
# 桌面平台 (qmake)
cd <INTERNAL_DEMO><demo-name>
qmake <demo-name>.pro
mingw32-make.exe -j8      # Windows MinGW
# 或 make -j8             # macOS/Linux

# 鸿蒙平台 (CMake)
# 通过 DevEco Studio 或 hdc 命令行构建部署
```

### 5.2 验证清单

- [ ] 编译通过（无 warning 或仅无害 warning）
- [ ] 运行正常（视觉效果符合预期）
- [ ] 如有性能指标，FPS/计时数据正常显示
- [ ] 无内存泄漏（快速检查：持续运行 30 秒观察内存）

### 5.3 编译失败处理

如果编译失败，参考 [E] 构建排障 流程：
1. 检查 `QT +=` 是否包含所有需要的模块
2. 检查 `#include` 是否完整
3. 检查 API 兼容性（Qt 5.12 vs 5.15 vs 6.x）
4. 查阅 `problems/_lookup.md` 是否有已知编译错误

---

## 阶段六：文档与知识沉淀

> **📋 TODO 同步点**：更新 `<LOCAL_TODO>` — 从「📌 进行中」移至「✅ 已完成」

### 6.1 README（可选但推荐）

```markdown
# <demo-name>

> 一句话描述

## 目的
...

## 编译运行
...

## 结构
...
```

### 6.2 知识库更新

| 操作 | 文件 |
|------|------|
| 提交变更 | git commit（消息格式 `<type>: <简述>`） |
| 如有新发现 | 沉淀到 `episodic/` 或 `problems/` |

---

## 检查清单

- [ ] 需求已明确（目标/功能/平台/版本）
- [ ] 技术方案已设计（模块/构建系统/结构）
- [ ] 工程已创建在 `<INTERNAL_DEMO><demo-name>/`
- [ ] 代码已编写（单文件优先、兼容 5.12、中文注释）
- [ ] 编译通过
- [ ] 运行正常
- [ ] 已提交 git commit

---

## 与其他工作流的关系

| 场景 | 使用工作流 |
|------|-----------|
| 独立创建功能/渲染/性能 demo | **[Q] Demo 生成**（本流程） |
| Bug 分析中的复现 demo | [I] 框架问题分析 → 阶段一 |
| 系统问题验证中的对照 demo | [P] 系统问题验证 → Qt Demo 复现阶段 |
| 整个应用迁移到鸿蒙 | [A] 应用移植 |

---

## 供应链

> 详见 工作流供应链 §[Q] Demo 生成

| 维度 | 详情 |
|------|------|
| **上游来源** | ① 用户直接需求（"写一个 xx demo"） ② 自驱动（功能验证/渲染测试） ③ 宣传/演示需求 |
| **上游输入** | demo 目标描述、功能需求、目标平台/版本 |
| **下游接收方** | 内部使用（测试验证）/ 宣传演示 / 客户展示 |
| **交付件** | `<INTERNAL_DEMO><demo-name>/`：完整工程 + README（可选） |
| **交付件路径** | `<WORK_ROOT>/lzh-skill/<INTERNAL_DEMO>` |
| **分流规则** | 无（独立交付）；如发现框架 bug → 转入 [I]；如需鸿蒙化 → 转入 [A] |

---

## 相关上下文

- [[qt-harmonyos-project-structure]] — 工程结构（鸿蒙工程创建参考）
- [[qt-harmonyos-build]] — 构建指南（编译环境配置）
- [[qt-app-harmonyos-migration]] — 应用迁移（鸿蒙工程模板使用）
- 工作流供应链 — 工作流供应链总览

## 内容来源

| 来源类型 | 说明 |
|----------|------|
| 🛠️ 工作经验 | 从 render-layers、mediaplayer-duration-test 等实际 demo 创建经验蒸馏 |
