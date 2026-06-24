# 碰一碰链接分享 — 最佳实践

**来源**: https://developer.huawei.com/consumer/cn/doc/best-practices/bpta-application-knock-video-share

**更新时间**: 2026-05-22 17:46

---

## 概述

随着全场景智慧生活的不断演进，跨设备内容分享已成为用户的核心需求之一。HarmonyOS 提供了 Share Kit（分享服务），并结合 App Linking 技术，可实现内容的快速跨设备分享，直达目标应用，无需依赖第三方应用中转。

本文以视频分享场景为例，介绍碰一碰快速分享视频的原理与开发步骤。

---

## 典型场景

当用户在源端使用视频应用播放视频时，可通过"碰一碰"功能将该视频分享至对端。根据对端是否安装视频应用以及是否配置了直达应用市场，有三种场景：

### 场景一：目标应用已安装

系统直接拉起目标应用视频播放页面播放视频，无需经过浏览器中转，一键直达。

### 场景二：目标应用未安装，已配置直达应用市场

直接跳转到应用市场的应用详情页。安装完成后，首次打开应用将通过延迟链接功能自动跳转到视频播放页面。

### 场景三：目标应用未安装，未配置直达应用市场（有Web页面）

系统通过浏览器打开 Web 页面，用户可直接查看内容。Web 页面可提供"下载"按钮引导用户安装应用。

**说明**: 对于不提供 Web 页面的应用，建议开启直达应用市场功能，避免因无法访问内容而造成体验断裂。

---

## 实现原理

碰一碰视频分享功能主要依赖于 Share Kit 与 App Linking 实现。应用需要集成 App Linking 来保证从分享到打开的端到端体验流畅无阻。

---

## 开发步骤

### 1. 配置 App Linking 服务

应用需集成 App Linking，在 `entry` 模块的 `module.json5` 中配置：

```json5
{
  "module": {
    "abilities": [
      {
        "name": "EntryAbility",
        "exported": true,
        "skills": [
          {
            "entities": [
              "entity.system.home",
              "entity.system.browsable"
            ],
            "actions": [
              "ohos.want.action.home",
              "ohos.want.action.viewData"
            ],
            "uris": [
              {
                "scheme": "https",
                "host": "www.example.com",
                "path": ""
              }
            ],
            "domainVerify": true
          }
        ]
      }
    ]
  }
}
```

**关键配置**:
- entities 必须包含 `entity.system.browsable`
- actions 必须包含 `ohos.want.action.viewData`
- scheme 必须为 `https`
- host 必须为关联域名
- domainVerify 必须为 `true`

---

### 2. 碰一碰分享事件监听/取消

封装 `KnockController` 类管理碰一碰事件：

```typescript
import { harmonyShare, systemShare } from '@kit.ShareKit';
import { fileUri } from '@kit.CoreFileKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { uniformTypeDescriptor } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

export class KnockController {
  private static controller: KnockController;
  private context: common.UIAbilityContext | undefined = undefined;
  private isKnockListening: boolean = false;

  public static getInstance(context: common.UIAbilityContext): KnockController {
    if (!KnockController.controller) {
      KnockController.controller = new KnockController(context);
    }
    return KnockController.controller;
  }

  // 手机端监听
  public immersiveListening() {
    if (canIUse('SystemCapability.Collaboration.HarmonyShare') && !this.isKnockListening) {
      harmonyShare.on('knockShare', (target: harmonyShare.SharableTarget) => {
        this.immersiveCallback(target);
      });
      this.isKnockListening = true;
    }
  }

  // 取消监听（手机端）
  public immersiveDisableListening() {
    if (canIUse('SystemCapability.Collaboration.HarmonyShare') && this.isKnockListening) {
      harmonyShare.off('knockShare');
      this.isKnockListening = false;
    }
  }

  // PC端监听（需要传入windowId）
  public immersiveListeningPC() {
    if (canIUse('SystemCapability.Collaboration.HarmonyShare') && !this.isKnockListening) {
      window.getLastWindow(this.context).then((data) => {
        let mainWindowID: number = data.getWindowProperties().id;
        harmonyShare.on('knockShare', { windowId: mainWindowID }, (target: harmonyShare.SharableTarget) => {
          this.immersiveCallback(target);
        });
      });
      this.isKnockListening = true;
    }
  }

  // 取消监听（PC端）
  public immersiveDisableListeningPC() {
    if (canIUse('SystemCapability.Collaboration.HarmonyShare') && this.isKnockListening) {
      window.getLastWindow(this.context).then((data) => {
        let mainWindowID: number = data.getWindowProperties().id;
        harmonyShare.off('knockShare', { windowId: mainWindowID });
      });
      this.isKnockListening = false;
    }
  }
}
```

