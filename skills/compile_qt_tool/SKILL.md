---
name: compile-qt-tool
description: Use when compiling Qt-dependent open-source projects for OpenHarmony/OHOS, including Qt OHOS branch and artifact checks, glue template setup, dependency audits, build planning, compiler/linker/package error analysis, and fix recording.
metadata:
  short-description: Compile Qt projects for OHOS
---

# 依赖 Qt 框架的开源项目鸿蒙化编译工具

### 0、铁律

**禁止分析编译问题中以及分析依赖过程中无依据的任何推测行为**

| 违规行为 | 正确做法 |

|---------|---------|

| 没读代码就开始猜测 | 先读源码 |

| "可能是因为..." | 找到具体代码行 |

| "我觉得可能是..." | 明确说"证据不足，需要XXX信息" |


**警示信号**

当你发现自己有以下想法时，立即停止：

- 仅凭文档就下结论

- 假设其他平台的行为也适用于OHOS

- 没有阅读实际源代码

- "这应该和windows一样..." 
- "这个错误可能是....."
- "我觉得依赖可能是..."

**捕获到这些信号 → 停止。回去读代码。**

**遇到问题，优先查询 `compile_fix_pro.md`**

| 触发时机 | 执行动作 |
|---------|---------|
| 编译 / 链接 / 打包 / 运行出现任何错误 | **第一步**：在 `compile_fix_pro.md` 中搜索是否已有匹配的解决方案 |
| 找到匹配方案 | 直接按方案执行修复，不再重复分析 |
| 未找到匹配方案 | 按正常流程分析问题，修复后将新方案**追加写入** `compile_fix_pro.md` |

> ⚠️ 跳过知识库查询直接分析问题 = 违规。已解决过的问题不应浪费时间重新分析。

**平台分支必须显式隔离**

| 违规行为 | 正确做法 |
|---------|---------|
| 直接修改通用逻辑适配 OHOS | 用 `#if defined(Q_OS_OHOS)` / CMake `if(OHOS)` / qmake `ohos:` 条件隔离 |
| 改动导致 Linux/Windows/macOS 原逻辑不可用 | OHOS 改动必须封闭在条件分支内，不影响其他平台 |

**只改源头，不优先改生成物**

| 违规行为 | 正确做法 |
|---------|---------|
| 修改 build 目录下的 Makefile 或临时产物 | 优先改 CMakeLists.txt、.pro、源码、模板配置 |
| 把构建中间产物当交付件提交 | 所有改动必须追溯到源头文件 |

**修复成功必须沉淀**

| 触发时机 | 执行动作 |
|---------|---------|
| 任何编译 / 链接 / 打包 / 运行问题修复成功 | **必须**追加到 `compile_fix_pro.md`，包含：错误原文、发生阶段、根因、改动文件、验证命令 |

**门禁失败禁止标记成功**

| 检查项 | 未通过时 |
|-------|---------|
| 编译产物缺失 / HAP 未生成 | ❌ 不能写"完成" |
| 安装失败 / 启动失败 | ❌ 不能写"完成" |
| Qt .so 缺失 / RPATH 不完整 / 依赖断裂 | ❌ 不能写"完成" |

> 只有全部门禁通过，才能标记步骤完成。

**依赖先盘点，缺失不可猜**

| 违规行为 | 正确做法 |
|---------|---------|
| 假设某个 Qt 模块 / 三方库 / SDK 存在 | 在 `qt_env.md` 中明确记录每项依赖的状态（☑ 已就绪 / ☐ 缺失） |
| 跳过盘点直接编译 | 先完成 §3 依赖环境梳理，所有项状态明确后再进入编译 |

**平台能力限制要降级，不要硬绕**

| 违规行为 | 正确做法 |
|---------|---------|
| 对同一个平台限制反复重试同一命令 | 确认是平台限制后，记录限制原因，选择替代方案或功能降级 |
| 例：syscall / 权限 / 文件系统 / 动态库加载限制 | 记录到 `qt_env.md`，标注为「平台限制」并给出降级策略 |

### 1、需求沟通

- 和用户确认当前项目鸿蒙化编译需求

---

### 2、qt / ohos 前置背景确认

**鸿蒙化分支：**

目前 qt 对于 ohos 系统已经鸿蒙化的分支：

- `tqtc/harmonyos-5.12.12`
- `tqtc/harmonyos-5.15.16`

> 需要向用户提问目前分支的源码路径

