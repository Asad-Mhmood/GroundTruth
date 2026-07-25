"""YouTube Data API v3 wrapper with a 1-hour TTL cache."""

import logging
from threading import Lock
from typing import Dict, List, Optional

import requests
from cachetools import TTLCache

from ..config import settings
from ..models import AppError

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/youtube/v3"
_MAX_RESULTS = 6

_search_cache: TTLCache = TTLCache(maxsize=256, ttl=60 * 60)
_cache_lock = Lock()


def search_videos(
    topic: str,
    channel_name: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict]:
    """Return up to 6 candidate videos as dicts with basic metadata."""
    cache_key = (topic.lower(), (channel_name or "").lower(), language or "")
    with _cache_lock:
        cached = _search_cache.get(cache_key)
    if cached is not None:
        return cached

    channel_id = _resolve_channel_id(channel_name) if channel_name else None

    params = {
        "part": "snippet",
        "type": "video",
        "maxResults": _MAX_RESULTS,
        "q": topic,
    }
    if channel_id:
        params["channelId"] = channel_id
    if language:
        params["relevanceLanguage"] = language

    # Prefer videos that definitely have captions; loosen if too few results.
    items = _yt_get("search", {**params, "videoCaption": "closedCaption"}).get(
        "items", []
    )
    if len(items) < 3:
        items = _yt_get("search", params).get("items", [])

    videos = []
    seen_ids = set()
    for item in items:
        video_id = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        if not video_id or video_id in seen_ids:
            continue
        seen_ids.add(video_id)
        thumbnails = snippet.get("thumbnails") or {}
        thumb = (
            thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        )
        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", "Untitled video"),
                "channel_title": snippet.get("channelTitle", "Unknown channel"),
                "published_at": (snippet.get("publishedAt") or "")[:10],
                "thumbnail_url": thumb.get("url", ""),
            }
        )

    with _cache_lock:
        _search_cache[cache_key] = videos
    return videos


def _resolve_channel_id(channel_name: str) -> Optional[str]:
    data = _yt_get(
        "search",
        {"part": "snippet", "type": "channel", "q": channel_name, "maxResults": 1},
    )
    items = data.get("items", [])
    if not items:
        return None
    return (items[0].get("id") or {}).get("channelId")


def _yt_get(endpoint: str, params: dict) -> dict:
    try:
        response = requests.get(
            f"{_BASE_URL}/{endpoint}",
            params={**params, "key": settings.youtube_api_key},
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("YouTube request failed: %s", exc)
        raise AppError(502, "Could not reach YouTube. Please try again shortly.")

    if response.status_code == 200:
        return response.json()

    reason = _error_reason(response)
    logger.warning("YouTube API %s error: %s", response.status_code, reason)

    if response.status_code == 403 and "quota" in reason.lower():
        raise AppError(
            503,
            "Today's free YouTube search quota has been used up. "
            "It resets at midnight Pacific time — please try again later.",
        )
    if response.status_code in (400, 401, 403):
        raise AppError(
            502,
            "YouTube rejected the request. If you run this backend, "
            "check that YOUTUBE_API_KEY is valid and the API is enabled.",
        )
    raise AppError(502, "YouTube search failed. Please try again shortly.")


def _error_reason(response: requests.Response) -> str:
    try:
        error = response.json().get("error") or {}
        errors = error.get("errors") or [{}]
        return errors[0].get("reason") or error.get("message") or ""
    except Exception:
        return ""
