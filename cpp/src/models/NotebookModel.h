#pragma once

#include <QObject>
#include <QList>
#include <QString>
#include <QJsonObject>
#include "CellModel.h"

class NotebookModel : public QObject {
    Q_OBJECT
public:
    explicit NotebookModel(QObject* parent = nullptr);
    ~NotebookModel() override;

    QString path() const { return m_path; }
    QString name() const;
    QString kernelName() const { return m_kernelName; }
    QString kernelId() const { return m_kernelId; }

    void setPath(const QString& path) { m_path = path; }
    void setKernelId(const QString& id) { m_kernelId = id; }

    QList<CellModel*> cells() const { return m_cells; }
    CellModel* cell(const QString& cellId) const;
    int cellIndex(const QString& cellId) const;

    void loadFromJson(const QJsonObject& nbJson);
    QJsonObject toJson() const;

    CellModel* addCell(CellType type, int index = -1);
    void removeCell(const QString& cellId);
    void moveCell(const QString& cellId, int newIndex);

signals:
    void cellAdded(int index, CellModel* cell);
    void cellRemoved(const QString& cellId);
    void cellMoved(const QString& cellId, int newIndex);

private:
    QString m_path;
    QString m_kernelName;
    QString m_kernelId;
    QList<CellModel*> m_cells;
    QJsonObject m_metadata;
    int m_nbformat = 4;
    int m_nbformat_minor = 5;
};
