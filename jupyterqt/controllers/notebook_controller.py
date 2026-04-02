from collections import deque

from PySide6.QtCore import QObject, Signal, QThreadPool

from jupyterqt.config import ServerConfig
from jupyterqt.jupyter.kernel_client import KernelClient
from jupyterqt.models.cell_model import CellModel, CellType, OutputItem
from jupyterqt.models.kernel_state import KernelStatus
from jupyterqt.models.notebook_model import NotebookModel
from jupyterqt.network.rest_client import RestClient
from jupyterqt.network.rest_workers import RestWorker


class NotebookController(QObject):
    # Signals to UI
    cell_source_changed = Signal(str, str)           # cell_id, source (broadcast to other views)
    cell_output_appended = Signal(str, object)      # cell_id, OutputItem
    cell_outputs_cleared = Signal(str)               # cell_id
    cell_execution_count_updated = Signal(str, object)  # cell_id, int|None
    cell_executing_changed = Signal(str, bool)       # cell_id, is_executing
    kernel_status_changed = Signal(object)           # KernelStatus
    notebook_loaded = Signal()
    notebook_load_failed = Signal(str)
    notebook_saved = Signal()
    notebook_save_failed = Signal(str)
    kernel_started = Signal(str)                     # kernel_id
    kernel_start_failed = Signal(str)
    cell_added = Signal(int, object)                 # index, CellModel
    cell_removed = Signal(str)                       # cell_id
    cell_moved = Signal(str, int)                    # cell_id, new_index

    def __init__(self, path: str, config: ServerConfig, parent=None):
        super().__init__(parent)
        self.path = path
        self._config = config
        self._rest = RestClient(config)
        self._model: NotebookModel | None = None
        self._kernel: KernelClient | None = None
        self._execution_queue: deque[str] = deque()
        self._executing_cell_id: str | None = None
        self._completion_callbacks: dict[str, object] = {}
        self._inspection_callbacks: dict[str, object] = {}
        self._pool = QThreadPool.globalInstance()

    @property
    def model(self) -> NotebookModel | None:
        return self._model

    @property
    def notebook_id(self) -> str | None:
        return self._model.notebook_id if self._model else None

    @property
    def kernel_status(self) -> KernelStatus:
        if self._kernel:
            return self._kernel.status
        return KernelStatus.DISCONNECTED

    # ---------- Loading ----------

    def load(self) -> None:
        w = RestWorker(self._rest.get_notebook, self.path)
        w.signals.finished.connect(self._on_notebook_loaded)
        w.signals.error.connect(self._on_notebook_load_error)
        self._pool.start(w)

    def _on_notebook_loaded(self, data: object) -> None:
        content = data["content"] if isinstance(data, dict) and "content" in data else data
        self._model = NotebookModel.from_ipynb_dict(self.path, content)
        self.notebook_loaded.emit()
        self._start_kernel()

    def _on_notebook_load_error(self, msg: str) -> None:
        self.notebook_load_failed.emit(msg)

    # ---------- Kernel lifecycle ----------

    def _start_kernel(self) -> None:
        kernel_name = self._model.kernel_name if self._model else "python3"
        w = RestWorker(self._rest.start_kernel, kernel_name)
        w.signals.finished.connect(self._on_kernel_started)
        w.signals.error.connect(self._on_kernel_start_failed)
        self._pool.start(w)

    def _on_kernel_started(self, data: object) -> None:
        kernel_id = data["id"]
        self._model.kernel_id = kernel_id
        self._setup_kernel_client(kernel_id)
        self.kernel_started.emit(kernel_id)

    def _on_kernel_start_failed(self, msg: str) -> None:
        self.kernel_start_failed.emit(msg)

    def _setup_kernel_client(self, kernel_id: str) -> None:
        if self._kernel:
            self._kernel.disconnect()
            self._kernel.deleteLater()
        self._kernel = KernelClient(kernel_id, self._model.notebook_id,
                                     self._config, self)
        self._kernel.kernel_status_changed.connect(self._on_kernel_status)
        self._kernel.stream_received.connect(self._on_stream)
        self._kernel.display_data_received.connect(self._on_display_data)
        self._kernel.execute_result_received.connect(self._on_execute_result)
        self._kernel.error_received.connect(self._on_error)
        self._kernel.clear_output_received.connect(self._on_clear_output)
        self._kernel.execute_reply_received.connect(self._on_execute_reply)
        self._kernel.complete_reply_received.connect(self._on_complete_reply)
        self._kernel.inspect_reply_received.connect(self._on_inspect_reply)
        self._kernel.connect()

    def restart_kernel(self) -> None:
        if not self._model or not self._model.kernel_id:
            return
        self._execution_queue.clear()
        self._executing_cell_id = None
        kid = self._model.kernel_id
        if self._kernel:
            self._kernel.disconnect()
        w = RestWorker(self._rest.restart_kernel, kid)
        w.signals.finished.connect(self._on_kernel_restart_done)
        w.signals.error.connect(self._on_kernel_restart_error)
        self._pool.start(w)

    def _on_kernel_restart_done(self, _: object) -> None:
        if self._kernel:
            self._kernel.connect()

    def _on_kernel_restart_error(self, e: str) -> None:
        self.kernel_status_changed.emit(KernelStatus.ERROR)

    def shutdown_kernel(self) -> None:
        if not self._model or not self._model.kernel_id:
            return
        self._execution_queue.clear()
        self._executing_cell_id = None
        if self._kernel:
            self._kernel.disconnect()
        kid = self._model.kernel_id
        w = RestWorker(self._rest.shutdown_kernel, kid)
        self._pool.start(w)

    def interrupt_kernel(self) -> None:
        if not self._model or not self._model.kernel_id:
            return
        self._execution_queue.clear()
        if self._executing_cell_id:
            self.cell_executing_changed.emit(self._executing_cell_id, False)
            self._executing_cell_id = None
        if self._kernel:
            self._kernel.interrupt()
        kid = self._model.kernel_id
        w = RestWorker(self._rest.interrupt_kernel, kid)
        self._pool.start(w)

    # ---------- Execution ----------

    def execute_cell(self, cell_id: str) -> None:
        if not self._model or not self._kernel:
            return
        cell = self._model.get_cell(cell_id)
        if cell is None or cell.cell_type != CellType.CODE:
            return
        # Clear outputs before execution
        cell.outputs.clear()
        cell.execution_count = None
        self.cell_outputs_cleared.emit(cell_id)
        self.cell_execution_count_updated.emit(cell_id, None)

        if self._executing_cell_id is not None:
            # Queue it
            if cell_id not in self._execution_queue:
                self._execution_queue.append(cell_id)
            return
        self._fire_execute(cell)

    def _fire_execute(self, cell: CellModel) -> None:
        self._executing_cell_id = cell.cell_id
        self.cell_executing_changed.emit(cell.cell_id, True)
        self._kernel.execute(cell, cell.source)

    def execute_all_cells(self) -> None:
        if not self._model:
            return
        code_cells = [c for c in self._model.cells if c.cell_type == CellType.CODE]
        if not code_cells:
            return
        for c in code_cells:
            c.outputs.clear()
            c.execution_count = None
            self.cell_outputs_cleared.emit(c.cell_id)
            self.cell_execution_count_updated.emit(c.cell_id, None)
        first = code_cells[0]
        for c in code_cells[1:]:
            self._execution_queue.append(c.cell_id)
        self._fire_execute(first)

    def execute_cell_and_advance(self, cell_id: str) -> None:
        """Execute cell, then move focus to next (called by Shift+Enter in UI)."""
        self.execute_cell(cell_id)

    # ---------- Save ----------

    def save(self) -> None:
        if not self._model:
            return
        content = self._model.to_ipynb_dict()
        w = RestWorker(self._rest.save_notebook, self.path, content)
        w.signals.finished.connect(self._on_save_done)
        w.signals.error.connect(self._on_save_error)
        self._pool.start(w)

    def _on_save_done(self, _: object) -> None:
        self.notebook_saved.emit()

    def _on_save_error(self, e: str) -> None:
        self.notebook_save_failed.emit(e)

    # ---------- Cell editing ----------

    def update_cell_source(self, cell_id: str, source: str) -> None:
        if not self._model:
            return
        cell = self._model.get_cell(cell_id)
        if cell and cell.source != source:
            cell.source = source
            self.cell_source_changed.emit(cell_id, source)

    def add_cell(self, cell_type: CellType = CellType.CODE,
                 index: int | None = None) -> CellModel | None:
        if not self._model:
            return None
        cell = self._model.add_cell(cell_type, index)
        idx = self._model.index_of(cell.cell_id)
        self.cell_added.emit(idx, cell)
        return cell

    def add_cell_below(self, ref_cell_id: str,
                       cell_type: CellType = CellType.CODE) -> CellModel | None:
        if not self._model:
            return None
        idx = self._model.index_of(ref_cell_id)
        return self.add_cell(cell_type, idx + 1)

    def add_cell_above(self, ref_cell_id: str,
                       cell_type: CellType = CellType.CODE) -> CellModel | None:
        if not self._model:
            return None
        idx = self._model.index_of(ref_cell_id)
        return self.add_cell(cell_type, max(0, idx))

    def delete_cell(self, cell_id: str) -> None:
        if not self._model:
            return
        self._model.remove_cell(cell_id)
        self.cell_removed.emit(cell_id)

    def move_cell_up(self, cell_id: str) -> None:
        if not self._model:
            return
        idx = self._model.index_of(cell_id)
        if idx > 0:
            self._model.move_cell(cell_id, idx - 1)
            self.cell_moved.emit(cell_id, idx - 1)

    def move_cell_down(self, cell_id: str) -> None:
        if not self._model:
            return
        idx = self._model.index_of(cell_id)
        if idx < len(self._model.cells) - 1:
            self._model.move_cell(cell_id, idx + 1)
            self.cell_moved.emit(cell_id, idx + 1)

    # ---------- Kernel message slots ----------

    def _on_kernel_status(self, status: KernelStatus) -> None:
        self.kernel_status_changed.emit(status)

    def _on_stream(self, msg_id: str, name: str, text: str) -> None:
        if not self._model:
            return
        cell = self._find_cell_by_msg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="stream", text=text,
                            data={"text/plain": text, "stream_name": name})
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cell_id, output)

    def _on_display_data(self, msg_id: str, content: dict) -> None:
        cell = self._find_cell_by_msg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="display_data",
                            data=content.get("data", {}),
                            metadata=content.get("metadata", {}))
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cell_id, output)

    def _on_execute_result(self, msg_id: str, content: dict) -> None:
        cell = self._find_cell_by_msg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="execute_result",
                            data=content.get("data", {}),
                            metadata=content.get("metadata", {}),
                            execution_count=content.get("execution_count"))
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cell_id, output)

    def _on_error(self, msg_id: str, content: dict) -> None:
        cell = self._find_cell_by_msg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="error", data={
            "ename": content.get("ename", ""),
            "evalue": content.get("evalue", ""),
            "traceback": content.get("traceback", []),
        })
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cell_id, output)

    def _on_clear_output(self, msg_id: str) -> None:
        cell = self._find_cell_by_msg(msg_id)
        if cell is None:
            return
        cell.outputs.clear()
        self.cell_outputs_cleared.emit(cell.cell_id)

    def _on_execute_reply(self, msg_id: str, content: dict) -> None:
        cell = self._find_cell_by_executing()
        if cell:
            ec = content.get("execution_count")
            cell.execution_count = ec
            self.cell_execution_count_updated.emit(cell.cell_id, ec)
            self.cell_executing_changed.emit(cell.cell_id, False)

        self._executing_cell_id = None

        # Fire next queued cell
        if self._execution_queue:
            next_id = self._execution_queue.popleft()
            if self._model:
                next_cell = self._model.get_cell(next_id)
                if next_cell:
                    self._fire_execute(next_cell)

    # ---------- Completion ----------

    def request_completion(self, code: str, cursor_pos: int, callback) -> None:
        """Send a complete_request to the kernel; callback(matches, cursor_start, cursor_end)."""
        if not self._kernel or not self._kernel.is_connected():
            return
        msg_id = self._kernel.complete(code, cursor_pos)
        self._completion_callbacks[msg_id] = callback

    def _on_complete_reply(self, msg_id: str, content: dict) -> None:
        cb = self._completion_callbacks.pop(msg_id, None)
        if cb:
            cb(
                content.get("matches", []),
                content.get("cursor_start", 0),
                content.get("cursor_end", 0),
            )

    def request_inspection(self, code: str, cursor_pos: int,
                           callback, detail_level: int = 0) -> None:
        """Send an inspect_request; callback(mime_data: dict)."""
        if not self._kernel or not self._kernel.is_connected():
            return
        msg_id = self._kernel.inspect(code, cursor_pos, detail_level)
        self._inspection_callbacks[msg_id] = callback

    def _on_inspect_reply(self, msg_id: str, content: dict) -> None:
        cb = self._inspection_callbacks.pop(msg_id, None)
        if cb and content.get("found"):
            data = content.get("data", {})
            if data:
                cb(data)

    # ---------- Helpers ----------

    def _find_cell_by_msg(self, msg_id: str) -> CellModel | None:
        if not self._kernel or not self._model:
            return None
        resolved = self._kernel._tracker.resolve(msg_id)
        if resolved:
            cell, _ = resolved
            return cell
        # Fall back: currently executing cell
        if self._executing_cell_id:
            return self._model.get_cell(self._executing_cell_id)
        return None

    def _find_cell_by_executing(self) -> CellModel | None:
        if self._executing_cell_id and self._model:
            return self._model.get_cell(self._executing_cell_id)
        return None

    def cleanup(self) -> None:
        self.shutdown_kernel()
