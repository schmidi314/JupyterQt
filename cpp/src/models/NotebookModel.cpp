#include "NotebookModel.h"
#include <QJsonArray>
#include <QFileInfo>

NotebookModel::NotebookModel(QObject* parent)
    : QObject(parent)
{
}

NotebookModel::~NotebookModel() {
    qDeleteAll(m_cells);
}

QString NotebookModel::name() const {
    return QFileInfo(m_path).fileName();
}

CellModel* NotebookModel::cell(const QString& cellId) const {
    for (auto* c : m_cells) {
        if (c->cellId() == cellId) return c;
    }
    return nullptr;
}

int NotebookModel::cellIndex(const QString& cellId) const {
    for (int i = 0; i < m_cells.size(); ++i) {
        if (m_cells[i]->cellId() == cellId) return i;
    }
    return -1;
}

void NotebookModel::loadFromJson(const QJsonObject& nbJson) {
    qDeleteAll(m_cells);
    m_cells.clear();

    m_metadata = nbJson[QStringLiteral("metadata")].toObject();
    m_nbformat = nbJson[QStringLiteral("nbformat")].toInt(4);
    m_nbformat_minor = nbJson[QStringLiteral("nbformat_minor")].toInt(5);

    auto kernelspec = m_metadata[QStringLiteral("kernelspec")].toObject();
    m_kernelName = kernelspec[QStringLiteral("name")].toString(QStringLiteral("python3"));

    auto cellsArr = nbJson[QStringLiteral("cells")].toArray();
    for (const auto& cv : cellsArr) {
        auto* cell = CellModel::fromJson(cv.toObject(), this);
        m_cells.append(cell);
    }
}

QJsonObject NotebookModel::toJson() const {
    QJsonObject nb;
    nb[QStringLiteral("nbformat")] = m_nbformat;
    nb[QStringLiteral("nbformat_minor")] = m_nbformat_minor;
    nb[QStringLiteral("metadata")] = m_metadata;

    QJsonArray cells;
    for (auto* c : m_cells) {
        cells.append(c->toJson());
    }
    nb[QStringLiteral("cells")] = cells;
    return nb;
}

CellModel* NotebookModel::addCell(CellType type, int index) {
    auto* cell = new CellModel(this);
    cell->setCellType(type);

    if (index < 0 || index >= m_cells.size()) {
        m_cells.append(cell);
        emit cellAdded(m_cells.size() - 1, cell);
    } else {
        m_cells.insert(index, cell);
        emit cellAdded(index, cell);
    }
    return cell;
}

void NotebookModel::removeCell(const QString& cellId) {
    int idx = cellIndex(cellId);
    if (idx < 0) return;
    auto* c = m_cells.takeAt(idx);
    emit cellRemoved(cellId);
    c->deleteLater();
}

void NotebookModel::moveCell(const QString& cellId, int newIndex) {
    int idx = cellIndex(cellId);
    if (idx < 0) return;
    newIndex = qBound(0, newIndex, m_cells.size() - 1);
    if (idx == newIndex) return;
    auto* c = m_cells.takeAt(idx);
    m_cells.insert(newIndex, c);
    emit cellMoved(cellId, newIndex);
}
