# Qt 鸿蒙化接口差异对比文档

> **社区版**：`/Users/xiaoliyu/code/gitcode/qt-sig`（模块名 `QtOhExtras`，命名前缀 `QOh`/`QOpenHarmony`，平台插件 key `openharmony`）
> **官方版**：`/Users/xiaoliyu/code/AiProject/qt-5.12.12/qt-harmonyos-src`（模块名 `QtOhosExtras`，命名前缀 `QOhos`，平台插件 key `ohos`）
>
> 本文档对比两个版本在鸿蒙（OpenHarmony/HarmonyOS）化适配中的接口实现差异，涵盖接口实现的能力范围、API 设计范式、架构层级。

---

## 目录

1. [总体架构差异](#1-总体架构差异)
2. [命名规范差异](#2-命名规范差异)
3. [Extras 模块公共 API 对比](#3-extras-模块公共-api-对比)
4. [QPA 平台插件接口对比](#4-qpa-平台插件接口对比)
5. [Corelib 内核支持接口对比](#5-corelib-内核支持接口对比)
6. [功能模块插件接口对比](#6-功能模块插件接口对比)
7. [社区版独有接口能力](#7-社区版独有接口能力)
8. [官方版独有接口能力](#8-官方版独有接口能力)
9. [共有接口的 API 范式差异](#9-共有接口的-api-范式差异)
10. [总结](#10-总结)

---

## 1. 总体架构差异

| 维度 | 社区版 (qt-sig) | 官方版 (qt-5.12.12) |
|------|----------------|-------------------|
| **Qt 基础版本** | 基于 Qt 5 后期/Qt 6 风格（含 `darkThemeEnabled`/`setThemeColorMode` 等 Qt6 覆写） | Qt 5.12.12 |
| **设计范式** | 具体类 + 同步 API + NAPI 回调 + 直接调用原生 C API | 抽象类 + 工厂函数 + `QSharedPointer` + 异步信号 + JS/NAPI 桥接抽象层 |
| **命名前缀** | `QOh` / `QOpenHarmony` / `QtOh` | `QOhos` / `QtOhos` / `QtOhosExtras` |
| **Extras 模块名** | `QtOhExtras` (`qtohextras`) | `QtOhosExtras` (`qtohosextras`) |
| **导出宏** | `Q_OPENHARMONYEXTRAS_EXPORT` | `Q_OHOS_EXTRAS_EXPORT` |
| **平台插件 key** | `"openharmony"` | `"ohos"` |
| **NAPI 依赖** | 公共 API 直接依赖 `QtNapi/napi.h`（如 `QAbilityResultReceiver::handleResult(Napi::Value&)`） | 公共 API 完全隐藏 NAPI（纯 Qt 抽象） |
| **中央 QPA 接口** | 无集中接口；功能分散在 `QtOh` 命名空间 + `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` 抽象 | ✅ `QtOhos::QOhosQpaFunctions` — 60+ 纯虚函数统一接口 |
| **Want 参数类型** | `QVariantMap` | `QJsonObject` |
| **StartOptions** | 普通结构体，直接赋值公共字段 | 抽象类，虚函数 setter + 工厂创建 |
| **权限请求** | 同步返回 bool / 回调函数 | 异步 void + Qt 信号通知 |
| **Ability 结果返回** | 回调类 `QAbilityResultReceiver`（`Napi::Value` 参数） | Qt 信号（`startAbilityForResultResponseReceived`） |
| **错误处理** | 枚举错误码 + 输出参数 | `QOhosOperationStatus` 抽象对象 + `QSharedPointer` |
| **窗口辅助** | 实例类 `QOhWidgetHelper`（绑定到 QWidget/QWindow） | 命名空间自由函数 `QOhosWindowUtils` |
| **窗口属性系统** | 名称字符串标识（`windowName`/`parentWindowName`） | 类型安全属性描述符 `QOhosPropertyDescriptor<T>` |
| **文件共享 API** | 静态方法 + 错误码 + 输出参数 | 命名空间自由函数 + `QSharedPointer<ActionResult>` |
| **线程桥接** | `runOnJsUIThreadNoWait/AndWait` 简单封装 + `uv_queue_work` 模板 | 完整 `QOhosJsThreadGateway` + `QOhosJsState` + `QOhosTaskPromise` 链式追踪 |
| **智能指针** | `QScopedPointer` | `std::unique_ptr` / `std::shared_ptr` |
| **许可协议** | LGPL (iSoftStone, 2024-2025) | Qt Commercial / LGPL-3.0 / GPL |
| **公共头文件数** | 13（含 1 私有） | 22 公共 + 7 私有 |
| **第三方库** | 不含 | 内置 fontconfig / libjpeg / libpng / openssl |
| **部署工具** | 无 | `openharmonydeployqt` |
| **DevEco 模板** | 简单 EntryAbility | 完整模板含 QAbility/QAbilityStage/嵌入扩展/子进程/4种页面节点 |
| **功能模块** | 蓝牙(含GATT/LE/NFC) + 定位 + 传感器(9种) + 多媒体 + WebView + 打印 + 样式 | 蓝牙(基础) + 定位(含MapKit) + 传感器(5种) + 多媒体 + WebView + 打印 + 样式 + TTS + 串口 + 网络承载 |

---

## 2. 命名规范差异

### 2.1 前缀映射

| 社区版 | 官方版 | 说明 |
|--------|--------|------|
| `openharmony` (目录/插件名) | `ohos` (目录/插件名) | 平台适配目录命名 |
| `QtOhExtras` | `QtOhosExtras` | Extras 模块名 |
| `QOh*` / `QOpenHarmony*` | `QOhos*` | 类名前缀 |
| `QtOh::` | `QtOhosExtras::` / `QtOhos::` | 命名空间 |
| `Q_OPENHARMONYEXTRAS_EXPORT` | `Q_OHOS_EXTRAS_EXPORT` | 导出宏 |
| `qopenharmonyextrasglobal.h` | `qtohosextrasglobal.h` | 全局头文件 |

### 2.2 关键类名映射

| 社区版类名 | 官方版类名 | 说明 |
|-----------|-----------|------|
| `QOhAppContext` | `QOhosAppContext` | 应用上下文 |
| `QOHFileShare` | `QtOhosExtras::FileShare` | 文件共享 |
| `QOhWidgetHelper` | `QtOhosExtras::QOhosWindowUtils` | 窗口辅助 |
| `QOhProcess` | （无直接对应） | 进程管理 |
| `QOhChildProcess` | （无直接对应） | 子进程 |
| `QOpenHarmonyAbility` (namespace) | `QtOhosExtras::QOhosAbilityContext` | Ability 上下文 |
| `QOpenHarmonyWant` | `QOhosWant` | Want 数据 |
| `QOpenHarmonyStartOptions` | `QOhosStartOptions` | 启动选项 |
| `QOhAbstractLocalSocket` | （无对应） | 本地 IPC |
| `QOhLocalServer` / `QOhLocalSocket` | （无对应） | 本地 IPC |
| `QOhWindowFunctions` | `QOhosFunctions` | 平台头文件函数 |
| `QtOh::Utility` | `QOhosDeviceInfo` | 设备信息 |
| `QOhFontDatabase` | `QOhosPlatformFontDatabase` | 字体数据库 |
| `QHarmonyStyle` | `QOhosStyle` | 样式插件 |
| `QHarmonyWebView` | `QOhosWebView` | WebView |
| `QOhPlatformIntegration` | `QOhosPlatformIntegration` | 平台集成 |
| `QOhPlatformWindow` | `QOhosPlatformWindow` | 平台窗口 |
| `QOhPlatformNativeInterface` | `QOhosPlatformNativeInterface` | 原生接口 |
| `QOhPlatformTheme` | `QOhosPlatformTheme` | 平台主题 |
| `QOhPlatformClipboard` | `QOhosPlatformClipboard` | 剪贴板 |
| `QOhPlatformInputContext` | `QOhosInputContext` | 输入法 |
| `QOhPlatformAbilityCtrl` | （无对应，能力在 `QOhosQpaFunctions`） | Ability 控制 |
| `QPlatformAccessCtrl` | （无对应，能力在 `QOhosQpaFunctions`） | 访问控制 |

---

## 3. Extras 模块公共 API 对比

### 3.1 AppContext（应用上下文）

| 接口能力 | 社区版 `QOhAppContext` | 官方版 `QOhosAppContext` |
|---------|----------------------|------------------------|
| **类设计** | 具体类，私有构造，单例 | 抽象类，全部纯虚函数，单例 |
| 主题模式枚举 | `ColorMode{Dark,Light,Default,FollowSystemSetting}` + `SysThem{Dark,Light}` | `ColorThemeMode{LightTheme,DarkTheme,FollowSystemSetting}` |
| 主题获取 | `colorMode()` / `sysThem()` | `darkThemeActive()` |
| 主题设置 | `setColorMode(ColorMode)` (slot) | `setColorThemeMode(ColorThemeMode)` (virtual) |
| 主题信号 | `sysThemChanged(SysThem)` / `colorModeChanged(ColorMode)` | `darkThemeActiveChanged(bool)` |
| PC 模式信号 | ✅ `pcModeChanged(bool)` | ❌ |
| 字体大小缩放 | ❌ | ✅ `fontSizeScale()` + `fontSizeScaleChanged(double)` 信号 |
| 权限查询 | `isPermissionGranted(QString)` → bool（同步） | `isPermissionGranted(Permission)` + `(QString)` → bool（虚函数） |
| 权限请求 | `requestPermissionFromUser(QString)` → bool（同步） | `requestPermissionFromUserIfNeeded(Permission)` → void（异步+信号） |
| 设置页权限 | `requestPermissionsOnSetting(QString)` → bool | `requestPermissionOnSettingIfNeeded(Permission)` → void |
| 串口权限 | ❌ | ✅ `hasSerialPortAccessRight()` / `requestSerialPortAccessRightIfNeeded()` + 信号 |
| 上下文菜单长按 | ❌ | ✅ `enableContextMenuEventOnLongPress()` |
| 应用包信息 | ❌ | ✅ `getBundleInfo()` → `QOhosBundleInfo`（`versionCode()`） |
| 应用重启 | ❌ | ✅ `restartApp()` / `restartApp(QOhosWant)` — `Q_NORETURN` |
| 无 UI 子进程模式 | ❌ | ✅ `isNoUiChildMode()` / `startNoUiChildProcess(libraryName, args)` |
| 应用启动 Want | ❌ | ✅ `getAppLaunchWant()` / `getAppLaunchWantInfo()` |
| 权限信号 | ❌ | ✅ `permissionRequestResponseReceived` / `permissionRequestResponseWithResultReceived` / `permissionRequestOnSettingResponseReceived` / `serialPortAccessRightResponseReceived` |

### 3.2 AbilityContext（Ability 上下文）

| 接口能力 | 社区版 `QOpenHarmonyAbility` (namespace) | 官方版 `QOhosAbilityContext` |
|---------|---------------------------------------|---------------------------|
| **类设计** | namespace 自由函数 + `QAbilityResultReceiver` 回调类 | 抽象类 + 信号通知 |
| 启动 Ability | `start(want)` / `start(want, options, receiver)` / `start(want, receiver)` — void | `startAbility(want)` / `startAbility(want, options)` / `startAbility(want, startRequest)` → `QSharedPointer<QOhosOperationStatus>` |
| 获取结果启动 | `startForResult(want)` / `startForResult(want, options, receiver)` — void | `startAbilityForResult(want)` → `QByteArray`(requestId) / `(want, options)` / `(want, startRequest)` |
| 结果回调 | `QAbilityResultReceiver::handleResult(Napi::Value err, Napi::Value result)` | Qt 信号: `startAbilityForResultResponseReceived(requestId, resultCode, want)` / `startAbilityForResultErrorResponseReceived(requestId)` |
| 终止自身 | ✅ `terminateSelfWithResult(QOpenHarmonyAbilityResult)` | ❌ 不在公共 API |
| 按类型启动 | ❌ | ✅ `startAbilityByType(appType, wantParameters)` |
| 新实例启动 | ❌ | ✅ `startNewAbilityInstance(QWidget*)` |
| 启动应用进程 | ❌（通过 `QOhProcess`/`QOhChildProcess`） | ✅ `startAppProcess(processId, want, ...)` (3 重载) |
| Ability 实例销毁控制 | ✅ `getSubProcessPid/AliveState/killSubProcess` (非官方) | ✅ `setAbilityInstanceDestroyEnabled(QWindow*, bool)` |
| 系统销毁控制 | ❌ | ✅ `setDestroyFromSystemEnabled(bool)` |
| 分享数据 | ❌ | ✅ `shareDataWithShareKit(records, options)` → `QByteArray` |
| 打开链接 | ❌ | ✅ `tryOpenLink(url)` / `tryOpenLink(url, QOhosOpenLinkOptions)` |
| 继续激活 | ❌ | ✅ `setContinuationActive(bool)` |
| 继续数据获取 | ❌ | ✅ `tryGetOnContinueData(want)` / `tryRestoreOnContinueDistributedDataObjects(want)` |
| NewWant 信号 | ❌ | ✅ `newWantReceived(want)` / `newWantInfoReceived(wantInfo)` |
| 继续请求信号 | ❌ | ✅ `continueRequestReceived(QOhosOnContinueContext)` |
| 分享面板信号 | ❌ | ✅ `shareKitPanelClosed(requestId)` / `shareKitCompleted(requestId, result)` |

### 3.3 Want 数据结构

| 字段/能力 | 社区版 `QOpenHarmonyWant` | 官方版 `QOhosWant` |
|----------|------------------------|-----------------|
| parameters 类型 | `QVariantMap` | `QJsonObject` |
| flags 类型 | `int` (直接赋值) | `QOhosWantFlags` (QFlags) |
| Want Flag 枚举 | ❌ 直接 int | ✅ `QOhosWantFlag`：AuthReadUriPermission / AuthWriteUriPermission / InstallOnDemand |
| 文件描述符 | ❌ | ✅ `QHash<QString,int> fds` |
| WantInfo | ❌ | ✅ `QOhosWantInfo` 抽象类: `LaunchReason` 枚举(Unknown/StartAbility/Continuation/PrepareContinuation/Preload) / `ContactInfo` 结构体 / `tryGetSharedRecordsFromShareKit()` / `tryGetContactInfo()` |
| 终止结果 | ✅ `QOpenHarmonyAbilityResult` (resultCode + want) | ❌ |
| NAPI 依赖 | ✅ 通过 `QAbilityResultReceiver` 间接依赖 | ❌ 纯 Qt 类型 |

### 3.4 StartOptions（启动选项）

| 字段/能力 | 社区版 `QOpenHarmonyStartOptions` | 官方版 `QOhosStartOptions` |
|----------|-------------------------------|--------------------------|
| 类型 | 普通结构体，公共字段直接赋值 | 抽象类，纯虚 setter + 工厂创建 |
| 窗口模式 | `int windowMode` (原始 int) | ✅ `enum class WindowMode`：SPLIT_PRIMARY / SPLIT_SECONDARY / FULLSCREEN |
| 进程模式 | `int processMode` | ✅ `enum class ProcessMode`：NEW_PROCESS_ATTACH_TO_PARENT / NEW_PROCESS_ATTACH_TO_STATUS_BAR_ITEM |
| 启动可见性 | `int startupVisibility` | ✅ `enum class StartupVisibility`：STARTUP_HIDE / STARTUP_SHOW |
| 起始窗口图标 | `QPixmap startWindowIcon` | `QImage` (通过 `setStartWindowIcon(QImage)`) |
| 起始窗口背景色 | `QString startWindowBackgroundColor` | `QColor` (通过 `setStartWindowBackgroundColor(QColor)`) |
| 窗口最小/最大尺寸 | ❌ | ✅ `setMinWindowWidth/Height` / `setMaxWindowWidth/Height` |
| 隐藏起始窗口 | ❌ | ✅ `setHideStartWindow(bool)` |
| 窗口创建参数 | ❌ | ✅ `setWindowCreateParams(QOhosWindowCreateParams)` |
| 窗口创建动画 | ❌ | ✅ `QOhosWindowCreateParams::AnimationType`：FADE_IN_OUT |
| 创建方式 | 直接构造 + 默认构造函数 | 工厂函数 `createStartOptions()` / `createWindowCreateParams()` |
| SupportWindowMode | 全局 `enum class SupportWindowMode{FULL_SCREEN,SPLIT,FLOATING,INVALID_VAL}` | 嵌套 `enum class QOhosStartOptions::SupportWindowMode{FULL_SCREEN,SPLIT,FLOATING}` |

### 3.5 文件共享

| 接口能力 | 社区版 `QOHFileShare` | 官方版 `QtOhosExtras::FileShare` |
|---------|----------------------|-------------------------------|
| 容器 | 静态类 | 命名空间 |
| 模式枚举 | `Mode{READ_MODE=1, WRITE_MODE=2}` | `OperationMode{Read=1, Write=2}` |
| 错误枚举 | `Error{ERR_OK, EXCEED_LIMIT, PERSISTENCE_FORBIDDEN, INVALID_MODE, INVALID_PATH, PERMISSION_NOT_PERSISTED}` | `PathPolicyError{Unknown, PersistenceForbidden, InvalidMode, InvalidPath, PermissionNotPersisted}` |
| 策略结构 | `Policy{Modes mode; QString file;}` | `PathPolicy{QString path; OperationModes operationModes;}` |
| API 模式 | 静态方法返回 `Error` + 输出参数 `Results&` | 自由函数返回 `QSharedPointer<ActionResult>` |
| 操作状态 | 仅错误码 | ✅ `QOhosOperationStatus` 对象 (`success()` 方法) |
| 检查方法名 | `checkPersistentPermission` | `checkPersistent` |

### 3.6 窗口辅助

| 接口能力 | 社区版 `QOhWidgetHelper` | 官方版 `QOhosWindowUtils` |
|---------|------------------------|--------------------------|
| API 风格 | 实例类，构造时绑定 QWidget/QWindow | 命名空间自由函数，含 QWindow*/QWidget* 重载 |
| 隐私模式 | `setPrivacyMode(bool)` / `isPrivacyMode()` | `setWindowPrivacyMode(QWindow*, bool)` (无 getter) |
| 圆角半径 | `setWindowCornerRadius(qreal)` / `windowCornerRadius()` | `setWindowCornerRadius(QWindow*, double)` (无 getter) |
| 保持屏幕常亮 | `setWindowKeepScreenOn(bool)` | `setWindowKeepScreenOn(QWindow*/QWidget*, bool)` |
| 背景色 | `setWindowBackgroundColor(QColor)` | `setSurfaceBackgroundColor(QWindow*/QWidget*, QColor)` |
| 拖拽可调整 | `setResizeByDragEnabled(bool)` | `setWindowDragResizable(QWindow*/QWidget*, bool)` |
| 几何持久化 | `setWindowRectAutoSave(bool)` (实例级) | `setMainWindowGeometryPersistenceHint(WindowGeometryPersistenceHint)` (全局级) |
| 浮动窗口提示 | ❌ | ✅ `setShowWindowAsFloatWindowHint()` |
| 关闭事件根因 | ❌ | ✅ `getCloseEventRootCause(QCloseEvent*)` |
| 拖拽关键帧策略 | ❌ | ✅ `enableWindowDragKeyFramePolicy()` / `disableWindowDragKeyFramePolicy()` |
| 最大化选项 | ❌ | ✅ `setWindowMaximizeOptions()` / `clearWindowMaximizeOptions()` |
| 原生窗口 ID | ❌ | ✅ `tryGetNativeWindowId()` |
| 屏幕 Display ID | ❌ | ✅ `tryGetScreenDisplayId()` |
| Ability 绑定键 | ❌ | ✅ `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| 装饰按钮样式 | ✅ `DecorButtonStyle` 结构体 + getter/setter | ❌ |
| 装饰可见性 | ✅ `windowDecorVisible()` / `setWindowDecorVisible()` | ❌ |
| 窗口阴影 | ✅ `setWindowShadowRadius()` | ❌ |
| 标题栏移动 | ✅ `setWindowTitleMoveEnabled()` | ❌ |
| 标题按钮可见性 | ✅ `setWindowTitleButtonVisible(bool, bool, bool)` | ❌ |
| 标题按钮矩形 | ✅ `titleButtonRect()` + `titleButtonRectChanged` 信号 | ❌ |
| 起始窗口移除 | ✅ `removeStartingWindow()` | ❌ |
| PC 模式信号 | ✅ `pcModeChanged(bool)` | ❌ |

### 3.7 进程管理

| 接口能力 | 社区版 | 官方版 |
|---------|--------|--------|
| QProcess 风格包装 | ✅ `QOhProcess`：`start()` / `startDetached()` / `setMode()` / `stop()` / `isRunning()` / `pid()` / `errorString()` + `started`/`finished`/`errorOccurred`/`stateChanged` 信号 | ❌ 无对应类 |
| 原生子进程 | ✅ `QOhChildProcess` namespace: `startChildProcess()` / `startNativeChildProcess()` / `createNativeChildProcess()` / `createNativeChildProcessWithConfig()` | ❌ 简化为 `QOhosAppContext::startNoUiChildProcess(libraryName, args)` |
| 子进程配置 | ✅ `StartMode`/`IsolationMode`/`Options`/`Fd`/`Args`/`ChildProcessConfig` 结构体 | ❌ |
| 子进程管理 | ✅ `getSubProcessPid()` / `getSubProcessAliveState()` / `killSubProcess()` | ❌ |

### 3.8 本地 IPC

| 接口能力 | 社区版 | 官方版 |
|---------|--------|--------|
| 抽象本地套接字 | ✅ `QOhAbstractLocalSocket`：`send(QString)` / `errorString()` / `close()` / `messageReady` 信号 | ❌ **完全不存在** |
| 本地套接字客户端 | ✅ `QOhLocalSocket`：`connect(address)` / `disconnectFromHost()` / `isConnected()` | ❌ |
| 本地套接字服务端 | ✅ `QOhLocalServer`：`listen(address)` / `nextPendingConnection()` / `newConnection` 信号 | ❌ |
| 本地套接字连接 | ✅ `QOhLocalConnection` | ❌ |

### 3.9 权限管理

| 接口能力 | 社区版 `QtOh` namespace | 官方版 `AppPermissions` + `QOhosAbilityContext` |
|---------|------------------------|----------------------------------------------|
| 权限类型 | 字符串 `QString` | ✅ 类型化枚举 `Permission`(ReadPasteboard/CustomScreenCapture/AccessBluetooth/ApproximatelyLocation/Location) + 字符串重载 |
| 同步请求 | ✅ `requestPermissionsSync(QStringList, timeoutMs)` | ❌ 仅异步 |
| 异步请求 | ✅ `requestPermissions(QStringList, callback)` | ✅ `requestPermissionFromUserIfNeeded(Permission)` + 信号 |
| 设置页同步请求 | ✅ `requestPermissionsOnSettingSync(QStringList, timeoutMs)` | ❌ |
| 设置页异步请求 | ✅ `requestPermissionsOnSetting(QStringList, callback)` | ✅ `requestPermissionOnSettingIfNeeded(Permission)` + 信号 |
| 权限检查 | `checkPermission(QString)` → `PermissionResult` 枚举 | `isPermissionGranted(Permission)` → bool |
| 结果类型 | `PermissionResult` 枚举(Denied/Granted/InValidRequest) | `PermissionResult` 结构体(bool permissionGranted, bool dialogShown) |
| 通知权限 | ✅ `requestEnableNotification()` / `requestEnableNotificationSync()` / `isNotificationEnabled()` / `openNotificationSettings()` | ❌ |
| SDK 版本 | ✅ `ohSdkVersion()` | ❌ |

### 3.10 官方版独有 Extras 接口

| 接口 | 实现能力 |
|------|---------|
| `QOhosDistributedDataObject` | 跨设备分布式数据同步：`create(QJsonObject)` / `get(key)` / `fieldNames()` / `addAssets(files)` / `assetKey()` / `assets()` / `areAssetsSynced()` / `sessionId()` / `save(deviceId)` + 4 个信号(dataChanged/statusChanged/progressChanged/saveFinished) |
| `QOhosShareKit` namespace | 系统分享框架：`QOhosSharedRecord`(13属性) / `QOhosShareControllerOptions`(anchor/单选/预览/排除) / `QOhosShareOperationResult` / 工厂函数 createContentRecord/createFileRecord/createUrlRecord |
| `QOhosMultimedia` namespace | 音频流使用提示：`AudioStreamUsageHint` 枚举(14值: Unknown/Music/VoiceCommunication/VoiceAssistant/Alarm/VoiceMessage/Ringtone/Notification/Accessibility/Movie/Game/Audiobook/Navigation/VideoCommunication) |
| `QOhosOnContinueContext` | 分布式迁移上下文：`setAgreeResponse()` / `setRejectResponse()` / `setMismatchResponse()` / `setResponseOnDistributedDataObjectsSaveResults()` / `setExitAppOnSourceDeviceAfterMigration()` / `sourceApplicationVersionCode()` / `targetDeviceId()` |
| `QOhosOpenLinkOptions` | 链接打开选项：`setAppLinkingOnly(bool)` |
| `QOhosStartRequest` | 异步启动请求：`requestSucceeded` / `requestFailed` 信号 |
| `QOhosOperationStatus` | 操作状态：`success()` |
| `QOhosFileUtils` | 文件工具：`moveFileToTrash()` / `authorizeFilePath()` |
| `QOhosBundleInfo` | 应用包信息：`versionCode()` |
| `QOhosPasteboard` | 剪贴板：`setInAppOnlyPasteboardShareOption()` |
| `QOhosDragKeyFramePolicy` | 拖拽关键帧策略：`setInterval()` / `setDistance()` / `setAnimationDuration()` / `setAnimationDelay()` |
| `QOhosWindowMaximizeOptions` | 窗口最大化选项：`MaximizePresentation`(4值) / `AcrossDisplayPresentation`(3值) / 快照动画配置 |
| `QOhosElementName` | 元素名称结构体：deviceId/bundleName/abilityName/uri/shortName/moduleName |
| `QOhosWantInfo` | Want 信息：`LaunchReason` 枚举(5值) / `ContactInfo` / `tryGetSharedRecordsFromShareKit()` / `tryGetContactInfo()` |

---

## 4. QPA 平台插件接口对比

### 4.1 PlatformIntegration（平台集成）

| 接口能力 | 社区版 `QOhPlatformIntegration` | 官方版 `QOhosPlatformIntegration` |
|---------|-------------------------------|--------------------------------|
| 窗口/BackingStore/OpenGL/Offscreen 创建 | ✅ | ✅ |
| 事件分发器 | ✅ | ✅ |
| 字体/剪贴板/拖拽/输入法/服务 | ✅ | ✅ |
| 主题管理 | ✅ `QOhPlatformTheme` | ✅ `QOhosPlatformTheme` |
| 无障碍 | ✅ SDK > 13 条件 | ✅ 无条件 + `tryInitializeAccessibilityForQWindowWithXComponent()` |
| 触摸设备管理 | ✅ `touchDevice()` / `setTouchDevice()` | ❌ 内部处理 |
| 键盘修饰键查询 | ✅ `queryKeyboardModifiers()` | ❌ |
| 虚拟桌面 | ✅ `isVirtualDesktop()` | ❌ |
| Vulkan 支持 | ✅ `createPlatformVulkanInstance()` | ❌ |
| Ability 控制钩子 | ✅ `abilityCtrl()` → `QPlatformAbilityCtrl` | ❌ 通过 `QOhosQpaFunctions` 实现 |
| 访问控制钩子 | ✅ `accessCtrl()` → `QPlatformAccessCtrl` | ❌ 通过 `QOhosQpaFunctions` 实现 |
| 单例访问 | ❌ | ✅ `instance()` (static) |
| 预初始化显示指标 | ❌ | ✅ `setDefaultDisplayMetrics()` (static) |
| 系统区域设置 | ❌ | ✅ `systemLocale()` / `setSystemLocale()` |
| 窗口几何持久化策略 | ❌ | ✅ `WindowGeometryPersistencePolicy` 枚举(Disabled/Enabled/FollowSystemSetting) |
| 长按上下文菜单 | ❌ | ✅ `setContextMenuOnLongPressEnabled()` / `getSyntheticQPointForContextMenuOnLongPress()` |
| 暗色主题静态控制 | ❌ | ✅ `setDarkThemeEnabled()` (static) |
| 应用状态跟踪 | ❌（窗口级 `applicationStateChanged()`） | ✅ 独立 `QOhosApplicationStateTracker` |
| 多屏管理 | ❌ 单屏 `screen()` | ✅ `screenManager()` → `QOhosScreenManager` |
| 输入法事件处理器 | ❌ | ✅ `inputMethodEventHandler()` |
| 文件引擎处理器 | ✅ `QOhFileEngineHandler` 成员 | ❌ 不在集成头文件暴露 |
| 密码模式标志 | ✅ `m_showPasswordEnabled` 静态标志 | ❌ |
| SDK 条件显示后端 | ✅ `QJsDisplay*`(SDK≤13) / `QOhDisplayManager`(SDK>13) | ❌ 统一使用 `QOhosScreenManager` + `QOhosDisplayInfo` |

### 4.2 PlatformWindow（平台窗口）

| 接口能力 | 社区版 `QOhPlatformWindow` | 官方版 `QOhosPlatformWindow` |
|---------|------------------------|---------------------------|
| 基本窗口操作 (几何/可见/光标/父子) | ✅ | ✅ |
| 窗口透明度 | ✅ `setOpacity(qreal)` 覆写 | ❌ |
| 窗口模态 | ✅ `modality()` 虚函数 | ❌ |
| 窗口属性标签系统 | ❌ 名称字符串标识 | ✅ 12 个静态属性描述符 `QOhosPropertyDescriptor<T>` |
| 子窗口/主窗口/浮动窗口标签 | ❌ | ✅ `tagWindowOrWidgetAsSubWindowOf()` / `tagWindowOrWidgetAsMainWindow()` / `tagWindowOrWidgetAsFloatWindow()` |
| Widget-窗口宿主标签 | ❌ | ✅ `tagWidgetWindowAsHostOfWidget()` |
| 窗口装饰预设 | ❌ | ✅ `DecorationPreset` (Standard/Frameless) |
| 安全区域边距 | ❌ | ✅ `safeAreaMargins()` |
| 实际边框边距 | ✅ `setFrameMargins()` (空操作虚函数) | ✅ `frameMargins()` (真实实现) |
| 窗口快照 | ❌ | ✅ `makeSnapshot()` → QPixmap |
| 表面消费者 API | ❌ | ✅ `setSurfaceConsumer()` |
| 非客户区指针事件 | ❌ | ✅ `onNonClientAreaPointerPress/Move/Release()` |
| 窗口亮度/对比度/饱和度 | ❌ | ✅ `setBrightness()` / `setContrast()` / `setSaturation()` |
| 窗口固定大小 | ❌ | ✅ `windowFixedSizeStateProperty` |
| OHOS→Qt 状态双向同步 | ❌ 单向(Qt→OHOS) | ✅ `setWindowStateFromOhos()` / `setWindowGeometryFromOhos()` / `setExposedFromOhos()` / `setDisplayIdFromOhos()` / `notifyWindowDestroyedFromOhos()` 等 |
| DPI 变化处理 | ❌ | ✅ `handleDpiChange()` |
| 窗口标志管理 | ❌ | ✅ `setWindowFlags()` / `windowFlags()` / `platformWindowFlagsForQWindow()` / `onWindowFlagsChanged()` |
| 窗口激活请求 | ❌ | ✅ `requestActivateWindow()` |
| 软键盘需求标志 | ❌ | ✅ `setNeedSoftKeyboard()` |
| 关闭事件根因 | ❌ | ✅ `CloseEventRootCause` 枚举 |
| Ability-QWindow 绑定键 | ❌ | ✅ `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| 弹出窗口关闭 | ❌ | ✅ `closeAllActivePopups()` (static) |
| 类型安全窗口查找 | ❌ | ✅ `fromQWindow()` / `fromQWindowOrNull()` (static) |
| 模板属性系统 | ❌ | ✅ `setWindowOrWidgetProperty<T>()` / `tryGetWindowOrWidgetProperty<T>()` |
| 窗口节点直接访问 | ✅ `nativeWindowNode()` → `QOhWindowNode*` | ❌ 使用属性系统替代 |
| 手动曝光触发 | ✅ `fireFullExpose()` / `fireExpose()` | ❌ 内部处理 |
| XComponent 大小 | ✅ `xcomponentSize()` | ❌ |
| 装饰按钮样式 | ✅ `DecorButtonStyle` 结构体 | ❌ |
| 装饰可见性 | ✅ `windowDecorVisible()` / `setWindowDecorVisible()` | ❌ |
| 窗口阴影半径 | ✅ `setWindowShadowRadius()` | ❌ |
| 标题栏移动 | ✅ `setWindowTitleMoveEnabled()` | ❌ |
| 标题按钮可见性 | ✅ `setWindowTitleButtonVisible(bool, bool, bool)` | ❌ |
| 标题按钮矩形 | ✅ `titleButtonRect()` + 信号 | ❌ |
| 起始窗口移除 | ✅ `removeStartingWindow()` | ❌ |
| 16 值渲染适配 | ✅ `setNativeNodeRenderFit(NativeNodeRenderFit)` — 16 种模式 | ❌ 2 值 `NativeNodeRenderFitPolicy` (TopLeft/Fill) |
| 原生节点背景色 | ✅ `setNativeNodeBackgroundColor(QColor)` 实例方法 | ❌ 静态 + 属性描述符 + QPA 函数 |
| 窗口状态事件 | ✅ `handleWindowStatusEvent(WindowStatusType)` + 7 值枚举 | ❌ `setWindowStateFromOhos()` + `onWindowStateChanged()` |
| 窗口光标类型 | ✅ `QCursorInfo*` 自定义结构 | ✅ 标准 `QCursor` + `QOhosOptional<QCursor>` |
| 窗口标识 | ✅ 名称字符串 (`windowName`/`parentWindowName`) | ✅ 类型化 `InternalWindowId` + 属性标签 |
| 原生窗口 ID | ✅ `nativeWindowId()` → `int32_t` (实例方法) | ✅ `tryGetNativeWindowId(QObject*)` → `QOhosOptional<double>` (QPA 函数) |

### 4.3 NativeInterface（原生接口）

| 接口能力 | 社区版 `QOhPlatformNativeInterface` | 官方版 `QOhosPlatformNativeInterface` |
|---------|-----------------------------------|-------------------------------------|
| 原生资源指针暴露 | ✅ `"UIAbility"`, `"UIAbilityContext"`, `"nativeSettings"` (via `nativeResourceForIntegration`) | ❌ 不暴露原生指针 |
| 窗口级原生资源 | ✅ `"nativeXComponent"`, `"NativeNode"`, `"nativeWindow"`, `"nativeWindowStage"`, `"vkSurface"` (via `nativeResourceForWindow`) | ❌ |
| 原生资源函数查询 | ✅ `"isFreeWindowEnable"` (via `nativeResourceFunctionForIntegration`) | ❌ |
| 平台函数 | ✅ `setNativeNodeRenderFit`, `setNativeNodeRenderBackgroundColor` | ✅ `tagWindowOrWidgetAsSubWindowOf`, `getWindowOrWidgetAsSubWindowOfTagValue`, `tagWindowOrWidgetAsMainWindow`, `setInAppOnlyPasteboardShareOption`, `tagWidgetWindowAsHostOfWidget`, `setSurfaceConsumer` |
| 自定义事件处理 | ❌ | ✅ `customEvent(QEvent*)` 覆写 |

### 4.4 其他 QPA 接口

| 接口 | 社区版 | 官方版 |
|------|--------|--------|
| **光标** | 丰富：`setOverrideCursor()`/`clearOverrideCursor()`/`enforceOverrideCursor()`/`setPos()`/`size()`/每窗口光标/像素缓存 | 极简：仅 `changeCursor()` + `pos()` |
| **系统托盘** | 完整类：`ContentType`(5值)/`SlotType`(5值)/明暗图标/NAPI 桥接 | 工厂函数隐藏实现 |
| **菜单** | ✅ `QOhPlatformMenu` + `QOhPlatformMenuItem` 完整实现 | ❌ 无 `QPlatformMenu` 子类 |
| **拖拽** | 具体类 `QOhDrag` + `QOhDropTarget` | 抽象类 `QOhosPlatformDrag`：`handlePreDrop()` + `updateDropAction()` |
| **剪贴板** | 直接 `OH_Pasteboard` C API + 进度(SDK≥15) + 观察者 + 单例 | `QOhosClipboardObject` 抽象 + 懒加载 + 应用内共享 + `setInAppOnlyPasteboardShareOption()` |
| **BackingStore** | 普通 `QPlatformBackingStore` + 简单 `BufferRegionHandler` + VSync(SDK>14) | `QRasterBackingStore` + `QImageView`/`BufferRegionHandler`/`FlushData`/`WindowContext`/`WindowContextManager`（多窗口脏区合并+延迟刷新）+ GL BackingStore |
| **EGL 上下文** | 普通 `QEGLPlatformContext` 子类 | 带结构化 `CreateInfo` + `swapBuffers()` 重写 + 交换状态跟踪 |
| **系统区域设置** | ❌ | ✅ `QOhosSystemLocale`：`query()` / `fallbackUiLocale()` |
| **屏幕管理** | `QOhDisplayManager`：`allScreens()`/`screenAt()` | `QOhosScreenManager`：`rebuildScreenList()`/display ID 查找 |
| **无障碍** | `QOhPlatformAccessibility::notifyAccessibilityUpdate()` (SDK>13) | 完整子系统：`QOhosAccessibilityTree`/`Provider`/`EventHandler`/`ArkUIHelpers`/`MenuActions`/`TabBars`/`TableModelChangeEventHandler` 等 17+ 文件对 |
| **应用状态** | `applicationStateChanged()` (窗口级) | 独立 `QOhosApplicationStateTracker` |
| **图标引擎** | ❌ | ✅ `QOhosPlatformTheme::createIconEngine()` |
| **输入法控制器** | `InputMethod::QOhController` (外部 C API `inputmethod_controller_capi.h`) | `QOhosInputMethodProxy` (JS/NAPI) + `ImConnectionState` 状态机 (Attached/Detached) |
| **输入法事件过滤** | `filterEvent(QEvent*)` 覆写 | `eventFilter(QObject*, QEvent*)` 覆写 |
| **输入法文本/回车类型** | 无自有枚举；使用 C API 类型 `InputMethod_TextInputType`/`InputMethod_EnterKeyType` + 转换函数 | ✅ 自有 `TextInputType`(10值) + `EnterKeyType`(9值) + `Direction`(4值) 枚举 + `OhosEnumMeta` JS 映射 |
| **输入法光标处理** | `setKeyboardRect()` + 私有槽 `cursorRectangleChanged()`/`updateCursor()` | `updateOhosCursor()` + `onCursorRectangleChanged()` + `tryQueryCursorPosition()` |
| **输入法预览文本** | `m_previewText` + `finishTextPreview()` 槽 | `m_pendingPreeditText` + `sendInsertedPreviewTextToQt()` + `PreviewReplaceRange` |
| **死锁检测** | ❌ | ✅ `QOhosDeadlockProtector` |
| **大数据事件日志** | ❌ | ✅ `QOhosBigDataEventLogging` |
| **窗口属性描述符** | ❌ | ✅ `QOhosPropertyDescriptor<T>` 模板 + `QOhosPropertiesStore` + `QOhosPropertiesProvider` |
| **手势识别器** | ❌ | ✅ `makeQOhosPinchGestureRecognizer()` (widgets) |

---

## 5. Corelib 内核支持接口对比

### 5.1 集中式平台函数接口

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| **中央 API 接口** | 分散在 `QtOh` 命名空间 + `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` 抽象 | ✅ `QtOhos::QOhosQpaFunctions` — **60+ 纯虚函数统一接口** |

官方版 `QOhosQpaFunctions` 涵盖的全部能力分类：

| 分类 | 方法数 | 能力 |
|------|--------|------|
| 窗口操作 | 15+ | 隐私模式/圆角/背景色/保持屏幕常亮/拖拽调整/关键帧策略/最大化选项/亮度/对比度/饱和度/浮动窗口标签/渲染适配策略/销毁标志/固定大小/Ability绑定 |
| 主题配置 | 6 | 暗色主题/字体大小缩放/暗色模式数据源/字体大小数据源/几何持久化策略 |
| 剪贴板 | 3 | 应用内共享/获取图像/获取文本 |
| 文件操作 | 2 | 移至废纸篓/文件对话框授权 |
| 上下文菜单 | 2 | 启用长按菜单/合成菜单点检测 |
| 屏幕/窗口 ID | 3 | 原生窗口 ID/屏幕 Display ID/屏幕取色 |
| Ability 生命周期 | 4 | 继续请求处理器/继续激活/销毁标志/应用重启 |
| Want 管理 | 3 | 获取启动 Want/获取启动 WantInfo/添加 Want 消费者(2重载) |
| 进程管理 | 4 | 启动应用进程/无UI子进程/读取无UI模式/版本号 |
| Ability 启动 | 3 | 启动 Ability/按类型启动/启动获取结果 |
| 权限管理 | 5 | 命名权限检查/从用户请求/从设置请求/批量从用户请求/批量从设置请求 |
| 串口权限 | 2 | 检查串口权限/请求串口权限 |
| 文件共享 | 5 | 持久化/撤销/激活/停用/检查持久权限 |
| Share Kit | 1 | 分享数据（含 SharedRecord/ShareControllerOptions） |
| 链接打开 | 1 | 尝试打开链接（含 appLinkingOnly 选项） |
| 分布式数据 | 3 | 生成会话 ID/获取分布式文件目录/创建分布式数据对象 |
| 无障碍 | 1 | 通知可访问接口已删除 |
| 音频流 | 2 | 设置/获取音频流使用提示（14 种 AudioStreamUsage） |

### 5.2 设备/系统信息

| 能力 | 社区版 `QtOh::Utility` | 官方版 `QOhosDeviceInfo` |
|------|------------------------|------------------------|
| 返回类型 | 类型化 `QString`/`int` | `QVariant` |
| 属性数量 | 27 个静态方法 | 32 个 Type 枚举值 |
| 设备类型 | `DeviceType` 位标志枚举(9值: Unknown/PC/Phone/Wearable/LiteWearable/Tablet/Tv/Car/SmartVision) | `RecognizedDeviceType` 枚举(3值: _2in1/tablet/phone) |
| 识别方法 | `isTabletDevice()`/`isPhoneDevice()`/`isSupportFreeWindow()`/`isOpenHarmonyDevice()` (在 `qohauxiliary.h`) | `isTablet()`/`is2in1()`/`isPhone()`/`isCurrentDeviceSupported()`/`tryGetRecognizedDeviceType()` |
| 独有属性 | `productSeries` | `hardwareProfile`/`serial`/`majorVersion`/`seniorVersion`/`featureVersion`/`buildVersion`/`udid` |
| SDK 版本 | `QtOh::Utility::sdkApiVersion()` + `QtOh::ohSdkVersion()` | `QOhosDeviceInfo::sdkApiVersion()` |

### 5.3 看门狗与事件

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 看门狗 | ✅ `QOhosWatchdog`（Hicollie）: `Init()`/`Stop()`/`SetAppMainThreadState()`/`AllowReportEvent()`/`IsReportEvent()`/`Timer()` | ✅ `QOhosWatchdog`（类似实现） |
| HiAppEvent | ✅ `QOhHiAppEvent` 单例: 事件类型(FAULT/STATISTIC/SECURITY/BEHAVIOR)/`writeDataTag()` | ✅ `QOhosBigDataEventLogging` |
| 死锁检测 | ❌ | ✅ `QOhosDeadlockProtector` |

### 5.4 线程桥接基础设施

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| JS 线程调度 | ✅ `QtOh::runOnJsUIThreadNoWait()` / `runOnJsUIThreadAndWait()` | ✅ `QOhosJsThreadGateway::invoke()` / `invokeAndWaitForContinue()` / `runAndWait()` |
| 带返回值的 JS 线程调度 | ✅ `runOnJsUIThreadWithResult<>()` 模板（直接 `uv_queue_work` + `std::promise`） | ✅ `QOhosJsThreadGateway::eval<Func>()` / `evalWithPromise<T>()` (含 static_assert 阻止 NAPI 值泄露到 JS 线程外) |
| JS 状态抽象 | ❌ 直接暴露 `napi_env` | ✅ `QOhosJsState` 抽象类：`env()` / `defaultWindowStageOrEmpty()` / `defaultUiContextOrEmpty()` / `tryGetJsWindowByQWindow()` / `tryGetQAbilityByQWindow()` / `defaultQAbility()` / `appLaunchWant()` / `eval<T>()` / `mapOhosEnumToJs<Enum>()` |
| JS 线程操作注册 | ❌ | ✅ `QOhosJsThreadOps`：`registerInstance()` / `instance()` |
| Qt 线程状态 | ❌ | ✅ `QtState`：`isQtThread()` / `invokeTask()` / `qpaFunctions()` |
| 线程安全 QObject 引用 | ❌ | ✅ `QObjectThreadSafeRef` / `QThreadSafeRef<T>`：`visitInQtThreadIfAlive()` |
| JS 线程安全删除代理 | ❌ | ✅ `makeProxyWithJsThreadDeleter<T>()` |
| Qt 线程初始化 | ❌ | ✅ `initQtThreadState()` / `getQtState()` / `invokeInQtThread()` |
| 回调信息扩展 | ❌ | ✅ `QOhosCallbackInfo` 扩展 `QNapi::CallbackInfo` |
| 枚举-JS 映射 | ❌ | ✅ `OhosEnumMeta<Enum>` 模板 + `OhosEnumInfo`/`OhosEnumFullTypeNameFetcher` SFINAE |
| NAPI 错误处理 | ✅ `GET_AND_THROW_LAST_ERROR`/`NAPI_ASSERT_*`/`NAPI_CALL_*` 宏 | ✅ `logJsCallbackError()` / `makeErrorLoggingJsCallback()` |
| Qt 主线程调度 | ✅ `runOnQtMainThread()`/`runOnQtMainThreadWithResult()`/`runOnQtMainThreadAndWait()`/`runOnQtMainThreadLater()` 模板族 | ✅ `invokeInQtThread()` (简化) |

### 5.5 通用工具

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 异步 Promise 链 | ❌ | ✅ `QOhosTaskPromise<Args...>`：`makeChained()` / `makeBranched()` / `makeThenCatchBranches()`，支持调用者上下文链追踪 + 死 promise 检测 |
| 数组视图 | ❌ | ✅ `QOhosSpan<T>`：`begin()` / `end()` / `data()` / `size()` / `operator[]` / `subspan()` + `as_bytes()` |
| 互斥保护值 | ❌ | ✅ `QOhosMutexProtectedValue<T>`：`processValue()` / `evalWithValue()` |
| Optional 类型 | ❌ | ✅ `QOhosOptional<T>`：`hasValue()` / `value()` / `valueOr()` / `andThen()` / `transform()` + 完整比较运算符 + `QOhosOptional<void>` 特化 |
| 命名函数包装器 | ❌ | ✅ `QOhosNamedFunc<FuncPtr,Invoker>` |
| 消费者/供应者 | ❌ | ✅ `QOhosConsumer<Ts...>` / `QOhosSupplier<T>` / `QOhosNoOpConsumer` |
| 致命错误报告 | ❌ | ✅ `qOhosReportFatalErrorAndAbort` 宏 |
| UDMF 助手 | ✅ `UdmfHelper`：`createQImageFromPixelmapNative()` / `createNativePixelMapFromQImage()` / `acquireDatasFromUdmfToMime()` / `makeUdmfDataFromMime()` | ❌ |

### 5.6 标准/路径后端

| 后端 | 社区版 | 官方版 |
|------|--------|--------|
| `QStandardPaths` | ✅ `qstandardpaths_openharmony.cpp` — 直接 `OH_Environment_*` | ✅ `qstandardpaths_ohos.cpp` — 使用 `QOhosAppContext::Type` 枚举 |
| `QSettings` | ✅ `qsettings_openharmony.cpp` | ✅ 类似实现 |
| 区域设置 | ✅ `qlocale_harmony.cpp` | ✅ `QOhosSystemLocale` 完整集成 |
| 时区 | ✅ `qtimezoneprivate_openharmony.cpp` | ✅ 类似实现 |
| OS 版本 | ✅ `qoperatingsystemversion_openharmony.cpp` | ✅ 类似实现 |
| 应用目录路径 | `QtOh::dir(QString)` / `setDir(QString, QString)` — 字符串 ID | ✅ `QOhosAppContext` 命名空间：8 种 `Type` 枚举 + `init()` / `getProperty()` / `getAllProperties()` |
| URI/路径转换 | ✅ `QtOh::pathFromUri()` / `uriFromPath()` | ❌ 内部处理 |

### 5.7 GUI 内核新 QPA 抽象（社区版独有）

| 接口 | 社区版 | 官方版 |
|------|--------|--------|
| `QPlatformAccessCtrl` | ✅ 在 `gui/kernel` 中新增抽象基类，集成到 `QPlatformIntegration::accessCtrl()`：`checkPermission` / `requestPermissions` / `requestPermissionsOnSetting` / `requestEnableNotification` / `isNotificationEnabled` / `openNotificationSettings` (含同步便利实现) + `accessTokenId` / `atManagerAcquire` / `bundleManagerAcquire` / `notificationManagerAcquire` | ❌ 无此抽象，能力在 `QOhosQpaFunctions` |
| `QPlatformAbilityCtrl` | ✅ 在 `gui/kernel` 中新增纯虚接口：`startAbility` / `startAbilityForResult` / `terminateSelfWithResult` (使用 `QVariantMap` + `Napi::Value`) | ❌ 无此抽象，能力在 `QOhosQpaFunctions` |
| `QtOhPrivate` 便利函数 | ✅ `qohosabilityctrl.h`：`startAbility()` / `startAbilityForResult()` / `terminateSelfWithResult()` — 委托到平台 `QPlatformAbilityCtrl` | ❌ |

### 5.8 公共平台头文件

| 能力 | 社区版 `QOhWindowFunctions` | 官方版 `QOhosFunctions` |
|------|---------------------------|------------------------|
| 原生节点渲染适配 | ✅ `setNativeNodeRenderFit()` — **16 种适配模式** | ❌ 移至 QPA 内部 `NativeNodeRenderFitPolicy`（2 值） |
| 原生节点背景色 | ✅ `setNativeNodeBackgroundColor()` | ❌ 移至 `QOhosWindowUtils::setSurfaceBackgroundColor()` |
| 窗口标签 | ❌ | ✅ `tagWindowOrWidgetAsSubWindowOf()` / `tagWindowOrWidgetAsMainWindow()` / `getWindowOrWidgetAsSubWindowOfTagValue()` |
| 应用内剪贴板共享 | ❌ | ✅ `setInAppOnlyPasteboardShareOption()` |

### 5.9 日志

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 日志宏 | ✅ `qopenharmonydefines.h`：`LOGI`/`LOGD`/`LOGW`/`LOGE` via `OH_LOG_Print` (domain `0xff11`, tag `QPAForOpenHarmony`) | ✅ `qohoslogger_p.h`：`qOhosPrintfDebug`/`qOhosPrintfInfo`/`qOhosPrintfWarning`/`qOhosPrintfError` + `qOhosLogMessage()` / `qOhosVPrintf()` + `QCScopedDebug` RAII + `QtForOhos()` 日志分类 |
| NAPI 宏 | ✅ `GET_AND_THROW_LAST_ERROR` / `NAPI_ASSERT_*` / `NAPI_CALL_*` / `DECLARE_NAPI_*` 属性/函数描述符 | ❌ 使用 `QNapi` 包装库 |

---

## 6. 功能模块插件接口对比

### 6.1 多媒体 (qtmultimedia)

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 播放器 | ✅ `qohplayer`(包装 `OH_AVPlayer`) / `qohdecoder` / `qohdemuxer` / `qohcodekit` | ✅ `qohosavplayer`(包装 `OH_AVPlayer`) / `qohosavplayerlist` / `qohosmediaplayercontrol` |
| 摄像头 | ✅ `qohcaptureservice` / `qohcameracontrol` / `qohcamerasession` / `qohcamerarendercontrol` / `qohcameraimagecapturecontrol` 等 | ✅ `qohoscameraservice` / `qohoscamerasession` / `qohoscapturesession` / `qohoscamerainput` / `qohoscameraphotooutput` / `qohoscamerapreviewoutput` / `qohoscameravideooutput` 等 |
| 录制 | ✅ `qohrecordercontrol` / `qohaudioencodercontrol` / `qohvideoencodercontrol` / `qohcontainercontrol` | ✅ `qohosavrecorder` / `qohosmediarecordercontrol` |
| 音频设备 | ✅ `ohaudiodevice` 插件：`qohaudiodeviceplugin` / `qopenharmonyengine` / `qopenharmonyaudiomanager` / `qopenharmonyaudioinput` / `qopenharmonyaudiooutput` | ✅ `ohos-audio` 插件：`qohosaudioplugin` / `qohosaudioinput` / `qohosaudiooutput` / `qohosaudiodeviceinfo` |
| 视频渲染 | ✅ `qopenharmonysgvideonode` (场景图视频节点) | ✅ `qohosvideorenderercontrol` / `qohosvideowidget` / `qohosvideobuffer` |
| NAPI 封装 | ✅ `ohcamera` / `ohmediarecorder` / `ohmultimediautils` | ❌ 直接使用 ArkTS 桥接 |
| 音频流使用提示 | ❌ | ✅ `QOhosMultimedia::AudioStreamUsageHint`(14值) |
| 录制定时器 | ❌ | ✅ `qohosrecordingtimer` |
| 图像编码/打包/接收 | ❌ | ✅ `qohosimageencodercontrol` / `qohosimagepacker` / `qohosimagereceiver` |
| 视频设备选择 | ❌ | ✅ `qohosvideodeviceselectorcontrol` |
| 取景器控件 | ✅ `qohviewfindersettingscontrol2` | ✅ `qohoscameraviewfindersettingscontrol2` + `qohoscameraviewfinderwidget` + `qohoscameraviewfindercontrol` |

### 6.2 连接性 (qtconnectivity)

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 蓝牙状态管理 | ✅ `qbluetoothlocaldevice_ohos.cpp` | ✅ `qohosbluetoothaccess`：`BluetoothState` 枚举(OFF/TURNING_ON/ON/.../BLE_ON) + `setBluetoothEnabled()` |
| 设备发现 | ✅ `qbluetoothdevicediscoveryagent_ohos.cpp` | ✅ `qohosbluetoothdevicediscovery` |
| 服务发现 | ✅ `qbluetoothservicediscoveryagent_ohos.cpp` | ❌ |
| 蓝牙套接字 | ✅ `qbluetoothsocket_ohos.cpp` + `qjssocket` | ✅ `qohosbluetoothsocket`：`BluetoothSppType` 枚举(SPP_RFCOMM) |
| 蓝牙服务端 | ✅ `qbluetoothserver_ohos.cpp` + `serveracceptancethread` | ✅ `qohosbluetoothserver` |
| 蓝牙服务信息 | ✅ `qbluetoothserviceinfo_ohos.cpp` | ❌ |
| GATT/LE | ✅ `qlowenergycontroller_ohos.cpp` + `lowenergynotificationhub` + `qjsble` | ❌ |
| NFC | ✅ `qnearfieldmanager_openharmony` / `qnearfieldtarget_openharmony` / `qllcpsocket_openharmony` / `qllcpserver_openharmony` + `openharmonynfc` / `openharmonynfclistener` + `qjscontroller` / `qjstag` | ❌ |
| ArkTS 桥接 | ✅ 11 个 `QtBluetooth*.ts` + 3 个 `JsNfc*.ts` | ❌ 使用 C++ 封装 |
| 远程设备 | ❌ | ✅ `qohosbluetoothremotedevice` |
| 蓝牙通用工具 | ❌ | ✅ `qohosbluetoothcommon` |

### 6.3 定位 (qtlocation)

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 位置信息源 | ✅ `qgeopositioninfosource_openharmony` (包装 `LocationKit/oh_location.h`) | ✅ `qohosgeopositioninfosource` |
| 卫星信息 | ❌ | ✅ `qohosgeosatelliteinfosource` |
| 地图服务 | ❌ | ✅ `ohosmapkit`：服务提供者插件/瓦片地图管理器/瓦片获取器/文件缓存/地理编码/路由/地点搜索/搜索建议/POI 分类 |
| 插件工厂 | ✅ `qgeopositioninfosourcefactory_openharmony` | ✅ `positionfactory_ohos` |
| JS 桥接 | ❌ | ✅ `qohosjsutils` |
| 公共工具 | ❌ | ✅ `qohospositioncommon` |

### 6.4 传感器 (qtsensors)

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| 传感器管理器 | ✅ `JsSensor` + `SensorManager` 单例 (JS 桥接) | ✅ `OhosSensorsManager` 单例 (直接 `oh_sensor.h` C API) |
| 后端模板 | ❌ 独立后端类 | ✅ `OhosSensorBackendBase<T>` 模板基类 |
| 加速度计 | ✅ `openharmonyaccelerometer` | ✅ `ohosaccelerometerbackend` |
| 陀螺仪 | ✅ `openharmonygyroscope` | ✅ `ohosgyroscopebackend` |
| 磁力计 | ✅ `openharmonymagnetometer` | ✅ `ohosmagnetometerbackend` |
| 光线 | ✅ `openharmonylight` | ✅ `ohoslightsensorbackend` |
| 接近 | ✅ `openharmonyproximity` | ❌ |
| 气压 | ✅ `openharmonypressure` | ❌ |
| 湿度 | ✅ `openharmonyhumidity` | ❌ |
| 温度 | ✅ `openharmonytemperature` | ❌ |
| 旋转 | ✅ `openharmonyrotation` | ✅ `ohosrotationsensorbackend` |
| 传感器能力查询 | ❌ | ✅ `OhosSensorCapabilities`(resolution/min-max data rate) |
| ArkTS 桥接 | ✅ `JsSensor.ts` / `JsSensorManager.ts` / `JsSensorsModule.ts` | ❌ 直接使用 `oh_sensor.h` |
| 传感器 ID 映射 | ✅ OHOS↔Qt 枚举映射(12种) | ✅ `ohossensorutils` |

### 6.5 WebView (qtwebview)

| 能力 | 社区版 | 官方版 |
|------|--------|--------|
| WebView 实现 | ✅ `QHarmonyWebView` | ✅ `QOhosWebView` |
| WebView 控制器 | ❌ | ✅ `qohoswebviewcontroller` |
| Web 组件监听器 | ❌ | ✅ `qohoswebcomponentlistener` |
| Web 资源错误 | ❌ | ✅ `qohoswebresourceerror` |
| ArkTS 桥接 | ✅ `JsWebView.ets` | ❌ |

### 6.6 其他模块

| 模块 | 社区版 | 官方版 |
|------|--------|--------|
| **网络承载** | ❌ | ✅ `ohos` bearer 插件：`QOhosBearerEngine` + `QOhosManagerInterface` + `QOhosWifiInterfaceProxy` (WiFi/蜂窝/蓝牙/以太网/VPN) |
| **打印** | ✅ `openharmony` 打印支持：`QOpenHarmonyPrinterSupport` + `QOpenHarmonyPrintEngine` + `OHPrinter` 结构体 | ✅ `ohos` 打印支持：`QOhosPrinterSupport` + `QOhosNativePrint`(连接/打印/查询/管理 + `PrinterCapabilities`/`PrinterDefaultValues`/`PrinterInfo`/`PageSize` 结构体) + `QOhosPdfPrintEngine` + `QOhosPrintDevice` |
| **语音合成** | ❌ | ✅ `ohos` TTS 插件：`QTextToSpeechEngineOhos` + `texttospeechproxy`(CoreSpeechKit) + `QOhosExpected<T,E>` |
| **串口** | ❌ | ✅ `ohos` 串口后端：`QtOhosSerialManager`(`BaudRates`/`DataBits`/`Parity`/`StopBits`/`OhosSerialPort`/`OhosSerialAttribute`) + `QOhosUsbManager` |
| **样式** | ✅ `QHarmonyStyle` (1499行实现) | ✅ `QOhosStyle` |
| **字体数据库** | ✅ `QOhFontDatabase` (继承 `QGenericUnixFontDatabase`) | ✅ `QOhosPlatformFontDatabase` (继承 `QFontconfigDatabase`，使用内置 fontconfig) |
| **部署工具** | ❌ | ✅ `openharmonydeployqt` 打包工具 |
| **DevEco 模板** | 简单 EntryAbility | ✅ 完整模板：`QAbility`/`QAbilityStage`/`QEmbeddedUiExtensionAbility`/`QBundledEmbeddedUiExtensionAbility`/`QEmbeddedComponentCreator`/`QChildProcess`/4种页面节点/`OhosExportModules` + `libqohos.d.ts` TS 声明 |
| **第三方库** | 不含 | ✅ 内置 fontconfig/libjpeg/libpng/openssl |
| **mkspecs** | `openharmony.prf` (应用模板 soname) | ✅ `ohos-clang` 工具链规格 + `ohos_deployment.prf` 部署特性 |
| **枚举生成** | ❌ | ✅ (如有) |
| **手势识别** | ❌ | ✅ `makeQOhosPinchGestureRecognizer()` (widgets) |

---

## 7. 社区版独有接口能力

### 7.1 本地 IPC 套接字栈

| 接口 | 实现能力 |
|------|---------|
| `QOhAbstractLocalSocket` | 本地 IPC 基类：`send(QString)` / `errorString()` / `close()` / `messageReady` 信号 |
| `QOhLocalSocket` | 客户端：`connect(address)` / `disconnectFromHost()` / `isConnected()` |
| `QOhLocalServer` | 服务端：`listen(address)` / `nextPendingConnection()` / `newConnection` 信号 |
| `QOhLocalConnection` | 服务端接受的连接对象 |

> 官方版**完全不存在**本地 IPC 子系统。

### 7.2 完整进程管理

| 接口 | 实现能力 |
|------|---------|
| `QOhProcess` | QProcess 风格包装：`start()` / `startDetached()` / `setMode(Mode)` / `stop()` / `isRunning()` / `pid()` / `errorString()` + `started`/`finished`/`errorOccurred`/`stateChanged` 信号 |
| `QOhChildProcess` | 原生子进程：`startChildProcess()` / `startNativeChildProcess()` / `createNativeChildProcess()` / `createNativeChildProcessWithConfig()` + `StartMode`/`IsolationMode`/`Options`/`Fd`/`Args`/`ChildProcessConfig` 结构体 |
| `getSubProcessPid/AliveState/killSubProcess` | 子进程管理（非官方 API） |

### 7.3 通知权限管理

| 接口 | 实现能力 |
|------|---------|
| `QtOh::requestEnableNotification(callback)` | 异步请求通知权限 |
| `QtOh::requestEnableNotificationSync(timeoutMs)` | 同步请求通知权限 |
| `QtOh::isNotificationEnabled()` | 检查通知是否启用 |
| `QtOh::openNotificationSettings()` | 打开通知设置页面 |

### 7.4 同步权限 API

| 接口 | 实现能力 |
|------|---------|
| `QtOh::requestPermissionsSync(permissions, timeoutMs)` | 同步批量请求权限，带超时 |
| `QtOh::requestPermissionsOnSettingSync(permissions, timeoutMs)` | 同步从设置页请求权限 |

### 7.5 窗口装饰控制

| 接口 | 实现能力 |
|------|---------|
| `QOhWidgetHelper::DecorButtonStyle` | 装饰按钮样式：colorMode/buttonBackgroundSize/spacingBetweenButtons/closeButtonRightMargin |
| `setWindowDecorVisible()` / `windowDecorVisible()` | 窗口装饰可见性 |
| `setWindowShadowRadius()` | 窗口阴影半径 |
| `setWindowTitleMoveEnabled()` | 标题栏拖拽移动 |
| `setWindowTitleButtonVisible(bool, bool, bool)` | 标题按钮（最大化/最小化/关闭）可见性 |
| `titleButtonRect()` + `titleButtonRectChanged` 信号 | 标题按钮矩形查询 |
| `removeStartingWindow()` | 移除起始窗口 |

### 7.6 Vulkan 渲染支持

| 接口 | 实现能力 |
|------|---------|
| `QOhPlatformIntegration::createPlatformVulkanInstance()` | 创建 Vulkan 实例 |
| `QOhPlatformVulkanInstance` | Vulkan 实例实现：`createOrAdoptInstance()` / `createSurface()` |
| `nativeResourceForWindow("vkSurface")` | 获取 Vulkan 表面 |

### 7.7 其他独有能力

| 接口 | 实现能力 |
|------|---------|
| `QtOh::Utility` | 27 个设备/系统信息查询方法（类型化返回值） |
| `QOhHiAppEvent` | HiAppEvent 事件上报（FAULT/STATISTIC/SECURITY/BEHAVIOR） |
| `QtOh::pathFromUri()` / `uriFromPath()` | URI-路径转换 |
| `QtOh::setBundleName/ModuleName/AbilityName` | 显式身份设置 |
| `QtOh::setUIEnv(napi_env)` / `uiEnv()` | 直接 NAPI 环境访问 |
| `QOhWindowFunctions::setNativeNodeRenderFit()` | 16 种原生节点渲染适配模式 |
| `QOhPlatformNativeInterface` | 原生资源指针暴露（UIAbility/UIAbilityContext/nativeSettings/nativeWindow/nativeWindowStage/nativeXComponent/NativeNode/vkSurface） |
| `QOhPlatformCursor` | 覆盖光标 / 像素缓存 / `setPos()` / `size()` / 每窗口光标 |
| `QOhPlatformMenu` / `QOhPlatformMenuItem` | 完整平台菜单实现 |
| `QOhSystemTrayIcon::ContentType` / `SlotType` | 通知内容类型(5值) / 通知槽类型(5值) |
| `QOhPlatformClipboard` | 剪贴板进度(SDK≥15) / 粘贴板观察者 / 单例 |
| `UdmfHelper` | UDMF 数据转换：QImage↔PixelMap / UDMF↔MimeData |
| `QOhDisplayManager::screenAt(point)` | 按坐标查找屏幕 |
| `QOhPlatformScreen::densityPixels()` | 像素密度 |
| `WindowStatusType` 枚举(7值) | 窗口状态类型 |
| `WindowState` 枚举(5值) | 窗口状态 |
| `QOhCompatibility` | SDK 版本弹性层：`OhosFunction<>` 模板 (dlsym + fallback) |
| `QOhFileEngineHandler` | OpenHarmony 文件引擎（URI/rawdir） |
| `isFreeWindowEnable()` | 自由窗口能力检查 |
| `isOpenHarmonyDevice()` | OpenHarmony 设备检查 |
| NFC 支持 | `qnearfieldmanager` / `qnearfieldtarget` / `qllcpsocket` / `qllcpserver` + `qjscontroller`/`qjstag` + ArkTS 桥接 |
| 蓝牙 GATT/LE | `qlowenergycontroller_ohos` + `lowenergynotificationhub` + `qjsble` |
| 蓝牙服务发现 | `qbluetoothservicediscoveryagent_ohos` |
| 蓝牙服务信息 | `qbluetoothserviceinfo_ohos` |
| 输入法 C API 控制器 | `InputMethod::QOhController` (使用 `inputmethod_controller_capi.h` 原生 C API) |
| 输入法能力查询 | `QOhPlatformInputContext::hasCapability()` |
| 输入法鼠标忽略 | `QOhPlatformInputContext::ignoreMouse()` |
| 输入法静态访问 | `QOhPlatformInputContext::ohInputContext()` (static) |
| Qt 主线程调度模板族 | `runOnQtMainThread()` / `runOnQtMainThreadWithResult()` / `runOnQtMainThreadAndWait()` / `runOnQtMainThreadLater()` |
| NAPI 宏集 | `GET_AND_THROW_LAST_ERROR` / `NAPI_ASSERT_*` / `NAPI_CALL_*` / `DECLARE_NAPI_*` |

---

## 8. 官方版独有接口能力

### 8.1 集中式 QPA 函数接口

| 接口 | 实现能力 |
|------|---------|
| `QtOhos::QOhosQpaFunctions` | **60+ 纯虚函数统一接口**：窗口操作(15+) / 主题配置(6) / 剪贴板(3) / 文件操作(2) / 上下文菜单(2) / 屏幕ID(3) / Ability生命周期(4) / Want管理(3) / 进程管理(4) / Ability启动(3) / 权限管理(5) / 串口(2) / 文件共享(5) / ShareKit(1) / 链接打开(1) / 分布式数据(3) / 无障碍(1) / 音频流(2) |

### 8.2 分布式数据对象

| 接口 | 实现能力 |
|------|---------|
| `QOhosDistributedDataObject` | 跨设备数据同步：`create(QJsonObject)` / `get(key)` / `fieldNames()` / `addAssets(files)` / `assetKey()` / `assets()` / `areAssetsSynced()` / `sessionId()` / `save(deviceId)` |
| 信号 | `dataChanged(sessionId, changedFields)` / `statusChanged(sessionId, networkId, Status)` / `progressChanged(sessionId, progress)` / `saveFinished(success)` |
| `QOhosQpaFunctions::genDistributedDataObjectSessionId()` | 生成会话 ID |
| `QOhosQpaFunctions::tryGetDistributedFilesDir()` | 获取分布式文件目录 |

### 8.3 ShareKit 分享框架

| 接口 | 实现能力 |
|------|---------|
| `QOhosSharedRecord` | 分享记录抽象类(13属性)：mimeType/content/filePath/isUrlContent/title/label/description/thumbnail/thumbnailFilePath/extraData |
| `QOhosShareControllerOptions` | 控制器选项：anchor(QPoint/QRect)/单选模式/预览模式/排除的Ability |
| `QOhosShareOperationResult` | 分享操作结果：targetAbilityName() |
| `ShareAbilityType` 枚举 | CopyToPasteboard/SaveToMediaAsset/SaveAsFile/Print/SaveToSuperHub |
| 工厂函数 | `createContentRecord()` / `createFileRecord()` / `createUrlRecord()` / `createControllerOptions()` |

### 8.4 Ability 继续（分布式迁移）

| 接口 | 实现能力 |
|------|---------|
| `QOhosOnContinueContext` | 迁移上下文：`setAgreeResponse()` / `setRejectResponse()` / `setMismatchResponse()` / `setResponseOnDistributedDataObjectsSaveResults()` / `setExitAppOnSourceDeviceAfterMigration()` / `sourceApplicationVersionCode()` / `targetDeviceId()` |
| `QOhosAbilityContext::setContinuationActive(bool)` | 设置继续激活 |
| `tryGetOnContinueData(want)` | 获取继续数据 |
| `tryRestoreOnContinueDistributedDataObjects(want)` | 恢复分布式数据对象 |
| `continueRequestReceived` 信号 | 继续请求通知 |

### 8.5 窗口高级控制

| 接口 | 实现能力 |
|------|---------|
| 窗口亮度/对比度/饱和度 | `setBrightness()` / `setContrast()` / `setSaturation()` |
| 窗口最大化选项 | `MaximizePresentation`(4值) / `AcrossDisplayPresentation`(3值) / 快照动画配置 |
| 拖拽关键帧策略 | `setInterval(ms)` / `setDistance(px)` / `setAnimationDuration(ms)` / `setAnimationDelay(ms)` |
| 浮动窗口提示 | `setShowWindowAsFloatWindowHint()` |
| 原生窗口/屏幕 ID | `tryGetNativeWindowId()` / `tryGetScreenDisplayId()` |
| Ability-窗口绑定键 | `setBundledAbilityAndQWindowBindingKeyForQWindow()` |
| 窗口属性标签系统 | 12 个静态属性描述符 `QOhosPropertyDescriptor<T>` |
| 非客户区指针事件 | `onNonClientAreaPointerPress/Move/Release()` |
| 安全区域边距 | `safeAreaMargins()` |
| 窗口快照 | `makeSnapshot()` |
| 窗口装饰预设 | `DecorationPreset` (Standard/Frameless) |
| OHOS→Qt 状态双向同步 | `setWindowStateFromOhos()` 等 7+ 个回调 |
| 窗口固定大小 | `windowFixedSizeStateProperty` |
| 模板属性系统 | `setWindowOrWidgetProperty<T>()` / `tryGetWindowOrWidgetProperty<T>()` |
| 类型安全窗口查找 | `fromQWindow()` / `fromQWindowOrNull()` (static) |

### 8.6 屏幕/取色

| 接口 | 实现能力 |
|------|---------|
| `startPickingColorFromScreenWithConsumer()` | 屏幕取色 |
| `tryGetNativeWindowId()` | 获取原生窗口 ID |
| `tryGetScreenDisplayId()` | 获取屏幕 Display ID |
| `QOhosScreenManager` | 多屏管理：`rebuildScreenList()` / `platformScreenForDisplayIdOrNull()` |
| `QOhosPlatformScreen::notifyWindowVisibleAndActivated()` | 合成器 API — 窗口可见性跟踪 |
| `QOhosPlatformScreen::fromQScreen()` (static) | 从 QScreen 反向查找 |

### 8.7 音频流使用提示

| 接口 | 实现能力 |
|------|---------|
| `AudioStreamUsageHint` 枚举 | 14 值：Music/VoiceCommunication/VoiceAssistant/Alarm/VoiceMessage/Ringtone/Notification/Accessibility/Movie/Game/Audiobook/Navigation/VideoCommunication/Unknown |
| `setAudioStreamUsageHintProperty(QObject*, hint)` | 为音频对象设置流使用提示 |
| `tryGetAudioStreamUsageHintProperty(QObject*, hint*)` | 获取音频对象的流使用提示 |

### 8.8 线程桥接基础设施

| 接口 | 实现能力 |
|------|---------|
| `QOhosJsState` | JS 状态抽象：`env()` / `defaultWindowStageOrEmpty()` / `defaultUiContextOrEmpty()` / `tryGetJsWindowByQWindow()` / `tryGetQAbilityByQWindow()` / `defaultQAbility()` / `appLaunchWant()` / `eval<T>()` / `evalToPromiseOrRejectOnThrow()` / `mapOhosEnumToJs<Enum>()` |
| `QOhosJsThreadGateway` | 线程安全 JS 调用：`invoke()` / `invokeAndWaitForContinue()` / `runAndWait()` / `eval<Func>()` (含 static_assert 阻止 NAPI 值泄露) / `evalWithPromise<T>()` |
| `QOhosJsThreadOps` | JS 线程操作注册：`registerInstance()` / `instance()` |
| `QObjectThreadSafeRef` / `QThreadSafeRef<T>` | 线程安全 QObject 引用：`visitInQtThreadIfAlive()` |
| `QtState` | Qt 线程状态：`isQtThread()` / `invokeTask()` / `qpaFunctions()` |
| `OhosEnumMeta<Enum>` | 枚举-JS 映射模板 + `OhosEnumInfo` / `OhosEnumFullTypeNameFetcher` SFINAE |
| `makeProxyWithJsThreadDeleter<T>()` | JS 线程安全删除代理 |
| `QOhosTaskPromise<Args...>` | Promise 链式追踪：`makeChained()` / `makeBranched()` / `makeThenCatchBranches()` + 死 promise 检测 |
| `QOhosOptional<T>` | 完整 Optional 类型：`andThen()` / `transform()` + 比较运算符 |
| `QOhosSpan<T>` | 数组视图：`begin()` / `end()` / `subspan()` / `as_bytes()` |
| `QOhosMutexProtectedValue<T>` | 互斥保护值：`processValue()` / `evalWithValue()` |
| `QOhosNamedFunc` | 命名函数包装器 |

### 8.9 其他独有能力

| 接口 | 实现能力 |
|------|---------|
| `QOhosAppContext::restartApp()` | 应用重启（带可选 Want） |
| `QOhosAppContext::getAppLaunchWant/WantInfo()` | 获取应用启动 Want |
| `QOhosAppContext::fontSizeScale()` | 字体大小缩放 |
| `QOhosAppContext::enableContextMenuEventOnLongPress()` | 长按上下文菜单 |
| `QOhosAppContext::getBundleInfo()` | 应用包信息 |
| `QOhosAppContext::isNoUiChildMode()/startNoUiChildProcess()` | 无 UI 子进程 |
| `QOhosAppContext::hasSerialPortAccessRight()` | 串口权限 |
| `QOhosFileUtils::moveFileToTrash()` | 移至废纸篓 |
| `QOhosFileUtils::authorizeFilePath()` | 文件路径授权 |
| `QOhosPasteboard::setInAppOnlyPasteboardShareOption()` | 应用内剪贴板共享限制 |
| `QOhosQpaFunctions::getImageDataFromPasteboard/getTextDataFromPasteboard()` | 剪贴板数据读取 |
| `QOhosQpaFunctions::setDarkThemeEnabled()` / `makeOhosConfigDarkModeFlagDataSource()` | 暗色主题数据源（响应式） |
| `QOhosQpaFunctions::getFontSizeScale()` / `makeOhosConfigFontSizeScaleDataSource()` | 字体大小数据源（响应式） |
| `QOhosCloseEventContext` | 关闭事件上下文：`CloseRootCause`(4值) / `CloseResolution` 枚举 |
| `QOhosSystemLocale` | 系统区域设置集成 |
| `QOhosPlatformBackingStore` | 多窗口脏区合并 + 延迟刷新 + GL BackingStore |
| `QOhosEGLPlatformContext` | 结构化 CreateInfo + 自定义 swapBuffers |
| `QOhosPlatformDrag` | 拖拽前置/后置钩子 |
| `QOhosApplicationStateTracker` | 应用状态跟踪 |
| `QOhosDeadlockProtector` | 死锁检测 |
| `QOhosBigDataEventLogging` | 大数据事件日志 |
| `QOhosDeviceInfo` | 32 种设备属性 + `RecognizedDeviceType`(3值) + `isCurrentDeviceSupported()` |
| `QOhosPropertyDescriptor<T>` | 类型安全属性描述符 + `QOhosPropertiesStore` |
| 输入法状态机 | `ImConnectionState`(Attached/Detached) + `dispatchRequestedImConnectionStateChange()` |
| 输入法自有枚举 | `TextInputType`(10值) + `EnterKeyType`(9值) + `Direction`(4值) + `OhosEnumMeta` |
| 输入法光标查询 | `tryQueryCursorPosition()` |
| 输入法功能键事件 | `sendFocusObjectFunctionalKeyEvent()` |
| 网络承载插件 | WiFi/蜂窝/蓝牙/以太网/VPN |
| 地图服务 (MapKit) | 瓦片地图/地理编码/路由/地点搜索/POI |
| 语音合成 (TTS) | CoreSpeechKit 代理 |
| 串口支持 | `QtOhosSerialManager` + `QOhosUsbManager` |
| `openharmonydeployqt` | 部署打包工具 |
| 内置第三方库 | fontconfig / libjpeg / libpng / openssl |
| 完整 DevEco 模板 | QAbility/QAbilityStage/嵌入扩展/子进程/4种页面节点/OhosExportModules/libqohos.d.ts |
| 死锁检测 | `QOhosDeadlockProtector` |
| 大数据事件日志 | `QOhosBigDataEventLogging` |
| 手势识别器 | `makeQOhosPinchGestureRecognizer()` (捏合手势) |

---

## 9. 共有接口的 API 范式差异

### 9.1 对象创建模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 对象创建 | 直接 `new` / 栈构造 | 工厂函数返回 `QSharedPointer<T>` |
| 类的具体性 | 具体类，有实现 | 抽象类，全部纯虚函数 |
| 生命周期 | 手动管理 / Qt 父对象 | `QSharedPointer` 引用计数 |
| 智能指针 | `QScopedPointer` | `std::unique_ptr` / `std::shared_ptr` |

### 9.2 权限请求模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 调用方式 | 同步：`bool result = requestPermissionFromUser(permission)` | 异步：`requestPermissionFromUserIfNeeded(permission)` → void |
| 结果获取 | 直接返回值 | 信号通知：`permissionRequestResponseReceived(Permission, bool)` |
| 超时控制 | ✅ `timeoutMs` 参数 | ❌ 无超时 |
| 权限类型 | 字符串 `QString` | 类型化枚举 `Permission` + 字符串重载 |
| 通知权限 | ✅ 完整支持 | ❌ 不存在 |

### 9.3 Ability 结果返回模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 结果传递 | 回调类 `QAbilityResultReceiver::handleResult(Napi::Value err, Napi::Value result)` | Qt 信号 `startAbilityForResultResponseReceived(QByteArray requestId, int resultCode, QSharedPointer<QOhosWant> want)` |
| 错误传递 | 回调参数 `Napi::Value err` | 独立信号 `startAbilityForResultErrorResponseReceived(QByteArray requestId)` |
| 请求标识 | ❌ 不跟踪 | ✅ `QByteArray requestId` |
| NAPI 依赖 | ✅ 公共 API 依赖 NAPI | ❌ 公共 API 无 NAPI 依赖 |

### 9.4 文件共享 API 模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 函数签名 | `static Error persistPermission(Policys, Results &results)` | `QSharedPointer<ActionResult> persistPermission(QList<PathPolicy>)` |
| 返回值 | 枚举错误码 + 输出参数 | 智能指针包装的抽象结果对象 |
| 结果访问 | 直接遍历 `Results` 列表 | `ActionResult::operationStatus()` + `ActionResult::errorInfoList()` |

### 9.5 StartOptions 配置模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 构造方式 | `QOpenHarmonyStartOptions options; options.windowMode = 1;` | `auto options = createStartOptions(); options->setWindowMode(WindowMode::FULLSCREEN);` |
| 类型安全 | ❌ 原始 int 赋值 | ✅ 强类型枚举 + 虚函数 setter |
| 扩展性 | 需修改结构体 | 新增虚函数即可 |

### 9.6 窗口辅助 API 模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 使用方式 | `QOhWidgetHelper *helper = new QOhWidgetHelper(widget); helper->setPrivacyMode(true);` | `QOhosWindowUtils::setWindowPrivacyMode(window, true);` |
| 绑定对象 | 绑定到特定 QWidget/QWindow 实例 | 每次调用传入目标 QWidget/QWindow |
| 状态管理 | 实例维护状态 | 无状态函数调用 |

### 9.7 窗口标识/属性模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 窗口标识 | 名称字符串 (`windowName`/`parentWindowName`/`transientParentName`) | 类型化 `InternalWindowId` + 属性标签 (`subWindowOfTagProperty`/`mainWindowTagProperty`/`floatWindowTagProperty`) |
| 窗口属性设置 | 实例虚函数直接设置 (`setNativeNodeRenderFit`/`setNativeNodeBackgroundColor`) | 模板属性描述符 `QOhosPropertyDescriptor<T>` + 静态方法 + QPA 函数 |
| 属性查询 | ❌ | ✅ `tryGetWindowOrWidgetProperty<T,propertyPtr>()` |
| 属性写入回调 | ❌ | ✅ `QOhosPropertiesStore::addPropertyWriteCallback<T,propertyPtr>()` |

### 9.8 线程桥接模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| JS 线程调度 | `QtOh::runOnJsUIThreadNoWait(lambda)` — 简单封装 | `QOhosJsThreadGateway::invoke(lambda)` — 含死锁保护 + 等待继续 |
| 带返回值调度 | `runOnJsUIThreadWithResult<T>()` 模板 (直接 `uv_queue_work` + `std::promise`) | `QOhosJsThreadGateway::eval<Func>()` (含 `static_assert` 阻止 NAPI 值泄露到 JS 线程外) |
| Promise 调度 | `runOnJsUIThreadWithPromise<ReturnType>()` 模板 | `QOhosJsThreadGateway::evalWithPromise<T>()` + `QOhosTaskPromise` 链式追踪 |
| NAPI 泄露防护 | ❌ | ✅ `static_assert` 编译时阻止 |

### 9.9 设备信息模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 接口风格 | `QtOh::Utility` 类，静态方法返回类型化 `QString`/`int` | `QOhosDeviceInfo` 命名空间，`Type` 枚举 + `getProperty(Type)` 返回 `QVariant` |
| 设备类型 | `DeviceType` 位标志枚举(9值) | `RecognizedDeviceType` 枚举(3值: _2in1/tablet/phone) + `tryGetRecognizedDeviceType()` |
| 识别方法 | `isTabletDevice()`/`isPhoneDevice()` (在 `qohauxiliary.h`) | `isTablet()`/`is2in1()`/`isPhone()`/`isCurrentDeviceSupported()` (在 `qohosdeviceinfo_p.h`) |
| 独有属性 | `productSeries` | `hardwareProfile`/`serial`/`majorVersion`/`seniorVersion`/`featureVersion`/`buildVersion`/`udid` |

### 9.10 输入法模式

| 模式 | 社区版 | 官方版 |
|------|--------|--------|
| 控制器 | `InputMethod::QOhController` (外部，委托到 C API `inputmethod_controller_capi.h`) | `QOhosInputMethodProxy` (内部) + `ImConnectionState` 状态机 (Attached/Detached) |
| 事件过滤 | `filterEvent(QEvent*)` 覆写 | `eventFilter(QObject*, QEvent*)` 覆写 |
| 文本/回车类型 | 无自有枚举；使用 C API 类型 + 转换函数 `ohEnterKeyType()`/`ohTextInputType()` | ✅ 自有 `TextInputType`(10值) + `EnterKeyType`(9值) + `OhosEnumMeta` JS 映射 |
| 光标处理 | `setKeyboardRect()` + 私有槽 | `updateOhosCursor()` + `onCursorRectangleChanged()` + `tryQueryCursorPosition()` |
| 键盘可见性跟踪 | ❌ | ✅ `setSoftwareKeyboardVisibilityStatus()` |
| 输入法连接管理 | ❌ | ✅ `attachToInputMethodController()` / `detachFromInputMethodController()` / `dispatchRequestedImConnectionStateChange()` |

---

## 10. 总结

### 10.1 能力覆盖范围对比

| 能力领域 | 社区版 | 官方版 |
|---------|--------|--------|
| QPA 平台抽象 | ✅ 完整 | ✅ 完整且更丰富 |
| Ability 生命周期 | ✅ 基本支持 | ✅ 完整支持（含继续/迁移/多实例/实例销毁控制） |
| 窗口管理 | ✅ 基本属性控制 + 装饰控制 | ✅ 高级属性控制（亮度/对比度/饱和度/最大化选项/关键帧策略/安全区域/非客户区） |
| 权限管理 | ✅ 同步+异步 | ✅ 仅异步（类型化枚举） |
| 进程管理 | ✅ 完整 QProcess 风格 + 原生子进程 | ✅ 简化的 startAppProcess/startNoUiChildProcess |
| 本地 IPC | ✅ 完整套接字栈 | ❌ 不存在 |
| 分布式数据 | ❌ | ✅ 完整分布式数据对象 |
| 分享 | ❌ | ✅ 完整 ShareKit 框架 |
| 文件操作 | ✅ 文件共享 | ✅ 文件共享 + 废纸篓 + 路径授权 |
| 通知权限 | ✅ 完整 | ❌ 不存在 |
| 串口 | ❌ | ✅ 串口权限 + 串口管理器 |
| 多媒体 | ✅ 播放/录制/摄像头/音频 | ✅ 播放/录制/摄像头/音频 + 音频流使用提示 |
| 蓝牙 | ✅ 完整（含 GATT/LE/NFC） | ✅ 基础（无 GATT/LE/服务发现/NFC） |
| 定位 | ✅ 位置信息 | ✅ 位置信息 + 卫星信息 + 地图服务 |
| 传感器 | ✅ 9 种传感器 | ✅ 5 种传感器 |
| WebView | ✅ 基本 | ✅ 完整（控制器/组件监听/资源错误） |
| 语音合成 | ❌ | ✅ TTS |
| 网络 | ❌ | ✅ Bearer 插件 |
| 打印 | ✅ 基本打印 | ✅ 原生打印（连接/任务/查询/管理） |
| 样式 | ✅ QHarmonyStyle | ✅ QOhosStyle |
| 无障碍 | ✅ 基本通知 | ✅ 完整子系统（17+ 文件对） |
| Vulkan | ✅ 完整支持 | ❌ 不支持 |
| 部署工具 | ❌ | ✅ openharmonydeployqt |
| 第三方库 | 不含 | ✅ 内置 fontconfig/libjpeg/libpng/openssl |
| 线程桥接 | ✅ 直接 uv_queue_work 模板 | ✅ 完整抽象层（JsState/JsThreadGateway/JsThreadOps/QtState/ThreadSafeRef/TaskPromise） |
| 关闭事件 | ❌ | ✅ CloseEventContext |
| 死锁检测 | ❌ | ✅ DeadlockProtector |
| 窗口属性系统 | ❌ 名称字符串 | ✅ 类型安全属性描述符 |
| 输入法 | ✅ C API 控制器 | ✅ JS/NAPI 代理 + 状态机 + 自有枚举 |
| 设备信息 | ✅ 27 方法 + 位标志枚举 | ✅ 32 属性 + 识别类型枚举 |
| 日志 | ✅ 基本宏 | ✅ 完整日志体系 |
| UDMF | ✅ UdmfHelper | ❌ |
| SDK 弹性 | ✅ QOhCompatibility (dlsym + fallback) | ❌ (SDK 条件编译) |

### 10.2 设计哲学差异

**社区版**的设计哲学：
- **实用性优先**：提供同步 API 方便简单场景使用
- **直接暴露**：公共 API 直接依赖 NAPI，暴露原生资源指针
- **实例管理**：窗口辅助通过实例类管理状态
- **丰富但不统一**：能力分散在多个命名空间和类中
- **进程/IPC 导向**：提供完整的进程管理和本地 IPC 栈
- **原生 C API 导向**：输入法使用 `inputmethod_controller_capi.h`，剪贴板使用 `OH_Pasteboard`
- **SDK 弹性**：`QOhCompatibility` 提供 dlsym + fallback 机制
- **平台抽象扩展**：在 `gui/kernel` 新增 `QPlatformAccessCtrl`/`QPlatformAbilityCtrl` 抽象

**官方版**的设计哲学：
- **抽象性优先**：全部抽象类 + 工厂函数，隐藏实现细节
- **异步优先**：权限/Ability 结果均使用信号异步通知
- **类型安全**：强类型枚举替代原始 int，QJsonObject 替代 QVariantMap，属性描述符替代名称字符串
- **集中统一**：60+ 方法的 `QOhosQpaFunctions` 统一接口
- **生命周期管理**：`QSharedPointer` + RAII 管理对象生命周期
- **NAPI 封装**：公共 API 完全隐藏 NAPI，`static_assert` 编译时阻止 NAPI 值泄露
- **高级特性**：分布式数据/ShareKit/Ability继续/窗口亮度对比度饱和度/音频流提示等
- **工程化**：部署工具/死锁检测/完整模板/内置第三方库/多屏管理
- **JS/NAPI 桥接**：输入法使用 `QOhosInputMethodProxy` (JS/NAPI)，输入法使用自有枚举 + `OhosEnumMeta`

### 10.3 迁移要点

从社区版迁移到官方版时需要注意：

1. **命名替换**：`QOh*` → `QOhos*`，`QtOh::` → `QtOhosExtras::`，`QOpenHarmony*` → `QOhos*`，`openharmony` → `ohos`
2. **API 范式转换**：同步调用 → 异步信号；回调类 → Qt 信号；直接构造 → 工厂函数 + `QSharedPointer`
3. **类型转换**：`QVariantMap` → `QJsonObject`；`int` flags → 强类型枚举；`QPixmap` → `QImage`
4. **IPC 迁移**：`QOhLocalSocket/Server` 需替换为其他 IPC 机制（如 `startAppProcess`）
5. **进程管理迁移**：`QOhProcess/QOhChildProcess` 需替换为 `startAppProcess()/startNoUiChildProcess()`
6. **通知权限迁移**：社区版的 `QtOh::requestEnableNotification()` 等需自行实现或移除
7. **窗口装饰迁移**：`DecorButtonStyle`/`setWindowShadowRadius`/`setWindowTitleButtonVisible` 等无对应接口
8. **Vulkan 迁移**：如使用 Vulkan 渲染，官方版不支持，需改用 OpenGL/EGL
9. **NAPI 依赖移除**：公共 API 不再依赖 `QtNapi/napi.h`，`QAbilityResultReceiver` 需替换为信号连接
10. **平台抽象迁移**：`QPlatformAccessCtrl`/`QPlatformAbilityCtrl` 在 `gui/kernel` 的抽象不再存在，能力在 `QOhosQpaFunctions`
11. **设备信息迁移**：`QtOh::Utility` 静态方法 → `QOhosDeviceInfo` 命名空间 + `Type` 枚举 + `QVariant` 返回
12. **输入法迁移**：`InputMethod::QOhController` (C API) → `QOhosInputMethodProxy` (JS/NAPI) + 自有枚举
13. **窗口标识迁移**：名称字符串 (`windowName`) → 属性标签 (`subWindowOfTagProperty`)
14. **渲染适配迁移**：16 值 `NativeNodeRenderFit` → 2 值 `NativeNodeRenderFitPolicy`
15. **新增能力利用**：可利用分布式数据对象/ShareKit/Ability继续/音频流提示/串口/TTS/地图服务等官方版新能力
