import uuid
from dataclasses import dataclass, field

from jupyterqt.models.cell_model import CellModel, CellType


@dataclass
class NotebookModel:
    notebookId: str
    path: str
    cells: list[CellModel]
    kernel_id: str | None = None
    kernel_name: str = "python3"
    metadata: dict = field(default_factory=dict)
    nbformat: int = 4
    nbformat_minor: int = 5

    @staticmethod
    def fromIpynbDict(path: str, data: dict) -> "NotebookModel":
        cells = [CellModel.fromIpynbCell(c) for c in data.get("cells", [])]
        if not cells:
            cells = [CellModel.new(CellType.CODE)]
        metadata = data.get("metadata", {})
        kernel_name = metadata.get("kernelspec", {}).get("name", "python3")
        return NotebookModel(
            notebookId=str(uuid.uuid4()),
            path=path,
            cells=cells,
            metadata=metadata,
            kernel_name=kernel_name,
            nbformat=data.get("nbformat", 4),
            nbformat_minor=data.get("nbformat_minor", 5),
        )

    def toIpynbDict(self) -> dict:
        return {
            "nbformat": self.nbformat,
            "nbformat_minor": self.nbformat_minor,
            "metadata": self.metadata,
            "cells": [c.toIpynbCell() for c in self.cells],
        }

    def getCell(self, cellId: str) -> CellModel | None:
        for c in self.cells:
            if c.cellId == cellId:
                return c
        return None

    def addCell(self, cell_type: CellType = CellType.CODE,
                 index: int | None = None) -> CellModel:
        cell = CellModel.new(cell_type)
        if index is None:
            self.cells.append(cell)
        else:
            self.cells.insert(index, cell)
        return cell

    def removeCell(self, cellId: str) -> None:
        self.cells = [c for c in self.cells if c.cellId != cellId]

    def moveCell(self, cellId: str, new_index: int) -> None:
        cell = self.getCell(cellId)
        if cell is None:
            return
        self.cells.remove(cell)
        self.cells.insert(new_index, cell)

    def indexOf(self, cellId: str) -> int:
        for i, c in enumerate(self.cells):
            if c.cellId == cellId:
                return i
        return -1
