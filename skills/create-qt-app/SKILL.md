---
name: create-qt-app
description: 生成Qt鸿蒙应用工程结构（QWidget或QML），或将已有Qt工程鸿蒙化。支持从零创建新工程和已有工程鸿蒙化两种场景。只负责创建工程目录、源码文件、CMake配置模板，不负责编译和SDK配置。开发者需要在DevEco Studio中配置Qt SDK路径、鸿蒙SDK路径，Qt运行时库通过CMake链接插件target自动部署。
---

# Qt for HarmonyOS 工程生成器

支持两种使用场景：

## 场景一：从零创建新工程

生成Qt鸿蒙应用工程结构（QWidget或QML），包含：
- 工程目录结构（基于Qt官方OHOS模板）
- Qt源码文件和QML界面
- CMake配置模板（需开发者填写Qt SDK路径）
- 胶水代码配置

## 场景二：已有Qt工程鸿蒙化

将已有的Qt工程（CMake/qmake/其他）转换为鸿蒙应用，包含：
- 在工程根目录放置Qt胶水代码（OHOS模板）
- 配置build-profile.json5指向已有工程的构建文件
- 配置QtAppConstants.ets匹配应用库名

**不包含**：
- 编译和构建（需在DevEco Studio中完成）

**官方文档参考**：
- QWidget: https://wiki.qt.io/Qt_for_HarmonyOS/user_development/deveco_cmake_guide_cross_compile
- QML部署: https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_deply_qml_app_zh

---

## ⚠️ 重要：参数提取与验证

**在执行任何操作之前，必须使用 clarify 工具提取和验证参数！**

**禁止直接使用用户提示词作为文件名或路径！**

用户提示词中可能包含应用描述（如"俄罗斯方块demo"），这些描述性文字只能用于：
1. 在代码注释中说明应用用途
2. 在 CMakeLists.txt 的 project() 中作为项目名称（需转换为合法标识符，如 `TetrisDemo`）

**绝对禁止将用户提示词直接用于：**
- 文件名
- 目录名
- 路径拼接
- 任何 shell 命令参数

**正确做法：**
1. 从用户提示词中提取明确的路径参数（工程目录、SDK路径等）
2. 如果用户没有提供路径，使用 clarify 工具询问
3. 所有路径参数必须经过验证（检查是否存在必要文件）后才能使用
4. 应用名称应从工程目录名提取，或通过 clarify 确认

---

## 前置确认（必须！）

### 快速模式：从 compile-qt-tool 调用

> 当本 skill 由 `compile-qt-tool`（§4.2）调用时，当前目录下应已存在 `qt_env.md`。
>
> **检测到 `qt_env.md` → 进入快速模式**：
> 1. 从 `qt_env.md` 读取已确认的路径（胶水工程模版路径、Qt 编译产物路径等）
> 2. **跳过下方确认点 1、确认点 2**，直接进入「核心流程」
> 3. 仅需向用户确认 **确认点 0（使用场景）** 和 **确认点 0.1/0.2（应用/工程类型）**
>
> **未检测到 `qt_env.md` → 独立模式**：按下方完整流程逐项确认。

### 独立模式：完整确认流程

**在开始任何操作之前，必须通过对话确认以下要点：**

使用 `clarify` 工具，依次向用户确认：

### 参数提取示例

**用户提示词示例：**
```
帮我生成一个俄罗斯方块的demo工程，使用QML。工程目录放到：C:\Users\lzh\Documents\test-qtdemo-skills\t3；模板胶水代码路径：C:\Users\lzh\Downloads\ohostemplateforqtapplication_20260331.zip
```

**正确提取结果：**
- 应用类型：QML（从"使用QML"提取）
- 应用描述：俄罗斯方块demo（仅供代码注释和项目命名参考）
- 工程目录：`C:\Users\lzh\Documents\test-qtdemo-skills\t3`
- 模板路径：`C:\Users\lzh\Downloads\ohostemplateforqtapplication_20260331.zip`

**注意**：
- Qt SDK路径和鸿蒙SDK路径不需要用户提供，由开发者自己在DevEco Studio中配置
- "俄罗斯方块demo" 只是一个描述，不应直接用于文件名
- 项目名应从工程目录名提取（如 `t3`），或通过 clarify 确认一个合适的项目名（如 `TetrisDemo`）
- 使用 clarify 确认提取的参数是否正确

### 确认点0：使用场景（新增！）
```
问题：请选择使用场景
选项：
  1. 从零创建新工程 - 创建全新的Qt鸿蒙应用工程
  2. 已有Qt工程鸿蒙化 - 将已有的Qt工程转换为鸿蒙应用

说明：
- 从零创建：生成完整的工程结构，包含Qt源码模板
- 已有工程鸿蒙化：在已有工程根目录放置胶水代码，配置构建文件路径
```

### 确认点0.1：应用类型（场景一需要）
```
问题：请选择要创建的应用类型
选项：
  1. QWidget - 传统Qt Widgets应用（适合桌面风格UI）
  2. QML - Qt Quick/QML应用（适合现代触摸UI、动画效果）

说明：两种方式的CMake配置和运行时库部署有所不同
```

