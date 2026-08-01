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
| 窗口/对话框/生命周期行为不对 | 窗口模型详解 + 生命周期/关闭拦截/接续 + 33 条铁律 |
| 编译失败、部署失败、运行崩溃 | 错误库（一错一文件，按错误码/症状速查）+ 构建运行全流程 |
| 判断一个问题是不是出在 Qt 鸿蒙框架层 | 铁律 + 平台限制 + API 差异 + 错误库，帮你识别"框架问题"特征 |
| 想报告 Qt for HarmonyOS 问题 / 疑似框架或系统 bug | bug 报告工作流（必填 5 项即可上报，两形态：完整交付件 + issue 精简版） |

> 本版聚焦 **应用鸿蒙化** 与 **应用问题分析**。它能帮你识别"这可能是 Qt 鸿蒙框架的已知行为/限制"，但不教你改 Qt 框架源码加日志定位根因——那是上游 Qt 团队的工作。

---

## 快速开始

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
├── _index/                 # 索引层：_map（知识地图）/ _tags / _dashboard / _task-routing
├── semantic/               # 语义知识：API 参考与映射、平台限制、模块状态、构建/工程
├── procedural/             # 程序知识：应用迁移工作流、Demo 生成、编译配方
├── episodic/               # 情景知识：实际移植项目复盘（SARibbon/Coin3D/退出死锁 等）
├── problems/               # 错误库：实际编译/部署/运行时报错与解决方案（一错一文件）
└── LICENSE
```

| 目录 | 回答 | 例子 |
|------|------|------|
| `semantic/` | 我知道什么？ | API 映射、窗口模型、平台限制、模块状态、33 条铁律 |
| `procedural/` | 我怎么做？ | 应用迁移工作流、落地编译配方（Playbook A/B）、Demo 生成 |
| `episodic/` | 发生过什么？ | 真实迁移复盘、bug 根因记录 |
| `problems/` | 遇到这个报错怎么办？ | 编译失败、dlopen 拒绝、签名不匹配（速查优先） |

---

## 怎么用：接到任务后的路径

AI 的处理顺序是固定的，你不用记：

```
你的请求
  → _index/_task-routing.md   匹配任务类型，确定工作流和必读页
  → semantic/qt-harmonyos-golden-rules.md   扫 33 条铁律（避已知陷阱）
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
| 想报告 bug / 疑似框架或系统问题 | **先读 `procedural/qt-bug-report-generation.md`**，按必填 5 项填 bug report 模板（见工作流页内嵌）form B |

### 错误库怎么用

遇到编译/部署/运行时报错，第一步查 `problems/_lookup.md`：按错误码、错误信息关键字或症状检索，命中就读对应问题文件拿方案。`problems/` 记的是真实踩过的坑（CMake find_package 失败、dlopen 拒绝可写路径、QPA 插件未部署、签名不匹配 等），不是 Qt 官方文档里的平台限制——后者在 `semantic/qt-harmonyos-platform-limits.md`。

### bug 报告工作流怎么用

遇到疑似 Qt 鸿蒙框架层或鸿蒙系统接口的问题、想上报时，第一步读 `procedural/qt-bug-report-generation.md`：它给你一份 bug 报告模板，**必填只 5 项**（复现环境 / 故障现象 / 错误日志 / 复现步骤 + demo / 紧急度），其余可选。每段附 hdc 抓 log 命令（`hdc file recv /data/log/faultlog/temp/cppcrash/`、`hdc shell hilog | grep -iE "crash|<包名>"`），复制即用。填完跑完整性自检（HARD 项打勾）即可提交。模板分两形态：**form B** 是 issue 精简版，贴 issue tracker 或邮件；**form A** 是完整交付件（含调用链追踪、纯鸿蒙复现 demo、官方文档对比），由接收方团队基于你的上报补全后正式交付上游。你能给的才是必填——Qt 源码追踪、绕过 Qt 直调系统接口、三层交叉验证这类需要 Qt 内部能力的工作，由接收方完成，不要求你做。填好的样例见 `procedural/qt-bug-report-sample.md`。

> 本工作流帮你把问题报清楚，但不替代上游 Qt/华为的修复。接收方会基于你提供的信息做框架调用链追踪、纯鸿蒙复现验证、根因签署，再决定走 Qt 修复还是上报华为——这些不需要你做。

---

## 本地环境配置

知识页以变量名（如 `QT5_15_OHOS_SDK`、`OHOS_SDK_NATIVE`）引用本地路径，不硬编码。把 `ENV.md` 里的 `<PLACEHOLDER_*>` 替换为你本机路径即可。需要的东西：

- **DevEco Studio + HarmonyOS SDK**（API 17/20）—— 提供 OHOS clang、sysroot、hvigorw、模拟器
- **Qt 5.12 / 5.15 鸿蒙源码**（tqtc/harmonyos 分支，公开获取）—— 见 `ENV.md`「源码获取」
- **MinGW + Strawberry Perl**（Windows 编译 Qt 用）
- 一个已编译的 **Qt OHOS SDK**（作为应用链接的 `CMAKE_PREFIX_PATH`）

> 应用开发者通常拿到团队分发的预编译 Qt OHOS SDK 即可开始；只有要自己重编 Qt 库时才需要源码 + MinGW + Perl。

---

## 设计理念

- **编译而非检索** — 借鉴 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)，把原始经验蒸馏成结构化知识页
- **分层加载** — 借鉴 Claude Code 的层级上下文机制，索引层始终加载，知识页按需加载
- **文件即数据** — 纯 Markdown + Git，零基础设施依赖
- **类型化记忆** — 借鉴认知科学，知识分四类 + 一个错误库

## 与源端知识库的关系

本仓库由一个更大的内部工作流知识库单向裁剪生成（见 `_scripts/kb-dev-edition.sh`）。裁剪保留 `audience: public` 的技术内容，移除：内部团队协作流程、商业支持/系统问题验证工作流、工作流供应链、Qt 框架源码级调试方法。因此本版可公开给 Qt 应用开发者使用。如发现内容问题，可在本仓库提 issue。

## License

见 `LICENSE`。
