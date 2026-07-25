# VidPoint — YouTube Timestamp Answer Finder

Ask a question in plain language ("What is the taxi fare from Almaty city center
to the railway station?") and get YouTube links that open at the **exact second
the answer is spoken**. Watch 20–30 seconds instead of scrubbing through videos.

- Works with **English, Hindi and Urdu** videos (auto-generated captions included).
- Optional filters: channel/YouTuber name and video language — typed naturally
  in the query ("where Dhruv Rathee discusses…") or set manually in the UI.
- 100% free to build and host: FastAPI on **Render free tier**, React on
  **Vercel**, YouTube Data API v3 (free quota) and Google Gemini (free tier).

## How it works

```
question ──► Gemini #1 (parse query) ──► YouTube search (6 candidates)
        ──► fetch transcripts concurrently (up to 4)
        ──► Gemini #2 (locate answers in 60s transcript blocks)
        ──► results with timestamps, summaries, quotes, confidence
```

No database, no embeddings — the LLM reads transcripts directly. Search results
are cached in memory for 1 hour and transcripts for 24 hours.

## Repository structure

```
├── backend/          FastAPI app (Python)
│   └── app/
│       ├── main.py               routes, CORS, rate limiting, error handling
│       ├── config.py             env loading + startup validation
│       ├── models.py             Pydantic request/response models
│       └── services/
│           ├── query_parser.py   Gemini call #1
│           ├── youtube_search.py YouTube Data API wrapper + cache
│           ├── transcripts.py    concurrent fetching + 60s block merging
│           └── answer_finder.py  Gemini call #2 + link building
├── frontend/         React 18 + Vite + Tailwind CSS
└── render.yaml       Render free-tier deploy config (must live at repo root)
```

---

## 1. Get your free API keys

### YouTube Data API v3 key (free — 10,000 units/day)

1. Go to <https://console.cloud.google.com> and sign in with any Google account.
2. Click the project dropdown (top bar) → **New Project** → name it (e.g.
   `vidpoint`) → **Create**, then make sure it is selected.
3. Open **APIs & Services → Library**, search for **"YouTube Data API v3"**,
   open it and click **Enable**.
4. Go to **APIs & Services → Credentials → + Create Credentials → API key**.
5. Copy the key. (Optional but recommended: click the key → under "API
   restrictions" restrict it to *YouTube Data API v3*.)

No billing/credit card is required. Each search costs ~100–200 units, so the
free quota allows roughly 50–100 searches per day.

### Google Gemini API key (free tier)

1. Go to <https://aistudio.google.com/apikey> and sign in.
2. Click **Create API key** (create it in any project).
3. Copy the key.

The free tier is enough for personal/small-launch use; the app retries once and
shows a friendly message if the per-minute limit is hit.

---

## 2. Run locally (two terminals)

Prerequisites: **Python 3.10+** and **Node.js 18+**.

### Terminal 1 — backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt

# Put your keys in place:
copy .env.example .env        # macOS/Linux: cp .env.example .env
# then edit backend/.env and paste YOUTUBE_API_KEY and GEMINI_API_KEY

uvicorn app.main:app --reload --port 8000
```

The API is now at <http://localhost:8000> (interactive docs at `/docs`).
If a key is missing the server refuses to start with a clear message.

### Terminal 2 — frontend

```bash
cd frontend
npm install

copy .env.example .env        # macOS/Linux: cp .env.example .env
# the default VITE_API_URL=http://localhost:8000 already works locally

npm run dev
```

Open <http://localhost:5173>.

---

## 3. Deploy for free

### Backend → Render (free tier)

**Option A — Blueprint (recommended).** `render.yaml` at the repo root already
describes the service.

1. Push this repo to GitHub.
2. On <https://render.com> (free account): **New → Blueprint**, pick the repo,
   and apply.
3. When prompted, fill in the environment variables:
   - `YOUTUBE_API_KEY` — your key
   - `GEMINI_API_KEY` — your key
   - `ALLOWED_ORIGINS` — your Vercel URL once you have it, e.g.
     `https://vidpoint.vercel.app,http://localhost:5173`
4. Deploy and note the backend URL, e.g. `https://vidpoint-backend.onrender.com`.

**Option B — manual web service.** New → Web Service → pick the repo, set
**Root Directory** `backend`, build command `pip install -r requirements.txt`,
start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check
path `/health`, plan **Free**, and add the same environment variables.

> **Free-tier note:** Render free instances **sleep after ~15 minutes of
> inactivity**; the next request takes ~30–60 s while the instance wakes. The
> frontend pings `/health` on page load and auto-retries to smooth this over.

### Frontend → Vercel

1. On <https://vercel.com>: **Add New → Project**, import the same repo.
2. Set **Root Directory** to `frontend` (framework preset: Vite — detected
   automatically).
3. Add environment variable `VITE_API_URL` = your Render backend URL
   (e.g. `https://vidpoint-backend.onrender.com`, no trailing slash).
4. Deploy.
5. Go back to Render and set `ALLOWED_ORIGINS` to include your Vercel domain
   (e.g. `https://vidpoint.vercel.app`), then let the service redeploy.

---

## Environment variables

| App | Variable | Required | Purpose |
|---|---|---|---|
| backend | `YOUTUBE_API_KEY` | yes | YouTube Data API v3 key |
| backend | `GEMINI_API_KEY` | yes | Google Gemini API key |
| backend | `ALLOWED_ORIGINS` | no (has localhost default) | comma-separated CORS origins |
| backend | `GEMINI_MODEL` | no (default `gemini-2.5-flash`) | free-tier flash model name |
| frontend | `VITE_API_URL` | yes in production | backend base URL |

Never commit `.env` files — they are git-ignored.

## Limits & troubleshooting

- **YouTube quota (403)** — the API returns a friendly 503 explaining the free
  daily quota is exhausted; it resets at midnight Pacific time.
- **Gemini rate limits** — calls are retried once after a short wait, then a
  friendly 503 is returned.
- **Rate limiting** — the backend allows 10 searches/minute per IP to protect
  the free quotas.
- **No captions** — videos without transcripts are skipped silently; if none of
  the candidates have captions you get a clear empty-state message.
- **Transcripts blocked from cloud IPs** — YouTube occasionally blocks caption
  requests from data-center IPs. If transcripts always fail on Render but work
  locally, this is why; it usually recovers, and there is no free workaround.

## Manual testing checklist

1. "What is the taxi fare from Almaty city center to Almaty railway station?" → travel-vlog results with working timestamped links.
2. "Burj Khalifa 124th floor ticket price" → timestamps land where prices are discussed.
3. "Video where Dhruv Rathee discusses his views on Rahul Gandhi" → channel filter extracted and applied.
4. Hindi query → Hindi summaries.
5. Nonsense query → clean empty state, no crash.
6. Missing API keys → clear backend startup error.
7. Mobile viewport (375 px) → layout fully usable.
