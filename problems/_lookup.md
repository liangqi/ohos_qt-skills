---
updated: 2026-08-01
total_problems: 29
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
| 00308018 | [build-fail-hvigor-spawn-java-enoent](build-fail-hvigor-spawn-java-enoent.md) | Qt5 鸿蒙 demo 用 bash 跑 `node hvigorw.js assembleHap`,CMake/ninja 编 C++ 通过、ArkTS 编译通过, 但最后 PackageHap 步骤报 `spawn java ENOENT` 失败。`which java` 在 bash 里即使把 DevEco jbr/bin 加进 PATH 也找不到(或找到但 node spawn 仍 ENOENT)。 |
| N/A | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| N/A | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic 字符 ֪ʶ⽻） |
| errno=22 (EINVAL) | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | 运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下 |

## 按症状速查

| 症状关键字 | 问题文件 | 简述 |
|-----------|---------|------|
| `C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native` | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| `编译报错：QtOhosExtras::AbilityClose 等枚举值找不到` | [build-fail-closeeventrootcause-path](build-fail-closeeventrootcause-path.md) | 编译报错：QtOhosExtras::AbilityClose 等枚举值找不到 |
| `CMake configure 阶段报错 find_package 找不到 OhosExtras` | [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) | CMake configure 阶段报错 find_package 找不到 OhosExtras 包 |
| `hvigor 构建在 ProcessLibs 阶段失败，报 Duplicated files f` | [build-fail-duplicate-so](build-fail-duplicate-so.md) | hvigor 构建在 ProcessLibs 阶段失败，报 Duplicated files found |
| `Linux 应用移植 OHOS，编译报 unknown type name '__pid_t'/` | [build-fail-glibc-internal-symbols-ohos-musl](build-fail-glibc-internal-symbols-ohos-musl.md) | Linux 应用移植 OHOS，编译报 unknown type name '__pid_t'/'__uid_t' 或 in6_addr no member 's6_addr32' |
| `Qt5 鸿蒙 demo 用 bash 跑 `node hvigorw.js assembleHa` | [build-fail-hvigor-spawn-java-enoent](build-fail-hvigor-spawn-java-enoent.md) | Qt5 鸿蒙 demo 用 bash 跑 `node hvigorw.js assembleHap`,CMake/ninja 编 C++ 通过、ArkTS 编译通过, 但最后 PackageHap 步骤报 `spawn java ENOENT` 失败。`which java` 在 bash 里即使把 DevEco jbr/bin 加进 PATH 也找不到(或找到但 node spawn 仍 ENOENT)。 |
| `Linux Qt 应用移植 OHOS，编译报找不到 uuid/uuid.h 或链接找不到 -lu` | [build-fail-libuuid-missing-ohos-musl](build-fail-libuuid-missing-ohos-musl.md) | Linux Qt 应用移植 OHOS，编译报找不到 uuid/uuid.h 或链接找不到 -luuid |
| `Qt OHOS app 入口 shim 用 extern "C" main + 有 .qrc 资` | [build-fail-qinitresource-extern-c-main](build-fail-qinitresource-extern-c-main.md) | Qt OHOS app 入口 shim 用 extern "C" main + 有 .qrc 资源，链接报 undefined symbol: qInitResources_<name> |
| `no member named 'nullptr_t' in the global namesp` | [build-fail-qt6-libcpp-musl-isystem](build-fail-qt6-libcpp-musl-isystem.md) | no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; -isystem sysroot/usr/include 注入致 musl 遮蔽 clang builtin) |
| `fatal error: 'QtOhosExtras/QOhosAppContext' file` | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| `spawn java ENOENT; BuildNativeWithCmake finished` | [build-hvigor-native-skip](build-hvigor-native-skip.md) | spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing) |
| `CMake Error: find_package(Qt5 COMPONENTS Widgets` | [build-missing-qt5uitools-ohos](build-missing-qt5uitools-ohos.md) | CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) 失败 (OHOS Qt5 SDK 缺 Qt5UiTools 模块) |
| `Q_ASSERT(receiver->d_func()->threadData.loadAcqu` | [ohos-mainthread-mismatch](ohos-mainthread-mismatch.md) | Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (Debug 构建鼠标点击事件触发) |
| `QFileDialog 在 OHOS 上无需 #ifdef 守卫；QOhosPlatformIn` | [ohos-qfiledialog-native-support](ohos-qfiledialog-native-support.md) | QFileDialog 在 OHOS 上无需 #ifdef 守卫；QOhosPlatformIntegrationPlugin 已内置原生支持， 直接使用 QFileDialog::getSaveFileName / getOpenFileName 即可。 |
| `Qt3D 实体贴图纯黑（cloud 球壳 / saturn 星环 / uranus 星环），光照` | [render-black-rgba8-zink-mipmap](render-black-rgba8-zink-mipmap.md) | Qt3D 实体贴图纯黑（cloud 球壳 / saturn 星环 / uranus 星环），光照与阴影正常； 同 effect 下用 RGB8 JPG 的实体贴图正常；唯一判别变量是贴图格式 RGBA8(alpha) vs RGB8(JPG)。 |
| `签名 HAP 安装成功,aa start 后进程 1-9s 内消失。faultlog 显示 js` | [runtime-crash-libqohos-libqt5core-version-mismatch](runtime-crash-libqohos-libqt5core-version-mismatch.md) | 签名 HAP 安装成功,aa start 后进程 1-9s 内消失。faultlog 显示 jscrash TypeError (handleAbilityStageOnCreate of undefined 或 deviceType property 缺失)。 |
| `签名 HAP 安装成功,aa start 启动后进程 1-2 秒内消失(启动即崩),桌面不显示应` | [runtime-crash-libqohos-modules-mismatch](runtime-crash-libqohos-modules-mismatch.md) | 签名 HAP 安装成功,aa start 启动后进程 1-2 秒内消失(启动即崩),桌面不显示应用窗口或一闪即退。 |
| `应用启动后约1秒崩溃（C++ SIGSEGV），QtMainThread栈帧显示空指针解引用` | [runtime-crash-null-pointer-entry-shim](runtime-crash-null-pointer-entry-shim.md) | 应用启动后约1秒崩溃（C++ SIGSEGV），QtMainThread栈帧显示空指针解引用 |
| `签名 HAP 安装成功,aa start 后应用能启动(Qt 窗口出现、QtWatchdog 运` | [runtime-crash-ohos-deviceinfo-global-expression](runtime-crash-ohos-deviceinfo-global-expression.md) | 签名 HAP 安装成功,aa start 后应用能启动(Qt 窗口出现、QtWatchdog 运行),但触发 onAcceptWant (多实例/窗口 recreate/QApplication 二次构造)时进程崩溃;faultlog LAST_FATAL_MESSAGE 即上述 Napi::Error。 注意:本错误与"object has no property named 'deviceType'"是 @ohos.deviceInfo 崩溃谱的两个不同代际错误(见下)。 |
| `应用启动后延迟崩溃（SIGABRT），崩溃栈显示配置文件写入失败后调用 exit(1)` | [runtime-crash-sandbox-readonly-path](runtime-crash-sandbox-readonly-path.md) | 应用启动后延迟崩溃（SIGABRT），崩溃栈显示配置文件写入失败后调用 exit(1) |
| `curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic` | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic 字符 ֪ʶ⽻） |
| `运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storag` | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | 运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下 |
| `Opening Add Qt Versions shows an invalid-path po` | [runtime-fail-file-dialog-invalid-default-uri](runtime-fail-file-dialog-invalid-default-uri.md) | Opening Add Qt Versions shows an invalid-path popup, or the system picker does not list a qmake file without an extension. |
| `应用启动后立即崩溃（JSCrash TypeError），日志显示 libQt5DBus.so ` | [runtime-fail-libqtdbus-missing](runtime-fail-libqtdbus-missing.md) | 应用启动后立即崩溃（JSCrash TypeError），日志显示 libQt5DBus.so 加载失败 |
| `应用启动后立即崩溃，日志报 dlopen failed 或 platform plugin no` | [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) | 应用启动后立即崩溃，日志报 dlopen failed 或 platform plugin not found |
| `应用启动即弹 QMessageBox '无法创建本地数据库 !' 后崩溃退出（实为 native` | [runtime-fail-sqlite-open-database](runtime-fail-sqlite-open-database.md) | 应用启动即弹 QMessageBox '无法创建本地数据库 !' 后崩溃退出（实为 native cppcrash），Login 窗口未显示 |
| `应用启动后工具栏/菜单/托盘图标位置空白不显示；QIcon(:/...x.ico) 加载为空；改` | [runtime-icons-missing-libqico](runtime-icons-missing-libqico.md) | 应用启动后工具栏/菜单/托盘图标位置空白不显示；QIcon(:/...x.ico) 加载为空；改用 .png 图标则正常显示。 |
| `Qt QML 应用在 OHOS 暗主题设备运行，按钮和输入框默认背景纯黑，控件与背景融为一片看不` | [runtime-style-dark-palette-pure-black](runtime-style-dark-palette-pure-black.md) | Qt QML 应用在 OHOS 暗主题设备运行，按钮和输入框默认背景纯黑，控件与背景融为一片看不清边界(文字可见)。 |
| `设置 XComponent surface opaque 时 SurfaceHolder_Cre` | [surfaceholder-nativexcomponent-incompatibility](surfaceholder-nativexcomponent-incompatibility.md) | 设置 XComponent surface opaque 时 SurfaceHolder_Create 返回 null； 或 GetNativeXComponent 在节点挂载前返回 null 导致启动崩溃。 |

## 按领域

| 领域 | 严重度 | 问题文件 | 简述 |
|------|:------:|---------|------|
| build | medium | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| build | high | [build-fail-closeeventrootcause-path](build-fail-closeeventrootcause-path.md) | 编译报错：QtOhosExtras::AbilityClose 等枚举值找不到 |
| build | high | [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) | CMake configure 阶段报错 find_package 找不到 OhosExtras 包 |
| build | medium | [build-fail-duplicate-so](build-fail-duplicate-so.md) | hvigor 构建在 ProcessLibs 阶段失败，报 Duplicated files found |
| build | medium | [build-fail-glibc-internal-symbols-ohos-musl](build-fail-glibc-internal-symbols-ohos-musl.md) | Linux 应用移植 OHOS，编译报 unknown type name '__pid_t'/'__uid_t' 或 in6_addr no member 's6_addr32' |
| build | high | [build-fail-hvigor-spawn-java-enoent](build-fail-hvigor-spawn-java-enoent.md) | Qt5 鸿蒙 demo 用 bash 跑 `node hvigorw.js assembleHap`,CMake/ninja 编 C++ 通过、ArkTS 编译通过, 但最后 PackageHap 步骤报 `spawn java ENOENT` 失败。`which java` 在 bash 里即使把 DevEco jbr/bin 加进 PATH 也找不到(或找到但 node spawn 仍 ENOENT)。 |
| build | high | [build-fail-libuuid-missing-ohos-musl](build-fail-libuuid-missing-ohos-musl.md) | Linux Qt 应用移植 OHOS，编译报找不到 uuid/uuid.h 或链接找不到 -luuid |
| build | medium | [build-fail-qinitresource-extern-c-main](build-fail-qinitresource-extern-c-main.md) | Qt OHOS app 入口 shim 用 extern "C" main + 有 .qrc 资源，链接报 undefined symbol: qInitResources_<name> |
| build | blocker | [build-fail-qt6-libcpp-musl-isystem](build-fail-qt6-libcpp-musl-isystem.md) | no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; -isystem sysroot/usr/include 注入致 musl 遮蔽 clang builtin) |
| build | medium | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| build | high | [build-hvigor-native-skip](build-hvigor-native-skip.md) | spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing) |
| build | medium | [build-missing-qt5uitools-ohos](build-missing-qt5uitools-ohos.md) | CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) 失败 (OHOS Qt5 SDK 缺 Qt5UiTools 模块) |
| runtime | high | [ohos-mainthread-mismatch](ohos-mainthread-mismatch.md) | Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (Debug 构建鼠标点击事件触发) |
| migration | low | [ohos-qfiledialog-native-support](ohos-qfiledialog-native-support.md) | QFileDialog 在 OHOS 上无需 #ifdef 守卫；QOhosPlatformIntegrationPlugin 已内置原生支持， 直接使用 QFileDialog::getSaveFileName / getOpenFileName 即可。 |
| runtime | high | [render-black-rgba8-zink-mipmap](render-black-rgba8-zink-mipmap.md) | Qt3D 实体贴图纯黑（cloud 球壳 / saturn 星环 / uranus 星环），光照与阴影正常； 同 effect 下用 RGB8 JPG 的实体贴图正常；唯一判别变量是贴图格式 RGBA8(alpha) vs RGB8(JPG)。 |
| runtime | critical | [runtime-crash-libqohos-libqt5core-version-mismatch](runtime-crash-libqohos-libqt5core-version-mismatch.md) | 签名 HAP 安装成功,aa start 后进程 1-9s 内消失。faultlog 显示 jscrash TypeError (handleAbilityStageOnCreate of undefined 或 deviceType property 缺失)。 |
| runtime | critical | [runtime-crash-libqohos-modules-mismatch](runtime-crash-libqohos-modules-mismatch.md) | 签名 HAP 安装成功,aa start 启动后进程 1-2 秒内消失(启动即崩),桌面不显示应用窗口或一闪即退。 |
| runtime | critical | [runtime-crash-null-pointer-entry-shim](runtime-crash-null-pointer-entry-shim.md) | 应用启动后约1秒崩溃（C++ SIGSEGV），QtMainThread栈帧显示空指针解引用 |
| runtime | critical | [runtime-crash-ohos-deviceinfo-global-expression](runtime-crash-ohos-deviceinfo-global-expression.md) | 签名 HAP 安装成功,aa start 后应用能启动(Qt 窗口出现、QtWatchdog 运行),但触发 onAcceptWant (多实例/窗口 recreate/QApplication 二次构造)时进程崩溃;faultlog LAST_FATAL_MESSAGE 即上述 Napi::Error。 注意:本错误与"object has no property named 'deviceType'"是 @ohos.deviceInfo 崩溃谱的两个不同代际错误(见下)。 |
| runtime | critical | [runtime-crash-sandbox-readonly-path](runtime-crash-sandbox-readonly-path.md) | 应用启动后延迟崩溃（SIGABRT），崩溃栈显示配置文件写入失败后调用 exit(1) |
| runtime | medium | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | curl POST/PATCH 请求体中的中文字符在 API 端显示为乱码（如 Cyrillic 字符 ֪ʶ⽻） |
| runtime | high | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | 运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下 |
| runtime | high | [runtime-fail-file-dialog-invalid-default-uri](runtime-fail-file-dialog-invalid-default-uri.md) | Opening Add Qt Versions shows an invalid-path popup, or the system picker does not list a qmake file without an extension. |
| runtime | critical | [runtime-fail-libqtdbus-missing](runtime-fail-libqtdbus-missing.md) | 应用启动后立即崩溃（JSCrash TypeError），日志显示 libQt5DBus.so 加载失败 |
| runtime | critical | [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) | 应用启动后立即崩溃，日志报 dlopen failed 或 platform plugin not found |
| runtime | high | [runtime-fail-sqlite-open-database](runtime-fail-sqlite-open-database.md) | 应用启动即弹 QMessageBox '无法创建本地数据库 !' 后崩溃退出（实为 native cppcrash），Login 窗口未显示 |
| runtime | high | [runtime-icons-missing-libqico](runtime-icons-missing-libqico.md) | 应用启动后工具栏/菜单/托盘图标位置空白不显示；QIcon(:/...x.ico) 加载为空；改用 .png 图标则正常显示。 |
| runtime | medium | [runtime-style-dark-palette-pure-black](runtime-style-dark-palette-pure-black.md) | Qt QML 应用在 OHOS 暗主题设备运行，按钮和输入框默认背景纯黑，控件与背景融为一片看不清边界(文字可见)。 |
| errors | high | [surfaceholder-nativexcomponent-incompatibility](surfaceholder-nativexcomponent-incompatibility.md) | 设置 XComponent surface opaque 时 SurfaceHolder_Create 返回 null； 或 GetNativeXComponent 在节点挂载前返回 null 导致启动崩溃。 |
