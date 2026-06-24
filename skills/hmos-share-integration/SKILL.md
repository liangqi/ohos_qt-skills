---
name: hmos-share-integration
description: 集成鸿蒙碰一碰分享和手势分享（隔空传送）功能到Qt鸿蒙应用。通过AKI框架将harmonyShare（华为分享）API桥接到Qt C++层，实现碰一碰/手势分享文件分享、链接分享、沙箱接收(dataReceive)。包含ArkTS侧Share API调用、AKI JSBinding声明、Qt C++桥接类设计、SafetyCallback回调。所有代码基于实际开发验证(knocksharedemo)。
---

# 鸿蒙碰一碰分享与手势分享集成工具

将鸿蒙的 `harmonyShare`（华为分享）API 通过 AKI 框架桥接到 Qt C++ 层，实现碰一碰分享、手势分享（隔空传送）、沙箱接收功能。

**适用场景**：
- Qt 鸿蒙应用需要实现碰一碰文件传输（PC/2in1 发送端，`on('knockShare')`）
- Qt 鸿蒙应用需要实现手势分享（隔空传送）文件传输（PC/2in1 发送端，`on('gesturesShare')`）
- Qt 鸿蒙应用需要实现碰一碰/手势分享链接分享（PC/2in1 发送端）
- Qt 鸿蒙应用需要实现沙箱接收(`on('dataReceive')`)（PC/2in1/tablet 接收端，碰一碰和手势分享共用同一接收接口）
- Qt C++ 层需要调用鸿蒙 Share Kit 的系统 API

**核心架构**：Qt (UI) → AKI (Bridge via bindFunction + SafetyCallback) → HarmonyOS Share Kit APIs

**实际验证项目**：knocksharedemo（所有教训均来自真实开发踩坑）

**重要说明**：`on/off('knockShare')` 和 `on/off('gesturesShare')` 的接口参数和代码逻辑完全相同，仅事件名不同。接收端碰一碰和手势分享共用 `on/off('dataReceive')`，无需区分来源。

---

## 执行策略（必须遵守）

### 原则 0：功能优先（最高优先级，不可违反）

**不管怎么改代码，第一优先级都是保证程序能完成预期功能。不能为了修 bug 或追崩溃而把功能给改没了。**

- 任何修改必须保留完整的业务流程和功能逻辑
- "stub" 和 "空实现" 仅作为临时诊断手段，不可作为最终方案
- 修改后必须验证：点击按钮 → 碰一碰注册走通 → 分享/接收功能正常
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

## 前置条件

### 必须已完成的步骤

1. **Qt 鸿蒙工程已创建**（使用 `create-qt-app` skill）
2. **AKI 框架已集成到项目**（使用 `aki-bridge-generator` skill）
3. **DevEco MCP 工具链已配置**（用于构建和测试）

### 必须确认的配置

| 检查项 | 说明 |
|--------|------|
| Qt SDK 路径 | CMAKE_PREFIX_PATH 已正确配置 |
| targetSdkVersion | **必须** = `6.0.0(20)`（硬约束） |
| compatibleSdkVersion | **必须** = `6.0.0(20)` |
| AKI 桥接代码 | share_bridge 已通过 AKI 注册 |
| module.json5 权限 | 已添加 `ohos.permission.SHARE` |
| oh-package.json5 | **绝不能**声明 `@kit.ShareKit`（系统 Kit，SDK 自动解析） |
| modules.xml | entry.iml 和 qEmbeddedUiExtensionHost.iml 已注册 |

---

## 关键教训（开发踩坑总结）

> 以下所有教训来自 knocksharedemo 实际开发，**必须严格遵守**。

### 教训 1：RecvCapabilityRegistry 类型（NOT ReceivableTargetConfig）

`harmonyShare.on('dataReceive')` 的第二个参数类型是 `RecvCapabilityRegistry`，继承自 `BaseCapabilityRegistry`。

**类型结构**：
```typescript
// BaseCapabilityRegistry（继承基类）
interface BaseCapabilityRegistry {
  windowId: number;  // 必填，不可选
}

// RecvCapabilityRegistry（继承 BaseCapabilityRegistry）
interface RecvCapabilityRegistry extends BaseCapabilityRegistry {
  capabilities: RecvCapability[];  // 必填，不可选
}

// RecvCapability
interface RecvCapability {
  utd: string;           // 必填，统一数据类型
  maxSupportedCount: number;  // 必填，必须 > 0
}
```

**正确写法**：
```typescript
let recvCapabilityRegistry: harmonyShare.RecvCapabilityRegistry = {
  windowId: windowIdFromQt,
  capabilities: [{
    utd: uniformTypeDescriptor.UniformDataType.IMAGE,
    maxSupportedCount: 5
  }, {
    utd: uniformTypeDescriptor.UniformDataType.FILE,
    maxSupportedCount: 5
  }]
};
harmonyShare.on('dataReceive', recvCapabilityRegistry, callback);
```

**常见错误**：
- ❌ 传入空 `capabilities` 数组 → 报错
- ❌ `maxSupportedCount` 设为 0 → 报错
- ❌ 使用虚构类型名 `ReceivableTargetConfig` → 不存在
- ❌ 缺少 `windowId` → 报错（继承自 BaseCapabilityRegistry）

### 教训 2：ReceivableTarget 回调流程（NOT SharableData）

`on('dataReceive')` 回调接收的是 `ReceivableTarget`，**不是** `SharableData`。你必须主动调用 `receivableTarget.receive()` 才能真正接收数据。

**完整回调流程**：
```typescript
harmonyShare.on('dataReceive', recvCapabilityRegistry,
  (receivableTarget: harmonyShare.ReceivableTarget) => {
    // 第一步：调用 receive() 发起接收
    receivableTarget.receive(receiveUri, {
      // 第二步： onDataReceived 回调获取 SharedData
      onDataReceived: (sharedData: systemShare.SharedData) => {
        let records = sharedData.getRecords();  // 获取内容记录数组
        records.forEach((record: systemShare.SharedRecord) => {
          // 处理每条记录
        });
      },
      // 第三步： onResult 回调获取传输结果
      onResult: (resultCode: harmonyShare.ShareResultCode) => {
        if (resultCode === harmonyShare.ShareResultCode.SHARE_SUCCESS) {
          // 接收成功
        }
      }
    });
  }
);
```

**ReceiveCallback 类型结构**：
```typescript
// ReceiveCallback（继承 TransferBaseResults）
interface ReceiveCallback extends TransferBaseResults {
  onDataReceived: Callback<systemShare.SharedData>;  // 必填
}

// TransferBaseResults
interface TransferBaseResults {
  onResult?: Callback<ShareResultCode>;  // 可选
}
```

**常见错误**：
- ❌ 以为回调直接传入 SharableData → 实际传入 ReceivableTarget
- ❌ 不调用 `receive()` → 数据不会被接收
- ❌ `receiveUri` 传入不存在目录 → 报错（必须真实存在）
- ❌ 忽略 `onDataReceived` → 必填字段

### 教训 3：off('dataReceive') 传入 RecvCapabilityRegistry 参数（可新构造）

`harmonyShare.off('dataReceive', capability: RecvCapabilityRegistry)` — **capability 参数是必填的**，不是可选的。传入的 `RecvCapabilityRegistry` 的 `windowId` 和 `capabilities` 必须与 `on()` 注册时一致。

