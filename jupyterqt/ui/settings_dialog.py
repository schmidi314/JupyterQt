from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QSpinBox,
                                QCheckBox, QDialogButtonBox, QLabel)

from jupyterqt.settings import Settings


class GeneralSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("General Settings")
        self.setMinimumWidth(340)

        settings = Settings.instance()
        layout = QVBoxLayout(self)

        hint = QLabel("Changes are applied immediately.")
        hint.setStyleSheet("color: #777; font-size: 9pt;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._input_font_size = QSpinBox()
        self._input_font_size.setRange(6, 72)
        self._input_font_size.setValue(settings.inputFontSize)
        self._input_font_size.setSuffix(" pt")
        self._input_font_size.valueChanged.connect(lambda v: setattr(Settings.instance(), 'inputFontSize', v))
        form.addRow("Input font size:", self._input_font_size)

        self._output_font_size = QSpinBox()
        self._output_font_size.setRange(6, 72)
        self._output_font_size.setValue(settings.outputFontSize)
        self._output_font_size.setSuffix(" pt")
        self._output_font_size.valueChanged.connect(lambda v: setattr(Settings.instance(), 'outputFontSize', v))
        form.addRow("Output font size:", self._output_font_size)

        self._output_max_lines = QSpinBox()
        self._output_max_lines.setRange(1, 200)
        self._output_max_lines.setValue(settings.outputMaxLines)
        self._output_max_lines.setSuffix(" lines")
        self._output_max_lines.valueChanged.connect(lambda v: setattr(Settings.instance(), 'outputMaxLines', v))
        form.addRow("Output scroll limit:", self._output_max_lines)

        self._heading_numbering = QCheckBox()
        self._heading_numbering.setChecked(settings.headingNumbering)
        self._heading_numbering.toggled.connect(lambda v: setattr(Settings.instance(), 'headingNumbering', v))
        form.addRow("Heading numbering:", self._heading_numbering)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
