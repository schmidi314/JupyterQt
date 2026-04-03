import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout

from jupyterqt.commands import CommandRegistry
from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.models.cell_model import CellModel, CellType, OutputItem
from jupyterqt.models.kernel_state import KernelStatus
from jupyterqt.ui.cell_widget import CellWidget, _headingLevel


class NotebookTab(QScrollArea):
    """
    Manages two interaction modes:

    Command mode  — keyboard navigates between cells (Up/Down/J/K), Enter enters
                    edit mode, A/B add cells, D+D deletes, Shift+Enter runs.
                    Selected cell shown with blue left border.

    Edit mode     — keyboard input goes to the cell's editor.
                    Active cell shown with green left border.
                    Esc returns to command mode.
    """

    def __init__(self, controller: NotebookController, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._cell_widgets: dict[str, CellWidget] = {}   # cellId → widget

        # Mode state
        self._mode = "command"     # "command" | "edit"
        self._selected_idx = 0
        self._last_key: int | None = None
        self._last_key_time: float = 0.0
        self._folded_headings: set[str] = set()

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self.setWidget(self._content)

        self._buildCells()
        self._connectController()

        # Start in command mode with first cell selected
        if self._orderedWidgets():
            self._select(0)
            self.setFocus()

    # #########################################################################################################################################
    # Commands

    def cmdInsertHeadingAbove(self) -> None:
        widgets = self._orderedWidgets()
        if not (0 <= self._selected_idx < len(widgets)):
            return
        current_cellId = widgets[self._selected_idx].cellId
        current_cell = self._controller.model.getCell(current_cellId)
        level = _headingLevel(current_cell.source) if current_cell else 0
        prefix = '#' * (level if level > 0 else 1) + ' '
        cell = self._controller.addCellAbove(current_cellId, CellType.MARKDOWN)
        if cell:
            self._controller.updateCellSource(cell.cellId, prefix)
            self._enterEditMode(cell.cellId)
            w = self._cell_widgets.get(cell.cellId)
            if w:
                w.focusEditor()

    def cmdInsertHeadingBelow(self) -> None:
        widgets = self._orderedWidgets()
        if not (0 <= self._selected_idx < len(widgets)):
            return
        current_cellId = widgets[self._selected_idx].cellId
        current_cell = self._controller.model.getCell(current_cellId)
        level = _headingLevel(current_cell.source) if current_cell else 0
        prefix = '#' * (level if level > 0 else 1) + ' '
        cell = self._controller.addCellBelow(current_cellId, CellType.MARKDOWN)
        if cell:
            self._controller.updateCellSource(cell.cellId, prefix)
            self._enterEditMode(cell.cellId)
            w = self._cell_widgets.get(cell.cellId)
            if w:
                w.focusEditor()

    def cmdChangeCellType(self, cell_type: CellType) -> None:
        widgets = self._orderedWidgets()
        if 0 <= self._selected_idx < len(widgets):
            self._controller.changeCellType(widgets[self._selected_idx].cellId, cell_type)

    def cmdAddCell(self, above_or_below: str) -> None:
        print('cmdAddCell', above_or_below)
        widgets = self._orderedWidgets()
        if 0 <= self._selected_idx < len(widgets):
            if above_or_below == 'above':
                self._controller.addCellAbove(widgets[self._selected_idx].cellId)
                self._select(self._selected_idx)
            elif above_or_below == 'below':
                self._controller.addCellBelow(widgets[self._selected_idx].cellId)
                self._select(self._selected_idx + 1)
            else:
                raise ValueError(f'{above_or_below=}')

    # #########################################################################################################################################
    # Build

    @property
    def controller(self) -> NotebookController:
        return self._controller

    def _buildCells(self) -> None:
        if not self._controller.model:
            return
        for cell in self._controller.model.cells:
            self._insertCellWidget(cell, len(self._cell_widgets))

    def _insertCellWidget(self, cell: CellModel, index: int) -> CellWidget:
        w = CellWidget(cell, self._content)
        self._cell_widgets[cell.cellId] = w
        stretch_idx = self._layout.count() - 1
        self._layout.insertWidget(min(index, stretch_idx), w)

        w.setCompletionProvider(self._controller.requestCompletion)
        w.setInspectionProvider(self._controller.requestInspection)
        w.source_changed.connect(self._controller.updateCellSource)
        w.execute_requested.connect(self._onExecuteRequested)
        w.delete_requested.connect(self._controller.deleteCell)
        w.add_above_requested.connect(self._controller.addCellAbove)
        w.add_below_requested.connect(self._controller.addCellBelow)
        w.move_up_requested.connect(self._controller.moveCellUp)
        w.move_down_requested.connect(self._controller.moveCellDown)
        w.edit_mode_requested.connect(self._onEditModeRequested)
        w.escape_pressed.connect(self._onEscapePressed)
        w.fold_toggle_requested.connect(self._onFoldToggle)
        return w

    def _connectController(self) -> None:
        self._controller.cell_source_changed.connect(self._onCellSourceChanged)
        self._controller.cell_output_appended.connect(self._onOutputAppended)
        self._controller.cell_outputs_cleared.connect(self._onOutputsCleared)
        self._controller.cell_execution_count_updated.connect(self._onExecCount)
        self._controller.cell_executing_changed.connect(self._onExecutingChanged)
        self._controller.cell_added.connect(self._onCellAdded)
        self._controller.cell_removed.connect(self._onCellRemoved)
        self._controller.cell_moved.connect(self._onCellMoved)
        self._controller.cell_type_changed.connect(self._onCellTypeChanged)

    # #########################################################################################################################################
    # Mode management

    def _orderedWidgets(self) -> list[CellWidget]:
        result = []
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item:
                w = item.widget()
                if isinstance(w, CellWidget):
                    result.append(w)
        return result

    def _select(self, idx: int) -> None:
        widgets = self._orderedWidgets()
        if not widgets:
            self._selected_idx = 0
            return
        idx = max(0, min(idx, len(widgets) - 1))
        # Skip hidden (folded) cells — find nearest visible
        if not widgets[idx].isVisible():
            fwd = next((i for i in range(idx, len(widgets)) if widgets[i].isVisible()), None)
            bwd = next((i for i in range(idx - 1, -1, -1) if widgets[i].isVisible()), None)
            if fwd is not None:
                idx = fwd
            elif bwd is not None:
                idx = bwd
            else:
                return
        self._selected_idx = idx
        for i, w in enumerate(widgets):
            w.setVisualMode("selected" if i == idx else "normal")
        self.ensureWidgetVisible(widgets[idx])

    def _enterCommandMode(self) -> None:
        self._mode = "command"
        self._select(self._selected_idx)
        self.setFocus()

    def _enterEditMode(self, cellId: str) -> None:
        widgets = self._orderedWidgets()
        for i, w in enumerate(widgets):
            if w.cellId == cellId:
                self._selected_idx = i
                w.setVisualMode("edit")
            else:
                w.setVisualMode("normal")
        self._mode = "edit"

    # #########################################################################################################################################
    # Slots from cell widgets

    def _onEditModeRequested(self, cellId: str) -> None:
        self._enterEditMode(cellId)

    def _onEscapePressed(self, cellId: str) -> None:
        self._enterCommandMode()

    def _onExecuteRequested(self, cellId: str) -> None:
        self._controller.executeCell(cellId)
        # After Shift+Enter: return to command mode and advance selection
        widgets = self._orderedWidgets()
        for i, w in enumerate(widgets):
            if w.cellId == cellId:
                next_idx = i + 1
                if next_idx < len(widgets):
                    self._enterCommandMode()
                    self._select(next_idx)
                else:
                    # Last cell — stay on it in command mode
                    self._enterCommandMode()
                return

    # #########################################################################################################################################
    # Key handling

    def keyPressEvent(self, event) -> None:
        reg = CommandRegistry.instance()
        if reg.tryToExecuteKeyboardShortcut(event, mod_filter=('at least one of', ('ctrl', 'alt', 'meta'))):
            return

        if self._mode == "edit":
            super().keyPressEvent(event)
            return

        if reg.tryToExecuteKeyboardShortcut(event):
            return

        key = event.key()
        mods = event.modifiers()
        widgets = self._orderedWidgets()

        # Shift+Enter: run selected cell
        if key == Qt.Key.Key_Return and mods & Qt.KeyboardModifier.ShiftModifier:
            if 0 <= self._selected_idx < len(widgets):
                self._onExecuteRequested(widgets[self._selected_idx].cellId)
            return

        # Enter: enter edit mode
        if key == Qt.Key.Key_Return:
            if 0 <= self._selected_idx < len(widgets):
                w = widgets[self._selected_idx]
                self._enterEditMode(w.cellId)
                w.focusEditor()
            return

        # Navigation
        if key in (Qt.Key.Key_Up, Qt.Key.Key_K):
            self._select(self._selected_idx - 1)
            return
        if key in (Qt.Key.Key_Down, Qt.Key.Key_J):
            self._select(self._selected_idx + 1)
            return

        # D + D to delete (two D presses within 500 ms)
        if key == Qt.Key.Key_D:
            now = time.monotonic()
            if (self._last_key == Qt.Key.Key_D and
                    now - self._last_key_time < 0.5):
                if 0 <= self._selected_idx < len(widgets):
                    self._controller.deleteCell(
                        widgets[self._selected_idx].cellId
                    )
                    # selection clamped in _onCellRemoved
                self._last_key = None
            else:
                self._last_key = key
                self._last_key_time = now
            return

        self._last_key = key
        self._last_key_time = time.monotonic()
        super().keyPressEvent(event)

    # #########################################################################################################################################
    # Controller slots

    def _onCellSourceChanged(self, cellId: str, source: str) -> None:
        """Called when another view edited this cell — update our editor silently."""
        w = self._cell_widgets.get(cellId)
        if w and w._editor.toPlainText() != source:
            w.setSource(source)

    def _onOutputAppended(self, cellId: str, output: object) -> None:
        w = self._cell_widgets.get(cellId)
        if w:
            w.appendOutput(output)

    def _onOutputsCleared(self, cellId: str) -> None:
        w = self._cell_widgets.get(cellId)
        if w:
            w.clearOutputs()

    def _onExecCount(self, cellId: str, count: object) -> None:
        w = self._cell_widgets.get(cellId)
        if w:
            w.setExecutionCount(count)

    def _onExecutingChanged(self, cellId: str, executing: bool) -> None:
        w = self._cell_widgets.get(cellId)
        if w:
            w.setExecuting(executing)
            if executing:
                self.ensureWidgetVisible(w)

    def _onCellAdded(self, index: int, cell: object) -> None:
        w = self._insertCellWidget(cell, index)
        # Select the new cell in command mode
        self._select(index)
        self._enterCommandMode()

    # #########################################################################################################################################
    # Heading fold

    def _foldRange(self, cellId: str) -> list:
        """Returns the widgets that fall under heading cellId (until next equal/higher heading)."""
        widgets = self._orderedWidgets()
        heading_idx = next((i for i, w in enumerate(widgets) if w.cellId == cellId), None)
        if heading_idx is None:
            return []
        cell = self._controller.model.getCell(cellId)
        if cell is None:
            return []
        heading_level = _headingLevel(cell.source)
        if heading_level == 0:
            return []
        result = []
        for w in widgets[heading_idx + 1:]:
            other_cell = self._controller.model.getCell(w.cellId)
            if other_cell:
                other_level = _headingLevel(other_cell.source)
                if other_level > 0 and other_level <= heading_level:
                    break
            result.append(w)
        return result

    def _onFoldToggle(self, cellId: str) -> None:
        fold_range = self._foldRange(cellId)
        if not fold_range:
            return
        is_folded = cellId in self._folded_headings
        for w in fold_range:
            w.setVisible(is_folded)    # unfold if currently folded, fold if not
        heading_w = self._cell_widgets.get(cellId)
        if is_folded:
            self._folded_headings.discard(cellId)
            if heading_w:
                heading_w.setFolded(False)
        else:
            self._folded_headings.add(cellId)
            if heading_w:
                heading_w.setFolded(True)

    def _onCellRemoved(self, cellId: str) -> None:
        # Unfold range before removing a heading that was folded
        if cellId in self._folded_headings:
            for w in self._foldRange(cellId):
                w.setVisible(True)
            self._folded_headings.discard(cellId)
        w = self._cell_widgets.pop(cellId, None)
        if w:
            self._layout.removeWidget(w)
            w.deleteLater()
        widgets = self._orderedWidgets()
        if widgets:
            self._select(min(self._selected_idx, len(widgets) - 1))

    def _onCellMoved(self, cellId: str, new_index: int) -> None:
        w = self._cell_widgets.get(cellId)
        if not w:
            return
        self._layout.removeWidget(w)
        stretch_idx = self._layout.count() - 1
        self._layout.insertWidget(min(new_index, stretch_idx), w)
        self._select(new_index)

    def _onCellTypeChanged(self, cellId: str, new_type) -> None:
        if cellId in self._folded_headings:
            for w in self._foldRange(cellId):
                w.setVisible(True)
            self._folded_headings.discard(cellId)
        old_w = self._cell_widgets.pop(cellId, None)
        if old_w is None:
            return
        idx = self._layout.indexOf(old_w)
        self._layout.removeWidget(old_w)
        old_w.deleteLater()
        cell = self._controller.model.getCell(cellId)
        if cell:
            self._insertCellWidget(cell, idx)
            self._select(self._selected_idx)

    def getCellWidget(self, cellId: str) -> CellWidget | None:
        return self._cell_widgets.get(cellId)