**两种写法均可**：

```typescript
// 写法A：保存成员变量，off 时传同一对象引用
private recvCapabilityRegistry: harmonyShare.RecvCapabilityRegistry = {
  windowId: windowId,
  capabilities: RECV_CAPABILITIES
};
harmonyShare.on('dataReceive', this.recvCapabilityRegistry, callback);
harmonyShare.off('dataReceive', this.recvCapabilityRegistry);

// 写法B：off 时新构造对象（windowId 和 capabilities 值与 on 时一致）
harmonyShare.on('dataReceive', recvCapabilityRegistry, callback);
harmonyShare.off('dataReceive', {
  windowId: windowId,
  capabilities: RECV_CAPABILITIES
} as harmonyShare.RecvCapabilityRegistry);
```

**常见错误**：
- ❌ `harmonyShare.off('dataReceive')` 不传参数 → 编译或运行时错误
- ❌ 传入的 capabilities 与注册时的 UTD 不一致 → 取消失败

### 教训 4：windowId 必须从 Qt 侧获取

windowId **绝不能**从 ArkTS 侧获取（如 `windowStage.getMainWindowSync().id`）。Qt 应用必须通过 Qt 侧获取真实 windowId，然后通过 SafetyCallback 传递给 ArkTS 侧。

**Qt 侧获取 windowId**：
```cpp
#include <QtOhosExtras>

int windowId = QtOhosExtras::tryGetNativeWindowId(window->windowHandle());
```

**通过 SafetyCallback 传递**：
```cpp
// SafetyCallback 将 windowId 作为 int 参数传递到 ArkTS
ShareBridge::notifyWindowId(windowId);
```

**ArkTS 侧接收 windowId**：
```typescript
ShareBridge.registerWindowIdCallback((windowId: number) => {
  ShareBridgeProxy.getInstance().setWindowId(windowId);
});
```

**原因**：ArkTS 侧 `windowStage.getMainWindowSync().id` 返回的是鸿蒙窗口管理器的窗口 ID，而 Qt 应用有自己的窗口层级。Qt 侧通过 `QtOhosExtras` 获取的才是与 Share Kit 匹配的真正窗口 ID。两者不一致会导致 `on('knockShare')` 和 `on('dataReceive')` 注册失败。

### 教训 5：@kit.ShareKit 是系统 Kit，NOT ohpm 包

`@kit.ShareKit` 是 HarmonyOS SDK 内置的系统 Kit，**绝不能**在 `oh-package.json5` 的 dependencies 中声明。

**错误做法**：
```json5
// ❌ 错误 — oh-package.json5 中声明 @kit.ShareKit
{
  "dependencies": {
    "@kit.ShareKit": "???"
  }
}
```
→ 导致 `ohpm install` 退出码 255，因为 ohpm 仓库中不存在此包。

**正确做法**：
```json5
// ✅ 正确 — oh-package.json5 中不声明 @kit.ShareKit
{
  "name": "entry",
  "version": "1.0.0",
  "description": "Knock Share Demo",
  "main": "",
  "author": "",
  "license": "",
  "dependencies": {}
}
```

ArkTS 代码中的 `import { harmonyShare } from '@kit.ShareKit'` 由 SDK 自动解析，无需 ohpm 安装。

### 教训 6：JSON5 严格兼容性

DevEco Studio 使用 fastjson2 解析器，**只支持标准 JSON 格式**。所有 `.json5` 配置文件（`build-profile.json5`、`module.json5`、`oh-package.json5` 等）必须是合法的标准 JSON。

**禁止的 JSON5 特性**：
- ❌ 尾部逗号（trailing commas）：`{ "a": 1, }` → 解析失败
- ❌ 单引号字符串：`{ 'name': 'entry' }` → 解析失败
- ❌ 注释：`// comment` 或 `/* comment */` → 解析失败

**正确写法**：
```json
{
  "name": "entry",
  "version": "1.0.0",
  "dependencies": {}
}
```

### 教训 7：modules.xml 注册

DevEco Studio 的 IntelliJ IDE 通过 `.idea/modules.xml` 识别模块。如果 `entry.iml` 和 `qEmbeddedUiExtensionHost.iml` 未注册，DevEco 不会将它们显示为模块。

**必须添加的条目**：
```xml
<!-- .idea/modules.xml -->
<component name="ProjectModuleManager">
  <modules>
    <module fileurl="file://$PROJECT_DIR$/.idea/modules/entry.iml"
            filepath="$PROJECT_DIR$/.idea/modules/entry.iml" />
    <module fileurl="file://$PROJECT_DIR$/.idea/modules/qEmbeddedUiExtensionHost.iml"
            filepath="$PROJECT_DIR$/.idea/modules/qEmbeddedUiExtensionHost.iml" />
  </modules>
</component>
```

### 教训 8：receiveDir 使用 context.filesDir

ShareBridgeProxy 需要 `receiveDir`（应用沙箱文件目录）用于 `ReceivableTarget.receive()` 的 `receiveUri` 参数。必须在 `QAbility.onWindowStageCreate` 中设置，使用 `this.context.filesDir`。

**QAbility.onWindowStageCreate 中设置**：
```typescript
// QAbility.ets（继承 UIAbility）
onWindowStageCreate(windowStage: Window.WindowStage) {
  ShareBridgeProxy.getInstance().setReceiveDir(this.context.filesDir);
  ShareBridgeProxy.getInstance().init();
}
```

**使用 receiveDir**：
```typescript
// ShareBridgeProxy 中
private receiveDir: string = '';

setReceiveDir(dir: string): void {
  this.receiveDir = dir;
}

// 接收时使用 fileUri.getUriFromPath 转换为 URI
receivableTarget.receive(fileUri.getUriFromPath(this.receiveDir), receiveCallback);
```

**注意**：官方 demo 使用 `this.context.filesDir`，不是 `cacheDir`。`fileUri.getUriFromPath()` 将路径转为 URI 格式。

### 教训 9：targetSdkVersion = 6.0.0(20) 硬约束

`on('dataReceive')` API 起始版本为 6.0.0(20)，低于此版本不可用。

**必须配置**：
- `targetSdkVersion` = `6.0.0(20)`
- `compatibleSdkVersion` = `6.0.0(20)`

**配置位置**：`build-profile.json5` 和 `AppScope/app.json5`

```json
{
  "app": {
    "compatibleSdkVersion": "6.0.0(20)",
    "targetSdkVersion": "6.0.0(20)"
  }
}
```

### 教训 10：设备类型限制

`on('dataReceive')` 的设备支持情况：

| API version | 支持设备 | 不支持设备 |
|-------------|---------|-----------|
| ≤ 22 | PC / 2in1 | phone、tablet → 返回错误码 801 |
| ≥ 23 | PC / 2in1 / tablet | phone → 返回错误码 801 |

**knocksharedemo 的 deviceTypes 配置**：
```json
{
  "module": {
    "deviceTypes": ["tablet", "2in1"]
  }
}
```

**注意**：phone 设备的碰一碰分享走不同流程（手机碰手机无需 windowId，且不支持沙箱接收 `dataReceive`）。

### 教训 11：SharableTarget.getInfo() 不可用

