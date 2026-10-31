---
name: qt-community-to-official
description: 指导用户将 Qt for OpenHarmony 应用从社区版（qtohextras/QtOhExtras）迁移到官方版（qtohosextras/QtOhosExtras）。当用户提到 社区版、官方版、QtOhExtras、QOhAppContext、qtohextras、ohextras、迁移 Qt OHOS 代码、修复 Qt OHOS 编译错误、生成迁移 patch、生成签名 hap 包、测试 Qt 应用启动时触发。涵盖代码迁移、patch 生成、编译修复、签名 hap 构建与测试。
---

# Qt for OpenHarmony 迁移：社区版 → 官方版

本 skill 将 Qt for OpenHarmony (OHOS) 应用从**社区版**（模块 `qtohextras` / `QtOhExtras`）
迁移到**官方版**（模块 `qtohosextras` / `QtOhosExtras`）。

所有 API 差异的权威参考文档位于本 skill 的 `docs/` 目录：

> **`docs/`**（相对于本 skill 基础目录）

**迁移前必须读取 `docs/` 下所有文档** — 包含完整的 API 映射表、代码示例和迁移速查表。
可随时向此目录添加新的迁移参考文档；始终扫描整个目录，而非仅读单个文件。

```bash
ls docs/    # 从本 skill 基础目录
```

## 适用场景

- 项目使用社区版 Qt OHOS API（`QtOhExtras`、`QOhAppContext`、`QOhFunctions`、
  `QOhFileShare`、`namespace QtOh`、`QT += ohextras`、`-platform openharmony`）。
- 用户需要迁移到官方版（`QtOhosExtras`、`QOhosAbilityContext`、`QT += ohosextras`、
  `-platform ohos`）。
- 用户需要在迁移后修复编译错误。
- 用户需要生成签名 `.hap` 包并验证应用启动不崩溃。

## Step 1：识别社区版代码并迁移为官方版

首先**选择 Qt 版本**（§1.0），然后读取版本特定文档和根文档，获取完整 API 映射。
接着获取工程路径和官方 SDK 路径，替换 Qt .so 文件，扫描项目中所有社区版 API 用法，
逐个替换为官方版等价物。

### 1.0 选择 Qt 版本

**这是第一步** — 在输入工程路径之前。从 `docs/` 子目录检测可用版本
（如 `docs/qt5.12.12/`、`docs/qt5.15.16/`）。

```bash
ls -d docs/qt*/ 2>/dev/null
```

提示用户：

> 请选择 Qt 版本（输入序号或版本号，直接 Enter 选择默认最高版本）

| 版本 | 根文档（通用） | 版本文档（特定） |
|------|--------------|----------------|
| Qt 5.12.12 | `docs/*.md` | `docs/qt5.12.12/Qt-Ohos-5.12.12-Diff.md`、`docs/qt5.12.12/qt_base.md` |
| Qt 5.15.16 | `docs/*.md` | `docs/qt5.15.16/Qt-Ohos-5.15.16-Diff.md` |

> **默认**：用户直接按 Enter，自动选择最高版本号。迁移同时使用根文档（通用修复）
> 和选定版本的差异文档（版本特定 API 差异）。

### 1.0a 获取路径并创建官方版工程

提示用户输入**两个路径**（模版自动从 `templates/` 读取）：

> 1. 请输入需要迁移的qt社区版工程路径
> 2. 请输入官方版 Qt SDK install 路径（含 lib/ 和 include/ 的目录）

```bash
# --- 1. 原始工程路径（胶水代码来源）---
ORIG_DIR="<用户输入>"
if [ "$ORIG_DIR" = "." ]; then ORIG_DIR="$(pwd)"; fi
[ -d "$ORIG_DIR" ] || { echo "错误: 原始工程目录不存在" >&2; exit 1; }

ORIG_NAME="$(basename "$ORIG_DIR")"
NEW_NAME="${ORIG_NAME}-official"

# --- 2. 模版工程（自动：使用与 SKILL.md 同目录的 templates/）---
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TEMPLATE_DIR="$SCRIPT_DIR/templates"
[ -d "$TEMPLATE_DIR" ] || { echo "错误: 模版工程目录不存在: $TEMPLATE_DIR" >&2; exit 1; }

# --- 3. 官方版 SDK install 路径 ---
SDK_DIR="<用户输入>"
[ -d "$SDK_DIR" ] || { echo "错误: SDK 目录不存在" >&2; exit 1; }

# --- 4. 在 skill 脚本同级目录创建新工程 ---
NEW_PROJECT_DIR="$SCRIPT_DIR/$NEW_NAME"
rm -rf "$NEW_PROJECT_DIR"
cp -r "$TEMPLATE_DIR" "$NEW_PROJECT_DIR"

# 删除模版中 libentry.so 相关文件（与导入的 CMakeLists.txt 库名冲突）
rm -f "$NEW_PROJECT_DIR/entry/src/main/cpp/hello.cpp"
rm -rf "$NEW_PROJECT_DIR/entry/src/main/cpp/types"
rm -f "$NEW_PROJECT_DIR/entry/oh_modules/@types/libentry.so"

cd "$NEW_PROJECT_DIR"
```

