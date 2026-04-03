from PySide6.QtCore import Signal, Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                                QLabel, QPushButton, QToolButton, QHBoxLayout, QMenu,
                                QInputDialog, QMessageBox)

from jupyterqt.config import ServerConfig
from jupyterqt.network.rest_client import RestClient
from jupyterqt.network.rest_workers import RestWorker
from jupyterqt.ui.icon_registry import icon


class FileBrowserWidget(QWidget):
    """Simple tree-based file browser for Jupyter server contents."""

    notebook_selected = Signal(str)       # path
    new_notebook_requested = Signal(str)  # directory path

    def __init__(self, config: ServerConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._rest = RestClient(config)
        self._pool = QThreadPool.globalInstance()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Row 1: action buttons
        action_row = QHBoxLayout()
        action_row.setContentsMargins(4, 4, 4, 4)
        new_nb_btn = QPushButton("+", self)
        new_nb_btn.setFixedWidth(28)
        new_nb_btn.setToolTip("New notebook in current directory")
        new_nb_btn.clicked.connect(lambda: self.new_notebook_requested.emit(self._current_path))
        new_dir_btn = QPushButton(self)
        new_dir_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogNewFolder))
        new_dir_btn.setFixedWidth(28)
        new_dir_btn.setToolTip("New folder in current directory")
        new_dir_btn.clicked.connect(self._onNewFolder)
        refresh_btn = QPushButton("↻", self)
        refresh_btn.setFixedWidth(28)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        action_row.addStretch()
        action_row.addWidget(new_nb_btn)
        action_row.addWidget(new_dir_btn)
        action_row.addWidget(refresh_btn)
        layout.addLayout(action_row)

        # Row 2: breadcrumb path
        self._breadcrumb_bar = QWidget(self)
        self._breadcrumb_bar.setStyleSheet(
            "QWidget#breadcrumb { background: #f0f0f0; border-bottom: 1px solid #d8d8d8; }"
            "QToolButton { border: none; padding: 1px 3px; background: transparent; font-size: 9pt; }"
            "QToolButton:hover { background: #dde; border-radius: 3px; }"
        )
        self._breadcrumb_bar.setObjectName("breadcrumb")
        self._breadcrumb_layout = QHBoxLayout(self._breadcrumb_bar)
        self._breadcrumb_layout.setContentsMargins(4, 3, 4, 3)
        self._breadcrumb_layout.setSpacing(0)
        layout.addWidget(self._breadcrumb_bar)

        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.itemDoubleClicked.connect(self._onItemDoubleClicked)
        self._tree.customContextMenuRequested.connect(self._onContextMenu)
        layout.addWidget(self._tree)

        self._server_info_label = QLabel("", self)
        self._server_info_label.setWordWrap(True)
        self._server_info_label.setStyleSheet(
            "QLabel { color: #666; font-size: 8pt; padding: 4px 6px; "
            "border-top: 1px solid #d8d8d8; background: #f8f8f8; }"
        )
        layout.addWidget(self._server_info_label)

        self._current_path = ""
        self._updateBreadcrumb()
        QTimer.singleShot(0, self._refresh)
        QTimer.singleShot(0, self._fetchServerInfo)

    def updateConfig(self, config: ServerConfig) -> None:
        self._config = config
        self._rest.updateConfig(config)
        self._refresh()
        self._fetchServerInfo()

    # ------------------------------------------------------------------ Refresh

    def _refresh(self) -> None:
        w = RestWorker(self._rest.listContents, self._current_path)
        w.signals.finished.connect(self._onContentsLoaded)
        w.signals.error.connect(self._onLoadError)
        self._pool.start(w)

    def _fetchServerInfo(self) -> None:
        w = RestWorker(self._rest.getServerInfo)
        w.signals.finished.connect(self._onServerInfo)
        self._pool.start(w)

    def _onServerInfo(self, data: object) -> None:
        if not isinstance(data, dict):
            return
        hostname = data.get("hostname") or data.get("base_url", "")
        root_dir = data.get("root_dir") or data.get("notebook_dir", "")
        parts = []
        if hostname:
            parts.append(f"Host: {hostname}")
        if root_dir:
            parts.append(f"Dir: {root_dir}")
        self._server_info_label.setText("\n".join(parts))

    def _onLoadError(self, error: str) -> None:
        self._tree.clear()
        item = QTreeWidgetItem()
        item.setText(0, f"⚠ {error}")
        self._tree.addTopLevelItem(item)

    def _onContentsLoaded(self, data: object) -> None:
        self._tree.clear()
        if not isinstance(data, dict):
            return
        items_data = data.get("content", [])
        if not isinstance(items_data, list):
            return
        dirs = sorted([i for i in items_data if i.get("type") == "directory"],
                      key=lambda x: x.get("name", ""))
        notebooks = sorted([i for i in items_data if i.get("type") == "notebook"],
                           key=lambda x: x.get("name", ""))
        others = sorted([i for i in items_data
                         if i.get("type") not in ("directory", "notebook")],
                        key=lambda x: x.get("name", ""))

        for item_data in dirs + notebooks + others:
            item = QTreeWidgetItem()
            name = item_data.get("name", "")
            itype = item_data.get("type", "")
            path = item_data.get("path", "")
            item.setText(0, name)
            if itype == "directory":
                item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
            elif itype == "notebook":
                item.setIcon(0, icon("notebook"))
            elif name.endswith(".py"):
                item.setIcon(0, icon("python"))
            else:
                item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": itype, "path": path,
                                                        "name": name})
            self._tree.addTopLevelItem(item)

    # ------------------------------------------------------------------ Navigation

    def _navigateTo(self, path: str) -> None:
        self._current_path = path
        self._updateBreadcrumb()
        self._refresh()

    def _updateBreadcrumb(self) -> None:
        while self._breadcrumb_layout.count():
            item = self._breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        root_btn = QToolButton(self._breadcrumb_bar)
        root_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
        root_btn.setToolTip("Root")
        root_btn.clicked.connect(lambda: self._navigateTo(""))
        self._breadcrumb_layout.addWidget(root_btn)

        if self._current_path:
            parts = self._current_path.split("/")
            for i, part in enumerate(parts):
                sep = QLabel(" › ", self._breadcrumb_bar)
                sep.setStyleSheet("color: #999; font-size: 9pt;")
                self._breadcrumb_layout.addWidget(sep)
                target = "/".join(parts[:i + 1])
                btn = QToolButton(self._breadcrumb_bar)
                btn.setText(part)
                btn.setToolTip(target)
                btn.clicked.connect(lambda checked=False, p=target: self._navigateTo(p))
                self._breadcrumb_layout.addWidget(btn)

        self._breadcrumb_layout.addStretch()

    def _onItemDoubleClicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data["type"] == "notebook":
            self.notebook_selected.emit(data["path"])
        elif data["type"] == "directory":
            self._navigateTo(data["path"])

    # ------------------------------------------------------------------ New folder

    def _onNewFolder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        path = f"{self._current_path}/{name}" if self._current_path else name
        w = RestWorker(self._rest.createDirectory, path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._showError("Create folder failed", e))
        self._pool.start(w)

    # ------------------------------------------------------------------ Context menu

    def _onContextMenu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data["type"] != "notebook":
            return

        path = data["path"]
        name = data["name"]

        menu = QMenu(self)
        rename_act = menu.addAction("Rename…")
        duplicate_act = menu.addAction("Duplicate")
        menu.addSeparator()
        delete_act = menu.addAction("Delete")

        action = menu.exec(self._tree.viewport().mapToGlobal(pos))

        if action == rename_act:
            self._renameNotebook(path, name)
        elif action == duplicate_act:
            self._duplicateNotebook(path)
        elif action == delete_act:
            self._deleteNotebook(path, name)

    def _renameNotebook(self, path: str, current_name: str) -> None:
        new_name, ok = QInputDialog.getText(
            self, "Rename Notebook", "New name:", text=current_name
        )
        if not ok or not new_name.strip() or new_name.strip() == current_name:
            return
        new_name = new_name.strip()
        if not new_name.endswith(".ipynb"):
            new_name += ".ipynb"
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        new_path = f"{parent}/{new_name}" if parent else new_name
        w = RestWorker(self._rest.renameFile, path, new_path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._showError("Rename failed", e))
        self._pool.start(w)

    def _duplicateNotebook(self, path: str) -> None:
        w = RestWorker(self._rest.copyFile, path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._showError("Duplicate failed", e))
        self._pool.start(w)

    def _deleteNotebook(self, path: str, name: str) -> None:
        reply = QMessageBox.question(
            self, "Delete Notebook",
            f'Permanently delete "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        w = RestWorker(self._rest.deleteFile, path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._showError("Delete failed", e))
        self._pool.start(w)

    def _showError(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
