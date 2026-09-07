"""
Env-driven configuration (brief PART 21 / PART 34.6: no hardcoded secrets,
everything through environment variables). Loaded once at app-factory time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # reads .env in the working directory if present


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    val = os.environ.get(name)
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass
class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://visiondecor:visiondecor_dev_password@localhost:5432/visiondecor",
    )

    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = int(
        os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "60")
    )
    JWT_COOKIE_SECURE: bool = _env_bool("JWT_COOKIE_SECURE", False)
    JWT_COOKIE_NAME: str = "vd_access_token"
    CSRF_COOKIE_NAME: str = "vd_csrf_token"

    CORS_ALLOWED_ORIGINS: list[str] = field(
        default_factory=lambda: _env_list("CORS_ALLOWED_ORIGINS", ["http://localhost:5173"])
    )

    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", "./uploads")
    GENERATED_DIR: str = os.environ.get("GENERATED_DIR", "./generated")
    MAX_UPLOAD_SIZE_MB: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "15"))
    ALLOWED_IMAGE_TYPES: list[str] = field(
        default_factory=lambda: _env_list(
            "ALLOWED_IMAGE_TYPES", ["image/jpeg", "image/png", "image/webp"]
        )
    )

    JOB_RUNNER_MAX_WORKERS: int = int(os.environ.get("JOB_RUNNER_MAX_WORKERS", "2"))

    def validate_for_production(self) -> list[str]:
        """Return a list of problems that must be fixed before deploying with
        FLASK_ENV=production. Called by create_app(); never called for tests."""
        problems = []
        if not self.SECRET_KEY or self.SECRET_KEY.startswith("change-me"):
            problems.append("SECRET_KEY is unset or still the placeholder value")
        if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY.startswith("change-me"):
            problems.append("JWT_SECRET_KEY is unset or still the placeholder value")
        if not self.JWT_COOKIE_SECURE:
            problems.append("JWT_COOKIE_SECURE must be true in production (HTTPS only)")
        return problems


def get_config() -> Config:
    return Config()