### 确认点0.2：已有工程类型（场景二需要）
```
问题：请选择已有工程的构建系统类型
选项：
  1. CMake工程 - 使用CMakeLists.txt构建
  2. qmake工程 - 使用.pro文件构建（TODO：待完善）
  3. 其他工程 - 其他构建系统（TODO：待完善）

说明：
- CMake工程：修改entry/build-profile.json5中的path指向根目录CMakeLists.txt
- qmake工程：需要额外转换步骤（待完善）
- 其他工程：需要额外转换步骤（待完善）
```

### 确认点1：工程目录
```
问题：请确认Qt鸿蒙工程的创建位置
示例：C:\Users\<username>\Documents\TetrisDemo\
```

### 确认点2：胶水代码模板
```
问题：是否需要从Qt官网下载最新的OHOS模板（胶水代码）？
下载地址：http://codereview.qtcompany.cn:29416/template/
如果用户已有模板zip文件，确认文件路径
```

**确认流程示例**：

**场景一（从零创建）**：
```
0. 先确认使用场景：从零创建新工程
0.1 再确认应用类型（QWidget 或 QML）
1. 确认工程目录（新创建的目录）
2. 最后确认胶水代码来源（下载或已有文件）
```

**场景二（已有工程鸿蒙化）**：
```
0. 先确认使用场景：已有Qt工程鸿蒙化
0.2 再确认已有工程类型（CMake/qmake/其他）
1. 确认工程目录（已有Qt工程的根目录）
2. 最后确认胶水代码来源（下载或已有文件）
```

**每确认一项后，验证路径是否存在必要文件，发现问题立即反馈。**

**注意**：Qt SDK路径和鸿蒙SDK路径由开发者自己在DevEco Studio中配置，本skill只负责生成工程结构。

---

## 核心流程（6步）

**场景一（从零创建）**：
```
确认参数 → 下载模板 → 放入Qt源码 → 配置CMake模板 → 复制样式库 → 配置胶水代码
```

**场景二（已有工程鸿蒙化）**：
```
确认参数 → 下载模板 → 解压到工程根目录 → 配置build-profile.json5路径 → 复制样式库 → 配置胶水代码
```

**后续步骤由开发者完成**：
- 在DevEco Studio中配置Qt SDK路径和鸿蒙SDK路径
- 构建和运行（Qt运行时库通过CMake链接插件自动部署）

---

## 场景二：已有Qt工程鸿蒙化

本节描述如何将已有的Qt工程转换为鸿蒙应用。

### Step H1: 获取Qt官方OHOS模板（胶水代码）

与场景一 Step 1 相同。快速模式下直接从 `qt_env.md` 读取已确认的模版路径。

### Step H2: 解压模板到已有工程根目录

**关键区别**：胶水代码放在已有工程根目录，而不是创建新目录。

解压后的目录结构：
```
<已有工程根目录>/           # 原有Qt工程目录
├── CMakeLists.txt          # 原有工程的CMake配置（或.pro文件）
├── src/                    # 原有工程的源码目录
├── ...                     # 其他原有文件
│
├── entry/                  # ★ 新增：OHOS胶水代码
│   ├── src/main/
│   │   ├── cpp/            # 空目录（不使用，原有源码在工程其他位置）
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets
│   ├── build-profile.json5 # ★ 模块级构建配置（需修改path）
│   └── libs/arm64-v8a/     # Qt运行时库位置
├── qEmbeddedUiExtensionHost/
├── build-profile.json5     # 项目级构建配置
├── local.properties
└── ...
```

### Step H3: 配置build-profile.json5（关键！）

根据已有工程的构建系统类型，修改 `entry/build-profile.json5`：

#### H3.1 CMake工程配置

修改 `entry/build-profile.json5` 中的 `path`，使用工程根目录CMakeLists.txt的**绝对路径**：

```json5
{
  "apiType": 'stageMode',
  "buildOption": {
    "externalNativeOptions": {
      "path": "C:\\code\\MyQtApp\\CMakeLists.txt",  // ★ 使用绝对路径，指向工程根目录的CMakeLists.txt
      "arguments": "-DCMAKE_PREFIX_PATH=<Qt SDK路径>",
      "abiFilters": [
        "arm64-v8a"
      ]
    }
  },
  // ... 其他配置保持不变
}
```

**关键修改**：
- `path`: 使用**绝对路径**（如 `C:\\code\\MyQtApp\\CMakeLists.txt`），而非相对路径
- 路径中的反斜杠需要转义（`\\`）
- 这样DevEco Studio会使用已有工程的CMakeLists.txt进行构建

#### H3.2 qmake工程配置（TODO：待完善）

qmake工程需要额外处理：

**方案A：转换为CMake工程**
- 使用 `qmake -query` 获取配置信息
- 手动创建CMakeLists.txt替代.pro文件
- 参考：https://wiki.qt.io/Qt_for_HarmonyOS/user_development/deveco_cmake_guide_cross_compile

**方案B：使用qmake构建（待验证）**
- TODO：需要验证DevEco Studio是否支持qmake构建
- 可能需要创建CMake wrapper脚本

