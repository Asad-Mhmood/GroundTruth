# Vlog Intelligence — Project Specification

A search engine for travel knowledge locked inside YouTube travel vlogs. Extracts structured, dated, sourced claims (prices, warnings, tips, verdicts) from vlog transcripts and answers traveler questions with evidence linked to the exact video moment — never with generated travel facts.

**One-line pitch:** "7 vloggers in the last 14 months paid $135–175 for the Ha Giang loop — here are the clips."

---

## 1. Core principles (do not violate)

1. **Evidence, not generation.** The system NEVER answers a travel question from LLM world knowledge. Every fact shown to a user must trace to an extracted claim with a video source and timestamp. If no claims exist, show an honest "no firsthand reports yet" state.
2. **Timestamps survive the whole pipeline.** Every claim carries `timestamp_seconds` so the UI can deep-link to `youtube.com/watch?v={id}&t={s}s`. This is the killer feature; never drop it.
3. **Zero budget.** Every component must run on free tiers or locally. No paid APIs, no paid hosting. The LLM used for extraction must be swappable via config (free-tier API today, stronger model later).
4. **Variance is information.** Prices differ by travel style (backpacker vs. luxury). Never average across styles into one mushy number — segment by channel style profile.
5. **Serve derived claims only.** Store transcripts privately for processing; never republish full transcripts. Public output = extracted claims + links back to YouTube.

## 2. MVP scope

- **One destination:** Vietnam (configurable; final choice comes from the coverage matrix — see 5.1).
- **One claim type fully supported:** `price`. Schema also captures `scam_warning`, `tip`, `verdict`, `logistics` (extracted and stored, but UI focuses on prices).
- **Curated channels only:** ~30–50 hand-picked channels from a YAML file. No open YouTube search in MVP.
- **Captions only:** skip videos without captions (no Whisper in MVP).
- **UI:** Streamlit app with (a) natural-language ask, (b) destination browse page, (c) claim detail with source clips.

**Explicitly out of scope for v1:** multiple destinations, Whisper transcription, open channel discovery/vetting funnel, visual/frame analysis, comments mining, user accounts, mobile app, real-time updates. Note them in the README as roadmap; do not build.

## 3. Tech stack (all free)

| Component | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Video discovery | YouTube Data API v3 | Free 10,000 units/day. NEVER use `search.list` (100 units/call). Use `channels.list` → uploads playlist → `playlistItems.list` (1 unit/page of 50). |
| Transcripts | `youtube-transcript-api` | Free. Preserve per-segment timestamps. Cache raw transcripts to disk (JSON), never re-fetch. Throttle politely; handle failures gracefully and continue. |
| LLM extraction | Config-swappable provider | Default: a free-tier API (e.g. Groq / Gemini Flash / OpenRouter free models) with a local Ollama fallback (e.g. qwen2.5:7b / llama3.1:8b). One interface: `extract(chunk) -> list[Claim]`. Respect rate limits; extraction is a resumable batch job that can spread across days. |
| Geocoding | Nominatim (OpenStreetMap) | Max 1 req/sec; cache every result permanently in a `places` table. |
| FX rates | frankfurter.app | Historical rates by date; cache. |
| Database | SQLite for dev; schema portable to Postgres (Supabase/Neon free tier) later | Use SQLAlchemy so the swap is config-only. |
| Embeddings | `sentence-transformers` locally (e.g. all-MiniLM-L6-v2) | For semantic claim retrieval. Store vectors in SQLite (sqlite-vec) or plain numpy + cosine for MVP. |
| UI | Streamlit | Deployable free to Streamlit Community Cloud / Hugging Face Spaces. |
| Orchestration | Plain Python CLI scripts + Makefile | No Airflow in MVP. Every stage idempotent and resumable. |

## 4. Data model

