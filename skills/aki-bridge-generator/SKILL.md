---
name: aki-bridge-generator
description: 使用AKI框架为Qt鸿蒙应用生成C++↔ArkTS桥接代码。基于knocksharedemo实战经验，强调SafetyCallback跨线程同步调用、JSBIND_GLOBAL全局函数模式（适配Qt Q_OBJECT单例）、SafetyCallback指针成员管理、TaskRunner初始化、windowId传递、AKI类型声明等关键实践。适用于Qt鸿蒙应用中需要调用鸿蒙系统API（Share、NFC等）的场景。
---

# AKI 桥接代码生成器

使用 AKI（Application Kit Interface）框架为 Qt 鸿蒙应用生成 C++ ↔ ArkTS 桥接代码。

**核心功能**：
- 根据 Qt C++ 侧接口签名自动生成 AKI JSBinding 声明（JSBIND_GLOBAL 模式）
- 生成 ArkTS 侧调用代码模板（SafetyCallback 回调注册）
- C++ ↔ ArkTS 类型映射参考
- SafetyCallback 跨线程同步回调桥接方案

**适用场景**：
- Qt 应用需要调用鸿蒙系统 API（Share Kit、NFC 等）
- ArkTS 侧需要回调 Qt C++ 层（跨线程安全）
- Qt Q_OBJECT 单例 Bridge 类的 AKI 桥接

**AKI 仓库参考**：https://gitcode.com/CPF-ApplicationTPC/aki

---

## 执行策略（必须遵守）

### 原则 0：功能优先（最高优先级，不可违反）

**不管怎么改代码，第一优先级都是保证程序能完成预期功能。不能为了修 bug 或追崩溃而把功能给改没了。**

- 任何修改必须保留完整的业务流程和功能逻辑
- "stub" 和 "空实现" 仅作为临时诊断手段，不可作为最终方案
- 修改后必须验证：点击按钮 → 完整流程走通 → 功能正常
- 如果修改导致功能缺失，必须立即恢复功能代码

遇到问题时，必须按以下流程执行，**不得擅自修改代码**：

1. **分析问题**：描述现象、错误日志、上下文
2. **列出原因**：逐条列出所有可能的原因（编号标注）
3. **给出修改方案**：对应每条原因，列出具体修改项（文件、行号、改什么）
4. **等待用户确认**：将 list 呈现给用户，询问：
   - list 本身有没有要修改的地方？
   - 是否直接按 list 执行修改？
5. **根据用户答复执行**：
   - 用户要求修改 list → 优化 list 后再次确认
   - 用户确认执行 → 按 list 逐一修改

---

## 前置确认（必须！）

**在开始任何操作之前，必须通过对话确认以下要点：**

### 确认点 1：桥接方向

```
问题：请选择桥接方向
选项：
  1. C++ → ArkTS（Qt C++ 调用鸿蒙 ArkTS API）— 最常见，使用 SafetyCallback 同步回调
  2. ArkTS → C++（鸿蒙 ArkTS 回调 Qt C++ 层）— 使用 JSBIND_GLOBAL 全局函数
  3. 双向桥接（C++ ↔ ArkTS）— 完整方案

说明：
- C++ → ArkTS：Qt 侧发起调用，通过 SafetyCallback 跨线程同步调用 ArkTS API
- ArkTS → C++：鸿蒙侧事件回调，通过 JSBIND_GLOBAL 全局函数通知 Qt 层
- 双向桥接：完整交互方案，包含 SafetyCallback 回调和全局函数通知
```

### 确认点 2：需桥接的接口列表

```
问题：请列出需要桥接的 C++ 接口（函数签名）
示例：
  - ShareBridge::registerKnockSend(const QString& content)
  - ShareBridge::registerKnockReceive(int windowId)
  - ShareBridge::unregisterKnockSend()
  - ShareBridge::unregisterKnockReceive()

说明：
  如果用户无法提供完整签名，可先描述功能需求，
  Skill 会根据需求推断接口签名并确认
```

### 确认点 3：工程目录

```
问题：请确认 Qt 鸿蒙工程目录路径
说明：桥接代码将放在 entry/src/main/cpp/ 目录下
```

---

## 核心概念（实战验证）

### AKI 在 Qt 鸿蒙应用中的角色

```
┌──────────────────┐     ┌───────────────────┐     ┌──────────────┐
│  Qt C++ UI       │     │  AKI JSBinding     │     │  ArkTS API   │
│  (Q_OBJECT 单例  │────→│  (JSBIND_GLOBAL    │────→│  (HarmonyOS  │
│   ShareBridge)   │←────│   全局函数+         │←────│   Share/NFC) │
│                  │     │   SafetyCallback)   │     │              │
└──────────────────┘     └───────────────────┘     └──────────────┘
        │                        │
        │  Qt main thread        │  napi_threadsafe_function
        │  (UI操作)              │  + std::promise/future
        │                        │  (10s超时同步返回)
```

### SafetyCallback vs std::function（关键区别）

