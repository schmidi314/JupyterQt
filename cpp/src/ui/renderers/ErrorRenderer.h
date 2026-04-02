#pragma once

#include <QTextEdit>
#include <QStringList>

class ErrorRenderer : public QTextEdit {
    Q_OBJECT
public:
    explicit ErrorRenderer(QWidget* parent = nullptr);
    void setError(const QString& ename, const QString& evalue,
                  const QStringList& traceback);

protected:
    void resizeEvent(QResizeEvent* event) override;

private:
    static QString ansiToHtml(const QString& text);
    void updateHeight();
};
