"""Phase 0 validation script (spec section 9).

Hard-coded video IDs -> cached transcripts -> chunked extraction -> a
printed table of claims for manual review. No database, no UI, no other
pipeline stages.

Usage:
    1. cp .env.example .env   and fill in GROQ_API_KEY
    2. pip install -r requirements.txt
    3. Replace the placeholders in VIDEO_IDS below with 10 real YouTube
       video IDs (Vietnam travel vlogs with captions work best).
    4. python phase0_validate.py
"""
import logging
from pathlib import Path

import tiktoken
import yaml
from dotenv import load_dotenv
from tabulate import tabulate

from src.extraction.extractor import extract_claims
from src.extraction.schemas import Claim
from src.transcripts import TranscriptUnavailable, fetch_transcript

# TODO: replace with 10 real YouTube video IDs (11-char IDs, e.g. from a URL
# like youtube.com/watch?v=XXXXXXXXXXX). Prefer videos with captions.
VIDEO_IDS = [
    "REPLACE_ME_1",
    "REPLACE_ME_2",
    "REPLACE_ME_3",
    "REPLACE_ME_4",
    "REPLACE_ME_5",
    "REPLACE_ME_6",
    "REPLACE_ME_7",
    "REPLACE_ME_8",
    "REPLACE_ME_9",
    "REPLACE_ME_10",
]

CONFIG_PATH = Path(__file__).parent / "config.yaml"

logger = logging.getLogger("phase0")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def chunk_transcript(
    segments: list[dict], enc, max_tokens: int, overlap_tokens: int
) -> list[list[dict]]:
    """Split segments into ~max_tokens windows with ~overlap_tokens overlap,
    keeping each segment (and its timestamp) intact."""
    chunks: list[list[dict]] = []
    n = len(segments)
    start = 0
    while start < n:
        tokens = 0
        end = start
        while end < n and tokens < max_tokens:
            tokens += len(enc.encode(segments[end]["text"]))
            end += 1
        chunks.append(segments[start:end])
        if end >= n:
            break
        back_tokens = 0
        new_start = end
        while new_start > start and back_tokens < overlap_tokens:
            new_start -= 1
            back_tokens += len(enc.encode(segments[new_start]["text"]))
        start = new_start if new_start > start else end
    return chunks


def print_claims_table(claims: list[Claim]) -> None:
    if not claims:
        print("\nNo claims extracted.")
        return

    rows = []
    for c in claims:
        m, s = divmod(c.timestamp_seconds, 60)
        quote = c.quote if len(c.quote) <= 70 else c.quote[:67] + "..."
        rows.append([
            c.video_id,
            f"{m}:{s:02d}",
            c.claim_type,
            c.item,
            c.amount if c.amount is not None else "",
            c.currency or "",
            c.place_raw or "",
            c.sentiment or "",
            f"{c.confidence:.2f}",
            "Y" if c.sponsored_context else "",
            quote,
        ])

    headers = [
        "video", "t", "type", "item", "amount", "cur",
        "place", "sentiment", "conf", "spon", "quote",
    ]
    print(f"\nExtracted {len(claims)} claim(s):\n")
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    load_dotenv()
    config = load_config()

    if any(v.startswith("REPLACE_ME") for v in VIDEO_IDS):
        logger.error(
            "VIDEO_IDS still contains placeholders. Edit phase0_validate.py "
            "with 10 real video IDs before running."
        )
        return

    enc = tiktoken.get_encoding("cl100k_base")
    max_tokens = config["chunking"]["max_tokens"]
    overlap_tokens = config["chunking"]["overlap_tokens"]

    all_claims: list[Claim] = []

    for video_id in VIDEO_IDS:
        logger.info("Processing video %s", video_id)
        try:
            segments = fetch_transcript(video_id, config)
        except TranscriptUnavailable as e:
            logger.warning("Skipping video %s: %s", video_id, e)
            continue

        chunks = chunk_transcript(segments, enc, max_tokens, overlap_tokens)
        logger.info(
            "video=%s: %d transcript segments -> %d chunks",
            video_id, len(segments), len(chunks),
        )

        for i, chunk_segments in enumerate(chunks):
            claims = extract_claims(video_id, i, chunk_segments, config)
            if claims:
                logger.info("video=%s chunk=%d: %d claim(s)", video_id, i, len(claims))
            all_claims.extend(claims)

    print_claims_table(all_claims)


if __name__ == "__main__":
    main()
