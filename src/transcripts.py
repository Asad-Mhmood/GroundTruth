"""Transcript fetching with on-disk caching (spec section 5.3).

Prefers manually-created captions over auto-generated; caches raw segment
JSON to data/transcripts/{video_id}.json so re-runs never re-fetch.
"""
import json
import logging
from pathlib import Path

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

logger = logging.getLogger(__name__)


class TranscriptUnavailable(Exception):
    """Raised when a video has no usable captions."""


def _cache_path(video_id: str, config: dict) -> Path:
    cache_dir = Path(config["transcript"]["cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{video_id}.json"


def _to_raw(fetched) -> list[dict]:
    # youtube-transcript-api >=0.6.2 returns a FetchedTranscript object;
    # older versions return a plain list of dicts.
    if hasattr(fetched, "to_raw_data"):
        return fetched.to_raw_data()
    return list(fetched)


def fetch_transcript(video_id: str, config: dict) -> list[dict]:
    cache_path = _cache_path(video_id, config)
    if cache_path.exists():
        logger.info("video=%s: using cached transcript", video_id)
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    languages = config["transcript"].get("languages", ["en"])
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        raise TranscriptUnavailable(f"no captions available: {e}") from e

    transcript = None
    try:
        transcript = transcript_list.find_manually_created_transcript(languages)
    except NoTranscriptFound:
        try:
            transcript = transcript_list.find_generated_transcript(languages)
        except NoTranscriptFound:
            try:
                transcript = next(iter(transcript_list))
                logger.warning(
                    "video=%s: no transcript in %s, falling back to %s",
                    video_id, languages, transcript.language_code,
                )
            except StopIteration as e:
                raise TranscriptUnavailable("no transcripts at all") from e

    try:
        raw = _to_raw(transcript.fetch())
    except Exception as e:
        raise TranscriptUnavailable(f"fetch failed: {e}") from e

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    logger.info("video=%s: fetched and cached %d segments", video_id, len(raw))
    return raw
