# Qt for HarmonyOS 知识库（开发者版）

> 一个面向 **Qt 应用开发者** 的 HarmonyOS 移植参考知识库。它把 Qt for HarmonyOS 实战经验蒸馏成结构化的 Markdown 知识页，帮你在把 Qt 应用搬到鸿蒙时少踩坑、快定位。
>
> 这是 **开发者版**：由一个更大的内部工作流知识库经 `_scripts/kb-dev-edition.sh` 裁剪后生成，仅保留对应用开发者有用的技术内容，不含内部团队协作、商业支持、供应链流程，也不含 Qt 框架源码级调试方法。

---

## 这是什么 / 能帮我做什么

| 你在做 | 这里的页能帮你 |
|------|------------|
| 把一个 Qt 应用移植到鸿蒙 | 8 步迁移工作流 + 落地编译配方（打成 HAP）+ 工程结构 |
| 查某 API 在鸿蒙上怎么替换 | 12 大类 API 迁移映射 + 13 组 Before/After 代码模式 |
| 查某 Qt 模块支不支持鸿蒙 | 模块适配状态速查（核心模块全完成，WebEngine/D-Bus 不支持） |
| 查鸿蒙平台有哪些限制 | 平台限制清单（chmod/symlink/dlopen/字体 等，含 QTBUG 编号） |
| 窗口/对话框/生命周期行为不对 | 窗口模型详解 + 生命周期/关闭拦截/接续 + 35 条铁律 |
| 编译失败、部署失败、运行崩溃 | 错误库（一错一文件，按错误码/症状速查）+ 构建运行全流程 |
| 判断一个问题是不是出在 Qt 鸿蒙框架层 | 铁律 + 平台限制 + API 差异 + 错误库，帮你识别"框架问题"特征 |

> 本版聚焦 **应用鸿蒙化** 与 **应用问题分析**。它能帮你识别"这可能是 Qt 鸿蒙框架的已知行为/限制"，但不教你改 Qt 框架源码加日志定位根因——那是上游 Qt 团队的工作。

---

## 快速开始

### 首次使用：运行初始化 skill

克隆本仓库后，在你的 AI 工具中说"初始化知识库"或"帮我配置环境"，Agent 会自动执行 `skills/kb-init/` 中的初始化流程，帮你完成所有环境配置。

初始化 skill 会引导你完成：
- 检测当前环境（DevEco Studio、HarmonyOS SDK、Qt 源码等）
- 引导安装缺失依赖
- 生成 `ENV.local.md`（本地路径配置）
- 验证环境可用

### 方式一：让 AI 工具自动用（推荐）

本库靠 `CLAUDE.md` / `AGENTS.md`（内容相同）驱动 AI。进入仓库根目录打开你的工具即可：

| 工具 | 怎么接 |
|------|--------|
| Claude Code | 仓库根目录打开，自动读 `CLAUDE.md` |
| Codex / OpenCode | 仓库根目录打开，自动读 `AGENTS.md` |
| Cursor | 建 `.cursorrules`，内容：`请阅读并遵循 _index/_map.md 中定义的知识库结构` |
| Windsurf | 建 `.windsurfrules`，同上 |
| ChatGPT / 其它 | 手动上传 `_index/_map.md` + 相关知识页，或把 `CLAUDE.md` 复制进系统提示 |

接入后，直接用自然语言提问，AI 会按"任务路由 → 扫铁律 → 按需加载知识页 → 给方案"处理。遇到报错它会先查 `problems/_lookup.md`。

### 方式二：人类直接浏览

从 `_index/_dashboard.md`（仪表盘，看全貌）或 `_index/_map.md`（知识地图，每页一句话摘要）开始，按需点开各域目录下的 `.md` 文件。每个文件都是自包含的知识单元。

### 方式三：Obsidian

把此文件夹作为 Vault 打开，装 Dataview 插件可做 frontmatter 高级查询，用 Graph View 看知识关联图谱。

---