`SharableTarget.getInfo()` 是 Beta 特性，起始版本 **26.0.0**，当前 SDK 版本（6.0.0(20)）不可使用。不要尝试调用此方法。

### 教训 12：RecvCapability UTD 必须使用 uniformTypeDescriptor 枚举

`harmonyShare.on('dataReceive')` 的 capabilities 中 `utd` 字段必须使用 `uniformTypeDescriptor.UniformDataType` 枚举（来自 `@kit.ArkData`），不能使用硬编码字符串。

**常见文件类型对应的 UTD 枚举**：
| 文件格式 | 硬编码字符串（不推荐） | uniformTypeDescriptor 枚举（推荐） |
|---------|---------------------|----------------------------------|
| txt | `general.text` | `UniformDataType.PLAIN_TEXT` |
| pdf | `general.pdf` | `UniformDataType.PDF` |
| 图片/视频 | `general.media` | `UniformDataType.MEDIA` |
| 通用文件 | `general.file` | `UniformDataType.FILE` |

**推荐写法**：
```typescript
import { uniformTypeDescriptor as utd } from '@kit.ArkData';

const RECV_CAPABILITIES: harmonyShare.RecvCapability[] = [
  { utd: utd.UniformDataType.PLAIN_TEXT, maxSupportedCount: 5 },
  { utd: utd.UniformDataType.PDF, maxSupportedCount: 5 },
  { utd: utd.UniformDataType.MEDIA, maxSupportedCount: 5 },
  { utd: utd.UniformDataType.FILE, maxSupportedCount: 5 },
];
```

### 教训 13：harmonyShare.on/off 是幂等接口，无需状态守卫

`harmonyShare.on('knockShare')` 和 `harmonyShare.on('dataReceive')` 是幂等接口，重复调用不会产生副作用。因此不需要 `isKnockListening` / `isDataReceiving` 等状态变量，也不需要 `if (!this.isListening)` 之类的守卫条件。直接调用即可。

**简化写法**：
```typescript
registerKnockReceiveImpl(windowId: number): boolean {
  harmonyShare.on('dataReceive', { windowId, capabilities: RECV_CAPABILITIES }, callback);
  return true;
}

unregisterKnockReceiveImpl(windowId: number): boolean {
  harmonyShare.off('dataReceive', { windowId, capabilities: RECV_CAPABILITIES });
  return true;
}
```

### 教训 14：ReceiveCallback 不需要类型断言

`receivableTarget.receive(receiveUri, callback)` 的 callback 参数直接传 `{ onDataReceived, onResult }` 即可，不需要 `as harmonyShare.ReceiveCallback` 类型断言。官方 demo 也没有使用类型断言。

### 教训 15：JS→C→QtMainThread 数据流必须通过消息队列

JS 线程通过 AKI notify 函数回调 C++ 时处于 JS 线程，**绝不能**在 JS 线程触发 Qt UI 操作（如 `m_logEdit->append()`）。必须通过消息队列（mutex 保护 + QTimer drain）将数据转发到 QtMainThread。

**实现模式**：
```cpp
// share_bridge.h — JS线程安全的 enqueue
void enqueue(const std::string& msg);  // mutex 保护，push 到 m_msgQueue

// JS线程调用的 postNotify* 只做 fprintf + enqueue，不触 m_logCallback
void ShareBridge::postNotifyDataReceiveFile(const std::string& fileName, const std::string& filePath) {
    fprintf(stderr, "[NotifyDataReceiveFile] name=%s, path=%s\n", fileName.c_str(), filePath.c_str());
    enqueue("[FileReceived] name=" + fileName + ", path=" + filePath);
}

// QtMainThread 通过 QTimer drain 队列并更新 UI
std::vector<std::string> ShareBridge::drainQueue() {
    std::lock_guard<std::mutex> lock(m_queueMutex);
    std::vector<std::string> result;
    result.swap(m_msgQueue);
    return result;
}
```

```cpp
// main.cpp — QTimer 定期 drain
QTimer *drainTimer = new QTimer(this);
drainTimer->setInterval(100);
connect(drainTimer, &QTimer::timeout, this, [this, bridge]() {
    auto msgs = bridge->drainQueue();
    for (const auto &m : msgs) {
        m_logEdit->append(QString::fromStdString(m) + "\n");
    }
});
drainTimer->start();
```

---

## 核心流程（碰一碰/手势分享发送端）

碰一碰和手势分享（隔空传送）的发送端流程完全相同，仅事件名不同：

```
碰一碰触发 → on('knockShare')    → ArkTS 侧获取 SharableTarget
手势分享触发 → on('gesturesShare') → ArkTS 侧获取 SharableTarget
    → AKI bindFunction/SafetyCallback 回调 C++ 侧（通知 Qt 分享事件发生）
    → Qt UI 显示分享确认界面
    → 用户确认分享
    → Qt C++ 调用 ShareBridge::startKnockShare()
    → AKI 桥接到 ArkTS 侧 ShareBridgeProxy.startKnockShare()
    → ArkTS 调用 SharableTarget.share(sharedData)
    → 鸿蒙系统执行跨端分享
    → 分享结果回调 → ArkTS → AKI SafetyCallback → Qt C++ 更新 UI
```

## 核心流程（沙箱接收端）

```
注册 dataReceive 监听 → 鸿蒙系统回调 on('dataReceive') → ArkTS 侧获取 ReceivableTarget
    → ArkTS 调用 receivableTarget.receive(receiveDir, callback)
    → onDataReceived 回调 → 获取 SharedData.getRecords()
    → AKI SafetyCallback 回调 C++ 侧（通知 Qt 接收数据）
    → Qt UI 显示接收到的文件/数据
    → onResult 回调 → ArkTS → AKI SafetyCallback → Qt C++ 更新状态
```

---

## Step 1: 确认需求与场景

使用 `clarify` 工具向用户确认：

### 确认点 1：分享角色

```
问题：请选择要实现的分享角色
选项：
  1. 发送端（碰一碰/手势分享） - 设备碰一碰或隔空传送后发送文件/链接到对端
  2. 接收端（沙箱接收） - 通过 dataReceive 接收对端分享的文件
  3. 两者都要 - 同时支持发送和接收
```

### 确认点 2：分享类型（仅发送端需要确认）

```
问题：请选择要实现的分享功能（发送端）
选项：
  1. 碰一碰文件分享 - 碰一碰后传输文件
  2. 碰一碰链接分享 - 碰一碰后分享链接/文本内容
  3. 手势分享（隔空传送）文件分享 - 隔空传送后传输文件
  4. 手势分享（隔空传送）链接分享 - 隔空传送后分享链接/文本内容
  3. 两者都要 - 同时支持文件和链接分享
```

### 确认点 3：Qt UI 类型

```
问题：请确认 Qt 应用 UI 类型
选项：
  1. QWidget - 传统 Widgets UI
  2. QML - Qt Quick/QML UI
```

### 硨认点 4：目标设备类型

```
问题：请确认目标设备类型
选项：
  1. tablet + 2in1 - 碑一碰沙箱接收可用
  2. 仅 phone - 不支持 dataReceive，需用不同方案
  3. 全设备 - 需分别处理
```

### 硨认点 5：工程目录

```
问题：请确认 Qt 鸿蒙工程目录路径
示例：C:\code\MyShareApp
```

---

## Step 2: 设计桥接方案