### 1.0b 导入胶水代码（合并，保留模版独有文件）

**胶水代码**是开发者编写的 C++ 应用代码 — 实际业务逻辑，不是 Qt SDK 或 ArkTS 壳。

```bash
ORIG_CPP="$ORIG_DIR/entry/src/main/cpp"
NEW_CPP="$NEW_PROJECT_DIR/entry/src/main/cpp"

# 模版独有文件/目录 — 不覆盖（已在上一步删除）
TEMPLATE_ONLY="types libentry hello.cpp"

mkdir -p "$NEW_CPP"
for item in "$ORIG_CPP"/*; do
    name=$(basename "$item")
    skip=false
    for t in $TEMPLATE_ONLY; do
        [ "$name" = "$t" ] && skip=true && break
    done
    if [ "$skip" = "true" ]; then continue; fi
    rm -rf "$NEW_CPP/$name"
    cp -r "$item" "$NEW_CPP/$name"
done
```

**导入资源文件**（合并，不覆盖模版配置文件）：

```bash
# 模版配置文件 — 保留不覆盖：
#   base/profile/main_pages.json   — 页面路由
#   base/element/string.json        — 字符串资源
#   base/element/color.json         — 颜色资源
TEMPLATE_CONFIGS="base/profile/main_pages.json base/element/string.json base/element/color.json"
```

**合并配置文件**（仅提取特定字段，不整体覆盖模版）：

| 文件 | 保留模版 | 从原工程合并 |
|------|---------|------------|
| `build-profile.json5` | `buildModeSet`、`modules` 等 | `signingConfigs`、`products` |
| `module.json5` | 整个文件 | 仅 `requestPermissions` |
| `AppScope/app.json5` | 模版配置 | `bundleName`、`vendor`、`versionCode`、`versionName`、`icon`、`label` |
| `entry/build-profile.json5` | — | 移除 `x86_64`，仅保留 `arm64-v8a` |
| `QtAppConstants.ets` | — | `APP_LIBRARY_NAME` 从 CMake `add_library(NAME SHARED)` 提取 |

### 1.0c 导入 SDK .so 文件

**仅替换原工程中已有的同名 .so** — 遍历 SDK 目录，只复制原工程中存在的 .so：

1. 遍历原工程所有 .so 文件，建立 `文件名 → [目录路径]` 索引
2. 对每个原工程 .so：
   - SDK 有同名 → 原地替换
   - 社区版改名文件 → 删除旧名，同目录放入官方版
   - SDK 无同名 → 跳过
3. 确保 `libqohos.so` 存在于所有 `platforms/` 目录
4. 确保 `libqohosstyle.so` 存在于所有 `styles/` 目录

**社区版 → 官方版 .so 重命名映射**：

| 社区版 .so | 官方版 .so | 类型 |
|---|---|---|
| `libQt5OhExtras.so` | `libQt5OhosExtras.so` | 库 |
| `libqopenharmony.so` | `libqohos.so` | 平台插件 |
| `libplugins_platforms_qopenharmony.so` | `libqohos.so` | 平台插件 |
| `libplugins_platforms_qohos.so` | `libqohos.so` | 平台插件 |
| `libplugins_styles_qharmonystyle.so` | `libqohosstyle.so` | 样式插件 |
| `libplugins_styles_qohosstyle.so` | `libqohosstyle.so` | 样式插件 |

**同时导入**：头文件 → `third_party/qt-ohos-dev/include/`，mkspecs → `third_party/qt-ohos-dev/mkspecs/`

