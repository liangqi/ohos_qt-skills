import { harmonyShare, systemShare } from '@kit.ShareKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { uniformTypeDescriptor as utd } from '@kit.ArkData';
import { fileUri } from '@kit.CoreFileKit';
import * as shareBridge from 'libsharebridge.so';

const RECV_CAPABILITIES: harmonyShare.RecvCapability[] = [
  { utd: utd.UniformDataType.PLAIN_TEXT, maxSupportedCount: 5 },
  { utd: utd.UniformDataType.PDF, maxSupportedCount: 5 },
  { utd: utd.UniformDataType.MEDIA, maxSupportedCount: 5 },
  { utd: utd.UniformDataType.FILE, maxSupportedCount: 5 },
];

export class ShareBridgeProxy {
  private static instance: ShareBridgeProxy | null = null;
  private shareTarget: harmonyShare.SharableTarget | null = null;
  private receiveDir: string = '';

  static getInstance(): ShareBridgeProxy {
    if (!ShareBridgeProxy.instance) {
      ShareBridgeProxy.instance = new ShareBridgeProxy();
    }
    return ShareBridgeProxy.instance;
  }

  setReceiveDir(dir: string): void {
    this.receiveDir = dir;
  }

  init(): void {
    shareBridge.JSBind.bindFunction("Share.registerKnockSend", (content: string, windowId: number): boolean => {
      return this.registerKnockSendImpl(content, windowId);
    });
    shareBridge.JSBind.bindFunction("Share.unregisterKnockSend", (windowId: number): boolean => {
      return this.unregisterKnockSendImpl(windowId);
    });
    shareBridge.JSBind.bindFunction("Share.registerKnockReceive", (windowId: number): boolean => {
      return this.registerKnockReceiveImpl(windowId);
    });
    shareBridge.JSBind.bindFunction("Share.unregisterKnockReceive", (windowId: number): boolean => {
      return this.unregisterKnockReceiveImpl(windowId);
    });
    shareBridge.prepareExecutor();
  }

  private registerKnockSendImpl(content: string, windowId: number): boolean {
    harmonyShare.on('knockShare', { windowId: windowId, sendOnly: false } as harmonyShare.SendCapabilityRegistry, (target: harmonyShare.SharableTarget) => {
      this.shareTarget = target;
      shareBridge.notifyKnockEvent();
      let sharedData = new systemShare.SharedData({
        utd: utd.UniformDataType.PLAIN_TEXT,
        content: content,
        title: 'Knock Share Demo',
        description: ''
      });
      target.share(sharedData).then(() => {
        shareBridge.notifyResult(0, 'Share content sent successfully');
      }).catch((error: BusinessError) => {
        shareBridge.notifyResult(error.code ?? -1, `Share failed: ${error.message}`);
      });
    });
    return true;
  }

  private unregisterKnockSendImpl(windowId: number): boolean {
    harmonyShare.off('knockShare', { windowId: windowId, sendOnly: false } as harmonyShare.SendCapabilityRegistry);
    return true;
  }

  private registerKnockReceiveImpl(windowId: number): boolean {
    let recvCapabilityRegistry = {
      windowId: windowId,
      capabilities: RECV_CAPABILITIES
    } as harmonyShare.RecvCapabilityRegistry;
    harmonyShare.on('dataReceive', recvCapabilityRegistry, (receivableTarget: harmonyShare.ReceivableTarget) => {
      receivableTarget.receive(fileUri.getUriFromPath(this.receiveDir), {
        onDataReceived: (sharedData: systemShare.SharedData) => {
          let records = sharedData.getRecords();
          for (let i = 0; i < records.length; i++) {
            let record = records[i];
            shareBridge.notifyDataReceiveFile(record.title ?? 'unknown', record.uri ?? '');
          }
        },
        onResult: (resultCode: harmonyShare.ShareResultCode) => {
          shareBridge.notifyResult(resultCode, `Receive result: ${resultCode}`);
        }
      }).catch((error: BusinessError) => {
        shareBridge.notifyResult(error.code ?? -1, `Receive initiation failed: ${error.message}`);
      });
    });
    return true;
  }

  private unregisterKnockReceiveImpl(windowId: number): boolean {
    harmonyShare.off('dataReceive', {
      windowId: windowId,
      capabilities: RECV_CAPABILITIES
    } as harmonyShare.RecvCapabilityRegistry);
    return true;
  }
}
