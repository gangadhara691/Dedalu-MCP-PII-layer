"""
FastAPI service representing the quarantined "judge" LLM layer.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:  # pragma: no cover
    from .liquidai_pii import ExtractionResult, LiquidAIPIIExtractor
except ImportError:  # pragma: no cover
    from liquidai_pii import ExtractionResult, LiquidAIPIIExtractor  # type: ignore


# Simple heuristic patterns to simulate threat detection.
SUSPICIOUS_PATTERNS = (
    "ignore all previous",
    "disable security",
    "format the drive",
    "exfiltrate",
    "upload credentials",
)


def vet_prompt(prompt: str) -> Tuple[bool, str]:
    lowered = prompt.lower()
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in lowered:
            return False, f"Prompt rejected: matched '{pattern}'."
    return True, "Allowed"


class IngestRequest(BaseModel):
    session_id: str
    user_prompt: str
    task_hint: str | None = None


class IngestResponse(BaseModel):
    session_id: str
    is_allowed: bool
    reason: str
    sanitized_command: str
    masked_text: str
    replacements: List[Dict[str, str]]


class RehydrateRequest(BaseModel):
    session_id: str
    text: str


class RehydrateResponse(BaseModel):
    session_id: str
    rehydrated_text: str


app = FastAPI(title="Judge LLM Service", version="0.1.0")


class JudgeState:
    def __init__(self) -> None:
        backend = os.getenv("PII_BACKEND", "offline")
        self.extractor = LiquidAIPIIExtractor(backend=backend)
        self.sessions: Dict[str, ExtractionResult] = {}

    def evaluate(self, session_id: str, prompt: str, hint: str | None = None) -> IngestResponse:
        allowed, reason = vet_prompt(prompt)
        sanitized_command = prompt.strip() if allowed else ""

        if allowed:
            result = self.extractor.extract(prompt)
            self.sessions[session_id] = result
            masked_text = result.masked_text
            replacements = result.replacements
        else:
            masked_text = ""
            replacements = []

        return IngestResponse(
            session_id=session_id,
            is_allowed=allowed,
            reason=reason,
            sanitized_command=sanitized_command,
            masked_text=masked_text,
            replacements=replacements,
        )

    def rehydrate(self, session_id: str, text: str) -> str:
        result = self.sessions.get(session_id)
        if not result:
            raise KeyError("Unknown session")
        rehydrated = text
        for record in result.replacements:
            placeholder = record["placeholder"]
            value = record["value"]
            rehydrated = rehydrated.replace(placeholder, value)
        return rehydrated


state = JudgeState()


@app.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest) -> IngestResponse:
    return state.evaluate(payload.session_id, payload.user_prompt, payload.task_hint)


@app.post("/rehydrate", response_model=RehydrateResponse)
def rehydrate(payload: RehydrateRequest) -> RehydrateResponse:
    try:
        text = state.rehydrate(payload.session_id, payload.text)
        return RehydrateResponse(session_id=payload.session_id, rehydrated_text=text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
