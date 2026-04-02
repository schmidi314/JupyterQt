from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    base_url: str = "http://localhost:8888"
    token: str = ""

    @property
    def ws_base_url(self) -> str:
        return self.base_url.replace("http://", "ws://").replace("https://", "wss://")

    @property
    def headers(self) -> dict:
        return {"Authorization": f"token {self.token}"}
