import uuid

from PySide6.QtCore import QObject, Signal, Slot

from jupyterqt.config import ServerConfig
from jupyterqt.jupyter.execution_tracker import ExecutionTracker
from jupyterqt.jupyter.message import JupyterMessage
from jupyterqt.models.cell_model import CellModel
from jupyterqt.models.kernel_state import KernelStateMachine, KernelStatus
from jupyterqt.network.kernel_websocket import KernelWebSocket


class KernelClient(QObject):
    kernel_status_changed = Signal(object)          # KernelStatus
    execute_reply_received = Signal(str, dict)       # msg_id, content
    stream_received = Signal(str, str, str)          # msg_id, stream_name, text
    display_data_received = Signal(str, dict)        # msg_id, content
    execute_result_received = Signal(str, dict)      # msg_id, content
    error_received = Signal(str, dict)               # msg_id, content
    clear_output_received = Signal(str)              # msg_id
    complete_reply_received = Signal(str, dict)      # msg_id, content
    inspect_reply_received = Signal(str, dict)       # msg_id, content
    ws_connected = Signal()
    ws_disconnected = Signal()
    ws_error = Signal(str)

    def __init__(self, kernel_id: str, notebookId: str,
                 config: ServerConfig, parent=None):
        super().__init__(parent)
        self.kernel_id = kernel_id
        self.notebookId = notebookId
        self._config = config
        self._session_id = str(uuid.uuid4())
        self._tracker = ExecutionTracker()
        self._pending_completions: set[str] = set()
        self._pending_inspections: set[str] = set()
        self._state = KernelStateMachine(self)
        self._state.status_changed.connect(self.kernel_status_changed)
        self._ws = KernelWebSocket(self)
        self._ws.connected.connect(self._onWsConnected)
        self._ws.disconnected.connect(self._onWsDisconnected)
        self._ws.error_occurred.connect(self._onWsError)
        self._ws.message_received.connect(self._onMessage)

    @property
    def status(self) -> KernelStatus:
        return self._state.current

    def connect(self) -> None:
        if self._ws.isConnected():
            return
        self._state.forceTransition(KernelStatus.CONNECTING)
        token = self._config.token
        url = (f"{self._config.wsBaseUrl}/api/kernels/{self.kernel_id}"
               f"/channels?session_id={self._session_id}")
        if token:
            url += f"&token={token}"
        self._ws.connectToKernel(url)

    def disconnect(self) -> None:
        self._ws.disconnectFromKernel()

    def execute(self, cell: CellModel, code: str) -> str:
        msg = JupyterMessage.create(
            msg_type="execute_request",
            content={
                "code": code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            session=self._session_id,
            channel="shell",
        )
        self._tracker.register(msg.msg_id, cell, self.notebookId)
        self._ws.sendMessage(msg.toDict())
        return msg.msg_id

    def complete(self, code: str, cursor_pos: int) -> str:
        msg = JupyterMessage.create(
            msg_type="complete_request",
            content={"code": code, "cursor_pos": cursor_pos},
            session=self._session_id,
            channel="shell",
        )
        self._pending_completions.add(msg.msg_id)
        self._ws.sendMessage(msg.toDict())
        return msg.msg_id

    def inspect(self, code: str, cursor_pos: int, detail_level: int = 0) -> str:
        msg = JupyterMessage.create(
            msg_type="inspect_request",
            content={"code": code, "cursor_pos": cursor_pos,
                     "detail_level": detail_level},
            session=self._session_id,
            channel="shell",
        )
        self._pending_inspections.add(msg.msg_id)
        self._ws.sendMessage(msg.toDict())
        return msg.msg_id

    def interrupt(self) -> None:
        # Kernel interrupt is done via REST; just cancel pending tracking
        self._tracker.cancelAllForNotebook(self.notebookId)

    def isConnected(self) -> bool:
        return self._ws.isConnected()

    @Slot()
    def _onWsConnected(self):
        self._state.forceTransition(KernelStatus.IDLE)
        self.ws_connected.emit()

    @Slot()
    def _onWsDisconnected(self):
        if self._state.current != KernelStatus.RESTARTING:
            self._state.forceTransition(KernelStatus.DISCONNECTED)
        self.ws_disconnected.emit()

    @Slot(str)
    def _onWsError(self, msg: str):
        self._state.forceTransition(KernelStatus.ERROR)
        self.ws_error.emit(msg)

    @Slot(dict)
    def _onMessage(self, data: dict):
        try:
            msg = JupyterMessage.fromDict(data)
        except Exception:
            return

        if msg.msg_type == "status":
            exec_state = msg.content.get("execution_state", "")
            if exec_state == "idle":
                self._state.transition(KernelStatus.IDLE)
            elif exec_state == "busy":
                self._state.transition(KernelStatus.BUSY)
            elif exec_state == "restarting":
                self._state.forceTransition(KernelStatus.RESTARTING)
            return

        parent_msg_id = msg.parent_header.get("msg_id", "")

        if msg.msg_type == "complete_reply":
            if parent_msg_id in self._pending_completions:
                self._pending_completions.discard(parent_msg_id)
                self.complete_reply_received.emit(parent_msg_id, msg.content)
            return

        if msg.msg_type == "inspect_reply":
            if parent_msg_id in self._pending_inspections:
                self._pending_inspections.discard(parent_msg_id)
                self.inspect_reply_received.emit(parent_msg_id, msg.content)
            return

        resolved = self._tracker.resolve(parent_msg_id)
        if resolved is None and msg.msg_type not in ("status", "comm_info_reply",
                                                      "kernel_info_reply"):
            return
        cell, _ = resolved if resolved else (None, None)

        if msg.msg_type == "stream":
            self.stream_received.emit(parent_msg_id,
                                      msg.content.get("name", "stdout"),
                                      msg.content.get("text", ""))

        elif msg.msg_type == "display_data":
            self.display_data_received.emit(parent_msg_id, msg.content)

        elif msg.msg_type == "execute_result":
            self.execute_result_received.emit(parent_msg_id, msg.content)

        elif msg.msg_type == "error":
            self.error_received.emit(parent_msg_id, msg.content)

        elif msg.msg_type == "clear_output":
            self.clear_output_received.emit(parent_msg_id)

        elif msg.msg_type == "execute_reply":
            self.execute_reply_received.emit(parent_msg_id, msg.content)
            self._tracker.cancel(parent_msg_id)
