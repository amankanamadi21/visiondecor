"""
Sample-room recognition (decision D022). A small, fixed set of shipped
placeholder images stand in for real user photos in the demo, each mapped
to one of the fixtures in fixtures.py. A user "uploads" a sample exactly
the way they would upload their own photo (same endpoint, same validation);
the backend recognizes it by content hash and auto-attaches the matching
fixture's RoomAnalysis — see backend/api/uploads.py.

The hash used for recognition MUST be computed the same way
image_validation.validate_and_clean_image computes RoomImage.file_hash
(hash of the re-encoded, EXIF-stripped bytes) — hashing the raw file
differently would never match what actually gets stored.

⚠ These are placeholder images (a colored rectangle with a text label),
generated for wiring/testing purposes — see PLAN.md D022. Before an actual
demo or submission, replace the files in frontend/public/samples/ with real
photos of the team's own rooms (see PLAN.md section G: "the demo must not
run on training data").
"""
from __future__ import annotations

import os

from ai.room_analysis.fixtures import FIXTURES
from backend.services.image_validation import validate_and_clean_image

SAMPLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "samples")
)

# filename (without extension) -> fixture name. Must be a 1:1 subset of FIXTURES.
SAMPLE_ROOM_FIXTURES: dict[str, str] = {name: name for name in FIXTURES}

_MAX_SAMPLE_SIZE_MB = 15
_ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"]

_hash_cache: dict[str, str] | None = None


def _compute_canonical_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        raw_bytes = f.read()
    validated = validate_and_clean_image(raw_bytes, _MAX_SAMPLE_SIZE_MB, _ALLOWED_TYPES)
    return validated.sha256_hex


def get_hash_to_fixture_map() -> dict[str, str]:
    """{canonical_content_hash: fixture_name}, computed once per process and
    cached. Recomputing per-request would be wasteful; the sample files are
    static assets that don't change at runtime."""
    global _hash_cache
    if _hash_cache is not None:
        return _hash_cache

    mapping: dict[str, str] = {}
    for filename, fixture_name in SAMPLE_ROOM_FIXTURES.items():
        path = os.path.join(SAMPLES_DIR, f"{filename}.jpg")
        if os.path.exists(path):
            mapping[_compute_canonical_hash(path)] = fixture_name
    _hash_cache = mapping
    return mapping


def fixture_for_uploaded_hash(sha256_hex: str) -> str | None:
    """Returns the fixture name if `sha256_hex` matches a known sample room,
    else None (a genuine user photo)."""
    return get_hash_to_fixture_map().get(sha256_hex)
