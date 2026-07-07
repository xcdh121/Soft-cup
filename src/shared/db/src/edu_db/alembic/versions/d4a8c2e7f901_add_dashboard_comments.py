"""add dashboard comments

Revision ID: d4a8c2e7f901
Revises: b7f3d2a91c04, b1f0d2a6c9e4
Create Date: 2026-07-07 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d4a8c2e7f901"
down_revision: str | Sequence[str] | None = ("b7f3d2a91c04", "b1f0d2a6c9e4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dashboard_comments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dashboard_comments_user_id"),
        "dashboard_comments",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_dashboard_comments_created_at"),
        "dashboard_comments",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dashboard_comments_created_at"),
        table_name="dashboard_comments",
    )
    op.drop_index(
        op.f("ix_dashboard_comments_user_id"),
        table_name="dashboard_comments",
    )
    op.drop_table("dashboard_comments")
