from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                                QToolButton, QLabel)

from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.ui.notebook_tab import NotebookTab


class EditorPane(QWidget):
    """A single pane containing a tab widget. Multiple panes live side-by-side
    in the WorkspaceWidget's splitter tree."""

    split_h_requested = Signal()   # split this pane horizontally
    split_v_requested = Signal()   # split this pane vertically
    close_requested = Signal()     # close this pane
    focused = Signal()             # a tab in this pane was activated
    current_controller_changed = Signal(object)   # NotebookController | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notebook_id_to_tab: dict[str, NotebookTab] = {}
        self._notebook_id_to_name: dict[str, str] = {}
        self._is_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── header bar ──────────────────────────────────────────────────
        header = QWidget(self)
        header.setFixedHeight(28)
        header.setStyleSheet("background: #f0f0f0; border-bottom: 1px solid #d0d0d0;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(4, 0, 4, 0)
        hl.setSpacing(2)
        hl.addStretch()

        for label, tip, sig in (
            ("⬛│⬛", "Split vertically",   self.split_v_requested),
            ("⬛\n⬛", "Split horizontally", self.split_h_requested),
        ):
            btn = QToolButton(header)
            btn.setToolTip(tip)
            btn.setFixedSize(24, 22)
            btn.setStyleSheet(
                "QToolButton { border: none; font-size: 9pt; color: #555; }"
                "QToolButton:hover { background: #ddd; border-radius: 3px; }"
            )
            btn.clicked.connect(sig)
            hl.addWidget(btn)

        hl.itemAt(hl.count() - 2).widget().setText("┃┃")  # split-v icon
        hl.itemAt(hl.count() - 1).widget().setText("═")   # split-h icon

        close_btn = QToolButton(header)
        close_btn.setText("✕")
        close_btn.setToolTip("Close pane")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            "QToolButton { border: none; color: #888; }"
            "QToolButton:hover { background: #e57373; color: white; border-radius: 3px; }"
        )
        close_btn.clicked.connect(self.close_requested)
        hl.addWidget(close_btn)
        layout.addWidget(header)

        # ── tab widget ──────────────────────────────────────────────────
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._onTabClose)
        self._tabs.currentChanged.connect(self._onCurrentChanged)
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; }"
            "QTabBar::tab { padding: 4px 10px; }"
        )
        layout.addWidget(self._tabs)

        self._updateBorder()

    # #########################################################################################################################################
    # Public API

    def openNotebook(self, controller: NotebookController) -> None:
        """Open a view of this notebook. Focuses an existing tab if already open."""
        notebookId = controller.notebookId
        if notebookId in self._notebook_id_to_tab:
            tab = self._notebook_id_to_tab[notebookId]
            self._tabs.setCurrentWidget(tab)
            return

        tab = NotebookTab(controller, self._tabs)
        tab_name = controller.path.split("/")[-1]
        idx = self._tabs.addTab(tab, tab_name)
        self._tabs.setCurrentIndex(idx)
        self._notebook_id_to_tab[notebookId] = tab
        self._notebook_id_to_name[notebookId] = tab_name

        controller.notebook_dirty_changed.connect(
            lambda dirty, nid=notebookId: self._onDirtyChanged(nid, dirty)
        )

    def currentController(self) -> NotebookController | None:
        tab = self._tabs.currentWidget()
        if isinstance(tab, NotebookTab):
            return tab.controller
        return None

    def setActive(self, active: bool) -> None:
        self._is_active = active
        self._updateBorder()

    def hasNotebooks(self) -> bool:
        return self._tabs.count() > 0

    def getCurrentNotebookTab(self):
        current_tab = self._tabs.currentWidget()
        assert isinstance(current_tab, NotebookTab)
        return current_tab

    # #########################################################################################################################################
    # Internal

    def _updateBorder(self) -> None:
        if self._is_active:
            self.setStyleSheet(
                "EditorPane > QWidget { border: 2px solid #1976d2; border-radius: 3px; }"
            )
        else:
            self.setStyleSheet("")

    def _onDirtyChanged(self, notebookId: str, dirty: bool) -> None:
        tab = self._notebook_id_to_tab.get(notebookId)
        if tab is None:
            return
        idx = self._tabs.indexOf(tab)
        if idx == -1:
            return
        base = self._notebook_id_to_name.get(notebookId, "")
        self._tabs.setTabText(idx, f"● {base}" if dirty else base)

    def _onTabClose(self, index: int) -> None:
        tab = self._tabs.widget(index)
        if isinstance(tab, NotebookTab):
            nid = tab.controller.notebookId
            self._notebook_id_to_tab.pop(nid, None)
            self._notebook_id_to_name.pop(nid, None)
        self._tabs.removeTab(index)
        self.current_controller_changed.emit(self.currentController())

    def _onCurrentChanged(self, _index: int) -> None:
        ctrl = self.currentController()
        self.current_controller_changed.emit(ctrl)
        self.focused.emit()