### 2.1 API 路径设计（发送端）

| Qt 侧方法 | AKI 桥接方向 | ArkTS 侧方法 | 鸿蒙 API |
|-----------|-------------|-------------|---------|
| `ShareBridge::startKnockShare(...)` | C++ → ArkTS | `ShareBridgeProxy.startKnockShare()` | `SharableTarget.share()` |
| `ShareBridge::rejectShare(errorCode)` | C++ → ArkTS | `ShareBridgeProxy.rejectShare()` | `SharableTarget.reject()` |
| `ShareBridge::updateShareData(...)` | C++ → ArkTS | `ShareBridgeProxy.updateShareData()` | `SharableTarget.updateShareData()` |
| `ShareBridge::notifyWindowId(windowId)` | C++ → ArkTS (SafetyCallback) | `ShareBridgeProxy.setWindowId()` | — |
  | 回调：碰一碰/手势分享事件通知 | ArkTS → C++ (SafetyCallback) | `ShareBridge.notifyKnockEvent()` | — |
| 回调：分享结果通知 | ArkTS → C++ (SafetyCallback) | `ShareBridge.notifyShareResult()` | — |

### 2.2 API 路径设计（接收端）

| Qt 侧方法 | AKI 桥接方向 | ArkTS 侧方法 | 鸿蒙 API |
|-----------|-------------|-------------|---------|
| `ShareBridge::registerDataReceive()` | C++ → ArkTS | `ShareBridgeProxy.registerDataReceiveListener()` | `harmonyShare.on('dataReceive', recvCapabilityRegistry, callback)` |
| `ShareBridge::unregisterDataReceive()` | C++ → ArkTS | `ShareBridgeProxy.unregisterDataReceiveListener()` | `harmonyShare.off('dataReceive', recvCapabilityRegistry)` |
| 回调：数据接收通知 | ArkTS → C++ (SafetyCallback) | `ShareBridge.notifyDataReceived()` | — |
| 回调：接收结果通知 | ArkTS → C++ (SafetyCallback) | `ShareBridge.notifyReceiveResult()` | — |

### 2.3 数据流设计（发送端）

```
Qt 获取 windowId → SafetyCallback 传递到 ArkTS → ShareBridgeProxy 存储 windowId
    → 注册 knockShare/gesturesShare 监听（使用 windowId 构造 SendCapabilityRegistry）
    → 碰一碰/手势分享触发 → SharableTarget 回调 → SafetyCallback 通知 Qt
    → Qt 用户确认 → ShareBridge.startKnockShare() → AKI → ShareBridgeProxy.startKnockShare()
    → SharableTarget.share() → 鸿蒙跨端分享 → 结果回调 → SafetyCallback → Qt
```

### 2.4 数据流设计（接收端）

```
Qt 获取 windowId → SafetyCallback 传递到 ArkTS → ShareBridgeProxy 存储 windowId
    → ShareBridgeProxy 使用 windowId 构造 RecvCapabilityRegistry
    → 注册 dataReceive 监听（传入 RecvCapabilityRegistry）
    → ReceivableTarget 回调 → receivableTarget.receive(receiveDir, callback)
    → onDataReceived → SharedData.getRecords() → SafetyCallback 通知 Qt
    → onResult → ShareResultCode → SafetyCallback 通知 Qt
```

---

## Step 3: 创建 ArkTS 侧代码

### 3.1 创建 ShareBridgeProxy.ets（完整版）

路径：`entry/src/main/ets/share/ShareBridgeProxy.ets`

```typescript
import { harmonyShare, systemShare } from '@kit.ShareKit';
import { ShareBridge } from 'share_bridge';
import { BusinessError } from '@kit.BasicServicesKit';
import { uniformTypeDescriptor as utd } from '@kit.ArkData';
import { fileUri } from '@kit.CoreFileKit';
import { common } from '@kit.AbilityKit';

export class ShareBridgeProxy {
  private shareTarget: harmonyShare.SharableTarget | null = null;
  private recvCapabilityRegistry: harmonyShare.RecvCapabilityRegistry | null = null;
  private static instance: ShareBridgeProxy | null = null;

  static getInstance(): ShareBridgeProxy {
    if (!ShareBridgeProxy.instance) {
      ShareBridgeProxy.instance = new ShareBridgeProxy();
    }
    return ShareBridgeProxy.instance;
  }

  // ======== windowId 和 receiveDir 管理 ========

  setReceiveDir(dir: string): void {
    this.receiveDir = dir;
  }

  private receiveDir: string = '';

  // ======== 碰一碰/手势分享发送端 ========

  registerKnockShareListener(windowId: number): void {
    harmonyShare.on('knockShare', { windowId: windowId, sendOnly: false },
      (target: harmonyShare.SharableTarget) => {
        this.shareTarget = target;
        ShareBridge.notifyKnockEvent();
      });
  }

  unregisterKnockShareListener(windowId: number): void {
    harmonyShare.off('knockShare', { windowId: windowId, sendOnly: false });
  }

  // 碰一碰/手势分享文件分享
  async startKnockFileShare(
    filePath: string,
    mimeType: string,
    fileName: string,
    thumbnailUri: string
  ): Promise<boolean> {
    if (!this.shareTarget) {
      console.error('[ShareBridge] No shareTarget available');
      ShareBridge.notifyShareResult(-1, 'No knock event');
      return false;
    }

    try {
      // 教训：文件分享必须使用 utd + uri，NOT files 数组
      const fileSuffix = '.' + fileName.split('.').pop();
      const fileUtd = utd.getUniformDataTypeByFilenameExtension(fileSuffix);

      const shareRecord: systemShare.SharedRecord = {
        utd: fileUtd,
        uri: fileUri.getUriFromPath(filePath),
        thumbnailUri: thumbnailUri ? fileUri.getUriFromPath(thumbnailUri) : '',
        title: fileName,
        description: ''
      };

      const sharedData = new systemShare.SharedData(shareRecord);
      await this.shareTarget.share(sharedData);
      ShareBridge.notifyShareResult(0, 'Share started');
      return true;
    } catch (err) {
      const e = err as BusinessError;
      console.error(`[ShareBridge] Share failed: code=${e.code}, msg=${e.message}`);
      ShareBridge.notifyShareResult(e.code ?? -1, e.message ?? 'Unknown error');
      return false;
    }
  }

  // 碰一碰/手势分享链接分享
  async startKnockLinkShare(
    linkUrl: string,
    title: string,
    description: string,
    thumbnailUri: string
  ): Promise<boolean> {
    if (!this.shareTarget) {
      console.error('[ShareBridge] No shareTarget available');
      ShareBridge.notifyShareResult(-1, 'No knock event');
      return false;
    }

    try {
      const shareRecord: systemShare.SharedRecord = {
        utd: utd.UniformDataType.HYPERLINK,
        content: linkUrl,
        thumbnailUri: thumbnailUri ? fileUri.getUriFromPath(thumbnailUri) : '',
        title: title,
        description: description
      };

      const sharedData = new systemShare.SharedData(shareRecord);
      await this.shareTarget.share(sharedData);
      ShareBridge.notifyShareResult(0, 'Link share started');
      return true;
    } catch (err) {
      const e = err as BusinessError;
      console.error(`[ShareBridge] Link share failed: code=${e.code}`);
      ShareBridge.notifyShareResult(e.code ?? -1, e.message ?? 'Unknown error');
      return false;
    }
  }

  // 拒绝分享
  async rejectShare(errorCode: number): Promise<void> {
    if (!this.shareTarget) return;
    try {
      await this.shareTarget.reject(errorCode as harmonyShare.SharableErrorCode);
      ShareBridge.notifyShareResult(-2, 'Share rejected');
    } catch (err) {
      console.error(`[ShareBridge] Reject failed: ${err}`);
    }
  }

  // 更新预览数据（碰一碰/手势分享支持）
  async updateShareData(thumbnailUri: string): Promise<boolean> {
    if (!this.shareTarget) return false;
    try {
      const updatedData: harmonyShare.UpdatedData = {
        thumbnailUri: fileUri.getUriFromPath(thumbnailUri)
      };
      await this.shareTarget.updateShareData(updatedData);
      return true;
    } catch (err) {
      console.error(`[ShareBridge] Update share data failed: ${err}`);
      return false;
    }
  }

  // ======== 沙箱接收端 ========

  private static RECV_CAPABILITIES: harmonyShare.RecvCapability[] = [
    { utd: utd.UniformDataType.PLAIN_TEXT, maxSupportedCount: 5 },
    { utd: utd.UniformDataType.PDF, maxSupportedCount: 5 },
    { utd: utd.UniformDataType.MEDIA, maxSupportedCount: 5 },
    { utd: utd.UniformDataType.FILE, maxSupportedCount: 5 },
  ];

  registerDataReceiveListener(windowId: number): void {
    this.recvCapabilityRegistry = {
      windowId: windowId,
      capabilities: ShareBridgeProxy.RECV_CAPABILITIES
    };
    harmonyShare.on('dataReceive', this.recvCapabilityRegistry,
      (receivableTarget: harmonyShare.ReceivableTarget) => {
        const receiveUri = fileUri.getUriFromPath(this.receiveDir);
        receivableTarget.receive(receiveUri, {
          onDataReceived: (sharedData: systemShare.SharedData) => {
            const records = sharedData.getRecords();
            for (let i = 0; i < records.length; i++) {
              const record = records[i];
              ShareBridge.notifyDataReceiveFile(record.title ?? 'unknown', record.uri ?? '');
            }
          },
          onResult: (resultCode: harmonyShare.ShareResultCode) => {
            ShareBridge.notifyResult(resultCode, `Receive result: ${resultCode}`);
          }
        });
      });
  }

  // off('dataReceive') 传入新构造的 RecvCapabilityRegistry（与 on 的 capabilities 一致）
  unregisterDataReceiveListener(windowId: number): void {
    harmonyShare.off('dataReceive', {
      windowId: windowId,
      capabilities: ShareBridgeProxy.RECV_CAPABILITIES
    } as harmonyShare.RecvCapabilityRegistry);
  }
}
```

