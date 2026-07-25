"""Environment loading and application settings."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "").strip()
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        raw_origins = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
        )
        self.allowed_origins: list[str] = [
            origin.strip() for origin in raw_origins.split(",") if origin.strip()
        ]

        self._validate()

    def _validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("YOUTUBE_API_KEY", self.youtube_api_key),
                ("GEMINI_API_KEY", self.gemini_api_key),
            )
            if not value
        ]
        if missing:
            sys.stderr.write(
                "\n"
                + "=" * 62
                + "\n  VidPoint backend cannot start: missing environment "
                + ("variable" if len(missing) == 1 else "variables")
                + "\n\n"
                + "".join(f"    - {name}\n" for name in missing)
                + "\n  Fix: copy backend/.env.example to backend/.env and fill in\n"
                "  your keys. The README explains how to get both for free.\n"
                + "=" * 62
                + "\n\n"
            )
            raise SystemExit(1)


settings = Settings()
