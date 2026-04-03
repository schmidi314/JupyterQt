from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
                                QDialogButtonBox, QHeaderView)

from jupyterqt.commands import CommandRegistry


def _formatShortcut(s: str) -> str:
    if not s:
        return ""
    parts = s.split('_')
    key = parts[-1]
    mods = parts[:-1]
    result = [m.capitalize() for m in mods]
    result.append(key.upper() if len(key) == 1 else key.capitalize())
    return '+'.join(result)


class KeyboardShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(520, 420)

        layout = QVBoxLayout(self)

        reg = CommandRegistry.instance()
        shortcut_map = {(ks.context, ks.command): ks.effective_shortcut
                        for ks in reg._keyboard_shortcuts.values()}

        commands = sorted(reg.allCommands(), key=lambda c: (c.context, c.command))

        self._table = QTableWidget(len(commands), 3, self)
        self._table.setHorizontalHeaderLabels(["Context", "Command", "Shortcut"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)

        for row, cmd in enumerate(commands):
            shortcut = shortcut_map.get((cmd.context, cmd.command), "")
            for col, text in enumerate([cmd.context, cmd.command, _formatShortcut(shortcut)]):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._table.setItem(row, col, item)

        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
