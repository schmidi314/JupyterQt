#pragma once

#include <QDialog>
#include <QLineEdit>
#include <QLabel>
#include "config/ServerConfig.h"

class ConnectionDialog : public QDialog {
    Q_OBJECT
public:
    explicit ConnectionDialog(const ServerConfig& config, QWidget* parent = nullptr);

    ServerConfig serverConfig() const;
    void setStatus(const QString& result);   // "ok" / "unauthorized" / error string

private slots:
    void testConnection();

private:
    QLineEdit* m_urlEdit;
    QLineEdit* m_tokenEdit;
    QLabel*    m_statusLabel;
};