**重要**: 收到碰一碰分享事件回调后，需尽快调用 `sharableTarget.share()` 方法发起分享，**超过 3 秒可能会失败**。

**页面监听/取消时机**:
- 进入页面时：在 `aboutToAppear()` 和 `onPageShow()` 中注册监听
- 离开页面时：在 `onPageHide()` 和 `aboutToDisappear()` 中取消监听

---

### 3. 加载预览图和发起分享

收到碰一碰事件回调后，构造链接分享数据并发起分享：

```typescript
public immersiveCallback(target: harmonyShare.SharableTarget) {
  try {
    let videoIndex: number = AppStorage.get('videoIndex') as number;
    let videoData: VideoData = VIDEO_SOURCES[videoIndex];
    let filePath: string = this.context?.filesDir + `/${videoData.head}`;
    let coverUri: string = fileUri.getUriFromPath(filePath);

    let shareData: systemShare.SharedData = new systemShare.SharedData({
      // 分享类型设置为链接
      utd: uniformTypeDescriptor.UniformDataType.HYPERLINK,
      // 分享的 App Linking 链接
      content: `https://www.example.com?videoIndex=${videoIndex}`,
      thumbnailUri: coverUri,
      title: videoData.name,
      description: videoData.description
    });

    target.share(shareData).then(() => {
      Logger.info(TAG, 'Share link success');
    }).catch((error: BusinessError) => {
      Logger.error(TAG, `Share link error. code: ${error.code}, message: ${error.message}`);
    });
  } catch (err) {
    Logger.error(TAG, `Share link exception`);
  }
}
```

**关键参数说明**:
- `utd`: 设置为 `UniformDataType.HYPERLINK`，表示分享内容为链接
- `content`: 设置为配置的 App Linking 链接，拼接视频唯一标识符
- `thumbnailUri`: 缩略图 URI（推荐使用，比 `thumbnail` 清晰度高）
- `title`: 分享卡片标题
- `description`: 分享卡片描述

**说明**: 建议优先使用 `thumbnailUri` 参数设置缩略图。`thumbnail` 参数限制为 32KB，可能导致图片模糊。`thumbnailUri` 仅支持沙箱文件 URI 或用户文件 URI。

---

### 4. 对端跳转处理

#### 应用未在后台运行：在 `onCreate()` 获取链接参数

```typescript
export default class EntryAbility extends UIAbility {
  private mVideoIndex: string = '';

  private getVideoIndex(want: Want): string {
    let uri = want?.uri;
    let videoIndex: string = '';
    if (uri) {
      let urlObject = url.URL.parseURL(want?.uri);
      videoIndex = urlObject.params.get('videoIndex') as string;
    }
    return videoIndex;
  }

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    this.mVideoIndex = this.getVideoIndex(want);
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    let pageUrl: string = 'pages/Index';
    if (this.mVideoIndex && this.mVideoIndex !== '') {
      AppStorage.setOrCreate('videoIndex', Number.parseInt(this.mVideoIndex));
      pageUrl = 'pages/VideoPlay';
    }
    windowStage.loadContent(pageUrl);
  }
}
```

#### 应用已在后台运行：在 `onNewWant()` 获取链接参数

```typescript
onNewWant(want: Want, launchParam: AbilityConstant.LaunchParam): void {
  let videoIndex: string = this.getVideoIndex(want);
  if (videoIndex && videoIndex !== '') {
    this.uiContext?.getRouter().pushUrl({
      url: 'pages/VideoPlay',
      params: { videoIndex: videoIndex }
    });
  }
}
```

#### 配置直达应用市场与延迟链接

通过 `deferredLink.popDeferredLink()` 获取延迟链接，确保安装后首次启动直达内容：

```typescript
@Entry
@Component
struct Index {
  aboutToAppear(): void {
    deferredLink.popDeferredLink()
      .then((link: string) => {
        const videoIndex = url.URL.parseURL(link)?.params?.get('videoIndex') as string;
        if (videoIndex) {
          this.getUIContext().getRouter().pushUrl({
            url: 'pages/VideoPlay',
            params: { videoIndex }
          });
        }
      });
  }
}
```

---

## 常见问题

### 碰一碰分享后，目标应用无法拉起

对端成功接收 App Linking 链接但未拉起目标应用，请查看 AGC 配置是否正确。参考"配置成功但无法拉起"解决方案。

### 碰一碰分享预览图模糊

可能原因：
1. 图片本身画质低
2. 使用了 `thumbnail` 参数（限制 32KB）

**解决方案**: 优先使用 `thumbnailUri` 参数设置缩略图，确保高清预览。

---

## 示例代码

- 基于 Share Kit 实现碰一碰视频快速分享