| 特性 | `aki::SafetyCallback<R(P...)>` | `std::function<R(P...)>` |
|------|-------------------------------|------------------------|
| 跨线程安全 | **安全** — 使用 napi_threadsafe_function + std::promise/future | **不安全** — 仅在同一个 JS 线程上有效 |
| 同步返回 | **支持** — 通过 std::promise/future，10s 超时（AKI_INVOKE_TIMEOUT_MS） | 不支持跨线程同步 |
| 适用场景 | C++ 线程 → ArkTS 线程的回调调用 | 仅在 JS 线程内使用 |
| Qt 鸿蒙必选 | **必须使用** | 禁止用于跨线程 C++→ArkTS |

**教训**：std::function 仅在 JS 线程内工作。Qt 主线程和 ArkTS JS 线程不同，C++ 从 Qt 线程调用 ArkTS 回调必须使用 SafetyCallback。

### JSBIND_GLOBAL vs JSBIND_CLASS（关键选择）

| 特性 | `JSBIND_GLOBAL + JSBIND_FUNCTION` | `JSBIND_CLASS + JSBIND_METHOD` |
|------|-----------------------------------|-------------------------------|
| 适合 Qt Q_OBJECT 单例 | **适合** — 全局自由函数调用 `Bridge::instance()->method()` | **不适合** — JSBIND_CLASS 会创建实例，与 Qt Q_OBJECT 单例冲突 |
| ArkTS 调用方式 | `shareBridge.setCallback(...)` — 模块级函数 | `new ShareBridge().setCallback(...)` — 需实例化 |
| SafetyCallback 支持 | **支持** — 全局函数参数可直接传 SafetyCallback | 支持，但与单例模式冲突 |
| 推荐模式 | **Qt Q_OBJECT 单例 Bridge 首选** | 非单例、需要实例化的场景 |

### 线程安全模型

```
C++ Qt主线程 ──→ SafetyCallback ──→ ArkTS JS线程
                                    (napi_threadsafe_function
                                     + std::promise/future
                                     10s超时同步返回R值)

ArkTS JS线程 ──→ JSBIND_GLOBAL函数 ──→ C++ 任意线程
                                       (C++方法内部通过
                                        QMetaObject::invokeMethod
                                        Qt::QueuedConnection
                                        回到Qt主线程)

⚠️ 禁止在ArkTS回调线程直接调用Qt UI方法！
   必须通过QMetaObject::invokeMethod(Qt::QueuedConnection)
   转发到Qt主线程。
```

---

## 核心流程（6步）

```
确认参数 → 设计桥接接口 → 生成C++桥接代码 → 生成AKI JSBinding → 生成ArkTS调用代码 → 配置类型声明
```

---

## Step 1: 确认参数

按前置确认流程确认桥接方向、接口列表和工程目录。

---

## Step 2: 设计桥接接口

### 设计原则（实战总结）

1. **Bridge 类为 Qt Q_OBJECT 单例**：继承 QObject，使用 `Q_OBJECT` 宏，通过 `instance()` 获取单例
2. **SafetyCallback 为指针成员**：`aki::SafetyCallback<R(P...)>* m_func`，初始化 nullptr，delete 在析构，delete+new 在 setter
3. **方法命名**：C++ 侧方法与鸿蒙 API 功能对应，使用 C++ 风格
4. **参数类型**：使用 AKI 支持的类型（std::string, int, bool 等），Qt 类型（QString）在调用时转换
5. **回调注册模式**：C++ 侧 setter 方法接收 SafetyCallback，存储为指针成员，业务方法通过指针调用

### 接口设计示例（碰一碰文件分享 — 来自 knocksharedemo）

```cpp
// share_bridge.h — Qt Q_OBJECT 单例 + SafetyCallback 指针成员
#pragma once

#include <QObject>
#include <QString>
#include <mutex>
#include <string>
#include <aki/jsbind.h>

class ShareBridge : public QObject {
    Q_OBJECT

public:
    static ShareBridge* instance();

    void initTaskRunner();  // 必须在 Qt main() 中调用！

    // 业务方法（由 Qt UI 调用，内部通过 SafetyCallback 调 ArkTS）
    void registerKnockSend(const QString& content);
    void unregisterKnockSend();
    void registerKnockReceive(int windowId);
    void unregisterKnockReceive();

    // ArkTS → C++ 通知方法（由 ArkTS 通过 JSBIND_GLOBAL 调用）
    void notifyResult(int resultCode, const std::string& resultMsg);
    void notifyKnockEvent();
    void notifyDataReceive(const std::string& data);
    void notifyDataReceiveFile(const std::string& fileName, const std::string& filePath);

    // SafetyCallback setter（由 ArkTS init() 时调用注册回调）
    void setRegisterKnockSendCallback(aki::SafetyCallback<bool(std::string)> callback);
    void setUnregisterKnockSendCallback(aki::SafetyCallback<bool()> callback);
    void setRegisterKnockReceiveCallback(aki::SafetyCallback<bool(int, std::string, int)> callback);
    void setUnregisterKnockReceiveCallback(aki::SafetyCallback<bool()> callback);

signals:
    void logMessage(const QString& msg);

private:
    ShareBridge();
    ~ShareBridge() override;

    static ShareBridge* m_instance;
    static std::mutex m_mutex;

    // SafetyCallback 指针成员 — 必须是指针，不能是值！
    aki::SafetyCallback<bool(std::string)>* m_registerKnockSendFunc;
    aki::SafetyCallback<bool()>* m_unregisterKnockSendFunc;
    aki::SafetyCallback<bool(int, std::string, int)>* m_registerKnockReceiveFunc;
    aki::SafetyCallback<bool()>* m_unregisterKnockReceiveFunc;

    std::string m_pendingContent;
};
```

