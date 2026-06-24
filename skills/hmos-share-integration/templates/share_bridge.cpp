#include "share_bridge.h"
#include <QMetaObject>
#include <QDebug>

ShareBridge* ShareBridge::m_instance = nullptr;
std::mutex ShareBridge::m_mutex;

ShareBridge* ShareBridge::instance() {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (!m_instance) {
        m_instance = new ShareBridge();
    }
    return m_instance;
}

ShareBridge::ShareBridge() : QObject(nullptr),
    m_registerKnockSendFunc(nullptr),
    m_unregisterKnockSendFunc(nullptr),
    m_registerKnockReceiveFunc(nullptr),
    m_unregisterKnockReceiveFunc(nullptr) {}

ShareBridge::~ShareBridge() {
    delete m_registerKnockSendFunc;
    delete m_unregisterKnockSendFunc;
    delete m_registerKnockReceiveFunc;
    delete m_unregisterKnockReceiveFunc;
}

void ShareBridge::initTaskRunner() {
    aki::TaskRunner::Create("sharebridge");
}

void ShareBridge::setRegisterKnockSendCallback(aki::SafetyCallback<bool(std::string)> callback) {
    delete m_registerKnockSendFunc;
    m_registerKnockSendFunc = new aki::SafetyCallback<bool(std::string)>(std::move(callback));
    notifyResult(0, "setRegisterKnockSendCallback OK");
}

void ShareBridge::setUnregisterKnockSendCallback(aki::SafetyCallback<bool()> callback) {
    delete m_unregisterKnockSendFunc;
    m_unregisterKnockSendFunc = new aki::SafetyCallback<bool()>(std::move(callback));
    notifyResult(0, "setUnregisterKnockSendCallback OK");
}

void ShareBridge::setRegisterKnockReceiveCallback(aki::SafetyCallback<bool(int, std::string, int)> callback) {
    delete m_registerKnockReceiveFunc;
    m_registerKnockReceiveFunc = new aki::SafetyCallback<bool(int, std::string, int)>(std::move(callback));
    notifyResult(0, "setRegisterKnockReceiveCallback OK");
}

void ShareBridge::setUnregisterKnockReceiveCallback(aki::SafetyCallback<bool()> callback) {
    delete m_unregisterKnockReceiveFunc;
    m_unregisterKnockReceiveFunc = new aki::SafetyCallback<bool()>(std::move(callback));
    notifyResult(0, "setUnregisterKnockReceiveCallback OK");
}

void ShareBridge::registerKnockSend(const QString& content) {
    m_pendingContent = content.toStdString();
    if (m_registerKnockSendFunc) {
        bool result = (*m_registerKnockSendFunc)(m_pendingContent);
        onRegisterKnockSendResult(result, m_pendingContent);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: registerKnockSend callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void ShareBridge::unregisterKnockSend() {
    if (m_unregisterKnockSendFunc) {
        bool result = (*m_unregisterKnockSendFunc)();
        onUnregisterKnockSendResult(result);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: unregisterKnockSend callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void ShareBridge::registerKnockReceive(int windowId) {
    if (m_registerKnockReceiveFunc) {
        std::string utdTypes = "general.image,general.file";
        bool result = (*m_registerKnockReceiveFunc)(5, utdTypes, windowId);
        onRegisterKnockReceiveResult(result);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: registerKnockReceive callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void ShareBridge::unregisterKnockReceive() {
    if (m_unregisterKnockReceiveFunc) {
        bool result = (*m_unregisterKnockReceiveFunc)();
        onUnregisterKnockReceiveResult(result);
    } else {
        QMetaObject::invokeMethod(this, [this]() {
            emit logMessage("Error: unregisterKnockReceive callback not initialized");
        }, Qt::QueuedConnection);
    }
}

void ShareBridge::notifyResult(int resultCode, const std::string& resultMsg) {
    QString msg = QString("[Result] code=%1, msg=%2")
        .arg(resultCode)
        .arg(QString::fromStdString(resultMsg));
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void ShareBridge::notifyEvent() {
    QMetaObject::invokeMethod(this, [this]() {
        emit logMessage("[Event] knock detected");
    }, Qt::QueuedConnection);
}

void ShareBridge::onRegisterKnockSendResult(bool success, const std::string& content) {
    QString msg = success
        ? QString("[RegisterKnockSend] SUCCESS - content: \"%1\"").arg(QString::fromStdString(content).left(50))
        : QString("[RegisterKnockSend] FAILED");
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void ShareBridge::onUnregisterKnockSendResult(bool success) {
    QString msg = success ? "[UnregisterKnockSend] SUCCESS" : "[UnregisterKnockSend] FAILED";
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void ShareBridge::onRegisterKnockReceiveResult(bool success) {
    QString msg = success ? "[RegisterKnockReceive] SUCCESS" : "[RegisterKnockReceive] FAILED";
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}

void ShareBridge::onUnregisterKnockReceiveResult(bool success) {
    QString msg = success ? "[UnregisterKnockReceive] SUCCESS" : "[UnregisterKnockReceive] FAILED";
    QMetaObject::invokeMethod(this, [this, msg]() {
        emit logMessage(msg);
    }, Qt::QueuedConnection);
}
