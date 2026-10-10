# find_package 回退系统 Qt6 导致 CMake 配置失败

> 编号：build-fix-04
> 日期：2026-10-10（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建）
> 涉及文件：`entry/src/main/cpp/CMakeLists.txt`
> 工程根：`QtBugDemo-official/`
> 当前状态：已修复（构建通过）

## 1. 报错

当 `CMakeLists.txt` 使用 `find_package(QT NAMES Qt5 Qt6 ...)` 时，构建在
CMake 配置阶段即中断：

```
-- Could NOT find WrapOpenGL (missing: WrapOpenGL_FOUND)
CMake Error at CMakeLists.txt:29 (find_package):
  Found package configuration file:
    /opt/homebrew/lib/cmake/Qt6/Qt6Config.cmake
  but it set Qt6_FOUND to FALSE — Failed to find required Qt component "Gui".

-- Configuring incomplete, errors occurred!
```

## 2. 根因

仓内 SDK 为精简分发版（实测）：

| 目录 | 存在? | 后果 |
|------|-------|------|
| `lib/cmake/Qt5*/` | ✗ | `find_package(Qt5)` 找不到配置文件 |
| `bin/moc` 等 | ✗ | AUTOMOC 无主机工具 |
| `include/` | ✓ | Qt 5.12.12 头文件 |

`find_package(QT NAMES Qt5 Qt6)` 流程：Qt5 候选落空（无 Config）→ 回退
Homebrew Qt6（`/opt/homebrew/lib/cmake/Qt6/`）→ Qt6Gui 要求 WrapOpenGL →
macOS 无 OpenGL 开发库 → 失败。

## 3. 修复（已应用）

绕开 `find_package`，改用直接头文件目录 + .so 绝对路径链接，关闭 AUTO\*：

```cmake
set(CMAKE_AUTOUIC OFF)
set(CMAKE_AUTOMOC OFF)
set(CMAKE_AUTORCC OFF)

set(QT_OHOS_DEV_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../../third_party/qt-ohos-dev)
set(QT_INCLUDE_DIR ${QT_OHOS_DEV_DIR}/include)
set(QT_LIB_DIR ${QT_OHOS_DEV_DIR}/lib)

target_include_directories(qtbugdemo PRIVATE
    ${QT_INCLUDE_DIR}/QtCore
    ${QT_INCLUDE_DIR}/QtGui
    ${QT_INCLUDE_DIR}/QtWidgets
    ${QT_INCLUDE_DIR}/QtNetwork
    ${QT_INCLUDE_DIR}
)

target_link_libraries(qtbugdemo PRIVATE
    ${QT_LIB_DIR}/libQt5Core.so
    ${QT_LIB_DIR}/libQt5Gui.so
    ${QT_LIB_DIR}/libQt5Widgets.so
    ${QT_LIB_DIR}/libQt5Network.so
)
```

> **注意**：若 DevEco Studio 回退了此修复（build-fix-11），需重新应用。

## Auto-fix

```yaml
match: "Failed to find required Qt component|WrapOpenGL not found|Qt6_FOUND.*FALSE"
files:
  - entry/src/main/cpp/CMakeLists.txt
actions:
  - type: rewrite_cmake
    target: qtbugdemo
    qt_dev_dir: third_party/qt-ohos-dev
```
