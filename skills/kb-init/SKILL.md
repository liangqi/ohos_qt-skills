---
name: kb-init
description: |
  Qt for HarmonyOS 知识库环境初始化。检测主机平台，引导用户选择 Qt 源码获取方式，
  自动安装缺失依赖、生成 ENV.local.md、验证环境就绪。
  当用户说"初始化"、"配置环境"、"第一次使用"、"setup"、"install"，
  或 ENV.local.md 不存在时，必须触发此 skill。
  即使用户没有明确说"初始化"，只要是第一次与知识库交互，也应主动建议运行。
---

# kb-init: 知识库初始化

引导用户完成 Qt for HarmonyOS 知识库的全量环境配置，达到"可以开始移植 Qt 应用"的状态。

## 决策树

```
开始
  │
  ├─ 1. 运行 detect-env.sh → 获取 OS / 已有工具 / 已有 Qt
  │
  ├─ 2. 询问 Qt 源码获取方式
  │     ├─ A. 有 Qt 商业 license → codereview.qt-project.org（可选 5.12 / 5.15）
  │     ├─ B. 无 license（开源）→ gitcode.com/ohos-qt/qt-harmonyos-src（仅 5.12.12）
  │     └─ C. 只需预编译 SDK → 下载 release 包（仅 5.12.12）
  │
  ├─ 3. 根据 OS 执行平台特定安装流程
  │     ├─ Windows → §Windows
  │     ├─ macOS   → §macOS
  │     └─ Linux   → §Linux
  │
  ├─ 4. 运行 generate-env-local.sh → 生成 ENV.local.md
  │
  └─ 5. 运行 verify-env.sh → 验证环境
```

## Step 1: 环境检测

```bash
bash skills/kb-init/scripts/detect-env.sh
```

**Agent 行为**：
1. 运行脚本，解析 key=value 输出
2. 向用户展示检测结果摘要：
   - 主机平台和架构
   - 已安装的工具（DevEco / hdc / git 等）
   - 已定位的 Qt 源码和 SDK
3. 如果 `APP_DEVELOPER_READY=true`，告知用户环境已基本就绪，只需确认

## Step 2: 询问 Qt 源码获取方式

向用户提问：

> 你有 Qt 商业 license 吗？
> 1. **有 license** — 从 codereview.qt-project.org 获取源码（可选 Qt 5.12 或 5.15）
> 2. **无 license（开源）** — 从 GitCode 获取开源 Qt 5.12.12 源码
> 3. **只需预编译 SDK** — 下载预编译 SDK 包，不需要源码

**如果用户不确定**，推荐选项 3（预编译 SDK），这是最快上手的方式。

## Step 3: 平台特定安装流程

根据 `detect-env.sh` 输出的 `OS` 值，选择对应章节执行。

---

### Windows

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| DevEco Studio | `DEVECO_FOUND` | 下载：https://developer.huawei.com/consumer/cn/deveco-studio/ |
| Qt OHOS SDK | `QT5_12_SDK_FOUND` | 见下方获取方式 |

**Qt 源码/SDK 获取**：

**场景 A（有 license）**：
```powershell
# 1. 访问 https://codereview.qt-project.org → Settings → HTTP Credentials → 生成密码
# 2. Clone（必须在 PowerShell 中执行）
git clone https://codereview.qt-project.org/qt/tqtc-qt5 <目标路径>
cd <目标路径>
git checkout tqtc/harmonyos-5.12.12   # 或 tqtc/harmonyos-5.15.16
git submodule update --init --recursive
```

**场景 B（无 license，开源）**：
```powershell
git clone https://gitcode.com/ohos-qt/qt-harmonyos-src <目标路径>
cd <目标路径>
# 当前仅有 qt-harmonyos-src-5.12.12-20260625 版本
```

**场景 C（预编译 SDK）**：

访问发布页面下载：https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

可用的 SDK：

| 平台 | 渲染后端 | 说明 |
|------|----------|------|
| Windows | Desktop GL | Windows 平台开发，Desktop GL 渲染 |
| Windows | GLES | Windows 平台开发，GLES 渲染 |

