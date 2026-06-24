#pragma once

#include <QObject>
#include <QString>
#include <functional>
#include <mutex>
#include <string>
#include <aki/jsbind.h>

class <BridgeName> : public QObject {
    Q_OBJECT

public:
    static <BridgeName>* instance();

    void initTaskRunner();
    void notifyResult(int resultCode, const std::string& resultMsg);

    // <AddActionMethodsHere>

signals:
    void logMessage(const QString& msg);

private:
    <BridgeName>();
    ~<BridgeName>() override;

    static <BridgeName>* m_instance;
    static std::mutex m_mutex;

    // <AddSafetyCallbackPointerMembersHere>
    // Example: aki::SafetyCallback<bool(P...)>* m_<callbackName>Func;

public:
    // <AddSetterMethodsHere>
    // Example: void set<CallbackName>Callback(aki::SafetyCallback<bool(P...)> callback);

private:
    // <AddResultHandlerMethodsHere>
};
