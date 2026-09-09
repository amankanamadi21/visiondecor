"""
Shared pytest fixtures. Uses a real PostgreSQL database (visiondecor_test) —
not SQLite or mocks — so tests exercise the actual pgvector/JSONB/Enum types
the app depends on. The test DB's schema is rebuilt fresh for every test
session and every test runs inside a transaction that is rolled back, so
tests never leak state into each other.
"""
from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app import create_app
from backend.models import Base
from backend.testing import get_test_config

TEST_CONFIG = get_test_config()


def _admin_engine():
    """Engine connected to the default 'postgres' maintenance DB, used only
    to create/drop the visiondecor_test database itself."""
    admin_url = TEST_CONFIG.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    return create_engine(admin_url, isolation_level="AUTOCOMMIT")


# Reference/catalog data — seeded once per test session (embedding 40
# principles is real, non-trivial compute; redoing it per-test would make
# the suite unusably slow) and deliberately EXCLUDED from the per-test
# TRUNCATE in _clean_tables below. This is data the app ships with, not
# data a test creates, so it behaves like a fixture of the schema itself.
REFERENCE_TABLES = {"furniture_catalog", "design_principles"}


def _seed_reference_data(engine):
    from ai.recommendation.embeddings import embed_texts
    from ai.recommendation.principles_data import PRINCIPLES
    from backend.models import DesignPrinciple, FurnitureCatalogItem
    from scripts.seed_catalog import CATALOG_SEED

    from datetime import date as _date

    with Session(engine) as db:
        for (name, category, styles, color, price, currency, w, d, h, image_url, product_url) in CATALOG_SEED:
            db.add(
                FurnitureCatalogItem(
                    name=name, category=category, style_tags=styles, color=color,
                    price=price, currency=currency, width_cm=w, depth_cm=d, height_cm=h,
                    image_url=image_url, product_url=product_url,
                    price_verified_at=_date(2026, 9, 9),
                )
            )

        texts = [f"{p['title']}. {p['body']}" for p in PRINCIPLES]
        vectors = embed_texts(texts)
        for principle, vector in zip(PRINCIPLES, vectors):
            db.add(
                DesignPrinciple(
                    code=principle["code"], category=principle["category"], title=principle["title"],
                    body=principle["body"], applies_to_room_types=principle["applies_to_room_types"],
                    applies_to_styles=principle["applies_to_styles"], source_note=principle["source_note"],
                    embedding=vector.tolist(),
                )
            )
        db.commit()


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    admin_engine = _admin_engine()
    db_name = TEST_CONFIG.DATABASE_URL.rsplit("/", 1)[1]
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    admin_engine.dispose()

    engine = create_engine(TEST_CONFIG.DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    _seed_reference_data(engine)
    engine.dispose()

    yield

    if os.path.isdir(TEST_CONFIG.UPLOAD_DIR):
        shutil.rmtree(TEST_CONFIG.UPLOAD_DIR)


@pytest.fixture()
def app():
    application = create_app(config_override=TEST_CONFIG)
    application.config["TESTING"] = True
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_tables(app):
    """Truncate every table between tests instead of relying on nested
    transactions — simpler to reason about given the app manages its own
    sessions per-request via Flask's app context.

    IMPORTANT ordering: a test may enqueue a background job (JobRunner,
    Batch 1) and return without waiting for it to finish. If we truncated
    tables while that thread is still writing, the thread's UPDATE could hit
    a row that TRUNCATE ... RESTART IDENTITY just removed (job_id reused by
    the next test), producing sporadic cross-test failures. So we always
    fully drain the current app's JobRunner (blocking until every submitted
    job completes) before truncating anything.
    """
    yield
    app.config["VD_JOB_RUNNER"].shutdown(wait=True)

    from backend.db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename NOT IN ('alembic_version')"
            )
        ).scalars().all()
        tables = [t for t in tables if t not in REFERENCE_TABLES]
        if tables:
            conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
            conn.commit()


@pytest.fixture()
def csrf_headers(client):
    """Returns a callable that produces the X-CSRF-Token header from the
    client's current CSRF cookie — mirrors what the real frontend must do
    (double-submit cookie pattern, decision D014). Call it fresh after each
    login/register, since the CSRF token rotates whenever the auth cookie is
    reissued."""

    def _headers():
        cookie = client.get_cookie("vd_csrf_token")
        assert cookie is not None, "CSRF cookie missing — are you logged in?"
        return {"X-CSRF-Token": cookie.value}

    return _headers
