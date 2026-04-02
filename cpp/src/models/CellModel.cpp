#include "CellModel.h"
#include <QJsonArray>

CellModel::CellModel(QObject* parent)
    : QObject(parent)
    , m_cellId(QUuid::createUuid().toString(QUuid::WithoutBraces))
{
}

void CellModel::setCellType(CellType type) {
    m_cellType = type;
}

void CellModel::setSource(const QString& source) {
    if (m_source != source) {
        m_source = source;
        emit sourceChanged(source);
    }
}

void CellModel::setExecutionCount(int count) {
    if (m_executionCount != count) {
        m_executionCount = count;
        emit executionCountChanged(count);
    }
}

void CellModel::setExecuting(bool executing) {
    if (m_executing != executing) {
        m_executing = executing;
        emit executingChanged(executing);
    }
}

void CellModel::appendOutput(const OutputItem& item) {
    m_outputs.append(item);
    emit outputsChanged();
}

void CellModel::clearOutputs() {
    if (!m_outputs.isEmpty()) {
        m_outputs.clear();
        emit outputsChanged();
    }
}

QString CellModel::cellTypeToString(CellType type) {
    switch (type) {
        case CellType::Code:     return QStringLiteral("code");
        case CellType::Markdown: return QStringLiteral("markdown");
        case CellType::Raw:      return QStringLiteral("raw");
    }
    return QStringLiteral("code");
}

CellType CellModel::cellTypeFromString(const QString& s) {
    if (s == QLatin1String("markdown")) return CellType::Markdown;
    if (s == QLatin1String("raw"))      return CellType::Raw;
    return CellType::Code;
}

QJsonObject CellModel::toJson() const {
    QJsonObject obj;
    obj[QStringLiteral("id")] = m_cellId;
    obj[QStringLiteral("cell_type")] = cellTypeToString(m_cellType);
    obj[QStringLiteral("source")] = m_source;

    if (m_cellType == CellType::Code) {
        obj[QStringLiteral("execution_count")] = m_executionCount > 0
            ? QJsonValue(m_executionCount)
            : QJsonValue(QJsonValue::Null);
    }

    QJsonArray outputs;
    for (const auto& out : m_outputs) {
        QJsonObject o;
        o[QStringLiteral("output_type")] = out.output_type;
        if (out.output_type == QLatin1String("stream")) {
            o[QStringLiteral("name")] = out.name;
            o[QStringLiteral("text")] = out.text;
        } else if (out.output_type == QLatin1String("error")) {
            o[QStringLiteral("ename")] = out.ename;
            o[QStringLiteral("evalue")] = out.evalue;
            QJsonArray tb;
            for (const auto& line : out.traceback) tb.append(line);
            o[QStringLiteral("traceback")] = tb;
        } else {
            o[QStringLiteral("data")] = out.data;
            if (out.output_type == QLatin1String("execute_result")) {
                o[QStringLiteral("execution_count")] = out.execution_count;
            }
            o[QStringLiteral("metadata")] = QJsonObject();
        }
        outputs.append(o);
    }
    obj[QStringLiteral("outputs")] = outputs;
    obj[QStringLiteral("metadata")] = QJsonObject();

    return obj;
}

CellModel* CellModel::fromJson(const QJsonObject& obj, QObject* parent) {
    auto* cell = new CellModel(parent);

    // Use stored id if present
    if (obj.contains(QStringLiteral("id"))) {
        cell->m_cellId = obj[QStringLiteral("id")].toString();
    }

    cell->m_cellType = cellTypeFromString(obj[QStringLiteral("cell_type")].toString());

    // source may be string or array of strings
    auto srcVal = obj[QStringLiteral("source")];
    if (srcVal.isArray()) {
        QStringList lines;
        for (const auto& v : srcVal.toArray()) lines << v.toString();
        cell->m_source = lines.join(QString());
    } else {
        cell->m_source = srcVal.toString();
    }

    auto ecVal = obj[QStringLiteral("execution_count")];
    if (ecVal.isDouble()) {
        cell->m_executionCount = ecVal.toInt();
    }

    auto outputsArr = obj[QStringLiteral("outputs")].toArray();
    for (const auto& ov : outputsArr) {
        auto o = ov.toObject();
        OutputItem item;
        item.output_type = o[QStringLiteral("output_type")].toString();

        if (item.output_type == QLatin1String("stream")) {
            item.name = o[QStringLiteral("name")].toString();
            auto textVal = o[QStringLiteral("text")];
            if (textVal.isArray()) {
                QStringList lines;
                for (const auto& v : textVal.toArray()) lines << v.toString();
                item.text = lines.join(QString());
            } else {
                item.text = textVal.toString();
            }
        } else if (item.output_type == QLatin1String("error")) {
            item.ename = o[QStringLiteral("ename")].toString();
            item.evalue = o[QStringLiteral("evalue")].toString();
            for (const auto& v : o[QStringLiteral("traceback")].toArray()) {
                item.traceback << v.toString();
            }
        } else {
            item.data = o[QStringLiteral("data")].toObject();
            item.execution_count = o[QStringLiteral("execution_count")].toInt();
        }

        cell->m_outputs.append(item);
    }

    return cell;
}
