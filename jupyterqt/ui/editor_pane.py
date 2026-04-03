from PySide6.QtCore import Signal, Qt, QMimeData, QPoint, QTimer
from PySide6.QtGui import QDrag, QPixmap, QCursor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTabBar,
                                QToolButton, QLabel, QMenu, QApplication)

from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.ui.notebook_tab import NotebookTab


class _DraggableTabBar(QTabBar):
    _drag_controller = None    # class-level: NotebookController being dragged
    _drag_source_pane = None   # class-level: source EditorPane
    _drag_source_idx: int = -1 # class-level: tab index in source pane

    def __init__(self, pane: 'EditorPane', parent=None):
        super().__init__(parent)
        self._pane = pane
        self._press_pos = None
        self._press_idx = -1
        self.setAcceptDrops(True)

        self._active_drag = None
        self._drag_label = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
            self._press_idx = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self._press_idx != -1 and self._press_pos is not None:
            if (event.pos() - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
                self._beginDrag(self._press_idx)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_idx = -1
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def _beginDrag(self, idx: int) -> None:
        tab = self._pane._tabs.widget(idx)
        if not isinstance(tab, NotebookTab):
            return
        _DraggableTabBar._drag_controller = tab.controller
        _DraggableTabBar._drag_source_pane = self._pane
        _DraggableTabBar._drag_source_idx = idx
        self._press_idx = -1
        self._press_pos = None

        label = QLabel(self.tabText(idx))
        label.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        label.setStyleSheet("QLabel { background: #e3eaf6; border: 1px solid #1976d2; border-radius: 4px; padding: 3px 10px; font-size: 9pt; color: #1a1a1a; }")
        label.adjustSize()
        label.move(QCursor.pos() + QPoint(12, 12))
        label.show()
        self._drag_label = label

        #timer = QTimer()
        #timer.timeout.connect(lambda: label.move(QCursor.pos() + QPoint(12, 12)))
        #timer.start(16)

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData('application/x-jupyterqt-tab', b'1')
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

        #timer.stop()
        #label.hide()
        #label.deleteLater()

    def _tabPixmap(self, idx: int) -> QPixmap:
        return self.grab(self.tabRect(idx))

    def dragEnterEvent(self, event):

        if event.mimeData().hasFormat('application/x-jupyterqt-tab') and _DraggableTabBar._drag_controller is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        print('dragMoveEvent')
        if event.mimeData().hasFormat('application/x-jupyterqt-tab'):
            event.acceptProposedAction()
        if self._drag_label is not None:
            self._drag_label.move(event.pos())

    def dropEvent(self, event):
        ctrl = _DraggableTabBar._drag_controller
        source_pane = _DraggableTabBar._drag_source_pane
        source_idx = _DraggableTabBar._drag_source_idx
        _DraggableTabBar._drag_controller = None
        _DraggableTabBar._drag_source_pane = None
        _DraggableTabBar._drag_source_idx = -1

        if ctrl is None:
            event.ignore()
            return

        if source_pane is self._pane:
            drop_idx = self.tabAt(event.pos())
            if drop_idx == -1:
                drop_idx = self.count() - 1
            if source_idx != drop_idx:
                self.moveTab(source_idx, drop_idx)
        else:
            self._pane.openNotebook(ctrl)
            self._pane.focused.emit()
            if source_pane is not None:
                source_pane._closeControllerTab(ctrl)

        event.acceptProposedAction()



class EditorPane(QWidget):
    """A single pane containing a tab widget. Multiple panes live side-by-side
    in the WorkspaceWidget's splitter tree."""

    split_h_requested = Signal()   # split this pane horizontally
    split_v_requested = Signal()   # split this pane vertically
    close_requested = Signal()     # close this pane
    focused = Signal()             # a tab in this pane was activated
    current_controller_changed = Signal(object)   # NotebookController | None
    new_view_requested = Signal(object)           # NotebookController

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
        self._tabs.setTabBar(_DraggableTabBar(self, self._tabs))
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(False)  # our _DraggableTabBar handles all tab movement
        self._tabs.tabCloseRequested.connect(self._onTabClose)
        self._tabs.currentChanged.connect(self._onCurrentChanged)
        self._tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tabs.tabBar().customContextMenuRequested.connect(self._onTabBarContextMenu)
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

    def _closeControllerTab(self, controller: NotebookController) -> None:
        tab = self._notebook_id_to_tab.get(controller.notebookId)
        if tab is None:
            return
        idx = self._tabs.indexOf(tab)
        if idx != -1:
            self._onTabClose(idx)

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

    def _onTabBarContextMenu(self, pos) -> None:
        idx = self._tabs.tabBar().tabAt(pos)
        if idx == -1:
            return
        tab = self._tabs.widget(idx)
        if not isinstance(tab, NotebookTab):
            return
        menu = QMenu(self)
        new_view_act = menu.addAction("New view for notebook")
        if menu.exec(self._tabs.tabBar().mapToGlobal(pos)) == new_view_act:
            self.new_view_requested.emit(tab.controller)