```json5
{
  "apiType": 'stageMode',
  "buildOption": {
    "externalNativeOptions": {
      // TODO：qmake工程的具体配置待完善
      "path": "./CMakeLists.txt",  // 可能需要创建wrapper CMake
      "arguments": "-DCMAKE_PREFIX_PATH=<Qt SDK路径>",
      "abiFilters": [
        "arm64-v8a"
      ]
    }
  }
}
```

#### H3.3 其他工程类型配置（TODO：待完善）

对于使用其他构建系统的工程（如Meson、Bazel等）：

**方案**：创建CMake wrapper或手动配置

```json5
{
  "apiType": 'stageMode',
  "buildOption": {
    "externalNativeOptions": {
      // TODO：其他构建系统的具体配置待完善
      "path": "./CMakeLists.txt",  // wrapper CMake或空配置
      "arguments": "-DCMAKE_PREFIX_PATH=<Qt SDK路径>",
      "abiFilters": [
        "arm64-v8a"
      ]
    }
  }
}
```

### Step H4: 复制OHOS样式库

与场景一相同，手动复制 `libqohosstyle.so` 到 `entry/libs/arm64-v8a/styles/`。

### Step H5: 配置胶水代码

#### H5.1 配置Qt应用库名

编辑 `entry/src/main/ets/common/QtAppConstants.ets`：

```typescript
export const APP_LIBRARY_NAME = 'lib<你的应用名>.so';
```

**重要**：库名必须与已有工程CMakeLists.txt中的 `add_library()` 目标名匹配。

#### H5.2 项目级构建配置

`build-profile.json5`（项目根目录）配置与场景一相同。

#### H5.3 SDK路径配置

`local.properties` 配置与场景一相同。

### 已有工程鸿蒙化的注意事项

1. **不要修改原有工程的源码目录结构**
2. **确保原有CMakeLists.txt正确链接Qt模块**：
   - 需要链接 `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin`（平台插件）
   - 需要设置交叉编译时的 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH`
3. **库名匹配**：`QtAppConstants.ets` 中的 `APP_LIBRARY_NAME` 必须与原有工程的库名一致
4. **entry/src/main/cpp/ 目录为空**：原有源码在工程其他位置，不需要放入cpp目录

---

## 场景一：从零创建新工程

## Step 1: 获取Qt官方OHOS模板（胶水代码）

模板下载地址：`http://codereview.qtcompany.cn:29416/template/`

> **快速模式**：若 `qt_env.md` 中已记录胶水工程模版路径且状态为 ☑，直接使用该路径，跳过下载步骤。

**独立模式 — 选择最新日期的模板**：
```bash
# 获取最新模板文件名
curl -s "http://codereview.qtcompany.cn:29416/template/" \
  | grep -o 'ohostemplateforqtapplication_[0-9]*\.zip' \
  | sort -r | head -1

# 下载到工程目录
curl -O "http://codereview.qtcompany.cn:29416/template/ohostemplateforqtapplication_YYYYMMDD.zip"

# 解压
python3 -c "import zipfile; zipfile.ZipFile('ohostemplateforqtapplication_*.zip').extractall('.')"
```

解压后的目录结构（模板项目根目录）与 `compile-qt-tool` §2 中描述一致：
```
<工程目录>/
├── entry/
│   ├── src/main/
│   │   ├── cpp/              # Qt应用代码位置
│   │   │   ├── main.cpp
│   │   │   └── CMakeLists.txt
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets
│   ├── build-profile.json5   # 模块级构建配置
│   └── libs/arm64-v8a/       # Qt运行时库位置
├── qEmbeddedUiExtensionHost/
├── build-profile.json5       # 项目级构建配置
├── local.properties
└── ...
```

---

## Step 2: 放入Qt源码

**Qt源码放在模板工程的cpp目录**：`entry/src/main/cpp/`

### 方式A：QWidget 应用

路径：`entry/src/main/cpp/main.cpp`

```cpp
#include <QApplication>
#include <QLabel>
#include <QWidget>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    
    QWidget window;
    QLabel *label = new QLabel("Hello HarmonyOS Qt Widgets!", &window);
    label->setAlignment(Qt::AlignCenter);
    window.resize(400, 300);
    window.show();
    
    return app.exec();
}
```

### 方式B：QML 应用

**QML应用需要以下文件：**

1. C++入口文件：`entry/src/main/cpp/main.cpp`
2. QML界面文件：`entry/src/main/cpp/main.qml`（放在cpp目录便于qrc管理）
3. 资源映射文件：`entry/src/main/cpp/qml.qrc`

#### main.cpp

路径：`entry/src/main/cpp/main.cpp`

```cpp
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    
    QQmlApplicationEngine engine;
    // 从Qt资源系统加载QML（qrc路径与qml.qrc中的prefix对应）
    engine.load(QUrl(QStringLiteral("qrc:/main.qml")));
    
    if (engine.rootObjects().isEmpty())
        return -1;
    
    return app.exec();
}
```

#### main.qml

路径：`entry/src/main/cpp/main.qml`

**注意**：QML文件放在cpp目录下，通过qrc编译进应用库。

