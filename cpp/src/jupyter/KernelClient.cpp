#include "KernelClient.h"
#include <QJsonDocument>
#include <QJsonArray>
#include <QUuid>
#include <QNetworkRequest>

KernelClient::KernelClient(QObject* parent)
    : QObject(parent)
    , m_socket(new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this))
    , m_sessionId(QUuid::createUuid().toString(QUuid::WithoutBraces))
{
    connect(m_socket, &QWebSocket::connected,    this, &KernelClient::onConnected);
    connect(m_socket, &QWebSocket::disconnected, this, &KernelClient::onDisconnected);
    connect(m_socket, &QWebSocket::textMessageReceived, this, &KernelClient::onTextMessageReceived);
    connect(m_socket, &QWebSocket::errorOccurred, this, &KernelClient::onError);
}

KernelClient::~KernelClient() {
    disconnectFromKernel();
}

void KernelClient::connectToKernel(const ServerConfig& config, const QString& kernelId) {
    m_config = config;
    m_kernelId = kernelId;

    QString url = config.wsUrl()
        + QStringLiteral("/api/kernels/") + kernelId
        + QStringLiteral("/channels?session_id=") + m_sessionId;
    if (!config.token.isEmpty()) {
        url += QStringLiteral("&token=") + config.token;
    }

    QNetworkRequest req(QUrl(url));
    m_socket->open(req);
}

void KernelClient::disconnectFromKernel() {
    if (m_socket->state() != QAbstractSocket::UnconnectedState) {
        m_socket->close();
    }
}

bool KernelClient::isConnected() const {
    return m_socket->state() == QAbstractSocket::ConnectedState;
}

QString KernelClient::executeCode(const QString& code) {
    QJsonObject content;
    content[QStringLiteral("code")]              = code;
    content[QStringLiteral("silent")]            = false;
    content[QStringLiteral("store_history")]     = true;
    content[QStringLiteral("user_expressions")]  = QJsonObject();
    content[QStringLiteral("allow_stdin")]        = false;
    content[QStringLiteral("stop_on_error")]      = true;

    auto msg = JupyterMessage::create(
        QStringLiteral("execute_request"), content, m_sessionId);
    sendMessage(msg);
    return msg.msg_id;
}

void KernelClient::sendInputReply(const QString& value) {
    QJsonObject content;
    content[QStringLiteral("value")] = value;
    auto msg = JupyterMessage::create(
        QStringLiteral("input_reply"), content, m_sessionId);
    sendMessage(msg);
}

void KernelClient::sendMessage(const JupyterMessage& msg) {
    if (!isConnected()) return;
    auto doc = QJsonDocument(msg.toJson());
    m_socket->sendTextMessage(QString::fromUtf8(doc.toJson(QJsonDocument::Compact)));
}

void KernelClient::onConnected() {
    emit connected();
}

void KernelClient::onDisconnected() {
    emit disconnected();
}

void KernelClient::onError(QAbstractSocket::SocketError error) {
    Q_UNUSED(error)
    // disconnected signal will fire
}

void KernelClient::onTextMessageReceived(const QString& msgText) {
    auto msg = JupyterMessage::fromBytes(msgText.toUtf8());
    if (!msg.isValid()) return;
    emit messageReceived(msg);
    routeMessage(msg);
}

void KernelClient::routeMessage(const JupyterMessage& msg) {
    const QString& type = msg.msg_type;
    const QString parentId = msg.parentMsgId();

    if (type == QLatin1String("status")) {
        QString state = msg.content[QStringLiteral("execution_state")].toString();
        emit kernelStatusChanged(state);

    } else if (type == QLatin1String("stream")) {
        QString name = msg.content[QStringLiteral("name")].toString();
        QString text = msg.content[QStringLiteral("text")].toString();
        emit streamOutput(name, text, parentId);

    } else if (type == QLatin1String("display_data")) {
        QJsonObject data = msg.content[QStringLiteral("data")].toObject();
        emit displayData(data, parentId);

    } else if (type == QLatin1String("execute_result")) {
        QJsonObject data = msg.content[QStringLiteral("data")].toObject();
        int execCount = msg.content[QStringLiteral("execution_count")].toInt();
        emit executeResult(data, execCount, parentId);

    } else if (type == QLatin1String("error")) {
        QString ename = msg.content[QStringLiteral("ename")].toString();
        QString evalue = msg.content[QStringLiteral("evalue")].toString();
        QStringList traceback;
        for (const auto& v : msg.content[QStringLiteral("traceback")].toArray()) {
            traceback << v.toString();
        }
        emit executeError(ename, evalue, traceback, parentId);

    } else if (type == QLatin1String("execute_reply")) {
        QString status = msg.content[QStringLiteral("status")].toString();
        int execCount = msg.content[QStringLiteral("execution_count")].toInt();
        emit executeReply(parentId, execCount, status);
    }
}
