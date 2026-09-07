"""
SQLAlchemy engine/session wiring. One process-wide engine; a scoped session
per request, torn down in the Flask app's teardown handler.
"""
from __future__ import annotations

from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_SessionFactory = None


def init_engine(database_url: str):
    global _engine, _SessionFactory
    _engine = create_engine(database_url, pool_pre_ping=True, future=True)
    _SessionFactory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine():
    if _engine is None:
        raise RuntimeError("Engine not initialized — call init_engine() from create_app() first")
    return _engine


def get_session() -> Session:
    """Return the current request's SQLAlchemy session, creating one if needed."""
    if "db_session" not in g:
        if _SessionFactory is None:
            raise RuntimeError("Session factory not initialized — call init_engine() first")
        g.db_session = _SessionFactory()
    return g.db_session


def register_teardown(app: Flask) -> None:
    @app.teardown_appcontext
    def _close_session(exception=None):  # noqa: ANN001
        session = g.pop("db_session", None)
        if session is not None:
            if exception is not None:
                session.rollback()
            session.close()
