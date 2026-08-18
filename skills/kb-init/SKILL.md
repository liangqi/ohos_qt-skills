---
name: kb-init
description: |
  Qt for HarmonyOS 知识库环境初始化。完整配置 DevEco Studio、HarmonyOS SDK、Qt SDK/源码、
  构建工具链，生成 ENV.local.md，验证环境就绪。
  当用户说"初始化"、"配置环境"、"第一次使用"、"setup"、"install"，
  或 ENV.local.md 不存在时，必须触发此 skill。
  即使用户没有明确说"初始化"，只要是第一次与知识库交互，也应主动建议运行。
---

# kb-init: Qt for HarmonyOS 开发环境一键配置

本 skill 引导你完成 Qt for HarmonyOS 开发所需的全部环境配置。整个过程分两阶段：

1. **收集决策**（Phase 1）：Agent 一次性问你几个问题，你回答完后就不用再管了
2. **自动执行**（Phase 2）：脚本自动安装、下载、配置，最后验证环境就绪

> 设计原则：能用脚本确定性完成的步骤，绝不让 Agent 自由发挥。Agent 只负责问你问题和调用脚本。

## Phase 1: 收集用户决策

按以下顺序**逐一**询问用户。每个问题等用户回答后再问下一个。不要一次性列出所有问题。

### Q1: Qt 源码获取方式

> 你有 Qt 商业 license 吗？这决定了我们如何获取 Qt 鸿蒙源码。
>
> 1. **有 license** — 从 Qt 官方 codereview.qt-project.org 获取（可选 5.12 或 5.15）
> 2. **没有 license** — 从 GitCode 获取开源版本（仅 5.12.12）
> 3. **我只需要预编译 SDK** — 直接下载编译好的 SDK，不需要源码（最快上手）
>
> 如果你不确定，推荐选 3。

记录用户选择为 `QT_SOURCE_METHOD`（`commercial` / `opensource` / `prebuilt`）。

### Q2: Qt 版本（仅 commercial 场景需要）

如果 Q1 选了 commercial：

> 你需要哪个 Qt 版本？
> 1. **Qt 5.15.16**（推荐，新项目使用）
> 2. **Qt 5.12.12**（旧项目维护）
> 3. **两个都要**

记录为 `QT_VERSION`（`5.15` / `5.12` / `both`）。

如果 Q1 选了 opensource 或 prebuilt，固定为 `QT_VERSION=5.12`（开源版本仅有 5.12.12）。

### Q3: 安装根目录

> 你希望把 Qt 相关文件安装到哪个目录？
> 例如：`D:\dev` 或 `/Users/你的用户名/dev`
>
> 脚本会在该目录下创建 `qt-sdk/`、`qt-src/` 等子目录。
> 请确保该目录有至少 5GB 可用空间。

记录为 `INSTALL_BASE`。如果用户不确定，推荐默认值：
- macOS: `$HOME/dev`
- Windows: `D:\dev`（如果 D 盘存在）或 `C:\dev`
- Linux: `$HOME/dev`

### Q4: DevEco Studio 状态

> 你已经安装了 DevEco Studio 吗？
> 1. **已安装** — 请告诉我安装路径（例如 `/Applications/DevEco-Studio.app`）
> 2. **未安装** — 我会引导你安装

记录为 `DEVECO_STATUS`（`installed` / `not-installed`）和 `DEVECO_PATH`（如已安装）。

### Q5: Git 配置（仅 commercial / opensource 场景）

如果 Q1 不是 prebuilt：

> 你的 git 是否已配置好用户名和邮箱？（clone 代码需要）
> 运行 `git config user.name` 和 `git config user.email` 看看有没有输出。

Agent 运行 `git config user.name` 和 `git config user.email` 检查。如果为空，引导用户配置：
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### Q6: Commercial 场景账号验证

如果 Q1 选了 commercial：

> 你能访问 https://codereview.qt-project.org 吗？
> 请先在浏览器中打开这个网址，确认你能登录。
> 登录后，进入 Settings → HTTP Credentials → GENERATE NEW PASSWORD，
> 记下生成的用户名和密码（clone 时会用到）。

等用户确认完成后再继续。

---

## Phase 2: 自动执行

Phase 1 完成后，Agent 已收集到所有必要信息。按以下顺序执行，**每步调用对应脚本**。

### Step 1: 环境检测

```bash
bash skills/kb-init/scripts/detect-env.sh
```

解析输出的 key=value，记录当前环境状态。向用户简要展示：
- 操作系统和架构
- 已安装的工具（DevEco / git / hdc 等）
- 已定位的 Qt SDK/源码

### Step 2: 安装 DevEco Studio（如果未安装）

如果 Q4 回答未安装：

**Agent 行为**：读取 `references/deveco-install.md`，根据用户 OS 执行对应安装流程。

简要流程：
- **macOS**: 打开下载链接 → 用户下载 .dmg → 脚本验证安装结果
- **Windows**: 打开下载链接 → 用户下载 .exe → 用户安装 → 脚本验证安装结果
- **Linux**: 下载命令行工具包 → 脚本解压到指定目录

DevEco 安装完成后，重新运行 `detect-env.sh` 确认 `DEVECO_FOUND=true` 和 `OHOS_SDK_NATIVE_FOUND=true`。

