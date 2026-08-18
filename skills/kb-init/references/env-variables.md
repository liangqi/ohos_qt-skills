# ENV.md 变量参考

本文件说明 `ENV.local.md` 中每个变量的含义和用途。

## IDE 与工具路径

| 变量名 | 含义 | 示例值 |
|--------|------|--------|
| `DEVECO_PATH` | DevEco Studio 安装路径 | macOS: `/Applications/DevEco-Studio.app`<br>Windows: `C:\Program Files\Huawei\DevEco Studio` |
| `OHOS_SDK_NATIVE` | OHOS SDK native 工具链路径（含 clang/sysroot） | macOS: `/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native` |

## Qt 源码路径

仅当你 clone 了 Qt 源码时需要配置。使用预编译 SDK 的用户不需要。

| 变量名 | 含义 | 示例值 |
|--------|------|--------|
| `QT5_12_SRC` | Qt 5.12.12 源码目录 | `/Users/you/dev/qt-src/qt5.12` |
| `QT5_15_SRC` | Qt 5.15.16 源码目录 | `/Users/you/dev/qt-src/qt5.15` |

## 编译产物与 SDK

| 变量名 | 含义 | 示例值 |
|--------|------|--------|
| `QT_BUILD_ROOT` | Qt 编译输出目录（仅编译 Qt 框架时需要） | `/Users/you/dev/qt-build` |
| `QT5_12_OHOS_SDK` | Qt 5.12 OHOS SDK 路径（CMake 的 CMAKE_PREFIX_PATH） | `/Users/you/dev/qt-sdk/Qt5.12.12-arm64-v8a` |
| `QT5_15_OHOS_SDK` | Qt 5.15 OHOS SDK 路径 | `/Users/you/dev/qt-sdk/Qt5.15.16-arm64-v8a` |

## 模板

| 变量名 | 含义 | 示例值 |
|--------|------|--------|
| `OHOS_TEMPLATE_SRC` | Qt 鸿蒙胶水模板路径（在 Qt 源码树内） | `/Users/you/dev/qt-src/qt5.12/qtbase/src/harmonyos/templates` |

> 仅当有 Qt 源码时自动计算，无需手动配置。

## 构建工具链（仅 Windows 编译 Qt 框架时需要）

| 变量名 | 含义 | 示例值 |
|--------|------|--------|
| `MINGW_ROOT` | MinGW 工具链路径 | `C:\mingw64` |
| `PERL_ROOT` | Strawberry Perl 路径 | `C:\Strawberry` |

> 应用开发者不需要这些变量。

## 知识库内嵌内容

| 变量名 | 含义 | 值 |
|--------|------|-----|
| `OHOS_COMMON_KB_PUBLIC` | 内嵌的 HarmonyOS 平台通用知识库 | `ohos-common-kb-public/`（相对路径，无需配置） |
