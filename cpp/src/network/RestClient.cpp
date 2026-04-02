#include "RestClient.h"
#include <QNetworkCookieJar>
#include <QNetworkCookie>
#include <QJsonDocument>
#include <QUrlQuery>

RestClient::RestClient(QObject* parent)
    : QObject(parent)
    , m_nam(new QNetworkAccessManager(this))
{
}

void RestClient::setConfig(const ServerConfig& config) {
    m_config = config;
}

QByteArray RestClient::xsrfToken() const {
    QUrl url(m_config.baseUrl);
    auto cookies = m_nam->cookieJar()->cookiesForUrl(url);
    for (const auto& cookie : cookies) {
        if (cookie.name() == "_xsrf") {
            return cookie.value();
        }
    }
    return {};
}

QNetworkRequest RestClient::buildRequest(const QString& endpoint) const {
    QUrl url(m_config.baseUrl + endpoint);
    QNetworkRequest req(url);
    req.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));

    if (!m_config.token.isEmpty()) {
        req.setRawHeader("Authorization",
            QStringLiteral("token %1").arg(m_config.token).toUtf8());
    }

    auto xsrf = xsrfToken();
    if (!xsrf.isEmpty()) {
        req.setRawHeader("X-XSRFToken", xsrf);
    }

    return req;
}

QNetworkReply* RestClient::fetchXsrf() {
    QUrl url(m_config.baseUrl + QStringLiteral("/login"));
    QNetworkRequest req(url);
    if (!m_config.token.isEmpty()) {
        req.setRawHeader("Authorization",
            QStringLiteral("token %1").arg(m_config.token).toUtf8());
    }
    return m_nam->get(req);
}

QNetworkReply* RestClient::listContents(const QString& path) {
    QString endpoint = QStringLiteral("/api/contents");
    if (!path.isEmpty()) endpoint += QStringLiteral("/") + path;
    return m_nam->get(buildRequest(endpoint));
}

QNetworkReply* RestClient::getNotebook(const QString& path) {
    QString endpoint = QStringLiteral("/api/contents/") + path;
    return m_nam->get(buildRequest(endpoint));
}

QNetworkReply* RestClient::saveNotebook(const QString& path, const QJsonObject& content) {
    QString endpoint = QStringLiteral("/api/contents/") + path;
    auto req = buildRequest(endpoint);

    QJsonObject body;
    body[QStringLiteral("type")]    = QStringLiteral("notebook");
    body[QStringLiteral("content")] = content;

    return m_nam->put(req, QJsonDocument(body).toJson(QJsonDocument::Compact));
}

QNetworkReply* RestClient::createNotebook(const QString& dir) {
    QString endpoint = QStringLiteral("/api/contents");
    if (!dir.isEmpty()) endpoint += QStringLiteral("/") + dir;

    auto req = buildRequest(endpoint);
    QJsonObject body;
    body[QStringLiteral("type")] = QStringLiteral("notebook");

    return m_nam->post(req, QJsonDocument(body).toJson(QJsonDocument::Compact));
}

QNetworkReply* RestClient::startKernel(const QString& name) {
    auto req = buildRequest(QStringLiteral("/api/kernels"));
    QJsonObject body;
    body[QStringLiteral("name")] = name.isEmpty() ? QStringLiteral("python3") : name;
    return m_nam->post(req, QJsonDocument(body).toJson(QJsonDocument::Compact));
}

QNetworkReply* RestClient::shutdownKernel(const QString& id) {
    auto req = buildRequest(QStringLiteral("/api/kernels/") + id);
    return m_nam->deleteResource(req);
}

QNetworkReply* RestClient::restartKernel(const QString& id) {
    auto req = buildRequest(QStringLiteral("/api/kernels/") + id + QStringLiteral("/restart"));
    return m_nam->post(req, QByteArray());
}

QNetworkReply* RestClient::interruptKernel(const QString& id) {
    auto req = buildRequest(QStringLiteral("/api/kernels/") + id + QStringLiteral("/interrupt"));
    return m_nam->post(req, QByteArray());
}

QNetworkReply* RestClient::checkServer() {
    auto req = buildRequest(QStringLiteral("/api"));
    return m_nam->get(req);
}