## 目录结构

```
ohos_qt-skills/
├── CLAUDE.md / AGENTS.md   # Agent 操作规范（AI 自动加载）
├── ENV.md                  # 本地路径变量（占位模板，替换为你的路径）
├── README.md               # 本文件
├── SETUP.md                # 安装指南（指向 kb-init skill）
├── CONTRIBUTING.md         # 贡献指南（如何反馈问题、贡献知识）
├── SECURITY.md             # 安全反馈入口
├── _index/                 # 索引层：_map（知识地图）/ _tags / _dashboard / _task-routing
├── semantic/               # 语义知识：API 参考与映射、平台限制、模块状态、构建/工程
├── procedural/             # 程序知识：应用迁移工作流、Demo 生成、编译配方
├── episodic/               # 情景知识：实际移植项目复盘（SARibbon/Coin3D/退出死锁 等）
├── problems/               # 错误库：实际编译/部署/运行时报错与解决方案（一错一文件）
├── ohos-common-kb-public/  # 内嵌的 HarmonyOS 平台通用知识（ArkTS、ArkUI、NAPI 等）
├── skills/                 # Agent skills（自动化脚本和工具）
│   └── kb-init/            # 初始化 skill：环境检测、依赖安装、ENV.local.md 生成
└── LICENSE
```

| 目录 | 回答 | 例子 |
|------|------|------|
| `semantic/` | 我知道什么？ | API 映射、窗口模型、平台限制、模块状态、35 条铁律 |
| `procedural/` | 我怎么做？ | 应用迁移工作流、落地编译配方（Playbook A/B）、Demo 生成 |
| `episodic/` | 发生过什么？ | 真实迁移复盘、bug 根因记录 |
| `problems/` | 遇到这个报错怎么办？ | 编译失败、dlopen 拒绝、签名不匹配（速查优先） |
| `ohos-common-kb-public/` | HarmonyOS 平台通用知识 | ArkTS、ArkUI、NAPI、Stage 模型、DevEco 工具链 |
| `skills/` | Agent 自动化脚本 | 初始化环境、配置路径 |

---

## 怎么用：接到任务后的路径

AI 的处理顺序是固定的，你不用记：

```
你的请求
  → _index/_task-routing.md   匹配任务类型，确定工作流和必读页
  → semantic/qt-harmonyos-golden-rules.md   扫 35 条铁律（避已知陷阱）
  → _index/_map.md            按 summary 判断相关性，只读需要的页
  → 沿 refs 字段追踪交叉引用     获取深度上下文
```

几个最高频入口：

| 想查 | 看哪页 |
|------|--------|
| 知识全貌 | `_index/_map.md` |
| API 替换 | `semantic/qt-harmonyos-api-mapping.md` + `qt-harmonyos-code-patterns.md` |
| 模块支持 | `semantic/qt-harmonyos-modules.md` |
| 平台限制 | `semantic/qt-harmonyos-platform-limits.md` |
| 工程结构 / 模板 / CMake | `semantic/qt-harmonyos-project-structure.md` |
| 落地编译（打 HAP） | `procedural/qt-ohos-concrete-build-recipe.md` |
| 构建运行全流程 / DevEco MCP | `semantic/qt-harmonyos-build-run-workflow.md` |
| 遇到报错 | **先读 `problems/_lookup.md`**，按错误码/症状检索 |

### 错误库怎么用

遇到编译/部署/运行时报错，第一步查 `problems/_lookup.md`：按错误码、错误信息关键字或症状检索，命中就读对应问题文件拿方案。`problems/` 记的是真实踩过的坑（CMake find_package 失败、dlopen 拒绝可写路径、QPA 插件未部署、签名不匹配 等），不是 Qt 官方文档里的平台限制——后者在 `semantic/qt-harmonyos-platform-limits.md`。

---

## 本地环境配置