**关键设计要点**：

1. **SafetyCallback 必须用指针成员**：`aki::SafetyCallback<bool(std::string)>* m_func`，不是值成员。SafetyCallback 内部持有 napi_threadsafe_function 资源，拷贝/移动操作有问题。用指针 + delete/new 管理生命周期更安全。

2. **setter 方法签名**：参数为 `aki::SafetyCallback<R(P...)> callback`（值传递），内部 `delete m_func; m_func = new aki::SafetyCallback<R(P...)>(std::move(callback));`

3. **业务方法调用 SafetyCallback**：通过 `(*m_func)(args)` 解引用指针调用，返回值为同步返回（10s超时）。

4. **initTaskRunner()**：必须在 Qt main() 中调用 `aki::TaskRunner::Create("share_bridge")`，创建 napi threadsafe_function 上下文。

---

## Step 3: 生成 C++ 桥接代码

### 3.1 桥接实现文件

路径：`entry/src/main/cpp/share_bridge.cpp`

```cpp
#include "share_bridge.h"
#include <QMetaObject>
#include <QDebug>

ShareBridge* ShareBridge::m_instance = nullptr;
std::mutex ShareBridge::m_mutex;

ShareBridge* ShareBridge::instance() {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (!m_instance) {
        m_instance = new ShareBridge();
    }
    return m_instance;
}

// 构造函数：所有 SafetyCallback 指针初始化为 nullptr
ShareBridge::ShareBridge() : QObject(nullptr),
    m_registerKnockSendFunc(nullptr),
    m_unregisterKnockSendFunc(nullptr),
    m_registerKnockReceiveFunc(nullptr),
    m_unregisterKnockReceiveFunc(nullptr) {}

// 析构函数：delete 所有 SafetyCallback 指针
ShareBridge::~ShareBridge() {
    delete m_registerKnockSendFunc;
    delete m_unregisterKnockSendFunc;
    delete m_registerKnockReceiveFunc;
    delete m_unregisterKnockReceiveFunc;
}

// TaskRunner 初始化 — 必须在 Qt main() 中调用！
void ShareBridge::initTaskRunner() {
    aki::TaskRunner::Create("share_bridge");
}

// SafetyCallback setter：delete旧指针 + new新指针
void ShareBridge::setRegisterKnockSendCallback(aki::SafetyCallback<bool(std::string)> callback) {
    delete m_registerKnockSendFunc;
    m_registerKnockSendFunc = new aki::SafetyCallback<bool(std::string)>(std::move(callback));
    notifyResult(0, "setRegisterKnockSendCallback OK");
}

void ShareBridge::setUnregisterKnockSendCallback(aki::SafetyCallback<bool()> callback) {
    delete m_unregisterKnockSendFunc;
    m_unregisterKnockSendFunc = new aki::SafetyCallback<bool()>(std::move(callback));
    notifyResult(0, "setUnregisterKnockSendCallback OK");
}

void ShareBridge::setRegisterKnockReceiveCallback(aki::SafetyCallback<bool(int, std::string, int)> callback) {
    delete m_registerKnockReceiveFunc;
    m_registerKnockReceiveFunc = new aki::SafetyCallback<bool(int, std::string, int)>(std::move(callback));
    notifyResult(0, "setRegisterKnockReceiveCallback OK");
}

void ShareBridge::setUnregisterKnockReceiveCallback(aki::SafetyCallback<bool()> callback) {
    delete m_unregisterKnockReceiveFunc;
    m_unregisterKnockReceiveFunc = new aki::SafetyCallback<bool()>(std::move(callback));
    notifyResult(0, "setUnregisterKnockReceiveCallback OK");
}

// 业务方法：通过 SafetyCallback 指针同步调用 ArkTS
void ShareBridge::registerKnockSend(const QString& content) {
    m_pendingContent = content.toStdString();
    if (m_registerKnockSendFunc) {
        bool result = (*m_registerKnockSendFunc)(m_pendingContent);
        // result 是 ArkTS 回调的同步返回值（10s超时保护）
        if (result) {
            onRegisterKnockSendResult(true, m_pendingContent);
        } else {
            onRegisterKnockSendResult(false, m_pendingContent);
        }
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: registerKnockSend callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void ShareBridge::registerKnockReceive(int windowId) {
    if (m_registerKnockReceiveFunc) {
        std::string utdTypes = "general.image,general.media,general.text,general.file,general.hyperlink,com.huawei.hmos.appLinking";
        bool result = (*m_registerKnockReceiveFunc)(999, utdTypes, windowId);
        if (result) {
            onRegisterKnockReceiveResult(true);
        } else {
            onRegisterKnockReceiveResult(false);
        }
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: registerKnockReceive callback not initialized");
        }, Qt::QueuedConnection);
    }
}

// ArkTS → C++ 通知方法（线程安全转发到 Qt 主线程）
void ShareBridge::notifyResult(int resultCode, const std::string& resultMsg) {
    QString msg = QString("[ShareResult] code=%1, msg=%2")
        .arg(resultCode)
        .arg(QString::fromStdString(resultMsg));
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void ShareBridge::notifyKnockEvent() {
    QMetaObject::invokeMethod(this, [this]() {
        emit logMessage("[KnockEvent] Knock share event detected!");
    }, Qt::QueuedConnection);
}
```

