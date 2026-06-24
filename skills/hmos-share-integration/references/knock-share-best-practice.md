# 碰一碰文件分享 — 最佳实践

**来源**: https://developer.huawei.com/consumer/cn/doc/best-practices/bpta-application-knock-file-share

**更新时间**: 2026-05-18 08:55

---

## 概述

随着消费者终端设备不断增加，不同设备间进行文本分享（链接、文本等）和文件分享（图片、视频、文档等）已成为用户日常生活中不可或缺的需求。HarmonyOS 通过 Share Kit（分享服务）提供便捷的分享功能，其中"碰一碰"分享功能使用户能够轻松实现跨设备分享。本文重点介绍应用如何实现碰一碰文件分享。

---

## 特性体验

目前 HarmonyOS 6.0.0 Beta1 及以上版本的手机和 PC/2in1 支持两种触碰形式：手机碰手机和手机碰 PC/2in1。

**说明**: 手机与手机碰一碰对华为账号无要求，而手机与 PC/2in1 碰一碰则需登录同一华为账号方可进行分享。

| 操作 | 手机碰手机 | 手机碰PC/2in1 |
|------|-----------|--------------|
| 手机发送 | 通过手机顶部相碰触发，文件被设备接收，接收端将媒体文件存储到图库中，非媒体文件存储到文件管理器中 | 通过手机顶部与PC/2in1窗口相碰触发，文件应被窗口所属的应用接收，统一存储入沙箱文件中 |
| 手机接收 | 通过手机顶部与PC/2in1窗口相碰触发，文件被手机设备接收，接收端将媒体文件存储到图库中，非媒体文件存储到文件管理器中 | — |

---

## 实现原理

碰一碰文件分享基于华为分享服务，通过手机与手机碰一碰或手机与 PC/2in1 屏幕碰一碰实现文件的跨端传输。应用需实现监听方法 `on('knockShare')`，用户触发碰一碰后即可分享文件至对方设备。文件接收则由分享服务按照规则处理，存储于图库或文件管理中。

PC/2in1 设备除了可以默认碰一碰将文件保存到文件管理中，应用还可以注册监听文件接收接口 `on('dataReceive')` 方法，手机分享的文件将存储于应用沙箱目录下。

---

## 开发步骤

### 发起分享

#### 分享数据构建

在分享数据时，分享发起方需要构建 `SharedRecord`。在文件分享的场景中，发起方在构造此参数时，**必须传入 uri 和 utd 这两个属性**。

**说明**:
- `uri` 是指要分享的文件 URI，而非文件路径。例如沙箱路径 `context.fileDir`，应通过 `fileUri.getUriFromPath()` 获取其 URI。
- `utd` 是当前文件的标准化数据类型，需要传入准确的值，以便系统匹配精确的目标应用。推荐使用 `uniformTypeDescriptor.getUniformDataTypeByFilenameExtension()` 方法，通过给定的文件后缀名查询标准化数据类型的 ID。

```typescript
public immersiveCallback(target: harmonyShare.SharableTarget) {
  let fileShare = AppStorage.get('KnockFileShare_fileShare') as number[];
  let videoDataList = AppStorage.get('KnockFileShare_videoDataList') as FileData[];
  if (!fileShare || fileShare.length === 0) {
    return;
  }
  let shareData: systemShare.SharedData = new systemShare.SharedData(this.getShareRecord(videoDataList[fileShare[0]]));
  for (let i = 1; i < fileShare.length; i++) {
    try {
      shareData.addRecord(this.getShareRecord(videoDataList[fileShare[i]]));
    } catch (e) {
      hilog.error(0x0000, 'KnockFileShare', `addRecord failed ${JSON.stringify(e)}`);
    }
  }
  target.share(shareData);
}

getShareRecord(data: FileData): systemShare.SharedRecord {
  let suffix = '.' + data.url.split('.').pop();
  let utd = uniformTypeDescriptor.getUniformDataTypeByFilenameExtension(suffix);
  return {
    utd: utd,
    uri: data.url,
    thumbnailUri: data.thumbnail,
    title: data.name,
    description: data.description
  };
}
```

#### 分享注册

华为分享模块提供了碰一碰分享事件的监听方法 `on('knockShare')`。在回调中调用分享数据构建方法，并通过 `sharableTarget.share()` 方法传输文件数据。

分享模块同样提供了取消监听的方法 `off('knockShare')`，当应用不需要碰一碰分享或离开页面时，应及时调用取消监听。

**注意**: PC 端的碰一碰事件监听和取消监听需要传入窗口的 ID。

