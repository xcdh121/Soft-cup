"""Add user avatar URL.

Revision ID: a6d9e3f1b742
Revises: f4a7c2d9e510
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6d9e3f1b742"
down_revision: str | Sequence[str] | None = "f4a7c2d9e510"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
