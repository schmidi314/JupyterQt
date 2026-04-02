import json

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtNetwork import QAbstractSocket


class KernelWebSocket(QObject):
    message_received = Signal(dict)
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws = QWebSocket()
        self._ws.connected.connect(self._on_connected)
        self._ws.disconnected.connect(self._on_disconnected)
        self._ws.textMessageReceived.connect(self._on_text_message)
        self._ws.errorOccurred.connect(self._on_error)

    def connect_to_kernel(self, ws_url: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest
        request = QNetworkRequest(QUrl(ws_url))
        self._ws.open(request)

    def send_message(self, msg: dict) -> None:
        self._ws.sendTextMessage(json.dumps(msg))

    def disconnect_from_kernel(self) -> None:
        self._ws.close()

    def is_connected(self) -> bool:
        return self._ws.state() == QAbstractSocket.SocketState.ConnectedState

    @Slot()
    def _on_connected(self):
        self.connected.emit()

    @Slot()
    def _on_disconnected(self):
        self.disconnected.emit()

    @Slot(str)
    def _on_text_message(self, text: str):
        try:
            data = json.loads(text)
            self.message_received.emit(data)
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"JSON decode error: {e}")

    @Slot(object)
    def _on_error(self, error):
        self.error_occurred.emit(self._ws.errorString())
