# harmonyShare（华为分享）— ArkTS API 参考

**来源**: https://developer.huawei.com/consumer/cn/doc/harmonyos-references/share-harmony-share

**更新时间**: 2026-05-26 14:48

**起始版本**: 5.0.0(12)

**模型约束**: 此模块的接口仅可在 Stage 模型下使用

**系统能力**: SystemCapability.Collaboration.HarmonyShare

---

## 导入模块

```typescript
import { harmonyShare } from '@kit.ShareKit';
```

---

## SharableErrorCode

拒绝分享回调时，提供拒绝原因，用户可收到系统通知消息。

**起始版本**: 5.0.3(15)

| 名称 | 值 | 说明 |
|------|---|------|
| NO_CONTENT_ERROR | 1 | 用于无内容分享场景 |
| NO_INTERNET_ERROR | 2 | 用于无网络场景 |
| DOWNLOAD_ERROR | 3 | 用于下载失败场景 |

---

## ReceivableErrorCode

拒绝沙箱接收回调时，提供拒绝原因。

**起始版本**: 6.0.0(20)

| 名称 | 值 | 说明 |
|------|---|------|
| NO_RECEIVABLE_ERROR | 1 | 用于当前无法接收数据的场景 |

---

## ShareResultCode

沙箱接收结果通知成功或失败原因。

**起始版本**: 6.0.0(20)

| 名称 | 值 | 说明 |
|------|---|------|
| SHARE_SUCCESS | 0 | 沙箱接收成功 |
| SEND_FAILED | 1 | 数据传输失败 |
| CANCEL_BY_SENDER | 2 | 发送端取消发送 |
| CANCEL_BY_RECEIVER | 3 | 接收端取消接收 |

---

## SharableTarget

华为分享事件触发后回调参数，可通过此参数跨端分享。

**起始版本**: 5.0.0(12)

### share(data: systemShare.SharedData): Promise<void>

跨端分享，使用 Promise 异步回调。

**起始版本**: 5.0.0(12)

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| data | systemShare.SharedData | 是 | 分享数据 |

**错误码**: 401 — 参数错误

### reject(error: SharableErrorCode): Promise<void>

拒绝本次分享，使用 Promise 异步回调。

**起始版本**: 5.0.3(15)

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| error | SharableErrorCode | 是 | 拒绝本次分享的原因，通过系统弹窗提示用户 |

**错误码**: 401 — 参数错误

### updateShareData(data: UpdatedData): Promise<void>

在分享数据未发送前，更新预览图。仅支持碰一碰分享功能。

**起始版本**: 6.0.0(20)

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| data | UpdatedData | 是 | 需要更新的数据信息 |

### clarifyNonShare(info: SharableErrorInfo): Promise<void>

告知用户当前界面无可分享内容，给出提示引导。仅支持碰一碰分享功能。

**起始版本**: 6.0.2(22)

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| info | SharableErrorInfo | 是 | 提示信息，告知用户无法分享的原因 |

---

## ReceivableTarget

沙箱接收事件触发后回调参数。

**起始版本**: 6.0.0(20)

### receive(receiveUri: string, callback: ReceiveCallback): Promise<void>

提供沙箱接收目录 uri，接收的文件保存至此目录下。

**起始版本**: 6.0.0(20)

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| receiveUri | string | 是 | 沙箱接收存放数据的目录（必须真实存在）。Share Kit 在传输开始前获取此目录授权，传输完成后自动撤销授权。建议使用已存在的空文件夹。 |
| callback | ReceiveCallback | 是 | 沙箱接收的回调 |

### reject(error: ReceivableErrorCode): Promise<void>

拒绝本次接收。

**起始版本**: 6.0.0(20)

---

## UpdatedData

华为分享事件发送的数据信息。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| thumbnailUri | string | 否 | 是 | 预览图的 uri |

---

## BaseCapabilityRegistry

华为分享事件注册基础配置。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| windowId | number | 否 | 否 | 窗口 id |

---

## SendCapabilityRegistry

华为分享事件窗口注册配置项。继承 BaseCapabilityRegistry。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| sendOnly | boolean | 否 | 是 | 是否仅支持发送数据。默认值：false，可同时接收分享数据。当双端设备均设置为 true 时，双向分享会被拦截。仅支持碰一碰分享功能。 |

---

## RecvCapability

沙箱接收支持的能力范围。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| utd | string | 否 | 否 | 统一数据类型，参考 @ohos.data.uniformTypeDescriptor |
| maxSupportedCount | number | 否 | 否 | 可接收文件的最大数量限制，仅允许设置大于 0 的整数 |

---

## RecvCapabilityRegistry

沙箱接收事件窗口注册配置项。继承 BaseCapabilityRegistry。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| capabilities | RecvCapability[] | 否 | 否 | 沙箱接收能力设置 |

---

## TransferBaseResults

