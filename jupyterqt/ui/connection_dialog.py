from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                                QLineEdit, QDialogButtonBox, QLabel, QPushButton,
                                QWidget)
from PySide6.QtCore import Qt

from jupyterqt.config import ServerConfig
from jupyterqt.network.rest_client import RestClient


class ConnectionDialog(QDialog):
    def __init__(self, config: ServerConfig | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Jupyter Server")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Enter the URL and token for your Jupyter server.\n"
            "Start one with:  jupyter notebook --no-browser\n"
            "The token appears in the server output after '?token='"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-size: 9pt;")
        layout.addWidget(info)

        form = QFormLayout()
        self._url_edit = QLineEdit(config.base_url if config else "http://localhost:8888")
        self._token_edit = QLineEdit(config.token if config else "")
        self._token_edit.setPlaceholderText("paste token here (leave blank if none)")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)

        show_btn = QPushButton("Show")
        show_btn.setCheckable(True)
        show_btn.setFixedWidth(50)
        show_btn.toggled.connect(
            lambda checked: self._token_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        token_row = QHBoxLayout()
        token_row.addWidget(self._token_edit)
        token_row.addWidget(show_btn)
        token_widget = QWidget()
        token_widget.setLayout(token_row)

        form.addRow("Server URL:", self._url_edit)
        form.addRow("Token:", token_widget)
        layout.addLayout(form)

        # Test button
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._testConnection)
        test_row.addWidget(self._test_btn)
        test_row.addStretch()
        layout.addLayout(test_row)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getConfig(self) -> ServerConfig:
        return ServerConfig(
            base_url=self._url_edit.text().rstrip("/"),
            token=self._token_edit.text().strip(),
        )

    def setStatus(self, result: str) -> None:
        if result == "ok":
            self._status_label.setStyleSheet("color: green; font-weight: bold;")
            self._status_label.setText("Connected successfully.")
        elif result == "unauthorized":
            self._status_label.setStyleSheet("color: orange; font-weight: bold;")
            self._status_label.setText(
                "Server reachable but token is wrong or missing.\n"
                "Check the token in your Jupyter server output."
            )
        else:
            self._status_label.setStyleSheet("color: red; font-weight: bold;")
            self._status_label.setText(
                f"Cannot reach server: {result}\n"
                "Is the Jupyter server running?"
            )

    def _testConnection(self) -> None:
        self._status_label.setStyleSheet("color: #555;")
        self._status_label.setText("Testing...")
        self._test_btn.setEnabled(False)
        config = self.getConfig()
        try:
            client = RestClient(config)
            result = client.checkServer()
        except Exception as e:
            result = f"error: {e}"
        self.setStatus(result)
        self._test_btn.setEnabled(True)
