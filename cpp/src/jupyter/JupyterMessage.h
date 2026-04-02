#pragma once

#include <QString>
#include <QJsonObject>
#include <QDateTime>
#include <QUuid>

struct JupyterMessage {
    // Header fields
    QString msg_id;
    QString msg_type;
    QString session;
    QString username;
    QString date;
    QString version;

    // Parent header
    QJsonObject parent_header;

    // Content
    QJsonObject content;

    // Metadata
    QJsonObject metadata;

    // Buffers (base64 encoded)
    QStringList buffers;

    static JupyterMessage create(const QString& msgType,
                                  const QJsonObject& content,
                                  const QString& sessionId = QString(),
                                  const QString& parentMsgId = QString());

    QJsonObject toJson() const;
    static JupyterMessage fromJson(const QJsonObject& obj);
    static JupyterMessage fromBytes(const QByteArray& data);

    bool isValid() const { return !msg_id.isEmpty() && !msg_type.isEmpty(); }

    QString parentMsgId() const {
        return parent_header[QStringLiteral("msg_id")].toString();
    }
};
