"""Pydantic request/response models and the shared application error type."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AppError(Exception):
    """Raised anywhere in the pipeline; converted to a structured JSON response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=300)
    channel_override: Optional[str] = Field(None, max_length=100)
    language_override: Optional[str] = Field(None, max_length=10)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("query must be at least 3 characters")
        return stripped

    @field_validator("channel_override", "language_override")
    @classmethod
    def blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ParsedQuery(BaseModel):
    search_topic: str
    channel_name: Optional[str] = None
    language: Optional[str] = None
    original_question: str


class VideoResult(BaseModel):
    video_id: str
    title: str
    channel_title: str
    published_at: str
    thumbnail_url: str
    timestamp_seconds: int
    timestamp_display: str
    answer_summary: str
    exact_quote: str
    confidence: str
    watch_url: str
    embed_url: str


class SearchResponse(BaseModel):
    parsed: ParsedQuery
    results: List[VideoResult]
    message: Optional[str] = None
