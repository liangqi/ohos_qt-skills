---
name: build-run-qt-app
description: 使用DevEco MCP工具链编译、运行Qt鸿蒙应用并查看日志。支持项目构建、应用启动、日志获取、UI操作等功能。适用于Qt鸿蒙工程的编译测试流程。
---

# Qt鸿蒙工程编译运行与日志查看

> **⚠️ 铁律继承（强制）**：在执行本 skill 的任何步骤之前，**必须先读取** `../compile_qt_tool/SKILL.md` 的第 10–140 行（`### 0、铁律` 完整章节），并在本 skill 执行期间**全程遵守**其中的所有铁律。
>
> 铁律优先级 **高于** 本 skill 的任何指令。若本 skill 的操作与铁律冲突，以铁律为准。

使用DevEco MCP工具链完成Qt鸿蒙应用的编译、运行和日志查看。

**核心功能**：
- 项目构建（build_project）
- 应用启动（start_app）
- 日志获取（get_hilog_or_faultlog_recent）
- UI树获取（get_app_ui_tree）
- UI操作（perform_ui_action）

**适用场景**：
- Qt鸿蒙工程的编译测试
- 运行时问题排查（查看日志）
- UI交互测试

---

## 前置条件：DevEco MCP工具链安装配置

**在使用本skill之前，必须先安装配置DevEco MCP工具链。**