后续所有步骤（§1.1–§4.6）在**新官方版工程**目录（`<skill_dir>/<原名>-official/`）下操作。

### 1.1 扫描社区版 API 标记

```bash
rg -n 'QtOhExtras|QOhAppContext|QOhFunctions|QOhFileShare|namespace QtOh|QT \+= ohextras|CONFIG \+= openharmony|libqopenharmony|platform openharmony|QOpenHarmony' --type cpp --type cmake
```

### 1.2 应用迁移映射

迁移由**选定 Qt 版本的文档**指导：

1. **读取版本特定文档**（`docs/qt<version>/*.md`）
2. **读取根文档**（`docs/*.md`）— 通用修复
3. **应用通用映射**（社区版 → 官方版）

#### 头文件（§9.1）

| 社区版 | 官方版 |
|---|---|
| `#include <QtOhExtras/QOhAppContext>` | `#include <QtOhosExtras/QOhosAbilityContext>` |
| `#include <QtOhExtras/QOhFunctions>` | `#include <QtOhosExtras/QOhosAppPermissions>` |
| `#include <QtOhExtras/QOhFileShare>` | `#include <QtOhosExtras/QOhosShareKit>` |

#### 类名和命名空间（§9.2）

| 社区版 | 官方版 | 说明 |
|---|---|---|
| `QOhAppContext` | `QOhosAbilityContext` | API 大幅增强 |
| `namespace QtOh` | `namespace QtOhosExtras` | 命名空间变更 |
| `QtOh::PermissionResult` | `AppPermissions::PermissionResult` | 枚举迁移 |
| `QtOh::checkPermission()` | `QOhosAbilityContext::requestPermissionFromUserIfNeeded()` | 检查→请求，同步→异步 |
| `QOhFileShare::shareFile()` | `QOhosAbilityContext::shareDataWithShareKit()` | API 完全重写 |
| `QOhAppContext::setColorMode()` | `QOhosPlatformIntegration::setDarkThemeEnabled()` | 主题 API 迁移 |

#### 构建配置（§4, §9.3）

| 配置项 | 社区版 | 官方版 |
|---|---|---|
| Qt 模块 | `QT += ohextras` | `QT += ohosextras` |
| 平台配置 | `CONFIG += openharmony` | `CONFIG += ohos` |
| 平台插件 | `libqopenharmony.so` | `libqohos.so` |
| 运行时平台参数 | `-platform openharmony` | `-platform ohos` |
| 部署 prf | `openharmony.prf` | `ohos_deployment.prf` |

#### 权限 API（§2.3, §10.1）— 同步 → 异步迁移

```cpp
// 社区版：同步阻塞
QtOh::PermissionResult result = QtOh::checkPermission("ohos.permission.CAMERA");

// 官方版：异步信号槽
auto ctx = QOhosAbilityContext::instance();
QObject::connect(ctx, &QOhosAbilityContext::namedPermissionRequestResponseReceived,
    [](QString permName, AppPermissions::PermissionResult result) { /* 处理结果 */ });
ctx->requestPermissionFromUserIfNeeded("ohos.permission.CAMERA");
```

#### 文件分享 API（§2.4, §10.2）— 完全重写

```cpp
// 社区版
QOhFileShare::shareFile(QUrl("file:///data/image.png"), "title");

// 官方版
auto ctx = QOhosAbilityContext::getDefaultInstance();
auto record = QSharedPointer<ShareKit::QOhosSharedRecord>::create();
record->setTitle("title");
record->addImage(QUrl("file:///data/image.png"));
auto options = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();
ctx->shareDataWithShareKit({record}, options);
```

### 1.3 窗口属性 API（§3）

标准 Qt 窗口 API 无需修改。如需 OHOS 特定窗口功能（圆角/隐私模式/亮度），使用官方版新增 API：

```cpp
#include <QtOhosExtras/QOhosWindowUtils>
QOhosPlatformWindow::setWindowCornerRadius(window, 20.0);
QOhosPlatformWindow::setWindowPrivacyMode(window, true);
```

### 1.4 验证无社区版标记残留

```bash
rg -n 'QtOhExtras|QOhAppContext|QOhFunctions|QOhFileShare|namespace QtOh[^o]|QT \+= ohextras\b|CONFIG \+= openharmony\b|platform openharmony\b' --type cpp --type cmake
# 预期：应用代码中零匹配
```

## Step 2：生成迁移 patch 文件

