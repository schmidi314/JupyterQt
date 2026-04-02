from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter

from jupyterqt.controllers.notebook_controller import NotebookController
from jupyterqt.ui.editor_pane import EditorPane


class WorkspaceWidget(QWidget):
    """
    Manages a tree of QSplitters containing EditorPanes.

    Panes can be split horizontally (side-by-side) or vertically (top/bottom).
    The same notebook controller can be open in multiple panes simultaneously.
    """

    active_controller_changed = Signal(object)   # NotebookController | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panes: list[EditorPane] = []
        self._active_pane: EditorPane | None = None

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)

        # Start with a single root splitter holding one pane
        self._root_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._root_splitter.setChildrenCollapsible(False)
        self._root_layout.addWidget(self._root_splitter)

        first_pane = self._make_pane()
        self._root_splitter.addWidget(first_pane)
        self._set_active(first_pane)

        self._registerCommands()

    # ##############################################################################################################
    # commands

    def _registerCommands(self):
        pass

    def cmd_add_cell_above(self):
        if self._active_pane is not None:
            self._active_pane.get_current_notebook_tab().cmd_add_cell('above')

    def cmd_add_cell_below(self):
        if self._active_pane is not None:
            self._active_pane.get_current_notebook_tab().cmd_add_cell('below')

    # ── public API ──────────────────────────────────────────────────────

    def open_notebook(self, controller: NotebookController) -> None:
        """Open (or focus) a notebook in the currently active pane."""
        pane = self._active_pane or self._panes[0]
        pane.open_notebook(controller)

    def open_notebook_in_new_view(self, controller: NotebookController) -> None:
        """Open a second view of an already-open notebook.
        Splits the active pane if there's only one, otherwise opens in the
        first OTHER pane (or a new split)."""
        if len(self._panes) == 1:
            self._split(self._panes[0], Qt.Orientation.Horizontal)
        # Open in a pane that doesn't already show this controller
        for pane in self._panes:
            if pane is not self._active_pane:
                pane.open_notebook(controller)
                self._set_active(pane)
                return

    def current_controller(self) -> NotebookController | None:
        if self._active_pane:
            return self._active_pane.current_controller()
        return None

    # ── pane lifecycle ───────────────────────────────────────────────────

    def _make_pane(self) -> EditorPane:
        pane = EditorPane(self)
        self._panes.append(pane)
        pane.split_h_requested.connect(
            lambda p=pane: self._split(p, Qt.Orientation.Horizontal)
        )
        pane.split_v_requested.connect(
            lambda p=pane: self._split(p, Qt.Orientation.Vertical)
        )
        pane.close_requested.connect(lambda p=pane: self._close_pane(p))
        pane.focused.connect(lambda p=pane: self._set_active(p))
        pane.current_controller_changed.connect(
            lambda ctrl, p=pane: self._on_pane_controller_changed(p, ctrl)
        )
        return pane

    def _set_active(self, pane: EditorPane) -> None:
        if self._active_pane and self._active_pane is not pane:
            self._active_pane.set_active(False)
        self._active_pane = pane
        pane.set_active(True)
        self.active_controller_changed.emit(pane.current_controller())

    def _on_pane_controller_changed(self, pane: EditorPane,
                                    ctrl: NotebookController | None) -> None:
        if pane is self._active_pane:
            self.active_controller_changed.emit(ctrl)

    def _split(self, pane: EditorPane, orientation: Qt.Orientation) -> None:
        parent_splitter = self._parent_splitter(pane)
        new_pane = self._make_pane()

        if parent_splitter and parent_splitter.orientation() == orientation:
            # Same direction as parent → just insert next to pane
            idx = parent_splitter.indexOf(pane)
            parent_splitter.insertWidget(idx + 1, new_pane)
            self._equalize(parent_splitter)
        else:
            # Need a new splitter wrapper
            new_splitter = QSplitter(orientation)
            new_splitter.setChildrenCollapsible(False)

            if parent_splitter:
                idx = parent_splitter.indexOf(pane)
                pane.setParent(None)
                new_splitter.addWidget(pane)
                new_splitter.addWidget(new_pane)
                parent_splitter.insertWidget(idx, new_splitter)
                self._equalize(parent_splitter)
            else:
                # pane is the direct child of root_layout via root_splitter
                idx = self._root_splitter.indexOf(pane)
                pane.setParent(None)
                new_splitter.addWidget(pane)
                new_splitter.addWidget(new_pane)
                self._root_splitter.insertWidget(idx, new_splitter)
                self._equalize(self._root_splitter)

            self._equalize(new_splitter)

        self._set_active(new_pane)

    def _close_pane(self, pane: EditorPane) -> None:
        if len(self._panes) <= 1:
            return  # Never close the last pane

        parent_splitter = self._parent_splitter(pane)
        self._panes.remove(pane)

        if parent_splitter:
            pane.setParent(None)
            pane.deleteLater()

            # If the splitter now has exactly one child, dissolve it
            if parent_splitter.count() == 1:
                self._dissolve_splitter(parent_splitter)
        else:
            pane.setParent(None)
            pane.deleteLater()

        if pane is self._active_pane:
            self._set_active(self._panes[-1])

    def _dissolve_splitter(self, splitter: QSplitter) -> None:
        """Replace a single-child splitter with its only child."""
        if splitter.count() != 1:
            return
        child = splitter.widget(0)
        grandparent = splitter.parent()

        if isinstance(grandparent, QSplitter):
            idx = grandparent.indexOf(splitter)
            child.setParent(None)
            splitter.setParent(None)
            splitter.deleteLater()
            grandparent.insertWidget(idx, child)
            self._equalize(grandparent)
        elif grandparent is self:
            # child of root layout
            child.setParent(None)
            self._root_layout.removeWidget(splitter)
            splitter.setParent(None)
            splitter.deleteLater()
            self._root_splitter = (child if isinstance(child, QSplitter)
                                   else self._root_splitter)
            self._root_layout.addWidget(child)

    def _parent_splitter(self, pane: EditorPane) -> QSplitter | None:
        p = pane.parent()
        return p if isinstance(p, QSplitter) else None

    @staticmethod
    def _equalize(splitter: QSplitter) -> None:
        n = splitter.count()
        if n == 0:
            return
        total = (splitter.width() if splitter.orientation() == Qt.Orientation.Horizontal
                 else splitter.height())
        splitter.setSizes([total // n] * n)
