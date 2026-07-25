"""Claim schema (spec section 4, extraction-relevant fields only).

Fields owned by later pipeline stages (id, place_id, amount_usd, claim_date)
are intentionally omitted -- they belong to normalize/db, not Phase 0.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Claim(BaseModel):
    video_id: str
    claim_type: Literal["price", "scam_warning", "tip", "verdict", "logistics"]
    item: str
    item_raw: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    place_raw: Optional[str] = None
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = None
    quote: str
    timestamp_seconds: int
    confidence: float = Field(ge=0.0, le=1.0)
    sponsored_context: bool = False

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v
