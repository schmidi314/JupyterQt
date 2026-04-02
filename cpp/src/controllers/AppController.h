#pragma once

#include <QObject>
#include <QHash>
#include <QString>
#include "config/ServerConfig.h"
#include "network/RestClient.h"
#include "jupyter/ExecutionTracker.h"

class NotebookController;

class AppController : public QObject {
    Q_OBJECT
public:
    explicit AppController(QObject* parent = nullptr);
    ~AppController() override;

    void setServerConfig(const ServerConfig& config);
    const ServerConfig& serverConfig() const { return m_config; }

    void checkServer();
    void openNotebook(const QString& path);
    void closeNotebook(const QString& notebookId);

    NotebookController* notebookController(const QString& notebookId) const;
    QList<NotebookController*> allNotebooks() const;

    RestClient* restClient() { return m_restClient; }

signals:
    void notebookOpened(const QString& notebookId, NotebookController* controller);
    void notebookClosed(const QString& notebookId);
    void serverChecked(const QString& result); // "ok", "unauthorized", or error message

private:
    ServerConfig m_config;
    RestClient* m_restClient;
    ExecutionTracker* m_tracker;
    QHash<QString, NotebookController*> m_notebooks;

    int m_notebookCounter = 0;
};
