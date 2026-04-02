from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class RestWorker(QRunnable):
    # Class-level set keeps Python wrappers alive until run() completes.
    # Without this, Python GC can destroy the wrapper (and its .signals)
    # while the C++ QRunnable is still running in the thread pool.
    _registry: set = set()

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        RestWorker._registry.add(self)
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            RestWorker._registry.discard(self)
