---
id: semantic-qt-harmonyos-build-run-workflow
type: semantic
domain: tech
tags: [qt, harmonyos, deveco-mcp, build, run, hilog, ui-test, troubleshooting, workflow]
created: 2026-06-02
updated: 2026-07-02
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-overview, semantic-harmonyos-dev-fundamentals]
summary: >
  Qt 鸿蒙编译运行全流程：DevEco MCP 工具链配置、构建/启动/日志/UI测试操作步骤、构建失败排查四步法。
---

# Qt 鸿蒙编译运行工作流

> 本页蒸馏自 `<INTERNAL_SKILL>`，覆盖从 MCP 配置到 UI 测试的完整链路。
> 构建环境搭建（configure、MinGW、Perl 等）详见 [[qt-harmonyos-build]]。

---

## 1. DevEco MCP 工具链

DevEco Toolbox = `deveco-toolbox`（可视化配置）+ `deveco-mcp-server`（MCP 服务），依赖 [[harmonyos-dev-fundamentals|DevEco Studio]]。

### 安装方式

| 方式 | 命令 / 步骤 | 适用场景 |
|------|-----------|---------|
| **npx（推荐）** | `npx -y @deveco-codegenie/mcp@beta` | IDE 项目级 MCP 配置 |
| **二进制** | GitHub Releases 下载 zip/dmg | 离线或无 Node 环境 |
| **可视化** | DevEco Toolbox GUI 一键添加到 IDE | Trae / Cursor 用户 |