**关键实现要点**：

1. **SafetyCallback 指针调用语法**：`(*m_func)(args)` — 解引用指针，传入参数，获得同步返回值。

2. **所有 Qt UI 操作必须通过 QMetaObject::invokeMethod(Qt::QueuedConnection)**：ArkTS 通过 JSBIND_GLOBAL 调用 C++ 方法时，处于 ArkTS JS 线程，不能直接操作 Qt UI。必须转发到 Qt 主线程。

3. **SafetyCallback setter 模式**：`delete m_func; m_func = new aki::SafetyCallback<R(P...)>(std::move(callback));` — 先 delete 旧指针，再 new 新对象，避免资源泄漏。

---

## Step 4: 生成 AKI JSBinding（JSBIND_GLOBAL 模式）

### 4.1 JSBinding 声明（全局函数模式）

路径：`entry/src/main/cpp/share_aki_binding.cpp`

**重要**：对于 Qt Q_OBJECT 单例 Bridge，必须使用 `JSBIND_GLOBAL + JSBIND_FUNCTION`，不能用 `JSBIND_CLASS + JSBIND_METHOD`！

```cpp
#include "aki/jsbind.h"
#include "share_bridge.h"

// 全局自由函数 — 调用 ShareBridge::instance()->method()
// SafetyCallback setter 函数：接收 ArkTS 回调并存储
void setRegisterKnockSendCallback(aki::SafetyCallback<bool(std::string)> callback) {
    ShareBridge::instance()->setRegisterKnockSendCallback(std::move(callback));
}

void setUnregisterKnockSendCallback(aki::SafetyCallback<bool()> callback) {
    ShareBridge::instance()->setUnregisterKnockSendCallback(std::move(callback));
}

void setRegisterKnockReceiveCallback(aki::SafetyCallback<bool(int, std::string, int)> callback) {
    ShareBridge::instance()->setRegisterKnockReceiveCallback(std::move(callback));
}

void setUnregisterKnockReceiveCallback(aki::SafetyCallback<bool()> callback) {
    ShareBridge::instance()->setUnregisterKnockReceiveCallback(std::move(callback));
}

// ArkTS → C++ 通知函数：ArkTS 侧直接调用
void notifyResult(int resultCode, std::string resultMsg) {
    ShareBridge::instance()->notifyResult(resultCode, resultMsg);
}

void notifyKnockEvent() {
    ShareBridge::instance()->notifyKnockEvent();
}

void notifyDataReceive(std::string data) {
    ShareBridge::instance()->notifyDataReceive(data);
}

void notifyDataReceiveFile(std::string fileName, std::string filePath) {
    ShareBridge::instance()->notifyDataReceiveFile(fileName, filePath);
}

// JSBIND_GLOBAL 注册全局函数（不是 JSBIND_CLASS！）
JSBIND_GLOBAL()
{
    JSBIND_FUNCTION(setRegisterKnockSendCallback);
    JSBIND_FUNCTION(setUnregisterKnockSendCallback);
    JSBIND_FUNCTION(setRegisterKnockReceiveCallback);
    JSBIND_FUNCTION(setUnregisterKnockReceiveCallback);
    JSBIND_FUNCTION(notifyResult);
    JSBIND_FUNCTION(notifyKnockEvent);
    JSBIND_FUNCTION(notifyDataReceive);
    JSBIND_FUNCTION(notifyDataReceiveFile);
}

// JSBIND_ADDON 注册 — addon 名与 .so 库名对应
JSBIND_ADDON(share_bridge);
```

**关键说明**：

- **JSBIND_GLOBAL()**：声明全局函数集合，不创建类实例。所有函数都是全局自由函数，内部调用 `ShareBridge::instance()->method()`。

- **JSBIND_FUNCTION**：注册全局自由函数。ArkTS 侧通过 `import * as shareBridge from 'libsharebridge.so'` 获取模块，然后 `shareBridge.setRegisterKnockSendCallback(...)` 调用。

- **JSBIND_ADDON(share_bridge)**：注册 N-API addon。名称对应关系：
  - addon 名 `share_bridge` → .so 库 `libsharebridge.so` → ArkTS import `from 'libsharebridge.so'` → oh-package type `@types/libsharebridge.so`

- **SafetyCallback 参数传递**：全局函数参数为 `aki::SafetyCallback<R(P...)> callback`（值传递），内部 `std::move(callback)` 转给单例 setter。

- **⚠️ 禁止使用 JSBIND_CLASS + JSBIND_METHOD 模式桥接 Qt Q_OBJECT 单例**：JSBIND_CLASS 会创建 C++ 类实例，与 Qt Q_OBJECT 单例模式冲突（Q_OBJECT 的 parent/children 关系、信号槽机制依赖 QObject 实例生命周期管理）。

### 4.2 JSBIND_CLASS vs JSBIND_GLOBAL 选择指南

