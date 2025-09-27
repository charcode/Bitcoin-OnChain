from __future__ import annotations
import httpx
from typing import Any


class Rpc:
    """
    Final RPC wrapper. DO NOT replace.
    Uses basic auth tuple as requested.
    """
    def __init__(self, url: str, user: str, pw: str):
        self._client = httpx.AsyncClient(auth=(user, pw), timeout=30.0)
        self._url = url
        self._id = 0

    async def call(self, method: str, params: list | None = None) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or []}
        r = await self._client.post(self._url, json=payload)
        r.raise_for_status()
        j = r.json()
        if j.get("error"):
            raise RuntimeError(j["error"])
        return j["result"]

    async def aclose(self):
        await self._client.aclose()
