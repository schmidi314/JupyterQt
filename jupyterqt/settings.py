import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

_DEFAULTS = {
    "input_font_size": 10,
    "output_font_size": 10,
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
    def input_font_size(self) -> int:
        return self._data["input_font_size"]

    @input_font_size.setter
    def input_font_size(self, size: int) -> None:
        size = max(6, min(size, 72))
        if self._data["input_font_size"] != size:
            self._data["input_font_size"] = size
            self._save()
            self.input_font_size_changed.emit(size)

    # ── output font size ──────────────────────────────────────────────

    @property
    def output_font_size(self) -> int:
        return self._data["output_font_size"]

    @output_font_size.setter
    def output_font_size(self, size: int) -> None:
        size = max(6, min(size, 72))
        if self._data["output_font_size"] != size:
            self._data["output_font_size"] = size
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
