# Project Specification: GroundTruth — YouTube Timestamp Answer Finder

## 1. Overview

Build a production-quality web application where a user types a natural-language question (e.g. "What is the taxi fare from Almaty city center to Almaty railway station?" or "What is the ticket price for Burj Khalifa 124th floor?") and the system returns YouTube video links with **exact timestamps** — clicking a link opens the video at the precise moment where the answer is spoken. The user watches 20–30 seconds instead of searching and scrubbing through videos manually.

Users can optionally filter by:
- **Channel / YouTuber name** (e.g. "show me where Dhruv Rathee discusses Rahul Gandhi")
- **Language** of the video (e.g. Hindi, Urdu, English)

The user may type these filters naturally inside the query — the system extracts them automatically. Optional manual filter inputs may also be shown in the UI.

This is a real website intended for public launch, not a prototype. Code quality, UI polish, responsiveness (mobile-first), and deployability matter.

## 2. Hard Constraints

- **Everything must be 100% free to build and host.** No paid APIs, no paid hosting tiers, no credit-card-required services.
- Must work well for **Hindi, Urdu, and English** videos (auto-generated captions included).
- Must run locally with simple commands and deploy free: frontend → **Vercel**, backend → **Render free tier**.
- Clean, readable, well-organized code — solo developer will maintain it.

## 3. Architecture & Tech Stack (all free)

Two separate deployable apps in one monorepo:

### Backend — Python / FastAPI
| Component | Technology | Notes |
|---|---|---|
| API framework | **FastAPI** + Uvicorn | REST API, automatic /docs |
| Video search | **YouTube Data API v3** | Free: 10,000 units/day; search = 100 units/call |
| Transcripts | **`youtube-transcript-api`** | No quota; segments include `start` seconds |
| LLM | **Google Gemini API free tier** (`google-generativeai`, model `gemini-1.5-flash` or newer flash) | Query parsing + answer locating |
| Caching | **In-memory TTL cache** (`cachetools`) | No Redis — must stay free/simple |
| Config | `python-dotenv` + environment variables | Never hardcode keys |

### Frontend — React
| Component | Technology | Notes |
|---|---|---|
| Framework | **React 18 + Vite** | Fast, simple, free to host anywhere |
| Styling | **Tailwind CSS** | Modern, responsive, no component library required |
| HTTP | `fetch` (native) | Backend URL from `VITE_API_URL` env var |
| Icons | `lucide-react` | Free |

Do **not** use embeddings, vector databases, Next.js server components, or any database in this version. Stateless app; the LLM reads transcripts directly.

## 4. Repository Structure (monorepo)

```
groundtruth/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, routes
│   │   ├── config.py            # env loading, settings
│   │   ├── models.py            # Pydantic request/response models
│   │   └── services/
│   │       ├── query_parser.py  # Gemini call #1
│   │       ├── youtube_search.py# YouTube Data API wrapper
│   │       ├── transcripts.py   # fetching + 60s block merging
│   │       └── answer_finder.py # Gemini call #2 + link building
│   ├── requirements.txt
│   ├── .env.example
│   └── render.yaml              # Render free-tier deploy config
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js               # backend client
│   │   └── components/
│   │       ├── SearchBar.jsx
│   │       ├── FilterPanel.jsx  # optional channel/language overrides
│   │       ├── ResultCard.jsx
│   │       ├── LoadingSteps.jsx # staged progress indicator
│   │       └── EmptyState.jsx
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   └── .env.example             # VITE_API_URL
├── .gitignore                   # includes .env, node_modules, __pycache__
└── README.md
```

## 5. Backend API

### `GET /health`
Returns `{"status": "ok"}` — used by Render health checks and to wake the free instance.

### `POST /api/search`
Request body:
```json
{
  "query": "user's natural language question",
  "channel_override": null,
  "language_override": null
}
```

Response body:
```json
{
  "parsed": {
    "search_topic": "...",
    "channel_name": null,
    "language": null,
    "original_question": "..."
  },
  "results": [
    {
      "video_id": "abc123",
      "title": "...",
      "channel_title": "...",
      "published_at": "2025-03-01",
      "thumbnail_url": "...",
      "timestamp_seconds": 307,
      "timestamp_display": "5:07",
      "answer_summary": "one-sentence answer in the user's language",
      "exact_quote": "what is actually said at that moment",
      "confidence": "high",
      "watch_url": "https://www.youtube.com/watch?v=abc123&t=307s",
      "embed_url": "https://www.youtube.com/embed/abc123?start=307"
    }
  ],
  "message": null
}
```

- CORS: allow the Vercel frontend origin plus localhost dev origins (configurable via env var `ALLOWED_ORIGINS`).
- All errors return structured JSON `{"detail": "user-friendly message"}` with proper status codes — never a raw stack trace.
- Quota-exceeded (YouTube 403) and Gemini rate limits produce clear, friendly messages; retry Gemini once after a short wait before failing.

## 6. Processing Pipeline (inside POST /api/search)