### 3.2 创建 QAbility.ets（初始化）

路径：`entry/src/main/ets/entryability/QAbility.ets`

```typescript
import { UIAbility, AbilityConstant, Want } from '@kit.AbilityKit';
import { ShareBridgeProxy } from '../share/ShareBridgeProxy';
import { ShareBridge } from 'share_bridge';

export class QAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    ShareBridgeProxy.getInstance().setReceiveDir(this.context.filesDir);
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index', (err, data) => {
      if (err.code) {
        console.error(`[QAbility] loadContent failed: ${err.message}`);
        return;
      }
    });
  }

  onDestroy(): void | Promise<void> {
    ShareBridgeProxy.getInstance().unregisterKnockShareListener();
    ShareBridgeProxy.getInstance().unregisterDataReceiveListener();
  }
}
```

---

## Step 4: 创建 AKI JSBinding 声明

### 4.1 ShareBridge C++ 桥接类头文件

路径：`entry/src/main/cpp/share_bridge.h`

```cpp
#pragma once

#include <string>
#include <functional>
#include <vector>
#include "aki/jsbind.h"

class ShareBridge {
public:
    // 发送端方法
    static bool startKnockFileShare(const std::string& filePath,
                                    const std::string& mimeType,
                                    const std::string& fileName,
                                    const std::string& thumbnailUri);
    static bool startKnockLinkShare(const std::string& linkUrl,
                                    const std::string& title,
                                    const std::string& description,
                                    const std::string& thumbnailUri);
    static bool rejectShare(int errorCode);
    static bool updateShareData(const std::string& thumbnailUri);

    // 接收端方法
    static bool registerDataReceive();
    static bool unregisterDataReceive();

    // SafetyCallback：Qt → ArkTS
    static void notifyWindowId(int windowId);

    // SafetyCallback：ArkTS → Qt
    static void notifyKnockEvent();
    static void notifyShareResult(int resultCode, const std::string& resultMsg);
    static void notifyDataReceived(const std::string& fileUris);
    static void notifyReceiveResult(int resultCode);

    // 注册 Qt 侧回调
    static void registerShareResultCallback(
        std::function<void(int, std::string)> callback);
    static void registerKnockEventCallback(
        std::function<void()> callback);
    static void registerDataReceivedCallback(
        std::function<void(std::string)> callback);
    static void registerReceiveResultCallback(
        std::function<void(int)> callback);

private:
    static std::function<void(int, std::string)> m_shareResultCallback;
    static std::function<void()> m_knockEventCallback;
    static std::function<void(std::string)> m_dataReceivedCallback;
    static std::function<void(int)> m_receiveResultCallback;
};
```

### 4.2 ShareBridge C++ 实现

路径：`entry/src/main/cpp/share_bridge.cpp`

```cpp
#include "share_bridge.h"

std::function<void(int, std::string)> ShareBridge::m_shareResultCallback;
std::function<void()> ShareBridge::m_knockEventCallback;
std::function<void(std::string)> ShareBridge::m_dataReceivedCallback;
std::function<void(int)> ShareBridge::m_receiveResultCallback;

bool ShareBridge::startKnockFileShare(const std::string& filePath,
                                      const std::string& mimeType,
                                      const std::string& fileName,
                                      const std::string& thumbnailUri) {
    return true;
}

bool ShareBridge::startKnockLinkShare(const std::string& linkUrl,
                                      const std::string& title,
                                      const std::string& description,
                                      const std::string& thumbnailUri) {
    return true;
}

bool ShareBridge::rejectShare(int errorCode) {
    return true;
}

bool ShareBridge::updateShareData(const std::string& thumbnailUri) {
    return true;
}

bool ShareBridge::registerDataReceive() {
    return true;
}

bool ShareBridge::unregisterDataReceive() {
    return true;
}

void ShareBridge::notifyWindowId(int windowId) {
    // 此方法由 Qt 侧通过 SafetyCallback 调用
    // 通知 ArkTS 侧 ShareBridgeProxy.setWindowId()
}

void ShareBridge::notifyKnockEvent() {
    if (m_knockEventCallback) {
        m_knockEventCallback();
    }
}

void ShareBridge::notifyShareResult(int resultCode, const std::string& resultMsg) {
    if (m_shareResultCallback) {
        m_shareResultCallback(resultCode, resultMsg);
    }
}

void ShareBridge::notifyDataReceived(const std::string& fileUris) {
    if (m_dataReceivedCallback) {
        m_dataReceivedCallback(fileUris);
    }
}

void ShareBridge::notifyReceiveResult(int resultCode) {
    if (m_receiveResultCallback) {
        m_receiveResultCallback(resultCode);
    }
}

void ShareBridge::registerShareResultCallback(
    std::function<void(int, std::string)> callback) {
    m_shareResultCallback = callback;
}

void ShareBridge::registerKnockEventCallback(
    std::function<void()> callback) {
    m_knockEventCallback = callback;
}

void ShareBridge::registerDataReceivedCallback(
    std::function<void(std::string)> callback) {
    m_dataReceivedCallback = callback;
}

void ShareBridge::registerReceiveResultCallback(
    std::function<void(int)> callback) {
    m_receiveResultCallback = callback;
}
```

