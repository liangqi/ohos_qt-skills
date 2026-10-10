# Qt for HarmonyOS 5.12.12 vs 5.15.16 鸿蒙化差异分析文档

> **对比路径**
> - 5.12.12: `qt-5.12.12/qt-harmonyos-src`
> - 5.15.16: `qt-5.15.16/qt5.15.16`
>
> **用途**: 开发者和 skill 可根据本文档实现两个版本之间的代码切换/迁移。

---

## 目录

1. [总体概览](#1-总体概览)
2. [构建系统差异(.pro / .qmake.conf / configure)](#2-构建系统差异)
3. [头文件差异(新增 / 重命名 / 删除)](#3-头文件差异)
4. [公共 API 接口差异(QtOhosExtras 模块)](#4-公共-api-接口差异qtohosextras-模块)
5. [平台插件 API 差异(qtbase ohos QPA)](#5-平台插件-api-差异qtbase-ohos-qpa)
6. [权限(Permissions)差异](#6-权限permissions差异)
7. [文件分享(File Sharing / ShareKit / UDMF)差异](#7-文件分享file-sharing--sharekit--udmf差异)
8. [主题(Theme / ColorMode)差异](#8-主题theme--colormode差异)
9. [无障碍(Accessibility)差异](#9-无障碍accessibility差异)
10. [剪贴板(Pasteboard)差异](#10-剪贴板pasteboard差异)
11. [窗口管理(Window Management)差异](#11-窗口管理window-management差异)
12. [输入法(Input Method)差异](#12-输入法input-method差异)
13. [新增类详解](#13-新增类详解)
14. [内部架构重构](#14-内部架构重构)
15. [版本切换/迁移指南](#15-版本切换迁移指南)

---

## 1. 总体概览

| 维度 | 5.12.12 | 5.15.16 |
|------|---------|---------|
| Qt 基线版本 | Qt 5.12.12 | Qt 5.15.16 |
| Git 分支 | `tqtc/harmonyos-5.12.12` | `tqtc/harmonyos-5.15.16` |
| 换行符 | **CRLF** (Windows 风格) | **LF** (Unix 风格) |
| 模块版本 | 硬编码 `MODULE_VERSION = 5.12.12` | 动态 `MODULE_VERSION = $$[QT_VERSION]` |
| N-API 集成方式 | `include(node-addon-api.pri)` + `-lace_napi.z` | `CONFIG += qnapi` (内置 qnapi 特性) |
| Optional 类型 | `QOhosOptional<T>` (自定义) | `nonstd::optional<T>` (optional-lite) |
| 枚举定义位置 | 分散在各文件内 | 统一集中到 `qohosqpaenums.h` |
| 设备信息 | 无独立模块 | 新增 `QOhosDeviceInfo` |
| 图标引擎 | `qohosimageformat` (像素格式转换) | `qohosiconengine` (QIconEngine 实现) |

### 文件变更统计

| 区域 | 仅 CRLF 差异 | 真实内容差异 | 新增文件 | 删除文件 |
|------|-------------|-------------|---------|---------|
| `qtohosextras/src` | 24 | 17 | 9 | 0 |
| `qtohosextras/include` | — | — | 6 | 0 |
| qtbase ohos QPA 插件 | 64 | 149 | 8 | 4 |
| qtohosextras/examples | — | — | 2 | 0 |

---

## 2. 构建系统差异

### 2.1 N-API 集成方式变更(关键)

**5.12.12** (`ohosextras.pro` / `ohos.pro`):
```qmake
include($$PWD/../../../qtbase/src/3rdparty/node-addon-api.pri)
```
平台插件还链接:
```qmake
LIBS += -lace_napi.z
```

**5.15.16** (`ohosextras.pro` / `ohos.pro`):
```qmake
CONFIG += qnapi
```
平台插件不再链接 `-lace_napi.z`，改为:
```qmake
LIBS += -lace_ndk.z    # 使用 ace_ndk 替代 ace_napi
include($$PWD/../../../3rdparty/optional-lite.pri)
```

> **迁移影响**: 自定义 `.pro` 文件若引用了 `node-addon-api.pri`，需改为 `CONFIG += qnapi`；若链接了 `-lace_napi.z` 需移除。

### 2.2 模块版本

**5.12.12** (`.qmake.conf`):
```qmake
MODULE_VERSION = 5.12.12
```

**5.15.16** (`.qmake.conf`):
```qmake
MODULE_VERSION = $$[QT_VERSION]
```

### 2.3 optional-lite 依赖

5.15.16 新增对 `optional-lite` 第三方库的依赖:
```qmake
include($$PWD/../../../3rdparty/optional-lite.pri)
```
引入 `<nonstd/optional.hpp>` 头文件，替代原有的 `QOhosOptional<T>`。

### 2.4 平台插件链接库差异

| 库 | 5.12.12 | 5.15.16 |
|----|---------|---------|
| `-lace_napi.z` | ✅ | ❌ (移除) |
| `-lace_ndk.z` | ✅ | ✅ |
| `-lhiappevent_ndk.z` | ✅ | ✅ |
| `-lhilog_ndk.z` | ✅ | ✅ |
| `-lEGL` | ✅ | ✅ |
| `-lnative_display_manager` | ✅ | ✅ |
| `-lnative_vsync` | ✅ | ✅ |
| `-lnative_window` | ✅ | ✅ |
| `-lnative_window_manager` | ✅ | ✅ |
| `-lohfileshare` | ✅ | ✅ |
| `-lohfileuri` | ✅ | ✅ |
| `-lohhicollie` | ✅ | ✅ |
| `-lohinput` | ✅ | ✅ |
| `-lpasteboard` | ✅ | ✅ |
| `-lpixelmap` | ✅ | ✅ |
| `-lqos` | ✅ | ✅ |
| `-ludmf` | ✅ | ✅ |
| `-lohinputmethod` | ✅ | ✅ |

### 2.5 headers.pri (syncqt 头文件注册)

5.15.16 在 `SYNCQT.HEADER_FILES` / `SYNCQT.PRIVATE_HEADER_FILES` / `SYNCQT.CLEAN_HEADER_FILES` 中新增:
- `qohosdistributeddataobject.h` (public)
- `qohosdragkeyframepolicy.h` (public)
- `qohoswindowmaximizeoptions.h` (public)
- `qohosdistributeddataobject_p.h` (private)
- `qohosdragkeyframepolicy_p.h` (private)
- `qohoswindowmaximizeoptions_p.h` (private)

### 2.6 configure / 许可协议

- 许可从 `LGPL21` 变为 `GPL-EXCEPT`
- Copyright 年份从 2015 更新为 2020
- `qt.pro` 和 `configure.json` 内容相同

---

## 3. 头文件差异

### 3.1 QtOhosExtras 模块新增公共头文件

| 头文件 | 类名 | 用途 |
|--------|------|------|
| `qohosdistributeddataobject.h` | `QOhosDistributedDataObject` | 分布式数据对象(跨设备数据同步) |
| `qohosdragkeyframepolicy.h` | `QOhosDragKeyFramePolicy` | 窗口拖拽关键帧策略 |
| `qohoswindowmaximizeoptions.h` | `QOhosWindowMaximizeOptions` | 窗口最大化选项 |

新增私有头文件:
- `qohosdistributeddataobject_p.h`
- `qohosdragkeyframepolicy_p.h`
- `qohoswindowmaximizeoptions_p.h`

### 3.2 平台插件(qtbase ohos QPA)头文件变更

#### 新增

| 头文件 | 用途 |
|--------|------|
| `qohosdeviceinfo_p.h` | 设备信息查询(设备类型/型号/SDK版本等) |
| `qohosiconengine.h` | QIconEngine 工厂函数 `tryCreateQOhosIconEngine()` |
| `qohosqpaenums.h` | **所有** OHOS 枚举的统一定义(替代分散定义) |
| `qohosdragkeyframepolicy.h` | 拖拽关键帧策略(平台侧) |
| `qohoswindowmaximizeoptions.h` | 最大化选项(平台侧) |
| `doc/jsscopedata.md` | JsScopeData 设计模式文档 |

#### 重命名

| 5.12.12 | 5.15.16 | 说明 |
|----------|---------|------|
| `qohosenums.h` | `qohosqpaenums.h` | 枚举集中化，命名空间从 `QtOhos::enums` 改为 `QtOhosQpa::enums` |
| `qohosimageformat.h` | `qohosiconengine.h` | 从像素格式转换改为图标引擎 |

#### 删除

| 头文件 | 说明 |
|--------|------|
| `qohospointerstyle.h` | `QOhosPointerStyle` 枚举合并到 `qohosqpaenums.h` 中 `ohos::multimodalInput::pointer::PointerStyle` |

---

## 4. 公共 API 接口差异(QtOhosExtras 模块)

> 以下为 `qtohosextras/src/ohosextras/` 中有真实内容差异的头文件。
> 其余头文件(如 `qohosenums.h`、`qohosapppermissions.h`、`qohosfileshare.h`、`qohossharekit.h` 等)内容相同，仅换行符从 CRLF 变为 LF。

### 4.1 qohosabilitycontext.h — 分布式数据对象支持

**新增 include:**
```cpp
#include <QtOhosExtras/qohosdistributeddataobject.h>
```

**`QOhosOnContinueContext` 新增方法:**
```cpp
// 设置跨设备迁移时分布式数据对象的保存结果回调
virtual void setResponseOnDistributedDataObjectsSaveResults(
    const QList<QSharedPointer<QOhosDistributedDataObject>> &dataObjects,
    QObject *saveResultsHandlerContext,
    std::function<void(QList<bool>)> saveResultsHandler) = 0;

// 获取目标设备 ID
virtual QString targetDeviceId() const = 0;
```

**新增自由函数:**
```cpp
// 从 Want 恢复跨设备迁移的分布式数据对象
Q_OHOS_EXTRAS_EXPORT QList<QSharedPointer<QOhosDistributedDataObject>>
    tryRestoreOnContinueDistributedDataObjects(const QOhosWant &want);
```

### 4.2 qohoswindowutils.h — 窗口拖拽关键帧 & 最大化选项

**新增 include:**
```cpp
#include <QtOhosExtras/qohosdragkeyframepolicy.h>
#include <QtOhosExtras/qohoswindowmaximizeoptions.h>
```

**新增函数(均有 QWindow* 和 QWidget* 两个重载):**
```cpp
// 拖拽关键帧策略
void enableWindowDragKeyFramePolicy(QWindow *window, const QOhosDragKeyFramePolicy &policy);
void enableWindowDragKeyFramePolicy(QWidget *widget, const QOhosDragKeyFramePolicy &policy);
void disableWindowDragKeyFramePolicy(QWindow *window);
void disableWindowDragKeyFramePolicy(QWidget *widget);

// 窗口最大化选项
void setWindowMaximizeOptions(QWindow *window, const QOhosWindowMaximizeOptions &options);
void setWindowMaximizeOptions(QWidget *widget, const QOhosWindowMaximizeOptions &options);
void clearWindowMaximizeOptions(QWindow *window);
void clearWindowMaximizeOptions(QWidget *widget);
```

### 4.3 .cpp 实现变更模式

所有有真实差异的 `.cpp` 文件主要变更:
1. `QOhosOptional` API 迁移: `.hasValue()` → `.has_value()`，`.valueOr(x)` → `.value_or(x)`，`makeQOhosOptional(x)` → `nonstd::make_optional(x)`，`makeEmptyQOhosOptional()` → `{}` / `nonstd::nullopt`
2. `QOhosOptional::andThen(f)` → `qAndThen(opt, f)` (辅助函数形式)
3. 文档补充(如 `ShareAbilityType` 枚举文档、`LaunchReason` 文档、`isPermissionGranted(QString)` 文档等)

---

## 5. 平台插件 API 差异(qtbase ohos QPA)

### 5.1 qohosqpaenums.h — 枚举统一化(最重要变更)

5.12.12 的 `qohosenums.h` 仅定义少量枚举(258 行)。5.15.16 的 `qohosqpaenums.h` 大幅扩展(907 行)，将原本分散在 `qohospointerstyle.h`、`render/qohoswindowproxy.h`、`qohossharekit.h`、`qohosdisplayinfo.h` 等文件中的枚举全部集中。

**命名空间变更:**
```
QtOhos::enums  →  QtOhosQpa::enums
```

**新增枚举类别:**

| 命名空间 | 枚举 | 说明 |
|----------|------|------|
| `kit::ShareKit::systemShare` | `SelectionMode`, `ShareAbilityType`, `SharePreviewMode` | 系统分享(从 qohossharekit.h 移入) |
| `ohos::app::ability::AbilityConstant` | `OnContinueResult`(新增), `LaunchReason`, `ContinueState`, `WindowMode` | Ability 常量 |
| `ohos::app::ability::ConfigurationConstant` | `ColorMode` | 颜色模式 |
| `ohos::app::ability::contextConstant` | `ProcessMode`(**新增 ATTACH_TO_STATUS_BAR_ITEM**), `StartupVisibility` | 进程模式 |
| `ohos::app::ability::wantConstant` | `Flags`(**新增**) | Want 标志 |
| `ohos::bundle::bundleManager` | `SupportWindowMode` | 窗口模式支持 |
| `ohos::display` | `DisplaySourceMode`, `Orientation` | 显示(从 qohosdisplayinfo.h 移入) |
| `ohos::file::picker` | `DocumentSelectMode`(**新增**) | 文件选择器 |
| `ohos::inputMethod` | `Direction`, `EnterKeyType`, `RequestKeyboardReason`, `TextInputType`(**新增**) | 输入法 |
| `ohos::multimodalInput::pointer` | `PointerStyle`(**新增 SCREENRECORDER_CURSOR**, 共 46 项) | 鼠标指针样式(从 qohospointerstyle.h 移入) |
| `ohos::net::connection` | `NetBearType`, `NetCap`(**新增**) | 网络 |
| `ohos::notificationManager` | `ContentType` | 通知内容类型 |
| `ohos::window` | `AnimationType`, `AvoidAreaType`, `MaximizePresentation`(**新增 FOLLOW_APP_IMMERSIVE_SETTING**), `ModalityType`, `RectChangeReason`, `WindowEventType`, `WindowStatusType` | 窗口(从 qohoswindowproxy.h 移入) |
| `Api26::ohos::window` | `AcrossDisplayPresentation`(**新增**) | API26 跨屏显示 |

**使用方式变更:**
```cpp
// 5.12.12 — 枚举定义在各文件内
QOhosWindowProxy::WindowEventType::WINDOW_SHOWN
QOhosShareKit::SelectionMode::SINGLE
QOhosDisplayInfo::JsDisplayOrientation::PORTRAIT

// 5.15.16 — 通过 using 别名引用集中定义
QOhosWindowProxy::WindowEventType::WINDOW_SHOWN  // using = QtOhosQpa::enums::ohos::window::WindowEventType
QOhosShareKit::SelectionMode                     // using = QtOhosQpa::enums::kit::ShareKit::systemShare::SelectionMode
QOhosDisplayInfo::JsDisplayOrientation            // using = QtOhosQpa::enums::ohos::display::Orientation
```

### 5.2 QOhosOptional → nonstd::optional (全局迁移)

这是最广泛的变化，影响 149+ 个文件:

| 5.12.12 (QOhosOptional) | 5.15.16 (nonstd::optional) |
|--------------------------|----------------------------|
| `QOhosOptional<T>` | `nonstd::optional<T>` |
| `.hasValue()` | `.has_value()` |
| `.valueOr(default)` | `.value_or(default)` |
| `.value()` | `.value()` 或 `*opt` |
| `makeQOhosOptional(x)` | `nonstd::make_optional(x)` |
| `makeEmptyQOhosOptional()` | `{}` / `nonstd::nullopt` |
| `#include <QtCore/private/qohoscommon_p.h>` (间接) | `#include <nonstd/optional.hpp>` |

### 5.3 qohosplugincore.h — 核心接口变更

```cpp
// Optional 类型变更
QOhosOptional<QNapi::Promise> → nonstd::optional<QNapi::Promise>
QOhosOptional<QNapi::Object> → nonstd::optional<QNapi::Object>
QOhosOptional<std::string>   → nonstd::optional<std::string>

// 新增方法
virtual void forceResolveQWindowDestroyPromiseIfPresent(Napi::Env env) = 0;

// 删除方法
// virtual void tagWidgetOrWindowAsFloatWindow(QObject *, bool) = 0;  // 已移除
// virtual QNapi::Object getModule(const std::string &) = 0;           // 已移除(标记为 QT_DEPRECATED)
// virtual QOhosOptional<QNapi::Object> optAppLaunchParam() = 0;      // 已移除
// virtual void startAppProcess(...) 旧重载                          // 已移除
// virtual void addNewWantConsumer(...) = 0;                          // 已移除

// startNewQAbilityInstance 参数变更
// 5.12: std::shared_ptr<QAbilityPeer> baseQAbilityPeer
// 5.15: QNapi::Object baseQAbility

// 超时类型变更
std::chrono::milliseconds timeout → std::chrono::nanoseconds timeout

// 类型别名
QOhosAbilityOnContinueResult → using = QtOhosQpa::enums::ohos::app::ability::AbilityConstant::OnContinueResult
```

### 5.4 qohosdisplayinfo.h — 显示信息

```cpp
// 枚举移除(改为 using 引用 qohosqpaenums.h)
enum class JsDisplayOrientation { ... } → using JsDisplayOrientation = QtOhosQpa::enums::ohos::display::Orientation;
enum class DisplaySourceMode { ... }     → using DisplaySourceMode = QtOhosQpa::enums::ohos::display::DisplaySourceMode;

// 新增字段
uint refreshRate;  // 刷新率

// Optional 变更
QOhosOptional<QNapi::Object> tryGetDisplayById(...) → nonstd::optional<QNapi::Object>
QOhosOptional<JsDisplayOrientation> orientation     → nonstd::optional<JsDisplayOrientation>
QOhosOptional<DisplaySourceMode> sourceMode            → nonstd::optional<DisplaySourceMode>
QOhosOptional<QPoint> topLeftOffsetPixels             → nonstd::optional<QPoint>
```

### 5.5 qohoswindowproperty.h — 窗口属性

```cpp
// 新增
void clearQOhosPropertyOnQObject(QObject *qObject);  // 清除属性
bool hasLiveConsumers() const;                        // 检查是否有活跃消费者

// 属性描述符变更
constexpr QOhosPropertyDescriptor()                  → explicit QOhosPropertyDescriptor(const char *name)
                                                        const char *name() const;  // 新增

// 属性名生成方式变更
// 5.12: 运行时 printfToString("_q_platform_ohos_%d_%p", ...) 生成名称
// 5.15: 直接使用 propertyPtr->name() (编译期确定)

// Optional 变更
QOhosOptional<T> tryGetQOhosPropertyFromQObject(...) → nonstd::optional<T>
QOhosOptional<T> tryGetProperty()                     → nonstd::optional<T>
```

### 5.6 qohosscreenmanager.h — 屏幕管理

```cpp
// 头文件规范化
#include <QObject> → #include <QtCore/qobject.h>
#include <QPointer> → #include <QtCore/qpointer.h>

// 移除依赖
// #include <qohosplugincore.h>  // 已移除

// Optional 变更
QOhosOptional<QOhosDisplayInfo> displayInfoOrEmpty() → nonstd::optional<QOhosDisplayInfo>
QOhosOptional<JsDisplayId> displayIdOrEmpty()         → nonstd::optional<JsDisplayId>
```

### 5.7 qohosplatformscreen.h — 平台屏幕

```cpp
// 新增
qreal refreshRate() const override;  // 刷新率
mutable nonstd::optional<Qt::ScreenOrientation> m_nativeOrientation;  // 原生方向缓存

// 头文件规范化
#include <QList> → #include <QtCore/qlist.h>
#include <QPainter> → #include <QtGui/qpainter.h>
#include <QTimer> → #include <QtCore/qtimer.h>
#include <QWaitCondition> → #include <QtCore/qwaitcondition.h>
```

### 5.8 qohosplatformtheme.h — 平台主题

```cpp
// 新增
QIconEngine *createIconEngine(const QString &iconName) const override;  // 图标引擎创建
```

### 5.9 qohossettings.h — 设置(重构为单例)

```cpp
// 5.12.12 — 命名空间 + 自由函数
namespace QOhosSettings {
    double fontSizeScale();
    bool isWindowPcModeEnabled();
}

// 5.15.16 — 单例类
class QOhosSettings {
public:
    static QOhosSettings &instance();
    std::shared_ptr<void> installSettingsCache();  // 新增: 设置缓存
    double fontSizeScale() const;
    bool isWindowPcModeEnabled() const;
private:
    QOhosSettings();
    QOhosSupplier<bool> m_windowPcModeEnabled;
};
```

### 5.10 qohosplatformintegration.h — 平台集成

```cpp
// 新增
std::shared_ptr<void> m_settingsCacheHandle;  // 设置缓存句柄

// 头文件规范化
#include <QTouchDevice> → #include <QtGui/qtouchdevice.h>
```

### 5.11 qohospixelmapconversions.h — 像素图转换

```cpp
// 移除
// std::shared_ptr<::OH_PixelmapNative> createNativePixelMapFromQImage(QImage);
// std::shared_ptr<::OH_PixelmapNative> makeEmptyNativePixelMap();
// std::shared_ptr<::OH_PixelmapNative> wrapNativePixelMapPtr(::OH_PixelmapNative *);
// QNapi::Object createNapiPixelMapFromQImage(...);

// 重命名
makeEmptyNativePixelMap() → makeEmptyOhosNativePixelMap()  // 在 qohosudsobject.h 中调用

// 变更
QNapi::Object createNapiPixelMapFromQImage(...) → QNapi::Object makeDisplayDensityScaledJsPixelMapFromQImage(...)

// 头文件依赖变更
// #include <qohosimageformat.h>  → 已移除(改用 QtGui/private/qohosimageconversions_p.h)
```

### 5.12 qohosplatformservices.h — 平台服务

```cpp
// 移除静态方法
// static std::string mapPathToOhosUriInJsThread(const std::string &path);
// static std::string mapOhosFileUriToPathInJsThread(const std::string &ohosFileUri);
```

### 5.13 qohosfloatingwindow.h — 浮动窗口

```cpp
// 方法签名变更
bool startSystemMove(const QPoint &pos) → bool startSystemMove()  // 不再需要位置参数

// 新增窗口事件处理方法
void handleWindowEvent(QOhosWindowProxy::WindowEvent evt);
void handleWindowStatusChange(QOhosWindowProxy::WindowStatus evt);
void handleWindowVisibilityChange(bool visible);
void handleAvoidAreaChanged(QOhosWindowProxy::AvoidAreaType, const QOhosWindowProxy::AvoidArea &);
void updateSafeAreaMargins();
void handleWindowRectChanged(const QOhosWindowProxy::RectChangeOptions &);
void handleSurfaceStatusChanged(const nonstd::optional<QSize> &);
void handleWindowDisplayIdChanged(QOhosDisplayInfo::JsDisplayId);

// 新增成员
nonstd::optional<QOhosWindowProxy::WindowEvent> m_activationEventDeferredUntilWindowUnblocked;
QMap<QOhosWindowProxy::AvoidAreaType, QOhosWindowProxy::AvoidArea> m_avoidAreaCache;
```

### 5.14 qohosdeviceinfo_p.h — 设备信息(新增)

```cpp
namespace QOhosDeviceInfo {
    enum class Type { deviceType, manufacture, brand, marketName, /* ... 30+ 属性 */ };
    enum class RecognizedDeviceType { _2in1, tablet, phone };

    void init(QMap<Type, QVariant> devinfo);
    QVariant getProperty(Type prop);
    nonstd::optional<RecognizedDeviceType> tryGetRecognizedDeviceType();
    bool isTablet();
    bool is2in1();
    bool isPhone();
    int sdkApiVersion();
    bool isCurrentDeviceSupported();
}
```

### 5.15 render/qohoswindowproxy.h — 窗口代理

```cpp
// 枚举变更: 本地枚举改为 using 引用
enum class WindowEventType { ... } → using WindowEventType = QtOhosQpa::enums::ohos::window::WindowEventType;
enum class WindowStatusType { ... } → using WindowStatusType = QtOhosQpa::enums::ohos::window::WindowStatusType;
enum class AvoidAreaType { ... }   → using AvoidAreaType = QtOhosQpa::enums::ohos::window::AvoidAreaType;
enum class RectChangeReason { ... } → using RectChangeReason = QtOhosQpa::enums::ohos::window::RectChangeReason;
enum class MaximizePresentation { ... } → using MaximizePresentation = QtOhosQpa::enums::ohos::window::MaximizePresentation;
enum class ModalityType { ... }   → using ModalityType = QtOhosQpa::enums::ohos::window::ModalityType;

// MaximizePresentation 新增值
ENTER_IMMERSIVE_DISABLE_TITLE_AND_DOCK_HOVER  // 5.12 无此值

// 新增方法
void setDragKeyFramePolicy(const QtOhos::QOhosKeyFramePolicy &policy);
void maximize(const QtOhos::QOhosWindowMaximizeOptions &options);  // 签名变更
QList<QRect> getDisplayCutoutRects() const;                          // 新增: 获取屏幕挖孔区域
void shiftAppWindowFocus(QOhosWindowProxy &targetProxy);            // 新增: 切换窗口焦点

// maximize 签名变更
void maximize(MaximizePresentation maximizePresentation)  // 5.12
void maximize(const QtOhos::QOhosWindowMaximizeOptions &options)  // 5.15

// 触摸事件结构变更
struct NonClientAreaTouchEvent {
    std::int32_t id;
    std::chrono::milliseconds timestamp;
    Qt::TouchPointState state;    // 5.12
    QEvent::Type action;           // 5.15 (变更)
    QPointF displayPosition;
    QPointF localPosition;         // 新增
    QPointF globalPosition;
};

// JsScopeData 构造变更
JsScopeData(..., std::shared_ptr<QtOhos::QAbilityPeer> qAbilityPeer);  // 5.12
JsScopeData(..., std::shared_ptr<QtOhos::QAbilityPeer> qAbilityPeer,
            QtOhos::QObjectThreadSafeRef owningQWindowRef);              // 5.15 (新增参数)

// Optional 变更(全部)
QOhosOptional<double> → nonstd::optional<double>
QOhosOptional<QOhosDisplayInfo::JsDisplayId> → nonstd::optional<...>
QOhosOptional<QSize> → nonstd::optional<QSize>
QOhosOptional<bool> → nonstd::optional<bool>
```

---

## 6. 权限(Permissions)差异

### 6.1 公共 API (qtohosextras)

`qohosapppermissions.h` 和 `qohosapppermissionsutils_p.h` 内容**相同**(仅 CRLF→LF)。

`qohosappcontext.cpp` 中文档变更:
- **移除** `AppPermission` 枚举的文档(枚举本身未变，仅文档位置调整)
- **新增** `isPermissionGranted(const QString &permissionName)` 的文档

### 6.2 平台插件 (qohosapppermissions_p.h)

权限请求函数签名变更:

```cpp
// 5.12.12 — 使用 QAbilityPeer 指针
void requestAppPermissionFromUser(
    QtOhos::JsState &jsState,
    std::shared_ptr<QtOhos::QAbilityPeer> abilityPeer,  // 旧
    const std::string &permissionName, ...);

// 5.15.16 — 使用 QNapi::Object
void requestAppPermissionFromUser(
    QtOhos::JsState &jsState,
    QNapi::Object qAbility,  // 新
    const std::string &permissionName, ...);
```

此变更影响 `requestAppPermissionFromUser`、`requestAppPermissionFromUserWithResult`、`requestAppPermissionOnSetting` 三个函数。

---

## 7. 文件分享(File Sharing / ShareKit / UDMF)差异

### 7.1 ShareKit (qtohosextras 公共层)

`qohossharekit.h` 内容**相同**(仅 CRLF→LF)。

`qohossharekit.cpp` 实现变更:
- 新增 `ShareAbilityType` 枚举文档
- `QOhosOptional` API 迁移为 `nonstd::optional`
- `.hasValue()` → `.has_value()`，`.valueOr()` → `.value_or()`

### 7.2 ShareKit (平台插件 qohossharekit.h)

```cpp
// 枚举定义方式变更: 本地定义 → using 引用
enum class SelectionMode { SINGLE, BATCH }              → using SelectionMode = QtOhosQpa::enums::kit::ShareKit::systemShare::SelectionMode;
enum class SharePreviewMode { DEFAULT, DETAIL }         → using SharePreviewMode = QtOhosQpa::enums::kit::ShareKit::systemShare::SharePreviewMode;
enum class ShareAbilityType { COPY_TO_PASTEBOARD, ... } → using ShareAbilityType = QtOhosQpa::enums::kit::ShareKit::systemShare::ShareAbilityType;

// 新增
#include <QtCore/qmap.h>

// Optional 变更
QOhosOptional<std::string> content → nonstd::optional<std::string> content
QOhosOptional<std::string> filePath → nonstd::optional<std::string> filePath
// ... 所有字段同理
QOhosOptional<ShareControllerAnchor> anchor → nonstd::optional<ShareControllerAnchor>
QOhosOptional<SelectionMode> selectionMode → nonstd::optional<SelectionMode>
```

### 7.3 UDMF (统一数据管理框架)

`qohosudmf.h`:
```cpp
QOhosOptional<QOhosSpan<const std::uint8_t>> tryGetGeneralEntry(...) → nonstd::optional<...>
```

`qohosudmfconversions.h`:
```cpp
QOhosOptional<bool> shareInAppOnly → nonstd::optional<bool>
QOhosOptional<std::string> tryMapUtdTypeIdToMimeType(...) → nonstd::optional<std::string>
QOhosOptional<std::string> tryMapMimeTypeToUtdTypeId(...) → nonstd::optional<std::string>
```

`qohosudsobject.h`:
```cpp
// 头文件依赖变更
#include <qohospixelmapconversions.h> → #include <QtGui/private/qohosimageconversions_p.h>

// 函数重命名
makeEmptyNativePixelMap() → makeEmptyOhosNativePixelMap()
```

### 7.4 文件分享 (qohosfileshare.cpp)

```cpp
// Optional API 迁移
optInternalValue.hasValue() → optInternalValue.has_value()
optInternalValue.value()    → optInternalValue.value()

// 链式操作变更
policyErrorResult.error.andThen(tryMap...).valueOr(...)           // 5.12
qAndThen(policyErrorResult.error, tryMap...).value_or(...)       // 5.15
```

---

## 8. 主题(Theme / ColorMode)差异

### 8.1 qohosplatformtheme

```cpp
// 新增图标引擎创建
QIconEngine *createIconEngine(const QString &iconName) const override;
```

`qohosplatformtheme.cpp`:
- 新增 `tryCreateQOhosIconEngine` 调用(替代旧的 `qohosimageformat` 像素格式转换)

### 8.2 ColorMode 枚举

`ColorMode` 枚举定义不变，但从 `qohosenums.h` 移到 `qohosqpaenums.h`:
```
QtOhos::enums::ohos::app::ability::ConfigurationConstant::ColorMode
→ QtOhosQpa::enums::ohos::app::ability::ConfigurationConstant::ColorMode
```

### 8.3 暗色主题

`qohosappcontext.cpp` 中:
```cpp
// Optional API 迁移
darkModeFlag.valueOr(darkModeFlagDefault) → darkModeFlag.value_or(darkModeFlagDefault)
m_ohosConfigDarkModeFlagSupplier().valueOr(darkModeFlagDefault) → .value_or(darkModeFlagDefault)
```

暗色主题的 `setDarkThemeEnabled` / `darkThemeActiveChanged` 信号机制本身不变。

### 8.4 设置系统重构

`qohossettings.h` 从命名空间重构为单例类:
- 新增 `installSettingsCache()` 用于设置缓存
- `fontSizeScale()` / `isWindowPcModeEnabled()` 变为 const 成员方法
- `qohosplatformintegration.h` 新增 `m_settingsCacheHandle` 成员

---

## 9. 无障碍(Accessibility)差异

### 9.1 新增事件类型

```cpp
// qohosaccessibilitytree.h
enum class AccessibilityEvent {
    // ...
    ElementTextUpdated,  // 新增: 文本更新事件
    // ...
};

// qohosaccessibleeventsconsumer.h
virtual void notifyInterfaceTextChanged(QAccessible::Id interfaceId) = 0;  // 新增: 文本变更通知
```

### 9.2 Optional 迁移

```cpp
// qohosaccessibilitytree.h
QOhosOptional<std::pair<std::string, std::string>> minMaxRange → nonstd::optional<...>
QOhosOptional<Id> parentId → nonstd::optional<Id>

// qohosaccessibilityarkuihelpers.h
QOhosOptional<AccessibilityNode::Id> tryMapOhosElementIdToNodeId(...) → nonstd::optional<...>
QOhosOptional<AccessibilityNode::Id> tryMapNumericIdToValidNodeId(...) → nonstd::optional<...>

// qohosaccessibilitytreeeventsconsumercommand.h
QOhosOptional<AccessibilityEvent> getOptEventType() → nonstd::optional<...>
QOhosOptional<AccessibilityWindowEvent> getOptWindowEventType() → nonstd::optional<...>
```

### 9.3 无障碍树查找

```cpp
// qohosaccessibilitytree.h
virtual QOhosOptional<std::pair<AccessibilityNode::Id, QXComponentRender>>
    tryFindNodeUpwardsWithXComponent(...) → nonstd::optional<...>
```

---

## 10. 剪贴板(Pasteboard)差异

### 10.1 qohosclipboardobject.h — 结构重构

```cpp
// Optional 迁移
QOhosOptional<PasteboardDataSource> dataSource → nonstd::optional<PasteboardDataSource>
QOhosOptional<bool> shareInAppOnly → nonstd::optional<bool>

// 新增 JsScopeData 结构(遵循 JsScopeData 设计模式)
struct JsScopeData {
    std::shared_ptr<::OH_Pasteboard> pasteboard;
    std::shared_ptr<void> pasteboardDataChangedListenerHandle;
};

// 成员变更
// 5.12: 直接持有
std::shared_ptr<::OH_Pasteboard> m_pasteboard;
std::shared_ptr<void> m_pasteboardDataChangedListenerHandle;

// 5.15: 通过 JsScopeData 持有(JS 线程安全销毁)
std::shared_ptr<QOhosConsumer<nonstd::optional<PasteboardDataSource>>> m_pasteboardUpdatesNotifier;
std::shared_ptr<JsScopeData> m_jsScopeData;
```

### 10.2 qohosplatformclipboard.h

```cpp
QOhosOptional<bool> &shareInAppOnlyFlagRef() → nonstd::optional<bool> &shareInAppOnlyFlagRef()
```

### 10.3 qohospasteboard.cpp (qtohosextras)

文档微调:
```cpp
\brief The QOhosPasteboard class is to manage native pasteboard.
→ \brief The QOhosPasteboard namespace provides functions to manage the native pasteboard.
```

---

## 11. 窗口管理(Window Management)差异

### 11.1 最大化选项(新功能)

5.15.16 新增 `QOhosWindowMaximizeOptions`:
```cpp
enum class MaximizePresentation {
    EnterImmersive,
    EnterImmersiveDisableTitleAndDockHover,  // 新增
    ExitImmersive,
    FollowAppImmersiveSetting,
};

enum class AcrossDisplayPresentation {  // 全新
    EnterAcrossDisplayMode,
    ExitAcrossDisplayMode,
    FollowAcrossDisplaySetting,
};

// 工厂函数
QSharedPointer<QOhosWindowMaximizeOptions> createWindowMaximizeOptions();
```

### 11.2 拖拽关键帧策略(新功能)

5.15.16 新增 `QOhosDragKeyFramePolicy`:
```cpp
void setInterval(std::chrono::milliseconds interval);
void setDistance(int distancePx);
void setAnimationDuration(std::chrono::milliseconds animationDuration);
void setAnimationDelay(std::chrono::milliseconds animationDelay);

// 工厂函数
QSharedPointer<QOhosDragKeyFramePolicy> createDragKeyFramePolicy();
```

### 11.3 窗口代理签名变更

```cpp
// maximize 签名变更
void maximize(MaximizePresentation)                          → void maximize(const QOhosWindowMaximizeOptions &)

// startSystemMove 签名变更(floatingwindow)
bool startSystemMove(const QPoint &pos)                      → bool startSystemMove()

// 新增
void setDragKeyFramePolicy(const QtOhos::QOhosKeyFramePolicy &policy);
QList<QRect> getDisplayCutoutRects() const;                   // 屏幕挖孔区域
void shiftAppWindowFocus(QOhosWindowProxy &targetProxy);      // 窗口焦点切换
```

### 11.4 窗口属性系统

```cpp
// 新增
void clearQOhosPropertyOnQObject(QObject *);  // 清除属性
bool hasLiveConsumers() const;                  // 检查活跃消费者
const char *name() const;                       // 属性描述符名称

// 属性名生成变更
// 5.12: 运行时生成 "_q_platform_ohos_%d_%p"
// 5.15: 编译期 propertyPtr->name()
```

---

## 12. 输入法(Input Method)差异

### 12.1 qohosinputmethodproxy.h — 预览文本回调变更

```cpp
// onInsertPreviewText 回调签名变更(新增 start/end 参数)
virtual void onInsertPreviewText(std::string text)                                    // 5.12
virtual void onInsertPreviewText(std::string text, int start, int end)               // 5.15

// 新增方法
void notifySelectionChange(std::u16string text, int start, int end);
void setTextAroundCursor(std::u16string leftText, std::u16string rightText, int cursorIndex);

// 新增内部结构
struct TextAroundCursor {
    std::u16string leftText;
    std::u16string rightText;
    int cursorIndex = 0;
};
std::shared_ptr<QOhosMutexProtectedValue<TextAroundCursor>> m_textAroundCursor;  // 新增成员

// registerCallbacks 新增参数
std::shared_ptr<QOhosMutexProtectedValue<TextAroundCursor>> textAroundCursor  // 新增
```

### 12.2 qohosinputmethodeventhandler.h — 焦点事件

```cpp
// 新增焦点事件结构
struct QOhosFocusEvent {
    QPointer<QWindow> targetWindow;
    bool isFocus = false;
};

// 新增方法
void onFocusEvent(const QOhosFocusEvent &focusEvent);
void requestActivationOnPressIfNeeded(QWindow *pressTargetWindow);

// 新增成员
QPointer<QWindow> m_pendingActivationWindow;
nonstd::optional<std::int32_t> m_optNonClientAreaTouchPointerId;

// Optional 迁移
QOhosOptional<QPoint> singleTouchPointEventGlobalPosition → nonstd::optional<QPoint>
QOhosOptional<std::pair<QWindow*, std::uint64_t>> getLastTouchedWindowWithSeqNoIfPresent() → nonstd::optional<...>
QOhosOptional<QOhosMouseEvent> m_lastWsiMouseEvent → nonstd::optional<...>
QOhosOptional<QWindowSystemInterfaceTouchEvent> m_lastWsiTouchEvent → nonstd::optional<...>
```

### 12.3 输入法枚举

新增输入法相关枚举到 `qohosqpaenums.h`:
- `ohos::inputMethod::Direction`
- `ohos::inputMethod::EnterKeyType`
- `ohos::inputMethod::RequestKeyboardReason` (新增)
- `ohos::inputMethod::TextInputType`

---

## 13. 新增类详解

### 13.1 QOhosDistributedDataObject (分布式数据对象)

**头文件:** `QtOhosExtras/qohosdistributeddataobject.h`
**命名空间:** `QtOhosExtras`

```cpp
class Q_OHOS_EXTRAS_EXPORT QOhosDistributedDataObject : public QObject {
    Q_OBJECT
public:
    enum class Status { Online, Offline, Restored };

    // 工厂创建(从 JSON 配置)
    static QSharedPointer<QOhosDistributedDataObject> create(const QJsonObject &source);

    // 数据访问
    virtual QJsonValue get(const QString &key) const = 0;
    virtual QStringList fieldNames() const = 0;

    // 资产管理
    virtual void addAssets(const QList<QSharedPointer<QFile>> &files) = 0;
    virtual QString assetKey() const = 0;
    virtual QJsonArray assets() const = 0;
    virtual bool areAssetsSynced() const = 0;

    virtual QString sessionId() const = 0;
    virtual void save(const QString &deviceId) = 0;

Q_SIGNALS:
    void dataChanged(QString sessionId, QStringList changedFields);
    void statusChanged(QString sessionId, QString networkId, Status status);
    void progressChanged(QString sessionId, int progress);
    void saveFinished(bool success);
};
```

**使用场景:** 跨设备迁移时同步分布式数据对象，通过 `QOhosOnContinueContext::setResponseOnDistributedDataObjectsSaveResults` 在迁移回调中处理。

### 13.2 QOhosDragKeyFramePolicy (拖拽关键帧策略)

**头文件:** `QtOhosExtras/qohosdragkeyframepolicy.h`
**命名空间:** `QtOhosExtras`

```cpp
class Q_OHOS_EXTRAS_EXPORT QOhosDragKeyFramePolicy {
public:
    virtual void setInterval(std::chrono::milliseconds interval) = 0;
    virtual void setDistance(int distancePx) = 0;
    virtual void setAnimationDuration(std::chrono::milliseconds animationDuration) = 0;
    virtual void setAnimationDelay(std::chrono::milliseconds animationDelay) = 0;
};

QSharedPointer<QOhosDragKeyFramePolicy> createDragKeyFramePolicy();
```

**使用方式:**
```cpp
auto policy = QtOhosExtras::createDragKeyFramePolicy();
policy->setInterval(std::chrono::milliseconds(16));
policy->setDistance(8);
QtOhosExtras::enableWindowDragKeyFramePolicy(window, *policy);
```

### 13.3 QOhosWindowMaximizeOptions (窗口最大化选项)

**头文件:** `QtOhosExtras/qohoswindowmaximizeoptions.h`
**命名空间:** `QtOhosExtras`

```cpp
enum class MaximizePresentation {
    EnterImmersive,
    EnterImmersiveDisableTitleAndDockHover,
    ExitImmersive,
    FollowAppImmersiveSetting,
};

enum class AcrossDisplayPresentation {
    EnterAcrossDisplayMode,
    ExitAcrossDisplayMode,
    FollowAcrossDisplaySetting,
};

class Q_OHOS_EXTRAS_EXPORT QOhosWindowMaximizeOptions {
public:
    virtual void setMaximizePresentation(MaximizePresentation) = 0;
    virtual void setAcrossDisplayPresentation(AcrossDisplayPresentation) = 0;
    virtual void setSnapshotAnimationDuration(std::chrono::milliseconds duration) = 0;
    virtual void setSnapshotAnimationDelay(std::chrono::milliseconds delay) = 0;
};

QSharedPointer<QOhosWindowMaximizeOptions> createWindowMaximizeOptions();
```

**使用方式:**
```cpp
auto opts = QtOhosExtras::createWindowMaximizeOptions();
opts->setMaximizePresentation(QtOhosExtras::MaximizePresentation::EnterImmersive);
QtOhosExtras::setWindowMaximizeOptions(window, *opts);
```

---

## 14. 内部架构重构

### 14.1 JsScopeData 设计模式(新增)

5.15.16 引入 `JsScopeData` 设计模式，用于解决 Qt 线程与 JS 线程的资源生命周期冲突。

**核心思想:** 将所有 JS 线程相关状态(JS 对象引用、监听器句柄)打包到 `struct JsScopeData`，通过 `shared_ptr` + JS 线程删除器管理生命周期。

**文档位置:** `qtbase/src/plugins/platforms/ohos/doc/jsscopedata.md`

**已应用该模式的类:**
- `QOhosClipboardObject` (剪贴板对象)
- 其他涉及 JS 线程状态的类

**规则:**
1. 严格分区: JS 线程状态放入 `JsScopeData`，Qt 线程状态放在类成员中
2. `m_jsScopeData->...` 表示 JS 线程状态，`m_xxx` 表示 Qt 线程状态
3. 只在 JS 线程闭包(`runInJsThreadAndWait`、`evalInJsThread`)中访问 `JsScopeData` 内容

### 14.2 枚举集中化

所有 OHOS 枚举统一到 `qohosqpaenums.h`，通过 `using` 别名在各模块中引用:
- 消除了重复定义
- 统一了 `OhosEnumMeta` 模板特化
- 为所有枚举添加 `Q_DECLARE_METATYPE`
- 新增 `Api26` 命名空间区分不同 API 级别的枚举

### 14.3 头文件 include 规范化

全局将 Qt 模块化 include 改为全路径 include:
```cpp
// 5.12                           // 5.15
#include <QObject>            →    #include <QtCore/qobject.h>
#include <QPointer>          →    #include <QtCore/qpointer.h>
#include <QList>             →    #include <QtCore/qlist.h>
#include <QPainter>          →    #include <QtGui/qpainter.h>
#include <QTimer>            →    #include <QtCore/qtimer.h>
#include <QWaitCondition>    →    #include <QtCore/qwaitcondition.h>
#include <QAtomicInt>        →    #include <QtCore/qatomic.h>
#include <QOpenGLPaintDevice>→   #include <QtGui/qopenglpaintdevice.h>
#include <QOpenGLContext>    →    #include <QtGui/qopenglcontext.h>
#include <QScopedPointer>    →    #include <QtCore/qscopedpointer.h>
#include <QTouchDevice>      →    #include <QtGui/qtouchdevice.h>
#include <QtCore/QtGlobal>   →    #include <QtCore/qglobal.h>
#include <QtCore/QSizeF>     →    #include <QtCore/qsize.h>
```

### 14.4 超时类型精确化

```cpp
std::chrono::milliseconds timeout → std::chrono::nanoseconds timeout
```
影响 `tryInvokeInQtThreadAndTryWaitForContinue` 和 `tryInvokeInMasterThreadAndTryWaitForContinue`。

### 14.5 代码风格调整

- 移除单行 `if` 语句的 `{}` 大括号(部分文件)
- 移除不必要的 `#include <utility>`

---

## 15. 版本切换/迁移指南

### 15.1 从 5.12.12 迁移到 5.15.16

#### Step 1: 构建系统

1. `.qmake.conf` 中 `MODULE_VERSION` 改为 `$$[QT_VERSION]`
2. `.pro` 文件中:
   - `include(.../node-addon-api.pri)` → `CONFIG += qnapi`
   - 移除 `LIBS += -lace_napi.z`
   - 添加 `include(.../optional-lite.pri)` (如使用 nonstd::optional)

#### Step 2: 头文件 include

1. `#include <qohosenums.h>` → `#include <qohosqpaenums.h>`
2. `#include <qohosimageformat.h>` → `#include <qohosiconengine.h>` (功能不同)
3. `#include <qohospointerstyle.h>` → 移除(合并到 `qohosqpaenums.h`)
4. `#include <qohospixelmapconversions.h>` 中引用的 `qohosimageformat.h` → `QtGui/private/qohosimageconversions_p.h`
5. 将所有 `#include <QObject>` 等 → 全路径形式

#### Step 3: Optional 类型迁移

全局替换:
```
QOhosOptional<T>           → nonstd::optional<T>
.hasValue()                → .has_value()
.valueOr(x)                → .value_or(x)
makeQOhosOptional(x)       → nonstd::make_optional(x)
makeEmptyQOhosOptional()   → nonstd::nullopt 或 {}
opt.andThen(f)             → qAndThen(opt, f)
```

#### Step 4: 枚举引用

```cpp
// 命名空间变更
QtOhos::enums::xxx → QtOhosQpa::enums::xxx

// 如使用本地定义的枚举，改为 using 引用
// 例如 qohossharekit.h 中的 SelectionMode 等
```

#### Step 5: 权限请求 API

```cpp
// 5.12 — 传 QAbilityPeer 指针
requestAppPermissionFromUser(jsState, abilityPeer, permissionName, ...);

// 5.15 — 传 QNapi::Object
requestAppPermissionFromUser(jsState, qAbility, permissionName, ...);
```

#### Step 6: 窗口管理 API

```cpp
// maximize 变更
window->maximize(MaximizePresentation::ENTER_IMMERSIVE);  // 5.12
auto opts = createWindowMaximizeOptions();                 // 5.15
opts->setMaximizePresentation(...);
setWindowMaximizeOptions(window, *opts);

// startSystemMove 变更
floatingWindow->startSystemMove(pos);  // 5.12
floatingWindow->startSystemMove();     // 5.15

// 新增功能可用
enableWindowDragKeyFramePolicy(window, *policy);  // 5.15 新增
```

#### Step 7: 输入法回调

```cpp
// onInsertPreviewText 签名变更
void onInsertPreviewText(std::string text)                            // 5.12
void onInsertPreviewText(std::string text, int start, int end)       // 5.15
```

#### Step 8: JsScopeData 模式(平台插件开发)

如开发新的平台插件类，遵循 `doc/jsscopedata.md` 中的 JsScopeData 模式管理 JS 线程资源。

### 15.2 从 5.15.16 回退到 5.12.12

1. `CONFIG += qnapi` → `include(.../node-addon-api.pri)`
2. 添加 `LIBS += -lace_napi.z`
3. `nonstd::optional` → `QOhosOptional`
4. `qohosqpaenums.h` → `qohosenums.h` + 各文件内枚举
5. `qohosiconengine` → `qohosimageformat`
6. 恢复 `QAbilityPeer` 参数形式的权限 API
7. `maximize(QOhosWindowMaximizeOptions)` → `maximize(MaximizePresentation)`
8. `startSystemMove()` → `startSystemMove(pos)`
9. 移除 JsScopeData 模式(直接持有 JS 资源)
10. 全路径 include → 模块化 include

### 15.3 迁移检查清单

- [ ] `.qmake.conf` MODULE_VERSION
- [ ] `.pro` 文件 N-API 集成方式
- [ ] `.pro` 文件 LIBS 链接库
- [ ] `QOhosOptional` → `nonstd::optional` 全局替换
- [ ] `qohosenums.h` → `qohosqpaenums.h`
- [ ] `qohosimageformat` → `qohosiconengine`
- [ ] `qohospointerstyle.h` → `qohosqpaenums.h`
- [ ] 枚举命名空间 `QtOhos::` → `QtOhosQpa::`
- [ ] 权限 API 参数 `QAbilityPeer` → `QNapi::Object`
- [ ] `maximize` 签名
- [ ] `startSystemMove` 签名
- [ ] 输入法 `onInsertPreviewText` 签名
- [ ] 新增 API(分布式数据对象/拖拽关键帧/最大化选项)的条件编译
- [ ] include 路径规范化
- [ ] 超时类型 `milliseconds` → `nanoseconds`
- [ ] `QOhosSettings` 命名空间 → 单例类
- [ ] `QOhosPlatformServices` 移除的路径映射方法
- [ ] `QOhosPluginCore` 移除的方法(getModule/optAppLaunchParam/tagWidgetOrWindowAsFloatWindow 等)
- [ ] `makeEmptyNativePixelMap` → `makeEmptyOhosNativePixelMap`
- [ ] JsScopeData 模式适配

---

## 附录 A: 完整文件差异索引

### A.1 qtohosextras 真实内容差异文件(17 个)

| 文件 | 主要变更 |
|------|---------|
| `ohosextras.pro` | 构建系统(napi + 新文件) |
| `qohosabilitycontext.h` | 分布式数据对象 API |
| `qohosabilitycontext.cpp` | Optional 迁移 + 新 API 实现 |
| `qohosappbundleinfo.cpp` | Optional 迁移 |
| `qohosappcontext.cpp` | 文档 + Optional 迁移 |
| `qohosapppermissionsutils.cpp` | Optional 迁移 |
| `qohosfileshare.cpp` | Optional 迁移 + qAndThen |
| `qohosmultimediautils.cpp` | Optional 迁移 |
| `qohosoperationstatus.cpp` | Optional 迁移 |
| `qohospasteboard.cpp` | 文档微调 |
| `qohossharekit.cpp` | 文档 + Optional 迁移 |
| `qohosstartoptions.cpp` | Optional 迁移 |
| `qohosstartrequest.cpp` | Optional 迁移 |
| `qohoswant.cpp` | LaunchReason 文档 |
| `qohoswantutils.cpp` | Optional 迁移 |
| `qohoswindowutils.h` | 拖拽关键帧 + 最大化选项 API |
| `qohoswindowutils.cpp` | 新 API 实现 |

### A.2 qtohosextras 仅 CRLF 差异文件(24 个)

内容完全相同，仅换行符 CRLF→LF:
`qohosenums.h`, `qohosapppermissions.h`, `qohosfileshare.h`, `qohossharekit.h`, `qohosstartoptions.h`, `qohosstartrequest.h`, `qohoswant.h`, `qohospasteboard.h`, `qohosfileutils.h`, `qohosappcontext.h`, `qohosappbundleinfo.h`, `qohosappbundleinfo_p.h`, `qohosbundlemanager.h`, `qohosoperationstatus.h`, `qohosoperationstatus_p.h`, `qohosmultimediautils.h`, `qohosuiabilitycontext.h`, `qohossharekit_p.h`, `qohosstartoptions_p.h`, `qohosstartrequest_p.h`, `qohoswantutils_p.h`, `qohosapppermissionsutils_p.h`, `qtohosextrasglobal.h`, `qohosfileutils.cpp`

### A.3 平台插件新增文件(8 个)

`doc/jsscopedata.md`, `qohosdeviceinfo_p.h`, `qohosdeviceinfo.cpp`, `qohosdragkeyframepolicy.h`, `qohosiconengine.cpp`, `qohosiconengine.h`, `qohosqpaenums.h`, `qohoswindowmaximizeoptions.h`

### A.4 平台插件删除/重命名文件(4 个)

| 状态 | 文件 |
|------|------|
| 重命名 | `qohosenums.h` → `qohosqpaenums.h` |
| 重命名 | `qohosimageformat.h/cpp` → `qohosiconengine.cpp/h` |
| 删除 | `qohospointerstyle.h` |
| 删除 | `qohosimageformat.cpp` |

### A.5 新增示例(1 个)

`examples/qtohosextras/windowdragkeyframe/` — 拖拽关键帧策略示例

---

## 附录 B: 枚举变更速查表

| 枚举 | 5.12 位置 | 5.15 位置 | 变更 |
|------|----------|----------|------|
| `SelectionMode` | `qohossharekit.h` | `qohosqpaenums.h` | 移动 |
| `ShareAbilityType` | `qohossharekit.h` | `qohosqpaenums.h` | 移动 |
| `SharePreviewMode` | `qohossharekit.h` | `qohosqpaenums.h` | 移动 |
| `LaunchReason` | `qohosenums.h` | `qohosqpaenums.h` | 移动 |
| `ContinueState` | `qohosenums.h` | `qohosqpaenums.h` | 移动 |
| `WindowMode` | `qohosenums.h` | `qohosqpaenums.h` | 移动 |
| `ColorMode` | `qohosenums.h` | `qohosqpaenums.h` | 移动 |
| `ProcessMode` | `qohosenums.h` | `qohosqpaenums.h` | **新增** `ATTACH_TO_STATUS_BAR_ITEM` |
| `StartupVisibility` | `qohosenums.h` | `qohosqpaenums.h` | 移动 |
| `SupportWindowMode` | `qohosenums.h` | `qohosqpaenums.h` | 移动 |
| `AnimationType` | `qohosenums.h` (WindowCreateParams) | `qohosqpaenums.h` | 命名空间变更 |
| `ContentType` | `qohosenums.h` (NotificationKit) | `qohosqpaenums.h` (ohos) | 命名空间变更 |
| `PointerStyle` | `qohospointerstyle.h` | `qohosqpaenums.h` | **新增** `SCREENRECORDER_CURSOR` |
| `WindowEventType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | 移动 |
| `WindowStatusType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | 移动 |
| `AvoidAreaType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | 移动 |
| `RectChangeReason` | `qohoswindowproxy.h` | `qohosqpaenums.h` | 移动 |
| `MaximizePresentation` | `qohoswindowproxy.h` | `qohosqpaenums.h` | **新增** `ENTER_IMMERSIVE_DISABLE_TITLE_AND_DOCK_HOVER` |
| `ModalityType` | `qohoswindowproxy.h` | `qohosqpaenums.h` | 移动 |
| `JsDisplayOrientation` | `qohosdisplayinfo.h` | `qohosqpaenums.h` (Orientation) | 移动+重命名 |
| `DisplaySourceMode` | `qohosdisplayinfo.h` | `qohosqpaenums.h` | 移动 |
| `OnContinueResult` | `qohosplugincore.h` (QOhosAbilityOnContinueResult) | `qohosqpaenums.h` | 移动+类型别名 |
| `Flags` | — | `qohosqpaenums.h` | **新增** |
| `DocumentSelectMode` | — | `qohosqpaenums.h` | **新增** |
| `Direction` | — | `qohosqpaenums.h` | **新增** |
| `EnterKeyType` | — | `qohosqpaenums.h` | **新增** |
| `RequestKeyboardReason` | — | `qohosqpaenums.h` | **新增** |
| `TextInputType` | — | `qohosqpaenums.h` | **新增** |
| `NetBearType` | — | `qohosqpaenums.h` | **新增** |
| `NetCap` | — | `qohosqpaenums.h` | **新增** |
| `AcrossDisplayPresentation` | — | `qohosqpaenums.h` (Api26) | **新增** |

---

*文档生成日期: 2026-10-08*
*基于源码对比: qt-harmonyos-src (5.12.12, tag a5efc71) vs qt5.15.16 (5.15.16, tag 4af6065)*
