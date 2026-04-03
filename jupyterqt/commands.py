from dataclasses import dataclass, field
from typing import Callable


# ── shortcut string format ─────────────────────────────────────────────────────────────────────────────────────────
# Modifiers (in order): ctrl, alt, shift, meta — separated by underscore, followed by the key name.
# Examples: "ctrl_s", "ctrl_shift_x", "alt_a", "b", "f5", "ctrl_f1", "escape"
# Valid keys: a-z, 0-9, f1-f12, return, enter, escape, space, tab, backspace, delete

_VALID_MODIFIERS = {'ctrl', 'alt', 'shift', 'meta'}
_VALID_KEYS = (
    set('abcdefghijklmnopqrstuvwxyz0123456789') |
    {f'f{i}' for i in range(1, 13)} |
    {'return', 'enter', 'escape', 'space', 'tab', 'backspace', 'delete'}
)


def _validate_shortcut(s: str) -> None:
    parts = s.split('_')
    key = parts[-1]
    modifiers = parts[:-1]
    for mod in modifiers:
        if mod not in _VALID_MODIFIERS:
            raise ValueError(f"Invalid modifier {mod!r} in shortcut {s!r} (valid: {sorted(_VALID_MODIFIERS)})")
    if key not in _VALID_KEYS:
        raise ValueError(f"Invalid key {key!r} in shortcut {s!r}")


def _shortcut_string_from_key_event(key_press_event) -> str | None:
    """Convert a QKeyEvent to a shortcut string (e.g. 'ctrl_shift_a', 'f5', 'escape'). Returns None for unrecognised keys."""
    from PySide6.QtCore import Qt
    mods = key_press_event.modifiers()
    key = key_press_event.key()

    parts = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append('ctrl')
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append('alt')
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append('shift')
    if mods & Qt.KeyboardModifier.MetaModifier:
        parts.append('meta')

    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        parts.append(chr(key).lower())
    elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        parts.append(chr(key))
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
        parts.append(f'f{key - Qt.Key.Key_F1 + 1}')
    else:
        _SPECIAL = {
            Qt.Key.Key_Return:    'return',
            Qt.Key.Key_Enter:     'enter',
            Qt.Key.Key_Escape:    'escape',
            Qt.Key.Key_Space:     'space',
            Qt.Key.Key_Tab:       'tab',
            Qt.Key.Key_Backspace: 'backspace',
            Qt.Key.Key_Delete:    'delete',
        }
        key_str = _SPECIAL.get(key)
        if key_str is None:
            return None
        parts.append(key_str)

    return '_'.join(parts)


@dataclass(frozen=True)
class Command:
    context: str
    command: str
    argument_names: list
    argument_types: list
    callback: Callable


@dataclass(frozen=True)
class KeyboardShortcut:
    context: str
    command: str
    actual_shortcut: str | None = field(default=None)
    default_shortcut: str | None = field(default=None)
    arguments: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.actual_shortcut is not None:
            _validate_shortcut(self.actual_shortcut)
        if self.default_shortcut is not None:
            _validate_shortcut(self.default_shortcut)

    @property
    def effective_shortcut(self) -> str | None:
        return self.actual_shortcut if self.actual_shortcut is not None else self.default_shortcut


class CommandRegistry:
    """Singleton registry of named, typed commands organised by context."""

    _instance: "CommandRegistry | None" = None

    def __init__(self) -> None:
        # (context, command) → Command
        self._commands: dict[tuple[str, str], Command] = {}
        # effective_shortcut_string → KeyboardShortcut
        self._keyboard_shortcuts: dict[str, KeyboardShortcut] = {}

    @classmethod
    def instance(cls) -> "CommandRegistry":
        if cls._instance is None:
            cls._instance = CommandRegistry()
        return cls._instance

    # #########################################################################################################################################
    # Registration

    def register(self, context: str, command: str, argument_names: list, argument_types: list, callback: Callable, default_keyboard_shortcut: str | None = None) -> None:
        """Register or replace a command."""
        self._commands[(context, command)] = Command(context, command, argument_names, argument_types, callback)
        if default_keyboard_shortcut is not None:
            self.addKeyboardShortcut(context, command, default_keyboard_shortcut)

    def unregister(self, context: str, command: str) -> None:
        """Remove a single command; silently ignored if not found."""
        self._commands.pop((context, command), None)

    def unregisterContext(self, context: str) -> None:
        """Remove all commands for a given context (e.g. on notebook close)."""
        keys = [k for k in self._commands if k[0] == context]
        for k in keys:
            del self._commands[k]

    def addKeyboardShortcut(self, context: str, command: str, shortcut: str) -> None:
        """Set (or replace) the default shortcut for a command."""
        _validate_shortcut(shortcut)
        # Remove any existing entry for this context/command
        existing = next((ks for ks in self._keyboard_shortcuts.values()
                         if ks.context == context and ks.command == command), None)
        if existing is not None:
            old_eff = existing.effective_shortcut
            if old_eff:
                self._keyboard_shortcuts.pop(old_eff, None)
            new_ks = KeyboardShortcut(context, command, existing.actual_shortcut, shortcut, list(existing.arguments))
        else:
            new_ks = KeyboardShortcut(context, command, default_shortcut=shortcut)
        eff = new_ks.effective_shortcut
        if eff:
            self._keyboard_shortcuts[eff] = new_ks

    # #########################################################################################################################################
    # Lookup

    def get(self, context: str, command: str) -> Command | None:
        return self._commands.get((context, command))

    def commandsForContext(self, context: str) -> list[Command]:
        return [c for c in self._commands.values() if c.context == context]

    def allCommands(self) -> list[Command]:
        return list(self._commands.values())

    # #########################################################################################################################################
    # Execution

    def tryToExecuteKeyboardShortcut(self, key_press_event, mod_filter: tuple|None=None) -> bool:
        """Generate a shortcut string from a QKeyEvent, look it up and execute. Returns True if handled.

        mod_filter may be a tuple (norm, mods_list)
          - allowed norms: 'at least one of', 'all of'
        """
        shortcut_str = _shortcut_string_from_key_event(key_press_event)
        if shortcut_str is None:
            return False

        if mod_filter is not None:
            norm, mods_list = mod_filter
            if norm == 'at least one of':
                shortcut_applies_to_filter = any([mod in shortcut_str for mod in mods_list])
            elif norm == 'all of':
                shortcut_applies_to_filter = any([mod in shortcut_str for mod in mods_list])
            else:
                raise ValueError(f'{norm} not supported')
            if not shortcut_applies_to_filter:
                return False

        ks = self._keyboard_shortcuts.get(shortcut_str)
        if ks is None:
            return False

        try:
            self.execute(ks.context, ks.command, *ks.arguments)
        except KeyError:
            return False

        return True

    def execute(self, context: str, command: str, *args) -> None:
        """Look up and call the command, passing *args to the callback."""
        cmd = self.get(context, command)
        if cmd is None:
            raise KeyError(f"No command registered for '{context}/{command}'")
        cmd.callback(*args)
