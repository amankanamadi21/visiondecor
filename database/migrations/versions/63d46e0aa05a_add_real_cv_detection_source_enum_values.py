"""add real cv detection source enum values

Revision ID: 63d46e0aa05a
Revises: dae5fd7e07e8
Create Date: 2026-09-08 16:16:27.674766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63d46e0aa05a'
down_revision: Union[str, None] = 'dae5fd7e07e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Distinguishes genuine real-photo CV output (pixel-space bbox, from the
    # 2026-09-08 detection+segmentation batch) from the pre-existing
    # DETECTION/SEGMENTATION values, which are cm-space and reserved for dev
    # fixture rows (persist_fixture) that load_room_model_from_db feeds into
    # the recommendation/layout engine. REAL_DETECTION/REAL_SEGMENTATION rows
    # are deliberately NOT read by that function this batch (display-only
    # scope decision) — see ai/room_analysis/db_adapter.py.
    #
    # As with the job_stage enum fix (dae5fd7e07e8): SQLAlchemy's Enum column
    # stores the Python member's NAME, not its .value, so the Postgres labels
    # must be uppercase to match JobStage/DetectionSource member names.
    op.execute("ALTER TYPE detection_source ADD VALUE IF NOT EXISTS 'REAL_DETECTION'")
    op.execute("ALTER TYPE detection_source ADD VALUE IF NOT EXISTS 'REAL_SEGMENTATION'")


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type.
    pass
