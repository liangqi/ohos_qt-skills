# DevEco 开发工具安装指南

本文件涵盖三类工具的安装：
1. **DevEco Studio** — GUI IDE（macOS / Windows）
2. **Command Line Tools** — 命令行工具集（Linux / HarmonyOS）
3. **deveco-cli** — 开源 AI 开发工具（全平台）

---

## macOS

### DevEco Studio

#### 下载

1. 访问 https://developer.huawei.com/consumer/cn/deveco-studio/
2. 选择 **DevEco Studio** macOS 版本（支持 Intel 和 Apple Silicon）
3. 下载 `.dmg` 安装包

> **自动下载**：`bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=<目录>` 可自动下载安装包到指定目录。

#### 安装

1. 双击 `.dmg` 文件
2. 将 DevEco Studio 拖入 `/Applications` 目录
3. 首次启动时，如果系统提示"无法验证开发者"，前往 **系统设置 → 隐私与安全性** 点击"仍要打开"
4. DevEco Studio 首次启动会自动下载 HarmonyOS SDK

#### 验证

```bash
ls /Applications/DevEco-Studio.app
ls /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/clang
ls /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc
```

### 将工具加入 PATH（推荐）

```bash
echo 'export PATH="/Applications/DevEco-Studio.app/Contents/tools:$PATH"' >> ~/.zshrc
echo 'export PATH="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains:$PATH"' >> ~/.zshrc
source ~/.zshrc
devecocli --version  # 验证 DevEco CLI
hdc version          # 验证 hdc
```

---

## Windows

### DevEco Studio

#### 下载

1. 访问 https://developer.huawei.com/consumer/cn/deveco-studio/
2. 选择 **DevEco Studio** Windows 版本
3. 下载 `.exe` 安装包

> **自动下载**：`bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=<目录>` 可自动下载安装包。

#### 安装

1. 双击 `.exe` 安装包
2. 按向导完成安装（默认安装到 `C:\Program Files\Huawei\DevEco Studio`）
3. 首次启动会自动下载 HarmonyOS SDK

#### 验证

```powershell
dir "C:\Program Files\Huawei\DevEco Studio"
dir "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\native\llvm\bin\clang.exe"
dir "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe"
```

### 将工具加入 PATH（推荐）

1. 打开 **系统设置 → 高级系统设置 → 环境变量**
2. 在 **Path** 中添加:
   - `C:\Program Files\Huawei\DevEco Studio\tools`
   - `C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains`
3. 打开新的 PowerShell 窗口验证：`devecocli --version` 和 `hdc version`

---

## Linux

### Command Line Tools

DevEco Studio **没有 Linux GUI 版本**。Linux 用户使用 **Command Line Tools for HarmonyOS**。

#### 自动安装（推荐）

```bash
bash skills/kb-init/scripts/download-cmdline-tools.sh \
  --dest=~/commandline-tools \
  --url=<从下载页获取的链接>
```

脚本会自动下载、解压并输出 SDK 路径。

#### 手动安装

1. 访问 https://developer.huawei.com/consumer/cn/download/
2. 找到 **Command Line Tools for HarmonyOS** Linux 版本
3. 下载 `.tar.gz` 归档

```bash
mkdir -p ~/commandline-tools
tar xzf commandline-tools-linux-*.tar.gz -C ~/commandline-tools
```

#### 配置 PATH

```bash
echo 'export PATH="$HOME/commandline-tools/tools:$PATH"' >> ~/.bashrc
echo 'export PATH="$HOME/commandline-tools/sdk/default/openharmony/toolchains:$PATH"' >> ~/.bashrc
echo 'export OHOS_SDK_NATIVE="$HOME/commandline-tools/sdk/default/openharmony/native"' >> ~/.bashrc
source ~/.bashrc
```

#### 验证

```bash
devecocli --version
hdc version
ls ~/commandline-tools/sdk/default/openharmony/native/llvm/bin/clang
```

---

## HarmonyOS

### 平台限制

鸿蒙 PC 当前存在以下限制：

| 工具 | 状态 | 获取方式 |
|------|------|----------|
| DevEco Studio | 不可用 | 无鸿蒙版，未上架应用市场 |
| Command Line Tools | 需申请 | 在统一工单平台提单申请遥测版本 |
| deveco-cli | 可尝试 | 仓库未声明支持，但可通过 npm 尝试安装 |

### 申请 Command Line Tools

1. 访问 https://developer.huawei.com/consumer/cn/ 统一工单平台
2. 提单申请 **Command Line Tools for HarmonyOS 遥测版本**
3. 获得下载链接后，运行：

```bash
bash skills/kb-init/scripts/download-cmdline-tools.sh \
  --dest=~/commandline-tools \
  --url=<下载链接>
```

4. 配置 PATH：

```bash
echo 'export PATH="$HOME/commandline-tools/tools:$PATH"' >> ~/.zshrc
echo 'export PATH="$HOME/commandline-tools/sdk/default/openharmony/toolchains:$PATH"' >> ~/.zshrc
echo 'export OHOS_SDK_NATIVE="$HOME/commandline-tools/sdk/default/openharmony/native"' >> ~/.zshrc
source ~/.zshrc
```

### 在等待 CLT 期间可完成的配置

以下工具可通过 HarmonyBrew 安装，不依赖 DevEco/CLT：

```bash
# 安装 HarmonyBrew（如未安装）
zsh -c "$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)"

# 安装基础工具
brew install git cmake node
```

---

## deveco-cli（全平台）

`devecocli` 命令由开源工具 deveco-cli 提供（仓库: https://gitcode.com/openharmony-sig/deveco-cli，npm 包名 `@deveco/deveco-cli`），封装 DevEco 工具链（ohpm/hvigor/hdc/emulator/hilog + bundled node/JBR/SDK），覆盖构建、安装、日志、签名、模拟器、UI 自动化。部分 DevEco Studio 版本在 `tools/devecocli{.bat}` 另有捆绑副本，功能一致，以定位到的为准（定位顺序见 `ohos-common-kb-public/procedural/deveco-cli-usage-rules.md` §工具可用性预检）。

- **依赖**: Node.js >= 18

### 自动安装（推荐）

```bash
bash skills/kb-init/scripts/install-deveco-cli.sh --method=npm
```

### 手动安装

```bash
npm i -g @deveco/deveco-cli
devecocli --version   # 注意：二进制名是 devecocli
```

### 验证

```bash
devecocli --version
```

### 常见误认

| 名称 | 实际身份 |
|------|---------|
| `devecocli` | 本工具（npm `@deveco/deveco-cli`，稳定渠道；部分 DevEco 版本捆绑） |
| `deveco-cli`（裸包名/命令） | **不存在**——npm 作用域包是 `@deveco/deveco-cli`，二进制只有 `devecocli` |
| `@deveco-test/deveco-cli` | 测试通道包，不要作为安装命令 |
| `devecostudio` | DevEco Studio GUI 启动器，不是构建 CLI |
