"""learning evidence and privacy-safe collective insights

Revision ID: f6c8d3e15220
Revises: e5b7a2c94110
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f6c8d3e15220"
down_revision: str | None = "e5b7a2c94110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_evidence_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_point_id",
            sa.String(),
            sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    for name in (
        "project_id",
        "user_id",
        "knowledge_point_id",
        "event_type",
        "source_type",
        "source_id",
        "occurred_at",
        "created_at",
    ):
        op.create_index(
            f"ix_learning_evidence_events_{name}",
            "learning_evidence_events",
            [name],
        )

    op.create_table(
        "collective_insights",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_point_id",
            sa.String(),
            sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pattern_type", sa.String(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("aggregate", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "version",
            sa.String(),
            nullable=False,
            server_default="collective-v1",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "sample_size >= 0", name="ck_collective_insights_sample_size"
        ),
        sa.UniqueConstraint(
            "course_id",
            "knowledge_point_id",
            "pattern_type",
            "window_start",
            "window_end",
            name="uq_collective_insights_window",
        ),
    )
    for name in (
        "course_id",
        "knowledge_point_id",
        "pattern_type",
        "window_start",
        "window_end",
        "expires_at",
        "created_at",
    ):
        op.create_index(
            f"ix_collective_insights_{name}", "collective_insights", [name]
        )


def downgrade() -> None:
    op.drop_table("collective_insights")
    op.drop_table("learning_evidence_events")
