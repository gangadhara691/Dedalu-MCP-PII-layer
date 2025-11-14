"""
Stateless MCP adapter that proxies sanitize/rehydrate requests to the judge service.
"""

from __future__ import annotations

import json
import os

import httpx
from dedalus.sdk import ToolServer, run_server, tool


class PIIProxyTools(ToolServer):
    base_url = os.getenv("JUDGE_URL", "http://127.0.0.1:9000")

    @tool
    async def sanitize(self, session_id: str, text: str) -> str:
        """Forward sanitize requests to the judge service."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/ingest",
                json={"session_id": session_id, "user_prompt": text},
                timeout=60,
            )
            response.raise_for_status()
        data = response.json()
        return json.dumps(data)

    @tool
    async def rehydrate(self, session_id: str, text: str) -> str:
        """Forward rehydrate requests to the judge service."""
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
