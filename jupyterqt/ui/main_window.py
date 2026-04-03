from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import (QMainWindow, QWidget, QSplitter, QStatusBar,
                                QLabel)

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

        self._buildUi()
        self._buildMenu()
        self._connectApp()

    # ------------------------------------------------------------------ UI

    def _buildUi(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(splitter)

        # Left: file browser
        self._file_browser = FileBrowserWidget(self._app.config, self)
        self._file_browser.setMinimumWidth(160)
        self._file_browser.setMaximumWidth(280)
        self._file_browser.notebook_selected.connect(self._onOpenNotebook)
        self._file_browser.new_notebook_requested.connect(self._onNewNotebook)
        splitter.addWidget(self._file_browser)

        # Right: workspace (panes + splits)
        self._workspace = WorkspaceWidget(self)
        self._workspace.active_controller_changed.connect(
            self._onActiveControllerChanged
        )
        splitter.addWidget(self._workspace)
        splitter.setStretchFactor(1, 1)

        # Status bar
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Not connected", self)
        self._status_bar.addWidget(self._status_label)

    def _buildMenu(self) -> None:
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        self._action_connect = QAction("&Connect to Server…", self)
        self._action_connect.triggered.connect(self._showConnectionDialog)
        file_menu.addAction(self._action_connect)
        file_menu.addSeparator()
        self._action_save = QAction("&Save Notebook", self)
        self._action_save.setShortcut(QKeySequence.StandardKey.Save)
        self._action_save.triggered.connect(self._saveCurrent)
        file_menu.addAction(self._action_save)
        file_menu.addSeparator()
        self._action_quit = QAction("&Quit", self)
        self._action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self._action_quit.triggered.connect(self.close)
        file_menu.addAction(self._action_quit)

        # Edit
        edit_menu = menubar.addMenu("&Edit")
        a = QAction("Add Code Cell Below", self)
        a.triggered.connect(lambda: self._addCell("code"))
        edit_menu.addAction(a)
        a = QAction("Add Markdown Cell Below", self)
        a.triggered.connect(lambda: self._addCell("markdown"))
        edit_menu.addAction(a)

        # View
        view_menu = menubar.addMenu("&View")
        self._action_split_h = QAction("Split Pane &Horizontally", self)
        self._action_split_h.setShortcut("Ctrl+\\")
        self._action_split_h.triggered.connect(self._splitH)
        view_menu.addAction(self._action_split_h)
        self._action_split_v = QAction("Split Pane &Vertically", self)
        self._action_split_v.setShortcut("Ctrl+Shift+\\")
        self._action_split_v.triggered.connect(self._splitV)
        view_menu.addAction(self._action_split_v)
        view_menu.addSeparator()
        self._action_new_view = QAction("Open &New View of Notebook", self)
        self._action_new_view.triggered.connect(self._openNewView)
        view_menu.addAction(self._action_new_view)

        # Kernel
        kernel_menu = menubar.addMenu("&Kernel")
        self._action_run_all = QAction("Run &All Cells", self)
        self._action_run_all.setShortcut("Ctrl+Shift+Return")
        self._action_run_all.triggered.connect(self._runAllCells)
        kernel_menu.addAction(self._action_run_all)
        kernel_menu.addSeparator()
        self._action_interrupt = QAction("&Interrupt Kernel", self)
        self._action_interrupt.setShortcut("Ctrl+.")
        self._action_interrupt.triggered.connect(self._interruptKernel)
        kernel_menu.addAction(self._action_interrupt)
        self._action_restart = QAction("&Restart Kernel", self)
        self._action_restart.triggered.connect(self._restartKernel)
        kernel_menu.addAction(self._action_restart)
        self._action_restart_run = QAction("Restart && Run All", self)
        self._action_restart_run.triggered.connect(self._restartAndRunAll)
        kernel_menu.addAction(self._action_restart_run)
        kernel_menu.addSeparator()
        self._action_shutdown = QAction("&Shutdown Kernel", self)
        self._action_shutdown.triggered.connect(self._shutdownKernel)
        kernel_menu.addAction(self._action_shutdown)

        # Settings
        settings_menu = menubar.addMenu("&Settings")
        self._action_settings_general = QAction("&General", self)
        self._action_settings_general.triggered.connect(self._showGeneralSettings)
        settings_menu.addAction(self._action_settings_general)
        self._action_settings_shortcuts = QAction("&Keyboard Shortcuts", self)
        self._action_settings_shortcuts.triggered.connect(self._showKeyboardShortcuts)
        settings_menu.addAction(self._action_settings_shortcuts)

    def _connectApp(self) -> None:
        self._app.notebook_opened.connect(self._onNotebookOpened)
        self._app.notebook_created.connect(self._file_browser._refresh)
        self._app.server_checked.connect(self._onServerChecked)

    # ------------------------------------------------------------------ Slots

    def _onOpenNotebook(self, path: str) -> None:
        self._app.openNotebook(path)

    def _onNotebookOpened(self, _notebook_id: str,
                             ctrl: NotebookController) -> None:
        self._workspace.openNotebook(ctrl)

    def _onActiveControllerChanged(self,
                                       ctrl: NotebookController | None) -> None:
        self._app.setActiveNotebook(ctrl)
        if ctrl:
            self.setWindowTitle(
                f"JupyterQt — {ctrl.path.split('/')[-1]}"
            )
        else:
            self.setWindowTitle("JupyterQt")

    def _onServerChecked(self, result: str) -> None:
        if result == "ok":
            self._status_label.setText(
                f"Connected to {self._app.config.base_url}"
            )
            self._file_browser.updateConfig(self._app.config)
        elif result == "unauthorized":
            self._status_label.setText(
                "Server reachable but token is wrong — use File > Connect to Server"
            )
            self._showConnectionDialog(status=result)
        else:
            self._status_label.setText(
                f"Cannot reach server ({result}) — use File > Connect to Server"
            )
            self._showConnectionDialog(status=result)

    # ------------------------------------------------------------------ Actions

    def _currentController(self) -> NotebookController | None:
        return self._workspace.currentController()

    def _saveCurrent(self) -> None:
        ctrl = self._currentController()
        if ctrl:
            ctrl.save()

    def _runAllCells(self) -> None:
        ctrl = self._currentController()
        if ctrl:
            ctrl.executeAllCells()

    def _interruptKernel(self) -> None:
        ctrl = self._currentController()
        if ctrl:
            ctrl.interruptKernel()

    def _restartKernel(self) -> None:
        ctrl = self._currentController()
        if ctrl:
            ctrl.restartKernel()

    def _restartAndRunAll(self) -> None:
        ctrl = self._currentController()
        if not ctrl:
            return
        ctrl.restartKernel()
        # Run all once kernel goes idle
        def _onStatus(status, c=ctrl):
            if status == KernelStatus.IDLE:
                c.kernel_status_changed.disconnect(_onStatus)
                c.executeAllCells()
        ctrl.kernel_status_changed.connect(_onStatus)

    def _shutdownKernel(self) -> None:
        ctrl = self._currentController()
        if ctrl:
            ctrl.shutdownKernel()

    def _addCell(self, cell_type_str: str) -> None:
        from jupyterqt.models.cell_model import CellType
        ctrl = self._currentController()
        if ctrl:
            ct = CellType.CODE if cell_type_str == "code" else CellType.MARKDOWN
            ctrl.addCell(ct)

    def _splitH(self) -> None:
        if self._workspace._active_pane:
            self._workspace._split(
                self._workspace._active_pane, Qt.Orientation.Horizontal
            )

    def _splitV(self) -> None:
        if self._workspace._active_pane:
            self._workspace._split(
                self._workspace._active_pane, Qt.Orientation.Vertical
            )

    def _openNewView(self) -> None:
        ctrl = self._currentController()
        if ctrl:
            self._workspace.openNotebookInNewView(ctrl)

    def _showGeneralSettings(self) -> None:
        from jupyterqt.ui.settings_dialog import GeneralSettingsDialog
        GeneralSettingsDialog(self).exec()

    def _showKeyboardShortcuts(self) -> None:
        from jupyterqt.ui.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
        KeyboardShortcutsDialog(self).exec()

    def _onNewNotebook(self, directory: str) -> None:
        self._app.createNotebook(directory)

    def _showConnectionDialog(self, status: str | None = None) -> None:
        dlg = ConnectionDialog(self._app.config, self)
        if status:
            dlg.setStatus(status)
        if dlg.exec() == ConnectionDialog.DialogCode.Accepted:
            config = dlg.getConfig()
            self._app.updateConfig(config)
            self._app.checkServer()

    # ------------------------------------------------------------------ Overrides

    def closeEvent(self, event) -> None:
        for ctrl in self._app.allNotebooks():
            ctrl.cleanup()
        super().closeEvent(event)
