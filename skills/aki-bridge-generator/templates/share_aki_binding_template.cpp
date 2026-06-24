#include "aki/jsbind.h"
#include "<bridgeHeader>.h"

void set<CallbackName1>Callback(aki::SafetyCallback<bool(std::string)> callback) {
    <BridgeName>::instance()->set<CallbackName1>Callback(std::move(callback));
}

void set<CallbackName2>Callback(aki::SafetyCallback<bool()> callback) {
    <BridgeName>::instance()->set<CallbackName2>Callback(std::move(callback));
}

void set<CallbackName3>Callback(aki::SafetyCallback<bool(int, std::string, int)> callback) {
    <BridgeName>::instance()->set<CallbackName3>Callback(std::move(callback));
}

void set<CallbackName4>Callback(aki::SafetyCallback<bool()> callback) {
    <BridgeName>::instance()->set<CallbackName4>Callback(std::move(callback));
}

void notifyResult(int resultCode, std::string resultMsg) {
    <BridgeName>::instance()->notifyResult(resultCode, resultMsg);
}

void notifyEvent() {
    <BridgeName>::instance()->notifyEvent();
}

JSBIND_GLOBAL()
{
    JSBIND_FUNCTION(set<CallbackName1>Callback);
    JSBIND_FUNCTION(set<CallbackName2>Callback);
    JSBIND_FUNCTION(set<CallbackName3>Callback);
    JSBIND_FUNCTION(set<CallbackName4>Callback);
    JSBIND_FUNCTION(notifyResult);
    JSBIND_FUNCTION(notifyEvent);
}

JSBIND_ADDON(<addonName>);
