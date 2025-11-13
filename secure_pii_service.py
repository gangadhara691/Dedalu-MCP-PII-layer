"""
Secure, stateful FastAPI service that masks PII and stores mappings per session.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# In-memory session storage: {session_id: {placeholder: real_value}}
pii_maps: Dict[str, Dict[str, str]] = {}


class SanitizeRequest(BaseModel):
    session_id: str
    text: str


class SanitizeResponse(BaseModel):
    session_id: str
    masked_text: str
    replacements: Dict[str, str]


class RehydrateRequest(BaseModel):
    session_id: str
    text: str


class RehydrateResponse(BaseModel):
    session_id: str
    rehydrated_text: str


def find_and_mask_pii(session_id: str, text: str) -> Tuple[str, Dict[str, str]]:
    """
    Demonstration-only PII masking helper.

    Detects simple Firstname Lastname strings, swaps them with placeholders,
    and updates the per-session mapping.
    """
    session_map = pii_maps.get(session_id, {})
    reverse_map = {real: placeholder for placeholder, real in session_map.items()}

    person_pattern = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")
    matches = person_pattern.findall(text)

    replacements: Dict[str, str] = {}
    person_to_placeholder: Dict[str, str] = {}
    next_index = len(session_map) + 1

    for match in matches:
        if match in person_to_placeholder:
            continue
        if match in reverse_map:
            placeholder = reverse_map[match]
        else:
            placeholder = f"[PERSON_{next_index}]"
            next_index += 1
            session_map[placeholder] = match
            replacements[placeholder] = match
        person_to_placeholder[match] = placeholder

    def _replace(match_obj: re.Match[str]) -> str:
        full = match_obj.group(0)
        return person_to_placeholder.get(full, full)

    masked_text = person_pattern.sub(_replace, text)
    pii_maps[session_id] = session_map
    return masked_text, replacements


app = FastAPI(title="Secure PII Vault", version="0.1.0")


@app.post("/sanitize", response_model=SanitizeResponse)
def sanitize(payload: SanitizeRequest) -> SanitizeResponse:
    masked_text, replacements = find_and_mask_pii(payload.session_id, payload.text)
    return SanitizeResponse(
        session_id=payload.session_id,
        masked_text=masked_text,
        replacements=replacements,
    )


@app.post("/rehydrate", response_model=RehydrateResponse)
def rehydrate(payload: RehydrateRequest) -> RehydrateResponse:
    mapping = pii_maps.get(payload.session_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    rehydrated = payload.text
    for placeholder, real_value in mapping.items():
        rehydrated = rehydrated.replace(placeholder, real_value)

    return RehydrateResponse(session_id=payload.session_id, rehydrated_text=rehydrated)


if __name__ == "__main__":
    uvicorn.run("secure_pii_service:app", host="127.0.0.1", port=8000, reload=False)