将迁移后的官方版工程与原工程对比，按目录生成 patch 文件。

### 2.1 确认 patch 输出目录

```bash
mkdir -p project-patches/<原工程名>/
```

### 2.2 按目录生成 patch

**对比基准**：原始工程 ←→ 官方版工程
**输出目录**：`project-patches/<原工程名>/`
**格式**：`git diff --no-index`（兼容 `git apply`）

```
project-patches/QtBugDemo/
├── root.patch                     # 顶层文件
├── AppScope.patch                 # AppScope/ 目录
├── entry.patch                    # entry/ 目录
├── entry_src_main_cpp.patch       # entry/src/main/cpp/ 目录
└── ...
```

**规则**：
- 所有 patch 扁平存放在 `project-patches/<原工程名>/` 下
- 文件名按目录路径命名（`/` → `_`，根目录 → `root`）
- 过滤 `.so`、`.py` 文件
- 排除 `.git`、`build`、`.hvigor`、`oh_modules`、`.cxx`、`.idea`、`third_party`
- 仅在有改动的目录生成 patch — 不生成空 patch

### 2.3 验证 patch

```bash
for patch in project-patches/<原工程名>/*.patch; do
    file_count=$(rg -c '^diff --git' "$patch" 2>/dev/null || echo 0)
    echo "$(basename "$patch"): ${file_count} files changed"
done
```

### 2.4 patch 回滚/重放

```bash
cd <project_root>
for patch in project-patches/<原工程名>/*.patch; do
    git apply --check "$patch"   # 预检
    git apply "$patch"           # 应用
done
```

### 2.5 输出路径并说明

> **迁移 patch 文件已生成**
>
> **生成数量**: N 个
> **目录**: `project-patches/<原工程名>/`
>
> **作用**: 记录 Step 1 迁移改动，按目录拆分
> **用途**: 回滚 / 重放 / 审查 / 归档 / 选择性应用

## Step 3：修复编译问题完成编译

### 3.0 构建环境准备

```bash
# 终止残留 hvigor 守护进程
pkill -f 'daemon-process-boot-script'
pkill -f 'hvigor-java-daemon'

# 设置 SDK 环境变量
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

> **DevEco Studio 警告**：如果 DevEco Studio 正在运行，可能会**回退外部文件编辑**。
> 应用修复前退出 DevEco Studio：`osascript -e 'quit app "DevEco-Studio"'`

### 3.1 构建工程

```bash
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

### 3.2 自动修复编译错误

编译失败时，**自动**读取 `fix-build-error/` 文档、匹配错误、应用修复、重新构建 — **不提示用户**。

**三层递进**：

```
编译失败
  ↓
Layer 1: fix-build-error/ 文档自动修复
  ↓ 修复成功 → 重新构建（回到顶部）
  ↓ 修复失败
Layer 2: 内置常见错误参考
  ↓ 匹配到 → 提示用户手动修复 → 重新构建（回到顶部）
  ↓ 未匹配到
Layer 3: 输出完整编译错误报告 + 工程路径
  ↓ 用户手动修复 → 重新构建（回到顶部，从 Layer 1 开始）
  ↓ 用户跳过 → 结束
```

**每次重新构建后如果仍然失败，始终从 Layer 1（fix-build-error/ 文档）开始重试。**

**fix-build-error/ 文档 Auto-fix 格式**：

```markdown
## Auto-fix

```yaml
match: "no member named 'SP_DialogSaveAllButton'"
files:
  - entry/src/main/cpp/pages/f19_qtoolbar.cpp
actions:
  - type: replace
    from: "QStyle::SP_DialogSaveAllButton"
    to: "QStyle::SP_DialogSaveButton"
```
```

**支持的 Action 类型**：

| 类型 | 字段 | 说明 |
|------|------|------|
| `replace` | `from`、`to` | 字符串替换 |
| `replace_regex` | `from`(正则)、`to` | 正则替换 |
| `remove_include` | `include` | 移除 `#include` 行 |
| `add_include` | `include` | 在最后一个 `#include` 后添加 |
| `remove_line` | `pattern` | 移除包含 pattern 的行 |
| `rewrite_cmake` | `target`、`qt_dev_dir` | 替换整个 CMakeLists.txt |

#### Layer 2：内置常见错误参考