DevEco Toolbox 是一个工具集（依赖于 [DevEco Studio](https://developer.huawei.com/consumer/cn/download/)）。在不打开 DevEco Studio 的情况下，可以在 Trae、Cursor、VS Code 等 AI IDE 中完成鸿蒙应用开发的大多数工作。

DevEco Toolbox 包含两个可执行文件：
- `deveco-toolbox` — 用于可视化配置
- `deveco-mcp-server` — 主要的 MCP 服务

### 安装方式一：npx 安装（推荐）

从 v0.1.4 版本开始，支持通过 npx 配置鸿蒙工具箱 MCP，该方法将拉取最新版本 Toolbox 与 MCP Server。

> **提示**：在 CLI 上使用推荐配置项目级 MCP。支持智能查找当前目录下的鸿蒙工程（多鸿蒙工程不适用），可在父目录使用 MCP 进行作业。无法获取项目根路径时可通过 `init_project_path` 工具更改初始化路径。

#### 各 IDE 配置示例

**Trae CN**（项目级 `.trae/mcp.json`）：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@deveco-codegenie/mcp@beta"
      ],
      "env": {
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

**Trae 国际版**：

```json
{
  "servers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@deveco-codegenie/mcp@beta"
      ],
      "env": {
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

**Cursor**（需指定 `PROJECT_PATH`，`${workspaceFolder}` 可能不支持时需手动替换）：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@deveco-codegenie/mcp@beta"
      ],
      "env": {
        "PROJECT_PATH": "${workspaceFolder}",
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

**VS Code / Gemini Code Assist**：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@deveco-codegenie/mcp@beta"
      ],
      "env": {
        "PROJECT_PATH": "path/to/your/project",
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

**Claude Desktop**：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@deveco-codegenie/mcp@beta"
      ],
      "env": {
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

**Gemini CLI**：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@deveco-codegenie/mcp@beta"
      ],
      "env": {
        "PROJECT_PATH": ".",
        "DEVECO_PATH": "path/to/your/deveco"
      }
    }
  }
}
```

**OpenCode**：

```json

"mcp": {
  "deveco-mcp": {
    "command": [
      "npx",
      "-y",
      "@deveco-codegenie/mcp@beta"
    ],
    "type": "local",
    "enabled": true,
    "timeout": 20000,
    "environment": {
      "PROJECT_PATH": ".",
      "DEVECO_PATH": "path/to/your/deveco"
    }
  }
}
```

**参数说明**：
- `PROJECT_PATH`: 工程路径。可不填写，通过调用 `init_project_path` 工具初始化。部分 IDE 支持 `${workspaceFolder}` 自动解析
- `DEVECO_PATH`: DevEco Studio 安装路径（无需到 bin 一层）

> **注意**：若 IDE 暂不支持项目路径解析，请手动将 `PROJECT_PATH` 设为实际项目路径。在大型工程下，工具箱会占用部分内存。

### 安装方式二：二进制安装

#### 下载地址

- GitHub Releases: https://github.com/open-deveco/deveco-mcp/releases

#### Windows 安装步骤

1. 下载 zip 包并解压（文件夹应包含 `deveco-toolbox.exe`、`deveco-mcp-server.exe` 和 `arkts-lang-server` 目录）
2. 尽量避免在安装路径中包含特殊字符或中文，部分 AI IDE 不支持解析此类路径

#### macOS 安装步骤

1. 下载并安装 dmg 程序
2. 打开终端执行以下命令：

```bash
xattr -cr /Applications/DevEco\ Toolbox.app
```

#### 二进制 MCP 配置（Windows 示例）

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "cmd",
      "args": [
        "/C",
        "D:\\program_files\\deveco-mcp_x64_windows\\deveco-mcp-server.exe"
      ],
      "env": {
        "PROJECT_PATH": "${workspaceFolder}"
      }
    }
  }
}
```

**注意**：如果 IDE 不支持 `${workspaceFolder}` 变量替换，需要手动替换为指定路径。

### 安装方式三：DevEco Toolbox 可视化配置

1. 下载并安装 DevEco Toolbox（https://github.com/open-deveco/deveco-toolbox/releases）
   - **macOS**: 下载 dmg 文件双击安装后，终端执行 `xattr -cr /Applications/DevEco\ Toolbox.app`
   - **Windows**: 下载 zip 包并解压，点击 `deveco-toolbox.exe` 启动
2. 启动后会自动探测本机安装的 DevEco Studio 路径，若未检测到需手动指定
3. 在可选配置中，可单独配置模拟器路径和镜像路径
4. 界面上已放置"添加到 Trae"和"添加到 Cursor"的按钮，点击即可将 MCP 配置添加到对应 IDE 中。如果是其他 IDE，可通过复制 MCP JSON 配置的方式手动添加

### ArkTS 语法校验插件（可选）

DevEco Toolbox 附带 ArkTS 语法校验插件，基于鸿蒙官方 DevEco Studio 编辑器的 LSP 语言服务器开发，支持语法高亮、代码 Hover 提示、定义跳转和引用查找。

**安装方式**：
- **方式一**：在 Toolbox 中一键安装到 Trae CN / Cursor
- **方式二**：手动安装 — 在 Toolbox 所在目录找到 ArkTS 高亮插件 vsix，将插件拖到对应 IDE 插件市场进行安装

**使用方式**：打开 IDE 后，右下角有一个状态指示，当插件初始化完成后变为白色，表示可以正常校验 ArkTS 语法。

### 验证 MCP 安装成功

安装完成后，在 AI IDE 中应能看到以下 MCP 工具：

| 工具名称 | 主要功能 | 备注 |
|---------|---------|------|
| `harmonyos_knowledge_search` | 查询鸿蒙云端知识库 | |
| `check_ets_files` | 对 ets 文件进行语法检查 | |
| `check_cpp_files` | 对 C/C++ 文件进行语法检查 | |
| `build_project` | 进行项目构建 | |
| `start_app` | 在模拟器或真机中启动应用 | |
| `get_app_ui_tree` | 获取 app 当前页面的 UI 树 | |
| `perform_ui_action` | 执行 UI 操作（点击、滑动、输入等） | |
| `verify_ui` | UI 验证 | 可选 |
| `get_hilog_or_faultlog_recent` | 获取 hilog/faultlog 日志 | |
| `project_sync` | 执行项目同步（ohpm install） | |
| `init_project_path` | 初始化/更改项目路径 | 可选 |

> **注意**：若出现 MCP 可用工具缺失问题，通常由 LSP 初始化未完成导致，重新启动 MCP 即可解决。

---

## 核心流程

```
项目同步 → 项目构建 → 启动应用 → 查看日志 → UI测试（可选）
```

---

## Step 1: 项目同步（可选）

如果项目依赖有变化，先执行项目同步：

**使用 `project_sync` 工具**：

```
参数：
- skip_ohpm_install: 是否跳过ohpm install（可选，默认false）
- product: 指定的Product名称（可选，默认'default'）
```

**示例场景**：
- 项目初始化时
- 修改 oh-package.json5 后
- 遇到依赖缺失问题时

---

## Step 2: 项目构建

**使用 `build_project` 工具**：

### 参数说明

| 参数 | 说明 | 是否必填 |
|------|------|---------|
| `module` | 指定的模块及Target（如 'entry@default'） | 可选 |
| `product` | 指定的Product名称 | 可选 |
| `build_mode` | 构建模式（'debug'/'release'） | 可选，默认debug |
| `clean` | 是否先执行clean清理 | 可选，默认false |
| `log_path` | 构建日志保存路径 | 可选 |
| `enable_inspector_source_jump` | 支持UI树跳转到源码位置 | 可选 |

### 构建示例

**构建整个APP**：
```
build_mode: 'debug'
clean: false
```

**构建指定模块**：
```
module: 'entry@default'
build_mode: 'debug'
```

**清理后构建**：
```
clean: true
build_mode: 'debug'
```

**Qt工程构建注意事项**：
- Qt工程的CMakeLists.txt需要正确配置Qt SDK路径
- 确保 `entry/build-profile.json5` 的 `externalNativeOptions.path` 正确指向CMakeLists.txt
- 首次构建建议设置 `clean: true`

### 构建失败排查

> ⚠️ **本节规则在任何调用场景下均强制生效**（无论是独立使用还是被 `compile_qt_tool` 调用）。

**Step A: 知识库优先查询**

遇到构建错误时，**第一动作**是检查当前工作目录是否存在 `compile_fix_pro.md`（问题解决知识库）：

| 情况 | 执行动作 |
|------|---------|
| `compile_fix_pro.md` 存在 | **必须先在其中搜索是否有已知方案**，找到则直接应用 |
| `compile_fix_pro.md` 不存在 | 跳过知识库查询，进入 Step B |

**Step B: 错误分类与分析**

识别错误产生在哪个环节（决定修复策略）：

| 环节 | 典型错误关键词 | 示例 |
|------|--------------|------|
| **预处理** | `#include not found`、`No such file or directory`（头文件） | 头文件路径缺失、宏定义错误 |
| **编译** | `error:`、`undefined reference`（源码级别） | 语法错误、API 不兼容、缺少类型定义 |
| **链接** | `undefined symbol`、`cannot find -l`、`multiple definition` | 库缺失、符号冲突、链接顺序 |
| **打包** | `BUILD FAILED`、`hap`、`sign`、`resource` | Hvigor 配置、签名、资源文件 |

