---
name: kb-init
description: |
  Qt for HarmonyOS 知识库环境初始化。检测主机平台、引导用户选择角色（应用开发者/框架开发者）和 Qt 版本（5.12/5.15），
  自动安装缺失依赖、生成 ENV.local.md、验证环境就绪。
  当用户说"初始化"、"配置环境"、"第一次使用"、"setup"、"install"，
  或 ENV.local.md 不存在时，必须触发此 skill。
  即使用户没有明确说"初始化"，只要是第一次与知识库交互，也应主动建议运行。
---

# kb-init: 知识库初始化

引导用户完成 Qt for HarmonyOS 知识库的全量环境配置。

## 决策树

```
开始
  │
  ├─ 1. 运行 detect-env.sh → 获取 OS / 已有工具 / 已有 Qt
  │
  ├─ 2. 询问用户角色
  │     ├─ 应用开发者（移植 Qt 应用到鸿蒙）→ 快速路径
  │     └─ 框架开发者（编译/修改 Qt 框架）→ 完整路径
  │
  ├─ 3. 询问 Qt 版本
  │     ├─ 5.15（推荐，大多数项目使用）
  │     ├─ 5.12（旧项目维护）
  │     └─ 两个都要
  │
  ├─ 4. 根据 OS + 角色 + 版本，执行平台特定安装流程
  │     ├─ Windows 应用开发者 → §Windows-App
  │     ├─ Windows 框架开发者 → §Windows-Fw
  │     ├─ macOS 应用开发者   → §macOS-App
  │     ├─ macOS 框架开发者   → §macOS-Fw
  │     ├─ Linux 应用开发者   → §Linux-App
  │     └─ Linux 框架开发者   → §Linux-Fw
  │
  ├─ 5. 运行 generate-env-local.sh → 生成 ENV.local.md
  │
  └─ 6. 运行 verify-env.sh --role=ROLE → 验证环境
```

## Step 1: 环境检测

```bash
bash skills/kb-init/scripts/detect-env.sh
```

**Agent 行为**：
1. 运行脚本，解析 key=value 输出
2. 向用户展示检测结果摘要：
   - 主机平台和架构
   - 已安装的工具（DevEco / hdc / git / cmake 等）
   - 已定位的 Qt 源码和 SDK
3. 如果 `APP_DEVELOPER_READY=true` 或 `FRAMEWORK_DEVELOPER_READY=true`，告知用户环境已基本就绪，只需确认

## Step 2: 询问用户角色

向用户提问：

> 你是哪种角色？
> 1. **应用开发者** — 把 Qt 应用移植到鸿蒙，使用预编译 SDK
> 2. **框架开发者** — 编译或修改 Qt 框架本身，需要 Qt 源码和完整工具链

**如果用户不确定**，默认推荐"应用开发者"。

## Step 3: 询问 Qt 版本

向用户提问：

> 你需要哪个 Qt 版本？
> 1. **Qt 5.15**（推荐）— 大多数新项目使用
> 2. **Qt 5.12** — 旧项目维护
> 3. **两个都要**

## Step 4: 平台特定安装流程

根据 `detect-env.sh` 输出的 `OS` 值和用户角色，选择对应章节执行。

---

### Windows-App（Windows 应用开发者）

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| DevEco Studio | `DEVECO_FOUND` | 下载：https://developer.huawei.com/consumer/cn/deveco-studio/ |
| Qt OHOS SDK | `QT5_15_SDK_FOUND` 或 `QT5_12_SDK_FOUND` | 下载预编译 SDK：https://gitcode.com/ohos-qt/qt-harmonyos-src/releases |

**SDK 选择**（根据用户选择的 Qt 版本和渲染需求）：

| 平台 | 渲染后端 | 适用场景 |
|------|----------|----------|
| Windows | Desktop GL | 大多数桌面场景 |
| Windows | GLES | 需要与设备端一致的渲染行为 |

**安装步骤**：
1. 如果 DevEco 未安装：引导用户下载安装，安装后重新运行 `detect-env.sh`
2. 如果 SDK 未定位：引导用户从发布页面下载对应版本，解压到指定路径
3. 跳过 MinGW / Perl / cmake（应用开发者不需要）

---

### Windows-Fw（Windows 框架开发者）

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| DevEco Studio | `DEVECO_FOUND` | 同上 |
| Qt 源码 | `QT5_15_SRC_FOUND` 或 `QT5_12_SRC_FOUND` | `git clone https://gitcode.com/ohos-qt/qt-harmonyos-src` |
| MinGW | `MINGW_FOUND` | https://www.mingw-w64.org/ |
| Strawberry Perl | `PERL_FOUND` | https://strawberryperl.com/ |
| cmake | `CMAKE_FOUND` | https://cmake.org/download/ |
| PowerShell | `POWERSHELL_FOUND` | Windows 自带 |

**重要**：Qt 编译命令必须在 PowerShell 中执行，不能在 bash/git-bash 中运行。