```sql
channels (
  id TEXT PRIMARY KEY,            -- YouTube channel ID
  name TEXT,
  handle TEXT,
  -- style profile (hand-tagged, inherited by all claims)
  budget_tier TEXT,               -- backpacker | midrange | comfort | luxury
  travel_mode TEXT,               -- solo | couple | family | group
  authenticity TEXT,              -- raw | produced | mixed
  sponsored_tendency TEXT,        -- low | medium | high
  credibility_note TEXT,
  status TEXT DEFAULT 'active'    -- active | paused
)

videos (
  id TEXT PRIMARY KEY,            -- YouTube video ID
  channel_id TEXT REFERENCES channels(id),
  title TEXT,
  published_at DATE,
  duration_seconds INT,
  destination_tags TEXT,          -- JSON list, from title/description keyword match
  transcript_status TEXT,         -- pending | fetched | no_captions | failed
  extraction_status TEXT          -- pending | done | failed
)

claims (
  id INTEGER PRIMARY KEY,
  video_id TEXT REFERENCES videos(id),
  claim_type TEXT,                -- price | scam_warning | tip | verdict | logistics
  item TEXT,                      -- normalized item name, e.g. "airport taxi"
  item_raw TEXT,                  -- as extracted
  amount REAL, currency TEXT,     -- as spoken
  amount_usd REAL,                -- converted at video publish date
  place_id INTEGER REFERENCES places(id),
  place_raw TEXT,
  sentiment TEXT,                 -- positive | negative | neutral | null
  quote TEXT,                     -- supporting transcript snippet (short)
  timestamp_seconds INT,          -- REQUIRED
  confidence REAL,                -- 0..1 from extractor
  claim_date DATE,                -- = video publish date
  sponsored_context BOOLEAN      -- claim made in sponsored segment
)

places (
  id INTEGER PRIMARY KEY,
  canonical_name TEXT,
  country TEXT,
  lat REAL, lon REAL,
  aliases TEXT                    -- JSON list of raw strings resolved here
)
```

## 5. Pipeline stages (each = one CLI command, idempotent, resumable)

### 5.1 `build_coverage_matrix`
Input: `channels.yaml` (the full 100-channel list). For each channel, pull upload titles via playlist pagination and keyword-match against a country keyword file. Output: a channels × countries count matrix (CSV) + a report of which destination has the deepest coverage. **The MVP destination is chosen from this report.**

### 5.2 `ingest`
For the chosen destination: filter videos by destination keywords in title/description, upsert `videos` rows. Track API quota usage; stop before exhausting the daily budget and resume next run.

### 5.3 `fetch_transcripts`
For each pending video: try `youtube-transcript-api` (manual captions preferred, auto-generated accepted). Save raw JSON to `data/transcripts/{video_id}.json`. Mark `no_captions` and skip if unavailable. Never re-fetch cached transcripts.

### 5.4 `extract_claims`
- Chunk transcript into ~2,000-token windows with ~200-token overlap, preserving segment timestamps.
- Call the configured LLM with a strict JSON-schema prompt (see 6). Validate output with Pydantic; on invalid JSON, retry once, then log and skip the chunk.
- Expect most chunks to yield ZERO claims — the prompt must make this explicit to prevent hallucinated claims.
- Deduplicate overlapping-window duplicates (same item + amount + nearby timestamp).
- Track cost/requests; resumable at chunk level.

### 5.5 `normalize`
- Currency: map spoken currency ("dong", "baht", "bucks") to ISO codes; convert to USD using frankfurter rate at `claim_date`; store both.
- Places: resolve `place_raw` to `places` via alias cache first, then Nominatim (1 req/sec, biased to the destination country). Unresolvable → leave place_id null, keep the claim.
- Items: normalize to a controlled vocabulary via a mapping file that grows over time (e.g. "cab from airport", "grab from the airport" → "airport taxi"). Log unmapped items for review.

### 5.6 `embed`
Compute sentence embeddings for `item + quote` per claim for semantic retrieval.

