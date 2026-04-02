#pragma once

#include <QObject>
#include <QString>
#include <QList>
#include <QJsonObject>
#include <QUuid>

enum class CellType {
    Code,
    Markdown,
    Raw
};

struct OutputItem {
    QString output_type;   // "stream", "display_data", "execute_result", "error"
    QJsonObject data;      // mime bundle: {"text/plain": ..., "image/png": ...}
    QString text;          // for stream output
    QString name;          // for stream: "stdout" or "stderr"
    int execution_count = 0;

    // error fields
    QString ename;
    QString evalue;
    QStringList traceback;
};

class CellModel : public QObject {
    Q_OBJECT
public:
    explicit CellModel(QObject* parent = nullptr);

    QString cellId() const { return m_cellId; }
    CellType cellType() const { return m_cellType; }
    QString source() const { return m_source; }
    QList<OutputItem> outputs() const { return m_outputs; }
    int executionCount() const { return m_executionCount; }
    bool isExecuting() const { return m_executing; }

    void setCellType(CellType type);
    void setSource(const QString& source);
    void setExecutionCount(int count);
    void setExecuting(bool executing);

    void appendOutput(const OutputItem& item);
    void clearOutputs();

    QJsonObject toJson() const;
    static CellModel* fromJson(const QJsonObject& obj, QObject* parent = nullptr);

    static QString cellTypeToString(CellType type);
    static CellType cellTypeFromString(const QString& s);

signals:
    void sourceChanged(const QString& source);
    void outputsChanged();
    void executionCountChanged(int count);
    void executingChanged(bool executing);

private:
    QString m_cellId;
    CellType m_cellType = CellType::Code;
    QString m_source;
    QList<OutputItem> m_outputs;
    int m_executionCount = 0;
    bool m_executing = false;
};
