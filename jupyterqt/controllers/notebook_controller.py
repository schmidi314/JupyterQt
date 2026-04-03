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
    cell_source_changed = Signal(str, str)           # cellId, source (broadcast to other views)
    cell_output_appended = Signal(str, object)      # cellId, OutputItem
    cell_outputs_cleared = Signal(str)               # cellId
    cell_execution_count_updated = Signal(str, object)  # cellId, int|None
    cell_executing_changed = Signal(str, bool)       # cellId, is_executing
    kernel_status_changed = Signal(object)           # KernelStatus
    notebook_loaded = Signal()
    notebook_load_failed = Signal(str)
    notebook_saved = Signal()
    notebook_save_failed = Signal(str)
    kernel_started = Signal(str)                     # kernel_id
    kernel_start_failed = Signal(str)
    cell_added = Signal(int, object)                 # index, CellModel
    cell_removed = Signal(str)                       # cellId
    cell_moved = Signal(str, int)                    # cellId, new_index
    cell_type_changed = Signal(str, object)          # cellId, CellType

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
    def notebookId(self) -> str | None:
        return self._model.notebookId if self._model else None

    @property
    def kernelStatus(self) -> KernelStatus:
        if self._kernel:
            return self._kernel.status
        return KernelStatus.DISCONNECTED

    # ---------- Loading ----------

    def load(self) -> None:
        w = RestWorker(self._rest.getNotebook, self.path)
        w.signals.finished.connect(self._onNotebookLoaded)
        w.signals.error.connect(self._onNotebookLoadError)
        self._pool.start(w)

    def _onNotebookLoaded(self, data: object) -> None:
        content = data["content"] if isinstance(data, dict) and "content" in data else data
        self._model = NotebookModel.fromIpynbDict(self.path, content)
        self.notebook_loaded.emit()
        self._startKernel()

    def _onNotebookLoadError(self, msg: str) -> None:
        self.notebook_load_failed.emit(msg)

    # ---------- Kernel lifecycle ----------

    def _startKernel(self) -> None:
        kernel_name = self._model.kernel_name if self._model else "python3"
        w = RestWorker(self._rest.startKernel, kernel_name)
        w.signals.finished.connect(self._onKernelStarted)
        w.signals.error.connect(self._onKernelStartFailed)
        self._pool.start(w)

    def _onKernelStarted(self, data: object) -> None:
        kernel_id = data["id"]
        self._model.kernel_id = kernel_id
        self._setupKernelClient(kernel_id)
        self.kernel_started.emit(kernel_id)

    def _onKernelStartFailed(self, msg: str) -> None:
        self.kernel_start_failed.emit(msg)

    def _setupKernelClient(self, kernel_id: str) -> None:
        if self._kernel:
            self._kernel.disconnect()
            self._kernel.deleteLater()
        self._kernel = KernelClient(kernel_id, self._model.notebookId,
                                     self._config, self)
        self._kernel.kernel_status_changed.connect(self._onKernelStatus)
        self._kernel.stream_received.connect(self._onStream)
        self._kernel.display_data_received.connect(self._onDisplayData)
        self._kernel.execute_result_received.connect(self._onExecuteResult)
        self._kernel.error_received.connect(self._onError)
        self._kernel.clear_output_received.connect(self._onClearOutput)
        self._kernel.execute_reply_received.connect(self._onExecuteReply)
        self._kernel.complete_reply_received.connect(self._onCompleteReply)
        self._kernel.inspect_reply_received.connect(self._onInspectReply)
        self._kernel.connect()

    def restartKernel(self) -> None:
        if not self._model or not self._model.kernel_id:
            return
        self._execution_queue.clear()
        self._executing_cell_id = None
        kid = self._model.kernel_id
        if self._kernel:
            self._kernel.disconnect()
        w = RestWorker(self._rest.restartKernel, kid)
        w.signals.finished.connect(self._onKernelRestartDone)
        w.signals.error.connect(self._onKernelRestartError)
        self._pool.start(w)

    def _onKernelRestartDone(self, _: object) -> None:
        if self._kernel:
            self._kernel.connect()

    def _onKernelRestartError(self, e: str) -> None:
        self.kernel_status_changed.emit(KernelStatus.ERROR)

    def shutdownKernel(self) -> None:
        if not self._model or not self._model.kernel_id:
            return
        self._execution_queue.clear()
        self._executing_cell_id = None
        if self._kernel:
            self._kernel.disconnect()
        kid = self._model.kernel_id
        w = RestWorker(self._rest.shutdownKernel, kid)
        self._pool.start(w)

    def interruptKernel(self) -> None:
        if not self._model or not self._model.kernel_id:
            return
        self._execution_queue.clear()
        if self._executing_cell_id:
            self.cell_executing_changed.emit(self._executing_cell_id, False)
            self._executing_cell_id = None
        if self._kernel:
            self._kernel.interrupt()
        kid = self._model.kernel_id
        w = RestWorker(self._rest.interruptKernel, kid)
        self._pool.start(w)

    # ---------- Execution ----------

    def executeCell(self, cellId: str) -> None:
        if not self._model or not self._kernel:
            return
        cell = self._model.getCell(cellId)
        if cell is None or cell.cell_type != CellType.CODE:
            return
        # Clear outputs before execution
        cell.outputs.clear()
        cell.execution_count = None
        self.cell_outputs_cleared.emit(cellId)
        self.cell_execution_count_updated.emit(cellId, None)

        if self._executing_cell_id is not None:
            # Queue it
            if cellId not in self._execution_queue:
                self._execution_queue.append(cellId)
            return
        self._fireExecute(cell)

    def _fireExecute(self, cell: CellModel) -> None:
        self._executing_cell_id = cell.cellId
        self.cell_executing_changed.emit(cell.cellId, True)
        self._kernel.execute(cell, cell.source)

    def executeAllCells(self) -> None:
        if not self._model:
            return
        code_cells = [c for c in self._model.cells if c.cell_type == CellType.CODE]
        if not code_cells:
            return
        for c in code_cells:
            c.outputs.clear()
            c.execution_count = None
            self.cell_outputs_cleared.emit(c.cellId)
            self.cell_execution_count_updated.emit(c.cellId, None)
        first = code_cells[0]
        for c in code_cells[1:]:
            self._execution_queue.append(c.cellId)
        self._fireExecute(first)

    def executeCellAndAdvance(self, cellId: str) -> None:
        """Execute cell, then move focus to next (called by Shift+Enter in UI)."""
        self.executeCell(cellId)

    # ---------- Save ----------

    def save(self) -> None:
        if not self._model:
            return
        content = self._model.toIpynbDict()
        w = RestWorker(self._rest.saveNotebook, self.path, content)
        w.signals.finished.connect(self._onSaveDone)
        w.signals.error.connect(self._onSaveError)
        self._pool.start(w)

    def _onSaveDone(self, _: object) -> None:
        self.notebook_saved.emit()

    def _onSaveError(self, e: str) -> None:
        self.notebook_save_failed.emit(e)

    # ---------- Cell editing ----------

    def updateCellSource(self, cellId: str, source: str) -> None:
        if not self._model:
            return
        cell = self._model.getCell(cellId)
        if cell and cell.source != source:
            cell.source = source
            self.cell_source_changed.emit(cellId, source)

    def addCell(self, cell_type: CellType = CellType.CODE,
                 index: int | None = None) -> CellModel | None:
        if not self._model:
            return None
        cell = self._model.addCell(cell_type, index)
        idx = self._model.indexOf(cell.cellId)
        self.cell_added.emit(idx, cell)
        return cell

    def addCellBelow(self, ref_cell_id: str,
                       cell_type: CellType = CellType.CODE) -> CellModel | None:
        if not self._model:
            return None
        idx = self._model.indexOf(ref_cell_id)
        return self.addCell(cell_type, idx + 1)

    def addCellAbove(self, ref_cell_id: str,
                       cell_type: CellType = CellType.CODE) -> CellModel | None:
        if not self._model:
            return None
        idx = self._model.indexOf(ref_cell_id)
        return self.addCell(cell_type, max(0, idx))

    def deleteCell(self, cellId: str) -> None:
        if not self._model:
            return
        self._model.removeCell(cellId)
        self.cell_removed.emit(cellId)

    def moveCellUp(self, cellId: str) -> None:
        if not self._model:
            return
        idx = self._model.indexOf(cellId)
        if idx > 0:
            self._model.moveCell(cellId, idx - 1)
            self.cell_moved.emit(cellId, idx - 1)

    def changeCellType(self, cellId: str, new_type: CellType) -> None:
        if not self._model:
            return
        cell = self._model.getCell(cellId)
        if cell is None or cell.cell_type == new_type:
            return
        cell.cell_type = new_type
        self.cell_type_changed.emit(cellId, new_type)

    def moveCellDown(self, cellId: str) -> None:
        if not self._model:
            return
        idx = self._model.indexOf(cellId)
        if idx < len(self._model.cells) - 1:
            self._model.moveCell(cellId, idx + 1)
            self.cell_moved.emit(cellId, idx + 1)

    # ---------- Kernel message slots ----------

    def _onKernelStatus(self, status: KernelStatus) -> None:
        self.kernel_status_changed.emit(status)

    def _onStream(self, msg_id: str, name: str, text: str) -> None:
        if not self._model:
            return
        cell = self._findCellByMsg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="stream", text=text,
                            data={"text/plain": text, "stream_name": name})
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cellId, output)

    def _onDisplayData(self, msg_id: str, content: dict) -> None:
        cell = self._findCellByMsg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="display_data",
                            data=content.get("data", {}),
                            metadata=content.get("metadata", {}))
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cellId, output)

    def _onExecuteResult(self, msg_id: str, content: dict) -> None:
        cell = self._findCellByMsg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="execute_result",
                            data=content.get("data", {}),
                            metadata=content.get("metadata", {}),
                            execution_count=content.get("execution_count"))
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cellId, output)

    def _onError(self, msg_id: str, content: dict) -> None:
        cell = self._findCellByMsg(msg_id)
        if cell is None:
            return
        output = OutputItem(output_type="error", data={
            "ename": content.get("ename", ""),
            "evalue": content.get("evalue", ""),
            "traceback": content.get("traceback", []),
        })
        cell.outputs.append(output)
        self.cell_output_appended.emit(cell.cellId, output)

    def _onClearOutput(self, msg_id: str) -> None:
        cell = self._findCellByMsg(msg_id)
        if cell is None:
            return
        cell.outputs.clear()
        self.cell_outputs_cleared.emit(cell.cellId)

    def _onExecuteReply(self, msg_id: str, content: dict) -> None:
        cell = self._findCellByExecuting()
        if cell:
            ec = content.get("execution_count")
            cell.execution_count = ec
            self.cell_execution_count_updated.emit(cell.cellId, ec)
            self.cell_executing_changed.emit(cell.cellId, False)

        self._executing_cell_id = None

        # Fire next queued cell
        if self._execution_queue:
            next_id = self._execution_queue.popleft()
            if self._model:
                next_cell = self._model.getCell(next_id)
                if next_cell:
                    self._fireExecute(next_cell)

    # ---------- Completion ----------

    def requestCompletion(self, code: str, cursor_pos: int, callback) -> None:
        """Send a complete_request to the kernel; callback(matches, cursor_start, cursor_end)."""
        if not self._kernel or not self._kernel.isConnected():
            return
        msg_id = self._kernel.complete(code, cursor_pos)
        self._completion_callbacks[msg_id] = callback

    def _onCompleteReply(self, msg_id: str, content: dict) -> None:
        cb = self._completion_callbacks.pop(msg_id, None)
        if cb:
            cb(
                content.get("matches", []),
                content.get("cursor_start", 0),
                content.get("cursor_end", 0),
            )

    def requestInspection(self, code: str, cursor_pos: int,
                           callback, detail_level: int = 0) -> None:
        """Send an inspect_request; callback(mime_data: dict)."""
        if not self._kernel or not self._kernel.isConnected():
            return
        msg_id = self._kernel.inspect(code, cursor_pos, detail_level)
        self._inspection_callbacks[msg_id] = callback

    def _onInspectReply(self, msg_id: str, content: dict) -> None:
        cb = self._inspection_callbacks.pop(msg_id, None)
        if cb and content.get("found"):
            data = content.get("data", {})
            if data:
                cb(data)

    # ---------- Helpers ----------

    def _findCellByMsg(self, msg_id: str) -> CellModel | None:
        if not self._kernel or not self._model:
            return None
        resolved = self._kernel._tracker.resolve(msg_id)
        if resolved:
            cell, _ = resolved
            return cell
        # Fall back: currently executing cell
        if self._executing_cell_id:
            return self._model.getCell(self._executing_cell_id)
        return None

    def _findCellByExecuting(self) -> CellModel | None:
        if self._executing_cell_id and self._model:
            return self._model.getCell(self._executing_cell_id)
        return None

    def cleanup(self) -> None:
        self.shutdownKernel()
