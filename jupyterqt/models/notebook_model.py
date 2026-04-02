import uuid
from dataclasses import dataclass, field

from jupyterqt.models.cell_model import CellModel, CellType


@dataclass
class NotebookModel:
    notebook_id: str
    path: str
    cells: list[CellModel]
    kernel_id: str | None = None
    kernel_name: str = "python3"
    metadata: dict = field(default_factory=dict)
    nbformat: int = 4
    nbformat_minor: int = 5

    @staticmethod
    def from_ipynb_dict(path: str, data: dict) -> "NotebookModel":
        cells = [CellModel.from_ipynb_cell(c) for c in data.get("cells", [])]
        if not cells:
            cells = [CellModel.new(CellType.CODE)]
        metadata = data.get("metadata", {})
        kernel_name = metadata.get("kernelspec", {}).get("name", "python3")
        return NotebookModel(
            notebook_id=str(uuid.uuid4()),
            path=path,
            cells=cells,
            metadata=metadata,
            kernel_name=kernel_name,
            nbformat=data.get("nbformat", 4),
            nbformat_minor=data.get("nbformat_minor", 5),
        )

    def to_ipynb_dict(self) -> dict:
        return {
            "nbformat": self.nbformat,
            "nbformat_minor": self.nbformat_minor,
            "metadata": self.metadata,
            "cells": [c.to_ipynb_cell() for c in self.cells],
        }

    def get_cell(self, cell_id: str) -> CellModel | None:
        for c in self.cells:
            if c.cell_id == cell_id:
                return c
        return None

    def add_cell(self, cell_type: CellType = CellType.CODE,
                 index: int | None = None) -> CellModel:
        cell = CellModel.new(cell_type)
        if index is None:
            self.cells.append(cell)
        else:
            self.cells.insert(index, cell)
        return cell

    def remove_cell(self, cell_id: str) -> None:
        self.cells = [c for c in self.cells if c.cell_id != cell_id]

    def move_cell(self, cell_id: str, new_index: int) -> None:
        cell = self.get_cell(cell_id)
        if cell is None:
            return
        self.cells.remove(cell)
        self.cells.insert(new_index, cell)

    def index_of(self, cell_id: str) -> int:
        for i, c in enumerate(self.cells):
            if c.cell_id == cell_id:
                return i
        return -1