**Step C: 修复尝试与重试策略**

| 规则 | 要求 |
|------|------|
| 最大重试次数 | 同一错误最多 **3 次** |
| 方案不可重复 | 每次修复尝试必须使用**不同方案**（禁止重复同一修复方式） |
| 超限处理 | 超过 3 次 → **立即停止**，整理完整的错误上下文和已尝试方案，向用户求助 |

**Step D: 修复沉淀**

| 修复结果 | 执行动作 |
|---------|---------|
| ✅ 修复成功 | 将问题及解决方案**按格式记入 `compile_fix_pro.md`**（若文件存在） |
| ❌ 修复失败（未超限） | 换方案重试，回到 Step C |
| ❌ 修复失败（已超限） | 向用户求助，提供：错误信息、根因分析、已尝试的 N 种方案及失败原因 |

**`compile_fix_pro.md` 记录格式**：
```
## <问题标题>
- 问题描述：<具体的错误信息>
- 发生环节：编译 / 链接 / 打包 / 运行
- 产生原因：<根因分析>
- 修复方案：<具体的修复步骤与代码改动>
- 改动文件：<涉及修改的文件列表>
```

**基础排查清单**（在上述流程中按需使用）：

1. 使用 `log_path` 参数保存详细构建日志
2. 检查 CMake/qmake 配置是否正确
3. 检查 Qt SDK 路径（`CMAKE_PREFIX_PATH`）是否配置
4. 检查 `entry/build-profile.json5` 的 `externalNativeOptions` 配置

---

## Step 3: 启动应用

**使用 `start_app` 工具**：

### 参数说明

| 参数 | 说明 | 是否必填 |
|------|------|---------|
| `hvd` | 目标设备名称或ID | 可选（不指定则列出可用设备） |
| `module` | 要启动的模块名称 | 可选，默认'entry' |
| `ability` | 要启动的Ability名称 | 可选，默认'EntryAbility' |
| `target` | 构建目标 | 可选，默认'default' |

