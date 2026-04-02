from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import (QMainWindow, QWidget, QSplitter, QStatusBar,
                                QLabel, QToolBar)

from jupyterqt.config import ServerConfig
from jupyterqt.controllers.app_controller import AppController
from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.models.kernel_state import KernelStatus
from jupyterqt.ui.connection_dialog import ConnectionDialog
from jupyterqt.ui.file_browser import FileBrowserWidget
from jupyterqt.ui.workspace_widget import WorkspaceWidget


class MainWindow(QMainWindow):
    def __init__(self, app_controller: AppController):
        super().__init__()
        self._app = app_controller

        self.setWindowTitle("JupyterQt")
        self.resize(1300, 850)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._connect_app()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(splitter)

        # Left: file browser
        self._file_browser = FileBrowserWidget(self._app.config, self)
        self._file_browser.setMinimumWidth(160)
        self._file_browser.setMaximumWidth(280)
        self._file_browser.notebook_selected.connect(self._on_open_notebook)
        self._file_browser.new_notebook_requested.connect(self._on_new_notebook)
        splitter.addWidget(self._file_browser)

        # Right: workspace (panes + splits)
        self._workspace = WorkspaceWidget(self)
        self._workspace.active_controller_changed.connect(
            self._on_active_controller_changed
        )
        splitter.addWidget(self._workspace)
        splitter.setStretchFactor(1, 1)

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Not connected", self)
        self._status_bar.addWidget(self._status_label)

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        self._action_connect = QAction("&Connect to Server…", self)
        self._action_connect.triggered.connect(self._show_connection_dialog)
        file_menu.addAction(self._action_connect)
        file_menu.addSeparator()
        self._action_save = QAction("&Save Notebook", self)
        self._action_save.setShortcut(QKeySequence.StandardKey.Save)
        self._action_save.triggered.connect(self._save_current)
        file_menu.addAction(self._action_save)
        file_menu.addSeparator()
        self._action_quit = QAction("&Quit", self)
        self._action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self._action_quit.triggered.connect(self.close)
        file_menu.addAction(self._action_quit)

        # Edit
        edit_menu = menubar.addMenu("&Edit")
        a = QAction("Add Code Cell Below", self)
        a.triggered.connect(lambda: self._add_cell("code"))
        edit_menu.addAction(a)
        a = QAction("Add Markdown Cell Below", self)
        a.triggered.connect(lambda: self._add_cell("markdown"))
        edit_menu.addAction(a)

        # View
        view_menu = menubar.addMenu("&View")
        self._action_split_h = QAction("Split Pane &Horizontally", self)
        self._action_split_h.setShortcut("Ctrl+\\")
        self._action_split_h.triggered.connect(self._split_h)
        view_menu.addAction(self._action_split_h)
        self._action_split_v = QAction("Split Pane &Vertically", self)
        self._action_split_v.setShortcut("Ctrl+Shift+\\")
        self._action_split_v.triggered.connect(self._split_v)
        view_menu.addAction(self._action_split_v)
        view_menu.addSeparator()
        self._action_new_view = QAction("Open &New View of Notebook", self)
        self._action_new_view.triggered.connect(self._open_new_view)
        view_menu.addAction(self._action_new_view)

        # Kernel
        kernel_menu = menubar.addMenu("&Kernel")
        self._action_run_all = QAction("Run &All Cells", self)
        self._action_run_all.setShortcut("Ctrl+Shift+Return")
        self._action_run_all.triggered.connect(self._run_all_cells)
        kernel_menu.addAction(self._action_run_all)
        kernel_menu.addSeparator()
        self._action_interrupt = QAction("&Interrupt Kernel", self)
        self._action_interrupt.setShortcut("Ctrl+.")
        self._action_interrupt.triggered.connect(self._interrupt_kernel)
        kernel_menu.addAction(self._action_interrupt)
        self._action_restart = QAction("&Restart Kernel", self)
        self._action_restart.triggered.connect(self._restart_kernel)
        kernel_menu.addAction(self._action_restart)
        self._action_restart_run = QAction("Restart && Run All", self)
        self._action_restart_run.triggered.connect(self._restart_and_run_all)
        kernel_menu.addAction(self._action_restart_run)
        kernel_menu.addSeparator()
        self._action_shutdown = QAction("&Shutdown Kernel", self)
        self._action_shutdown.triggered.connect(self._shutdown_kernel)
        kernel_menu.addAction(self._action_shutdown)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self._action_save)
        tb.addSeparator()
        tb.addAction(self._action_run_all)
        tb.addAction(self._action_interrupt)
        tb.addAction(self._action_restart)
        tb.addSeparator()
        tb.addAction(self._action_split_h)
        tb.addAction(self._action_split_v)
        tb.addAction(self._action_new_view)

    def _connect_app(self) -> None:
        self._app.notebook_opened.connect(self._on_notebook_opened)
        self._app.notebook_created.connect(self._file_browser._refresh)
        self._app.server_checked.connect(self._on_server_checked)

    # ------------------------------------------------------------------ Slots

    def _on_open_notebook(self, path: str) -> None:
        self._app.open_notebook(path)

    def _on_notebook_opened(self, _notebook_id: str,
                             ctrl: NotebookController) -> None:
        self._workspace.open_notebook(ctrl)

    def _on_active_controller_changed(self,
                                       ctrl: NotebookController | None) -> None:
        self._app.set_active_notebook(ctrl)
        if ctrl:
            self.setWindowTitle(
                f"JupyterQt — {ctrl.path.split('/')[-1]}"
            )
        else:
            self.setWindowTitle("JupyterQt")

    def _on_server_checked(self, result: str) -> None:
        if result == "ok":
            self._status_label.setText(
                f"Connected to {self._app.config.base_url}"
            )
            self._file_browser.update_config(self._app.config)
        elif result == "unauthorized":
            self._status_label.setText(
                "Server reachable but token is wrong — use File > Connect to Server"
            )
            self._show_connection_dialog(status=result)
        else:
            self._status_label.setText(
                f"Cannot reach server ({result}) — use File > Connect to Server"
            )
            self._show_connection_dialog(status=result)

    # ------------------------------------------------------------------ Actions

    def _current_controller(self) -> NotebookController | None:
        return self._workspace.current_controller()

    def _save_current(self) -> None:
        ctrl = self._current_controller()
        if ctrl:
            ctrl.save()

    def _run_all_cells(self) -> None:
        ctrl = self._current_controller()
        if ctrl:
            ctrl.execute_all_cells()

    def _interrupt_kernel(self) -> None:
        ctrl = self._current_controller()
        if ctrl:
            ctrl.interrupt_kernel()

    def _restart_kernel(self) -> None:
        ctrl = self._current_controller()
        if ctrl:
            ctrl.restart_kernel()

    def _restart_and_run_all(self) -> None:
        ctrl = self._current_controller()
        if not ctrl:
            return
        ctrl.restart_kernel()
        # Run all once kernel goes idle
        def _on_status(status, c=ctrl):
            if status == KernelStatus.IDLE:
                c.kernel_status_changed.disconnect(_on_status)
                c.execute_all_cells()
        ctrl.kernel_status_changed.connect(_on_status)

    def _shutdown_kernel(self) -> None:
        ctrl = self._current_controller()
        if ctrl:
            ctrl.shutdown_kernel()

    def _add_cell(self, cell_type_str: str) -> None:
        from jupyterqt.models.cell_model import CellType
        ctrl = self._current_controller()
        if ctrl:
            ct = CellType.CODE if cell_type_str == "code" else CellType.MARKDOWN
            ctrl.add_cell(ct)

    def _split_h(self) -> None:
        if self._workspace._active_pane:
            self._workspace._split(
                self._workspace._active_pane, Qt.Orientation.Horizontal
            )

    def _split_v(self) -> None:
        if self._workspace._active_pane:
            self._workspace._split(
                self._workspace._active_pane, Qt.Orientation.Vertical
            )

    def _open_new_view(self) -> None:
        ctrl = self._current_controller()
        if ctrl:
            self._workspace.open_notebook_in_new_view(ctrl)

    def _on_new_notebook(self, directory: str) -> None:
        self._app.create_notebook(directory)

    def _show_connection_dialog(self, status: str | None = None) -> None:
        dlg = ConnectionDialog(self._app.config, self)
        if status:
            dlg.set_status(status)
        if dlg.exec() == ConnectionDialog.DialogCode.Accepted:
            config = dlg.get_config()
            self._app.update_config(config)
            self._app.check_server()

    # ------------------------------------------------------------------ Overrides

    def closeEvent(self, event) -> None:
        for ctrl in self._app.all_notebooks():
            ctrl.cleanup()
        super().closeEvent(event)
