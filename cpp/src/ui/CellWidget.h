#pragma once

#include <QWidget>
#include <QFrame>
#include <QLabel>
#include <QPlainTextEdit>
#include <QSyntaxHighlighter>
#include <QTextCharFormat>
#include <QRegularExpression>
#include "models/CellModel.h"

// ── Python syntax highlighter ─────────────────────────────────────────────
class PythonHighlighter : public QSyntaxHighlighter {
    Q_OBJECT
public:
    explicit PythonHighlighter(QTextDocument* parent);
protected:
    void highlightBlock(const QString& text) override;
private:
    struct Rule { QRegularExpression pattern; QTextCharFormat format; };
    QList<Rule> m_rules;
};

// ── Auto-height plain text editor ────────────────────────────────────────
class AutoHeightEditor : public QPlainTextEdit {
    Q_OBJECT
public:
    explicit AutoHeightEditor(QWidget* parent = nullptr);
    void updateHeight();

signals:
    void escapePressed();
    void shiftEnterPressed();
    void focusGained();

protected:
    void keyPressEvent(QKeyEvent* event) override;
    void focusInEvent(QFocusEvent* event) override;
    void scrollContentsBy(int dx, int dy) override;
};

// ── Cell visual mode ─────────────────────────────────────────────────────
enum class CellVisualMode { Normal, Selected, Edit, Executing };

// ── Cell widget ───────────────────────────────────────────────────────────
class OutputArea;

class CellWidget : public QWidget {
    Q_OBJECT
public:
    explicit CellWidget(CellModel* model, QWidget* parent = nullptr);

    QString cellId() const;
    CellModel* cellModel() const { return m_model; }

    void setVisualMode(CellVisualMode mode);
    void setExecuting(bool executing);
    void setExecutionCount(int count);
    void focusEditor();
    void appendOutput(const OutputItem& item);
    void clearOutputs();
    void setSourceSilently(const QString& source);

signals:
    void executeRequested(const QString& cellId);
    void escapePressed(const QString& cellId);
    void editModeRequested(const QString& cellId);
    void sourceChanged(const QString& cellId, const QString& source);
    void addAboveRequested(const QString& cellId);
    void addBelowRequested(const QString& cellId);
    void deleteRequested(const QString& cellId);
    void moveUpRequested(const QString& cellId);
    void moveDownRequested(const QString& cellId);

private:
    void applyStyle();

    CellModel*       m_model;
    QFrame*          m_frame;
    QLabel*          m_prompt;
    AutoHeightEditor* m_editor;
    OutputArea*      m_outputArea;
    CellVisualMode   m_mode = CellVisualMode::Normal;
    bool             m_executing = false;
};
