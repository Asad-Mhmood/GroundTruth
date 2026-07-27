# GroundTruth — YouTube Timestamp Answer Finder

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
   `groundtruth`) → **Create**, then make sure it is selected.
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

### Backend → PythonAnywhere (free, no card required)

The backend ships with `backend/wsgi.py`, which bridges FastAPI (ASGI) to
PythonAnywhere's WSGI hosting via `a2wsgi`.

1. Push this repo to GitHub.
2. Create a free **Beginner** account at <https://www.pythonanywhere.com>
   (no credit card asked).
3. Open a **Bash console** (Consoles tab) and run — replace `YOUR_GITHUB` and
   `YOUR_REPO` with your values:

   ```bash
   git clone -b production https://github.com/YOUR_GITHUB/YOUR_REPO.git
   cd YOUR_REPO/backend
   mkvirtualenv groundtruth --python=python3.11
   pip install -r requirements.txt
   cp .env.example .env
   nano .env    # paste YOUTUBE_API_KEY, GEMINI_API_KEY, save with Ctrl+O, exit Ctrl+X
   ```

   (You'll come back to set `ALLOWED_ORIGINS` after the Vercel deploy.)
4. Go to the **Web** tab → **Add a new web app** → your free domain →
   **Manual configuration** → **Python 3.11**.
5. On the web app page set:
   - **Virtualenv:** `/home/YOUR_USERNAME/.virtualenvs/groundtruth`
   - **WSGI configuration file** (click it to edit) — replace the whole file with:

   ```python
   import sys

   PROJECT_PATH = "/home/YOUR_USERNAME/YOUR_REPO/backend"
   if PROJECT_PATH not in sys.path:
       sys.path.insert(0, PROJECT_PATH)

   from wsgi import application  # noqa: E402,F401
   ```
6. Click the green **Reload** button, then open
   `https://YOUR_USERNAME.pythonanywhere.com/health` — you should see
   `{"status": "ok"}`.

> **PythonAnywhere free-tier notes:**
> - Web apps don't sleep, but they **expire after 3 months** unless you press
>   the "Run until…" extend button on the Web tab (a reminder email is sent).
> - Free accounts route outbound traffic through a proxy with an allowlist.
>   The YouTube Data API and Gemini (both `*.googleapis.com`) are allowed;
>   transcript downloads from `youtube.com` may be blocked — if so, searches
>   return the friendly "no readable captions" message. Test after deploying.
> - To update the app later: `cd YOUR_REPO && git pull`, then Reload on the
>   Web tab.

<details>
<summary>Alternative: Render (works too, but asks for a card on sign-up)</summary>

`render.yaml` at the repo root describes the service: **New → Blueprint**,
pick the repo, fill in `YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`.
Render free instances sleep after ~15 min of inactivity; the frontend's
`/health` ping and auto-retry smooth over the ~30–60 s wake-up.
</details>

### Frontend → Vercel

1. On <https://vercel.com>: **Add New → Project**, import the same repo.
2. Set **Root Directory** to `frontend` (framework preset: Vite — detected
   automatically). If your repo's default branch is not `production`, set the
   production branch to `production` under **Settings → Environments →
   Production** after importing.
3. Add environment variable `VITE_API_URL` = your backend URL
   (e.g. `https://YOUR_USERNAME.pythonanywhere.com`, no trailing slash).
4. Deploy and note your site URL, e.g. `https://groundtruth.vercel.app`.
5. Back on PythonAnywhere, edit `backend/.env` and set
   `ALLOWED_ORIGINS=https://groundtruth.vercel.app,http://localhost:5173`
   (your real Vercel URL), then hit **Reload** on the Web tab.

---

## Environment variables

| App | Variable | Required | Purpose |
|---|---|---|---|
| backend | `YOUTUBE_API_KEY` | yes | YouTube Data API v3 key |
| backend | `GEMINI_API_KEY` | yes | Google Gemini API key |
| backend | `ALLOWED_ORIGINS` | no (has localhost default) | comma-separated CORS origins |
| backend | `GEMINI_MODEL` | no (default `gemini-flash-latest`) | free-tier flash model name |
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
- **Transcripts blocked (429 / bot check)** — YouTube blocks the standard
  caption endpoint on many IPs (data centers, shared ISP connections). The
  backend automatically falls back to yt-dlp's android player client, which
  works without cookies on most blocked IPs. If both strategies fail for every
  video, you'll see the "don't have readable captions" empty state.

## Manual testing checklist

1. "What is the taxi fare from Almaty city center to Almaty railway station?" → travel-vlog results with working timestamped links.
2. "Burj Khalifa 124th floor ticket price" → timestamps land where prices are discussed.
3. "Where did WildLens by Abrar film snow leopards?" → channel filter extracted and applied.
4. Hindi query → Hindi summaries.
5. Nonsense query → clean empty state, no crash.
6. Missing API keys → clear backend startup error.
7. Mobile viewport (375 px) → layout fully usable.