### Step 3: 平台依赖安装

根据 OS 运行对应脚本：

**macOS**:
```bash
bash skills/kb-init/scripts/install-deps-macos.sh
```

**Linux**:
```bash
bash skills/kb-init/scripts/install-deps-linux.sh
```

**Windows**（在 Git Bash 中运行）:
```bash
bash skills/kb-init/scripts/install-deps-linux.sh  # Windows Git Bash 兼容
```

脚本会检查并报告缺失的依赖。如果脚本提示需要用户手动安装某项（如 Xcode CLT），Agent 引导用户完成后重新运行脚本。

### Step 4: 获取 Qt SDK / 源码

根据 Q1 的选择执行对应脚本：

**场景 A (commercial) 或 B (opensource) — 需要源码**:
```bash
bash skills/kb-init/scripts/clone-qt-src.sh \
  --method=<commercial|opensource> \
  --version=<5.12|5.15|both> \
  --dest=<INSTALL_BASE>/qt-src
```

脚本行为：
- commercial: 使用用户 Q6 中生成的 HTTP 凭据 clone codereview.qt-project.org
- opensource: clone gitcode.com/ohos-qt/qt-harmonyos-src
- 自动 checkout 正确分支 + submodule update
- 输出 `QT5_12_SRC` / `QT5_15_SRC` 路径

**场景 C (prebuilt) — 下载预编译 SDK**:
```bash
bash skills/kb-init/scripts/download-qt-sdk.sh \
  --platform=<macos|windows|linux> \
  --dest=<INSTALL_BASE>/qt-sdk
```

脚本行为：
- 列出 GitCode releases 页面可用的 SDK 包
- 根据用户 OS 自动选择对应平台版本
- 下载并解压到 `INSTALL_BASE/qt-sdk/`
- 输出 `QT5_12_OHOS_SDK` 路径

**所有场景都需要预编译 SDK**（场景 A/B 的用户也可能需要下载预编译 SDK 作为 CMAKE_PREFIX_PATH，除非他们打算自己编译 Qt）。

Agent 询问：
> 你是否还需要下载预编译 Qt SDK？（用于 CMake 链接，如果你打算自己编译 Qt 框架则不需要）

如果用户说是，也运行 `download-qt-sdk.sh`。

### Step 5: 生成 ENV.local.md

```bash
bash skills/kb-init/scripts/generate-env-local.sh \
  --deveco-path="<DEVECO_PATH>" \
  --qt5-12-src="<QT5_12_SRC_PATH>" \
  --qt5-15-src="<QT5_15_SRC_PATH>" \
  --qt-build-root="<INSTALL_BASE>/qt-build" \
  --qt5-12-ohos-sdk="<QT5_12_OHOS_SDK_PATH>" \
  --qt5-15-ohos-sdk="<QT5_15_OHOS_SDK_PATH>" \
  --ohos-sdk-native="<OHOS_SDK_NATIVE_PATH>"
```

参数说明：
- 只传用户实际有的路径，缺失的参数不传
- `QT_BUILD_ROOT` 固定为 `INSTALL_BASE/qt-build`
- 脚本自动生成 `ENV.local.md` 到 KB 根目录

Agent 向用户展示生成结果，请用户确认。

### Step 6: 验证环境

```bash
bash skills/kb-init/scripts/verify-env.sh
```

- 如果 `STATUS=ready`：告知用户环境就绪，可以开始使用知识库
- 如果 `STATUS=not-ready`：逐项展示 FAIL 原因，引导修复后重新验证

---

## 完成标志

- `ENV.local.md` 已生成到 KB 根目录
- DevEco Studio + OHOS SDK native 已就绪
- Qt OHOS SDK 或 Qt 源码至少一项已配置
- `verify-env.sh` 输出 `STATUS=ready`

## 错误处理

| 错误 | 处理 |
|------|------|
| `detect-env.sh` 执行失败 | 检查 bash ≥ 4.0；`chmod +x skills/kb-init/scripts/*.sh` |
| DevEco 安装后检测不到 | macOS 检查 `/Applications/DevEco-Studio.app`；Windows 检查注册表路径 |
| git clone 失败 (commercial) | 检查 HTTP 凭据是否正确；检查网络是否能访问 codereview.qt-project.org |
| git clone 失败 (opensource) | 检查网络是否能访问 gitcode.com；尝试 `git config --global http.sslVerify false` |
| SDK 下载失败 | 检查网络；手动访问 https://gitcode.com/ohos-qt/qt-harmonyos-src/releases 下载 |
| `generate-env-local.sh` 写入失败 | 检查 KB 根目录写权限 |
| `verify-env.sh` 报告 FAIL | 按 FAIL 项提示修复，重新运行 |
| Linux 用户无 DevEco Studio GUI | 正常——使用命令行工具，不报错 |

## 参考文档

如需更详细的安装说明，读取以下文件：
- `references/deveco-install.md` — DevEco Studio 各平台安装详细步骤
- `references/qt-src-acquisition.md` — Qt 源码获取的三种方式详细说明
- `references/env-variables.md` — ENV.md 中所有变量的含义和用途
