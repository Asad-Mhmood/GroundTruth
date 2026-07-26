"""Concurrent transcript fetching with 60-second block merging and a 24h cache.

Two fetch strategies, tried in order:
1. youtube-transcript-api — fast, but YouTube blocks it on many IPs (429).
2. yt-dlp with the "android" player client — slower but reliably bypasses
   the watch-page bot check without cookies.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional

import requests
import yt_dlp
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


def _preferred_langs(language: Optional[str]) -> List[str]:
    langs = []
    for lang in (language, "en"):
        if lang and lang not in langs:
            langs.append(lang)
    return langs


def _fetch_raw_segments(video_id: str, language: Optional[str]) -> Optional[List[Dict]]:
    """Try youtube-transcript-api first, then fall back to yt-dlp."""
    segments = _fetch_via_transcript_api(video_id, language)
    if segments is None:
        segments = _fetch_via_ytdlp(video_id, language)
    return segments


def _fetch_via_transcript_api(
    video_id: str, language: Optional[str]
) -> Optional[List[Dict]]:
    """Pick the best available transcript track.

    Priority: detected language -> English -> any available,
    preferring manually-created tracks over auto-generated ones.
    """
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
    except Exception:
        return None  # IP blocked, transcripts disabled, video unavailable, etc.

    manual, generated = [], []
    for transcript in transcript_list:
        (generated if transcript.is_generated else manual).append(transcript)

    preferred_langs = _preferred_langs(language)

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


_YTDLP_OPTS = {
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
    # The android player client bypasses the watch-page bot check that blocks
    # plain HTTP clients (and youtube-transcript-api) on many IPs.
    "extractor_args": {"youtube": {"player_client": ["android"]}},
}


def _fetch_via_ytdlp(video_id: str, language: Optional[str]) -> Optional[List[Dict]]:
    try:
        with yt_dlp.YoutubeDL(dict(_YTDLP_OPTS)) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
    except Exception as exc:
        logger.info("yt-dlp extract failed for %s: %s", video_id, str(exc)[:200])
        return None

    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    preferred_langs = _preferred_langs(language)

    # Same priority as the primary path: preferred languages first, manual
    # tracks before auto-generated ones, then anything else that's available.
    candidates: List[List[Dict]] = []
    added = set()

    def add(group: Dict, group_name: str, lang_filter: Optional[str]) -> None:
        for key, tracks in group.items():
            if lang_filter and key.split("-")[0].lower() != lang_filter:
                continue
            marker = (group_name, key)
            if marker not in added and tracks:
                added.add(marker)
                candidates.append(tracks)

    for group, group_name in ((manual, "manual"), (auto, "auto")):
        for lang in preferred_langs:
            add(group, group_name, lang)
    add(manual, "manual", None)
    add(auto, "auto", None)

    for tracks in candidates:
        fmt = next((t for t in tracks if t.get("ext") == "json3" and t.get("url")), None)
        if not fmt:
            continue
        try:
            response = requests.get(fmt["url"], timeout=20)
            if response.status_code != 200:
                continue
            events = response.json().get("events") or []
        except Exception:
            continue
        segments = []
        for event in events:
            segs = event.get("segs")
            if not segs:
                continue
            text = "".join(s.get("utf8", "") for s in segs).strip()
            if not text:
                continue
            segments.append(
                {
                    "text": text,
                    "start": (event.get("tStartMs") or 0) / 1000.0,
                    "duration": (event.get("dDurMs") or 0) / 1000.0,
                }
            )
        if segments:
            return segments
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
