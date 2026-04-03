import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

_DEFAULTS = {
    "inputFontSize": 10,
    "outputFontSize": 10,
}

_SETTINGS_PATH = Path.home() / ".jupyter" / "qtj" / "settings.json"


class Settings(QObject):
    input_font_size_changed = Signal(int)
    output_font_size_changed = Signal(int)

    _instance: "Settings | None" = None

    def __init__(self):
        super().__init__()
        self._data: dict = dict(_DEFAULTS)
        self._load()

    @classmethod
    def instance(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = Settings()
        return cls._instance

    # ── input font size ───────────────────────────────────────────────

    @property
    def inputFontSize(self) -> int:
        return self._data["inputFontSize"]

    @inputFontSize.setter
    def inputFontSize(self, size: int) -> None:
        size = max(6, min(size, 72))
        if self._data["inputFontSize"] != size:
            self._data["inputFontSize"] = size
            self._save()
            self.input_font_size_changed.emit(size)

    # ── output font size ──────────────────────────────────────────────

    @property
    def outputFontSize(self) -> int:
        return self._data["outputFontSize"]

    @outputFontSize.setter
    def outputFontSize(self, size: int) -> None:
        size = max(6, min(size, 72))
        if self._data["outputFontSize"] != size:
            self._data["outputFontSize"] = size
            self._save()
            self.output_font_size_changed.emit(size)

    # ── persistence ───────────────────────────────────────────────────

    def _load(self) -> None:
        if _SETTINGS_PATH.exists():
            try:
                with open(_SETTINGS_PATH) as f:
                    stored = json.load(f)
                self._data.update({k: v for k, v in stored.items() if k in _DEFAULTS})
            except Exception:
                pass

    def _save(self) -> None:
        try:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_SETTINGS_PATH, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass
