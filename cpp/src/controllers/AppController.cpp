#include "AppController.h"
#include "NotebookController.h"
#include <QNetworkReply>

AppController::AppController(QObject* parent)
    : QObject(parent)
    , m_restClient(new RestClient(this))
    , m_tracker(new ExecutionTracker(this))
{
}

AppController::~AppController() {
    qDeleteAll(m_notebooks);
}

void AppController::setServerConfig(const ServerConfig& config) {
    m_config = config;
    m_restClient->setConfig(config);

    // Seed XSRF cookie
    auto* reply = m_restClient->fetchXsrf();
    connect(reply, &QNetworkReply::finished, reply, &QNetworkReply::deleteLater);
}

void AppController::checkServer() {
    auto* reply = m_restClient->checkServer();
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        int code = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        if (reply->error() == QNetworkReply::NoError && code == 200) {
            emit serverChecked(QStringLiteral("ok"));
        } else if (code == 401 || code == 403) {
            emit serverChecked(QStringLiteral("unauthorized"));
        } else {
            emit serverChecked(reply->errorString());
        }
    });
}

void AppController::openNotebook(const QString& path) {
    // Check if already open
    for (auto it = m_notebooks.begin(); it != m_notebooks.end(); ++it) {
        if (it.value()->notebookModel()->path() == path) {
            emit notebookOpened(it.key(), it.value());
            return;
        }
    }

    QString notebookId = QStringLiteral("nb-%1").arg(++m_notebookCounter);
    auto* controller = new NotebookController(notebookId, m_restClient, m_tracker, this);
    m_notebooks[notebookId] = controller;

    controller->load(path, m_config);
    emit notebookOpened(notebookId, controller);
}

void AppController::closeNotebook(const QString& notebookId) {
    auto* controller = m_notebooks.take(notebookId);
    if (!controller) return;

    controller->shutdownKernel();
    controller->deleteLater();
    emit notebookClosed(notebookId);
}

NotebookController* AppController::notebookController(const QString& notebookId) const {
    return m_notebooks.value(notebookId, nullptr);
}

QList<NotebookController*> AppController::allNotebooks() const {
    return m_notebooks.values();
}
