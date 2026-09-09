"""add product_url and price_verified_at to furniture_catalog

Revision ID: 5219def286a1
Revises: b626eb003f26
Create Date: 2026-09-09 11:21:59.352947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5219def286a1'
down_revision: Union[str, None] = 'b626eb003f26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("furniture_catalog", sa.Column("product_url", sa.String(length=500), nullable=True))
    op.add_column("furniture_catalog", sa.Column("price_verified_at", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("furniture_catalog", "price_verified_at")
    op.drop_column("furniture_catalog", "product_url")