### 启动流程

1. **不指定设备**：工具会列出所有可用设备供选择
2. **选择设备**：可以是已连接的真机或模拟器
3. **自动启动模拟器**：如果选择未运行的模拟器，会自动启动

### 启动示例

**列出可用设备**：
```
不传任何参数
```

**在指定设备启动**：
```
hvd: 'emulator-5554'  // 模拟器ID
module: 'entry'
ability: 'EntryAbility'
```

### Qt应用启动注意事项

- Qt应用使用 `EntryAbility` 作为入口
- 确保应用已正确构建
- 首次启动可能需要等待模拟器启动

---

## Step 4: 查看日志

**使用 `get_hilog_or_faultlog_recent` 工具**：

### 参数说明

| 参数 | 说明 | 是否必填 |
|------|------|---------|
| `hvd` | 目标设备 | 可选 |
| `is_crash_log` | 是否获取崩溃日志（faultlog） | 可选，默认false |
| `bundle_name` | 应用包名（自动获取PID过滤） | 可选 |
| `level` | 日志级别（D/I/W/E/F） | 可选 |
| `tag` | 过滤标签 | 可选 |
| `domain` | 日志领域 | 可选 |
| `keyword` | 关键字过滤（正则表达式） | 可选 |
| `log_size` | 日志缓冲区大小 | 可选，默认4M |

### 日志类型

**普通日志（hilog）**：
```
is_crash_log: false
```

**崩溃日志（faultlog）**：
```
is_crash_log: true
```

### 日志级别

| 级别 | 说明 |
|------|------|
| D | Debug |
| I | Info |
| W | Warning |
| E | Error |
| F | Fatal |

### Qt应用日志查看示例

**查看应用普通日志**：
```
bundle_name: 'com.example.qtapp'
level: 'I'
```

**查看错误日志**：
```
bundle_name: 'com.example.qtapp'
level: 'E'
```

**查看崩溃日志**：
```
is_crash_log: true
bundle_name: 'com.example.qtapp'
```

**按标签过滤**：
```
tag: 'Qt'
level: 'D'
```

**按关键字过滤**：
```
keyword: 'libqohos'
level: 'E'
```

### Qt应用常见日志问题

| 日志信息 | 可能原因 |
|---------|---------|
| `dlopen failed: library "libqohos.so" not found` | 平台插件未正确部署 |
| `dlopen failed: library "libQt5Core.so" not found` | Qt核心库未部署 |
| `Cannot load Qt platform plugin` | 平台插件加载失败 |
| `module "QtQuick" is not installed` | QML模块未正确配置 |

### 运行时错误处理

> 应用启动后的崩溃、异常行为均按「构建失败排查」的 Step A → D 流程处理，但**发生环节**标记为「运行」。

| 步骤 | 执行动作 |
|------|---------|
| 1 | 获取崩溃日志：`is_crash_log: true` + `bundle_name` |
| 2 | 获取错误级别日志：`level: 'E'` + `bundle_name` |
| 3 | 查 `compile_fix_pro.md` 是否有已知方案（Step A） |
| 4 | 分类错误、修复、沉淀（Step B → D） |

---

## Step 5: UI树获取（可选）

**使用 `get_app_ui_tree` 工具**：

### 参数说明

| 参数 | 说明 | 是否必填 |
|------|------|---------|
| `mode` | dump模式：'simple'或'full' | 必填 |
| `outputDirectory` | JSON文件保存目录 | 必填 |
| `hvd` | 目标设备 | 可选 |

### dump模式

| 模式 | 说明 |
|------|------|
| `simple` | 获取窗口节点信息（WindowManagerService element dump） |
| `full` | 获取完整UI树 |

### 使用示例

```
mode: 'full'
outputDirectory: 'C:\\logs\\ui_tree'
```

---

## Step 6: UI操作（可选）

**使用 `perform_ui_action` 工具**：

### 操作类型

| actionType | 说明 |
|------------|------|
| `click` | 单击 |
| `directionalFling` | 方向滑动 |
| `inputText` | 输入文本 |
| `keyEvent` | 按键事件 |
| `screenshot` | 截图 |

