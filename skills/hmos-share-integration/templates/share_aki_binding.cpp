#include "aki/jsbind.h"
#include "share_bridge.h"

void setRegisterKnockSendCallback(aki::SafetyCallback<bool(std::string)> callback) {
    ShareBridge::instance()->setRegisterKnockSendCallback(std::move(callback));
}

void setUnregisterKnockSendCallback(aki::SafetyCallback<bool()> callback) {
    ShareBridge::instance()->setUnregisterKnockSendCallback(std::move(callback));
}

void setRegisterKnockReceiveCallback(aki::SafetyCallback<bool(int, std::string, int)> callback) {
    ShareBridge::instance()->setRegisterKnockReceiveCallback(std::move(callback));
}

void setUnregisterKnockReceiveCallback(aki::SafetyCallback<bool()> callback) {
    ShareBridge::instance()->setUnregisterKnockReceiveCallback(std::move(callback));
}

void notifyResult(int resultCode, std::string resultMsg) {
    ShareBridge::instance()->notifyResult(resultCode, resultMsg);
}

void notifyEvent() {
    ShareBridge::instance()->notifyEvent();
}

JSBIND_GLOBAL()
{
    JSBIND_FUNCTION(setRegisterKnockSendCallback);
    JSBIND_FUNCTION(setUnregisterKnockSendCallback);
    JSBIND_FUNCTION(setRegisterKnockReceiveCallback);
    JSBIND_FUNCTION(setUnregisterKnockReceiveCallback);
    JSBIND_FUNCTION(notifyResult);
    JSBIND_FUNCTION(notifyEvent);
}

JSBIND_ADDON(sharebridge);
