#include "JupyterMessage.h"
#include <QJsonDocument>
#include <QJsonArray>

JupyterMessage JupyterMessage::create(const QString& msgType,
                                       const QJsonObject& content,
                                       const QString& sessionId,
                                       const QString& parentMsgId)
{
    JupyterMessage msg;
    msg.msg_id = QUuid::createUuid().toString(QUuid::WithoutBraces);
    msg.msg_type = msgType;
    msg.session = sessionId.isEmpty() ? QUuid::createUuid().toString(QUuid::WithoutBraces) : sessionId;
    msg.username = QStringLiteral("jupyterqt");
    msg.date = QDateTime::currentDateTimeUtc().toString(Qt::ISODate);
    msg.version = QStringLiteral("5.3");
    msg.content = content;
    msg.metadata = QJsonObject();

    if (!parentMsgId.isEmpty()) {
        QJsonObject ph;
        ph[QStringLiteral("msg_id")] = parentMsgId;
        msg.parent_header = ph;
    }

    return msg;
}

QJsonObject JupyterMessage::toJson() const {
    QJsonObject header;
    header[QStringLiteral("msg_id")]  = msg_id;
    header[QStringLiteral("msg_type")] = msg_type;
    header[QStringLiteral("session")] = session;
    header[QStringLiteral("username")] = username;
    header[QStringLiteral("date")]    = date;
    header[QStringLiteral("version")] = version;

    QJsonObject obj;
    obj[QStringLiteral("header")]        = header;
    obj[QStringLiteral("parent_header")] = parent_header;
    obj[QStringLiteral("metadata")]      = metadata;
    obj[QStringLiteral("content")]       = content;
    obj[QStringLiteral("buffers")]       = QJsonArray();
    return obj;
}

JupyterMessage JupyterMessage::fromJson(const QJsonObject& obj) {
    JupyterMessage msg;
    auto header = obj[QStringLiteral("header")].toObject();
    msg.msg_id   = header[QStringLiteral("msg_id")].toString();
    msg.msg_type = header[QStringLiteral("msg_type")].toString();
    msg.session  = header[QStringLiteral("session")].toString();
    msg.username = header[QStringLiteral("username")].toString();
    msg.date     = header[QStringLiteral("date")].toString();
    msg.version  = header[QStringLiteral("version")].toString();

    msg.parent_header = obj[QStringLiteral("parent_header")].toObject();
    msg.metadata      = obj[QStringLiteral("metadata")].toObject();
    msg.content       = obj[QStringLiteral("content")].toObject();

    return msg;
}

JupyterMessage JupyterMessage::fromBytes(const QByteArray& data) {
    QJsonParseError err;
    auto doc = QJsonDocument::fromJson(data, &err);
    if (err.error != QJsonParseError::NoError || !doc.isObject()) {
        return JupyterMessage{};
    }
    return fromJson(doc.object());
}
