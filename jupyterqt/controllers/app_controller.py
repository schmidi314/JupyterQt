from PySide6.QtCore import QObject, Signal, QThreadPool

from jupyterqt.commands import CommandRegistry
from jupyterqt.config import ServerConfig
from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.network.rest_client import RestClient
from jupyterqt.network.rest_workers import RestWorker


class AppController(QObject):
    notebook_opened = Signal(str, object)    # notebook_id, NotebookController
    notebook_closed = Signal(str)            # notebook_id
    notebook_created = Signal()              # fired after a new notebook file is created
    server_checked = Signal(str)             # "ok", "unauthorized", or error string

    def __init__(self, config: ServerConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._rest = RestClient(config)
        self._notebooks: dict[str, NotebookController] = {}
        self._active_notebook: NotebookController | None = None
        self._pool = QThreadPool.globalInstance()

    # ##############################################################################################################
    # commands

    def _registerCommands(self):
        reg = CommandRegistry.instance()
        reg.register('notebook', 'add-cell-above', [], [], self.cmd_add_cell_above)
        reg.register('notebook', 'add-cell-below', [], [], self._cmd_add_cell_below)

    def cmd_add_cell_above(self):
        if self._active_notebook is not None:
            self._active_notebook.n


    # ##############################################################################################################
    #

    @property
    def config(self) -> ServerConfig:
        return self._config

    def update_config(self, config: ServerConfig) -> None:
        self._config = config
        self._rest.update_config(config)

    def check_server(self) -> None:
        w = RestWorker(self._rest.check_server)
        w.signals.finished.connect(lambda result: self.server_checked.emit(str(result)))
        w.signals.error.connect(lambda e: self.server_checked.emit(f"error: {e}"))
        self._pool.start(w)

    def open_notebook(self, path: str) -> None:
        # Avoid opening same path twice
        for ctrl in self._notebooks.values():
            if ctrl.path == path:
                self.notebook_opened.emit(ctrl.notebook_id, ctrl)
                return

        ctrl = NotebookController(path, self._config, self)
        # We need notebook_id after load; connect a one-shot
        ctrl.notebook_loaded.connect(lambda: self._on_controller_loaded(ctrl))
        ctrl.notebook_load_failed.connect(lambda e: self._on_load_failed(ctrl, e))
        ctrl.load()

    def _on_controller_loaded(self, ctrl: NotebookController) -> None:
        notebook_id = ctrl.notebook_id
        self._notebooks[notebook_id] = ctrl
        self.notebook_opened.emit(notebook_id, ctrl)

    def _on_load_failed(self, ctrl: NotebookController, error: str) -> None:
        ctrl.deleteLater()

    def close_notebook(self, notebook_id: str) -> None:
        ctrl = self._notebooks.pop(notebook_id, None)
        if ctrl:
            if self._active_notebook is ctrl:
                self._active_notebook = None
            ctrl.cleanup()
            ctrl.deleteLater()
        self.notebook_closed.emit(notebook_id)

    def get_controller(self, notebook_id: str) -> NotebookController | None:
        return self._notebooks.get(notebook_id)

    def create_notebook(self, directory: str = "") -> None:
        w = RestWorker(self._rest.create_notebook, directory)
        w.signals.finished.connect(self._on_notebook_created)
        self._pool.start(w)

    def _on_notebook_created(self, data: object) -> None:
        if isinstance(data, dict) and "path" in data:
            self.notebook_created.emit()
            self.open_notebook(data["path"])

    def active_notebook(self) -> NotebookController | None:
        return self._active_notebook

    def set_active_notebook(self, ctrl: NotebookController | None) -> None:
        print(f'Notebook {ctrl.path} is now active.')
        self._active_notebook = ctrl

    def all_notebooks(self) -> list[NotebookController]:
        return list(self._notebooks.values())