### Step 1 — Query parsing (Gemini call #1)
Send the raw query to Gemini; require **strict JSON only** (no markdown fences, no preamble):
```json
{
  "search_topic": "concise YouTube search query",
  "channel_name": "channel if mentioned, else null",
  "language": "ISO 639-1 code if mentioned/implied, else null",
  "original_question": "cleaned-up question"
}
```
Parse defensively: strip ``` fences if present, try/except `json.loads`, fall back to raw query as `search_topic` on failure. Manual overrides from the request body take priority over extracted values.

### Step 2 — YouTube search
- If `channel_name` present: resolve to `channelId` via `search.list type=channel`, then search within it.
- `search.list`: `part=snippet`, `type=video`, `maxResults=6`, `q=search_topic`, `relevanceLanguage` if known.
- Prefer `videoCaption='closedCaption'`; if fewer than 3 results, retry without it.
- Cache search results in the TTL cache (1 hour) keyed by parameters.

### Step 3 — Transcript fetching
- Fetch transcripts concurrently (ThreadPoolExecutor) for up to 6 candidates; stop once 4 succeed.
- Language priority: detected language → English → any available (manual before auto-generated).
- Skip videos with disabled/missing transcripts silently.
- Merge raw segments into ~60-second blocks (concatenate text, keep first segment's `start`).
- Cache transcripts (TTL 24 hours) keyed by video ID + language.

### Step 4 — Answer locating (Gemini call #2)
One combined prompt containing the original question plus, per video: title, channel, upload date, and its blocks as `[312s] text...` lines. If total text exceeds ~150,000 characters, truncate each transcript proportionally from the end.

Require strict JSON:
```json
{
  "results": [
    {
      "video_id": "abc123",
      "timestamp_seconds": 312,
      "answer_summary": "one sentence, in the user's language",
      "exact_quote": "what is said at that moment",
      "confidence": "high | medium | low"
    }
  ]
}
```
Rules: only include videos whose transcript genuinely contains an answer; empty list is valid. Subtract 5 seconds from the block start (floor at 0) for context. Order best-first. Same defensive parsing.

### Step 5 — Response assembly
Join Gemini results with video metadata; compute `timestamp_display` (MM:SS or H:MM:SS), `watch_url`, `embed_url`.

## 7. Frontend Requirements

- **Design:** modern, clean, mobile-first. Centered hero search on landing (think a search engine, not a dashboard). Dark-mode friendly is a bonus, not required.
- **Search bar:** large input + button; Enter submits. Placeholder shows an example query.
- **Filters:** collapsible panel with optional Channel input and Language dropdown (Auto/English/Hindi/Urdu + a few more).
- **Loading:** staged indicator with steps ("Understanding your question…", "Searching YouTube…", "Reading transcripts…", "Locating answers…") advanced on a timer while the single API call runs.
- **Result cards:** thumbnail, title, channel, upload date, prominent answer summary, quote styled as a blockquote, confidence badge (green/yellow/gray), and a prominent **▶ Watch answer at 5:07** button opening `watch_url` in a new tab. Clicking the thumbnail expands an inline embedded player (iframe using `embed_url`) so users can watch without leaving the site.
- **Disclaimer** under results: "Answers come from video content and may be outdated — check the upload date."
- **Empty state:** friendly message suggesting rephrasing or removing filters.
- **Error state:** clear message from the API's `detail`, plus a note about the free backend possibly waking up (first request after idle may take ~30–60s on Render free tier) with an automatic retry.
- **Cold-start handling:** on page load, silently ping `GET /health` to wake the backend early.

## 8. Quality & Robustness

- Pydantic models for all request/response bodies; input validation (query length 3–300 chars).
- Basic per-IP rate limiting on the backend (e.g. `slowapi`, 10 searches/minute) to protect free quotas.
- All user-facing generated text (summaries, messages) in the user's query language.
- No secrets in code or git; `.env.example` in both apps documents every variable:
  - Backend: `YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`
  - Frontend: `VITE_API_URL`
- Clear startup errors if keys are missing.

## 9. Deployment (free)

- **Backend → Render free tier:** include `render.yaml` (web service, Python, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/health`, env vars listed). Document that free instances sleep after inactivity.
- **Frontend → Vercel:** standard Vite build; document setting `VITE_API_URL` to the Render URL.
- README must contain step-by-step guides for: getting the free YouTube Data API v3 key, getting the free Gemini key, running both apps locally (two terminals), and deploying both.

## 10. Testing Checklist (verify manually after building)

1. "What is the taxi fare from Almaty city center to Almaty railway station?" → travel-vlog results with working timestamped links.
2. "Burj Khalifa 124th floor ticket price" → timestamps land where prices are discussed.
3. "Video where Dhruv Rathee discusses his views on Rahul Gandhi" → channel filter extracted and applied.
4. Hindi query → Hindi summaries.
5. Nonsense query → clean empty state, no crash.
6. Missing API keys → clear backend startup/UI error.
7. Mobile viewport (375px) → layout fully usable.

## 11. Out of Scope (do not build now)

- Whisper transcription for caption-less videos
- Vector database / embeddings / any database
- User accounts, history, favorites, analytics
- Payments or ads
