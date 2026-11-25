# find_package falls back to the system Qt6 and CMake configuration fails

> ID: build-fix-04
> Date: 2026-10-10 (updated based on actual build)
> Files involved: `entry/src/main/cpp/CMakeLists.txt`
> Project root: `QtBugDemo-official/`
> Status: Fixed (build passes)

## 1. Error

When `CMakeLists.txt` uses `find_package(QT NAMES Qt5 Qt6 ...)`, the build stops
in the CMake configuration phase:

```
-- Could NOT find WrapOpenGL (missing: WrapOpenGL_FOUND)
CMake Error at CMakeLists.txt:29 (find_package):
  Found package configuration file:
    /opt/homebrew/lib/cmake/Qt6/Qt6Config.cmake
  but it set Qt6_FOUND to FALSE — Failed to find required Qt component "Gui".

-- Configuring incomplete, errors occurred!
```

## 2. Root cause

The in-repo SDK is a trimmed distribution (measured):

| Directory | Present? | Consequence |
|-----------|----------|-------------|
| `lib/cmake/Qt5*/` | ✗ | `find_package(Qt5)` cannot find a config file |
| `bin/moc`, etc. | ✗ | AUTOMOC has no host tools |
| `include/` | ✓ | Qt 5.12.12 headers |

The `find_package(QT NAMES Qt5 Qt6)` flow: the Qt5 candidate fails (no Config) → falls back to
the Homebrew Qt6 (`/opt/homebrew/lib/cmake/Qt6/`) → Qt6Gui requires WrapOpenGL →
macOS has no OpenGL development library → failure.

## 3. Fix (applied)

Bypass `find_package`; use direct header directories + absolute .so paths for linking, and turn off AUTO\*:

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

> **Note**: if DevEco Studio reverts this fix (build-fix-11), apply it again.

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
