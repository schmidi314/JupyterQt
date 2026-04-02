#pragma once

#include <QObject>
#include <QWebSocket>
#include <QString>
#include <QTimer>
#include "JupyterMessage.h"
#include "models/KernelState.h"
#include "config/ServerConfig.h"

class KernelClient : public QObject {
    Q_OBJECT
public:
    explicit KernelClient(QObject* parent = nullptr);
    ~KernelClient() override;

    void connectToKernel(const ServerConfig& config, const QString& kernelId);
    void disconnectFromKernel();

    bool isConnected() const;
    QString kernelId() const { return m_kernelId; }
    QString sessionId() const { return m_sessionId; }

    // Send an execute_request, returns msg_id
    QString executeCode(const QString& code);

    // Send interrupt / restart via kernel client channel
    void sendInputReply(const QString& value);

signals:
    void connected();
    void disconnected();
    void messageReceived(const JupyterMessage& msg);

    // Convenience signals routed from messageReceived
    void statusMessage(const QString& execState);        // kernel_info_reply / status
    void streamOutput(const QString& name, const QString& text, const QString& parentMsgId);
    void displayData(const QJsonObject& data, const QString& parentMsgId);
    void executeResult(const QJsonObject& data, int execCount, const QString& parentMsgId);
    void executeError(const QString& ename, const QString& evalue, const QStringList& traceback, const QString& parentMsgId);
    void executeReply(const QString& parentMsgId, int execCount, const QString& status);
    void kernelStatusChanged(const QString& execState);

private slots:
    void onTextMessageReceived(const QString& msg);
    void onConnected();
    void onDisconnected();
    void onError(QAbstractSocket::SocketError error);

private:
    void routeMessage(const JupyterMessage& msg);
    void sendMessage(const JupyterMessage& msg);

    QWebSocket* m_socket = nullptr;
    QString m_kernelId;
    QString m_sessionId;
    ServerConfig m_config;
};
