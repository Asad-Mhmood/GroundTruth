# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

VidPoint — a monorepo with two independently deployed apps: a FastAPI backend
(`backend/`) and a React 18 + Vite + Tailwind frontend (`frontend/`). A user
asks a natural-language question; the backend returns YouTube links that open at
the exact second the answer is spoken.

`PROJECT_SPEC (1).md` is the original build spec and remains the source of truth
for intended behavior (API shape, pipeline rules, out-of-scope items). Notably
out of scope: databases, embeddings/vector search, Whisper transcription, user
accounts. The app is stateless apart from in-process caches.

## Commands

Backend (from `backend/`, venv at `backend/.venv`):

```bash
.venv\Scripts\activate            # Windows; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000    # docs at /docs
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # production build (what Vercel runs)
```

Both apps need a `.env` copied from their `.env.example`. There is **no test
suite, linter, or formatter configured** in either app — verification is manual
(see the checklist at the end of `README.md`). To exercise the backend directly,
POST to `/api/search` rather than adding a test harness unless asked.

## Architecture

### The request pipeline

`POST /api/search` in `backend/app/main.py` runs the whole pipeline inline, in
this order, and each stage lives in `backend/app/services/`:

1. `query_parser.parse_query` — **Gemini call #1**: raw question → `search_topic`,
   `channel_name`, `language`, cleaned `original_question`. Request-body
   overrides (`channel_override`, `language_override`) are applied *after* this
   and win over what Gemini extracted.
2. `youtube_search.search_videos` — YouTube Data API v3, 6 candidates. Tries
   `videoCaption=closedCaption` first and re-queries without it if fewer than 3
   results. Channel names cost an extra `search.list type=channel` call.
3. `transcripts.fetch_transcripts` — concurrent fetch, stops at 4 successes,
   merges caption segments into ~60s blocks keyed by the first segment's start.
4. `answer_finder.find_answers` — **Gemini call #2**: one prompt containing every
   transcript as `[312s] text…` lines; the model returns which video/second
   answers the question. 5 seconds are subtracted from the returned timestamp for
   lead-in context, and `watch_url`/`embed_url` are built here.

Each stage returning empty short-circuits into a `SearchResponse` with an empty
`results` list and a user-facing `message` — an empty result is a normal outcome,
not an error. Keep it that way.

### Things that will bite you

- **`config.py` validates at import time and calls `raise SystemExit(1)`** if
  `YOUTUBE_API_KEY` or `GEMINI_API_KEY` is missing. `settings` is a module-level
  singleton, so *importing* `app.main` (or anything under `app.services`) without
  a populated `backend/.env` kills the process. It loads `.env` by absolute path
  because PythonAnywhere doesn't start in the project directory.
- **The route handler is `def`, not `async def`.** The entire pipeline is
  blocking I/O and relies on FastAPI's threadpool. `slowapi`'s `@limiter.limit`
  also requires the `request: Request` parameter in the signature — don't remove it.
- **Both caches are in-process** (`cachetools.TTLCache` + a `Lock`): searches 1h,
  transcripts 24h. They're per-worker and die on restart/reload. The transcript
  cache also stores `None` (negative caching), so a video that failed once won't
  be retried for 24 hours in that process.
- **Transcripts have two fetch strategies** and both are needed:
  `youtube-transcript-api` first, then a `yt-dlp` fallback pinned to the
  `android` player client, which bypasses YouTube's watch-page bot check that
  429s many server IPs. Track selection priority (preferred language → English →
  anything; manual before auto-generated) is duplicated in both paths — change
  them together.
- **All Gemini output is parsed defensively** via `gemini.generate_json` →
  `parse_json_loose` (strips ``` fences, falls back to outermost braces, returns
  `None`). Callers must handle `None`; `parse_query` degrades to using the raw
  query, `find_answers` returns `[]`. Never assume a well-formed model response.
- **Error surface:** anything user-facing raises `AppError(status, detail)` from
  `models.py`; handlers in `main.py` turn it, rate limits, validation errors and
  unhandled exceptions into `{"detail": "..."}`. Stack traces must never reach
  the client, and messages are written for end users, not developers.
- The frontend's `LoadingSteps` progression is **timer-driven and cosmetic** —
  there is one API call, no streaming or progress events.
- `frontend/src/api.js` treats 502/503/504 and network failures as `retryable`;
  `App.jsx` auto-retries twice with a 12s gap to cover free-tier cold starts, and
  pings `/health` on page load for the same reason.

### Prompting

Both prompts live as module constants (`query_parser._PROMPT`,
`answer_finder._PROMPT_HEADER`) and are `.format()`-ed, so literal braces in the
JSON examples are doubled (`{{`). Quotes in user input are replaced with `'`
before interpolation. Summaries must come back in the *question's* language
(Hindi/Urdu/English all supported) — preserve that instruction when editing.

Model comes from `GEMINI_MODEL`, defaulting to the `gemini-flash-latest` alias so
it survives model retirements. Keep the default on a free-tier flash model.

## Deployment

- The **`production` branch** is what deploys; `main` is the default branch for PRs.
- Backend → PythonAnywhere via `backend/wsgi.py` (a2wsgi ASGI→WSGI bridge).
  `render.yaml` documents an alternative Render deploy and **must stay at the
  repo root** — Render only reads it from there, with `rootDir: backend`.
- Frontend → Vercel with root directory `frontend` and `VITE_API_URL` pointing at
  the backend (no trailing slash). The backend's `ALLOWED_ORIGINS` must then list
  that Vercel URL or CORS blocks every request.