知识页以变量名（如 `QT5_15_OHOS_SDK`、`OHOS_SDK_NATIVE`）引用本地路径，不硬编码。运行 `skills/kb-init/` 初始化 skill 会自动生成 `ENV.local.md`，或手动把 `ENV.md` 里的 `<PLACEHOLDER_*>` 替换为你本机路径。需要的东西：

- **DevEco Studio + HarmonyOS SDK**（API 17/20）—— 提供 OHOS clang、sysroot、hvigorw、模拟器
- **Qt 5.12 / 5.15 鸿蒙源码**（tqtc/harmonyos 分支，公开获取）—— 见 `ENV.md`「源码获取」
- **MinGW + Strawberry Perl**（Windows 编译 Qt 用）
- 一个已编译的 **Qt OHOS SDK**（作为应用链接的 `CMAKE_PREFIX_PATH`）

> 应用开发者通常拿到团队分发的预编译 Qt OHOS SDK 即可开始；只有要自己重编 Qt 库时才需要源码 + MinGW + Perl。

### Qt 源码获取渠道

根据是否有 Qt 商业 license，选择不同的获取路径：

| 场景 | 获取方式 | 说明 |
|------|----------|------|
| **有 Qt 商业 license** | `git clone https://codereview.qt-project.org/qt/tqtc-qt5` | 需要 Qt 商业 license，可获取最新补丁和完整历史 |
| **无 license（开源）** | https://gitcode.com/ohos-qt/qt-harmonyos-src | 开源代码，无需 license |
| **只需预编译 SDK** | https://gitcode.com/ohos-qt/qt-harmonyos-src/releases | 包含 Windows/macOS/HarmonyOS 多平台 SDK |

详细步骤见 `ENV.md`「源码获取渠道」小节，或运行 `skills/kb-init/` 初始化 skill 自动引导。

预编译 SDK 发布页面包含以下平台版本：

| 平台 | 渲染后端 | 说明 |
|------|----------|------|
| Windows | Desktop GL | Windows 平台开发，Desktop GL 渲染 |
| Windows | GLES | Windows 平台开发，GLES 渲染 |
| macOS | Desktop GL | macOS 平台开发，Desktop GL 渲染 |
| macOS | GLES | macOS 平台开发，GLES 渲染 |
| HarmonyOS | GLES | HarmonyOS 设备上运行，GLES 渲染 |

---

## 设计理念

- **编译而非检索** — 借鉴 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，把原始经验蒸馏成结构化知识页
- **分层加载** — 借鉴 Claude Code 的层级上下文机制，索引层始终加载，知识页按需加载
- **文件即数据** — 纯 Markdown + Git，零基础设施依赖
- **类型化记忆** — 借鉴认知科学，知识分四类 + 一个错误库

## 与源端知识库的关系

本仓库由一个更大的内部工作流知识库单向裁剪生成（见 `_scripts/kb-dev-edition.sh`）。裁剪保留 `audience: public` 的技术内容，移除：内部团队协作流程、商业支持/系统问题验证工作流、工作流供应链、Qt 框架源码级调试方法。因此本版可公开给 Qt 应用开发者使用。如发现内容问题，可在本仓库提 issue。

## Skills（Agent 自动化脚本）

本知识库提供以下 Agent skills，位于 `skills/` 目录：

| Skill | 用途 | 触发方式 |
|-------|------|----------|
| `kb-init` | 初始化知识库环境（检测依赖、安装缺失组件、生成 ENV.local.md、验证环境） | 用户说"初始化"、"配置环境"、"第一次使用"、"ENV.local.md 不存在"时自动触发 |

**首次使用**：如果用户是第一次使用本知识库，或 `ENV.local.md` 不存在，**必须**先执行 `skills/kb-init/SKILL.md` 完成初始化。

## 反馈与贡献

- 发现内容错误或想补充知识：提 Issue（见 `CONTRIBUTING.md`）
- 安全问题：见 `SECURITY.md`
- 本仓库是只读派生视图，不接受直接修改内容文件的 PR

## License

见 `LICENSE`。
