"""Gemini call #2: locate answers inside transcripts and build final results."""

import logging
from typing import Dict, List

from ..models import VideoResult
from .gemini import generate_json

logger = logging.getLogger(__name__)

_MAX_TOTAL_CHARS = 150_000
_CONTEXT_LEAD_SECONDS = 5
_VALID_CONFIDENCE = {"high", "medium", "low"}

_PROMPT_HEADER = """You are analyzing YouTube video transcripts to find the exact moments where a question is answered.

Question: "{question}"

Below are transcripts of candidate videos. Each transcript line starts with its
timestamp in seconds, like [312s].

Return ONLY a strict JSON object — no markdown fences, no preamble:

{{
  "results": [
    {{
      "video_id": "abc123",
      "timestamp_seconds": 312,
      "answer_summary": "one sentence answering the question, written in the same language as the question",
      "exact_quote": "the words actually spoken at that moment, copied from the transcript",
      "confidence": "high | medium | low"
    }}
  ]
}}

Rules:
- Only include a video if its transcript GENUINELY contains an answer to the question. An empty results list is valid.
- timestamp_seconds must be the bracketed [Ns] number of the block where the answer is spoken.
- Order results best-first (most direct, most trustworthy answer first).
- At most one result per video.

"""


def find_answers(
    question: str,
    videos: List[Dict],
    transcripts: Dict[str, List[Dict]],
) -> List[VideoResult]:
    videos_by_id = {
        video["video_id"]: video for video in videos if video["video_id"] in transcripts
    }
    if not videos_by_id:
        return []

    prompt = _build_prompt(question, videos_by_id, transcripts)
    data = generate_json(prompt)
    if not isinstance(data, dict):
        logger.warning("Answer finder: unparseable Gemini response")
        return []
    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        return []

    results: List[VideoResult] = []
    seen = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        video_id = item.get("video_id")
        if not isinstance(video_id, str) or video_id not in videos_by_id or video_id in seen:
            continue
        try:
            timestamp = int(float(item.get("timestamp_seconds", 0)))
        except (TypeError, ValueError):
            continue
        # Back up a few seconds so the viewer gets context before the answer.
        timestamp = max(0, timestamp - _CONTEXT_LEAD_SECONDS)

        summary = str(item.get("answer_summary") or "").strip()
        quote = str(item.get("exact_quote") or "").strip()
        if not summary:
            continue
        confidence = str(item.get("confidence") or "").strip().lower()
        if confidence not in _VALID_CONFIDENCE:
            confidence = "low"

        seen.add(video_id)
        meta = videos_by_id[video_id]
        results.append(
            VideoResult(
                video_id=video_id,
                title=meta["title"],
                channel_title=meta["channel_title"],
                published_at=meta["published_at"],
                thumbnail_url=meta["thumbnail_url"],
                timestamp_seconds=timestamp,
                timestamp_display=format_timestamp(timestamp),
                answer_summary=summary,
                exact_quote=quote,
                confidence=confidence,
                watch_url=f"https://www.youtube.com/watch?v={video_id}&t={timestamp}s",
                embed_url=f"https://www.youtube.com/embed/{video_id}?start={timestamp}",
            )
        )
    return results


def format_timestamp(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _build_prompt(
    question: str,
    videos_by_id: Dict[str, Dict],
    transcripts: Dict[str, List[Dict]],
) -> str:
    transcript_texts = {
        video_id: "\n".join(f"[{block['start']}s] {block['text']}" for block in blocks)
        for video_id, blocks in transcripts.items()
        if video_id in videos_by_id
    }

    total_chars = sum(len(text) for text in transcript_texts.values())
    if total_chars > _MAX_TOTAL_CHARS:
        # Truncate each transcript proportionally, cutting from the end.
        ratio = _MAX_TOTAL_CHARS / total_chars
        for video_id, text in transcript_texts.items():
            keep = int(len(text) * ratio)
            cut = text[:keep]
            # Avoid ending mid-line so every kept line still has its [Ns] tag.
            last_newline = cut.rfind("\n")
            if last_newline > 0:
                cut = cut[:last_newline]
            transcript_texts[video_id] = cut

    sections = []
    for video_id, text in transcript_texts.items():
        meta = videos_by_id[video_id]
        sections.append(
            f"=== VIDEO video_id: {video_id} ===\n"
            f"Title: {meta['title']}\n"
            f"Channel: {meta['channel_title']}\n"
            f"Uploaded: {meta['published_at']}\n"
            f"Transcript:\n{text}\n"
        )

    return (
        _PROMPT_HEADER.format(question=question.replace('"', "'"))
        + "\n".join(sections)
    )
