#!/usr/bin/env python3
"""JupyterQt - PySide6 frontend for Jupyter notebooks."""

import sys
import faulthandler
faulthandler.enable()  # print C-level traceback on segfault

from PySide6.QtWidgets import QApplication

from jupyterqt.config import ServerConfig
from jupyterqt.controllers.app_controller import AppController
from jupyterqt.ui.connection_dialog import ConnectionDialog
from jupyterqt.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JupyterQt")
    app.setOrganizationName("JupyterQt")

    # Start with default config; user can change via File > Connect
    config = ServerConfig(base_url="http://localhost:8888", token="")

    # Check for --url and --token CLI args
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg.startswith("--url="):
            config.base_url = arg[6:].rstrip("/")
        elif arg == "--url" and i + 1 < len(args):
            config.base_url = args[i + 1].rstrip("/")
        elif arg.startswith("--token="):
            config.token = arg[8:]
        elif arg == "--token" and i + 1 < len(args):
            config.token = args[i + 1]

    app_ctrl = AppController(config)
    window = MainWindow(app_ctrl)
    window.show()

    # Defer server check until after the event loop starts.
    # Without this, a fast response (e.g. "connection refused") can arrive
    # before the event loop is running, causing dialog-in-dialog issues.
    from PySide6.QtCore import QTimer
    def _startup():
        app_ctrl.checkServer()
        for arg in args:
            if arg.endswith(".ipynb"):
                app_ctrl.openNotebook(arg)

    QTimer.singleShot(0, _startup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
