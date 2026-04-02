import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout

from jupyterqt.commands import CommandRegistry
from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.models.cell_model import CellModel, CellType, OutputItem
from jupyterqt.models.kernel_state import KernelStatus
from jupyterqt.ui.cell_widget import CellWidget


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
        self._cell_widgets: dict[str, CellWidget] = {}   # cell_id → widget

        # Mode state
        self._mode = "command"     # "command" | "edit"
        self._selected_idx = 0
        self._last_key: int | None = None
        self._last_key_time: float = 0.0

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(4)
        self._layout.addStretch()
        self.setWidget(self._content)

        self._build_cells()
        self._connect_controller()

        # Start in command mode with first cell selected
        if self._ordered_widgets():
            self._select(0)
            self.setFocus()

    # ------------------------------------------------------------------ Commands

    def cmd_add_cell(self, above_or_below: str) -> None:
        print('cmd_add_cell', above_or_below)
        widgets = self._ordered_widgets()
        if 0 <= self._selected_idx < len(widgets):
            if above_or_below == 'above':
                self._controller.add_cell_above(widgets[self._selected_idx].cell_id)
                self._select(self._selected_idx)
            elif above_or_below == 'below':
                self._controller.add_cell_below(widgets[self._selected_idx].cell_id)
                self._select(self._selected_idx + 1)
            else:
                raise ValueError(f'{above_or_below=}')

    def _cmd_add_cell_above(self) -> None:
        widgets = self._ordered_widgets()
        if 0 <= self._selected_idx < len(widgets):
            self._controller.add_cell_above(widgets[self._selected_idx].cell_id)
            self._select(self._selected_idx)

    def _cmd_add_cell_below(self) -> None:
        widgets = self._ordered_widgets()
        if 0 <= self._selected_idx < len(widgets):
            self._controller.add_cell_below(widgets[self._selected_idx].cell_id)
            self._select(self._selected_idx + 1)

    # ------------------------------------------------------------------ Build

    @property
    def controller(self) -> NotebookController:
        return self._controller

    def _build_cells(self) -> None:
        if not self._controller.model:
            return
        for cell in self._controller.model.cells:
            self._insert_cell_widget(cell, len(self._cell_widgets))

    def _insert_cell_widget(self, cell: CellModel, index: int) -> CellWidget:
        w = CellWidget(cell, self._content)
        self._cell_widgets[cell.cell_id] = w
        stretch_idx = self._layout.count() - 1
        self._layout.insertWidget(min(index, stretch_idx), w)

        w.set_completion_provider(self._controller.request_completion)
        w.set_inspection_provider(self._controller.request_inspection)
        w.source_changed.connect(self._controller.update_cell_source)
        w.execute_requested.connect(self._on_execute_requested)
        w.delete_requested.connect(self._controller.delete_cell)
        w.add_above_requested.connect(self._controller.add_cell_above)
        w.add_below_requested.connect(self._controller.add_cell_below)
        w.move_up_requested.connect(self._controller.move_cell_up)
        w.move_down_requested.connect(self._controller.move_cell_down)
        w.edit_mode_requested.connect(self._on_edit_mode_requested)
        w.escape_pressed.connect(self._on_escape_pressed)
        return w

    def _connect_controller(self) -> None:
        self._controller.cell_source_changed.connect(self._on_cell_source_changed)
        self._controller.cell_output_appended.connect(self._on_output_appended)
        self._controller.cell_outputs_cleared.connect(self._on_outputs_cleared)
        self._controller.cell_execution_count_updated.connect(self._on_exec_count)
        self._controller.cell_executing_changed.connect(self._on_executing_changed)
        self._controller.cell_added.connect(self._on_cell_added)
        self._controller.cell_removed.connect(self._on_cell_removed)
        self._controller.cell_moved.connect(self._on_cell_moved)

    # ------------------------------------------------------------------ Mode management

    def _ordered_widgets(self) -> list[CellWidget]:
        result = []
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item:
                w = item.widget()
                if isinstance(w, CellWidget):
                    result.append(w)
        return result

    def _select(self, idx: int) -> None:
        widgets = self._ordered_widgets()
        if not widgets:
            self._selected_idx = 0
            return
        idx = max(0, min(idx, len(widgets) - 1))
        self._selected_idx = idx
        for i, w in enumerate(widgets):
            w.set_visual_mode("selected" if i == idx else "normal")
        self.ensureWidgetVisible(widgets[idx])

    def _enter_command_mode(self) -> None:
        self._mode = "command"
        self._select(self._selected_idx)
        self.setFocus()

    def _enter_edit_mode(self, cell_id: str) -> None:
        widgets = self._ordered_widgets()
        for i, w in enumerate(widgets):
            if w.cell_id == cell_id:
                self._selected_idx = i
                w.set_visual_mode("edit")
            else:
                w.set_visual_mode("normal")
        self._mode = "edit"

    # ------------------------------------------------------------------ Slots from cell widgets

    def _on_edit_mode_requested(self, cell_id: str) -> None:
        self._enter_edit_mode(cell_id)

    def _on_escape_pressed(self, cell_id: str) -> None:
        self._enter_command_mode()

    def _on_execute_requested(self, cell_id: str) -> None:
        self._controller.execute_cell(cell_id)
        # After Shift+Enter: return to command mode and advance selection
        widgets = self._ordered_widgets()
        for i, w in enumerate(widgets):
            if w.cell_id == cell_id:
                next_idx = i + 1
                if next_idx < len(widgets):
                    self._enter_command_mode()
                    self._select(next_idx)
                else:
                    # Last cell — stay on it in command mode
                    self._enter_command_mode()
                return

    # ------------------------------------------------------------------ Key handling

    def keyPressEvent(self, event) -> None:
        if self._mode != "command":
            super().keyPressEvent(event)
            return

        key = event.key()
        mods = event.modifiers()
        widgets = self._ordered_widgets()

        # Shift+Enter: run selected cell
        if (key == Qt.Key.Key_Return and
                mods & Qt.KeyboardModifier.ShiftModifier):
            if 0 <= self._selected_idx < len(widgets):
                self._on_execute_requested(widgets[self._selected_idx].cell_id)
            return

        # Enter: enter edit mode
        if key == Qt.Key.Key_Return:
            if 0 <= self._selected_idx < len(widgets):
                w = widgets[self._selected_idx]
                self._enter_edit_mode(w.cell_id)
                w.focus_editor()
            return

        # Navigation
        if key in (Qt.Key.Key_Up, Qt.Key.Key_K):
            self._select(self._selected_idx - 1)
            return
        if key in (Qt.Key.Key_Down, Qt.Key.Key_J):
            self._select(self._selected_idx + 1)
            return

        # Add cell above / below — dispatched through the command registry
        if key == Qt.Key.Key_A:
            CommandRegistry.instance().execute('notebook', 'add-cell-above')
            return

        if key == Qt.Key.Key_B:
            CommandRegistry.instance().execute('notebook', 'add-cell-below')
            return

        # D + D to delete (two D presses within 500 ms)
        if key == Qt.Key.Key_D:
            now = time.monotonic()
            if (self._last_key == Qt.Key.Key_D and
                    now - self._last_key_time < 0.5):
                if 0 <= self._selected_idx < len(widgets):
                    self._controller.delete_cell(
                        widgets[self._selected_idx].cell_id
                    )
                    # selection clamped in _on_cell_removed
                self._last_key = None
            else:
                self._last_key = key
                self._last_key_time = now
            return

        self._last_key = key
        self._last_key_time = time.monotonic()
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ Controller slots

    def _on_cell_source_changed(self, cell_id: str, source: str) -> None:
        """Called when another view edited this cell — update our editor silently."""
        w = self._cell_widgets.get(cell_id)
        if w and w._editor.toPlainText() != source:
            w.set_source(source)

    def _on_output_appended(self, cell_id: str, output: object) -> None:
        w = self._cell_widgets.get(cell_id)
        if w:
            w.append_output(output)

    def _on_outputs_cleared(self, cell_id: str) -> None:
        w = self._cell_widgets.get(cell_id)
        if w:
            w.clear_outputs()

    def _on_exec_count(self, cell_id: str, count: object) -> None:
        w = self._cell_widgets.get(cell_id)
        if w:
            w.set_execution_count(count)

    def _on_executing_changed(self, cell_id: str, executing: bool) -> None:
        w = self._cell_widgets.get(cell_id)
        if w:
            w.set_executing(executing)
            if executing:
                self.ensureWidgetVisible(w)

    def _on_cell_added(self, index: int, cell: object) -> None:
        w = self._insert_cell_widget(cell, index)
        # Select the new cell in command mode
        self._select(index)
        self._enter_command_mode()

    def _on_cell_removed(self, cell_id: str) -> None:
        w = self._cell_widgets.pop(cell_id, None)
        if w:
            self._layout.removeWidget(w)
            w.deleteLater()
        widgets = self._ordered_widgets()
        if widgets:
            self._select(min(self._selected_idx, len(widgets) - 1))

    def _on_cell_moved(self, cell_id: str, new_index: int) -> None:
        w = self._cell_widgets.get(cell_id)
        if not w:
            return
        self._layout.removeWidget(w)
        stretch_idx = self._layout.count() - 1
        self._layout.insertWidget(min(new_index, stretch_idx), w)
        self._select(new_index)

    def get_cell_widget(self, cell_id: str) -> CellWidget | None:
        return self._cell_widgets.get(cell_id)
