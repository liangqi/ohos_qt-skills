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
    void <registerMethodName>(const QString& content);
    void <unregisterMethodName>();
    void <registerMethodName2>(int windowId);
    void <unregisterMethodName2>();
    void notifyResult(int resultCode, const std::string& resultMsg);
    void notifyEvent();

signals:
    void logMessage(const QString& msg);

private:
    <BridgeName>();
    ~<BridgeName>() override;

    static <BridgeName>* m_instance;
    static std::mutex m_mutex;

    aki::SafetyCallback<bool(std::string)>* m_<callbackName1>Func;
    aki::SafetyCallback<bool()>* m_<callbackName2>Func;
    aki::SafetyCallback<bool(int, std::string, int)>* m_<callbackName3>Func;
    aki::SafetyCallback<bool()>* m_<callbackName4>Func;

    std::string m_pendingContent;

public:
    void set<CallbackName1>Callback(aki::SafetyCallback<bool(std::string)> callback);
    void set<CallbackName2>Callback(aki::SafetyCallback<bool()> callback);
    void set<CallbackName3>Callback(aki::SafetyCallback<bool(int, std::string, int)> callback);
    void set<CallbackName4>Callback(aki::SafetyCallback<bool()> callback);

private:
    void on<RegisterMethodName>Result(bool success, const std::string& content);
    void on<UnregisterMethodName>Result(bool success);
    void on<RegisterMethodName2>Result(bool success);
    void on<UnregisterMethodName2>Result(bool success);
};
