"""make email nullable to allow tokens without email claim

Revision ID: ade830f47c9e
Revises: f628d758948b
Create Date: 2026-07-28 14:20:35.690025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ade830f47c9e'
down_revision: Union[str, None] = 'f628d758948b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