### 4.3 AKI JSBinding 注册

路径：`entry/src/main/cpp/share_aki_binding.cpp`

```cpp
#include "aki/jsbind.h"
#include "share_bridge.h"

JSBIND_CLASS(ShareBridge) {
    JSBIND_METHOD(startKnockFileShare);
    JSBIND_METHOD(startKnockLinkShare);
    JSBIND_METHOD(rejectShare);
    JSBIND_METHOD(updateShareData);
    JSBIND_METHOD(registerDataReceive);
    JSBIND_METHOD(unregisterDataReceive);
    JSBIND_METHOD(notifyWindowId);
    JSBIND_METHOD(notifyKnockEvent);
    JSBIND_METHOD(notifyShareResult);
    JSBIND_METHOD(notifyDataReceived);
    JSBIND_METHOD(notifyReceiveResult);
    JSBIND_METHOD(registerShareResultCallback);
    JSBIND_METHOD(registerKnockEventCallback);
    JSBIND_METHOD(registerDataReceivedCallback);
    JSBIND_METHOD(registerReceiveResultCallback);
}

JSBIND_ADDON(share_bridge, ShareBridge);
```

---

## Step 5: Qt 侧集成

### 5.1 获取 windowId 并传递到 ArkTS（教训4）

```cpp
#include <QMainWindow>
#include <QtOhosExtras>
#include "share_bridge.h"

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    MainWindow(QWidget *parent = nullptr) : QMainWindow(parent) {
        // 教训4：windowId 必须从 Qt 侧获取
        int windowId = QtOhosExtras::tryGetNativeWindowId(this->windowHandle());
        ShareBridge::notifyWindowId(windowId);

        // 注册回调
        ShareBridge::registerKnockEventCallback([this]() {
            onKnockEvent();
        });
        ShareBridge::registerShareResultCallback([this](int code, const std::string& msg) {
            onShareResult(code, msg);
        });
        ShareBridge::registerDataReceivedCallback([this](const std::string& uris) {
            onDataReceived(uris);
        });
        ShareBridge::registerReceiveResultCallback([this](int code) {
            onReceiveResult(code);
        });
    }

    // 碰一碰/手势分享事件回调
    void onKnockEvent() {
        qDebug() << "Knock event detected! Show share confirmation UI";
    }

    // 发起文件分享
    void startFileShare(const QString& filePath, const QString& thumbnailPath) {
        ShareBridge::startKnockFileShare(
            filePath.toStdString(),
            "",  // mimeType 由 ArkTS 侧通过 utd 推断
            QFileInfo(filePath).fileName().toStdString(),
            thumbnailPath.toStdString()
        );
    }

    // 发起链接分享
    void startLinkShare(const QString& url, const QString& title) {
        ShareBridge::startKnockLinkShare(
            url.toStdString(),
            title.toStdString(),
            "",
            ""
        );
    }

    // 分享结果回调
    void onShareResult(int resultCode, const std::string& resultMsg) {
        qDebug() << "Share result:" << resultCode << resultMsg;
    }

    // 接收数据回调（教训2）
    void onDataReceived(const std::string& fileUris) {
        QStringList uris = QString::fromStdString(fileUris).split('|');
        qDebug() << "Received files:" << uris;
    }

    // 接收结果回调
    void onReceiveResult(int resultCode) {
        qDebug() << "Receive result:" << resultCode;
    }
};
```

### 5.2 注册/取消 dataReceive 监听

```cpp
// 注册沙箱接收监听
void registerDataReceive() {
    ShareBridge::registerDataReceive();
}

// 取消沙箱接收监听（教训3：ArkTS 侧会传入保存的 recvCapabilityRegistry）
void unregisterDataReceive() {
    ShareBridge::unregisterDataReceive();
}
```

---

## Step 6: 配置权限和依赖

### 6.1 module.json5 权限配置

路径：`entry/src/main/module.json5`

```json
{
  "module": {
    "name": "entry",
    "type": "entry",
    "deviceTypes": ["tablet", "2in1"],
    "targetSdkVersion": "6.0.0(20)",
    "compatibleSdkVersion": "6.0.0(20)",
    "requestPermissions": [
      {
        "name": "ohos.permission.SHARE"
      },
      {
        "name": "ohos.permission.FILE_READ_PERSISTENT"
      }
    ]
  }
}
```

**教训10**：deviceTypes 使用 `["tablet", "2in1"]`（phone 不支持 dataReceive API version ≤22，返回错误码 801）。

### 6.2 oh-package.json5（教训5）

路径：`entry/oh-package.json5`

```json
{
  "name": "entry",
  "version": "1.0.0",
  "description": "Knock Share Demo",
  "main": "",
  "author": "",
  "license": "",
  "dependencies": {}
}
```

**绝不能**在 dependencies 中声明 `@kit.ShareKit`。它是系统 Kit，由 SDK 自动解析，ohpm 仓库中不存在此包，声明会导致 `ohpm install` 退出码 255。

### 6.3 build-profile.json5（教训6 + 教训9）

路径：`build-profile.json5`

```json
{
  "app": {
    "signingConfigs": [],
    "compatibleSdkVersion": "6.0.0(20)",
    "targetSdkVersion": "6.0.0(20)",
    "products": [
      {
        "name": "default",
        "signingConfig": "default"
      }
    ]
  },
  "modules": [
    {
      "name": "entry",
      "srcPath": "./entry",
      "targets": [
        {
          "name": "default",
          "applyToProducts": ["default"]
        }
      ]
    }
  ]
}
```

**教训6**：所有 `.json5` 文件必须是合法标准 JSON。禁止尾部逗号、单引号、注释。

### 6.4 modules.xml 注册（教训7）

路径：`.idea/modules.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectModuleManager">
    <modules>
      <module fileurl="file://$PROJECT_DIR$/.idea/modules/entry.iml"
              filepath="$PROJECT_DIR$/.idea/modules/entry.iml" />
      <module fileurl="file://$PROJECT_DIR$/.idea/modules/qEmbeddedUiExtensionHost.iml"
              filepath="$PROJECT_DIR$/.idea/modules/qEmbeddedUiExtensionHost.iml" />
    </modules>
  </component>
</project>
```

### 6.5 CMakeLists.txt 更新

在 `entry/src/main/cpp/CMakeLists.txt` 中添加 share_bridge 源文件：

```cmake
set(PROJECT_SOURCES
  main.cpp
  share_bridge.h
  share_bridge.cpp
  share_aki_binding.cpp
)
```

---

## 鸿蒙 Share API 参考（核心接口）

### harmonyShare 模块

