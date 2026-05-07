---
name: build-run-qt-app
description: 使用DevEco MCP工具链编译、运行Qt鸿蒙应用并查看日志。支持项目构建、应用启动、日志获取、UI操作等功能。适用于Qt鸿蒙工程的编译测试流程。
---

# Qt鸿蒙工程编译运行与日志查看

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

### 安装方式一：npx安装（推荐）

在AI IDE的MCP配置文件中添加以下配置：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "deveco-mcp-server"
      ],
      "env": {
        "PROJECT_PATH": "${workspaceFolder}",
        "DEVECO_PATH": "C:\\Program Files\\Huawei\\DevEco Studio"
      }
    }
  }
}
```

**参数说明**：
- `PROJECT_PATH`: 工程路径，使用 `${workspaceFolder}` 变量或指定具体路径
- `DEVECO_PATH`: DevEco Studio安装路径

**FAQ**：如果npx配置失败提示 "Platform package deveco-mcp-server-xxx not found"，请使用以下配置：

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": [
        "--registry=https://registry.npmjs.org",
        "-y",
        "deveco-mcp-server"
      ],
      "env": {
        "PROJECT_PATH": "${workspaceFolder}",
        "DEVECO_PATH": "C:\\Program Files\\Huawei\\DevEco Studio"
      }
    }
  }
}
```

### 安装方式二：二进制安装

#### 下载地址

- GitHub Releases: https://github.com/open-deveco/deveco-mcp/releases

#### Windows安装步骤

1. 下载zip包并解压
2. 尽量避免在安装路径中包含特殊字符或中文

#### MCP配置

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

**注意**：如果IDE不支持 `${workspaceFolder}` 变量替换，需要手动替换为指定路径。

### 安装方式三：DevEco Toolbox可视化配置

1. 下载并安装DevEco Toolbox（https://github.com/open-deveco/deveco-toolbox/releases）
2. Windows: 下载zip包并解压，点击 `deveco-toolbox.exe` 启动
3. 启动后会自动探测DevEco Studio路径
4. 界面上有添加到Trae和Cursor的按钮，点击即可配置MCP

### 验证MCP安装成功

安装完成后，在AI IDE中应能看到以下MCP工具：

| 工具名称 | 主要功能 |
|---------|---------|
| `harmonyos_knowledge_search` | 查询鸿蒙云端知识库 |
| `check_ets_files` | 对ets文件进行语法检查 |
| `check_cpp_files` | 对C/C++文件进行语法检查 |
| `build_project` | 进行项目构建 |
| `start_app` | 在模拟器或真机中启动应用 |
| `get_app_ui_tree` | 获取app当前页面的UI树 |
| `perform_ui_action` | 执行UI操作（点击、滑动、输入等） |
| `get_hilog_or_faultlog_recent` | 获取hilog/faultlog日志 |
| `project_sync` | 执行项目同步（ohpm install） |
| `create_harmony_project` | 创建鸿蒙模板工程 |

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

1. 查看构建日志输出
2. 检查CMake配置是否正确
3. 检查Qt SDK路径是否配置
4. 使用 `log_path` 参数保存详细日志

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
- 飞书指导文档: https://my.feishu.cn/wiki/open-deveco/deveco-toolbox
- 问题反馈: https://github.com/open-deveco/deveco-toolbox/issues