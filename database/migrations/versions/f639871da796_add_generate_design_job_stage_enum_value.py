"""add generate_design job stage enum value

Revision ID: f639871da796
Revises: 2bebb51afeca
Create Date: 2026-09-06 21:21:34.736734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f639871da796'
down_revision: Union[str, None] = '2bebb51afeca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_stage ADD VALUE IF NOT EXISTS 'generate_design'")


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type.
    # Downgrading this migration is a no-op; the value simply becomes unused.
    pass