导入：
```typescript
import { harmonyShare, systemShare } from '@kit.ShareKit';
```

**教训5**：`@kit.ShareKit` 是系统 Kit，不在 oh-package.json5 中声明。

### SharableTarget（碰一碰/手势分享回调参数）

碰一碰或手势分享事件触发后回调获得的跨端分享对象。

| 方法 | 说明 | 起始版本 |
|------|------|---------|
| `share(data: SharedData)` | 跨端分享 | 5.0.0(12) |
| `reject(error: SharableErrorCode)` | 拒绝本次分享 | 5.0.3(15) |
| `updateShareData(data: UpdatedData)` | 更新预览图（碰一碰/手势分享） | 6.0.0(20) |
| `clarifyNonShare(info: SharableErrorInfo)` | 告知用户无可分享内容（碰一碰/手势分享） | 6.0.2(22) |
| `getInfo()` | **Beta，起始版本 26.0.0，不可用** | 26.0.0(Beta) |

**教训11**：`SharableTarget.getInfo()` 当前 SDK 版本不可用（起始版本 26.0.0）。

### SharableErrorCode

| 名称 | 值 | 说明 | 起始版本 |
|------|---|------|---------|
| NO_CONTENT_ERROR | 1 | 无内容分享场景 | 5.0.3(15) |
| NO_INTERNET_ERROR | 2 | 无网络场景 | 5.0.3(15) |
| DOWNLOAD_ERROR | 3 | 下载失败场景 | 5.0.3(15) |

### ReceivableErrorCode

| 名称 | 值 | 说明 | 起始版本 |
|------|---|------|---------|
| NO_RECEIVABLE_ERROR | 1 | 当前无法接收数据 | 6.0.0(20) |

### ShareResultCode

| 名称 | 值 | 说明 | 起始版本 |
|------|---|------|---------|
| SHARE_SUCCESS | 0 | 沙箱接收成功 | 6.0.0(20) |
| SEND_FAILED | 1 | 数据传输失败 | 6.0.0(20) |
| CANCEL_BY_SENDER | 2 | 发送端取消 | 6.0.0(20) |
| CANCEL_BY_RECEIVER | 3 | 接收端取消 | 6.0.0(20) |

### ReceivableTarget（沙箱接收回调参数）

**教训2**：回调接收的是 `ReceivableTarget`，**不是** `SharableData`。必须调用 `receive()` 才能获取数据。

| 方法 | 说明 | 起始版本 |
|------|------|---------|
| `receive(receiveUri: string, callback: ReceiveCallback)` | 发起沙箱接收 | 6.0.0(20) |
| `reject(error: ReceivableErrorCode)` | 拒绝本次接收 | 6.0.0(20) |

### RecvCapabilityRegistry（教训1）

**类型结构**（继承 BaseCapabilityRegistry）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| windowId | number | 是 | 继承自 BaseCapabilityRegistry |
| capabilities | RecvCapability[] | 是 | 接收能力设置 |

### RecvCapability

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| utd | string | 是 | 统一数据类型 |
| maxSupportedCount | number | 是 | 最大接收数量，必须 > 0 |

### SendCapabilityRegistry（继承 BaseCapabilityRegistry）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| windowId | number | 是 | 继承自 BaseCapabilityRegistry |
| sendOnly | boolean | 否 | 是否仅发送，默认 false |

### ReceiveCallback（继承 TransferBaseResults）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| onDataReceived | Callback\<SharedData\> | 是 | 接收数据回调 |
| onResult | Callback\<ShareResultCode\> | 否 | 传输完成回调（继承自 TransferBaseResults） |

### UpdatedData

| 字段 | 类型 | 可选 | 说明 | 起始版本 |
|------|------|------|------|---------|
| thumbnailUri | string | 是 | 预览图 URI | 6.0.0(20) |

### 事件监听

| 事件名 | 参数类型 | 说明 | 起始版本 |
|--------|---------|------|---------|
| `on('knockShare')` | 基础版：callback；PC版：SendCapabilityRegistry + callback | 碰一碰分享事件 | 5.0.0(12) |
| `off('knockShare')` | 基础版：可选 callback；PC版：SendCapabilityRegistry | 取消碰一碰监听 | 5.0.0(12) |
| `on('gesturesShare')` | 基础版：callback；PC版：SendCapabilityRegistry + callback | 手势分享（隔空传送）事件 | 6.0.0(20) |
| `off('gesturesShare')` | 基础版：可选 callback；PC版：SendCapabilityRegistry | 取消手势分享监听 | 6.0.0(20) |
| `on('dataReceive')` | **RecvCapabilityRegistry** + callback | 沙箱接收事件 | 6.0.0(20) |
| `off('dataReceive')` | **RecvCapabilityRegistry**（必填） | 取消沙箱接收监听 | 6.0.0(20) |
| `on('gesturesShare')` | SendCapabilityRegistry + callback | 手势分享事件 | 6.0.0(20) |

---

## 碰一碰/手势分享文件分享最佳实践要点

1. **权限声明**：module.json5 必须声明 `ohos.permission.SHARE` 和 `ohos.permission.FILE_READ_PERSISTENT`
2. **windowId 来源**：必须从 Qt 侧通过 `QtOhosExtras::tryGetNativeWindowId()` 获取，**不能**从 ArkTS 侧获取
3. **SendCapabilityRegistry**：PC/2in1 端的 `on('knockShare')` 和 `on('gesturesShare')` 都必须传入 `SendCapabilityRegistry`（含 windowId），参数和逻辑完全相同
4. **SharableTarget 获取**：碰一碰/手势分享事件回调参数即为 SharableTarget，必须保存引用
5. **3秒超时**：收到碰一碰/手势分享回调后，必须在 3 秒内调用 `sharableTarget.share()`，否则分享可能失败
6. **文件分享数据格式**：使用 `systemShare.SharedRecord` 构造，包含 `utd`（通过 `getUniformDataTypeByFilenameExtension` 获取）和 `uri`（通过 `fileUri.getUriFromPath` 获取）
7. **不要混合分享**：不要在同一个 SharedData 中混合文件分享（uri）和内容分享（content）
8. **预览图**：优先使用 `thumbnailUri`（无大小限制），避免使用 `thumbnail`（限制 32KB）
9. **错误处理**：所有 Share API 调用应捕获 BusinessError，错误码 401 表示参数错误
10. **off 传参**：`off('knockShare')` 和 `off('gesturesShare')` 在 PC 端都必须传入 `SendCapabilityRegistry`，可保存为成员变量或新构造

---

## 沙箱接收(dataReceive)最佳实践要点

1. **RecvCapabilityRegistry 类型**：必须使用 `RecvCapabilityRegistry`（含 windowId + capabilities），不能用虚构类型名
2. **capabilities 非空**：`capabilities` 数组不能为空，每个 RecvCapability 的 `maxSupportedCount` 必须 > 0
3. **ReceivableTarget 回调**：回调参数是 `ReceivableTarget`，必须调用 `receive()` 才能接收数据
4. **receiveUri 真实存在**：`receive()` 的 `receiveUri` 必须指向真实存在的沙箱目录，建议使用 `context.cacheDir`
5. **ReceiveCallback.onDataReceived 必填**：不能省略
6. **off('dataReceive') 必须传参**：必须传入与 on() 相同的 `RecvCapabilityRegistry`，保存为成员变量
7. **设备限制**：API version ≤22 仅 PC/2in1 可用，≥23 支持 tablet。其他设备返回错误码 801
8. **receiveDir 设置时机**：在 `QAbility.onCreate` 中通过 `ShareBridgeProxy.setReceiveDir(this.context.cacheDir)` 设置

