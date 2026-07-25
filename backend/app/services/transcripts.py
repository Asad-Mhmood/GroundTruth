"""Concurrent transcript fetching with 60-second block merging and a 24h cache."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional

from cachetools import TTLCache
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

BLOCK_SECONDS = 60
_MAX_SUCCESSFUL = 4

_transcript_cache: TTLCache = TTLCache(maxsize=512, ttl=24 * 60 * 60)
_cache_lock = Lock()


def fetch_transcripts(
    video_ids: List[str], language: Optional[str] = None
) -> Dict[str, List[Dict]]:
    """Fetch transcripts concurrently; stop once 4 succeed. Videos with
    disabled/missing transcripts are skipped silently.

    Returns {video_id: [{"start": int, "text": str}, ...]} of merged 60s blocks.
    """
    results: Dict[str, List[Dict]] = {}
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(video_ids)))) as pool:
        futures = {
            pool.submit(_get_blocks, video_id, language): video_id
            for video_id in video_ids
        }
        for future in as_completed(futures):
            video_id = futures[future]
            try:
                blocks = future.result()
            except Exception as exc:
                logger.info("Transcript fetch failed for %s: %s", video_id, exc)
                blocks = None
            if blocks:
                results[video_id] = blocks
                if len(results) >= _MAX_SUCCESSFUL:
                    for pending in futures:
                        pending.cancel()
                    break
    # Preserve the original candidate order (search relevance order).
    return {vid: results[vid] for vid in video_ids if vid in results}


def _get_blocks(video_id: str, language: Optional[str]) -> Optional[List[Dict]]:
    cache_key = (video_id, language or "")
    with _cache_lock:
        if cache_key in _transcript_cache:
            return _transcript_cache[cache_key]

    segments = _fetch_raw_segments(video_id, language)
    blocks = _merge_into_blocks(segments) if segments else None

    with _cache_lock:
        _transcript_cache[cache_key] = blocks
    return blocks


def _fetch_raw_segments(video_id: str, language: Optional[str]) -> Optional[List[Dict]]:
    """Pick the best available transcript track.

    Priority: detected language -> English -> any available,
    preferring manually-created tracks over auto-generated ones.
    """
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
    except Exception:
        return None  # transcripts disabled, video unavailable, etc.

    manual, generated = [], []
    for transcript in transcript_list:
        (generated if transcript.is_generated else manual).append(transcript)

    preferred_langs = []
    for lang in (language, "en"):
        if lang and lang not in preferred_langs:
            preferred_langs.append(lang)

    ordered = []
    for group in (manual, generated):
        for lang in preferred_langs:
            ordered.extend(
                t for t in group if t.language_code.split("-")[0].lower() == lang
            )
    ordered.extend(manual)
    ordered.extend(generated)

    seen = set()
    for transcript in ordered:
        marker = id(transcript)
        if marker in seen:
            continue
        seen.add(marker)
        try:
            return transcript.fetch().to_raw_data()
        except Exception:
            continue
    return None


def _merge_into_blocks(segments: List[Dict]) -> Optional[List[Dict]]:
    """Merge raw caption segments into ~60-second blocks, keeping the first
    segment's start time for each block."""
    blocks: List[Dict] = []
    block_start: Optional[float] = None
    block_text: List[str] = []

    for segment in segments:
        text = (segment.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        start = float(segment.get("start") or 0)
        if block_start is None:
            block_start, block_text = start, [text]
        elif start - block_start >= BLOCK_SECONDS:
            blocks.append({"start": int(block_start), "text": " ".join(block_text)})
            block_start, block_text = start, [text]
        else:
            block_text.append(text)

    if block_start is not None and block_text:
        blocks.append({"start": int(block_start), "text": " ".join(block_text)})
    return blocks or None
