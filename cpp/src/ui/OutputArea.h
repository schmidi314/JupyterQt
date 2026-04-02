#pragma once

#include <QWidget>
#include <QVBoxLayout>
#include "models/CellModel.h"

class TextRenderer;

class OutputArea : public QWidget {
    Q_OBJECT
public:
    explicit OutputArea(QWidget* parent = nullptr);

    void appendOutput(const OutputItem& item);
    void clearOutputs();

private:
    QWidget* renderItem(const OutputItem& item);

    QVBoxLayout* m_layout;
    // Track per-stream TextRenderer for appending
    QHash<QString, TextRenderer*> m_streamWidgets;
};
