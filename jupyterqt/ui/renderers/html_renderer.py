from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextBrowser


class HtmlRenderer(QTextBrowser):
    def __init__(self, html: str, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameStyle(0)
        self.setOpenExternalLinks(True)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        from jupyterqt.settings import Settings
        font = QFont("Monospace", Settings.instance().outputFontSize)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        Settings.instance().output_font_size_changed.connect(self._onFontSizeChanged)
        self.setHtml(html)
        self._adjustHeight()

    def _onFontSizeChanged(self, size: int) -> None:
        f = self.font()
        f.setPointSize(size)
        self.setFont(f)
        self._adjustHeight()

    def _adjustHeight(self):
        doc = self.document()
        doc.setTextWidth(self.width() if self.width() > 0 else 600)
        height = int(doc.size().height()) + 4
        self.setFixedHeight(max(height, 20))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjustHeight()
