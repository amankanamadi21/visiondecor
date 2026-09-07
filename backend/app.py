"""
Flask application factory (decision D012). Wires together config, database
engine, CORS, error handlers, the background JobRunner, and API blueprints.
"""
from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from backend.config import get_config
from backend.db import init_engine, register_teardown
from backend.errors import register_error_handlers
from backend.services.job_runner import JobRunner


def create_app(config_override=None) -> Flask:
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__)

    config = config_override or get_config()
    app.config["VD_CONFIG"] = config
    app.config["SECRET_KEY"] = config.SECRET_KEY

    if app.config.get("ENV") == "production":
        problems = config.validate_for_production()
        if problems:
            raise RuntimeError(
                "Refusing to start in production with unsafe configuration: " + "; ".join(problems)
            )

    CORS(
        app,
        origins=config.CORS_ALLOWED_ORIGINS,
        supports_credentials=True,  # required so the auth cookie is sent cross-origin (frontend on :5173)
    )

    engine = init_engine(config.DATABASE_URL)
    register_teardown(app)

    def _session_factory():
        from sqlalchemy.orm import Session

        return Session(engine)

    app.config["VD_JOB_RUNNER"] = JobRunner(_session_factory, max_workers=config.JOB_RUNNER_MAX_WORKERS)

    register_error_handlers(app)

    from backend.api.auth import bp as auth_bp
    from backend.api.design import bp as design_bp
    from backend.api.feedback import bp as feedback_bp
    from backend.api.jobs import bp as jobs_bp
    from backend.api.sessions import bp as sessions_bp
    from backend.api.uploads import bp as uploads_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(design_bp)
    app.register_blueprint(feedback_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
