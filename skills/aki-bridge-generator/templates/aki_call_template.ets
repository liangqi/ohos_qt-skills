import * as <addonName> from 'lib<addonName>.so';

export class <BridgeName>Proxy {
  private static instance: <BridgeName>Proxy | null = null;

  static getInstance(): <BridgeName>Proxy {
    if (!<BridgeName>Proxy.instance) {
      <BridgeName>Proxy.instance = new <BridgeName>Proxy();
    }
    return <BridgeName>Proxy.instance;
  }

  init(): void {
    <addonName>.set<CallbackName1>Callback((param1: string): boolean => {
      return this.<registerMethodImpl>(param1);
    });
    <addonName>.set<CallbackName2>Callback((): boolean => {
      return this.<unregisterMethodImpl>();
    });
    <addonName>.set<CallbackName3>Callback((param1: number, param2: string, param3: number): boolean => {
      return this.<registerMethodImpl2>(param1, param2, param3);
    });
    <addonName>.set<CallbackName4>Callback((): boolean => {
      return this.<unregisterMethodImpl2>();
    });
    <addonName>.notifyResult(0, '<BridgeName>Proxy init OK');
  }

  private <registerMethodImpl>(param: string): boolean {
    try {
      return true;
    } catch (err) {
      <addonName>.notifyResult(-1, `Register failed: ${err}`);
      return false;
    }
  }

  private <unregisterMethodImpl>(): boolean {
    try {
      return true;
    } catch (err) {
      <addonName>.notifyResult(-1, `Unregister failed: ${err}`);
      return false;
    }
  }

  private <registerMethodImpl2>(maxFileCount: number, utdTypes: string, windowId: number): boolean {
    try {
      return true;
    } catch (err) {
      <addonName>.notifyResult(-1, `Register failed: ${err}`);
      return false;
    }
  }

  private <unregisterMethodImpl2>(): boolean {
    try {
      return true;
    } catch (err) {
      <addonName>.notifyResult(-1, `Unregister failed: ${err}`);
      return false;
    }
  }
}
