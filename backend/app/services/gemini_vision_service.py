"""Gemini vision analysis for uploaded engineering photos and video frames."""
from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from app.config import Settings
from app.services.media_processor import MediaPart


class GeminiVisionError(RuntimeError):
    """Raised when Gemini vision cannot produce usable visual evidence."""


class GeminiVisionService:
    """Converts processed images and video frames into concise visual evidence."""

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise GeminiVisionError(
                "GEMINI_API_KEY is not set. Add a Gemini API key to backend/.env to analyze uploaded media."
            )
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = settings.gemini_vision_model

    def analyze(self, media: list[MediaPart]) -> str:
        contents: list[Any] = [
            """Analyze the supplied site photographs and sampled video frames for an engineering
scope-of-work workflow. Return concise, factual visual evidence grouped by filename.
Describe only visible conditions, components, labels, defects, safety concerns, and
uncertainties. Do not estimate costs, prescribe work, or claim measurements that are
not visible. If a frame is inconclusive, say so."""
        ]
        for item in media:
            if item.kind == "image":
                contents.append(f"File: {item.filename}")
                contents.append(types.Part.from_bytes(data=item.bytes, mime_type=item.mime_type))
            elif item.kind == "video":
                for index, (_, frame) in enumerate(item.frames, start=1):
                    contents.append(f"File: {item.filename}, sampled frame {index}")
                    contents.append(types.Part.from_bytes(data=frame, mime_type="image/jpeg"))
        try:
            response = self.client.models.generate_content(model=self.model_name, contents=contents)
        except Exception as exc:
            raise GeminiVisionError(f"Gemini vision API call failed: {exc}") from exc
        evidence = (response.text or "").strip()
        if not evidence:
            raise GeminiVisionError("Gemini vision returned an empty analysis.")
        return evidence