#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonObject>
#include <QUrl>
#include "config/ServerConfig.h"

class RestClient : public QObject {
    Q_OBJECT
public:
    explicit RestClient(QObject* parent = nullptr);

    void setConfig(const ServerConfig& config);
    const ServerConfig& config() const { return m_config; }

    // Seed XSRF cookie
    QNetworkReply* fetchXsrf();

    // Contents API
    QNetworkReply* listContents(const QString& path);
    QNetworkReply* getNotebook(const QString& path);
    QNetworkReply* saveNotebook(const QString& path, const QJsonObject& content);
    QNetworkReply* createNotebook(const QString& dir);

    // Kernel API
    QNetworkReply* startKernel(const QString& name);
    QNetworkReply* shutdownKernel(const QString& id);
    QNetworkReply* restartKernel(const QString& id);
    QNetworkReply* interruptKernel(const QString& id);

    // Server check
    QNetworkReply* checkServer();

    QNetworkAccessManager* nam() { return m_nam; }

private:
    QNetworkRequest buildRequest(const QString& endpoint) const;
    QByteArray xsrfToken() const;

    QNetworkAccessManager* m_nam;
    ServerConfig m_config;
};
