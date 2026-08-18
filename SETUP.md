# 安装指南

本知识库提供自动化初始化 skill，帮你快速完成环境配置。

## 快速开始

克隆本仓库后，在你的 AI 工具中说"初始化知识库"或"帮我配置环境"，Agent 会自动执行 `skills/kb-init/` 中的初始化流程。

## 初始化 skill 会做什么

`skills/kb-init/` 包含以下组件：

| 文件 | 职责 |
|------|------|
| `SKILL.md` | Agent 指令：引导用户完成交互式决策（选择 Qt 版本、确认路径等） |
| `scripts/detect-env.sh` | 确定性检测：扫描已安装的工具、SDK、Qt 源码，输出结构化结果 |
| `scripts/generate-env-local.sh` | 确定性生成：根据检测结果写入 `ENV.local.md` |
| `scripts/verify-env.sh` | 确定性验证：检查所有必要路径存在、工具版本兼容，输出就绪报告 |

## 初始化流程

```
1. Agent 读取 SKILL.md，开始引导

2. 运行 detect-env.sh（确定性）
   ├── 检测操作系统（Windows / macOS / Linux）
   ├── 检测已安装工具（DevEco Studio? hdc? git? cmake? MinGW? Perl?）
   ├── 检测已有的 Qt 源码/SDK（扫描常见路径）
   └── 输出结构化检测结果

3. Agent 根据检测结果，引导用户补齐缺失依赖
   ├── DevEco Studio + HarmonyOS SDK
   ├── Qt 源码获取（有 license / 无 license / 预编译 SDK）
   ├── 构建工具链（MinGW / Strawberry Perl，仅 Windows 编译 Qt 时需要）
   └── 验证各工具版本兼容

4. 运行 generate-env-local.sh（确定性）
   ├── 输入：检测结果 + 用户选择
   ├── 输出：ENV.local.md
   └── Agent 展示生成结果，请用户确认

5. 运行 verify-env.sh（确定性）
   ├── 检查所有必要路径存在
   ├── 检查工具版本兼容
   ├── 可选：尝试编译一个最简 Qt 鸿蒙 demo
   └── 输出环境就绪报告（通过/未通过 + 具体缺失项）
```

## 手动安装（不使用 skill）

如果你不想使用初始化 skill，可以手动完成以下步骤：

1. **安装 DevEco Studio + HarmonyOS SDK**
   - 下载：https://developer.huawei.com/consumer/cn/deveco-studio/
   - 版本要求：API 17/20

2. **获取 Qt 源码**
   - 有 license：`git clone https://codereview.qt-project.org/qt/tqtc-qt5`
   - 无 license：`git clone https://gitcode.com/ohos-qt/qt-harmonyos-src`
   - 只需预编译 SDK：访问 https://gitcode.com/ohos-qt/qt-harmonyos-src/releases 下载

3. **安装构建工具链**（仅 Windows 编译 Qt 时需要）
   - MinGW：https://www.mingw-w64.org/
   - Strawberry Perl：https://strawberryperl.com/

4. **生成 ENV.local.md**
   - 复制 `ENV.md` 为 `ENV.local.md`
   - 替换所有 `<PLACEHOLDER_*>` 为你本机的实际路径

5. **验证环境**
   - 检查所有必要路径存在
   - 尝试编译一个最简 Qt 鸿蒙 demo

## 常见问题

### Q: 我没有 Qt 商业 license，能使用本知识库吗？

A: 可以。本知识库支持三种 Qt 源码获取方式：
- 有 license：从 codereview.qt-project.org 获取
- 无 license：从 https://gitcode.com/ohos-qt/qt-harmonyos-src 获取开源代码
- 只需预编译 SDK：从 https://gitcode.com/ohos-qt/qt-harmonyos-src/releases 下载预编译产物

### Q: 初始化 skill 检测不到我已安装的工具？

A: 初始化 skill 会扫描常见路径。如果你的工具安装在非标准路径，可以在 Agent 引导时手动指定路径。

### Q: 初始化完成后，如何验证环境可用？

A: 初始化 skill 的最后一步会运行 `verify-env.sh`，输出环境就绪报告。如果报告中有缺失项，按提示补齐即可。

## 相关文件

- `ENV.md`：路径变量定义（占位模板）
- `ENV.local.md`：你的本地路径配置（由初始化 skill 生成，或手动创建）
- `skills/kb-init/SKILL.md`：初始化 skill 的 Agent 指令
- `skills/kb-init/scripts/`：初始化 skill 的确定性脚本
