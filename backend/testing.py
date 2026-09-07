"""
Test-only Config override — points at a separate `visiondecor_test` database
so `pytest` never touches development data, and disables features that would
otherwise require real secrets or a running Docker container beyond Postgres.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.config import Config


def get_test_config() -> Config:
    return Config(
        SECRET_KEY="test-secret-key-not-for-production",
        JWT_SECRET_KEY="test-jwt-secret-key-not-for-production",
        DATABASE_URL="postgresql+psycopg2://visiondecor:visiondecor_dev_password@localhost:5432/visiondecor_test",
        JWT_COOKIE_SECURE=False,
        UPLOAD_DIR="./uploads_test",
        MAX_UPLOAD_SIZE_MB=15,
        JOB_RUNNER_MAX_WORKERS=1,
    )
