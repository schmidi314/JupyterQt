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
        self._ws.connected.connect(self._onConnected)
        self._ws.disconnected.connect(self._onDisconnected)
        self._ws.textMessageReceived.connect(self._onTextMessage)
        self._ws.errorOccurred.connect(self._onError)

    def connectToKernel(self, ws_url: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest
        request = QNetworkRequest(QUrl(ws_url))
        self._ws.open(request)

    def sendMessage(self, msg: dict) -> None:
        self._ws.sendTextMessage(json.dumps(msg))

    def disconnectFromKernel(self) -> None:
        self._ws.close()

    def isConnected(self) -> bool:
        return self._ws.state() == QAbstractSocket.SocketState.ConnectedState

    @Slot()
    def _onConnected(self):
        self.connected.emit()

    @Slot()
    def _onDisconnected(self):
        self.disconnected.emit()

    @Slot(str)
    def _onTextMessage(self, text: str):
        try:
            data = json.loads(text)
            self.message_received.emit(data)
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"JSON decode error: {e}")

    @Slot(object)
    def _onError(self, error):
        self.error_occurred.emit(self._ws.errorString())
