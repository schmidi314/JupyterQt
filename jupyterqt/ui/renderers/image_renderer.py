import base64

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class ImageRenderer(QLabel):
    """Renders a base64-encoded PNG/JPEG/SVG image."""

    def __init__(self, b64_data: str, mime_type: str = "image/png", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._original_pixmap = QPixmap()
        try:
            raw = base64.b64decode(b64_data)
            self._original_pixmap.loadFromData(raw)
        except Exception:
            self.setText("[Image failed to load]")
            return
        if self._original_pixmap.isNull():
            self.setText("[Image failed to load]")
        else:
            self._display_pixmap()

    def _display_pixmap(self):
        if self._original_pixmap.isNull():
            return
        max_w = self.parent().width() if self.parent() else 700
        if max_w <= 0:
            max_w = 700
        if self._original_pixmap.width() > max_w:
            scaled = self._original_pixmap.scaledToWidth(
                max_w, Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)
            self.setFixedSize(scaled.size())
        else:
            self.setPixmap(self._original_pixmap)
            self.setFixedSize(self._original_pixmap.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._display_pixmap()
