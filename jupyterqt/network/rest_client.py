import requests

from jupyterqt.config import ServerConfig


class RestClient:
    def __init__(self, config: ServerConfig):
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(config.headers)
        self._fetchXsrf()

    def updateConfig(self, config: ServerConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(config.headers)
        self._fetchXsrf()

    def _fetchXsrf(self) -> None:
        """GET /login to obtain the _xsrf cookie required for mutating requests."""
        try:
            self._session.get(f"{self._config.base_url}/login", timeout=5)
        except Exception:
            pass

    def _xsrfHeaders(self) -> dict:
        """Return X-XSRFToken header if we have the cookie, else empty dict."""
        token = self._session.cookies.get("_xsrf", "")
        return {"X-XSRFToken": token} if token else {}

    # ---------- Notebooks ----------

    def listContents(self, path: str = "") -> dict:
        url = f"{self._config.base_url}/api/contents/{path}"
        r = self._session.get(url, timeout=15)
        r.raise_for_status()
        return r.json()

    def getNotebook(self, path: str) -> dict:
        url = f"{self._config.base_url}/api/contents/{path}"
        r = self._session.get(url, params={"type": "notebook"}, timeout=30)
        r.raise_for_status()
        return r.json()

    def saveNotebook(self, path: str, content: dict) -> None:
        url = f"{self._config.base_url}/api/contents/{path}"
        payload = {"type": "notebook", "content": content}
        r = self._session.put(url, json=payload, timeout=30,
                              headers=self._xsrfHeaders())
        r.raise_for_status()

    def createDirectory(self, path: str) -> dict:
        """Create a new directory; path is the full path including the new dir name."""
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        url = f"{self._config.base_url}/api/contents/{parent}"
        r = self._session.post(url, json={"type": "directory"}, timeout=15,
                               headers=self._xsrfHeaders())
        r.raise_for_status()
        result = r.json()
        # Rename from Untitled Folder to the requested name if needed
        new_name = path.rsplit("/", 1)[-1]
        if result.get("name") != new_name:
            self.renameFile(result["path"], path)
        return result

    def renameFile(self, old_path: str, new_path: str) -> dict:
        url = f"{self._config.base_url}/api/contents/{old_path}"
        r = self._session.patch(url, json={"path": new_path}, timeout=15,
                                headers=self._xsrfHeaders())
        r.raise_for_status()
        return r.json()

    def deleteFile(self, path: str) -> None:
        url = f"{self._config.base_url}/api/contents/{path}"
        r = self._session.delete(url, timeout=15, headers=self._xsrfHeaders())
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()

    def copyFile(self, path: str) -> dict:
        """Duplicate a file into the same directory."""
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        url = f"{self._config.base_url}/api/contents/{parent}"
        r = self._session.post(url, json={"copy_from": path}, timeout=15,
                               headers=self._xsrfHeaders())
        r.raise_for_status()
        return r.json()

    def createNotebook(self, path: str = "") -> dict:
        url = f"{self._config.base_url}/api/contents/{path}"
        r = self._session.post(url, json={"type": "notebook"}, timeout=15,
                               headers=self._xsrfHeaders())
        r.raise_for_status()
        return r.json()

    # ---------- Kernels ----------

    def listKernels(self) -> list[dict]:
        url = f"{self._config.base_url}/api/kernels"
        r = self._session.get(url, timeout=10)
        r.raise_for_status()
        return r.json()

    def startKernel(self, kernel_name: str = "python3") -> dict:
        url = f"{self._config.base_url}/api/kernels"
        r = self._session.post(url, json={"name": kernel_name}, timeout=30,
                               headers=self._xsrfHeaders())
        r.raise_for_status()
        return r.json()

    def shutdownKernel(self, kernel_id: str) -> None:
        url = f"{self._config.base_url}/api/kernels/{kernel_id}"
        r = self._session.delete(url, timeout=10, headers=self._xsrfHeaders())
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()

    def restartKernel(self, kernel_id: str) -> dict:
        url = f"{self._config.base_url}/api/kernels/{kernel_id}/restart"
        r = self._session.post(url, timeout=30, headers=self._xsrfHeaders())
        r.raise_for_status()
        return r.json()

    def interruptKernel(self, kernel_id: str) -> None:
        url = f"{self._config.base_url}/api/kernels/{kernel_id}/interrupt"
        r = self._session.post(url, timeout=10, headers=self._xsrfHeaders())
        r.raise_for_status()

    def getKernel(self, kernel_id: str) -> dict:
        url = f"{self._config.base_url}/api/kernels/{kernel_id}"
        r = self._session.get(url, timeout=10)
        r.raise_for_status()
        return r.json()

    # ---------- Sessions ----------

    def listSessions(self) -> list[dict]:
        url = f"{self._config.base_url}/api/sessions"
        r = self._session.get(url, timeout=10)
        r.raise_for_status()
        return r.json()

    def getServerInfo(self) -> dict:
        url = f"{self._config.base_url}/api"
        r = self._session.get(url, timeout=5)
        r.raise_for_status()
        return r.json()

    def checkServer(self) -> str:
        """Returns 'ok', 'unauthorized', or an error message string."""
        try:
            url = f"{self._config.base_url}/api"
            r = self._session.get(url, timeout=5)
            if r.status_code == 200:
                return "ok"
            elif r.status_code in (401, 403):
                return "unauthorized"
            else:
                return f"HTTP {r.status_code}"
        except Exception as e:
            return f"error: {e}"