```qml
import QtQuick 2.12
import QtQuick.Window 2.12

Window {
    id: root
    visible: true
    width: 400
    height: 300
    title: "Hello HarmonyOS QML"
    color: "#1a1a2e"
    
    // 注意：Window没有focus属性，键盘事件需要放在内部Item中
    Item {
        anchors.fill: parent
        focus: true  // Item有focus属性
        Keys.onPressed: {
            console.log("Key pressed:", event.key)
        }
    }
    
    Text {
        anchors.centerIn: parent
        text: "Hello HarmonyOS QML!"
        font.pixelSize: 24
        color: "white"
    }
    
    // 简单按钮示例（使用Rectangle+MouseArea，不依赖Controls）
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 20
        width: 100
        height: 40
        color: "#e94560"
        radius: 5
        
        Text {
            anchors.centerIn: parent
            text: "Click Me"
            color: "white"
            font.pixelSize: 14
        }
        
        MouseArea {
            anchors.fill: parent
            onClicked: {
                console.log("Button clicked!")
            }
        }
    }
}
```

**注意**：
- Qt SDK for HarmonyOS是精简版，不包含QtQuick.Controls模块
- 使用Rectangle+MouseArea替代Button控件
- Window没有focus属性，键盘事件需要放在内部Item或FocusScope中

#### qml.qrc（资源映射文件）

路径：`entry/src/main/cpp/qml.qrc`

**重要**：prefix必须与main.cpp中的qrc路径一致！

```xml
<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource prefix="/">
        <!-- QML文件放在cpp目录，相对路径简单 -->
        <file>main.qml</file>
    </qresource>
</RCC>
```

**路径对应关系**：
- qml.qrc prefix `/` + file `main.qml` → 资源路径 `:/main.qml`
- main.cpp 加载 `qrc:/main.qml` → 正确匹配！

**创建QML应用文件的命令**（在工程目录执行）：
```bash
# 进入cpp目录
cd entry/src/main/cpp

# 创建 main.cpp（复制上述代码）
# 创建 main.qml（复制上述代码）
# 创建 qml.qrc（复制上述代码）
```

---

## Step 3: 配置CMake（关键！）

### 3.1 配置 entry/build-profile.json5

> 此配置与 `compile-qt-tool` §2「配置 CMake」中的内容相同，是两个 skill 共享的关键配置项。

**这是最关键的配置**，在模块级构建配置中指定CMake和Qt路径：

```json5
{
  "apiType": 'stageMode',
  "buildOption": {
    "externalNativeOptions": {
      "path": "./src/main/cpp/CMakeLists.txt",
      "arguments": "-DCMAKE_PREFIX_PATH=<Qt SDK路径>",  // ★ 开发者需要修改为实际Qt SDK路径
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

**关键参数说明**：
- `path`: 指向模块的CMakeLists.txt
- `arguments`: `-DCMAKE_PREFIX_PATH` 需要开发者修改为实际的Qt SDK路径（如 `C:/Qt/Qt5.15.16-arm64-v8a`）
- `abiFilters`: 必须匹配目标设备ABI（arm64-v8a），否则会导致库加载或打包失败

### 3.2 编写 CMakeLists.txt

路径：`entry/src/main/cpp/CMakeLists.txt`

#### 方式A：QWidget CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.5)
project(QtHarmonyApp)

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# OHOS toolchains commonly set CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY for
# cross-compiling, which prevents CMake from finding Qt via CMAKE_PREFIX_PATH
# when Qt is installed outside the sysroot.
# 关键：交叉编译时需要临时放宽查找策略
if(CMAKE_CROSSCOMPILING)
  set(_saved_root_path_mode_package "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()

find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Widgets)

# 如果应用使用了其他模块，在此添加：
# find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Network)  # 网络功能
# find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS OpenGL)   # OpenGL/QGLWidget
# find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS OhosExtras)  # 鸿蒙特有功能

if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "${_saved_root_path_mode_package}")
  unset(_saved_root_path_mode_package)
endif()

set(NATIVERENDER_ROOT_PATH ${CMAKE_CURRENT_SOURCE_DIR})
include_directories(
  ${NATIVERENDER_ROOT_PATH}
  ${NATIVERENDER_ROOT_PATH}/include
)

set(PROJECT_SOURCES
  main.cpp
)

# 生成动态库（库名必须与QtAppConstants.ets中的APP_LIBRARY_NAME匹配）
add_library(QtHarmonyApp SHARED ${PROJECT_SOURCES})

target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::Core
  Qt${QT_VERSION_MAJOR}::Widgets
)

# 链接Qt for HarmonyOS平台插件（自动部署libqohos.so到 libs/${ABI_DIR}/）
target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin
)
```

#### 方式B：QML CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.5)
project(QtHarmonyApp)

# 关键：启用Qt自动工具
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# 关键：交叉编译时需要临时放宽查找策略
if(CMAKE_CROSSCOMPILING)
  set(_saved_root_path_mode_package "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()

find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core)
# QML应用需要的模块
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Gui Qml Quick)

if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "${_saved_root_path_mode_package}")
  unset(_saved_root_path_mode_package)
endif()