```
决策树：

Bridge类是Qt Q_OBJECT单例？
  ├─ YES → JSBIND_GLOBAL + JSBIND_FUNCTION（全局自由函数调用单例方法）
  │         原因：JSBIND_CLASS 创建实例与Q_OBJECT单例冲突
  │
  └─ NO → Bridge类需要实例化？
           ├─ YES → JSBIND_CLASS + JSBIND_METHOD + JSBIND_CONSTRUCTOR
           │         适合：纯数据类、工具类、无Qt生命周期管理
           │
           └─ NO → JSBIND_GLOBAL + JSBIND_FUNCTION（静态方法或全局函数）
                    适合：纯函数式API、无需对象管理
```

### 4.3 类型映射注意事项

| C++ 类型 | AKI 映射的 ArkTS 类型 | 说明 |
|----------|----------------------|------|
| `bool` | `boolean` | 直接映射 |
| `int` | `number` | 直接映射 |
| `std::string` | `string` | AKI 自动 UTF-8 转换 |
| `aki::SafetyCallback<R(P...)>` | `(P...) => R` | SafetyCallback 参数映射为 ArkTS 函数 |
| `std::function<void(...)>` | `(...) => void` | 仅 JS 线程内有效，**禁止跨线程使用** |
| `std::vector<T>` | `T[]` | 数组映射 |
| 自定义类 | ArkTS class | 需要 JSBIND_CLASS 注册 |

详见 `references/aki-type-mapping.md`

### 4.4 CMakeLists.txt 配置

在 `entry/src/main/cpp/CMakeLists.txt` 中：

```cmake
cmake_minimum_required(VERSION 3.16)
project(knocksharedemo)

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

if(CMAKE_CROSSCOMPILING)
  set(_saved_root_path_mode_package "${CMAKE_FIND_ROOT_PATH_MODE_PACKAGE}")
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()

# Qt5 模块：必须包含 OhosExtras！
find_package(QT NAMES Qt5 Qt6 REQUIRED COMPONENTS Core)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Core Widgets OhosExtras)

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
  share_bridge.h
  share_bridge.cpp
  share_aki_binding.cpp
)

# AKI 源码目录（根据实际路径配置）
set(AKI_SOURCE_DIR "path/to/aki-reference")

add_library(knocksharedemo SHARED ${PROJECT_SOURCES})
add_subdirectory(${AKI_SOURCE_DIR} aki)

# 链接：必须包含 Qt5::OhosExtras 和 aki_jsbind
target_link_libraries(knocksharedemo PRIVATE
  Qt${QT_VERSION_MAJOR}::Core
  Qt${QT_VERSION_MAJOR}::Widgets
  Qt${QT_VERSION_MAJOR}::OhosExtras
  Qt${QT_VERSION_MAJOR}::QOhosPlatformIntegrationPlugin
  aki_jsbind
)
```

**关键要点**：
- `find_package(Qt5 REQUIRED COMPONENTS Core Widgets OhosExtras)` — OhosExtras 是获取 windowId 的必要模块
- `Qt5::OhosExtras` 必须在 target_link_libraries 中
- `aki_jsbind` 是 AKI 框架的链接目标

---

## Step 5: 生成 ArkTS 调用代码

### 5.1 ArkTS 桥接代理模块

路径：`entry/src/main/ets/share/ShareBridgeProxy.ets`

