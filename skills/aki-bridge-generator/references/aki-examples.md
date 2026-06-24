# AKI 桥接示例代码集合

---

## 示例 1： 简单方法桥接

### C++ 侧 (simple_bridge.h)

```cpp
#pragma once

#include <string>
#include "aki/jsbind.h"

class SimpleBridge {
public:
    static std::string greet(const std::string& name);
    static int add(int a, int b);
};
```

### C++ 侧 (simple_bridge.cpp)

```cpp
#include "simple_bridge.h"

std::string SimpleBridge::greet(const std::string& name) {
    return "Hello, " + name + "!";
}

int SimpleBridge::add(int a, int b) {
    return a + b;
}
```

### JSBinding (simple_aki_binding.cpp)

```cpp
#include "aki/jsbind.h"
#include "simple_bridge.h"

JSBIND_CLASS(SimpleBridge) {
    JSBIND_METHOD(greet);
    JSBIND_METHOD(add);
}

JSBIND_ADDON(simple_bridge, SimpleBridge);
```

### ArkTS 侧

```typescript
import { SimpleBridge } from 'simple_bridge';

const msg = SimpleBridge.greet('HarmonyOS');
console.log(msg);  // "Hello, HarmonyOS!"



const sum = SimpleBridge.add(3, 5);
console.log(sum);  // 8
```

---

## 示例 2: 回调函数桥接

### C++ 侧 (callback_bridge.h)

```cpp
#pragma once

#include <string>
#include <functional>
#include "aki/jsbind.h"

class CallbackBridge {
public:
    static void registerCallback(
        std::function<void(int resultCode, const std::string& message)> callback);
    static void triggerEvent(int code, const std::string& msg);

private:
    static std::function<void(int, std::string)> m_callback;
};
```

### C++ 侧 (callback_bridge.cpp)

```cpp
#include "callback_bridge.h"

std::function<void(int, std::string)> CallbackBridge::m_callback;

void CallbackBridge::registerCallback(
    std::function<void(int resultCode, const std::string& message)> callback) {
    m_callback = callback;
}

void CallbackBridge::triggerEvent(int code, const std::string& msg) {
    if (m_callback) {
        m_callback(code, msg);
    }
}
```

### JSBinding (callback_aki_binding.cpp)

```cpp
#include "aki/jsbind.h"
#include "callback_bridge.h"

JSBIND_CLASS(CallbackBridge) {
    JSBIND_METHOD(registerCallback);
    JSBIND_METHOD(triggerEvent);
}

JSBIND_ADDON(callback_bridge, CallbackBridge);
```

### ArkTS 侧

```typescript
import { CallbackBridge } from 'callback_bridge';

// 注册回调
CallbackBridge.registerCallback((resultCode: number, message: string) => {
    console.log(`Event received: code=${resultCode}, msg=${message}`);
});

// C++ 侧可随时触发事件
// 当 C++ 调用 triggerEvent(1, "Share completed") 时
// ArkTS 侧回调将被执行
```

---

## 示例 3: 碡一碰分享桥接（完整场景)

'

### C++ 侧 (share_bridge.h)

```cpp
#pragma once

#include <string>
#include <functional>
#include "aki/jsbind.h"

class ShareBridge {
public:
    // 发起碰一碰分享
 static bool startKnockShare(const std::string& filePath, const std::string& mimeType);

    // 更新预览
 static bool updatePreview(const std::string& imageData);

    // 注册分享结果回调
 static void registerShareResultCallback(
        std::function<void(int resultCode, const std::string& resultMsg)> callback);

    // 拒绝分享
 static bool rejectShare(int errorCode);

    // ArkTS → C++ 回调触发
 static void notifyShareResult(int resultCode, const std::string& resultMsg);

private:
    static std::function<void(int, std::string)> m_shareResultCallback;
};
```

### JSBinding (share_aki_binding.cpp)

```cpp
#include "aki/jsbind.h"
#include "share_bridge.h"

JSBIND_CLASS(ShareBridge) {
    JSBIND_METHOD(startKnockShare);
    JSBIND_METHOD(updatePreview);
    JSBIND_METHOD(registerShareResultCallback);
    JSBIND_METHOD(rejectShare);
    JSBIND_METHOD(notifyShareResult);
}

 }

JSBIND_ADDON(share_bridge, ShareBridge);
```

### ArkTS 侧 (ShareBridgeProxy.ets)
```typescript
import { harmonyShare } from '@kit.ShareKit';
import { systemShare } from '@kit.ShareKit';
import { ShareBridge } from 'share_bridge';

export class ShareBridgeProxy {
  private shareTarget: harmonyShare.SharableTarget | null = null;

 null;

  static instance: ShareBridgeProxy | null = null;

  static getInstance(): ShareBridgeProxy {
    if (!ShareShareBridgeProxy.instance) {
      ShareBridgeProxy.instance = new ShareBridgeProxy();
    }
    return ShareBridgeProxy.instance;
  }

  registerQtCallback(): void {
    ShareBridge.registerShareResultCallback((resultCode: number, resultMsg: string) => {
      console.info(`Share result: code=${resultCode}, msg=${resultMsg}`);
 null  }

  async startKnockShare(filePath: string, mimeType: string): Promise<void> {
    if (!this.shareTarget) {
      console.error('No shareTarget available');
      return;
 null  }

 try {
      const sharedData = new systemShare.SharedData({
        text: filePath,
 mimeType: mimeType
      });
      await this.shareTarget.share(sharedData);
      ShareBridge.notifyShareResult(0, 'Share started');
 null  } catch (err) {
      ShareBridge.notifyShareResult(-1, `Share failed: ${err}`);
 });
    }
  }
}