### 5.7 `serve` (Streamlit)
Three views:
1. **Ask** — text box; retrieval = SQL filters (destination, claim_type, recency) + semantic search over claims; an LLM composes the answer **using only retrieved claims**, with every number linked to its source clip. If retrieval returns nothing relevant: render the honest empty state, optionally showing nearest related items.
2. **Browse** — per-destination cost sheet: items grouped, each showing median + range (USD), source count, recency badge, expandable source clips. Segment by `budget_tier` when a style filter is applied; if per-item variance is high across tiers, show tiered sub-ranges instead of one range.
3. **Claim detail / source card** — quote, channel name + style tags, publish date, "jump to M:SS" link.

Answer-rendering rules: lead with the number/range, then evidence cards; show "N independent vloggers" and "last X months" badges; flag `sponsored_context` claims visually; only show claims above a confidence threshold (config, default 0.7).

## 6. Extraction prompt contract

System prompt requirements (implement as a versioned prompt file):
- Role: extract structured travel claims from a (possibly messy, auto-generated) vlog transcript chunk.
- Output: JSON array matching the Claim schema; empty array `[]` when nothing qualifies. "Most chunks contain no claims — returning [] is the expected common case."
- Only firsthand statements by the speaker about their own experience. Exclude: hypotheticals, prices read from menus/websites they didn't pay, other people's stories, sponsor ad-reads (unless flagged `sponsored_context: true`).
- Numbers as spoken; do not convert currency; do not guess missing amounts.
- Each claim must include the shortest supporting quote and the timestamp of the segment it came from.
- Include a `confidence` score; be conservative.

Provide 2–3 few-shot examples in the prompt, including one messy auto-caption example ("four hundred thousand dong" → amount 400000, currency VND) and one zero-claim chunk → `[]`.

## 7. Evaluation (required, not optional)

- Build `data/gold/`: hand-labeled claims from 20 videos (~150 claims) using a small labeling helper script.
- `evaluate` command: run the extractor on gold videos, compute precision/recall/F1 for claim detection and field accuracy (amount, currency, item, timestamp ±15s).
- Report results in README. Target: ≥0.8 precision on price claims before building the UI polish. If below, iterate on the prompt, not the UI.

## 8. Project structure

```
vlog-intelligence/
  channels.yaml            # curated channels + style profiles
  config.yaml              # destination, LLM provider, thresholds, quotas
  keywords/countries.yaml
  src/
    discovery.py  ingest.py  transcripts.py
    extraction/ (prompt.md, extractor.py, schemas.py)
    normalize/ (currency.py, places.py, items.py)
    db.py  embed.py  evaluate.py
  app/streamlit_app.py
  data/ (transcripts/, gold/, cache/)   # gitignored
  Makefile                 # make coverage | ingest | transcripts | extract | normalize | eval | app
  README.md
```

## 9. Build order (phases; finish each before the next)

- **Phase 0 — validation (build FIRST, minimal code):** script that takes 10 hard-coded video IDs → fetches transcripts → runs the extraction prompt → prints claims for manual review. Decision gate: good vlogs should yield 5–15 correct price claims each.
- **Phase 1:** channels.yaml schema, coverage matrix, ingestion with quota tracking.
- **Phase 2:** transcript fetching with caching; extraction pipeline with validation, dedupe, resumability.
- **Phase 3:** normalization (currency, places, items) + database + embeddings.
- **Phase 4:** aggregation queries + Streamlit UI (Ask, Browse, source cards, empty states).
- **Phase 5:** gold set + evaluation + README with metrics; deploy to Streamlit Community Cloud / HF Spaces.

## 10. Constraints & risks to engineer around

- **API quota:** hard daily budget tracking; the pipeline must stop gracefully and resume. Never call `search.list`.
- **Transcript flakiness:** cache everything, exponential backoff, per-video failure isolation (one failure never kills a batch).
- **Extraction hallucination:** zero-claim default, confidence thresholds, gold-set evaluation, Pydantic validation.
- **Free LLM rate limits:** batch job with checkpointing; provider swappable in config; acceptable for extraction to take days.
- **ToS respect:** private transcripts, public derived claims + YouTube links only; no video/audio redistribution.
- **Roadmap (do not build now):** additional claim types in UI (scams, tips), open channel discovery + automated vetting classifier, Whisper backfill, more destinations, React frontend.
