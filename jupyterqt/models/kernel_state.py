import enum

from PySide6.QtCore import QObject, Signal


class KernelStatus(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    BUSY = "busy"
    RESTARTING = "restarting"
    ERROR = "error"


_VALID_TRANSITIONS: dict[KernelStatus, set[KernelStatus]] = {
    KernelStatus.DISCONNECTED: {KernelStatus.CONNECTING, KernelStatus.ERROR},
    KernelStatus.CONNECTING:   {KernelStatus.IDLE, KernelStatus.ERROR, KernelStatus.DISCONNECTED},
    KernelStatus.IDLE:         {KernelStatus.BUSY, KernelStatus.RESTARTING, KernelStatus.DISCONNECTED, KernelStatus.ERROR},
    KernelStatus.BUSY:         {KernelStatus.IDLE, KernelStatus.RESTARTING, KernelStatus.DISCONNECTED, KernelStatus.ERROR},
    KernelStatus.RESTARTING:   {KernelStatus.IDLE, KernelStatus.DISCONNECTED, KernelStatus.ERROR},
    KernelStatus.ERROR:        {KernelStatus.CONNECTING, KernelStatus.DISCONNECTED},
}


class KernelStateMachine(QObject):
    status_changed = Signal(object)   # KernelStatus

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = KernelStatus.DISCONNECTED

    @property
    def current(self) -> KernelStatus:
        return self._current

    def transition(self, new_status: KernelStatus) -> bool:
        allowed = _VALID_TRANSITIONS.get(self._current, set())
        if new_status not in allowed:
            return False
        self._current = new_status
        self.status_changed.emit(new_status)
        return True

    def force_transition(self, new_status: KernelStatus) -> None:
        self._current = new_status
        self.status_changed.emit(new_status)