set(NATIVERENDER_ROOT_PATH ${CMAKE_CURRENT_SOURCE_DIR})
include_directories(
  ${NATIVERENDER_ROOT_PATH}
  ${NATIVERENDER_ROOT_PATH}/include
)

# QML应用源文件（包含qrc资源文件）
set(PROJECT_SOURCES
  main.cpp
  main.qml      # QML界面文件
  qml.qrc       # 资源映射文件，将main.qml编译进应用库
)

# 生成动态库（库名必须与QtAppConstants.ets中的APP_LIBRARY_NAME匹配）
add_library(QtHarmonyApp SHARED ${PROJECT_SOURCES})

# QML应用链接库
target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::Core
  Qt${QT_VERSION_MAJOR}::Gui
  Qt${QT_VERSION_MAJOR}::Qml
  Qt${QT_VERSION_MAJOR}::Quick
)

# 链接Qt for HarmonyOS平台插件（自动部署libqohos.so到 libs/${ABI_DIR}/）
target_link_libraries(QtHarmonyApp PRIVATE
  Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin
)
```

**QML CMakeLists.txt 关键点**：
1. **CMAKE_AUTORCC ON**：启用Qt资源编译器，将qml.qrc编译成C++代码嵌入应用库
2. **PROJECT_SOURCES 包含 main.qml 和 qml.qrc**：确保QML文件被正确编译
3. **链接 Qml 和 Quick 模块**：QML应用必需的Qt模块

**关键点**：
1. **交叉编译find_package问题**：OHOS工具链默认设置 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY`，这会阻止CMake通过CMAKE_PREFIX_PATH找到Qt。必须在find_package前临时设置为BOTH，找到Qt后恢复原值。
2. **库名匹配**：`add_library(QtHarmonyApp SHARED ...)` 生成的库名必须与 `QtAppConstants.ets` 中的 `APP_LIBRARY_NAME` 一致。
3. **OHOS平台插件部署**：
   - **libqohos.so**：通过链接 `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin` 自动部署到 `libs/${ABI_DIR}/libqohos.so`（不使用platforms子目录）
4. **OHOS样式插件部署**：
   - **libqohosstyle.so**：手动复制到 `libs/${ABI_DIR}/styles/libqohosstyle.so`（Step 4执行）
   - 原因：target_link_libraries无法保证子目录结构

---

## Step 4: 复制OHOS样式库

**libqohosstyle.so需要手动复制**，因为target_link_libraries无法保证子目录结构。

### 复制步骤

```bash
# 目标目录
TARGET_DIR=<工程目录>/entry/libs/arm64-v8a/styles/

# 创建目录
mkdir -p "$TARGET_DIR"

# 从Qt SDK复制（Qt SDK路径由开发者配置）
# 假设Qt SDK路径为 C:/Qt/Qt5.15.16-arm64-v8a
cp <Qt_SDK路径>/lib/styles/libqohosstyle.so "$TARGET_DIR"
```

**说明**：
- Qt SDK路径需要在DevEco Studio中配置后确定
- styles目录必须手动创建
- libqohosstyle.so必须放在styles/子目录下

---

## Step 5: 配置胶水代码

### 5.1 配置Qt应用库名

编辑 `entry/src/main/ets/common/QtAppConstants.ets`：

```typescript
export const APP_LIBRARY_NAME = 'libQtHarmonyApp.so';
```

**重要**：库名必须与CMakeLists.txt中的 `add_library()` 目标名匹配：
- CMake: `add_library(QtHarmonyApp SHARED ...)` → 生成 `libQtHarmonyApp.so`
- ArkTS: `APP_LIBRARY_NAME = 'libQtHarmonyApp.so'`

### 5.2 项目级构建配置

`build-profile.json5`（项目根目录）：

```json5
{
  "app": {
    "signingConfigs": [],
    "products": [
      {
        "name": "default",
        "signingConfig": "default",
        "compatibleSdkVersion": "5.0.0(12)",
        "runtimeOS": "HarmonyOS",
      }
    ],
    "buildModeSet": [
      {"name": "debug"},
      {"name": "release"}
    ],
  },
  "modules": [
    {
      "name": "entry",
      "srcPath": "./entry",
      "targets": [{"name": "default", "applyToProducts": ["default"]}]
    },
    {
      "name": "qEmbeddedUiExtensionHost",
      "srcPath": "./qEmbeddedUiExtensionHost",
      "targets": [{"name": "default", "applyToProducts": ["default"]}]
    },
  ]
}
```

**关键**：
- 不要设置 `compileSdkVersion` 和 `targetSdkVersion`
- `runtimeOS` 必须是 `"HarmonyOS"`

### 5.3 SDK路径配置

`local.properties`：

```properties
sdk.dir=<DevEco SDK路径>  # ★ 开发者需要修改为实际路径，如 C:\\Program Files\\Huawei\\DevEco Studio\\sdk\\default
```

**注意**：SDK路径需要在DevEco Studio中配置或手动填写。

---

## 后续步骤（开发者需要完成）

本skill生成的工程只包含源码和配置模板，以下步骤需要开发者自己完成：

### 1. 在DevEco Studio中配置SDK路径