```typescript
// 手机端监听
public immersiveListening() {
  if (canIUse('SystemCapability.Collaboration.HarmonyShare')) {
    harmonyShare.on('knockShare', (target: harmonyShare.SharableTarget) => {
      this.immersiveCallback(target);
    });
  }
}

// PC端监听（需要传入windowId）
public immersiveListeningPC() {
  if (canIUse('SystemCapability.Collaboration.HarmonyShare')) {
    window.getLastWindow(this.context).then((data) => {
      let mainWindowID: number = data.getWindowProperties().id;
      harmonyShare.on('knockShare', { windowId: mainWindowID }, (target: harmonyShare.SharableTarget) => {
        this.immersiveCallback(target);
      });
    });
  }
}

// 取消监听（手机端）
public immersiveDisableListening() {
  if (canIUse('SystemCapability.Collaboration.HarmonyShare')) {
    harmonyShare.off('knockShare');
  }
}

// 取消监听（PC端）
public immersiveDisableListeningPC() {
  if (canIUse('SystemCapability.Collaboration.HarmonyShare')) {
    window.getLastWindow(this.context).then((data) => {
      let mainWindowID: number = data.getWindowProperties().id;
      harmonyShare.off('knockShare', { windowId: mainWindowID });
    });
  }
}
```

### 接收文件

华为分享模块提供了 `harmonyShare.on('dataReceive')` 方法，用于实现应用沙箱接收文件的事件监听。**当前接口仅在 2in1 设备类型可以正常调用，其他设备类型会返回 801 错误码**。

PC/2in1 应用需要传入当前应用的窗口 ID，以及 `capabilities` 属性（表示当前应用支持接收的文件标准化数据类型及其最大接收数量，**该属性不能传入空数组**）。

在 `dataReceive` 回调中，通过 `receiveTarget.receive()` 传入应用接收文件的沙箱路径。当接收到文件后触发 `onDataReceived` 回调，通过 `shareData.getRecords()` 获取分享数据。接收结束后响应 `onResult` 回调，通过 `resultCode` 判断是否成功。

```typescript
public dataReceiveListeningPC() {
  if (!canIUse('SystemCapability.Collaboration.HarmonyShare')) {
    return;
  }
  window.getLastWindow(this.context).then((data) => {
    let mainWindowID: number = data.getWindowProperties().id;
    harmonyShare.on('dataReceive', {
      windowId: mainWindowID,
      capabilities: [
        { utd: uniformTypeDescriptor.UniformDataType.MEDIA, maxSupportedCount: 5 },
        { utd: uniformTypeDescriptor.UniformDataType.FILE, maxSupportedCount: 5 }
      ]
    }, (receiveTarget: harmonyShare.ReceivableTarget) => {
      receiveTarget.receive(fileUri.getUriFromPath(this.context.filesDir), {
        onDataReceived: (shareData: systemShare.SharedData) => {
          let shareRecords = shareData.getRecords();
          shareRecords.forEach(async (record: systemShare.SharedRecord) => {
            if (!record.uri) return;
            // 处理接收到的文件
          });
        },
        onResult(resultCode: harmonyShare.ShareResultCode) {
          if (resultCode === harmonyShare.ShareResultCode.SHARE_SUCCESS) {
            hilog.info(0x0000, 'KnockFileShare', 'receive file success');
          }
        }
      });
    });
  });
}
```

---

## 系统拦截策略

碰一碰分享接收端接收数据时遵循统一规则，详情参考目标设备接收分享数据一步直达体验。

---

## 不同类型分享数据构建

碰一碰文件分享需要关注文件分享类型，在发起分享时作为参数传入。系统提供标准化数据类型（UTD）解决跨设备传输中的数据类型模糊问题。

- 当传入的 `utd` 为 `uniformTypeDescriptor.UniformDataType.IMAGE` 且文件确认为图片文件时，接收端会默认将其存储在图库中
- 当传入的 `utd` 为 `uniformTypeDescriptor.UniformDataType.FILE` 时，文件会默认存储到文件管理中

### 常用 UTD 类型对照表

| 后缀名 | UTD-ID | MIMEType | 说明 |
|--------|---------|----------|------|
| .png | general.png | image/png | PNG图片 |
| .jpg/.jpeg/.jpe | general.jpeg | image/jpeg | JPEG图片 |
| .mp4/.mp4v/.mpeg4 | general.mpeg-4 | video/mp4 | MPEG-4视频 |
| .avi/.vfw | general.avi | video/avi | AVI视频 |
| .txt/.text | general.plain-text | text/plain | 纯文本 |
| .doc | com.microsoft.word.doc | application/msword | Word文档 |
| .xls | com.microsoft.excel.xls | application/vnd.ms-excel | Excel表格 |
| .ppt | com.microsoft.powerpoint.ppt | application/vnd.ms-powerpoint | PPT演示文稿 |

更多类型参考 UTD 预置列表。

---

## 常见问题

### 数据在分享过程中被丢弃或者提示无效的数据类型

分享服务支持内容分享和文件分享两种场景，但不支持两者混合分享。在混合分享时，数据可能会在分享过程中丢失或提示无效的数据类型。

**关键规则**: 不要在同一个 `SharedData` 中混合传入文件分享（uri）和内容分享（content）数据。

---

## 示例代码

- 基于 Share Kit 实现碰一碰文件分享
- 碰一碰链接分享
- 隔空传送快速分享