```typescript
import { harmonyShare } from '@kit.ShareKit';
import { systemShare } from '@kit.ShareKit';
import { BusinessError } from '@kit.BasicServicesKit';
import * as shareBridge from 'libsharebridge.so';

export class ShareBridgeProxy {
  private static instance: ShareBridgeProxy | null = null;
  private shareTarget: harmonyShare.SharableTarget | null = null;
  private recvCapabilityRegistry: harmonyShare.RecvCapabilityRegistry | null = null;
  private isKnockListening: boolean = false;
  private isDataReceiving: boolean = false;
  private receiveDir: string = '';

  static getInstance(): ShareBridgeProxy {
    if (!ShareBridgeProxy.instance) {
      ShareBridgeProxy.instance = new ShareBridgeProxy();
    }
    return ShareBridgeProxy.instance;
  }

  setReceiveDir(receiveDir: string): void {
    this.receiveDir = receiveDir;
  }

  // init()：注册 SafetyCallback 回调到 C++ 侧
  // 必须在 ArkTS UI 初始化后调用，此时 JS 环境就绪
  init(): void {
    shareBridge.setRegisterKnockSendCallback((content: string): boolean => {
      return this.registerKnockSendImpl(content);
    });
    shareBridge.setUnregisterKnockSendCallback((): boolean => {
      return this.unregisterKnockSendImpl();
    });
    shareBridge.setRegisterKnockReceiveCallback((maxFileCount: number, utdTypes: string, windowId: number): boolean => {
      return this.registerKnockReceiveImpl(maxFileCount, utdTypes, windowId);
    });
    shareBridge.setUnregisterKnockReceiveCallback((): boolean => {
      return this.unregisterKnockReceiveImpl();
    });
    shareBridge.notifyResult(0, 'ShareBridgeProxy init OK');
  }

  private registerKnockSendImpl(content: string): boolean {
    try {
      if (!this.isKnockListening) {
        harmonyShare.on('knockShare', (target: harmonyShare.SharableTarget) => {
          this.shareTarget = target;
          shareBridge.notifyKnockEvent();
          try {
            let sharedData = new systemShare.SharedData({
              utd: 'general.text',
              content: content,
              title: 'Knock Share Demo',
              description: 'Shared from KnockShareDemo app'
            });
            target.share(sharedData).then(() => {
              shareBridge.notifyResult(0, 'Share content sent successfully');
            }).catch((error: BusinessError) => {
              shareBridge.notifyResult(error.code ?? -1, `Share failed: ${error.message}`);
            });
          } catch (err) {
            shareBridge.notifyResult(-1, `Share exception: ${err}`);
          }
        });
        this.isKnockListening = true;
        return true;
      }
      shareBridge.notifyResult(0, 'Already registered knock send');
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Register knock send failed: ${err}`);
      return false;
    }
  }

  private registerKnockReceiveImpl(maxFileCount: number, utdTypes: string, windowId: number): boolean {
    try {
      if (!this.isDataReceiving) {
        if (!this.receiveDir) {
          shareBridge.notifyResult(-1, 'receiveDir not set');
          return false;
        }
        let utdArray: string[] = utdTypes.split(',');
        let capabilities: harmonyShare.RecvCapability[] = utdArray.map((utd: string) => {
          return { utd: utd, maxSupportedCount: maxFileCount } as harmonyShare.RecvCapability;
        });
        this.recvCapabilityRegistry = {
          windowId: windowId,
          capabilities: capabilities
        } as harmonyShare.RecvCapabilityRegistry;
        harmonyShare.on('dataReceive', this.recvCapabilityRegistry, (receivableTarget: harmonyShare.ReceivableTarget) => {
          // ... 处理接收数据
        });
        this.isDataReceiving = true;
        return true;
      }
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Register knock receive failed: ${err}`);
      return false;
    }
  }

  private unregisterKnockSendImpl(): boolean {
    try {
      if (this.isKnockListening) {
        harmonyShare.off('knockShare');
        this.isKnockListening = false;
        this.shareTarget = null;
        return true;
      }
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Unregister knock send failed: ${err}`);
      return false;
    }
  }

  private unregisterKnockReceiveImpl(): boolean {
    try {
      if (this.isDataReceiving) {
        if (this.recvCapabilityRegistry) {
          harmonyShare.off('dataReceive', this.recvCapabilityRegistry);
        }
        this.isDataReceiving = false;
        this.recvCapabilityRegistry = null;
        return true;
      }
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Unregister knock receive failed: ${err}`);
      return false;
    }
  }
}
```

**关键说明**：

- **import 方式**：`import * as shareBridge from 'libsharebridge.so'` — JSBIND_GLOBAL 注册的是模块级函数，不是类，使用 `* as` 导入整个模块。

- **init() 回调注册**：SafetyCallback 回调在 `init()` 中一次性注册。回调函数的**返回值**是同步返回给 C++ 的（SafetyCallback 通过 std::promise/future 实现）。

- **回调函数返回 boolean**：SafetyCallback 签名 `aki::SafetyCallback<bool(P...)>`，ArkTS 回调必须返回 boolean 值，C++ 侧通过 `(*m_func)(args)` 同步获取。

### 5.2 Qt main() 中初始化 TaskRunner

路径：`entry/src/main/cpp/main.cpp`

```cpp
#include <QApplication>
#include <QWidget>
#include <QtOhosExtras>  // 模块级头文件，不要用 QtOhosExtras/QOhosWindowUtils
#include "share_bridge.h"

class KnockShareWindow : public QWidget {
    Q_OBJECT
public:
    KnockShareWindow(QWidget *parent = nullptr) : QWidget(parent) {
        setupUI();
        connectSignals();
    }

private:
    void connectSignals() {
        ShareBridge *bridge = ShareBridge::instance();

        connect(m_btnRegisterReceive, &QPushButton::clicked, this, [&]() {
            // windowId 获取模式：QtOhosExtras::tryGetNativeWindowId
            auto windowIdPtr = QtOhosExtras::tryGetNativeWindowId(window()->windowHandle());
            int windowId = windowIdPtr ? static_cast<int>(*windowIdPtr) : -1;
            bridge->registerKnockReceive(windowId);
        });

        connect(bridge, &ShareBridge::logMessage, this, [this](const QString &msg) {
            m_logEdit->append(msg);
        });
    }
};

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    KnockShareWindow window;
    window.resize(800, 600);
    window.show();

    // ⚠️ 必须在 Qt main() 中调用 initTaskRunner()！
    // 在 window.show() 之后调用，确保 napi 环境已就绪
    ShareBridge::instance()->initTaskRunner();

    return app.exec();
}
```

**关键要点**：

- **TaskRunner 初始化顺序**：`ShareBridge::instance()->initTaskRunner()` 必须在 Qt main() 中调用，且在 window.show() 之后（确保 napi 环境已就绪）。这创建 napi_threadsafe_function 上下文，SafetyCallback 依赖它。

- **QtOhosExtras include**：使用 `#include <QtOhosExtras>`（模块级头文件），不要用 `#include <QtOhosExtras/QOhosWindowUtils>`（Qt5 不为子头文件生成 forwarding headers）。

- **windowId 获取**：
  ```cpp
  auto windowIdPtr = QtOhosExtras::tryGetNativeWindowId(window()->windowHandle());
  int windowId = windowIdPtr ? static_cast<int>(*windowIdPtr) : -1;
  ```
  - `tryGetNativeWindowId()` 返回 `QSharedPointer<double>`
  - 转为 int：`static_cast<int>(*windowIdPtr)`
  - 无效时返回 -1

---

## Step 6: 配置 AKI 类型声明

### 6.1 创建类型声明文件

路径：`entry/src/main/cpp/types/share_bridge/index.d.ts`

```typescript
export const setRegisterKnockSendCallback: (callback: (content: string) => boolean) => void;
export const setUnregisterKnockSendCallback: (callback: () => boolean) => void;
export const setRegisterKnockReceiveCallback: (callback: (maxFileCount: number, utdTypes: string, windowId: number) => boolean) => void;
export const setUnregisterKnockReceiveCallback: (callback: () => boolean) => void;
export const notifyResult: (resultCode: number, resultMsg: string) => void;
export const notifyKnockEvent: () => void;
export const notifyDataReceive: (data: string) => void;
export const notifyDataReceiveFile: (fileName: string, filePath: string) => void;
```

**关键**：JSBIND_GLOBAL 模式下，所有导出都是 `export const` 函数声明（不是 `export class`）。

### 6.2 创建 oh-package.json5

路径：`entry/src/main/cpp/types/share_bridge/oh-package.json5`

```json5
{
  "name": "libsharebridge.so",
  "types": "./index.d.ts",
  "version": "",
  "description": "Knock Share Bridge AKI addon"
}
```

**关键**：`name` 必须为 `lib<addonname>.so` 格式。addon 名 `share_bridge` → name `libsharebridge.so`。

### 6.3 在 entry/oh-package.json5 中添加 devDependencies

路径：`entry/oh-package.json5`

```json5
{
  "devDependencies": {
    "@types/libentry.so": "file:./src/main/cpp/types/libentry",
    "@types/libsharebridge.so": "file:./src/main/cpp/types/share_bridge",
    "@types/libqohos.so": "file:./src/main/qt"
  },
  "name": "entry",
  "version": "1.0.0",
  "dependencies": {}
}
```

**关键对应关系**：
- addon 名 `share_bridge` → .so 库名 `libsharebridge.so`
- type 包名 `@types/libsharebridge.so` → 指向 `file:./src/main/cpp/types/share_bridge`
- ArkTS import `from 'libsharebridge.so'` → type 声明在 `@types/libsharebridge.so`

---

## 回调签名变更检查清单（7层一致性）

**当修改 SafetyCallback 参数签名时（如添加 windowId 参数），必须同步更新所有 7 层：**

| 层 | 文件 | 修改内容 |
|----|------|----------|
| 1 | `share_bridge.h` | SafetyCallback 指针成员类型：`aki::SafetyCallback<bool(int, std::string, int)>* m_func` |
| 2 | `share_bridge.h` | setter 方法参数类型：`void setXxxCallback(aki::SafetyCallback<bool(int, std::string, int)> callback)` |
| 3 | `share_bridge.cpp` | setter 实现：`new aki::SafetyCallback<bool(int, std::string, int)>(std::move(callback))` |
| 4 | `share_bridge.cpp` | 业务方法调用：`(*m_func)(999, utdTypes, windowId)` |
| 5 | `share_aki_binding.cpp` | 全局函数签名：`void setXxxCallback(aki::SafetyCallback<bool(int, std::string, int)> callback)` |
| 6 | `ShareBridgeProxy.ets` | init() 回调签名：`(maxFileCount: number, utdTypes: string, windowId: number): boolean` |
| 7 | `index.d.ts` | 类型声明：`(callback: (maxFileCount: number, utdTypes: string, windowId: number) => boolean) => void` |

**遗漏任何一层都会导致编译类型不匹配错误！**

---

## 完整集成步骤

### 1. 安装 AKI 框架

```bash
# 源码集成（推荐）
# 从 https://gitcode.com/CPF-ApplicationTPC/aki 克隆源码
# 在 CMakeLists.txt 中 add_subdirectory 指向 AKI 源码目录
```

### 2. 配置 CMakeLists.txt

- 添加 Qt OhosExtras 模块：`find_package(Qt5 REQUIRED COMPONENTS Core Widgets OhosExtras)`
- 链接 `Qt5::OhosExtras` 和 `aki_jsbind`
- 添加桥接源文件（share_bridge.h/cpp, share_aki_binding.cpp）

### 3. 配置 AKI 类型声明

- 创建 `entry/src/main/cpp/types/<addon_name>/index.d.ts` 和 `oh-package.json5`
- 在 `entry/oh-package.json5` devDependencies 中添加 `@types/lib<addonname>.so`

### 4. Qt main() 中初始化

- 调用 `Bridge::instance()->initTaskRunner()` 创建 TaskRunner
- 在 window.show() 之后调用

### 5. ArkTS 侧初始化

- 在 UI Ability 或页面初始化时调用 `ShareBridgeProxy.getInstance().init()`
- 注册 SafetyCallback 回调

### 6. 构建

在 DevEco Studio 中构建项目，确认 AKI 桥接代码编译通过。

---

## 常见问题与解决方案

| 问题 | 根因 | 解决方案 |
|------|------|----------|
| SafetyCallback 调用超时/崩溃 | 未调用 `aki::TaskRunner::Create("addon_name")` | 在 Qt main() 中调用 `initTaskRunner()`，必须在 SafetyCallback 使用之前 |
| SafetyCallback 拷贝/移动错误 | SafetyCallback 作为值成员 | 改为指针成员：`aki::SafetyCallback<R(P...)>* m_func`，nullptr初始化，delete析构，delete+new setter |
| JSBIND_CLASS 创建实例与 Q_OBJECT 单例冲突 | JSBIND_CLASS 会实例化 C++ 对象 | 改用 JSBIND_GLOBAL + JSBIND_FUNCTION 全局函数模式，内部调用 `Bridge::instance()->method()` |
| ArkTS import 找不到 addon | addon 名与 .so 名对应关系错误 | addon 名 `share_bridge` → .so `libsharebridge.so` → import `from 'libsharebridge.so'` |
| ArkTS import 类型报错 | 缺少 index.d.ts 或 oh-package.json5 | 创建 `types/<addon>/index.d.ts` + `oh-package.json5`，在 entry 的 devDependencies 中添加 |
| C++ 调 ArkTS 回调崩溃 | 使用 std::function 而非 SafetyCallback | 跨线程必须用 `aki::SafetyCallback`，std::function 仅在同 JS 线程有效 |
| Qt UI 方法在 ArkTS 回调线程崩溃 | ArkTS 回调不在 Qt 主线程 | 使用 `QMetaObject::invokeMethod(this, [...], Qt::QueuedConnection)` 转发 |
| QtOhosExtras include 错误 | 使用子头文件路径 | 用 `#include <QtOhosExtras>` 模块级头文件 |
| windowId 获取 | `QtOhosExtras::tryGetNativeWindowId` 返回 `QSharedPointer<double>` | 转为 int：`static_cast<int>(*windowIdPtr)` |
| SafetyCallback 签名变更编译错误 | 仅修改了部分层 | 按 7层一致性检查清单逐一更新 |
| JSBIND_GLOBAL 模式 ArkTS 调用方式错误 | 使用 `new ShareBridge()` 实例化 | JSBIND_GLOBAL 导出模块级函数，用 `import * as shareBridge from 'libsharebridge.so'` |

---

## 关键约束（实战红线）

**禁止**：
- ❌ 在跨线程 C++→ArkTS 回调中使用 `std::function`（必须用 SafetyCallback 或 bindFunction+InvokeInJsThreadAndWait）
- ❌ 将 SafetyCallback 作为值成员存储（必须用指针成员）
- ❌ 使用 `JSBIND_CLASS + JSBIND_METHOD` 桥接 Qt Q_OBJECT 单例（必须用 JSBIND_GLOBAL）
- ❌ Bridge 类继承 QObject（d_ptr 在 OHOS 运行时被破坏，导致 `0x8bxxxx` 崩溃）
- ❌ JS 线程调用任何 Qt API（qDebug、QObject、QMetaObject、emit 等，**即使 Qt 已初始化也不行**）
- ❌ 在 ArkTS 回调线程直接调用 Qt UI 方法（必须通过 std::function callback 回到 QtMainThread）
- ❌ 使用 `#include <QtOhosExtras/QOhosWindowUtils>` 子头文件（Qt5 不生成 forwarding headers）
- ❌ 在 AKI 桥接代码中使用 Qt 类型（QString/QByteArray 等，必须转为 std::string）
- ❌ 修改 AKI 框架源码
- ❌ JS 线程使用 std::mutex 等 QObject 子类成员（d_ptr 破坏后成员偏移无效）

**必须**：
- ✅ Bridge 类为**普通 C++ 类**（不继承 QObject），用 `std::function` callback 替代 Qt signal
- ✅ SafetyCallback 跨线程回调：C++→ArkTS 使用 `aki::SafetyCallback<R(P...)>`
- ✅ QtMainThread→JS 调用推荐使用 `aki::JSBind.bindFunction` + `InvokeInJsThreadAndWait`
- ✅ SafetyCallback 指针成员：`aki::SafetyCallback<R(P...)>* m_func`，nullptr 初始化，delete 析构
- ✅ setter 方法 delete+new 模式：`delete m_func; m_func = new aki::SafetyCallback<R(P...)>(std::move(callback));`
- ✅ JSBIND_GLOBAL + JSBIND_FUNCTION：Bridge 类桥接模式
- ✅ ThreadSafeExecutor 两阶段初始化：Phase1（JS线程缓存 env）+ Phase2（QtMainThread 创建 tsfn）
- ✅ JS 线程日志用 `fprintf(stderr, ...)` 替代 `qDebug()`
- ✅ AKI 类型声明：index.d.ts + oh-package.json5 + entry devDependencies
- ✅ 签名变更 7层一致性检查

**建议**：
- 每个功能模块创建独立的 Bridge 类（如 ShareBridge、NfcBridge）
- Bridge 类使用普通 C++ 类 + `std::function` callback + 全局变量（非 QObject 单例）
- SafetyCallback 回调返回 boolean 表示操作成功/失败
- 复杂数据传递使用 JSON 字符串（std::string ↔ string）
- 所有 ArkTS→C++ 通知方法使用 `notify*` 前缀命名
- 所有 SafetyCallback setter 使用 `set*Callback` 前缀命名
