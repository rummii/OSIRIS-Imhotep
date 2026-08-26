"""DeepSeek text generation through its OpenAI-compatible API."""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.config import Settings


class DeepSeekAnalysisError(RuntimeError):
    """Raised when DeepSeek cannot produce a usable SOW payload."""


class AnalyzeResult:
    def __init__(self, payload: dict[str, Any], model: str) -> None:
        self.payload = payload
        self.model = model


class DeepSeekService:
    """Runs structured SOW generation against DeepSeek's chat endpoint."""

    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise DeepSeekAnalysisError(
                "DEEPSEEK_API_KEY is not set. Add your key to backend/.env and restart the backend."
            )
        self.model_name = settings.deepseek_model
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            timeout=120.0,       # fail fast instead of hanging the request
            max_retries=1,
        )

    def analyze(self, system_prompt: str, user_prompt: str) -> AnalyzeResult:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as exc:
            raise DeepSeekAnalysisError(f"DeepSeek API call failed: {exc}") from exc

        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise DeepSeekAnalysisError("DeepSeek returned an empty response.")
        return AnalyzeResult(payload=self._parse_json(text), model=self.model_name)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise DeepSeekAnalysisError("DeepSeek output did not contain valid JSON.") from exc
        if not isinstance(payload, dict):
            raise DeepSeekAnalysisError("DeepSeek output JSON was not an object.")
        return DeepSeekService._unwrap_schema_echo(payload)

    @staticmethod
    def _unwrap_schema_echo(payload: Any) -> Any:
        """Best-effort rescue for a common DeepSeek failure mode.

        When handed a JSON-Schema style contract, the model sometimes echoes the
        schema back as ``{"type": "OBJECT", "properties": {..., "value": ...}}``
        instead of producing data. Recover what we can (scalars + objects) by
        walking the echoed ``properties`` tree and pulling every ``value`` leaf.
        Arrays cannot be reconstructed from an echoed item schema, so they are
        returned empty.
        """
        if not isinstance(payload, dict):
            return payload

        # Not a schema echo -> return unchanged.
        if "properties" not in payload or not isinstance(payload.get("properties"), dict):
            return payload

        def walk(node: Any) -> Any:
            if isinstance(node, dict):
                if "value" in node:  # schema leaf -> actual value
                    return node["value"]
                props = node.get("properties")
                if isinstance(props, dict):
                    return {key: walk(sub) for key, sub in props.items()}
                return [] if node.get("type") == "ARRAY" else None
            if isinstance(node, list):
                return [walk(item) for item in node]
            return node

        return walk(payload)