**编译产物确认：**

- 前置条件：用户需提前将 qt 源码编译完毕
- 确认流程：
  1. 向用户提问是否已经编译完成
  2. 如果已完成，向用户询问以下分支的编译产物路径：
     - `tqtc/harmonyos-5.12.12`
     - `tqtc/harmonyos-5.15.16`

**胶水工程模版确认：**

> 详细的模版下载、解压、目录结构说明见 `create-qt-app` Step 1，此处仅做确认。

- 前置条件：运行 qt 的 ohos 程序需要依赖胶水工程模版
- 确认流程：
  1. 向用户询问是否已下载胶水工程、如果下载询问用户具体路径
  2. 如果没有下载，询问用户指定的下载目录
  3. 帮用户进行在用户指定的目录下载

> 下载Qt官方OHOS模板（胶水代码）
>
> 模板下载地址：http://codereview.qtcompany.cn:29416/template/
>
> 选择最新日期的模板：

```bash
# 获取最新模板文件名
curl -s "http://codereview.qtcompany.cn:29416/template/" \
  | grep -o 'ohostemplateforqtapplication_[0-9]*\.zip' \
  | sort -r | head -1

# 下载到工程目录
curl -O "http://codereview.qtcompany.cn:29416/template/ohostemplateforqtapplication_YYYYMMDD.zip"

# 使用Python解压（WSL可能没有unzip）
python3 -c "import zipfile; zipfile.ZipFile('ohostemplateforqtapplication_*.zip').extractall('.')"
```

解压后的目录结构（模板项目根目录）：

```
<工程目录>/
├── entry/
│   ├── src/main/
│   │   ├── cpp/                    # Qt应用代码位置
│   │   │   ├── main.cpp
│   │   │   └── CMakeLists.txt
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets
│   ├── build-profile.json5         # 模块级构建配置
│   └── libs/arm64-v8a/             # Qt运行时库位置
├── qEmbeddedUiExtensionHost/
├── build-profile.json5             # 项目级构建配置
├── local.properties
└── ...
```
**配置 CMake（关键！）**

> 此配置与 `create-qt-app` Step 3.1 内容相同，此处作为前置检查项确认配置正确性。

配置 `entry/build-profile.json5`

这是最关键的配置，在模块级构建配置中指定 CMake 和 Qt 路径：

```json5
{
  "apiType": "stageMode",
  "buildOption": {
    "externalNativeOptions": {
      "path": "./src/main/cpp/CMakeLists.txt",
      "arguments": "-DCMAKE_PREFIX_PATH=<Qt SDK路径>",  // ★ 需修改为实际路径
      "abiFilters": [
        "arm64-v8a"
      ]
    }
  },
  "buildOptionSet": [
    {
      "name": "release",
      "arkOptions": {
        "obfuscation": {
          "ruleOptions": {
            "enable": true,
            "files": [
              "./obfuscation-rules.txt"
            ]
          }
        }
      }
    },
  ],
  "targets": [
    {
      "name": "default"
    },
    {
      "name": "ohosTest",
    }
  ]
}
```

关键参数说明：

- `path` — 指向当前项目的 CMakeLists.txt、路径必须为绝对路径
- `arguments` — `-DCMAKE_PREFIX_PATH` 需要修改为实际的 Qt 产物 路径（如 `C:/Qt/Qt5.15.16-arm64-v8a`）
- `abiFilters` — 必须匹配目标设备 ABI（`arm64-v8a`），否则会导致库加载或打包失败

**在当前目录下输出文档：`qt_env.md`**

完成以上前置确认后，创建 `qt_env.md` 文档，用于追踪环境就绪状态：

- 将所有前置准备项整理为检查表，格式如下：

| 序号  | 检查项         | 需确认内容                         | 状态  |
| :-: | ----------- | ----------------------------- | :-: |
|  1  | 鸿蒙化分支源码路径确认 | 用户提供的分支源码路径                   |  ☐  |
|  2  | Qt 编译产物路径确认 | `5.12.12` / `5.15.16` 编译产物路径  |  ☐  |
|  3  | 胶水工程模版      | 模版下载路径及解压确认                   |  ☐  |
|  4  | CMake 配置    | `build-profile.json5` 中路径配置正确 |  ☐  |

- 每项确认完成后将状态标记为 ☑
- **所有检查项均为 ☑ 后，方可进入下一步骤**

---
### 3、依赖环境

