import re

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextEdit


# Maps ANSI color codes to CSS colors
_ANSI_COLORS = {
    "30": "#000000", "31": "#cc0000", "32": "#00aa00", "33": "#aaaa00",
    "34": "#0000cc", "35": "#aa00aa", "36": "#00aaaa", "37": "#aaaaaa",
    "90": "#555555", "91": "#ff5555", "92": "#55ff55", "93": "#ffff55",
    "94": "#5555ff", "95": "#ff55ff", "96": "#55ffff", "97": "#ffffff",
    # Bold versions (via 1;3x)
    "1;31": "#ff0000", "1;32": "#00ff00", "1;33": "#ffff00",
    "1;34": "#5555ff", "1;35": "#ff55ff", "1;36": "#55ffff",
    "1;37": "#ffffff",
}

_ANSI_PATTERN = re.compile(r'\x1b\[([0-9;]*)m')


def _ansi_to_html(text: str) -> str:
    result = []
    last_end = 0
    open_span = False

    def escape_html(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    for match in _ANSI_PATTERN.finditer(text):
        # Add text before this escape
        before = escape_html(text[last_end:match.start()])
        result.append(before)
        last_end = match.end()

        code = match.group(1)
        if code in ("", "0", "00"):
            if open_span:
                result.append("</span>")
                open_span = False
        elif code in _ANSI_COLORS:
            if open_span:
                result.append("</span>")
            result.append(f'<span style="color:{_ANSI_COLORS[code]}">')
            open_span = True

    result.append(escape_html(text[last_end:]))
    if open_span:
        result.append("</span>")
    return "".join(result)


class ErrorRenderer(QTextEdit):
    def __init__(self, content: dict, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameStyle(0)
        from jupyterqt.settings import Settings
        font = QFont("Monospace", Settings.instance().output_font_size)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        Settings.instance().output_font_size_changed.connect(self._on_font_size_changed)
        self.setStyleSheet(
            "QTextEdit { background: #fff0f0; border: 1px solid #ffcccc; "
            "border-radius: 3px; padding: 4px; }"
        )

        ename = content.get("ename", "Error")
        evalue = content.get("evalue", "")
        traceback_lines = content.get("traceback", [])

        html_parts = [
            f'<span style="color:#cc0000; font-weight:bold">{ename}: </span>'
            f'<span style="color:#cc0000">{evalue}</span><br>'
        ]
        for line in traceback_lines:
            html_parts.append(_ansi_to_html(line) + "<br>")

        self.setHtml("".join(html_parts))
        self._adjust_height()

    def _on_font_size_changed(self, size: int) -> None:
        f = self.font()
        f.setPointSize(size)
        self.setFont(f)
        self._adjust_height()

    def _adjust_height(self):
        doc = self.document()
        doc.setTextWidth(self.width() if self.width() > 0 else 600)
        height = int(doc.size().height()) + 8
        self.setFixedHeight(max(height, 40))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_height()