| 错误 | 原因 | 修复 |
|------|------|------|
| `fatal error: 'QtOhExtras/xxx.h' file not found` | 旧头文件路径 | 替换为 `QtOhosExtras/xxx.h` |
| `QOhAppContext was not declared` | 类名变更 | 替换为 `QOhosAbilityContext` |
| `requestPermissionsSync` | 同步 API 已移除 | 改为异步信号槽 |
| `cannot find -lQt5OhExtras` | 旧模块名 | 使用 `QT += ohosextras` |
| `EPERM: operation not permitted, uv_cwd` | hvigor 守护进程 | 终止残留守护进程 |
| `00303217 Configuration Error` | `DEVECO_SDK_HOME` 未设置 | 设置环境变量 |
| `00308018 Unknown Error` | CMake 执行失败 | 检查 `find_package`/SDK 结构 |

#### Layer 3：完整错误报告

所有修复尝试失败后输出：
1. 过滤后的错误行（最多 20 条）
2. 构建命令、工程路径
3. 提示用 DevEco Studio 打开工程手动修复

### 3.3 CMake / qmake 配置

**精简 SDK**（无 `lib/cmake/`、无 `bin/`）— 使用直接路径链接：

```cmake
set(CMAKE_AUTOMOC OFF)
set(QT_OHOS_DEV_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../../third_party/qt-ohos-dev)
target_include_directories(myapp PRIVATE ${QT_OHOS_DEV_DIR}/include/QtCore ...)
target_link_libraries(myapp PRIVATE ${QT_OHOS_DEV_DIR}/lib/libQt5Core.so ...)
```

**完整 SDK**（有 `lib/cmake/` 和 `bin/`）— 使用 `find_package`：

```cmake
find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core Gui Widgets Network OhosExtras)
target_link_libraries(myapp PRIVATE Qt5::Core Qt5::OhosExtras)
```

### 3.4 迭代直到零错误

每次修复后重新构建。`hvigorw assembleHap` 成功且零错误时迁移完成。

### 3.5 刷新编译修复文档

构建完成后，**刷新已使用**的 `build-fix-*.md` 文档（不创建新时间戳文件）：

1. 收集所有构建尝试中的错误行
2. 匹配现有 `build-fix-*.md` 文档
3. 已覆盖 → 刷新（更新日期、状态、追加最新错误输出）
4. 未覆盖 → 在输出摘要中报告（不创建新文件）
5. 输出刷新的文档路径，提示用户上传

## Step 4：生成签名 hap 并测试启动

### 4.1 确认签名配置

签名在 `build-profile.json5` 的 `app.signingConfigs` 中配置（机器绑定自动签名）。

> 换机器构建时需在 DevEco Studio 中重新生成签名。

### 4.2 构建签名 hap

```bash
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

签名 `.hap` 文件输出路径：
```
entry/build/default/outputs/default/entry-default-signed.hap
```

### 4.3 安装并启动

```bash
# 检查设备连接
hdc list targets

# 安装
hdc install entry/build/default/outputs/default/entry-default-signed.hap

# 启动（ability 名称从 module.json5 读取，不硬编码）
hdc shell aa start -a <ability_name> -b <bundle_name>
```

> **ability 名称**：从 `entry/src/main/module.json5` → `"abilities"[0]."name"` 读取，
> 不硬编码为 `EntryAbility`。

### 4.4 验证启动不崩溃

```bash
# 检查进程存活（带重试）
sleep 2
hdc shell ps -ef | grep <bundle_name>

# 检查 hilog 崩溃日志
hdc shell hilog | grep -i "<bundle_name\|FATAL\|crash\|SIGSEGV"

