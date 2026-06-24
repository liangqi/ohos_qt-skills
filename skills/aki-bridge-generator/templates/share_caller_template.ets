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
              title: '<ShareTitle>',
              description: '<ShareDescription>'
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

  private unregisterKnockSendImpl(): boolean {
    try {
      if (this.isKnockListening) {
        harmonyShare.off('knockShare');
        this.isKnockListening = false;
        this.shareTarget = null;
        return true;
      }
      shareBridge.notifyResult(0, 'Already unregistered knock send');
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Unregister knock send failed: ${err}`);
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
          try {
            let receiveCallback: harmonyShare.ReceiveCallback = {
              onDataReceived: (sharedData: systemShare.SharedData) => {
                try {
                  let records = sharedData.getRecords();
                  for (let i = 0; i < records.length; i++) {
                    let record = records[i];
                    if (record.utd === 'general.text' || record.utd === 'general.hyperlink') {
                      shareBridge.notifyDataReceive(record.content ?? '');
                    } else {
                      shareBridge.notifyDataReceiveFile(record.title ?? 'unknown', this.receiveDir + '/' + (record.title ?? 'unknown'));
                    }
                  }
                  shareBridge.notifyResult(0, `Data received: ${records.length} records`);
                } catch (err) {
                  shareBridge.notifyResult(-1, `Process received data failed: ${err}`);
                }
              },
              onResult: (resultCode: harmonyShare.ShareResultCode) => {
                shareBridge.notifyResult(resultCode, `Receive result code: ${resultCode}`);
              }
            } as harmonyShare.ReceiveCallback;
            receivableTarget.receive(this.receiveDir, receiveCallback).then(() => {
              shareBridge.notifyResult(0, 'Receive initiated successfully');
            }).catch((error: BusinessError) => {
              shareBridge.notifyResult(error.code ?? -1, `Receive initiation failed: ${error.message}`);
            });
          } catch (err) {
            shareBridge.notifyResult(-1, `Process receivable target failed: ${err}`);
          }
        });
        this.isDataReceiving = true;
        return true;
      }
      shareBridge.notifyResult(0, 'Already registered data receive');
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Register knock receive failed: ${err}`);
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
      shareBridge.notifyResult(0, 'Already unregistered data receive');
      return true;
    } catch (err) {
      shareBridge.notifyResult(-1, `Unregister knock receive failed: ${err}`);
      return false;
    }
  }
}
