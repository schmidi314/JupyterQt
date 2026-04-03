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
        self._layout.setSpacing(2)
        # Track stream widgets per stream_name for appending
        self._stream_widgets: dict[str, TextRenderer] = {}

    def appendOutput(self, output: OutputItem) -> None:
        widget = self._render(output)
        if widget:
            self._layout.addWidget(widget)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stream_widgets.clear()

    def _render(self, output: OutputItem) -> QWidget | None:
        if output.output_type == "error":
            return ErrorRenderer(output.data, self)

        if output.output_type == "stream":
            name = output.data.get("stream_name", "stdout")
            text = output.text or ""
            # Append to existing stream widget if same stream_name
            if name in self._stream_widgets:
                self._stream_widgets[name].appendText(text)
                return None
            w = TextRenderer(text, stream_name=name, parent=self)
            self._stream_widgets[name] = w
            return w

        # For display_data and execute_result, check MIME types in priority order
        data = output.data
        if not data:
            return None

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
            # Clear stream widgets so execute_result doesn't get merged
            self._stream_widgets.clear()
            return TextRenderer(data["text/plain"], parent=self)
        return None
