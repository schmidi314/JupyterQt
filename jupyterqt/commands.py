from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Command:
    context: str
    command: str
    argument_names: list
    argument_types: list
    callback: Callable


class CommandRegistry:
    """Singleton registry of named, typed commands organised by context."""

    _instance: "CommandRegistry | None" = None

    def __init__(self) -> None:
        # (context, command) → Command
        self._commands: dict[tuple[str, str], Command] = {}

    @classmethod
    def instance(cls) -> "CommandRegistry":
        if cls._instance is None:
            cls._instance = CommandRegistry()
        return cls._instance

    # ------------------------------------------------------------------ registration

    def register(self, context: str, command: str,
                 argument_names: list, argument_types: list,
                 callback: Callable) -> None:
        """Register or replace a command."""
        self._commands[(context, command)] = Command(
            context, command, argument_names, argument_types, callback
        )

    def unregister(self, context: str, command: str) -> None:
        """Remove a single command; silently ignored if not found."""
        self._commands.pop((context, command), None)

    def unregister_context(self, context: str) -> None:
        """Remove all commands for a given context (e.g. on notebook close)."""
        keys = [k for k in self._commands if k[0] == context]
        for k in keys:
            del self._commands[k]

    # ------------------------------------------------------------------ lookup

    def get(self, context: str, command: str) -> Command | None:
        return self._commands.get((context, command))

    def commands_for_context(self, context: str) -> list[Command]:
        return [c for c in self._commands.values() if c.context == context]

    def all_commands(self) -> list[Command]:
        return list(self._commands.values())

    # ------------------------------------------------------------------ execution

    def execute(self, context: str, command: str, *args) -> None:
        """Look up and call the command, passing *args to the callback."""
        cmd = self.get(context, command)
        if cmd is None:
            raise KeyError(f"No command registered for '{context}/{command}'")
        cmd.callback(*args)
