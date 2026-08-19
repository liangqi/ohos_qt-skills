# DevEco Studio 安装指南

## macOS

### 下载

1. 访问 https://developer.huawei.com/consumer/cn/deveco-studio/
2. 选择 **DevEco Studio** macOS 版本（支持 Intel 和 Apple Silicon）
3. 下载 `.dmg` 安装包

### 安装

1. 双击 `.dmg` 文件
2. 将 DevEco Studio 拖入 `/Applications` 目录
3. 首次启动时，如果系统提示"无法验证开发者"，前往 **系统设置 → 隐私与安全性** 点击"仍要打开"
4. DevEco Studio 首次启动会自动下载 HarmonyOS SDK

### 验证

```bash
# 检查 DevEco Studio 是否安装
ls /Applications/DevEco-Studio.app

# 检查 HarmonyOS SDK（DevEco 首次启动后自动下载）
ls /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/clang

# 检查 hdc
ls /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc
```

### 将 hdc 加入 PATH（可选但推荐）

```bash
echo 'export PATH="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains:$PATH"' >> ~/.zshrc
source ~/.zshrc
hdc version  # 验证
```

---

## Windows

### 下载

1. 访问 https://developer.huawei.com/consumer/cn/deveco-studio/
2. 选择 **DevEco Studio** Windows 版本
3. 下载 `.exe` 安装包

### 安装

1. 双击 `.exe` 安装包
2. 按向导完成安装（默认安装到 `C:\Program Files\Huawei\DevEco Studio`）
3. 首次启动会自动下载 HarmonyOS SDK

### 验证

```powershell
# 检查 DevEco Studio
dir "C:\Program Files\Huawei\DevEco Studio"

# 检查 HarmonyOS SDK
dir "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\native\llvm\bin\clang.exe"

# 检查 hdc
dir "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe"
```

### 将 hdc 加入 PATH（可选但推荐）

1. 打开 **系统设置 → 高级系统设置 → 环境变量**
2. 在 **Path** 中添加: `C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains`
3. 打开新的 PowerShell 窗口，运行 `hdc version` 验证

---

## Linux

### 注意

DevEco Studio **没有 Linux GUI 版本**。Linux 用户需要下载 **Command Line Tools for HarmonyOS**。

### 下载

1. 访问 https://developer.huawei.com/consumer/en/download/
2. 找到 **Command Line Tools for HarmonyOS**
3. 下载 Linux 版本（`.tar.gz`）

### 安装

```bash
# 创建安装目录
mkdir -p ~/dev/deveco-studio

# 解压
tar xzf commandline-tools-linux-*.tar.gz -C ~/dev/deveco-studio

# 将工具链加入 PATH
echo 'export PATH="$HOME/dev/deveco-studio/sdk/default/openharmony/toolchains:$PATH"' >> ~/.bashrc
echo 'export OHOS_SDK_NATIVE="$HOME/dev/deveco-studio/sdk/default/openharmony/native"' >> ~/.bashrc
source ~/.bashrc
```

### 验证

```bash
# 检查 SDK
ls ~/dev/deveco-studio/sdk/default/openharmony/native/llvm/bin/clang

# 检查 hdc
hdc version
```