下载对应版本，解压到指定路径。

**安装步骤**：
1. 如果 DevEco 未安装：引导用户下载安装，安装后重新运行 `detect-env.sh`
2. 根据用户选择的场景，引导获取 Qt SDK
3. 完成

---

### macOS

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| DevEco Studio | `DEVECO_FOUND` | 下载：https://developer.huawei.com/consumer/cn/deveco-studio/ |
| Qt OHOS SDK | `QT5_12_SDK_FOUND` | 见下方获取方式 |

**Qt 源码/SDK 获取**：

**场景 A（有 license）**：
```bash
git clone https://codereview.qt-project.org/qt/tqtc-qt5 <目标路径>
cd <目标路径>
git checkout tqtc/harmonyos-5.12.12   # 或 tqtc/harmonyos-5.15.16
git submodule update --init --recursive
```

**场景 B（无 license，开源）**：
```bash
git clone https://gitcode.com/ohos-qt/qt-harmonyos-src <目标路径>
cd <目标路径>
# 当前仅有 qt-harmonyos-src-5.12.12-20260625 版本
```

**场景 C（预编译 SDK）**：

访问发布页面下载：https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

| 平台 | 渲染后端 | 说明 |
|------|----------|------|
| macOS | Desktop GL | macOS 平台开发，Desktop GL 渲染 |
| macOS | GLES | macOS 平台开发，GLES 渲染 |

**安装步骤**：同 Windows。

---

### Linux

**注意**：DevEco Studio 没有 Linux GUI 版本。Linux 用户使用 HarmonyOS 命令行工具。

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| HarmonyOS SDK（命令行工具） | `OHOS_SDK_NATIVE_FOUND` | https://developer.huawei.com/consumer/en/download/ |
| Qt OHOS SDK | `QT5_12_SDK_FOUND` | 下载预编译 SDK |

**Qt 源码/SDK 获取**：同 macOS 场景（bash 命令相同）。

**安装步骤**：
1. 下载 HarmonyOS 命令行工具
2. 根据用户选择的场景，引导获取 Qt SDK
3. 如果 DevEco Studio 未检测到，不报错（Linux 正常）

---

## Step 4: 生成 ENV.local.md

收集完所有路径后：

```bash
bash skills/kb-init/scripts/generate-env-local.sh \
  --deveco-path="<DEVECO_PATH>" \
  --qt5-12-src="<QT5_12_SRC_PATH>" \
  --qt-build-root="<QT_BUILD_ROOT_PATH>" \
  --qt5-12-ohos-sdk="<QT5_12_OHOS_SDK_PATH>" \
  --ohos-sdk-native="<OHOS_SDK_NATIVE_PATH>"
```

**Agent 行为**：
1. 根据 Step 1 检测结果和 Step 2-3 收集的信息，组装参数
2. 只传用户实际有的路径，缺失的参数不传
3. 运行脚本
4. 向用户展示生成的 `ENV.local.md` 内容
5. 请用户确认或修改

## Step 5: 验证环境

```bash
bash skills/kb-init/scripts/verify-env.sh
```

**Agent 行为**：
1. 运行脚本
2. 如果 `STATUS=ready`：告知用户环境就绪
3. 如果 `STATUS=not-ready`：向用户展示缺失项，引导修复后重新验证

## 完成标志

- `ENV.local.md` 已生成
- DevEco Studio + OHOS SDK native + Qt OHOS SDK 均已就绪
- `verify-env.sh` 输出 `STATUS=ready`
- 用户确认环境配置正确

## 错误处理

| 错误 | 处理 |
|------|------|
| `detect-env.sh` 执行失败 | 检查 bash 版本 ≥ 4.0；检查脚本权限 `chmod +x` |
| `generate-env-local.sh` 写入失败 | 检查 KB 根目录写权限 |
| `verify-env.sh` 报告 FAIL | 按 FAIL 项的具体提示修复，重新运行 |
| 用户无法安装某个依赖 | 记录缺失项，告知用户哪些功能受限 |
| Linux 用户无 DevEco Studio | 正常——Linux 使用命令行工具，不报错 |
