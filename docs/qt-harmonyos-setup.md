# Qt for HarmonyOS 环境配置指南

本文档介绍如何配置 Qt for HarmonyOS 开发环境。

## 前置条件

1. **DevEco Studio**：华为鸿蒙开发 IDE
   - 下载地址：https://developer.huawei.com/consumer/cn/deveco-studio/
   - 版本要求：4.0 或更高

2. **Qt for HarmonyOS SDK**：
   - Qt 官方提供的鸿蒙版 Qt SDK
   - 包含 Qt 核心库和鸿蒙平台插件

## 环境配置

### 1. 安装 DevEco Studio

1. 下载并安装 DevEco Studio
2. 启动 DevEco Studio，完成 SDK 初始化配置
3. SDK 默认路径：`C:\Program Files\Huawei\DevEco Studio\sdk\default`

### 2. 获取 Qt for HarmonyOS SDK

Qt for HarmonyOS SDK 可从 Qt 官方获取：
- 下载地址：http://codereview.qtcompany.cn:29416/template/

SDK 目录结构示例：
```
Qt5.15.16-arm64-v8a/
├── bin/                    # Qt 工具
│   ├── openharmonydeployqt.exe
│   └── qmlimportscanner.exe
├── lib/                    # Qt 库文件
│   ├── libQt5Core.so
│   ├── libQt5Gui.so
│   ├── libQt5Qml.so
│   ├── libQt5Quick.so
│   └── cmake/              # CMake 配置文件
│       ├── Qt5Core/
│       ├── Qt5Gui/
│       │   └── Qt5Gui_QOhosPlatformIntegrationPlugin.cmake
│       └── ...
├── plugins/                # Qt 插件
│   └── platforms/
│       └── libqohos.so     # 鸿蒙平台插件
├── qml/                    # QML 模块资源
│   ├── QtQuick.2/
│   ├── QtQml/
│   └── ...
└── include/                # 头文件
```

### 3. 配置 CMake 路径

在 DevEco Studio 项目中配置 Qt SDK 路径：

**修改 `entry/build-profile.json5`**：

```json5
{
  "buildOption": {
    "externalNativeOptions": {
      "path": "./src/main/cpp/CMakeLists.txt",
      "arguments": "-DCMAKE_PREFIX_PATH=C:/Qt/Qt5.15.16-arm64-v8a",
      "abiFilters": ["arm64-v8a"]
    }
  }
}
```

## Qt 模块说明

### 可用模块

Qt for HarmonyOS 是精简版，包含以下模块：

| 模块 | 描述 | CMake Target |
|------|------|--------------|
| QtCore | Qt 核心库 | Qt5::Core |
| QtGui | GUI 基础 | Qt5::Gui |
| QtWidgets | Widgets 控件 | Qt5::Widgets |
| QtQml | QML 引擎 | Qt5::Qml |
| QtQuick | Quick 模块 | Qt5::Quick |
| QtQmlModels | QML 模型 | Qt5::QmlModels |
| QtQmlWorkerScript | WorkerScript | Qt5::QmlWorkerScript |
| QtQuickShapes | Quick Shapes | Qt5::QuickShapes |
| QtNetwork | 网络模块 | Qt5::Network |

### 鸿蒙专属插件

| 插件 | 描述 | CMake Target |
|------|------|--------------|
| QOhosPlatformIntegrationPlugin | 鸿蒙平台插件 | Qt5::QOhosPlatformIntegrationPlugin |
| QOhosBearerEnginePlugin | 网络 bearer | Qt5::QOhosBearerEnginePlugin |
| QOhosPrinterSupportPlugin | 打印支持 | Qt5::QOhosPrinterSupportPlugin |
| QOhosStylePlugin | 样式插件 | Qt5::QOhosStylePlugin |

## 常见问题

### Q: find_package(Qt5) 失败？

A: 检查 CMakeLists.txt 中的交叉编译配置：

```cmake
if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()
find_package(Qt5 REQUIRED COMPONENTS Core Gui)
```

### Q: 运行时找不到 libqohos.so？

A: 链接平台插件：

```cmake
target_link_libraries(MyApp PRIVATE Qt5::QOhosPlatformIntegrationPlugin)
```

构建后，libqohos.so 会自动部署到 `libs/arm64-v8a/platforms/`。

### Q: QML 应用黑屏？

A: 检查以下配置：
1. Qt 模块是否正确链接（Qml、Quick、QmlModels、QmlWorkerScript）
2. qml.qrc 是否正确配置 QML 文件
3. QML 插件是否复制到 libs 目录

## 参考链接

- [Qt for HarmonyOS 用户开发指南](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide)
- [DevEco CMake 交叉编译指南](https://wiki.qt.io/Qt_for_HarmonyOS/user_development/deveco_cmake_guide_cross_compile)
- [QML 应用部署指南](https://wiki.qt.io/Qt_for_HarmonyOS/user_development_guide/how_to_deply_qml_app_zh)