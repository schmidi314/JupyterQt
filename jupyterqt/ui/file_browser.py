from PySide6.QtCore import Signal, Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                                QLabel, QPushButton, QHBoxLayout, QMenu,
                                QInputDialog, QMessageBox)

from jupyterqt.network.rest_client import RestClient
from jupyterqt.config import ServerConfig
from jupyterqt.network.rest_workers import RestWorker


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

        header = QHBoxLayout()
        self._path_label = QLabel("/", self)
        new_nb_btn = QPushButton("+", self)
        new_nb_btn.setFixedWidth(28)
        new_nb_btn.setToolTip("New notebook in current directory")
        new_nb_btn.clicked.connect(
            lambda: self.new_notebook_requested.emit(self._current_path)
        )
        new_dir_btn = QPushButton(self)
        new_dir_btn.setIcon(self.style().standardIcon(
            self.style().StandardPixmap.SP_FileDialogNewFolder
        ))
        new_dir_btn.setFixedWidth(28)
        new_dir_btn.setToolTip("New folder in current directory")
        new_dir_btn.clicked.connect(self._on_new_folder)
        refresh_btn = QPushButton("↻", self)
        refresh_btn.setFixedWidth(28)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(self._path_label, 1)
        header.addWidget(new_nb_btn)
        header.addWidget(new_dir_btn)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tree)

        self._current_path = ""
        QTimer.singleShot(0, self._refresh)

    def update_config(self, config: ServerConfig) -> None:
        self._config = config
        self._rest.update_config(config)
        self._refresh()

    # ------------------------------------------------------------------ Refresh

    def _refresh(self) -> None:
        w = RestWorker(self._rest.list_contents, self._current_path)
        w.signals.finished.connect(self._on_contents_loaded)
        w.signals.error.connect(self._on_load_error)
        self._pool.start(w)

    def _on_load_error(self, error: str) -> None:
        self._tree.clear()
        item = QTreeWidgetItem()
        item.setText(0, f"⚠ {error}")
        self._tree.addTopLevelItem(item)

    def _on_contents_loaded(self, data: object) -> None:
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
            if itype == "directory":
                item.setText(0, f"📁 {name}")
            elif itype == "notebook":
                item.setText(0, f"📓 {name}")
            else:
                item.setText(0, f"📄 {name}")
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": itype, "path": path,
                                                        "name": name})
            self._tree.addTopLevelItem(item)

    # ------------------------------------------------------------------ Navigation

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data["type"] == "notebook":
            self.notebook_selected.emit(data["path"])
        elif data["type"] == "directory":
            self._current_path = data["path"]
            self._path_label.setText("/" + self._current_path)
            self._refresh()

    # ------------------------------------------------------------------ New folder

    def _on_new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        path = f"{self._current_path}/{name}" if self._current_path else name
        w = RestWorker(self._rest.create_directory, path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._show_error("Create folder failed", e))
        self._pool.start(w)

    # ------------------------------------------------------------------ Context menu

    def _on_context_menu(self, pos) -> None:
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
            self._rename_notebook(path, name)
        elif action == duplicate_act:
            self._duplicate_notebook(path)
        elif action == delete_act:
            self._delete_notebook(path, name)

    def _rename_notebook(self, path: str, current_name: str) -> None:
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
        w = RestWorker(self._rest.rename_file, path, new_path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._show_error("Rename failed", e))
        self._pool.start(w)

    def _duplicate_notebook(self, path: str) -> None:
        w = RestWorker(self._rest.copy_file, path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._show_error("Duplicate failed", e))
        self._pool.start(w)

    def _delete_notebook(self, path: str, name: str) -> None:
        reply = QMessageBox.question(
            self, "Delete Notebook",
            f'Permanently delete "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        w = RestWorker(self._rest.delete_file, path)
        w.signals.finished.connect(lambda _: self._refresh())
        w.signals.error.connect(lambda e: self._show_error("Delete failed", e))
        self._pool.start(w)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
