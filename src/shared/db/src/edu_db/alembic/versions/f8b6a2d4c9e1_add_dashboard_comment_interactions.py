"""add dashboard comment likes and replies

Revision ID: f8b6a2d4c9e1
Revises: c3a61fd82b10
Create Date: 2026-07-14 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8b6a2d4c9e1"
down_revision: str | Sequence[str] | None = "c3a61fd82b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dashboard_comments", sa.Column("parent_id", sa.String(), nullable=True)
    )
    op.create_foreign_key(
        "fk_dashboard_comments_parent_id",
        "dashboard_comments",
        "dashboard_comments",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_dashboard_comments_parent_id"),
        "dashboard_comments",
        ["parent_id"],
        unique=False,
    )
    op.create_table(
        "dashboard_comment_likes",
        sa.Column("comment_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["comment_id"], ["dashboard_comments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id", "user_id"),
    )
    op.create_index(
        op.f("ix_dashboard_comment_likes_user_id"),
        "dashboard_comment_likes",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dashboard_comment_likes_user_id"),
        table_name="dashboard_comment_likes",
    )
    op.drop_table("dashboard_comment_likes")
    op.drop_index(
        op.f("ix_dashboard_comments_parent_id"), table_name="dashboard_comments"
    )
    op.drop_constraint(
        "fk_dashboard_comments_parent_id", "dashboard_comments", type_="foreignkey"
    )
    op.drop_column("dashboard_comments", "parent_id")
