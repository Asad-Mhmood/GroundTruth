"""Provider-swappable claim extraction: extract_claims(...) -> list[Claim].

To add another provider (Gemini, Ollama, ...), add a `_call_<name>` function
with the same signature and register it in PROVIDERS.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Callable

from groq import Groq
from pydantic import ValidationError

from src.extraction.schemas import Claim

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompt.md"

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def format_chunk_text(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        total_seconds = int(seg["start"])
        m, s = divmod(total_seconds, 60)
        lines.append(f"[{m:02d}:{s:02d}] {seg['text']}")
    return "\n".join(lines)


def _call_groq(system_prompt: str, user_prompt: str, config: dict) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set (check your .env file)")
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=config["llm"]["model"],
        temperature=config["llm"].get("temperature", 0.1),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


PROVIDERS: dict[str, Callable[[str, str, dict], str]] = {
    "groq": _call_groq,
}


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    match = _CODE_FENCE_RE.match(text)
    return match.group(1).strip() if match else text


def extract_claims(
    video_id: str, chunk_index: int, segments: list[dict], config: dict
) -> list[Claim]:
    provider_name = config["llm"]["provider"]
    call_fn = PROVIDERS.get(provider_name)
    if call_fn is None:
        raise ValueError(
            f"Unknown LLM provider '{provider_name}'. Available: {list(PROVIDERS)}"
        )

    system_prompt = load_system_prompt()
    user_prompt = format_chunk_text(segments)
    max_retries = config["llm"].get("max_retries", 1)

    payload = None
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            raw = call_fn(system_prompt, user_prompt, config)
            parsed = json.loads(_strip_code_fence(raw))
            if not isinstance(parsed, list):
                raise ValueError("LLM response is not a JSON array")
            payload = parsed
            break
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(
                "video=%s chunk=%d: invalid JSON on attempt %d/%d: %s",
                video_id, chunk_index, attempt, max_retries + 1, e,
            )

    if payload is None:
        logger.error(
            "video=%s chunk=%d: skipping after %d failed attempt(s): %s",
            video_id, chunk_index, max_retries + 1, last_error,
        )
        return []

    claims: list[Claim] = []
    for raw_item in payload:
        try:
            raw_item = dict(raw_item)
            raw_item["video_id"] = video_id
            claims.append(Claim.model_validate(raw_item))
        except (ValidationError, TypeError) as e:
            logger.warning(
                "video=%s chunk=%d: dropping claim that failed schema validation: %s | data=%s",
                video_id, chunk_index, e, raw_item,
            )
    return claims
