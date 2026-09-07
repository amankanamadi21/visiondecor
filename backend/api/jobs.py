"""
Job polling — frontend polls this endpoint while a background job runs
(Batch 1 thread-based JobRunner). Per-user authorization: a job is only
visible to the owner of the design_session it belongs to.
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify

from backend.api.sessions import get_owned_session
from backend.db import get_session
from backend.errors import not_found
from backend.models.session import Job
from backend.utils.auth_decorators import login_required

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def _job_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "session_id": job.session_id,
        "stage": job.stage.value,
        "status": job.status.value,
        "progress": job.progress,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@bp.get("/<int:job_id>")
@login_required
def get_job(job_id: int):
    db = get_session()
    job = db.get(Job, job_id)
    if job is None:
        raise not_found("Job not found.")
    # Confirms the job's session belongs to the caller — raises 404 otherwise.
    get_owned_session(db, job.session_id, g.user.id)
    return jsonify({"job": _job_dict(job)})
