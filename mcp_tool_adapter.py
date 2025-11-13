"""
Stateless MCP adapter that proxies sanitize/rehydrate requests to the secure PII service.
"""

from __future__ import annotations

import httpx
from dedalus.sdk import ToolServer, run_server, tool


class PIIProxyTools(ToolServer):
    base_url = "http://127.0.0.1:8000"

    @tool
    async def sanitize(self, session_id: str, text: str) -> str:
        """Forward sanitize requests to the secure PII service."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sanitize",
                json={"session_id": session_id, "text": text},
                timeout=30,
            )
            response.raise_for_status()
        data = response.json()
        return data["masked_text"]

    @tool
    async def rehydrate(self, session_id: str, text: str) -> str:
        """Forward rehydrate requests to the secure PII service."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rehydrate",
                json={"session_id": session_id, "text": text},
                timeout=30,
            )
            response.raise_for_status()
        data = response.json()
        return data["rehydrated_text"]


if __name__ == "__main__":
    run_server(PIIProxyTools())
