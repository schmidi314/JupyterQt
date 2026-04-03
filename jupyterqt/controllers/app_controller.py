from PySide6.QtCore import QObject, Signal, QThreadPool

from jupyterqt.config import ServerConfig
from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.network.rest_client import RestClient
from jupyterqt.network.rest_workers import RestWorker


class AppController(QObject):
    notebook_opened = Signal(str, object)    # notebookId, NotebookController
    notebook_closed = Signal(str)            # notebookId
    notebook_created = Signal()              # fired after a new notebook file is created
    server_checked = Signal(str)             # "ok", "unauthorized", or error string

    def __init__(self, config: ServerConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._rest = RestClient(config)
        self._notebooks: dict[str, NotebookController] = {}
        self._active_notebook: NotebookController | None = None
        self._pool = QThreadPool.globalInstance()


    # #########################################################################################################################################
    #

    @property
    def config(self) -> ServerConfig:
        return self._config

    def updateConfig(self, config: ServerConfig) -> None:
        self._config = config
        self._rest.updateConfig(config)

    def checkServer(self) -> None:
        w = RestWorker(self._rest.checkServer)
        w.signals.finished.connect(lambda result: self.server_checked.emit(str(result)))
        w.signals.error.connect(lambda e: self.server_checked.emit(f"error: {e}"))
        self._pool.start(w)

    def openNotebook(self, path: str) -> None:
        # Avoid opening same path twice
        for ctrl in self._notebooks.values():
            if ctrl.path == path:
                self.notebook_opened.emit(ctrl.notebookId, ctrl)
                return

        ctrl = NotebookController(path, self._config, self)
        # We need notebookId after load; connect a one-shot
        ctrl.notebook_loaded.connect(lambda: self._onControllerLoaded(ctrl))
        ctrl.notebook_load_failed.connect(lambda e: self._onLoadFailed(ctrl, e))
        ctrl.load()

    def _onControllerLoaded(self, ctrl: NotebookController) -> None:
        notebookId = ctrl.notebookId
        self._notebooks[notebookId] = ctrl
        self.notebook_opened.emit(notebookId, ctrl)

    def _onLoadFailed(self, ctrl: NotebookController, error: str) -> None:
        ctrl.deleteLater()

    def closeNotebook(self, notebookId: str) -> None:
        ctrl = self._notebooks.pop(notebookId, None)
        if ctrl:
            if self._active_notebook is ctrl:
                self._active_notebook = None
            ctrl.cleanup()
            ctrl.deleteLater()
        self.notebook_closed.emit(notebookId)

    def getController(self, notebookId: str) -> NotebookController | None:
        return self._notebooks.get(notebookId)

    def createNotebook(self, directory: str = "") -> None:
        w = RestWorker(self._rest.createNotebook, directory)
        w.signals.finished.connect(self._onNotebookCreated)
        self._pool.start(w)

    def _onNotebookCreated(self, data: object) -> None:
        if isinstance(data, dict) and "path" in data:
            self.notebook_created.emit()
            self.openNotebook(data["path"])

    def activeNotebook(self) -> NotebookController | None:
        return self._active_notebook

    def setActiveNotebook(self, ctrl: NotebookController | None) -> None:
        print(f'Notebook {ctrl.path} is now active.')
        self._active_notebook = ctrl

    def allNotebooks(self) -> list[NotebookController]:
        return list(self._notebooks.values())
