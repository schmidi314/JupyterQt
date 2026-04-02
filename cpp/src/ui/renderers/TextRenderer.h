#pragma once

#include <QTextEdit>
#include <QString>

class TextRenderer : public QTextEdit {
    Q_OBJECT
public:
    explicit TextRenderer(QWidget* parent = nullptr);
    void setContent(const QString& text, bool isStderr = false);
    void appendContent(const QString& text, bool isStderr = false);

protected:
    void resizeEvent(QResizeEvent* event) override;

private:
    void updateHeight();
};