1. 打开DevEco Studio → File → Open → 选择生成的工程目录
2. 配置Qt SDK路径：修改 `entry/build-profile.json5` 中的 `-DCMAKE_PREFIX_PATH` 为实际路径（如 `C:/Qt/Qt5.15.16-arm64-v8a`）
3. 配置鸿蒙SDK路径：DevEco Studio会自动检测，或手动配置 `local.properties`

### 2. Qt运行时库部署

Qt运行时库部署分为两部分：

**自动部署**：
- 平台插件：链接 `Qt5::QOhosPlatformIntegrationPlugin` → libqohos.so自动部署到 `libs/${ABI_DIR}/`
- Qt核心库：通过 `find_package` + `target_link_libraries` 链接 → 构建时自动处理依赖

**手动复制（Step 4）**：
- 样式插件：libqohosstyle.so → 复制到 `libs/${ABI_DIR}/styles/`

**可能需要手动部署的库**：
- Qt核心库文件（libQt5Core.so等）可能需要手动复制到 `libs/arm64-v8a/`
- QML模块插件（libqtquick2plugin.so等）需要手动复制

**建议**：先尝试构建，如果运行时缺少库，再手动复制对应的.so文件。

### 3. 签名配置

在DevEco Studio中：File → Project Structure → Signing Configs → 自动签名

### 4. 构建运行

点击 Build → Make Project，然后 Run 到设备

**验证Qt库部署**：构建后检查 `entry/libs/${ABI_DIR}/` 是否包含：
- libQt5Core.so, libQt5Gui.so（自动部署）
- libqohos.so（OHOS平台插件，链接Qt5::QOhosPlatformIntegrationPlugin自动部署）
- styles/libqohosstyle.so（OHOS样式插件，Step 4手动复制）

---

## 常见问题

### 场景一（从零创建）常见问题

| 问题 | 解决方案 |
|------|----------|
| find_package(Qt5)失败 | 在CMakeLists.txt中交叉编译时设置 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` |
| SDK component missing | 在DevEco Studio中打开项目，让IDE自动配置SDK和工具链 |
| Schema validate failed | 不要设置 compileSdkVersion，只设置 compatibleSdkVersion |
| ArkTS编译错误 (Kit模块缺失) | runtimeOS 设置为 "HarmonyOS"，不要修改 OhosExportModules.ts |
| dlopen failed / cannot locate symbol | 检查 CMakeLists.txt 是否链接了 Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin |
| **平台插件加载失败** | 确保 libqohos.so 在 libs/${ABI_DIR}/ 目录下（通过链接Qt5::QOhosPlatformIntegrationPlugin自动部署） |
| **样式插件加载失败** | 确保 Step 4 正确复制 libqohosstyle.so 到 libs/${ABI_DIR}/styles/ |
| 库名不匹配 | 确保CMake的add_library名称与QtAppConstants.ets的APP_LIBRARY_NAME一致 |
| **QML: module "QtQuick" is not installed** | 检查Qt SDK路径是否正确配置在CMAKE_PREFIX_PATH |
| **QML应用黑屏** | 检查Qt模块是否正确链接，CMAKE_PREFIX_PATH配置是否正确 |
| **QML: Cannot assign to non-existent property "focus"** | Window元素没有focus属性，键盘事件处理需要放在内部Item或FocusScope中，使用Item { focus: true; Keys.onXPressed: ... } |
| **源工程资源文件丢失** | 创建占位资源文件（如简单PNG图片），并在resources.qrc中引用，确保CMake编译通过 |

### 场景二（已有工程鸿蒙化）常见问题

| 问题 | 解决方案 |
|------|----------|
| **构建找不到源文件** | 检查 `entry/build-profile.json5` 的 `path` 是否使用绝对路径指向根目录CMakeLists.txt |
| **原有工程CMakeLists.txt缺少OHOS配置** | 添加交叉编译时的 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` 设置，链接 `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin` |
| **库名不匹配** | 修改 `QtAppConstants.ets` 的 `APP_LIBRARY_NAME` 为原有工程的库名（如 `libMyApp.so`） |
| **qmake工程如何转换** | TODO：待完善，建议转换为CMake工程或创建CMake wrapper |
| **其他构建系统如何处理** | TODO：待完善，建议创建CMake wrapper脚本 |
| **原有工程目录结构混乱** | 确保胶水代码放在根目录，不要修改原有源码位置 |
| **构建时找不到Qt模块** | 确保原有CMakeLists.txt正确使用 `find_package(Qt...)` 并设置 `CMAKE_PREFIX_PATH` |

---

## 替换为你的Qt应用（最小操作步骤）

### 场景一：从零创建后替换源码

**本skill生成工程结构后，开发者需要完成以下步骤：**

#### 修改源码

1. 将你的Qt源码放入 `entry/src/main/cpp/`
2. 修改 `CMakeLists.txt` 更新源文件列表和Qt模块依赖
3. QML应用：更新 `qml.qrc` 添加你的QML文件
4. 确保库名与 `QtAppConstants.ets` 中的 `APP_LIBRARY_NAME` 一致

#### 配置SDK路径（在DevEco Studio中）

