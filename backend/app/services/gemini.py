"""Shared Gemini client: strict-JSON generation with retry and defensive parsing."""

import json
import logging
import re
import time
from typing import Any, Optional

from google import genai
from google.genai import errors as genai_errors

from ..config import settings
from ..models import AppError

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_json(prompt: str) -> Optional[Any]:
    """Ask Gemini for strict JSON. Returns the parsed object, or None if the
    model replied with something that cannot be parsed as JSON."""
    text = _generate_text(prompt)
    return parse_json_loose(text)


def _generate_text(prompt: str) -> str:
    """Call Gemini, retrying once after a short wait before failing."""
    for attempt in (1, 2):
        try:
            response = _get_client().models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                },
            )
            return response.text or ""
        except genai_errors.APIError as exc:
            logger.warning("Gemini API error (attempt %d): %s", attempt, exc)
            if attempt == 1:
                time.sleep(3)
                continue
            if getattr(exc, "code", None) == 429:
                raise AppError(
                    503,
                    "The free AI quota is temporarily rate-limited. "
                    "Please wait about a minute and try again.",
                )
            raise AppError(
                502, "The AI service returned an error. Please try again shortly."
            )
        except Exception as exc:  # network failures, timeouts, etc.
            logger.warning("Gemini call failed (attempt %d): %s", attempt, exc)
            if attempt == 1:
                time.sleep(2)
                continue
            raise AppError(
                502, "Could not reach the AI service. Please try again shortly."
            )
    return ""  # unreachable


def parse_json_loose(text: str) -> Optional[Any]:
    """Parse model output defensively: strip markdown fences, then fall back to
    the outermost braces. Returns None when nothing parseable is found."""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass
    logger.warning("Gemini returned unparseable JSON: %.200s", text)
    return None