**安装步骤**：
1. DevEco Studio（同上）
2. Qt 源码：`git clone https://gitcode.com/ohos-qt/qt-harmonyos-src <路径>` → `git checkout tqtc/harmonyos-5.15.16`（或 5.12.12）
3. MinGW + Strawberry Perl + cmake
4. 验证 PowerShell 可用

---

### macOS-App（macOS 应用开发者）

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| DevEco Studio | `DEVECO_FOUND` | 下载：https://developer.huawei.com/consumer/cn/deveco-studio/ |
| Qt OHOS SDK | `QT5_15_SDK_FOUND` 或 `QT5_12_SDK_FOUND` | 下载预编译 SDK |

**SDK 选择**：

| 平台 | 渲染后端 | 适用场景 |
|------|----------|----------|
| macOS | Desktop GL | 大多数桌面场景 |
| macOS | GLES | 需要与设备端一致的渲染行为 |

**安装步骤**：同 Windows-App，跳过 MinGW / Perl。

---

### macOS-Fw（macOS 框架开发者）

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| DevEco Studio | `DEVECO_FOUND` | 同上 |
| Xcode CLT | `XCODE_CLT_FOUND` | `xcode-select --install` |
| Qt 源码 | `QT5_15_SRC_FOUND` 或 `QT5_12_SRC_FOUND` | `git clone` |
| cmake | `CMAKE_FOUND` | `brew install cmake` 或 https://cmake.org |

**注意**：macOS 不需要 MinGW 和 Strawberry Perl（那是 Windows 专属）。

---

### Linux-App（Linux 应用开发者）

**注意**：DevEco Studio 没有 Linux GUI 版本。Linux 用户使用 DevEco CLI 或命令行工具。

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| HarmonyOS SDK（命令行工具） | `OHOS_SDK_NATIVE_FOUND` | https://developer.huawei.com/consumer/en/download/ |
| Qt OHOS SDK | `QT5_15_SDK_FOUND` 或 `QT5_12_SDK_FOUND` | 下载预编译 SDK |

**安装步骤**：
1. 下载 HarmonyOS 命令行工具
2. 下载预编译 Qt SDK
3. 如果 DevEco Studio 未检测到，不报错（Linux 正常）

---

### Linux-Fw（Linux 框架开发者）

**必需依赖**：

| 依赖 | 检测变量 | 缺失时的安装方式 |
|------|----------|-----------------|
| HarmonyOS SDK | `OHOS_SDK_NATIVE_FOUND` | 同上 |
| Qt 源码 | `QT5_15_SRC_FOUND` 或 `QT5_12_SRC_FOUND` | `git clone` |
| cmake | `CMAKE_FOUND` | 包管理器安装 |
| gcc/g++ | 系统自带 | 包管理器安装 |

---

## Step 5: 生成 ENV.local.md

收集完所有路径后：

```bash
bash skills/kb-init/scripts/generate-env-local.sh \
  --role=<app-developer|framework-developer> \
  --qt-version=<5.12|5.15|both> \
  --deveco-path="<DEVECO_PATH>" \
  --qt5-12-src="<QT5_12_SRC_PATH>" \
  --qt5-15-src="<QT5_15_SRC_PATH>" \
  --qt-build-root="<QT_BUILD_ROOT_PATH>" \
  --qt5-12-ohos-sdk="<QT5_12_OHOS_SDK_PATH>" \
  --qt5-15-ohos-sdk="<QT5_15_OHOS_SDK_PATH>" \
  --mingw-root="<MINGW_ROOT_PATH>" \
  --perl-root="<PERL_ROOT_PATH>" \
  --ohos-sdk-native="<OHOS_SDK_NATIVE_PATH>"
```

**Agent 行为**：
1. 根据 Step 1 检测结果和 Step 2-4 收集的信息，组装参数
2. 只传用户实际有的路径，缺失的参数不传
3. 运行脚本
4. 向用户展示生成的 `ENV.local.md` 内容
5. 请用户确认或修改

## Step 6: 验证环境

```bash
bash skills/kb-init/scripts/verify-env.sh --role=<app-developer|framework-developer>
```

**Agent 行为**：
1. 运行脚本
2. 如果 `STATUS=ready`：告知用户环境就绪
3. 如果 `STATUS=not-ready`：向用户展示缺失项，引导修复后重新验证

## 完成标志

| 角色 | 完成条件 |
|------|----------|
| 应用开发者 | DevEco + OHOS SDK native + Qt OHOS SDK + ENV.local.md + verify pass |
| 框架开发者 | 上述 + Qt 源码 + cmake + (Windows: MinGW + Perl) + verify pass |

## 错误处理

| 错误 | 处理 |
|------|------|
| `detect-env.sh` 执行失败 | 检查 bash 版本 ≥ 4.0；检查脚本权限 `chmod +x` |
| `generate-env-local.sh` 写入失败 | 检查 KB 根目录写权限 |
| `verify-env.sh` 报告 FAIL | 按 FAIL 项的具体提示修复，重新运行 |
| 用户无法安装某个依赖 | 记录缺失项，告知用户哪些功能受限 |
| Linux 用户无 DevEco Studio | 正常——Linux 使用命令行工具，不报错 |