1. 修改 `entry/build-profile.json5` 中的 `-DCMAKE_PREFIX_PATH` 为Qt SDK路径
2. 配置鸿蒙SDK路径

#### Qt运行时库部署

Qt运行时库部署方式：
- libqohos.so：链接 `Qt5::QOhosPlatformIntegrationPlugin` 自动部署到 `libs/${ABI_DIR}/`
- libqohosstyle.so：Step 4手动复制到 `libs/${ABI_DIR}/styles/`
- 构建后检查目录确认库是否正确部署

### 场景二：已有工程鸿蒙化后配置

**已有工程添加胶水代码后，开发者需要完成以下步骤：**

#### 配置build-profile.json5

1. **CMake工程**：修改 `entry/build-profile.json5` 的 `path` 为工程根目录CMakeLists.txt的**绝对路径**（如 `C:\\code\\MyQtApp\\CMakeLists.txt`）
2. **qmake工程**：TODO（待完善）
3. **其他工程**：TODO（待完善）

#### 配置SDK路径（在DevEco Studio中）

1. 修改 `entry/build-profile.json5` 中的 `-DCMAKE_PREFIX_PATH` 为Qt SDK路径
2. 配置鸿蒙SDK路径

#### 配置库名匹配

1. 查看原有工程的CMakeLists.txt中的 `add_library()` 目标名
2. 修改 `entry/src/main/ets/common/QtAppConstants.ets` 的 `APP_LIBRARY_NAME` 为对应库名

#### Qt运行时库部署

Qt运行时库部署方式：
- libqohos.so：确保原有CMakeLists.txt链接 `Qt5::QOhosPlatformIntegrationPlugin`
- libqohosstyle.so：Step H4手动复制到 `libs/${ABI_DIR}/styles/`
- 构建后检查目录确认库是否正确部署

---

## 关键约束

**禁止**：
- 修改DevEco SDK或Qt SDK目录中的任何文件
- 修改 `OhosExportModules.ts`（开发者后续可能需要添加模块）
- 设置 `compileSdkVersion` 或 `targetSdkVersion`
- **将用户提示词直接用作文件名、目录名或路径的一部分**
- **将应用描述（如"俄罗斯方块demo"）直接用作项目名或库名**
- **在任何 shell 命令中直接拼接用户输入而未经验证**

**参数命名规范**：
- 项目名：从工程目录名提取，或使用英文标识符（如 `TetrisDemo`、`HelloWorld`）
- 库名：使用 `lib` 前缀 + 项目名 + `.so`（如 `libTetrisDemo.so`）
- 禁止在项目名中使用中文、空格、特殊字符

**场景一（从零创建）必须**：
- 开始前确认关键点（使用场景、应用类型、工程目录、胶水代码模板）
- Qt源码放在 `entry/src/main/cpp/` 目录
- CMakeLists.txt中交叉编译时设置 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH`
- CMakeLists.txt中链接 `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin`（平台插件，自动部署libqohos.so）
- Step 4手动复制 libqohosstyle.so 到 `libs/${ABI_DIR}/styles/`
- 库名与 `QtAppConstants.ets` 中的 `APP_LIBRARY_NAME` 匹配
- runtimeOS 设置为 "HarmonyOS"
- **QML应用**：应用QML文件放在 `cpp/` 目录并通过 qml.qrc 编译

**场景二（已有工程鸿蒙化）必须**：
- 开始前确认关键点（使用场景、已有工程类型、工程目录、胶水代码模板）
- 胶水代码解压到已有工程根目录（不创建新目录）
- **CMake工程**：修改 `entry/build-profile.json5` 的 `path` 为工程根目录CMakeLists.txt的**绝对路径**（如 `C:\\code\\MyQtApp\\CMakeLists.txt`）
- **qmake工程**：TODO（待完善）
- **其他工程**：TODO（待完善）
- 确保原有CMakeLists.txt链接 `Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin`
- 确保原有CMakeLists.txt设置交叉编译时的 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH`
- 库名与 `QtAppConstants.ets` 中的 `APP_LIBRARY_NAME` 匹配（使用原有工程的库名）
- Step H4手动复制 libqohosstyle.so 到 `libs/${ABI_DIR}/styles/`
- runtimeOS 设置为 "HarmonyOS"
- **不要修改原有工程的源码目录结构**

**开发者自己配置**（skill生成占位符）：
- Qt SDK路径：修改 `entry/build-profile.json5` 中的 `-DCMAKE_PREFIX_PATH`
- 鸿蒙SDK路径：DevEco Studio自动配置或手动配置 `local.properties`
- Qt核心库：可能需要手动复制到 `entry/libs/<abi>/`（视构建情况而定）
- QML插件：需要手动复制到 `entry/libs/<abi>/`

---

## 目录结构总结

### 场景一：从零创建 - QWidget应用

