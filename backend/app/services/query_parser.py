"""Gemini call #1: turn the raw user question into a structured search plan."""

import logging
from typing import Optional

from ..models import ParsedQuery
from .gemini import generate_json

logger = logging.getLogger(__name__)

_PROMPT = """You are a query parser for a tool that finds answers inside YouTube videos.

Analyze this user query and return ONLY a strict JSON object — no markdown fences,
no preamble, no trailing text:

{{
  "search_topic": "concise YouTube search query that would surface videos answering the question",
  "channel_name": "YouTube channel or YouTuber name if the user mentions one, else null",
  "language": "two-letter ISO 639-1 code if a language is explicitly mentioned OR clearly implied by the language the query is written in, else null",
  "original_question": "the user's question, lightly cleaned up (fix typos, remove channel/language instructions), in its original language"
}}

Rules:
- search_topic: keyword-style, in the language most likely used by relevant videos.
- channel_name: only a real channel/person the user explicitly names (e.g. "Dhruv Rathee"). Never invent one.
- language: e.g. "hi" for Hindi, "ur" for Urdu, "en" for English. If the query is written in Hindi/Urdu, that implies the language.
- original_question must stay a self-contained question.

User query: "{query}"
"""


def parse_query(raw_query: str) -> ParsedQuery:
    data = generate_json(_PROMPT.format(query=raw_query.replace('"', "'")))

    if not isinstance(data, dict):
        logger.warning("Query parser fell back to raw query")
        return ParsedQuery(search_topic=raw_query, original_question=raw_query)

    search_topic = _clean_str(data.get("search_topic")) or raw_query
    original_question = _clean_str(data.get("original_question")) or raw_query
    channel_name = _clean_str(data.get("channel_name"))
    language = _clean_str(data.get("language"))
    if language:
        language = language.lower()[:2]

    return ParsedQuery(
        search_topic=search_topic,
        channel_name=channel_name,
        language=language,
        original_question=original_question,
    )


def _clean_str(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in ("null", "none", "n/a"):
        return None
    return stripped
