# 贡献指南

## 本仓库的性质

本仓库是 **只读派生视图**：内容由一个更大的 Qt for HarmonyOS 工作流知识库（内部源）经 `_scripts/kb-dev-edition.sh` 按 frontmatter `audience:public` 过滤后重生成。**源端即公开安全**（门禁在源端兜底，发布只过滤、不脱敏）。

正因如此：

- **请不要对本仓库的内容文件提 PR**。所有 `.md`（`semantic/`、`procedural/`、`episodic/`、`problems/`、`_index/`、根文档）每次发布会**整体覆盖**，直接编辑会被下一次发布冲掉。
- **请提 Issue**。Issue 是唯一被保留的社区贡献入口。

## 如何贡献

1. **提 Issue**：在仓库提 issue，描述
   - 你遇到的问题 / 发现的错误 / 想补充的知识
   - 涉及的具体页面（文件路径或小节标题）
   - 尽可能附：错误信息原文、复现步骤、期望内容
2. **维护者在【内部源】修复**（必要时走蒸馏流程：issue 信息 → 蒸馏为结构化知识页，并入对应域）。
3. **经 PR 发布解决**：修复后维护者重生成本仓库并开 PR，PR 描述里写 `closes #N`，合并后你的 issue 自动关闭、内容出现在本仓库。

## 欢迎的贡献类型

- ✅ **报错库补充**：实际编译/部署/运行时遇到的、本仓库 `problems/` 未收录的报错（附完整错误信息与解决方案）
- ✅ **提交新问题草稿**：按 `faults/_drafts/_template.md` 的清单准备（必填：现象原文 / 环境三件套 / **证据——复现 demo（缺陷类必附，七原则见 `faults/_index.md` §六）或调试日志+栈**，规格限制类可用官方文档链接替代 / 查重声明），通过 issue 提交（维护者转录为 `faults/_drafts/` 草稿）。**无证据的转述不予受理**；主编合入前会**复现测试 demo + 人工核验**，见 `faults/_index.md` §六·协作草稿模式
- ✅ **故障库情报**：某已知故障在新版本（Qt OHOS SDK / HarmonyOS SDK / DevEco）已修复或仍复现的实证（附版本号与验证环境）
- ✅ **API 映射 / 平台限制**的勘误与补充
- ✅ **迁移复盘、Demo 经验**
- ✅ **文档笔误、链接失效**
- ✅ **Skills 改进建议**：`skills/` 目录中的自动化脚本和工具

## 不接受

- ❌ 直接修改内容文件的 PR（会被发布覆盖；请转成 issue）
- ❌ 涉及内部/私有信息的内容（本仓库仅含 `audience:public` 内容）

## 反馈流程

### 发现内容错误

1. 在本仓库提 Issue，选择"Knowledge correction"模板
2. 描述错误内容、涉及页面、正确信息
3. 维护者会在内部源修复，下次发布时自动带入

### 想补充新知识

1. 在本仓库提 Issue，选择"Knowledge contribution"模板
2. 描述你想补充的知识、证据来源
3. 维护者会评估并蒸馏到内部源，下次发布时自动带入

### 想改进 Skills

1. 在本仓库提 Issue，选择"Feature / structure proposal"模板
2. 描述你想改进的 skill、改进建议
3. 维护者会评估并实现改进

## 内嵌的 HarmonyOS 平台通用知识

本仓库内嵌了 `ohos-common-kb-public/` 目录，包含 HarmonyOS 平台通用知识（ArkTS、ArkUI、NAPI、Stage 模型、DevEco 工具链等）。这些内容由内部 `ohos-common-kb` 仓库按 `audience:public` 过滤后生成。

如果你发现平台通用知识有问题，同样在本仓库提 Issue，维护者会路由到内部 `ohos-common-kb` 修复。

## License

MIT（见 `LICENSE`）。提交的 issue 内容视同在该协议下贡献。
