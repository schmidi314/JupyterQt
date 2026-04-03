import re

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import (QFont, QColor, QTextOption, QSyntaxHighlighter,
                            QTextCharFormat)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                                QLabel, QFrame, QSizePolicy, QListWidget,
                                QListWidgetItem, QTextBrowser, QApplication,
                                QToolButton)

from jupyterqt.models.cell_model import CellModel, CellType, OutputItem
from jupyterqt.ui.output_area import OutputArea


# #########################################################################################################################################
# Heading detection

_HEADING_RE = re.compile(r'^#{1,6}')


def _headingLevel(source: str) -> int:
    """Returns 1-6 if source starts with markdown heading hashes, else 0."""
    m = _HEADING_RE.match(source.lstrip('\n'))
    return len(m.group(0)) if m else 0


# #########################################################################################################################################
# Markdown CSS

_MD_CSS = """<style>
body { font-family: sans-serif; margin: 0; padding: 2px 4px; }
h1 { font-size: 1.8em; font-weight: bold; margin: 4px 0 2px 0; border-bottom: 1px solid #ddd; padding-bottom: 2px; }
h2 { font-size: 1.4em; font-weight: bold; margin: 4px 0 2px 0; }
h3 { font-size: 1.15em; font-weight: bold; margin: 4px 0 2px 0; }
h4, h5, h6 { font-size: 1.0em; font-weight: bold; margin: 4px 0 2px 0; }
p { margin: 2px 0; }
code { background: #f0f0f0; padding: 1px 3px; font-family: monospace; border-radius: 2px; }
pre { background: #f0f0f0; padding: 8px; border-radius: 4px; }
ul, ol { margin: 2px 0; padding-left: 24px; }
li { margin: 1px 0; }
blockquote { border-left: 3px solid #ddd; margin: 4px 0; padding-left: 8px; color: #666; }
table { border-collapse: collapse; margin: 4px 0; }
th, td { border: 1px solid #ddd; padding: 4px 8px; }
th { background: #f5f5f5; font-weight: bold; }
</style>"""


# #########################################################################################################################################
# Syntax highlighter (code cells)

