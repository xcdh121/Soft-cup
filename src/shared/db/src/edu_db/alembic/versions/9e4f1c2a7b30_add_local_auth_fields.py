"""add self-hosted authentication fields

Revision ID: 9e4f1c2a7b30
Revises: f8b6a2d4c9e1
Create Date: 2026-07-14 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e4f1c2a7b30"
down_revision: str | Sequence[str] | None = "f8b6a2d4c9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_admin", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