# 检查 faultlog（仅检查本次运行新增的）
hdc shell ls /data/log/faultlog/temp/
```

**常见启动崩溃**：

| 崩溃症状 | 原因 | 修复 |
|---------|------|------|
| `dlopen failed: libQt5OhExtras.so not found` | 旧社区版库仍被引用 | 确保有 `libQt5OhosExtras.so` |
| `dlopen failed: libqopenharmony.so not found` | QPA 插件名不匹配 | 替换为 `libqohos.so` |
| `SIGSEGV in QOhosAbilityContext::instance()` | 上下文未初始化 | 延迟到 `QGuiApplication` 构造后访问 |
| `platform "ohos" not available` | QPA 插件缺失 | 确认 `libqohos.so` 在 platforms 目录 |

### 4.5 崩溃处理

**faultlog 时间戳检查**：启动前记录已有 faultlog，启动后仅检查新增的。

如果检测到**新增 faultlog**（本次运行崩溃）：
1. 显示崩溃日志内容
2. 显示常见崩溃原因表
3. 输出：`应用启动崩溃，需要用户手动修复。跳过崩溃处理步骤。`
4. **跳过此步骤** — 不进入修复循环
5. 用户手动修复后重新运行脚本验证

> **无修复循环**：脚本不会在崩溃后自动重新构建和测试。崩溃通常需要手动诊断
> （库替换、插件路径修正、代码修改）。脚本通知用户并跳到下一步。

### 4.6 功能冒烟测试

验证核心迁移功能正常工作：

1. **权限请求** — 触发权限操作，确认系统弹窗出现（不阻塞 UI）
2. **文件分享** — 触发分享操作，确认系统分享面板出现
3. **窗口渲染** — 确认主窗口正常显示（QHarmonyStyle）
4. **主题切换** — 如使用深色模式，确认 `setDarkThemeEnabled()` 生效

## 输出目录

| 目录 | 用途 | 使用步骤 |
|------|------|---------|
| `docs/` | 迁移参考文档（API 差异） | Step 1 — 迁移前读取所有文档 |
| `fix-build-error/` | 编译修复文档（错误→修复指南） | Step 3 — 编译失败时自动读取匹配 |
| `project-patches/` | 生成的 patch 文件（按目录） | Step 2（迁移）+ Step 3.5（编译修复） |
| `templates/` | 官方版模版工程 | Step 1.0b — 自动复制创建新工程 |

### `docs/` — 迁移参考

**根文档**（`docs/*.md`）— 所有 Qt 版本通用：
- `SP_DialogSaveAllButton.md` — SP_DialogSaveAllButton API 修复
- `delete_include.md` — 无用 include 移除
- `screen.md` — QWidget::screen() API 修复

**版本特定文档**（`docs/qt<version>/*.md`）— 在 §1.0 选择：

| 版本目录 | 文档 |
|---------|------|
| `docs/qt5.12.12/` | `Qt-Ohos-5.12.12-Diff.md`（版本差异）、`qt_base.md`（基础指南） |
| `docs/qt5.15.16/` | `Qt-Ohos-5.15.16-Diff.md`（版本差异） |

> 添加新版本：创建 `docs/qt<版本>/` 目录并放入差异文档。
> 添加根文档：在 `docs/` 下放置 `.md` 文件即可。

### `fix-build-error/` — 编译修复指南

编译失败时**自动**读取 `fix-build-error/` 下所有 `.md` 文件，匹配错误并应用修复。

每个 `build-fix-*.md` 包含 **`## Auto-fix`** YAML 区块，指定：
- `match`：匹配错误的正则
- `files`：要修改的源文件列表
- `actions`：修复动作列表

当前编译修复文档：

| 文档 | 错误 | 自动修复动作 |
|------|------|------------|
| `build-fix-04` | CMake `find_package` 回退到系统 Qt6 | `rewrite_cmake` |
| `build-fix-05` | QtOhosExtras 转发头文件缺失 | `remove_include` |
| `build-fix-06` | `QWidget::screen()` Qt 5.14+ API | `add_include` + `replace_regex` |
| `build-fix-07` | `SP_DialogSaveAllButton` Qt 5.15+ API | `replace` |
| `build-fix-08` | `compatibleSdkVersion` 不匹配 | `replace` |
| `build-fix-09` | ohpm `types/libentry` 缺失 | `remove_line` |
| `build-fix-10` | `EPERM: uv_cwd` 守护进程残留 | 终止守护进程（内置） |
| `build-fix-11` | DevEco Studio 回退编辑 | 警告（内置） |
| `build-fix-12` | `DEVECO_SDK_HOME` 未设置 | 自动设置环境变量（内置） |

> 添加新修复文档：在 `fix-build-error/` 下放置 `.md` 文件，包含 `## Auto-fix` YAML 区块即可。

### `project-patches/` — 生成的 patch 文件

- `<原工程名>/root.patch` — 顶层文件
- `<原工程名>/<目录路径>.patch` — 按目录拆分的迁移 patch

### `templates/` — 官方版模版工程

官方版 Qt for OpenHarmony 空工程模版，包含正确的构建配置、ArkTS 壳、签名配置。
Step 1.0b 自动复制此目录创建新工程。
