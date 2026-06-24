# AKI 使用指南

## AKI 框架概述

AKI（Application Kit Interface）是一个用于鸿蒙应用的 C++/ArkTS 桥接框架，由 CPF-ApplicationTPC 团队维护。

**仓库地址**：https://gitcode.com/CPF-ApplicationTPC/aki

**核心能力**：
- 将 C++ 类、方法、属性注册为 JS/ArkTS 可调用的对象
- 自动类型映射（C++ ↔ JS/ArkTS）
- 回调函数桥接（ArkTS → C++ 和 C++ → ArkTS）
- C++ 对象在 ArkTS 侧的生命周期管理

## 基本使用流程

### 1. 定义 C++ 桥接类

```cpp
// my_bridge.h
#pragma once
#include <string>
#include "aki/jsbind.h"

class MyBridge {
public:
    static std::string getMessage();
    static void setMessage(const std::string& msg);
    static int addNumbers(int a, int b);
};
```

### 2. 实现 C++ 桥接类

```cpp
// my_bridge.cpp
#include "my_bridge.h"

std::string MyBridge::getMessage() {
    return "Hello from C++!";
}

void MyBridge::setMessage(const std::string& msg) {
    // 处理来自 ArkTS 的数据
}

int MyBridge::addNumbers(int a, int b) {
    return a + b;
}
```

### 3. 注册 JSBinding

```cpp
// my_aki_binding.cpp
#include "aki/jsbind.h"
#include "my_bridge.h"

JSBIND_CLASS(MyBridge) {
    JSBIND_METHOD(getMessage);
    JSBIND_METHOD(setMessage);
    JSBIND_METHOD(addNumbers);
}

JSBIND_ADDON(my_bridge, MyBridge);
```

**关键说明**：

- `JSBIND_CLASS(MyBridge)`：声明要桥接的 C++ 类
- `JSBIND_METHOD(...)`：声明要暴露的方法名（必须与 C++ 方法名完全一致）
- `JSBIND_ADDON(my_bridge, MyBridge)`：注册 addon，名称 `my_bridge` 是 ArkTS import 使用的模块名

### 4. ArkTS 侧调用

```typescript
import { MyBridge } from 'my_bridge';

// 调用 C++ 方法
const msg = MyBridge.getMessage();
MyBridge.setMessage('New message from ArkTS');
const sum = MyBridge.addNumbers(3, 5);
```

## 回调函数桥接

### C++ 侧定义回调

```cpp
class CallbackBridge {
public:
    // 注册 ArkTS → C++ 回调
    static void registerCallback(std::function<void(int, std::string)> callback);

private:
    static std::function<void(int, std::string)> m_callback;
};

void CallbackBridge::registerCallback(
    std::function<void(int, std::string)> callback) {
    m_callback = callback;
}

// C++ 侧触发回调
void CallbackBridge::triggerCallback(int code, std::string msg) {
    if (m_callback) {
        m_callback(code, msg);
    }
}
```

### JSBinding 注册

```cpp
JSBIND_CLASS(CallbackBridge) {
    JSBIND_METHOD(registerCallback);
}

JSBIND_ADDON(callback_bridge, CallbackBridge);
```

### ArkTS 侧使用回调

```typescript
import { CallbackBridge } from 'callback_bridge';

CallbackBridge.registerCallback((code: number, msg: string) => {
    console.log(`Callback received: code=${code}, msg=${msg}`);
});
```

## 实例方法 vs 静态方法

### 静态方法（推荐用于 Bridge 类）

```cpp
class StaticBridge {
public:
    static void doSomething();
};

JSBIND_CLASS(StaticBridge) {
    JSBIND_METHOD(doSomething);
}
```

ArkTS 调用：
```typescript
StaticBridge.doSomething();
```

### 实例方法

```cpp
class InstanceBridge {
public:
    InstanceBridge(int value);
    int getValue();
    void setValue(int value);
};

JSBIND_CLASS(InstanceBridge) {
    JSBIND_CONSTRUCTOR(int value);
    JSBIND_METHOD(getValue);
    JSBIND_METHOD(setValue);
}
```

ArkTS 调用：
```typescript
const bridge = new InstanceBridge(42);
bridge.getValue();
bridge.setValue(100);
```

## 属性桥接

```cpp
class PropertyBridge {
public:
    std::string name;
    int count;
};

JSBIND_CLASS(PropertyBridge) {
    JSBIND_PROPERTY(name);
    JSBIND_PROPERTY(count);
}
```

ArkTS 使用：
```typescript
const obj = new PropertyBridge();
obj.name = "Test";
console.log(obj.count);
```

## CMakeLists.txt 配置

```cmake
# AKI 框架头文件路径
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/aki/include
)

# 桥接源文件
set(BRIDGE_SOURCES
    my_bridge.h
    my_bridge.cpp
    my_aki_binding.cpp
)

# 添加到项目源文件
set(PROJECT_SOURCES
    main.cpp
    ${BRIDGE_SOURCES}
)

# 链接 AKI 库（如果提供了预编译库）
target_link_libraries(MyApp PRIVATE aki)
```

## oh-package.json5 配置

```json5
{
  "dependencies": {
    "aki": "1.0.0"
  }
}
```

## 常见注意事项

1. **JSBIND_METHOD 名称必须与 C++ 方法名一致**：不能使用不同的方法名
2. **JSBIND_ADDON 名称是 ArkTS import 的模块名**：需要唯一且不含特殊字符
3. **回调参数类型必须两端匹配**：C++ `std::function<void(int, std::string)>` 对应 ArkTS `(code: number, msg: string) => void`
4. **std::string ↔ string 转换使用 UTF-8**：确保编码一致
5. **静态方法在 ArkTS 侧直接通过类名调用**：不需要实例化