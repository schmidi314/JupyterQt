#include "ImageRenderer.h"
#include <QPixmap>

ImageRenderer::ImageRenderer(QWidget* parent)
    : QLabel(parent)
{
    setAlignment(Qt::AlignLeft | Qt::AlignTop);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    setScaledContents(false);
}

void ImageRenderer::setImageData(const QString& base64Data, const QString& /*mimeType*/) {
    QByteArray imgData = QByteArray::fromBase64(base64Data.toLatin1());
    m_originalPixmap.loadFromData(imgData);

    if (m_originalPixmap.isNull()) {
        setText(QStringLiteral("[Image failed to load]"));
        return;
    }

    // Scale to reasonable width while preserving aspect ratio
    int maxWidth = 700;
    if (m_originalPixmap.width() > maxWidth) {
        setPixmap(m_originalPixmap.scaledToWidth(maxWidth, Qt::SmoothTransformation));
    } else {
        setPixmap(m_originalPixmap);
    }
    setFixedHeight(pixmap().height());
}
