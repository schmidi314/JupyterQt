from PySide6.QtWidgets import QWidget, QVBoxLayout

from jupyterqt.models.cell_model import OutputItem
from jupyterqt.ui.renderers.error_renderer import ErrorRenderer
from jupyterqt.ui.renderers.html_renderer import HtmlRenderer
from jupyterqt.ui.renderers.image_renderer import ImageRenderer
from jupyterqt.ui.renderers.text_renderer import TextRenderer


class OutputArea(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)
        # Track stream widgets per stream_name for appending
        self._stream_widgets: dict[str, TextRenderer] = {}

    def appendOutput(self, output: OutputItem) -> None:
        widget = self._render(output)
        if widget:
            self._layout.insertWidget(self._layout.count() - 1, widget)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._layout.addStretch(1)
        self._stream_widgets.clear()

    def _render(self, output: OutputItem) -> QWidget | None:
        if not output.data:
            return None
        data = output.data
        if output.output_type == "error":
            return ErrorRenderer(data, self)
        # Matplotlib/PIL images come as image/png
        if "image/png" in data:
            return ImageRenderer(data["image/png"], "image/png", self)
        if "image/jpeg" in data:
            return ImageRenderer(data["image/jpeg"], "image/jpeg", self)
        if "image/svg+xml" in data:
            return HtmlRenderer(data["image/svg+xml"], self)
        if "text/html" in data:
            return HtmlRenderer(data["text/html"], self)
        if "text/plain" in data:
            return TextRenderer(data["text/plain"], parent=self)
        return None
