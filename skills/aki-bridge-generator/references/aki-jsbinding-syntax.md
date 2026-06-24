# AKI JSBinding 声明语法参考

## JSBIND_CLASS

声明要桥接的 C++ 类：

```cpp
JSBIND_CLASS(ClassName) {
    // 内部声明方法、属性、构造函数等
}
```

**参数**：
- `ClassName`：C++ 类名，必须与实际定义的类名完全一致

**限制**：
- 类必须在使用 JSBIND_CLASS 之前已完整定义
- 类名不能包含命名空间（需使用实际类名）

## JSBIND_METHOD

声明要暴露给 ArkTS 的 C++ 方法：

```cpp
JSBIND_CLASS(MyBridge) {
    JSBIND_METHOD(methodName);
}
```

**参数**：
- `methodName`：C++ 方法名，必须与类中定义的方法名完全一致

**支持的方法类型**：
- 静态方法：`static void methodName()`
- 实例方法：`void methodName()`
- 有返回值方法：`int methodName()`
- 有参数方法：`void methodName(int a, std::string b)`
- 重载方法：不支持，需使用不同方法名

**ArkTS 侧调用**：
- 静态方法：`MyBridge.methodName()`
- 实例方法：`const obj = new MyBridge(); obj.methodName()`

## JSBIND_CONSTRUCTOR

声明 C++ 类的构造函数：

```cpp
JSBIND_CLASS(MyBridge) {
    JSBIND_CONSTRUCTOR(int value, std::string name);
}
```

**参数**：
- 构造函数参数类型列表，必须与 C++ 构造函数签名匹配

**ArkTS 侧使用**：
```typescript
const obj = new MyBridge(42, "test");
```

## JSBIND_PROPERTY

声明 C++ 类的属性（成员变量）：

```cpp
JSBIND_CLASS(MyBridge) {
    JSBIND_PROPERTY(propertyName);
}
```

**参数**：
- `propertyName`：C++ 公开成员变量名

**ArkTS 侧使用**：
```typescript
obj.propertyName = "new value";
console.log(obj.propertyName);
```

## JSBIND_ADDON

注册 N-API addon 模块：

```cpp
JSBIND_ADDON(addonName, ClassName);
```

**参数**：
- `addonName`：ArkTS import 使用的模块名（字符串标识符）
- `ClassName`：要暴露的主 C++ 类名

**ArkTS 侧导入**：
```typescript
import { ClassName } from 'addonName';
```

**示例**：
```cpp
JSBIND_ADDON(share_bridge, ShareBridge);
// ArkTS: import { ShareBridge } from 'share_bridge';
```

## JSBIND_ENUM

声明 C++ 枚举类型：

```cpp
JSBIND_ENUM(ErrorCodes) {
    JSBIND_ENUM_VALUE(NO_CONTENT_ERROR, 1);
    JSBIND_ENUM_VALUE(NO_INTERNET_ERROR, 2);
    JSBIND_ENUM_VALUE(DOWNLOAD_ERROR, 3);
}
```

**ArkTS 侧使用**：
```typescript
ErrorCodes.NO_CONTENT_ERROR  // 1
ErrorCodes.NO_INTERNET_ERROR // 2
```

## JSBIND_ENUM_VALUE

在 JSBIND_ENUM 内声明枚举值：

```cpp
JSBIND_ENUM_VALUE(NAME, VALUE);
```

## 多类桥接

一个 addon 可以桥接多个类：

```cpp
JSBIND_CLASS(ShareBridge) {
    JSBIND_METHOD(startKnockShare);
    JSBIND_METHOD(rejectShare);
}

JSBIND_CLASS(FileHelper) {
    JSBIND_METHOD(readFile);
    JSBIND_METHOD(writeFile);
}

JSBIND_ADDON(my_addon, ShareBridge, FileHelper);
```

ArkTS 侧：
```typescript
import { ShareBridge, FileHelper } from 'my_addon';
```

## 完整语法示例

```cpp
#include "aki/jsbind.h"
#include "share_bridge.h"

// 枚举桥接
JSBIND_ENUM(ShareErrorCode) {
    JSBIND_ENUM_VALUE(NO_CONTENT, 1);
    JSBIND_ENUM_VALUE(NO_NETWORK, 2);
}

// 类桥接
JSBIND_CLASS(ShareBridge) {
    JSBIND_METHOD(startKnockShare);
    JSBIND_METHOD(updatePreview);
    JSBIND_METHOD(rejectShare);
    JSBIND_METHOD(notifyShareResult);
}

// addon 注册
JSBIND_ADDON(share_bridge, ShareBridge);
```

## 常见语法错误

| 错误 | 原因 | 修复 |
|------|------|------|
| `JSBIND_CLASS(ShareBridge)` 编译报错 | 类定义在 JSBIND_CLASS 之后 | 确保 #include 头文件在 JSBIND_CLASS 之前 |
| `JSBIND_METHOD(methodName)` 找不到方法 | 方法名与 C++ 定义不一致 | 检查方法名拼写，必须完全匹配 |
| ArkTS import 找不到 addon | JSBIND_ADDON 名称与 import 不一致 | 确保 addonName 与 ArkTS import 字符串匹配 |
| 构造函数参数不匹配 | JSBIND_CONSTRUCTOR 参数与 C++ 构造函数签名不一致 | 检查参数类型列表 |
| 重载方法桥接失败 | AKI 不支持方法重载 | 使用不同方法名区分重载版本 |