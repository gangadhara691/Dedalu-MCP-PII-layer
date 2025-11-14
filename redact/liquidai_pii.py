"""
Liquid AI PII extraction helpers built around the Hugging Face inference API.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import re
import requests


DEFAULT_ENTITIES: Sequence[str] = (
    "address",
    "company_name",
    "email_address",
    "human_name",
    "phone_number",
)


def _alphabetical_entities(entities: Iterable[str]) -> Tuple[str, ...]:
    normalized = sorted({e.strip() for e in entities if e.strip()})
    return tuple(normalized)


@dataclass
class ExtractionResult:
    raw_json: Dict[str, List[str]]
    masked_text: str
    replacements: List[Dict[str, str]]


class LiquidAIPIIExtractor:
    """
    Wrapper for the LiquidAI LFM2 PII models hosted on Hugging Face.

    The extractor streams prompts through the Hugging Face InferenceClient
    (no local weights required) and returns parsed JSON plus a masked version
    of the original text that can be piped back into downstream systems.
    """

    def __init__(
        self,
        model_name: str = "LiquidAI/LFM2-350M-PII-Extract-JP",
        entities: Sequence[str] = DEFAULT_ENTITIES,
        *,
        hf_token: Optional[str] = None,
        backend: str = "remote",
        max_new_tokens: int = 256,
    ) -> None:
        self.model_name = model_name
        self.entities = _alphabetical_entities(entities)
        self.system_prompt = "Extract " + ", ".join(f"<{entity}>" for entity in self.entities)
        self.backend = backend
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.endpoint_url = os.getenv("HF_ENDPOINT")
        if self.backend == "remote":
            if not self.hf_token:
                raise ValueError(
                    "LiquidAIPIIExtractor needs a Hugging Face token. "
                    "Pass --hf-token or set the HF_TOKEN env var."
                )
            if not self.endpoint_url:
                raise ValueError("Set HF_ENDPOINT to your Hugging Face Inference Endpoint URL.")
        elif self.backend != "offline":
            raise ValueError(f"Unknown backend '{backend}'")
        else:
            self.endpoint_url = None
        self.max_new_tokens = max_new_tokens

    def _build_prompt(self, text: str) -> str:
        clean_text = text.strip()
        return (
            "<|startoftext|><|im_start|>system\n"
            f"{self.system_prompt}<|im_end|>\n"
            "<|im_start|>user\n"
            f"{clean_text}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    def _parse_json(self, generation: str) -> Dict[str, List[str]]:
        if not generation:
            return {entity: [] for entity in self.entities}
        start = generation.find("{")
        end = generation.rfind("}")
        if start == -1 or end == -1:
            return {entity: [] for entity in self.entities}
        snippet = generation[start : end + 1]
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError:
            return {entity: [] for entity in self.entities}
        normalized: Dict[str, List[str]] = {}
        for entity in self.entities:
            values = parsed.get(entity, [])
            if isinstance(values, list):
                normalized[entity] = [str(v) for v in values if isinstance(v, str)]
            else:
                normalized[entity] = []
        return normalized

    def _mask_text(self, text: str, entities: Dict[str, List[str]]) -> Tuple[str, List[Dict[str, str]]]:
        masked = text
        replacements: List[Dict[str, str]] = []
        counter = 1
        # Replace longer spans first to avoid clobbering substrings.
        spans: List[Tuple[str, str]] = []
        for category, values in entities.items():
            for value in values:
                spans.append((category, value))
        spans.sort(key=lambda item: len(item[1]), reverse=True)

        for category, value in spans:
            placeholder = f"[{category.upper()}_{counter}]"
            if value:
                masked = masked.replace(value, placeholder)
                replacements.append(
                    {"category": category, "value": value, "placeholder": placeholder}
                )
                counter += 1
        return masked, replacements

    def extract(self, text: str) -> ExtractionResult:
        if self.backend == "offline":
            parsed = {entity: [] for entity in self.entities}
            email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
            phone_pattern = re.compile(r"\+?\d[\d\-]{6,}\d")
            parsed["email_address"] = email_pattern.findall(text)
            parsed["phone_number"] = phone_pattern.findall(text)
            masked_text, replacements = self._mask_text(text, parsed)
            return ExtractionResult(raw_json=parsed, masked_text=masked_text, replacements=replacements)

        if self.backend != "remote":
            raise RuntimeError("PII extraction backend is offline; provide a remote backend to run inference.")

        prompt = self._build_prompt(text)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": self.max_new_tokens,
                "temperature": 0.1,
                "stop": ["<|im_end|>"],
            },
        }
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                self.endpoint_url,
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - depends on HF availability
            raise RuntimeError(
                "Failed to call Hugging Face Inference API. "
                "Confirm your HF_TOKEN/HF_ENDPOINT are valid and the endpoint is running."
            ) from exc

        data = response.json()
        if isinstance(data, list):
            generation = data[0].get("generated_text", "")
        elif isinstance(data, dict):
            generation = data.get("generated_text", "")
        else:
            generation = ""
        parsed = self._parse_json(generation)
        masked_text, replacements = self._mask_text(text, parsed)
        return ExtractionResult(raw_json=parsed, masked_text=masked_text, replacements=replacements)


def iter_text_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
    else:
        yield from sorted(path.glob("*.txt"))
