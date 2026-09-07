"""fix generate_design job stage enum casing

Revision ID: dae5fd7e07e8
Revises: f639871da796
Create Date: 2026-09-07 00:24:33.749206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dae5fd7e07e8'
down_revision: Union[str, None] = 'f639871da796'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's Enum type stores the Python member's NAME (e.g.
    # 'PREPROCESS'), not its .value ('preprocess') — confirmed by inspecting
    # existing rows. The prior migration (f639871da796) added the value
    # 'generate_design' (lowercase), which does not match the Python enum
    # member JobStage.GENERATE_DESIGN and would fail on first use. This adds
    # the correct uppercase label; the lowercase one is inert, harmless dead
    # weight (Postgres cannot remove enum values, so it must stay).
    op.execute("ALTER TYPE job_stage ADD VALUE IF NOT EXISTS 'GENERATE_DESIGN'")


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type.
    pass
