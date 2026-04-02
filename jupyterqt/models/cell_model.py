import enum
import uuid
from dataclasses import dataclass, field


class CellType(enum.Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    RAW = "raw"


@dataclass
class OutputItem:
    output_type: str        # "stream", "display_data", "execute_result", "error"
    data: dict = field(default_factory=dict)   # MIME bundle
    metadata: dict = field(default_factory=dict)
    text: str | None = None              # for stream outputs
    execution_count: int | None = None   # for execute_result


@dataclass
class CellModel:
    cell_id: str
    cell_type: CellType
    source: str
    outputs: list[OutputItem] = field(default_factory=list)
    execution_count: int | None = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def new(cell_type: CellType = CellType.CODE) -> "CellModel":
        return CellModel(
            cell_id=str(uuid.uuid4()),
            cell_type=cell_type,
            source="",
        )

    @staticmethod
    def from_ipynb_cell(data: dict) -> "CellModel":
        cell_type = CellType(data.get("cell_type", "code"))
        source = data.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        outputs = []
        for o in data.get("outputs", []):
            otype = o.get("output_type", "")
            if otype == "stream":
                text = o.get("text", "")
                if isinstance(text, list):
                    text = "".join(text)
                outputs.append(OutputItem(output_type="stream", text=text,
                                          data={"text/plain": text},
                                          metadata=o.get("metadata", {})))
            elif otype in ("display_data", "execute_result"):
                outputs.append(OutputItem(
                    output_type=otype,
                    data=o.get("data", {}),
                    metadata=o.get("metadata", {}),
                    execution_count=o.get("execution_count"),
                ))
            elif otype == "error":
                tb = o.get("traceback", [])
                outputs.append(OutputItem(
                    output_type="error",
                    data={"ename": o.get("ename", ""), "evalue": o.get("evalue", ""),
                          "traceback": tb},
                    metadata={},
                ))

        cell_id = data.get("id", str(uuid.uuid4()))
        return CellModel(
            cell_id=cell_id,
            cell_type=cell_type,
            source=source,
            outputs=outputs,
            execution_count=data.get("execution_count"),
            metadata=data.get("metadata", {}),
        )

    def to_ipynb_cell(self) -> dict:
        d: dict = {
            "id": self.cell_id,
            "cell_type": self.cell_type.value,
            "source": self.source,
            "metadata": self.metadata,
        }
        if self.cell_type == CellType.CODE:
            d["execution_count"] = self.execution_count
            d["outputs"] = [self._output_to_dict(o) for o in self.outputs]
        return d

    def _output_to_dict(self, o: OutputItem) -> dict:
        if o.output_type == "stream":
            return {"output_type": "stream", "name": "stdout",
                    "text": o.text or "", "metadata": o.metadata}
        elif o.output_type in ("display_data", "execute_result"):
            d = {"output_type": o.output_type, "data": o.data, "metadata": o.metadata}
            if o.output_type == "execute_result":
                d["execution_count"] = o.execution_count
            return d
        elif o.output_type == "error":
            return {
                "output_type": "error",
                "ename": o.data.get("ename", ""),
                "evalue": o.data.get("evalue", ""),
                "traceback": o.data.get("traceback", []),
            }
        return {"output_type": o.output_type}
