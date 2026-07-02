---
updated: 2026-07-02
total_problems: 13
description: >
  错误速查索引（开发者版，从 problem 页 frontmatter 重建）。
---

# 错误速查表

> 遇到执行错误时，先在此搜索 error_message / error_code。
> Qt 平台已知限制在 semantic/qt-harmonyos-platform-limits.md。

## 按错误码速查

| 错误码 | 问题文件 | 简述 |
|--------|---------|------|
| N/A | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| 00306049 | [build-fail-duplicate-so](build-fail-duplicate-so.md) | hvigor 构建在 ProcessLibs 阶段失败，报 Duplicated files found |
| N/A | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| N/A | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic 字符 ֪ʶ⽻） |
| errno=22 (EINVAL) | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | 运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下 |

## 按症状速查

| 症状关键字 | 问题文件 | 简述 |
|-----------|---------|------|
| `C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native` | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| `编译报错：QtOhosExtras::AbilityClose 等枚` | [build-fail-closeeventrootcause-path](build-fail-closeeventrootcause-path.md) | 编译报错：QtOhosExtras::AbilityClose 等枚举值找不到 |
| `CMake configure 阶段报错 find_package 找不` | [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) | CMake configure 阶段报错 find_package 找不到 OhosExtras 包 |
| `hvigor 构建在 ProcessLibs 阶段失败，报 ` | [build-fail-duplicate-so](build-fail-duplicate-so.md) | hvigor 构建在 ProcessLibs 阶段失败，报 Duplicated files found |
| `no member named 'nullptr_t' in the global namesp` | [build-fail-qt6-libcpp-musl-isystem](build-fail-qt6-libcpp-musl-isystem.md) | no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; -isystem sysroot/usr/include 注入致 musl 遮蔽 clang builtin) |
| `fatal error: 'QtOhosExtras/QOhosAppContext' file` | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| `spawn java ENOENT; BuildNativeWithCmake finished` | [build-hvigor-native-skip](build-hvigor-native-skip.md) | spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing) |
| `CMake Error: find_package(Qt5 COMPONENTS Widgets` | [build-missing-qt5uitools-ohos](build-missing-qt5uitools-ohos.md) | CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) 失败 (OHOS Qt5 SDK 缺 Qt5UiTools 模块) |
| `Q_ASSERT(receiver->d_func()->threadData.loadAcqu` | [ohos-mainthread-mismatch](ohos-mainthread-mismatch.md) | Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (Debug 构建鼠标点击事件触发) |
| `curl POST/PATCH 请求体中的中文字符在 A` | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic 字符 ֪ʶ⽻） |
| `运行时加载 .so 插件失败，dlopen 返回` | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | 运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下 |
| `应用启动后立即崩溃，日志报 dlopen f` | [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) | 应用启动后立即崩溃，日志报 dlopen failed 或 platform plugin not found |
| `设置 XComponent surface opaque 时 SurfaceHold` | [surfaceholder-nativexcomponent-incompatibility](surfaceholder-nativexcomponent-incompatibility.md) | 设置 XComponent surface opaque 时 SurfaceHolder_Create 返回 null； 或 GetNativeXComponent 在节点挂载前返回 null 导致启动崩溃。 |

## 按领域

| 领域 | 严重度 | 问题文件 | 简述 |
|------|:------:|---------|------|
| build | medium | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| build | high | [build-fail-closeeventrootcause-path](build-fail-closeeventrootcause-path.md) | 编译报错：QtOhosExtras::AbilityClose 等枚举值找不到 |
| build | high | [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) | CMake configure 阶段报错 find_package 找不到 OhosExtras 包 |
| build | medium | [build-fail-duplicate-so](build-fail-duplicate-so.md) | hvigor 构建在 ProcessLibs 阶段失败，报 Duplicated files found |
| build | blocker | [build-fail-qt6-libcpp-musl-isystem](build-fail-qt6-libcpp-musl-isystem.md) | no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; -isystem sysroot/usr/include 注入致 musl 遮蔽 clang builtin) |
| build | medium | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| build | high | [build-hvigor-native-skip](build-hvigor-native-skip.md) | spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing) |
| build | medium | [build-missing-qt5uitools-ohos](build-missing-qt5uitools-ohos.md) | CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) 失败 (OHOS Qt5 SDK 缺 Qt5UiTools 模块) |
| runtime | high | [ohos-mainthread-mismatch](ohos-mainthread-mismatch.md) | Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (Debug 构建鼠标点击事件触发) |
| runtime | medium | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic 字符 ֪ʶ⽻） |
| runtime | high | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | 运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下 |
| runtime | critical | [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) | 应用启动后立即崩溃，日志报 dlopen failed 或 platform plugin not found |
| errors | high | [surfaceholder-nativexcomponent-incompatibility](surfaceholder-nativexcomponent-incompatibility.md) | 设置 XComponent surface opaque 时 SurfaceHolder_Create 返回 null； 或 GetNativeXComponent 在节点挂载前返回 null 导致启动崩溃。 |