---

## 碰一碰/手势分享链接分享最佳实践要点

1. **utd 类型**：链接分享使用 `utd.UniformDataType.HYPERLINK`
2. **content 字段**：传入 App Linking 链接（如 `https://www.example.com?videoIndex=0`）
3. **App Linking 配置**：对端需要配置 App Linking 以实现一键直达
4. **thumbnailUri**：推荐使用 `thumbnailUri` 设置预览图
5. **domainVerify**：module.json5 中 App Linking 配置的 `domainVerify` 必须为 `true`

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| `ohpm install` 退出码 255 | **教训5**：删除 oh-package.json5 中的 `@kit.ShareKit` 依赖 |
| `on('dataReceive')` 报错类型不匹配 | **教训1**：使用 `RecvCapabilityRegistry` 类型（含 windowId + capabilities） |
| `on('dataReceive')` 回调参数不是数据 | **教训2**：回调参数是 `ReceivableTarget`，必须调用 `receive()` |
| `off('dataReceive')` 无法取消监听 | **教训3**：必须传入 `RecvCapabilityRegistry` 参数，保存为成员变量 |
| `on('dataReceive')` 返回错误码 801 | **教训10**：API ≤22 仅 PC/2in1 支持，≥23 支持 tablet |
| windowId 不匹配导致注册失败 | **教训4**：windowId 必须从 Qt 侧 `QtOhosExtras::tryGetNativeWindowId()` 获取 |
| DevEco Studio 不显示模块 | **教训7**：检查 `.idea/modules.xml` 是否注册了 entry.iml |
| .json5 文件解析失败 | **教训6**：确保是合法标准 JSON，无尾部逗号、单引号、注释 |
| 分享数据被丢弃或无效类型 | 不要在同一个 SharedData 中混合文件(uri)和内容(content) |
| SharableTarget.getInfo() 调用失败 | **教训11**：Beta 特性起始版本 26.0.0，当前不可用 |
| 碰一碰/手势分享超过 3 秒失败 | 收到回调后必须在 3 秒内调用 `share()` |
| 接收端 receiveDir 无效 | **教训8**：在 QAbility.onCreate 设置 `ShareBridgeProxy.setReceiveDir(context.cacheDir)` |
| 预览图模糊 | 使用 `thumbnailUri` 替代 `thumbnail`（32KB 限制） |
| Qt QString 传到 ArkTS 变乱码 | 使用 `QString::toStdString()`，确保 UTF-8 编码 |

---

## 关键约束

**必须**：
- Qt 侧所有数据类型转换为 AKI 支持类型后再桥接
- oh-package.json5 **绝不能**声明 `@kit.ShareKit` 依赖（系统 Kit 由 SDK 自动解析）
- 项目 **targetSdkVersion** 和 **compatibleSdkVersion** 设置为 `6.0.0(20)`
- windowId 从 Qt 侧 `QtOhosExtras::tryGetNativeWindowId()` 获取，通过 SafetyCallback 传递
- `RecvCapabilityRegistry` 的 `capabilities` 数组非空，`maxSupportedCount` > 0
- `off('dataReceive')` 必须传入 `RecvCapabilityRegistry` 参数（保存为成员变量）
- `ReceivableTarget.receive()` 的 `receiveUri` 必须指向真实存在的沙箱目录
- `ReceiveCallback.onDataReceived` 是必填字段
- `ShareBridgeProxy.setReceiveDir()` 在 `QAbility.onCreate` 中调用
- `.idea/modules.xml` 注册 entry.iml 和 qEmbeddedUiExtensionHost.iml
- 所有 `.json5` 文件必须是合法标准 JSON（无尾部逗号、单引号、注释）
- knockShare/gesturesShare 监听在 Ability onCreate 注册，onDestroy 取消
- 所有 Share API 调用捕获 BusinessError
- SharableTarget 引用在分享完成前不要释放
- JSBIND_ADDON 名称与 ArkTS import 字符串完全匹配
- SDK 组件（ets、js、native、previewer、toolchains）从 OpenHarmony SDK 目录获取

**禁止**：
- 在 oh-package.json5 dependencies 中声明 `@kit.ShareKit`
- 从 ArkTS 侧获取 windowId（如 `windowStage.getMainWindowSync().id`）
- 使用虚构类型名 `ReceivableTargetConfig`（不存在）
- 以为 `on('dataReceive')` 回调直接传入 SharableData（实际传入 ReceivableTarget）
- 不调用 `ReceivableTarget.receive()` 就期望接收数据
- `off('dataReceive')` 不传 `RecvCapabilityRegistry` 参数
- 在 `.json5` 文件中使用尾部逗号、单引号、注释
- 在同一个 SharedData 中混合文件分享(uri)和内容分享(content)
- 调用 `SharableTarget.getInfo()`（Beta，起始版本 26.0.0）
- 直接在 Qt C++ 侧调用鸿蒙系统 API（必须通过 AKI 桥接）
- 将 Qt 类型（QString/QByteArray）直接传入 AKI 桥接方法
- 从 hms/ 目录获取 SDK 组件的 oh-uni-package.json

---

## API 版本兼容性速查

| API | 起始版本 | 约束 |
|-----|---------|------|
| `harmonyShare.on('knockShare')` | 5.0.0(12) | 手机端无需 windowId |
| `harmonyShare.on('knockShare')` with SendCapabilityRegistry | 6.0.0(20) | PC/2in1 端需 windowId |
| `harmonyShare.on('gesturesShare')` | 6.0.0(20) | 手势分享（隔空传送） |
| `harmonyShare.on('gesturesShare')` with SendCapabilityRegistry | 6.0.0(20) | PC/2in1 端需 windowId |
| `SharableTarget.share()` | 5.0.0(12) | 3秒超时 |
| `SharableTarget.reject()` | 5.0.3(15) | — |
| `SharableTarget.updateShareData()` | 6.0.0(20) | 碰一碰/手势分享 |
| `SharableTarget.clarifyNonShare()` | 6.0.2(22) | 碰一碰/手势分享 |
| `harmonyShare.on('dataReceive')` | 6.0.0(20) | API≤22: PC/2in1; API≥23: PC/2in1+tablet |
| `harmonyShare.on('gesturesShare')` | 6.0.0(20) | — |
| `SharableTarget.getInfo()` | 26.0.0(Beta) | **不可用** |

---

## 相关资源

- AKI 框架仓库: https://gitcode.com/CPF-ApplicationTPC/aki
- 鸿蒙 Share API 参考: https://developer.huawei.com/consumer/cn/doc/harmonyos-references/share-harmony-share
- 碰一碰文件分享最佳实践: https://developer.huawei.com/consumer/cn/doc/best-practices/bpta-application-knock-file-share
- 碰一碰链接分享最佳实践: https://developer.huawei.com/consumer/cn/doc/best-practices/bpta-application-knock-video-share
- QtOhosExtras 文档: Qt 鸿蒙适配层提供 `tryGetNativeWindowId()` 方法
