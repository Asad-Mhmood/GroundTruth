"""VidPoint API — FastAPI app, CORS, rate limiting, and routes."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import settings
from .models import AppError, SearchRequest, SearchResponse
from .services.answer_finder import find_answers
from .services.query_parser import parse_query
from .services.transcripts import fetch_transcripts
from .services.youtube_search import search_videos

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="VidPoint API",
    description="Find YouTube videos with exact timestamps where your question is answered.",
    version="1.0.0",
)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "You're searching a little too fast. "
            "Please wait a minute and try again."
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Please enter a question between 3 and 300 characters long."
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side. Please try again."},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
@limiter.limit("10/minute")
def search(request: Request, body: SearchRequest) -> SearchResponse:
    # Step 1 — understand the question (Gemini call #1).
    parsed = parse_query(body.query)
    if body.channel_override:
        parsed.channel_name = body.channel_override
    if body.language_override:
        parsed.language = body.language_override.lower()[:2]

    # Step 2 — find candidate videos on YouTube.
    videos = search_videos(parsed.search_topic, parsed.channel_name, parsed.language)
    if not videos:
        return SearchResponse(
            parsed=parsed,
            results=[],
            message="No YouTube videos matched this search. "
            "Try rephrasing your question or removing filters.",
        )

    # Step 3 — fetch transcripts for the candidates.
    transcripts = fetch_transcripts([v["video_id"] for v in videos], parsed.language)
    if not transcripts:
        return SearchResponse(
            parsed=parsed,
            results=[],
            message="The videos we found don't have readable captions. "
            "Try rephrasing your question — different videos may have transcripts.",
        )

    # Steps 4–5 — locate answers (Gemini call #2) and assemble the response.
    results = find_answers(parsed.original_question, videos, transcripts)
    message = None
    if not results:
        message = (
            "We read the top videos but couldn't find a moment that clearly "
            "answers this. Try rephrasing, or remove the channel/language filter."
        )
    return SearchResponse(parsed=parsed, results=results, message=message)
