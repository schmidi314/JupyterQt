import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _newMsgId() -> str:
    return str(uuid.uuid4())


def _nowIso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JupyterMessage:
    msg_id: str
    msg_type: str
    session: str
    username: str
    date: str
    parent_header: dict
    metadata: dict
    content: dict
    channel: str
    version: str = "5.3"

    @staticmethod
    def create(msg_type: str, content: dict, session: str,
               channel: str = "shell", username: str = "jupyterqt",
               parent_header: dict | None = None) -> "JupyterMessage":
        return JupyterMessage(
            msg_id=_newMsgId(),
            msg_type=msg_type,
            session=session,
            username=username,
            date=_nowIso(),
            parent_header=parent_header or {},
            metadata={},
            content=content,
            channel=channel,
        )

    def toDict(self) -> dict:
        return {
            "header": {
                "msg_id": self.msg_id,
                "msg_type": self.msg_type,
                "session": self.session,
                "username": self.username,
                "date": self.date,
                "version": self.version,
            },
            "parent_header": self.parent_header,
            "metadata": self.metadata,
            "content": self.content,
            "channel": self.channel,
            "buffers": [],
        }

    @staticmethod
    def fromDict(data: dict) -> "JupyterMessage":
        header = data.get("header", {})
        return JupyterMessage(
            msg_id=header.get("msg_id", ""),
            msg_type=header.get("msg_type", ""),
            session=header.get("session", ""),
            username=header.get("username", ""),
            date=header.get("date", ""),
            parent_header=data.get("parent_header", {}),
            metadata=data.get("metadata", {}),
            content=data.get("content", {}),
            channel=data.get("channel", ""),
            version=header.get("version", "5.3"),
        )
