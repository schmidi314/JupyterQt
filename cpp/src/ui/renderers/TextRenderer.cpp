#include "TextRenderer.h"
#include <QResizeEvent>
#include <QScrollBar>

TextRenderer::TextRenderer(QWidget* parent)
    : QTextEdit(parent)
{
    setReadOnly(true);
    setLineWrapMode(QTextEdit::NoWrap);
    setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    setFrameShape(QFrame::NoFrame);

    QFont mono(QStringLiteral("Monospace"), 10);
    mono.setStyleHint(QFont::Monospace);
    setFont(mono);
}

void TextRenderer::setContent(const QString& text, bool isStderr) {
    clear();
    if (isStderr) {
        setTextColor(Qt::red);
    } else {
        setTextColor(palette().text().color());
    }
    setPlainText(text);
    updateHeight();
}

void TextRenderer::appendContent(const QString& text, bool isStderr) {
    moveCursor(QTextCursor::End);
    if (isStderr) {
        setTextColor(Qt::red);
    } else {
        setTextColor(palette().text().color());
    }
    insertPlainText(text);
    updateHeight();
}

void TextRenderer::resizeEvent(QResizeEvent* event) {
    QTextEdit::resizeEvent(event);
    updateHeight();
}

void TextRenderer::updateHeight() {
    document()->setTextWidth(viewport()->width());
    int h = static_cast<int>(document()->size().height()) + 4;
    setFixedHeight(qMax(h, 20));
}
