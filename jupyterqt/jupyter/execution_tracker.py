from jupyterqt.models.cell_model import CellModel


class ExecutionTracker:
    def __init__(self):
        # msg_id -> (cell_model, notebook_id)
        self._pending: dict[str, tuple[CellModel, str]] = {}

    def register(self, msg_id: str, cell: CellModel, notebook_id: str) -> None:
        self._pending[msg_id] = (cell, notebook_id)

    def resolve(self, msg_id: str) -> tuple[CellModel, str] | None:
        return self._pending.get(msg_id)

    def cancel(self, msg_id: str) -> None:
        self._pending.pop(msg_id, None)

    def cancel_all_for_notebook(self, notebook_id: str) -> list[str]:
        to_remove = [mid for mid, (_, nid) in self._pending.items()
                     if nid == notebook_id]
        for mid in to_remove:
            del self._pending[mid]
        return to_remove

    def pending_msg_ids(self) -> list[str]:
        return list(self._pending.keys())
