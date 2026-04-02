#pragma once

#include <QWidget>
#include <QTreeWidget>
#include <QLabel>
#include "config/ServerConfig.h"
#include "network/RestClient.h"

class FileBrowser : public QWidget {
    Q_OBJECT
public:
    explicit FileBrowser(QWidget* parent = nullptr);

    void setConfig(const ServerConfig& config);
    void refresh();

signals:
    void notebookSelected(const QString& path);
    void newNotebookRequested(const QString& directory);

private slots:
    void onItemDoubleClicked(QTreeWidgetItem* item, int column);
    void onRefreshClicked();

private:
    void loadContents(const QString& path);
    void populateTree(const QJsonDocument& doc);

    RestClient*   m_rest;
    QTreeWidget*  m_tree;
    QLabel*       m_pathLabel;
    QString       m_currentPath;
};