class _PythonHighlighter(QSyntaxHighlighter):
    _KEYWORDS = [
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield",
    ]

    def __init__(self, document):
        super().__init__(document)
        import re as _re
        self._rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#0000aa"))
        kw_fmt.setFontWeight(700)
        self._rules.append((_re.compile(r'\b(' + '|'.join(self._KEYWORDS) + r')\b'), kw_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#008000"))
        self._rules.append((_re.compile(r'\".*?\"|\'.*?\''), str_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#808080"))
        comment_fmt.setFontItalic(True)
        self._rules.append((_re.compile(r'#[^\n]*'), comment_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#aa5500"))
        self._rules.append((_re.compile(r'\b\d+(\.\d+)?\b'), num_fmt))

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#6600aa"))
        self._rules.append((_re.compile(r'\b\w+(?=\()'), func_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# #########################################################################################################################################
# Completion popup

class _CompletionPopup(QFrame):
    """Floating completion list; never steals keyboard focus from the editor."""

    def __init__(self, parent_editor):
        super().__init__(parent_editor.window(), Qt.WindowType.ToolTip)
        self._editor = parent_editor
        self._cursor_start = 0
        self._cursor_end = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setFrameStyle(0)
        self._list.setFont(parent_editor.font())
        self._list.itemDoubleClicked.connect(self._onDoubleClick)
        layout.addWidget(self._list)
        self.setStyleSheet(
            "QFrame { background: white; border: 1px solid #aaaacc; }"
            "QListWidget { background: white; border: none; }"
            "QListWidget::item { padding: 1px 4px; }"
            "QListWidget::item:selected { background: #0066cc; color: white; }"
        )
        self.hide()

    def populate(self, matches: list, cursor_start: int, cursor_end: int, global_pos) -> None:
        self._cursor_start = cursor_start
        self._cursor_end = cursor_end
        self._list.clear()
        for m in matches:
            self._list.addItem(QListWidgetItem(m))
        if self._list.count() == 0:
            self.hide()
            return
        self._list.setCurrentRow(0)
        col_width = self._list.sizeHintForColumn(0)
        width = max(180, min(420, col_width + 24))
        row_h = self._list.sizeHintForRow(0) if self._list.count() else 20
        height = min(10, self._list.count()) * row_h + 4
        self.resize(width, height)
        self.move(global_pos)
        self.show()

    def moveSelection(self, delta: int) -> None:
        row = max(0, min(self._list.currentRow() + delta, self._list.count() - 1))
        self._list.setCurrentRow(row)

    def acceptCurrent(self) -> tuple[str | None, int, int]:
        item = self._list.currentItem()
        if item:
            return item.text(), self._cursor_start, self._cursor_end
        return None, 0, 0

    def _onDoubleClick(self, item: QListWidgetItem) -> None:
        self.hide()
        self._editor._applyCompletion(item.text(), self._cursor_start, self._cursor_end)
        self._editor.setFocus()


# #########################################################################################################################################
# Inspect popup

class _InspectPopup(QFrame):
    """Shows function signature and docstring from an inspect_reply."""

    _MAX_W = 620
    _MAX_H = 360

    def __init__(self, parent_editor):
        super().__init__(parent_editor.window(), Qt.WindowType.ToolTip)
        self._editor = parent_editor
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)
        self._browser = QTextBrowser()
        self._browser.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._browser.setFrameStyle(0)
        self._browser.setOpenExternalLinks(False)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._browser)
        self.setStyleSheet(
            "QFrame { background: #fffff0; border: 1px solid #c8c880; }"
            "QTextBrowser { background: #fffff0; border: none; }"
        )
        self.hide()

    def showContent(self, mime_data: dict, cursor_global_pos, line_height: int) -> None:
        from jupyterqt.settings import Settings
        size = Settings.instance().outputFontSize

        if "text/html" in mime_data:
            html = mime_data["text/html"]
            self._browser.setHtml(
                f'<div style="font-family:monospace; font-size:{size}pt">{html}</div>'
            )
        else:
            from jupyterqt.ui.renderers.error_renderer import _ansiToHtml
            text = mime_data.get("text/plain", "")
            html = _ansiToHtml(text).replace("\n", "<br>")
            self._browser.setHtml(
                f'<span style="font-family:monospace; font-size:{size}pt">{html}</span>'
            )

        self.resize(self._MAX_W, self._MAX_H)

        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(cursor_global_pos.x(), screen.right() - self._MAX_W))
        y_above = cursor_global_pos.y() - self._MAX_H - 4
        y_below = cursor_global_pos.y() + line_height + 4
        y = y_above if y_above >= screen.top() else y_below
        self.move(x, y)
        self.show()
        self.raise_()


# #########################################################################################################################################
# Base editor

class _AutoHeightEditor(QPlainTextEdit):
    """Base class: no scrollbars, height tracks document content exactly."""
    escape_pressed = Signal()
    focused = Signal()
    shift_enter_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().contentsChanged.connect(self._updateHeight)
        self.horizontalScrollBar().valueChanged.connect(self._updateHeight)
        self.horizontalScrollBar().setStyleSheet(
            "QScrollBar:horizontal { height: 8px; }"
        )
        from jupyterqt.settings import Settings
        Settings.instance().input_font_size_changed.connect(self._onFontSizeChanged)

    def _onFontSizeChanged(self, size: int) -> None:
        f = self.font()
        f.setPointSize(size)
        self.setFont(f)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self._updateHeight()

    def _updateHeight(self):
        fm = self.fontMetrics()
        n = max(1, self.document().blockCount())
        doc_margin = self.document().documentMargin()
        self.setFixedHeight(int(fm.lineSpacing() * n + doc_margin * 2 + 6 + (self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0)))

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        if dx != 0:
            super().scrollContentsBy(dx, 0)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focused.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            return
        if (event.key() == Qt.Key.Key_Return and
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.shift_enter_pressed.emit()
            return
        super().keyPressEvent(event)


# #########################################################################################################################################
# Code editor

class _CodeEditor(_AutoHeightEditor):
    def __init__(self, parent=None):
        super().__init__(parent)
        from jupyterqt.settings import Settings
        font = QFont("Monospace", Settings.instance().inputFontSize)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.setStyleSheet(
            "QPlainTextEdit { background: #f8f8f8; border: none; padding: 4px; }"
        )
        self._highlighter = _PythonHighlighter(self.document())
        self._popup = _CompletionPopup(self)
        self._completion_provider = None
        self._completion_seq = 0
        self._inspect_popup = _InspectPopup(self)
        self._inspection_provider = None
        self._last_inspect_detail = -1

    def setCompletionProvider(self, fn) -> None:
        """fn(code, cursor_pos, callback) — provided by NotebookController."""
        self._completion_provider = fn

    def setInspectionProvider(self, fn) -> None:
        """fn(code, cursor_pos, callback) — provided by NotebookController."""
        self._inspection_provider = fn

    def focusOutEvent(self, event):
        self._popup.hide()
        self._inspect_popup.hide()
        super().focusOutEvent(event)

    def event(self, event) -> bool:
        # Qt's QWidget::event() intercepts Key_Backtab for focus traversal
        # before keyPressEvent is called.  Grab it here so our handler fires.
        from PySide6.QtCore import QEvent
        if (event.type() == QEvent.Type.KeyPress and
                event.key() == Qt.Key.Key_Backtab):
            self.keyPressEvent(event)
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Backtab:
            if not self._inspect_popup.isVisible():
                self._triggerInspection(detail_level=0)
            elif self._last_inspect_detail == 0:
                self._triggerInspection(detail_level=1)
            else:
                self._inspect_popup.hide()
                self._last_inspect_detail = -1
            return

        if self._inspect_popup.isVisible() and key not in (
                Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt,
                Qt.Key.Key_Meta):
            self._inspect_popup.hide()
            self._last_inspect_detail = -1

        if self._popup.isVisible():
            if key == Qt.Key.Key_Up:
                self._popup.moveSelection(-1)
                return
            if key == Qt.Key.Key_Down:
                self._popup.moveSelection(1)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                match, start, end = self._popup.acceptCurrent()
                self._popup.hide()
                if match is not None:
                    self._applyCompletion(match, start, end)
                return
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                return
            super().keyPressEvent(event)
            self._triggerCompletion(retrigger=True)
            return

        if key == Qt.Key.Key_Space and mods & Qt.KeyboardModifier.ControlModifier:
            self._triggerCompletion(retrigger=False)
            return

        if key == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            col = cursor.positionInBlock()
            line_text = cursor.block().text()
            if (self._completion_provider and col > 0 and
                    (line_text[col - 1].isalnum() or line_text[col - 1] in ('_', '.'))):
                self._triggerCompletion(retrigger=False)
                return
            self.textCursor().insertText("    ")
            return

        super().keyPressEvent(event)

    def _triggerCompletion(self, *, retrigger: bool) -> None:
        if not self._completion_provider:
            return
        self._completion_seq += 1
        seq = self._completion_seq
        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        self._completion_provider(
            code, cursor_pos,
            lambda matches, cs, ce: self._onCompletions(matches, cs, ce, seq),
        )

    def _onCompletions(self, matches: list, cursor_start: int, cursor_end: int, seq: int) -> None:
        if seq != self._completion_seq:
            return
        if not matches:
            self._popup.hide()
            return
        cursor_rect = self.cursorRect()
        global_pos = self.mapToGlobal(cursor_rect.bottomLeft())
        self._popup.populate(matches, cursor_start, cursor_end, global_pos)

    def _triggerInspection(self, detail_level: int = 0) -> None:
        if not self._inspection_provider:
            return
        self._last_inspect_detail = detail_level
        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        self._inspection_provider(
            code, cursor_pos,
            lambda data: self._onInspection(data, detail_level),
            detail_level,
        )

    def _onInspection(self, mime_data: dict, detail_level: int) -> None:
        if detail_level != self._last_inspect_detail:
            return
        cursor_rect = self.cursorRect()
        global_pos = self.mapToGlobal(cursor_rect.topLeft())
        line_h = self.fontMetrics().lineSpacing()
        self._inspect_popup.showContent(mime_data, global_pos, line_h)

    def _applyCompletion(self, match: str, cursor_start: int, cursor_end: int) -> None:
        from PySide6.QtGui import QTextCursor
        cursor = self.textCursor()
        cursor.setPosition(cursor_start)
        cursor.setPosition(cursor_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(match)
        self.setTextCursor(cursor)


# #########################################################################################################################################
# Markdown editor

class _MarkdownEditor(_AutoHeightEditor):
    def __init__(self, parent=None):
        super().__init__(parent)
        from jupyterqt.settings import Settings
        font = QFont("sans-serif", Settings.instance().inputFontSize)
        self.setFont(font)
        self.setStyleSheet(
            "QPlainTextEdit { background: #fffde7; border: none; padding: 4px; }"
        )

    def _updateHeight(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.width() if self.width() > 0 else 600)
        height = int(doc.size().height()) + 8
        scrollbar_h = self.horizontalScrollBar().height() if self.horizontalScrollBar().isVisible() else 0
        self.setFixedHeight(max(height + scrollbar_h, 30))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._updateHeight()


# #########################################################################################################################################
# Markdown rendered view

class _MarkdownView(QTextBrowser):
    """Read-only rendered markdown. Emits clicked on mouse press to trigger edit mode."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameStyle(0)
        self.setOpenExternalLinks(True)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; padding: 0; }")
        from jupyterqt.settings import Settings
        Settings.instance().output_font_size_changed.connect(self._adjustHeight)

    def _adjustHeight(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.width() if self.width() > 0 else 600)
        height = int(doc.size().height()) + 8
        self.setFixedHeight(max(height, 20))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjustHeight()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


# #########################################################################################################################################
# Visual mode style constants

_STYLE_NORMAL = (
    "QFrame { border: 1px solid #e0e0e0; border-radius: 4px; background: white; }"
)
_STYLE_SELECTED = (
    "QFrame { border-top: 1px solid #b0c4de; border-right: 1px solid #b0c4de; "
    "border-bottom: 1px solid #b0c4de; border-left: 4px solid #1976d2; "
    "border-radius: 2px; background: white; }"
)
_STYLE_EDIT = (
    "QFrame { border-top: 1px solid #b0c4de; border-right: 1px solid #b0c4de; "
    "border-bottom: 1px solid #b0c4de; border-left: 4px solid #4caf50; "
    "border-radius: 2px; background: white; }"
)
_STYLE_EXECUTING = (
    "QFrame { border-top: 1px solid #b0c4de; border-right: 1px solid #b0c4de; "
    "border-bottom: 1px solid #b0c4de; border-left: 4px solid #ff9800; "
    "border-radius: 2px; background: white; }"
)


# #########################################################################################################################################
# CellWidget

class CellWidget(QWidget):
    source_changed = Signal(str, str)           # cellId, source
    execute_requested = Signal(str)             # cellId
    delete_requested = Signal(str)              # cellId
    add_above_requested = Signal(str)           # cellId
    add_below_requested = Signal(str)           # cellId
    move_up_requested = Signal(str)             # cellId
    move_down_requested = Signal(str)           # cellId
    edit_mode_requested = Signal(str)           # cellId — editor got focus
    escape_pressed = Signal(str)                # cellId — Esc in editor
    fold_toggle_requested = Signal(str)         # cellId — heading fold button clicked

    def __init__(self, cell_model: CellModel, parent=None):
        super().__init__(parent)
        self._cell_model = cell_model
        self._is_executing = False
        self._visual_mode = "normal"   # "normal" | "selected" | "edit"
        self._is_rendered = False
        self._setupUi()
        self._connectSignals()

    @property
    def cellId(self) -> str:
        return self._cell_model.cellId

    # #########################################################################################################################################
    # UI setup

    def _setupUi(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(0)

        self._frame = QFrame(self)
        self._frame.setFrameStyle(QFrame.Shape.NoFrame)
        self._frame.setStyleSheet(_STYLE_NORMAL)
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(4, 4, 4, 4)
        top_row.setSpacing(6)

        is_markdown = self._cell_model.cell_type == CellType.MARKDOWN

        if is_markdown:
            self._prompt_label = None
            self._fold_btn = QToolButton(self)
            self._fold_btn.setFixedSize(20, 20)
            self._fold_btn.setText("▼")
            self._fold_btn.setVisible(False)
            self._fold_btn.setStyleSheet(
                "QToolButton { border: none; color: #888; font-size: 9pt; background: transparent; }"
                "QToolButton:hover { color: #333; }"
            )
            self._fold_btn.clicked.connect(lambda: self.fold_toggle_requested.emit(self.cellId))
            top_row.addWidget(self._fold_btn)

            self._editor = _MarkdownEditor(self)
            self._rendered_view = _MarkdownView(self)
            self._rendered_view.setVisible(False)
            self._rendered_view.clicked.connect(lambda: self.edit_mode_requested.emit(self.cellId))
            top_row.addWidget(self._editor, 1)
            top_row.addWidget(self._rendered_view, 1)
        else:
            self._fold_btn = None
            self._rendered_view = None
            self._prompt_label = QLabel("[ ]:", self)
            self._prompt_label.setFixedWidth(60)
            self._prompt_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            self._prompt_label.setStyleSheet("color: #888; font-family: monospace; font-size: 10pt;")
            self._editor = _CodeEditor(self)
            top_row.addWidget(self._prompt_label)
            top_row.addWidget(self._editor, 1)

        self._editor.setPlainText(self._cell_model.source)
        self._editor._updateHeight()
        frame_layout.addLayout(top_row)

        if is_markdown:
            self._output_area = None
            if self._cell_model.source.strip():
                self._renderMarkdown()
            self._updateFoldButton()
        else:
            self._output_area = OutputArea(self)
            self._output_area.setVisible(False)
            frame_layout.addWidget(self._output_area)
            for o in self._cell_model.outputs:
                self._output_area.appendOutput(o)
            if self._cell_model.outputs:
                self._output_area.setVisible(True)
            self.setExecutionCount(self._cell_model.execution_count)

        outer.addWidget(self._frame)

    def _connectSignals(self):
        if self._cell_model.cell_type == CellType.MARKDOWN:
            self._editor.shift_enter_pressed.connect(self._onMarkdownShiftEnter)
            self._editor.textChanged.connect(self._updateFoldButton)
        else:
            self._editor.shift_enter_pressed.connect(
                lambda: self.execute_requested.emit(self.cellId)
            )
        self._editor.textChanged.connect(
            lambda: self.source_changed.emit(self.cellId, self._editor.toPlainText())
        )
        self._editor.escape_pressed.connect(
            lambda: self.escape_pressed.emit(self.cellId)
        )
        self._editor.focused.connect(
            lambda: self.edit_mode_requested.emit(self.cellId)
        )

    # #########################################################################################################################################
    # Markdown rendering

    def _onMarkdownShiftEnter(self) -> None:
        if self._editor.toPlainText().strip():
            self._renderMarkdown()
        self.execute_requested.emit(self.cellId)

    def _renderMarkdown(self) -> None:
        import markdown as md_lib
        source = self._editor.toPlainText()
        html = md_lib.markdown(source, extensions=['tables', 'fenced_code'])
        self._rendered_view.setHtml(_MD_CSS + html)
        self._editor.setVisible(False)
        self._rendered_view.setVisible(True)
        self._rendered_view._adjustHeight()
        self._is_rendered = True
        self._updateFoldButton()

    def _updateFoldButton(self) -> None:
        if self._fold_btn is None:
            return
        level = _headingLevel(self._editor.toPlainText())
        self._fold_btn.setVisible(level > 0)

    def setFolded(self, folded: bool) -> None:
        if self._fold_btn:
            self._fold_btn.setText("▶" if folded else "▼")

    # #########################################################################################################################################
    # Public API

    def setExecutionCount(self, count: int | None) -> None:
        if self._prompt_label is None or self._is_executing:
            return
        self._prompt_label.setText(f"[{count}]:" if count is not None else "[ ]:")

    def setExecuting(self, executing: bool) -> None:
        self._is_executing = executing
        if executing:
            if self._prompt_label:
                self._prompt_label.setText("[*]:")
            self._frame.setStyleSheet(_STYLE_EXECUTING)
        else:
            self._applyVisualMode()
            self.setExecutionCount(self._cell_model.execution_count)

    def setVisualMode(self, mode: str) -> None:
        """mode: 'normal' | 'selected' | 'edit'"""
        self._visual_mode = mode
        if not self._is_executing:
            self._applyVisualMode()

    def _applyVisualMode(self) -> None:
        if self._rendered_view is not None:
            if self._visual_mode == "edit":
                self._rendered_view.setVisible(False)
                self._editor.setVisible(True)
            elif self._is_rendered:
                self._editor.setVisible(False)
                self._rendered_view.setVisible(True)

        if self._visual_mode == "selected":
            self._frame.setStyleSheet(_STYLE_SELECTED)
        elif self._visual_mode == "edit":
            self._frame.setStyleSheet(_STYLE_EDIT)
        else:
            self._frame.setStyleSheet(_STYLE_NORMAL)

    def focusEditor(self) -> None:
        self._editor.setFocus()
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._editor.setTextCursor(cursor)

    def appendOutput(self, output: OutputItem) -> None:
        if self._output_area is None:
            return
        self._output_area.appendOutput(output)
        self._output_area.setVisible(True)

    def clearOutputs(self) -> None:
        if self._output_area is None:
            return
        self._output_area.clear()
        self._output_area.setVisible(False)

    def setCompletionProvider(self, fn) -> None:
        if isinstance(self._editor, _CodeEditor):
            self._editor.setCompletionProvider(fn)

    def setInspectionProvider(self, fn) -> None:
        if isinstance(self._editor, _CodeEditor):
            self._editor.setInspectionProvider(fn)

    def setSource(self, source: str) -> None:
        self._editor.blockSignals(True)
        self._editor.setPlainText(source)
        self._editor.blockSignals(False)
        if self._cell_model.cell_type == CellType.MARKDOWN and self._is_rendered:
            self._renderMarkdown()
        self._updateFoldButton()
