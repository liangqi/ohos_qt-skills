# Qt for HarmonyOS 知识库（开发者版）

> 一个面向 **Qt 应用开发者** 的 HarmonyOS 移植参考知识库。它把 Qt for HarmonyOS 实战经验蒸馏成结构化的 Markdown 知识页，帮你在把 Qt 应用搬到鸿蒙时少踩坑、快定位。
>
> 这是 **开发者版**：由一个更大的内部工作流知识库经 `_scripts/kb-dev-edition.sh` 裁剪后生成，仅保留对应用开发者有用的技术内容，不含内部团队协作、商业支持、供应链流程，也不含 Qt 框架源码级调试方法。
>
> **当前版本**：v2.2.1（2026-08-29）｜ [变更日志](CHANGELOG.md) ｜ [能力规格](#能力规格)


加入项目：
邀请您成为 AtomGit ohos_qt-skills 项目开发者
邀请链接: https://gitcode.com/invite/link/2e56b63b436047228fac


---

## 能力规格

> 本节是外部知识库（开发者版）的正式功能规格：**能**做什么、输入输出契约、版本与兼容策略。
> 版本对象 = 外部仓整包（Qt 公开子集 + 内嵌 ohos-common-kb + kb-init skill + 根文档），不是单个 KB。

### 功能清单

本知识库覆盖 **12 类公开任务**（路由码见 `_index/_task-routing.md`）：

| 路由码 | 任务 | 入口页 | 预期输出 |
|------|------|--------|---------|
| [A] | 应用移植到鸿蒙 | `procedural/qt-app-harmonyos-migration` + `semantic/qt-harmonyos-porting-workflow` | 可行性评估 → 工程创建 → 8 步迁移 → 编译验证 |
| [B] | API 替换查询 | `semantic/qt-harmonyos-api-mapping`（12 类映射）+ `qt-harmonyos-code-patterns` | 替换方案 + Before/After 代码 |
| [C] | Qt 模块支持查询 | `semantic/qt-harmonyos-modules` | 是否支持 + 版本(5.12/5.15) + 替代方案 |
| [D] | 平台限制查询 | `semantic/qt-harmonyos-platform-limits` | 限制描述 + QTBUG 编号 + Workaround |
| [E] | 构建排障 | `semantic/qt-harmonyos-build-run-workflow` §四步法 + `problems/_lookup` | 错误分类 → 根因 → 修复步骤 |
| [F] | 窗口问题 | `semantic/qt-harmonyos-golden-rules` §二 + `qt-harmonyos-window-model` | 规则说明 + 修复代码 |
| [G] | 生命周期 | `semantic/qt-harmonyos-lifecycle` | 行为说明 + 代码示例 + 枚举路径 |
| [H] | QtOhosExtras API | `semantic/qt-ohos-extras`（145+ API） | API 签名 + 用途 + 使用示例 |
| [L] | Qt6 状态 | `semantic/qt-harmonyos-qt6-status` | 当前状态 + 已知差异 + 待验证项 |
| [M] | 三方库 | `semantic/qt-harmonyos-third-party-libs` | 交叉编译方法 / 部署步骤 / 兼容性 |
| [N] | 工具链 | `semantic/deveco-mcp-toolchain` + `deveco-cli-commands` | 安装/配置 或 headless 编译配方 |
| [Q] | Demo 生成 | `procedural/demo-generation`（Qt+CEF/WebEngine demo 见 §3.3 + `qt-cef-ohos-dev-guide` + `tools/kb-cef-graft.py`） | 需求 → 设计 → 工程 → 代码 → 编译 → 文档；Qt+CEF demo 用 `tools/kb-cef-graft.py --run` 一条龙 |

**捆绑工具**：`skills/kb-init/` —— 环境探测（DevEco/SDK/Qt 源码）→ 引导安装缺失依赖 → 生成 `ENV.local.md` → 校验环境可用。`tools/kb-cef-graft.py` + `tools/kb-cef-graft.config.example.json` —— Qt+CEF demo 嫁接脚本（把 CEF 嫁接到 Qt OHOS 模板，`--run` 签名+装机+启动+崩溃检查，环境配置全在配置文件，见 `procedural/qt-cef-ohos-dev-guide.md`）。

**内嵌 common-KB 子集**：`ohos-common-kb-public/` 提供 HarmonyOS 平台通用知识（ArkTS/ArkUI/NAPI/Stage 模型/DevEco 工具链基础），与 Qt 知识互补。

### 输入 / 输出契约

| 输入 | 处理 | 输出 |
|------|------|------|
| 自然语言请求（喂 AI 工具） | 任务路由 → 扫铁律 → 按需加载页 → 综合 | 替换方案+代码 / 模块状态 / 限制+QTBUG / 错误解决方案 / 编译配方 |
| 直接浏览（人类 / Obsidian） | `_dashboard` 看全貌 → `_map` 看摘要 → 点开自包含页 | 结构化技术参考 |

固定入口链：`_index/_task-routing → semantic/qt-harmonyos-golden-rules → _index/_map → 按需页 → refs 深追`。报错第一步：`problems/_lookup.md` 按错误码 / 症状检索。

### 版本与兼容策略

- **版本号**：[SemVer](https://semver.org/lang/zh-CN/) `vMAJOR.MINOR.PATCH`，版本对象 = 外部仓整包。基线 `v2.0.0`（2026-08-19），不回填 v1。
- **MAJOR（破坏性）**：删/移走用户依赖的页、`audience` 由 public→internal、目录重排致旧链接断、铁律/API 映射被证伪并反转。
- **MINOR（内容新增）**：新页/新节/新 API 映射条目/新 task 类型/内嵌新 KB 或 skill。
- **PATCH（内容修正）**：typo/措辞修正、错误解决方案更新、Qt 参考版本 bump。
- **Pin 某版**：`git clone --branch vX.Y.Z <本仓库>`。
- **变更日志**：见 [CHANGELOG.md](CHANGELOG.md)。
- **可复现性**：每版生成 `RELEASE-MANIFEST.yaml`（记录源端 KB 的 git SHA + `content_tree_sha256` + 页数计数），可据 `source_kbs` SHA 复现该版内容。
- **Qt 框架版本校验基准**：Qt 5.15.16（tqtc/harmonyos-5.15.16, 962aa625）/ Qt 5.12.12（tqtc/harmonyos-5.12.12, 613336de）。

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

本仓库由更大的内部工作流知识库单向裁剪生成（`audience: public` 子集），能力边界、裁剪规则与版本策略见上方 [能力规格](#能力规格)。

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
