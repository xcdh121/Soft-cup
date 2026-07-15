"""add local account username

Revision ID: 1b7d4e9a6c20
Revises: 9e4f1c2a7b30
Create Date: 2026-07-14 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1b7d4e9a6c20"
down_revision: str | Sequence[str] | None = "9e4f1c2a7b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.execute(
        "UPDATE users SET username = 'legacy_' || substr(md5(id), 1, 16) "
        "WHERE username IS NULL"
    )
    op.alter_column("users", "username", nullable=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "username")