### MCP JSON 配置模板（以 Cursor 为例）

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": ["-y", "@deveco-codegenie/mcp@beta"],
      "env": {
        "PROJECT_PATH": "${workspaceFolder}",
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

- `PROJECT_PATH`：工程路径，可通过 `init_project_path` 工具后续修改
- `DEVECO_PATH`：DevEco Studio 安装路径（无需到 bin 层）
- macOS 二进制安装后需执行 `xattr -cr /Applications/DevEco\ Toolbox.app`

### 可用工具清单

| 工具 | 功能 |
|------|------|
| `build_project` | 项目构建 |
| `start_app` | 启动应用（真机/模拟器） |
| `get_hilog_or_faultlog_recent` | 获取 hilog / faultlog 日志 |
| `get_app_ui_tree` | 获取当前页面 UI 树 |
| `perform_ui_action` | 执行 UI 操作（点击/滑动/输入/按键/截图） |
| `project_sync` | 项目同步（ohpm install） |
| `check_ets_files` | ArkTS 语法检查 |
| `check_cpp_files` | C/C++ 语法检查 |
| `harmonyos_knowledge_search` | 查询鸿蒙云端知识库 |
| `verify_ui` | UI 验证（可选） |
| `init_project_path` | 初始化/更改项目路径 |

---

## 2. 核心流程

```
项目同步 → 项目构建 → 启动应用 → 查看日志 → UI 测试（可选）
```

### Step 1: 项目同步（按需）

`project_sync` — 在修改 `oh-package.json5` 或首次初始化时执行。

### Step 2: 项目构建

`build_project` 关键参数：

| 参数 | 说明 | 默认 |
|------|------|------|
| `module` | 模块+Target，如 `'entry@default'` | 全部 |
| `build_mode` | `'debug'` / `'release'` | debug |
| `clean` | 是否先 clean | false |
| `log_path` | 构建日志保存路径 | — |
| `enable_inspector_source_jump` | UI 树跳转到源码 | — |

**Qt 工程要点**：
- CMakeLists.txt 须正确配置 Qt SDK 路径（`CMAKE_PREFIX_PATH`）
- `entry/build-profile.json5` 的 `externalNativeOptions.path` 须指向 CMakeLists.txt
- 首次构建建议 `clean: true`

#### hvigorw CLI 替代法（无 MCP init_project_path 时）

`build_project` 工具无 project path 参数，`init_project_path` 在部分 MCP 工具集不可用。此时可**命令行直调 hvigorw** 编译任意路径工程（批量编译/CI 场景必备）：

```bash
# 前置：工程 HarmonyOS/ 下有 local.properties（sdk.dir=C:\\Program Files\\Huawei\\DevEco Studio\\sdk）
export PATH="/c/Program Files/Huawei/DevEco Studio/jbr/bin:/c/Program Files/Huawei/DevEco Studio/tools/node:$PATH"
export DEVECO_SDK_HOME="C:\Program Files\Huawei\DevEco Studio\sdk"
cd "<工程目录>/HarmonyOS"
node "/c/Program Files/Huawei/DevEco Studio/tools/hvigor/bin/hvigorw.js" assembleHap \
  --mode module -p product=default -p buildMode=debug --no-daemon
```

关键环境：
- `DEVECO_SDK_HOME` 必须设（否则 `Configuration Error: Invalid value of 'DEVECO_SDK_HOME'`）
- PATH 必须含 DevEco JBR（`jbr/bin`，java，PackageHap/SignHap 需要；否则 `spawn java ENOENT`）+ DevEco node（`tools/node`，运行 hvigorw.js）
- 模板不含 hvigorw 包装器；直接 `node .../hvigorw.js`（引擎在 `tools/hvigor/{hvigor,hvigor-ohos-plugin}`）
- 模板根需有 `local.properties`：`sdk.dir=C:\\Program Files\\Huawei\\DevEco Studio\\sdk`

成功标志：`BUILD SUCCESSFUL` 且产物 `entry-default-unsigned.hap` 生成于 `entry/build/default/` 下（**编译工作流以未签名 HAP 为完成标志，签名是独立的后续步骤**；如需 signed HAP 需独立配置签名，不在编译工作流范围）。

> 2026-07-02 批量移植 10 个 Qt 开源应用用此法全部编译通过（10/10 unsigned HAP）。

### Step 3: 启动应用

`start_app` 关键参数：

| 参数 | 说明 | 默认 |
|------|------|------|
| `hvd` | 设备名称/ID | 列出可用设备 |
| `module` | 模块名 | `'entry'` |
| `ability` | Ability 名 | `'EntryAbility'` |

- 不指定设备时列出所有可用设备（真机 + 模拟器）
- 选择未运行的模拟器会自动启动

### Step 4: 查看日志

`get_hilog_or_faultlog_recent` 关键参数：

| 参数 | 说明 |
|------|------|
| `is_crash_log` | `false` = hilog, `true` = faultlog（崩溃日志） |
| `bundle_name` | 应用包名（自动 PID 过滤） |
| `level` | `D` / `I` / `W` / `E` / `F` |
| `tag` / `keyword` | 标签 / 正则关键字过滤 |

**Qt 应用常用查询**：

```
# 普通日志
bundle_name: 'com.example.qtapp', level: 'I'

# 错误日志
bundle_name: 'com.example.qtapp', level: 'E'

# 崩溃日志
is_crash_log: true, bundle_name: 'com.example.qtapp'

# 按 Qt 标签过滤
tag: 'Qt', level: 'D'
```

**Qt 特有日志关键字**：

| 日志信息 | 原因 |
|---------|------|
| `dlopen failed: library "libqohos.so" not found` | 平台插件未部署 |
| `dlopen failed: library "libQt5Core.so" not found` | Qt 核心库未部署 |
| `Cannot load Qt platform plugin` | 平台插件加载失败 |
| `module "QtQuick" is not installed` | QML 模块未配置 |

### Step 5 & 6: UI 树与 UI 操作

**获取 UI 树** — `get_app_ui_tree`：
- `mode: 'full'`（完整 UI 树）或 `'simple'`（窗口节点）
- `outputDirectory`：JSON 保存路径

**执行 UI 操作** — `perform_ui_action`：

| actionType | 关键参数 | 说明 |
|------------|---------|------|
| `click` | `x`, `y` | 单击 |
| `directionalFling` | `direction`(0左/1右/2上/3下), `velocity`, `stepLength` | 滑动 |
| `inputText` | `x`, `y`, `text` | 输入文本 |
| `keyEvent` | `key1`/`key2`/`key3`（Back/Home/Power/KeyCode） | 按键 |
| `screenshot` | `localPath` | 截图保存到本地 |

---

## 3. 构建失败排查（四步法）

> ⚠️ 此流程对构建错误和运行时错误**均强制生效**。

### Step A: 知识库优先查询

检查当前工作目录是否存在 `compile_fix_pro.md`：
- **存在** → 先搜索已知方案，找到则直接应用
- **不存在** → 跳过，进入 Step B

### Step B: 错误分类

| 环节 | 关键词 | 示例 |
|------|--------|------|
| 预处理 | `#include not found`, `No such file or directory` | 头文件路径缺失 |
| 编译 | `error:`, `undefined reference`（源码级） | 语法错误、API 不兼容 |
| 链接 | `undefined symbol`, `cannot find -l`, `multiple definition` | 库缺失、符号冲突 |
| 打包 | `BUILD FAILED`, `hap`, `sign`, `resource` | Hvigor/签名/资源 |

### Step C: 修复与重试

| 规则 | 要求 |
|------|------|
| 最大重试 | 同一错误最多 **3 次** |
| 方案不重复 | 每次必须用**不同方案** |
| 超限 | 立即停止，整理错误上下文 + 已尝试方案，**向用户求助** |

### Step D: 修复沉淀

- ✅ 成功 → 记入 `compile_fix_pro.md`（若存在）
- ❌ 失败（超限）→ 向用户提供：错误信息 + 根因分析 + N 种方案及失败原因

**`compile_fix_pro.md` 记录格式**：

```markdown
## <问题标题>
- 问题描述：<具体错误信息>
- 发生环节：编译 / 链接 / 打包 / 运行
- 产生原因：<根因分析>
- 修复方案：<具体步骤与代码改动>
- 改动文件：<文件列表>
```

### 运行时错误处理

与构建失败共用 Step A → D 流程，但**发生环节标记为「运行」**：

1. 获取崩溃日志：`is_crash_log: true` + `bundle_name`
2. 获取错误日志：`level: 'E'` + `bundle_name`
3. 查 `compile_fix_pro.md`
4. 分类 → 修复 → 沉淀

---

## 4. 常见问题速查

### 构建问题

| 问题 | 排查 |
|------|------|
| CMake 配置失败 | 检查 `entry/build-profile.json5` 的 `externalNativeOptions.path` |
| Qt 模块找不到 | 检查 `CMAKE_PREFIX_PATH` 是否指向正确 Qt SDK |
| 编译错误 | 用 `log_path` 保存详细日志分析 |

### 启动问题

| 问题 | 排查 |
|------|------|
| 应用无法启动 | 确认构建成功 + 查看错误日志 |
| 模拟器启动失败 | 确认 DevEco Studio 已安装模拟器 |
| 真机连接失败 | 检查 USB + 开发者模式 |

### 运行时问题

| 问题 | 排查 |
|------|------|
| Qt 库加载失败 | 查日志中 dlopen 错误，检查库部署 |
| 平台插件失败 | 确认 `libqohos.so` 已正确部署 |
| QML 加载失败 | 检查 QML 资源文件和模块配置 |
| 应用崩溃 | `is_crash_log: true` 获取崩溃日志 |

---

## 参考来源

- 原始 Skill 文件：`<INTERNAL_SKILL>`
- 前置铁律：`<INTERNAL_SKILL>`（第 10–140 行）
- DevEco Toolbox GitHub: https://github.com/open-deveco/deveco-toolbox
- DevEco MCP Releases: https://github.com/open-deveco/deveco-mcp/releases
- 飞书指导文档: https://<INTERNAL_DOC>
