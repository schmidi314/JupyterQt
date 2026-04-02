#pragma once

#include <QTextBrowser>

class HtmlRenderer : public QTextBrowser {
    Q_OBJECT
public:
    explicit HtmlRenderer(QWidget* parent = nullptr);
    void setHtmlContent(const QString& html);

protected:
    void resizeEvent(QResizeEvent* event) override;

private:
    void updateHeight();
};
