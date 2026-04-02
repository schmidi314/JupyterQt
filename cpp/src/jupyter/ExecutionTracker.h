#pragma once

#include <QObject>
#include <QHash>
#include <QPair>
#include <QString>

class CellModel;

class ExecutionTracker : public QObject {
    Q_OBJECT
public:
    explicit ExecutionTracker(QObject* parent = nullptr);

    void track(const QString& msgId, CellModel* cell, const QString& notebookId);
    void cancel(const QString& msgId);
    void cancelAllForNotebook(const QString& notebookId);
    void cancelAll();

    CellModel* cell(const QString& msgId) const;
    QString notebookId(const QString& msgId) const;
    bool contains(const QString& msgId) const;

    QStringList msgIdsForNotebook(const QString& notebookId) const;

private:
    struct Entry {
        CellModel* cell;
        QString notebookId;
    };
    QHash<QString, Entry> m_entries;
};
