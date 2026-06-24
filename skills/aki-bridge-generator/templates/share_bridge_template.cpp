#include "<bridgeHeader>.h"
#include <QMetaObject>
#include <QDebug>

<BridgeName>* <BridgeName>::m_instance = nullptr;
std::mutex <BridgeName>::m_mutex;

<BridgeName>* <BridgeName>::instance() {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (!m_instance) {
        m_instance = new <BridgeName>();
    }
    return m_instance;
}

<BridgeName>::<BridgeName>() : QObject(nullptr),
    m_<callbackName1>Func(nullptr),
    m_<callbackName2>Func(nullptr),
    m_<callbackName3>Func(nullptr),
    m_<callbackName4>Func(nullptr) {}

<BridgeName>::~<BridgeName>() {
    delete m_<callbackName1>Func;
    delete m_<callbackName2>Func;
    delete m_<callbackName3>Func;
    delete m_<callbackName4>Func;
}

void <BridgeName>::initTaskRunner() {
    aki::TaskRunner::Create("<addonName>");
}

void <BridgeName>::set<CallbackName1>Callback(aki::SafetyCallback<bool(std::string)> callback) {
    delete m_<callbackName1>Func;
    m_<callbackName1>Func = new aki::SafetyCallback<bool(std::string)>(std::move(callback));
    notifyResult(0, "set<CallbackName1>Callback OK");
}

void <BridgeName>::set<CallbackName2>Callback(aki::SafetyCallback<bool()> callback) {
    delete m_<callbackName2>Func;
    m_<callbackName2>Func = new aki::SafetyCallback<bool()>(std::move(callback));
    notifyResult(0, "set<CallbackName2>Callback OK");
}

void <BridgeName>::set<CallbackName3>Callback(aki::SafetyCallback<bool(int, std::string, int)> callback) {
    delete m_<callbackName3>Func;
    m_<callbackName3>Func = new aki::SafetyCallback<bool(int, std::string, int)>(std::move(callback));
    notifyResult(0, "set<CallbackName3>Callback OK");
}

void <BridgeName>::set<CallbackName4>Callback(aki::SafetyCallback<bool()> callback) {
    delete m_<callbackName4>Func;
    m_<callbackName4>Func = new aki::SafetyCallback<bool()>(std::move(callback));
    notifyResult(0, "set<CallbackName4>Callback OK");
}

void <BridgeName>::<registerMethodName>(const QString& content) {
    m_pendingContent = content.toStdString();
    if (m_<callbackName1>Func) {
        bool result = (*m_<callbackName1>Func)(m_pendingContent);
        on<RegisterMethodName>Result(result, m_pendingContent);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: <registerMethodName> callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void <BridgeName>::<unregisterMethodName>() {
    if (m_<callbackName2>Func) {
        bool result = (*m_<callbackName2>Func)();
        on<UnregisterMethodName>Result(result);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: <unregisterMethodName> callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void <BridgeName>::<registerMethodName2>(int windowId) {
    if (m_<callbackName3>Func) {
        std::string utdTypes = "<defaultUtdTypes>";
        bool result = (*m_<callbackName3>Func)(<defaultMaxFileCount>, utdTypes, windowId);
        on<RegisterMethodName2>Result(result);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: <registerMethodName2> callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void <BridgeName>::<unregisterMethodName2>() {
    if (m_<callbackName4>Func) {
        bool result = (*m_<callbackName4>Func)();
        on<UnregisterMethodName2>Result(result);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: <unregisterMethodName2> callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void <BridgeName>::notifyResult(int resultCode, const std::string& resultMsg) {
    QString msg = QString("[Result] code=%1, msg=%2")
        .arg(resultCode)
        .arg(QString::fromStdString(resultMsg));
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void <BridgeName>::notifyEvent() {
    QMetaObject::invokeMethod(this, [this]() {
        emit logMessage("[Event] <eventName> detected");
    }, Qt::QueuedConnection);
}

void <BridgeName>::on<RegisterMethodName>Result(bool success, const std::string& content) {
    QString msg = success
        ? QString("[<RegisterMethodName>] SUCCESS - content: \"%1\"").arg(QString::fromStdString(content).left(50))
        : QString("[<RegisterMethodName>] FAILED");
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void <BridgeName>::on<UnregisterMethodName>Result(bool success) {
    QString msg = success ? "[<UnregisterMethodName>] SUCCESS" : "[<UnregisterMethodName>] FAILED";
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void <BridgeName>::on<RegisterMethodName2>Result(bool success) {
    QString msg = success ? "[<RegisterMethodName2>] SUCCESS" : "[<RegisterMethodName2>] FAILED";
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void <BridgeName>::on<UnregisterMethodName2>Result(bool success) {
    QString msg = success ? "[<UnregisterMethodName2>] SUCCESS" : "[<UnregisterMethodName2>] FAILED";
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}
