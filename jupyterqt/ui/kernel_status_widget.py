from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from jupyterqt.models.kernel_state import KernelStatus

_STATUS_COLORS = {
    KernelStatus.DISCONNECTED: "#888888",
    KernelStatus.CONNECTING:   "#aaaaff",
    KernelStatus.IDLE:         "#44aa44",
    KernelStatus.BUSY:         "#ffaa00",
    KernelStatus.RESTARTING:   "#ffaa00",
    KernelStatus.ERROR:        "#cc0000",
}

_STATUS_LABELS = {
    KernelStatus.DISCONNECTED: "Disconnected",
    KernelStatus.CONNECTING:   "Connecting...",
    KernelStatus.IDLE:         "Idle",
    KernelStatus.BUSY:         "Busy",
    KernelStatus.RESTARTING:   "Restarting...",
    KernelStatus.ERROR:        "Error",
}


class _LED(QWidget):
    def __init__(self, color: str = "#888888", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(12, 12)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 10, 10)


class KernelStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        self._led = _LED(parent=self)
        self._label = QLabel("Disconnected", self)
        layout.addWidget(self._led)
        layout.addWidget(self._label)

    def set_status(self, status: KernelStatus) -> None:
        color = _STATUS_COLORS.get(status, "#888888")
        label = _STATUS_LABELS.get(status, str(status.value))
        self._led.set_color(color)
        self._label.setText(label)
