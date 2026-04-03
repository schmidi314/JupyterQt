from jupyterqt.models.cell_model import CellModel


class ExecutionTracker:
    def __init__(self):
        # msg_id -> (cell_model, notebookId)
        self._pending: dict[str, tuple[CellModel, str]] = {}

    def register(self, msg_id: str, cell: CellModel, notebookId: str) -> None:
        self._pending[msg_id] = (cell, notebookId)

    def resolve(self, msg_id: str) -> tuple[CellModel, str] | None:
        return self._pending.get(msg_id)

    def cancel(self, msg_id: str) -> None:
        self._pending.pop(msg_id, None)

    def cancelAllForNotebook(self, notebookId: str) -> list[str]:
        to_remove = [mid for mid, (_, nid) in self._pending.items()
                     if nid == notebookId]
        for mid in to_remove:
            del self._pending[mid]
        return to_remove

    def pendingMsgIds(self) -> list[str]:
        return list(self._pending.keys())
