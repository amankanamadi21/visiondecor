"""add confirmed geometry columns to detected_objects

Revision ID: b626eb003f26
Revises: 63d46e0aa05a
Create Date: 2026-09-08 18:49:41.165761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b626eb003f26'
down_revision: Union[str, None] = '63d46e0aa05a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detected_objects", sa.Column("confirmed_width_cm", sa.Float(), nullable=True))
    op.add_column("detected_objects", sa.Column("confirmed_depth_cm", sa.Float(), nullable=True))
    op.add_column("detected_objects", sa.Column("confirmed_height_cm", sa.Float(), nullable=True))
    op.add_column("detected_objects", sa.Column("confirmed_x_cm", sa.Float(), nullable=True))
    op.add_column("detected_objects", sa.Column("confirmed_y_cm", sa.Float(), nullable=True))
    op.add_column("detected_objects", sa.Column("confirmed_rotation_deg", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("detected_objects", "confirmed_rotation_deg")
    op.drop_column("detected_objects", "confirmed_y_cm")
    op.drop_column("detected_objects", "confirmed_x_cm")
    op.drop_column("detected_objects", "confirmed_height_cm")
    op.drop_column("detected_objects", "confirmed_depth_cm")
    op.drop_column("detected_objects", "confirmed_width_cm")
