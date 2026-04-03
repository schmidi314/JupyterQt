from pathlib import Path

from PySide6.QtGui import QIcon

_ICONS_DIR = Path(__file__).parent / "icons"
_cache: dict[str, QIcon] = {}


def icon(name: str) -> QIcon:
    """Return a QIcon for *name* (no extension). Looks up jupyterqt/ui/icons/<name>.svg.
    Returns an empty QIcon when the file does not exist.
    Icons are cached after the first load."""
    if name in _cache:
        return _cache[name]
    path = _ICONS_DIR / f"{name}.svg"
    if not path.exists():
        return QIcon()
    ic = QIcon(str(path))
    _cache[name] = ic
    return ic
