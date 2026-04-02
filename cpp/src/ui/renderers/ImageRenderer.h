#pragma once

#include <QLabel>
#include <QString>

class ImageRenderer : public QLabel {
    Q_OBJECT
public:
    explicit ImageRenderer(QWidget* parent = nullptr);
    void setImageData(const QString& base64Data, const QString& mimeType = QStringLiteral("image/png"));

private:
    QPixmap m_originalPixmap;
};
