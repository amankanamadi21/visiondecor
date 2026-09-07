#!/usr/bin/env python3
"""
DEV-ONLY: attach a synthetic room fixture (D018) to an existing design
session, so the recommendation/layout pipeline can be exercised end-to-end
through the real API before real CV (detection + segmentation) exists.

This writes RoomAnalysis/DetectedObject/StylePrediction rows tagged
model_versions={"source": "fixture", ...} — the production
recommendation-trigger endpoint accepts these exactly as it would accept
real ones (same schema), but nothing here is presented to a real user as
genuine detection output; this script exists only for development,
testing, and demoing the algorithmic core (see PLAN.md D018 guardrail).

Usage:
    source .venv/bin/activate
    python scripts/seed_fixture_analysis.py <session_id> <fixture_name>

Example:
    python scripts/seed_fixture_analysis.py 1 bedroom_small_scandinavian
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.room_analysis.db_adapter import persist_fixture
from ai.room_analysis.fixtures import FIXTURES, get_fixture
from backend.config import get_config
from backend.db import init_engine
from sqlalchemy.orm import Session


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        print(f"Available fixtures: {sorted(FIXTURES)}")
        return 1

    session_id, fixture_name = int(sys.argv[1]), sys.argv[2]
    fixture = get_fixture(fixture_name)

    config = get_config()
    engine = init_engine(config.DATABASE_URL)
    with Session(engine) as db:
        analysis = persist_fixture(db, session_id, fixture)
        print(f"Attached fixture '{fixture_name}' to session {session_id} as RoomAnalysis id={analysis.id}")
        print("This is DEV/TEST data (model_versions.source='fixture') — not real detection output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
