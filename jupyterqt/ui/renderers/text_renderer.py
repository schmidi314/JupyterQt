from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import QTextEdit


class TextRenderer(QTextEdit):
    """Renders plain stdout/stderr text, respecting stream name for coloring."""

    def __init__(self, text: str, stream_name: str = "stdout", parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameStyle(0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        from jupyterqt.settings import Settings
        font = QFont("Monospace", Settings.instance().output_font_size)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        Settings.instance().output_font_size_changed.connect(self._on_font_size_changed)

        if stream_name == "stderr":
            self.setStyleSheet("QTextEdit { color: #cc0000; background: transparent; border: none; }")
        else:
            self.setStyleSheet("QTextEdit { background: transparent; border: none; }")

        self.setPlainText(text)
        self._adjust_height()

    def _adjust_height(self):
        doc = self.document()
        doc.setTextWidth(self.width() if self.width() > 0 else 600)
        height = int(doc.size().height()) + 4
        self.setFixedHeight(max(height, 20))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_height()

    def _on_font_size_changed(self, size: int) -> None:
        f = self.font()
        f.setPointSize(size)
        self.setFont(f)
        self._adjust_height()

    def append_text(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self._adjust_height()
