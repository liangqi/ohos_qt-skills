#pragma once

#include <QObject>
#include <QString>
#include <functional>
#include <mutex>
#include <string>
#include "aki/jsbind.h"

class ShareBridge : public QObject {
    Q_OBJECT

public:
    static ShareBridge* instance();

    void initTaskRunner();
    void registerKnockSend(const QString& content);
    void unregisterKnockSend();
    void registerKnockReceive(int windowId);
    void unregisterKnockReceive();
    void notifyResult(int resultCode, const std::string& resultMsg);
    void notifyEvent();

signals:
    void logMessage(const QString& msg);

private:
    ShareBridge();
    ~ShareBridge() override;

    static ShareBridge* m_instance;
    static std::mutex m_mutex;

    aki::SafetyCallback<bool(std::string)>* m_registerKnockSendFunc;
    aki::SafetyCallback<bool()>* m_unregisterKnockSendFunc;
    aki::SafetyCallback<bool(int, std::string, int)>* m_registerKnockReceiveFunc;
    aki::SafetyCallback<bool()>* m_unregisterKnockReceiveFunc;

    std::string m_pendingContent;

public:
    void setRegisterKnockSendCallback(aki::SafetyCallback<bool(std::string)> callback);
    void setUnregisterKnockSendCallback(aki::SafetyCallback<bool()> callback);
    void setRegisterKnockReceiveCallback(aki::SafetyCallback<bool(int, std::string, int)> callback);
    void setUnregisterKnockReceiveCallback(aki::SafetyCallback<bool()> callback);

private:
    void onRegisterKnockSendResult(bool success, const std::string& content);
    void onUnregisterKnockSendResult(bool success);
    void onRegisterKnockReceiveResult(bool success);
    void onUnregisterKnockReceiveResult(bool success);
};
