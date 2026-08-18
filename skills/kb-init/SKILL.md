# kb-init: 知识库初始化 Skill

> 引导用户完成 Qt for HarmonyOS 知识库的环境配置，达到"可以开始移植 Qt 应用"的状态。

---

## 触发条件

当以下任一条件满足时，**必须**执行本 skill：
- 用户说"初始化"、"配置环境"、"第一次使用"
- `ENV.local.md` 不存在
- 用户明确要求运行初始化

## 执行流程

### Step 1: 环境检测（确定性）

运行检测脚本，获取当前环境状态：

```bash
bash skills/kb-init/scripts/detect-env.sh
```

脚本输出结构化结果（key=value 格式），包括：
- `OS`：操作系统（windows / macos / linux）
- `DEVECO_FOUND`：DevEco Studio 是否已安装（true / false）
- `DEVECO_PATH`：DevEco Studio 路径（如已安装）
- `HDC_FOUND`：hdc 是否可用（true / false）
- `GIT_FOUND`：git 是否可用（true / false）
- `CMAKE_FOUND`：cmake 是否可用（true / false）
- `MINGW_FOUND`：MinGW 是否可用（true / false，仅 Windows）
- `PERL_FOUND`：Strawberry Perl 是否可用（true / false，仅 Windows）
- `QT5_12_SRC_FOUND`：Qt 5.12 源码是否已定位（true / false）
- `QT5_15_SRC_FOUND`：Qt 5.15 源码是否已定位（true / false）
- `QT5_12_SDK_FOUND`：Qt 5.12 OHOS SDK 是否已定位（true / false）
- `QT5_15_SDK_FOUND`：Qt 5.15 OHOS SDK 是否已定位（true / false）

**Agent 行为**：读取脚本输出，向用户展示检测结果摘要。

### Step 2: 引导补齐缺失依赖（交互式）

根据检测结果，逐项引导用户安装缺失依赖。

#### 2a. DevEco Studio + HarmonyOS SDK

如果 `DEVECO_FOUND=false`：
- 告知用户下载地址：https://developer.huawei.com/consumer/cn/deveco-studio/
- 版本要求：API 17 或更高
- 安装后重新运行 `detect-env.sh` 确认

如果 `DEVECO_FOUND=true`：
- 向用户确认检测到的路径是否正确

#### 2b. Qt 源码获取（解决 Issue #3）

询问用户属于哪种场景：

| 场景 | 获取方式 | Agent 行为 |
|------|----------|------------|
| **A. 有 Qt 商业 license** | codereview.qt-project.org | 引导用户执行 git clone + checkout + submodule update |
| **B. 无 license（开源）** | https://gitcode.com/ohos-qt/qt-harmonyos-src | 开源代码，无需 license |
| **C. 只需预编译 SDK** | https://gitcode.com/ohos-qt/qt-harmonyos-src/releases | 包含 Windows/macOS/HarmonyOS 多平台 SDK |

**场景 A 详细步骤**：
```bash
# 1. 生成 HTTP 密码：访问 https://codereview.qt-project.org → Settings → HTTP Credentials
# 2. Clone
git clone https://codereview.qt-project.org/qt/tqtc-qt5 <目标路径>
# 3. 切分支
cd <目标路径>
git checkout tqtc/harmonyos-5.12.12   # 或 tqtc/harmonyos-5.15.16
# 4. 子模块
git submodule update --init --recursive
```

**场景 B 详细步骤**：
```bash
# 从 GitCode 获取 Qt 鸿蒙开源代码
git clone https://gitcode.com/ohos-qt/qt-harmonyos-src <目标路径>
cd <目标路径>
git checkout tqtc/harmonyos-5.12.12   # 或 tqtc/harmonyos-5.15.16
```

**场景 C 详细步骤**：

访问发布页面下载预编译 SDK：
https://gitcode.com/ohos-qt/qt-harmonyos-src/releases

可用的 SDK 版本：

| 平台 | 渲染后端 | 说明 |
|------|----------|------|
| Windows | Desktop GL | Windows 平台开发，Desktop GL 渲染 |
| Windows | GLES | Windows 平台开发，GLES 渲染 |
| macOS | Desktop GL | macOS 平台开发，Desktop GL 渲染 |
| macOS | GLES | macOS 平台开发，GLES 渲染 |
| HarmonyOS | GLES | HarmonyOS 设备上运行，GLES 渲染 |

下载对应平台的 SDK 包，解压到指定路径。

Agent 根据用户选择的场景，引导完成获取步骤。

#### 2c. 构建工具链（仅 Windows 编译 Qt 时需要）

如果用户需要自己编译 Qt（场景 A 或 B），且 `OS=windows`：
- MinGW：如果 `MINGW_FOUND=false`，引导安装
- Strawberry Perl：如果 `PERL_FOUND=false`，引导安装 https://strawberryperl.com/

如果用户选择场景 C（预编译 SDK），跳过此步。

### Step 3: 生成 ENV.local.md（确定性）

收集完所有信息后，运行生成脚本：

```bash
bash skills/kb-init/scripts/generate-env-local.sh \
  --deveco-path="<DEVECO_PATH>" \
  --qt5-12-src="<QT5_12_SRC_PATH>" \
  --qt5-15-src="<QT5_15_SRC_PATH>" \
  --qt-build-root="<QT_BUILD_ROOT_PATH>" \
  --qt5-12-ohos-sdk="<QT5_12_OHOS_SDK_PATH>" \
  --qt5-15-ohos-sdk="<QT5_15_OHOS_SDK_PATH>" \
  --mingw-root="<MINGW_ROOT_PATH>" \
  --perl-root="<PERL_ROOT_PATH>"
```

参数说明：
- 只传用户实际有的路径，缺失的参数传空字符串或不传
- 脚本会生成 `ENV.local.md` 到知识库根目录

**Agent 行为**：
1. 根据 Step 1 和 Step 2 收集的信息，组装参数
2. 运行脚本
3. 向用户展示生成的 `ENV.local.md` 内容
4. 请用户确认或修改

### Step 4: 验证环境（确定性）

运行验证脚本：

```bash
bash skills/kb-init/scripts/verify-env.sh
```

脚本输出验证报告：
- `STATUS`：整体状态（ready / not-ready）
- 各项检查结果（pass / fail / skip）
- 如有 fail 项，列出具体缺失内容和修复建议

**Agent 行为**：
1. 运行脚本
2. 如果 `STATUS=ready`：告知用户环境就绪，可以开始使用知识库
3. 如果 `STATUS=not-ready`：向用户展示缺失项，引导修复后重新验证

## 完成标志

当以下条件全部满足时，初始化完成：
- `ENV.local.md` 已生成
- `verify-env.sh` 输出 `STATUS=ready`
- 用户确认环境配置正确

## 错误处理

| 错误 | 处理 |
|------|------|
| `detect-env.sh` 执行失败 | 检查 bash 是否可用；检查脚本权限 |
| `generate-env-local.sh` 执行失败 | 检查参数格式；检查写入权限 |
| `verify-env.sh` 报告 fail | 按修复建议逐项修复，重新运行 |
| 用户无法安装某个依赖 | 记录缺失项，告知用户哪些功能受限 |