**3.0 梳理当前项目的用途**

**3.1 Qt 版本依赖**

- 确认项目依赖的 Qt 大版本（Qt5 / Qt6）
  - 若为 Qt6，确认是否使用了 Qt6 独有特性
  - 若为 Qt5，确认最低兼容的小版本号

**3.2 Qt 模块依赖**

- 逐一梳理项目实际引用了哪些 Qt 模块
  - 核心模块：QtCore、QtGui、QtWidgets、QtNetwork 等
  - 扩展模块：QtMultimedia、QtWebEngine、QtBluetooth 等
  - 确认每个模块在鸿蒙化分支中是否已移植

**3.3 系统能力直调**

- 确认项目是否绕过 Qt 直接调用了操作系统 API
  - 若存在，评估在 OHOS 上的替代方案

**3.4 三方库依赖**

- 梳理除 Qt 仓库本身之外的所有三方库依赖
  - 记录库名、版本、引入方式（源码编译 / 预编译包 / 系统安装）
  - 确认各三方库是否支持 OHOS 交叉编译

**3.5 构建系统与编译配置**

- 梳理项目的构建系统类型（qmake / CMake / 混合）
- 梳理编译选项、宏定义、条件编译分支
- 确认是否存在平台相关的构建脚本或工具链文件
- 列出详细的依赖项

**3.6 环境就绪比对**

- 盘点当前已具备的编译环境（工具链、SDK、已编译产物等）
- 将已具备的环境与 3.1～3.5 梳理出的依赖项逐一比对
  - **已就绪**：标记为 ☑
  - **不确定**：向用户提问确认，明确列出需要确认的具体项
  - **缺失**：标记为 ☐，记录缺失原因

**追加至 `qt_env.md`**

将 3.1～3.6 的梳理结果按表格形式追加到 `qt_env.md` 中，作为依赖全景记录

**与用户确认编译就绪状态**

请用户查看 `qt_env.md`，根据比对结果按以下分支处理：

1. **环境已就绪** — 请用户确认文档信息无误后，进入下一步编译步骤
2. **存在不确定项** — 向用户列出具体的不确定项，逐项讨论确认
3. **环境存在缺失且无法自动获取** — 向用户提供：
   - 明确的求助信息（缺什么、为什么需要）
   - 具体的操作步骤
   - 预期结果（用户按步骤操作后，反馈结果与预期一致即视为通过）
4. **最终确认不具备编译条件** — 在 `qt_env.md` 追加结论段落，列出无法编译的具体原因，作为最终报告

----
### 4、计划协同
**4.1 知识库准备**

- 询问用户是否已有 `compile_fix_pro.md`（问题解决集合知识库）
  - **已有** — 记录其路径到 `qt_compile_plan.md` 中
  - **没有** — 询问用户创建路径，创建 `compile_fix_pro.md` 并写入示例格式：

    ```
    ## 问题标题
    - 问题描述：具体的错误信息
    - 发生环节：编译 / 链接 / 打包 / 运行
    - 产生原因：根因分析
    - 修复方案：具体的修复步骤与代码改动
    ```

**4.2 编译前准备**

- 查看 `qt_env.md`，对当前项目的编译依赖进行充分评估
- 调用create-qt-app这个skill
- 如果调用create-qt-app遇到错误：
  1. 识别错误产生在哪个环节（预处理 / 编译 / 链接 / 打包）
  2. 分析错误发生的原因
  3. 尝试修复
     - 修复成功 — 将问题及解决方案按照示例格式记入 `compile_fix_pro.md`
     - 修复失败 — 向用户求助，提供错误信息、已尝试的方案和需要的协助

- 在当前目录创建 `qt_compile_plan.md`，整理详细的编译步骤与计划

**4.3 参照 `qt_compile_plan.md` 执行调用build-run-qt-app编译**

- 按照计划逐步执行编译
- 如果编译遇到错误：
  1. 识别错误产生在哪个环节（预处理 / 编译 / 链接 / 打包）
  2. 分析错误发生的原因
  3. 尝试修复
     - 修复成功 — 将问题及解决方案按照示例格式记入 `compile_fix_pro.md`
     - 修复失败 — 向用户求助，提供错误信息、已尝试的方案和需要的协助

**4.4 编译完成确认**

- 确认编译按计划执行完毕且无报错
- 确认已生成预期的编译产物
- 更新 `qt_compile_plan.md` 标记编译状态为完成

---







---

