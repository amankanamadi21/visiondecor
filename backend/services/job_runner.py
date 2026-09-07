"""
Thread-based background job runner (decision: Batch 1 "Jobs" — background
thread + `jobs` DB table, frontend polls `GET /api/jobs/<id>`).

STATED LIMITATION (recorded against report NFR-5 "Scalability"): this runner
is single-process. It does not distribute work across machines and does not
survive a process restart mid-job. That trade was made deliberately for demo
reliability within a 4-week solo build — see PLAN.md decision log, Batch 1.
Migration path: replace `JobRunner` with an RQ+Redis-backed implementation
that satisfies the same interface (`submit(session_id, stage, fn)`); no
caller code would need to change.

Each submitted callable receives the job's own id and must call
`update_progress(job_id, percent)` itself to report progress; the runner
only manages the QUEUED -> RUNNING -> DONE/FAILED transitions and the
started_at/finished_at timestamps.
"""
from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable

from backend.models.session import Job, JobStage, JobStatus

logger = logging.getLogger("visiondecor.jobs")


class JobRunner:
    def __init__(self, session_factory, max_workers: int = 2):
        """`session_factory` must be a zero-arg callable returning a fresh
        SQLAlchemy Session — the worker thread cannot share the request's
        session, since that session is closed when the request ends."""
        self._session_factory = session_factory
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="vd-job")

    def submit(self, session_id: int, stage: JobStage, work_fn: Callable[[int, Callable[[int], None]], None]) -> Job:
        db = self._session_factory()
        try:
            job = Job(session_id=session_id, stage=stage, status=JobStatus.QUEUED, progress=0)
            db.add(job)
            db.commit()
            job_id = job.id
        finally:
            db.close()

        self._executor.submit(self._run, job_id, work_fn)
        # Re-fetch on the caller's own session isn't necessary — callers only
        # need the id to start polling, so return a lightweight view instead
        # of the (now-detached) ORM object.
        return job_id

    def _run(self, job_id: int, work_fn: Callable[[int, Callable[[int], None]], None]) -> None:
        db = self._session_factory()
        try:
            job = db.get(Job, job_id)
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

            def report_progress(percent: int) -> None:
                p_db = self._session_factory()
                try:
                    p_job = p_db.get(Job, job_id)
                    p_job.progress = max(0, min(100, percent))
                    p_db.commit()
                finally:
                    p_db.close()

            work_fn(job_id, report_progress)

            job = db.get(Job, job_id)
            job.status = JobStatus.DONE
            job.progress = 100
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:  # noqa: BLE001 — must not crash the worker thread
            logger.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
            db.rollback()
            job = db.get(Job, job_id)
            job.status = JobStatus.FAILED
            # A stage may raise PipelineStageError with a specific, user-safe
            # code/message (e.g. "room analysis not available yet") — use it
            # verbatim rather than collapsing every failure into one generic
            # message (brief PART 15). Any other exception (a real bug) still
            # gets the generic message; its traceback is logged above, never
            # shown to the user.
            code = getattr(exc, "code", None)
            message = getattr(exc, "message", None)
            job.error_code = code or "stage_failed"
            job.error_message = message or "This step could not be completed. Please try again."
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def shutdown(self, wait: bool = False) -> None:
        """`wait=True` blocks until every submitted job has finished (used by
        the test suite to drain jobs before truncating tables — see
        tests/conftest.py). `wait=False` (the production default, e.g. at
        app/process shutdown) does not block the caller."""
        self._executor.shutdown(wait=wait)