### 参数说明

| 参数 | 适用操作 | 说明 |
|------|---------|------|
| `x`, `y` | click, inputText | 坐标点 |
| `direction` | directionalFling | 滑动方向：0=左,1=右,2=上,3=下 |
| `velocity` | directionalFling | 滑动速度（px/s） |
| `stepLength` | directionalFling | 滑动步长（px） |
| `text` | inputText | 输入文本内容 |
| `key1`, `key2`, `key3` | keyEvent | 按键ID（Back/Home/Power或KeyCode） |
| `savePath` | screenshot | 设备上的保存路径 |
| `localPath` | screenshot | 本地保存路径 |

### 使用示例

**点击操作**：
```
actionType: 'click'
x: 200
y: 300
```

**滑动操作**：
```
actionType: 'directionalFling'
direction: 3  // 向下滑动
velocity: 600
```

**输入文本**：
```
actionType: 'inputText'
x: 100
y: 200
text: 'Hello HarmonyOS'
```

**按键事件**：
```
actionType: 'keyEvent'
key1: 'Back'
```

**截图**：
```
actionType: 'screenshot'
localPath: 'C:\\screenshots\\test.png'
```

---

## 完整工作流程示例

### 场景：Qt鸿蒙应用编译测试

```
1. 项目构建
   build_project:
     clean: true
     build_mode: 'debug'

2. 启动应用
   start_app:
     hvd: 'emulator-5554'

3. 查看日志
   get_hilog_or_faultlog_recent:
     bundle_name: 'com.example.qtapp'
     level: 'I'

4. 如果有问题，查看错误日志
   get_hilog_or_faultlog_recent:
     bundle_name: 'com.example.qtapp'
     level: 'E'

5. 如果崩溃，查看崩溃日志
   get_hilog_or_faultlog_recent:
     is_crash_log: true
     bundle_name: 'com.example.qtapp'
```

### 场景：UI交互测试

```
1. 启动应用
   start_app

2. 获取UI树
   get_app_ui_tree:
     mode: 'full'
     outputDirectory: './ui_tree'

3. 执行点击操作
   perform_ui_action:
     actionType: 'click'
     x: 200
     y: 300

4. 查看日志确认操作结果
   get_hilog_or_faultlog_recent:
     level: 'D'
```

---

## 常见问题排查

### 构建问题

| 问题 | 排查步骤 |
|------|---------|
| CMake配置失败 | 检查 `entry/build-profile.json5` 的 `path` 是否正确 |
| Qt模块找不到 | 检查 `-DCMAKE_PREFIX_PATH` 是否配置正确的Qt SDK路径 |
| 编译错误 | 使用 `log_path` 保存详细日志分析 |

### 启动问题

| 问题 | 排查步骤 |
|------|---------|
| 应用无法启动 | 检查构建是否成功，查看错误日志 |
| 模拟器启动失败 | 确认DevEco Studio已正确安装模拟器 |
| 真机连接失败 | 检查USB连接和开发者模式 |

### 运行时问题

| 问题 | 排查步骤 |
|------|---------|
| Qt库加载失败 | 查看日志中的dlopen错误，检查库部署 |
| 平台插件加载失败 | 确认libqohos.so已正确部署 |
| QML加载失败 | 检查QML资源文件和模块配置 |
| 应用崩溃 | 使用 `is_crash_log: true` 获取崩溃日志 |

---

## 关键约束

**必须**：
- 先安装配置DevEco MCP工具链
- 确保DevEco Studio已正确安装
- Qt工程的CMake配置正确

**建议**：
- 首次构建使用 `clean: true`
- 使用 `bundle_name` 过滤日志更精准
- 遇到问题先查看错误级别日志

---

## 相关资源

- DevEco Toolbox GitHub: https://github.com/open-deveco/deveco-toolbox
- DevEco MCP Releases: https://github.com/open-deveco/deveco-mcp/releases
- 飞书指导文档: https://my.feishu.cn/wiki/Swg4wVCfQikeSHkiyRXcPBainOb
- 问题反馈: https://github.com/open-deveco/deveco-toolbox/issues
- 飞书答疑群: 搜索「鸿蒙 MCP 官方交流群」加入