沙箱接收时文件数据传输完成的回调函数。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| onResult | Callback<ShareResultCode> | 否 | 是 | 传输完成的回调函数 |

---

## ReceiveCallback

沙箱接收传输完成后回调函数。继承 TransferBaseResults。

**起始版本**: 6.0.0(20)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| onDataReceived | Callback<systemShare.SharedData> | 否 | 否 | 接收已保存至沙箱路径下的文件列表 |

---

## SharableErrorInfo

提示信息，告知用户无法分享的原因。

**起始版本**: 6.0.2(22)

| 名称 | 类型 | 只读 | 可选 | 说明 |
|------|------|------|------|------|
| message | string | 否 | 是 | 提示文案 |

---

## on('knockShare')

注册设备轻贴的事件监听。

**起始版本**: 5.0.0(12)

### 基础版本

```typescript
on(event: 'knockShare', callback: Callback<SharableTarget>): void
```

**参数**:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| event | string | 是 | 'knockShare'，设备轻贴时触发 |
| callback | Callback<SharableTarget> | 是 | 事件回调 |

**示例**:

```typescript
import { uniformTypeDescriptor as utd } from '@kit.ArkData';
import { systemShare, harmonyShare } from '@kit.ShareKit';

harmonyShare.on('knockShare', (sharableTarget: harmonyShare.SharableTarget) => {
  let shareData: systemShare.SharedData = new systemShare.SharedData({
    utd: utd.UniformDataType.PLAIN_TEXT,
    content: '这是一段文本内容'
  });
  sharableTarget.share(shareData);
});
```

### 带注册配置版本 (API 6.0.0(20))

```typescript
on(event: 'knockShare', capability: SendCapabilityRegistry, callback: Callback<SharableTarget>): void
```

**示例**:

```typescript
let capabilityRegistry: harmonyShare.SendCapabilityRegistry = {
  windowId: 999
};
harmonyShare.on('knockShare', capabilityRegistry, (sharableTarget: harmonyShare.SharableTarget) => {
  let shareData: systemShare.SharedData = new systemShare.SharedData({
    utd: utd.UniformDataType.PLAIN_TEXT,
    content: '这是一段文本内容'
  });
  sharableTarget.share(shareData);
});
```

---

## off('knockShare')

取消设备轻贴的事件监听。

**起始版本**: 5.0.0(12)

```typescript
// 基础版本
off(event: 'knockShare', callback?: Callback<SharableTarget>): void

// 带注册配置版本 (API 6.0.0(20))
off(event: 'knockShare', capability: SendCapabilityRegistry, callback?: Callback<SharableTarget>): void
```

**示例**:

```typescript
harmonyShare.off('knockShare');

// 带配置版本
harmonyShare.off('knockShare', capabilityRegistry);
```

---

## on('gesturesShare')

注册隔空传送的事件监听。

**起始版本**: 6.0.0(20)

```typescript
on(event: 'gesturesShare', callback: Callback<SharableTarget>): void
on(event: 'gesturesShare', capability: SendCapabilityRegistry, callback: Callback<SharableTarget>): void
```

---

## off('gesturesShare')

取消隔空传送的事件监听。

**起始版本**: 6.0.0(20)

---

## on('dataReceive')

注册沙箱接收事件监听。仅支持文件类型数据。

**起始版本**: 6.0.0(20)

**设备行为差异**: API version 22 及之前，仅 PC/2in1 可调用；从 API version 23 开始，PC/2in1、Tablet 均可使用。

```typescript
on(event: 'dataReceive', capability: RecvCapabilityRegistry, callback: Callback<ReceivableTarget>): void
```

**示例**:

```typescript
import { uniformTypeDescriptor as utd } from '@kit.ArkData';
import { systemShare, harmonyShare } from '@kit.ShareKit';
import { common } from '@kit.AbilityKit';

let capabilityRegistry: harmonyShare.RecvCapabilityRegistry = {
  windowId: 999,
  capabilities: [{
    utd: utd.UniformDataType.IMAGE,
    maxSupportedCount: 1
  }]
};

harmonyShare.on('dataReceive', capabilityRegistry, (receivableTarget: harmonyShare.ReceivableTarget) => {
  let context = this.getUIContext().getHostContext() as common.UIAbilityContext;
  receivableTarget.receive(context.filesDir, {
    onDataReceived: (sharedData: systemShare.SharedData) => {
      let sharedRecords = sharedData.getRecords();
      sharedRecords.forEach((record: systemShare.SharedRecord) => {
        // 处理分享数据
      });
    },
    onResult(resultCode: harmonyShare.ShareResultCode) {
      if (resultCode === harmonyShare.ShareResultCode.SHARE_SUCCESS) {
        // To do things
      }
    }
  });
});
```

---

## off('dataReceive')

取消沙箱接收的事件监听。

**起始版本**: 6.0.0(20)