#include "ExecutionTracker.h"

ExecutionTracker::ExecutionTracker(QObject* parent)
    : QObject(parent)
{
}

void ExecutionTracker::track(const QString& msgId, CellModel* cell, const QString& notebookId) {
    m_entries[msgId] = Entry{cell, notebookId};
}

void ExecutionTracker::cancel(const QString& msgId) {
    m_entries.remove(msgId);
}

void ExecutionTracker::cancelAllForNotebook(const QString& notebookId) {
    auto it = m_entries.begin();
    while (it != m_entries.end()) {
        if (it.value().notebookId == notebookId) {
            it = m_entries.erase(it);
        } else {
            ++it;
        }
    }
}

void ExecutionTracker::cancelAll() {
    m_entries.clear();
}

CellModel* ExecutionTracker::cell(const QString& msgId) const {
    auto it = m_entries.find(msgId);
    if (it != m_entries.end()) return it.value().cell;
    return nullptr;
}

QString ExecutionTracker::notebookId(const QString& msgId) const {
    auto it = m_entries.find(msgId);
    if (it != m_entries.end()) return it.value().notebookId;
    return {};
}

bool ExecutionTracker::contains(const QString& msgId) const {
    return m_entries.contains(msgId);
}

QStringList ExecutionTracker::msgIdsForNotebook(const QString& notebookId) const {
    QStringList ids;
    for (auto it = m_entries.begin(); it != m_entries.end(); ++it) {
        if (it.value().notebookId == notebookId) {
            ids << it.key();
        }
    }
    return ids;
}