```
<工程目录>/                           # 模板项目根目录（ohostemplateforqtapplication）
├── entry/
│   ├── src/main/
│   │   ├── cpp/                      # ★ Qt应用代码位置
│   │   │   ├── main.cpp              # Qt Widgets源码
│   │   │   └── CMakeLists.txt        # CMake配置（关键）
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets # 配置库名 APP_LIBRARY_NAME
│   ├── build-profile.json5           # ★ 模块级构建配置（externalNativeOptions）
│   └── libs/arm64-v8a/               # Qt运行时库
│       ├── libqohos.so               # OHOS平台插件（链接Qt5::QOhosPlatformIntegrationPlugin自动部署）
│       ├── styles/
│       │   └── libqohosstyle.so      # OHOS样式插件（Step 4手动复制）
│       ├── libQt5Core.so             # Qt核心库（CMake自动部署）
│       ├── libQt5Gui.so              # Qt GUI库（CMake自动部署）
│       ├── libQt5Widgets.so          # Qt Widgets库（CMake自动部署）
│       └── libQtHarmonyApp.so        # 应用库（DevEco构建生成）
├── qEmbeddedUiExtensionHost/
├── build-profile.json5               # 项目级构建配置
└── local.properties                  # SDK路径配置
```

### 场景一：从零创建 - QML应用

```
<工程目录>/                           # 模板项目根目录
├── entry/
│   ├── src/main/
│   │   ├── cpp/                      # ★ Qt C++代码和QML资源位置
│   │   │   ├── main.cpp              # QML引擎初始化
│   │   │   ├── main.qml              # ★ 应用QML文件（通过qrc编译进库）
│   │   │   ├── qml.qrc               # ★ 资源映射文件
│   │   │   └── CMakeLists.txt        # CMake配置（包含Qml Quick模块）
│   │   ├── ets/
│   │   │   └── common/
│   │   │       └── QtAppConstants.ets
│   ├── build-profile.json5
│   └── libs/arm64-v8a/               # Qt运行时库
│       ├── libqohos.so               # OHOS平台插件（链接Qt5::QOhosPlatformIntegrationPlugin自动部署）
│       ├── styles/
│       │   └── libqohosstyle.so      # OHOS样式插件（Step 4手动复制）
│       ├── libQt5Core.so             # Qt核心库（CMake自动部署）
│       ├── libQt5Gui.so              # Qt GUI库（CMake自动部署）
│       ├── libQt5Qml.so              # QML引擎库（CMake自动部署）
│       ├── libQt5Quick.so            # Quick模块库（CMake自动部署）
│       └── libQtHarmonyApp.so        # 应用库（DevEco构建生成）
├── qEmbeddedUiExtensionHost/
├── build-profile.json5
└── local.properties
```

### 场景二：已有工程鸿蒙化 - CMake工程

```
<已有工程根目录>/                     # 原有Qt工程目录
├── CMakeLists.txt                    # ★ 原有工程的CMake配置（需添加OHOS配置）
├── src/                              # 原有工程的源码目录
│   ├── main.cpp                      # 原有源码
│   ├── widget.cpp
│   └── ...
├── ...                               # 其他原有文件
│
├── entry/                            # ★ 新增：OHOS胶水代码
│   ├── src/main/
│   │   ├── cpp/                      # 空目录（不使用）
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets # ★ 配置库名（需匹配原有工程库名）
│   ├── build-profile.json5           # ★ path使用绝对路径指向根目录CMakeLists.txt
│   └── libs/arm64-v8a/               # Qt运行时库
│       ├── libqohos.so               # OHOS平台插件
│       ├── styles/
│       │   └── libqohosstyle.so      # OHOS样式插件（Step H4手动复制）
│       └── libMyApp.so               # ★ 应用库（原有工程库名）
├── qEmbeddedUiExtensionHost/
├── build-profile.json5               # 项目级构建配置
└── local.properties                  # SDK路径配置
```

### 场景二：已有工程鸿蒙化 - qmake工程（TODO）

```
<已有工程根目录>/                     # 原有Qt工程目录
├── MyApp.pro                         # ★ 原有工程的qmake配置
├── src/                              # 原有工程的源码目录
│   ├── main.cpp
│   └── ...
├── ...                               # 其他原有文件
│
├── entry/                            # ★ 新增：OHOS胶水代码
│   ├── src/main/
│   │   ├── cpp/                      # 空目录或wrapper CMake
│   │   └── ets/
│   │       └── common/
│   │           └── QtAppConstants.ets
│   ├── build-profile.json5           # ★ TODO：qmake配置待完善
│   └── libs/arm64-v8a/
├── qEmbeddedUiExtensionHost/
├── build-profile.json5
└── local.properties
```

**qmake工程转换方案（待完善）**：
- 方案A：创建CMake wrapper替代.pro文件
- 方案B：使用qmake生成CMake配置
- 方案C：手动创建CMakeLists.txt

**QML应用关键说明**：
- **应用QML文件（main.qml）**：放在 `cpp/` 目录，通过 qml.qrc 编译进应用库
- **Qt运行时库**：通过CMake链接Qt模块和自定义命令部署，无需手动复制
- **OHOS平台插件**：链接 `Qt5::QOhosPlatformIntegrationPlugin` → libqohos.so自动部署到 `libs/${ABI_DIR}/libqohos.so`（不使用platforms子目录）
- **OHOS样式插件**：Step 4手动复制 → libqohosstyle.so到 `libs/${ABI_DIR}/styles/libqohosstyle.so`