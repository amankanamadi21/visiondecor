"""
Room image upload — FR-2 entry point. Validates the file (magic bytes, size,
corruption), strips EXIF/GPS, dedupes by content hash, stores it under a
per-user path, records a RoomImage row, and enqueues the `preprocess`
background job.

Detection/segmentation/style recognition as REAL, general-purpose stages
are explicitly NOT triggered here — see backend/services/pipeline_stages.py
and decision D018/D022. However, if the uploaded image's content hash
matches one of the shipped sample-room images, its corresponding fixture
RoomAnalysis is auto-attached (decision D022) — this is recognition of a
known, fixed set of demo images, not general room analysis, and it never
happens for a genuine, unrecognized user photo.
"""
from __future__ import annotations

import os

from flask import Blueprint, current_app, g, jsonify, request

from backend.api.sessions import get_owned_session
from backend.db import get_session
from backend.errors import validation_error
from backend.models.room import RoomImage
from backend.models.session import JobStage
from backend.services.image_validation import validate_and_clean_image
from backend.services.pipeline_stages import run_preprocess
from backend.utils.auth_decorators import login_required

bp = Blueprint("uploads", __name__, url_prefix="/api/sessions")


@bp.post("/<int:session_id>/image")
@login_required
def upload_room_image(session_id: int):
    config = current_app.config["VD_CONFIG"]
    db = get_session()
    design_session = get_owned_session(db, session_id, g.user.id)

    if "image" not in request.files:
        raise validation_error("No image file provided.", {"field": "image"})
    file_storage = request.files["image"]
    raw_bytes = file_storage.read()

    validated = validate_and_clean_image(
        raw_bytes, config.MAX_UPLOAD_SIZE_MB, config.ALLOWED_IMAGE_TYPES
    )

    user_dir = os.path.join(config.UPLOAD_DIR, str(g.user.id), str(session_id))
    os.makedirs(user_dir, exist_ok=True)
    original_path = os.path.join(user_dir, f"{validated.sha256_hex}.jpg")
    with open(original_path, "wb") as f:
        f.write(validated.clean_bytes)

    # Dedupe: if this exact (already-cleaned) image was uploaded before for
    # this session, reuse the row instead of creating a duplicate.
    existing = (
        db.query(RoomImage)
        .filter_by(session_id=session_id, file_hash=validated.sha256_hex)
        .first()
    )
    if existing is not None:
        room_image = existing
    else:
        room_image = RoomImage(
            session_id=session_id,
            original_path=original_path,
            width=validated.width,
            height=validated.height,
            file_hash=validated.sha256_hex,
            quality_flags={},
        )
        db.add(room_image)
        db.commit()

    # D022: recognize a shipped sample-room image and auto-attach its
    # fixture RoomAnalysis — idempotent (skipped if this room_image already
    # has one, e.g. from a prior identical upload for this same session).
    from ai.room_analysis.db_adapter import persist_fixture
    from ai.room_analysis.fixtures import get_fixture
    from ai.room_analysis.sample_rooms import fixture_for_uploaded_hash

    fixture_name = fixture_for_uploaded_hash(validated.sha256_hex)
    if fixture_name is not None and not room_image.analyses:
        persist_fixture(db, session_id, get_fixture(fixture_name))

    processed_path = os.path.join(user_dir, f"{validated.sha256_hex}_processed.jpg")

    job_runner = current_app.config["VD_JOB_RUNNER"]

    def _work(job_id: int, report_progress):
        run_preprocess(job_id, report_progress, image_path=original_path, output_path=processed_path)
        # Record the processed path on a fresh session — the worker thread
        # cannot reuse the request-scoped session `db` above.
        from backend.db import get_engine
        from sqlalchemy.orm import Session as SASession

        with SASession(get_engine()) as s:
            img = s.get(RoomImage, room_image.id)
            img.processed_path = processed_path
            s.commit()

    job_id = job_runner.submit(session_id, JobStage.PREPROCESS, _work)

    return (
        jsonify(
            {
                "room_image": {
                    "id": room_image.id,
                    "width": room_image.width,
                    "height": room_image.height,
                },
                # Lets the frontend show "Sample room (demo data)" immediately
                # rather than waiting for the recommendation/layout response
                # to discover it — D022 disclosure guardrail.
                "is_sample_room": fixture_name is not None,
                "job_id": job_id,
            }
        ),
        202,
    )
