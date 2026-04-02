from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import (QFont, QColor, QTextOption, QSyntaxHighlighter,
                            QTextCharFormat)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                                QLabel, QFrame, QSizePolicy, QListWidget,
                                QListWidgetItem, QTextBrowser, QApplication)

from jupyterqt.models.cell_model import CellModel, CellType, OutputItem
from jupyterqt.ui.output_area import OutputArea


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
        import re
        self._rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#0000aa"))
        kw_fmt.setFontWeight(700)
        self._rules.append((re.compile(r'\b(' + '|'.join(self._KEYWORDS) + r')\b'), kw_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#008000"))
        self._rules.append((re.compile(r'\".*?\"|\'.*?\''), str_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#808080"))
        comment_fmt.setFontItalic(True)
        self._rules.append((re.compile(r'#[^\n]*'), comment_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#aa5500"))
        self._rules.append((re.compile(r'\b\d+(\.\d+)?\b'), num_fmt))

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#6600aa"))
        self._rules.append((re.compile(r'\b\w+(?=\()'), func_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


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
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)
        self.setStyleSheet(
            "QFrame { background: white; border: 1px solid #aaaacc; }"
            "QListWidget { background: white; border: none; }"
            "QListWidget::item { padding: 1px 4px; }"
            "QListWidget::item:selected { background: #0066cc; color: white; }"
        )
        self.hide()

    def populate(self, matches: list, cursor_start: int, cursor_end: int,
                 global_pos) -> None:
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

    def move_selection(self, delta: int) -> None:
        row = max(0, min(self._list.currentRow() + delta, self._list.count() - 1))
        self._list.setCurrentRow(row)

    def accept_current(self) -> tuple[str | None, int, int]:
        item = self._list.currentItem()
        if item:
            return item.text(), self._cursor_start, self._cursor_end
        return None, 0, 0

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self.hide()
        self._editor._apply_completion(item.text(), self._cursor_start, self._cursor_end)
        self._editor.setFocus()


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

    def show_content(self, mime_data: dict, cursor_global_pos, line_height: int) -> None:
        from jupyterqt.settings import Settings
        size = Settings.instance().output_font_size



        if "text/html" in mime_data:
            # Kernel provided HTML — use it directly, inject font size
            html = mime_data["text/html"]
            self._browser.setHtml(
                f'<div style="font-family:monospace; font-size:{size}pt">{html}</div>'
            )
        else:
            from jupyterqt.ui.renderers.error_renderer import _ansi_to_html
            text = mime_data.get("text/plain", "")
            html = _ansi_to_html(text).replace("\n", "<br>")
            self._browser.setHtml(
                f'<span style="font-family:monospace; font-size:{size}pt">{html}</span>'
            )

        self.resize(self._MAX_W, self._MAX_H)

        # Prefer showing above the cursor; fall back to below
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(cursor_global_pos.x(),
                                   screen.right() - self._MAX_W))
        y_above = cursor_global_pos.y() - self._MAX_H - 4
        y_below = cursor_global_pos.y() + line_height + 4
        y = y_above if y_above >= screen.top() else y_below
        self.move(x, y)
        self.show()
        self.raise_()


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
        self.document().contentsChanged.connect(self._update_height)
        self.horizontalScrollBar().valueChanged.connect(self._update_height)
        self.horizontalScrollBar().setStyleSheet(
            "QScrollBar:horizontal { height: 8px; }"
        )
        from jupyterqt.settings import Settings
        Settings.instance().input_font_size_changed.connect(self._on_font_size_changed)

    def _on_font_size_changed(self, size: int) -> None:
        f = self.font()
        f.setPointSize(size)
        self.setFont(f)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self._update_height()

    def _update_height(self):
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


class _CodeEditor(_AutoHeightEditor):
    def __init__(self, parent=None):
        super().__init__(parent)
        from jupyterqt.settings import Settings
        font = QFont("Monospace", Settings.instance().input_font_size)
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
        self._completion_provider = None   # set via set_completion_provider()
        self._completion_seq = 0           # guards against stale async replies
        self._inspect_popup = _InspectPopup(self)
        self._inspection_provider = None   # set via set_inspection_provider()
        self._last_inspect_detail = -1     # tracks detail_level of current popup

    def set_completion_provider(self, fn) -> None:
        """fn(code, cursor_pos, callback) — provided by NotebookController."""
        self._completion_provider = fn

    def set_inspection_provider(self, fn) -> None:
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

        # Shift+Tab: first press → detail_level 0 (signature),
        #            second press while popup open → detail_level 1 (full docstring),
        #            third press → dismiss
        if key == Qt.Key.Key_Backtab:
            if not self._inspect_popup.isVisible():
                self._trigger_inspection(detail_level=0)
            elif self._last_inspect_detail == 0:
                self._trigger_inspection(detail_level=1)
            else:
                self._inspect_popup.hide()
                self._last_inspect_detail = -1
            return

        # Any key dismisses the inspect popup (except bare modifiers)
        if self._inspect_popup.isVisible() and key not in (
                Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt,
                Qt.Key.Key_Meta):
            self._inspect_popup.hide()
            self._last_inspect_detail = -1

        if self._popup.isVisible():
            if key == Qt.Key.Key_Up:
                self._popup.move_selection(-1)
                return
            if key == Qt.Key.Key_Down:
                self._popup.move_selection(1)
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                match, start, end = self._popup.accept_current()
                self._popup.hide()
                if match is not None:
                    self._apply_completion(match, start, end)
                return
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                return
            # Any other key: pass through, then re-trigger
            super().keyPressEvent(event)
            self._trigger_completion(retrigger=True)
            return

        # Ctrl+Space always triggers completion
        if key == Qt.Key.Key_Space and mods & Qt.KeyboardModifier.ControlModifier:
            self._trigger_completion(retrigger=False)
            return

        if key == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            col = cursor.positionInBlock()
            line_text = cursor.block().text()
            if (self._completion_provider and col > 0 and
                    (line_text[col - 1].isalnum() or line_text[col - 1] in ('_', '.'))):
                self._trigger_completion(retrigger=False)
                # Popup will appear asynchronously; don't insert spaces yet.
                # If no provider or no completions arrive, fall through on next Tab.
                return
            self.textCursor().insertText("    ")
            return

        super().keyPressEvent(event)

    def _trigger_completion(self, *, retrigger: bool) -> None:
        if not self._completion_provider:
            return
        self._completion_seq += 1
        seq = self._completion_seq
        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        self._completion_provider(
            code, cursor_pos,
            lambda matches, cs, ce: self._on_completions(matches, cs, ce, seq),
        )

    def _on_completions(self, matches: list, cursor_start: int,
                        cursor_end: int, seq: int) -> None:
        if seq != self._completion_seq:
            return   # stale reply
        if not matches:
            self._popup.hide()
            return
        cursor_rect = self.cursorRect()
        global_pos = self.mapToGlobal(cursor_rect.bottomLeft())
        self._popup.populate(matches, cursor_start, cursor_end, global_pos)

    def _trigger_inspection(self, detail_level: int = 0) -> None:
        if not self._inspection_provider:
            return
        self._last_inspect_detail = detail_level
        code = self.toPlainText()
        cursor_pos = self.textCursor().position()
        self._inspection_provider(
            code, cursor_pos,
            lambda data: self._on_inspection(data, detail_level),
            detail_level,
        )

    def _on_inspection(self, mime_data: dict, detail_level: int) -> None:
        if detail_level != self._last_inspect_detail:
            return   # stale reply
        cursor_rect = self.cursorRect()
        global_pos = self.mapToGlobal(cursor_rect.topLeft())
        line_h = self.fontMetrics().lineSpacing()
        self._inspect_popup.show_content(mime_data, global_pos, line_h)

    def _apply_completion(self, match: str, cursor_start: int,
                          cursor_end: int) -> None:
        from PySide6.QtGui import QTextCursor
        cursor = self.textCursor()
        cursor.setPosition(cursor_start)
        cursor.setPosition(cursor_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(match)
        self.setTextCursor(cursor)


class _MarkdownEditor(_AutoHeightEditor):
    def __init__(self, parent=None):
        super().__init__(parent)
        from jupyterqt.settings import Settings
        font = QFont("Monospace", Settings.instance().input_font_size)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self.setStyleSheet(
            "QPlainTextEdit { background: #fffde7; border: none; padding: 4px; }"
        )


# Visual mode constants
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


class CellWidget(QWidget):
    source_changed = Signal(str, str)       # cell_id, source
    execute_requested = Signal(str)         # cell_id
    delete_requested = Signal(str)          # cell_id
    add_above_requested = Signal(str)       # cell_id
    add_below_requested = Signal(str)       # cell_id
    move_up_requested = Signal(str)         # cell_id
    move_down_requested = Signal(str)       # cell_id
    # Mode signals (for NotebookTab)
    edit_mode_requested = Signal(str)       # cell_id — editor got focus
    escape_pressed = Signal(str)            # cell_id — Esc in editor

    def __init__(self, cell_model: CellModel, parent=None):
        super().__init__(parent)
        self._cell_model = cell_model
        self._is_executing = False
        self._visual_mode = "normal"   # "normal" | "selected" | "edit"
        self._setup_ui()
        self._connect_signals()

    @property
    def cell_id(self) -> str:
        return self._cell_model.cell_id

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(0)

        self._frame = QFrame(self)
        self._frame.setFrameStyle(QFrame.Shape.NoFrame)
        self._frame.setStyleSheet(_STYLE_NORMAL)
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Top row: prompt + editor + run button + menu
        top_row = QHBoxLayout()
        top_row.setContentsMargins(4, 4, 4, 4)
        top_row.setSpacing(6)

        self._prompt_label = QLabel("[ ]:", self)
        self._prompt_label.setFixedWidth(60)
        self._prompt_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        self._prompt_label.setStyleSheet(
            "color: #888; font-family: monospace; font-size: 10pt;"
        )

        if self._cell_model.cell_type == CellType.CODE:
            self._editor = _CodeEditor(self)
        else:
            self._editor = _MarkdownEditor(self)
            self._prompt_label.setText("Md:")

        self._editor.setPlainText(self._cell_model.source)
        self._editor._update_height()
        top_row.addWidget(self._prompt_label)
        top_row.addWidget(self._editor, 1)
        frame_layout.addLayout(top_row)

        self._output_area = OutputArea(self)
        self._output_area.setVisible(False)
        frame_layout.addWidget(self._output_area)

        outer.addWidget(self._frame)

        for o in self._cell_model.outputs:
            self._output_area.append_output(o)
        if self._cell_model.outputs:
            self._output_area.setVisible(True)

        self.set_execution_count(self._cell_model.execution_count)

    def _connect_signals(self):
        self._editor.shift_enter_pressed.connect(
            lambda: self.execute_requested.emit(self.cell_id)
        )
        self._editor.textChanged.connect(
            lambda: self.source_changed.emit(self.cell_id, self._editor.toPlainText())
        )
        self._editor.escape_pressed.connect(
            lambda: self.escape_pressed.emit(self.cell_id)
        )
        self._editor.focused.connect(
            lambda: self.edit_mode_requested.emit(self.cell_id)
        )


    # ------------------------------------------------------------------ Public API

    def set_execution_count(self, count: int | None) -> None:
        if self._is_executing:
            return
        if count is not None:
            self._prompt_label.setText(f"[{count}]:")
        else:
            self._prompt_label.setText("[ ]:")

    def set_executing(self, executing: bool) -> None:
        self._is_executing = executing
        if executing:
            self._prompt_label.setText("[*]:")
            self._frame.setStyleSheet(_STYLE_EXECUTING)
        else:
            self._apply_visual_mode()
            # Execution count was updated in the model before this signal fired;
            # read it directly so we don't depend on signal ordering.
            self.set_execution_count(self._cell_model.execution_count)

    def set_visual_mode(self, mode: str) -> None:
        """mode: 'normal' | 'selected' | 'edit'"""
        self._visual_mode = mode
        if not self._is_executing:
            self._apply_visual_mode()

    def _apply_visual_mode(self) -> None:
        if self._visual_mode == "selected":
            self._frame.setStyleSheet(_STYLE_SELECTED)
        elif self._visual_mode == "edit":
            self._frame.setStyleSheet(_STYLE_EDIT)
        else:
            self._frame.setStyleSheet(_STYLE_NORMAL)

    def focus_editor(self) -> None:
        self._editor.setFocus()
        # Move cursor to end so user can type immediately
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._editor.setTextCursor(cursor)

    def append_output(self, output: OutputItem) -> None:
        self._output_area.append_output(output)
        self._output_area.setVisible(True)

    def clear_outputs(self) -> None:
        self._output_area.clear()
        self._output_area.setVisible(False)

    def set_completion_provider(self, fn) -> None:
        if isinstance(self._editor, _CodeEditor):
            self._editor.set_completion_provider(fn)

    def set_inspection_provider(self, fn) -> None:
        if isinstance(self._editor, _CodeEditor):
            self._editor.set_inspection_provider(fn)

    def set_source(self, source: str) -> None:
        self._editor.blockSignals(True)
        self._editor.setPlainText(source)
        self._editor.blockSignals(False)
