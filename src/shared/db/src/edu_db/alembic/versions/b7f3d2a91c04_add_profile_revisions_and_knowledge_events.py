"""add_profile_revisions_and_knowledge_events

Revision ID: b7f3d2a91c04
Revises: a4c8e2f91b6d
Create Date: 2026-06-11 10:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7f3d2a91c04"
down_revision: Union[str, Sequence[str], None] = "a4c8e2f91b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auditable profile and knowledge-state update history."""
    op.add_column(
        "practice_records",
        sa.Column("knowledge_point_id", sa.String(), nullable=True),
    )
    op.create_index(
        op.f("ix_practice_records_knowledge_point_id"),
        "practice_records",
        ["knowledge_point_id"],
    )
    op.create_foreign_key(
        "fk_practice_records_knowledge_point_id",
        "practice_records",
        "knowledge_points",
        ["knowledge_point_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "learner_profile_revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("field_key", sa.String(), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_learner_profile_revisions_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["learner_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("profile_id", "field_key", "source_type", "source_id"):
        op.create_index(
            op.f(f"ix_learner_profile_revisions_{column}"),
            "learner_profile_revisions",
            [column],
        )

    op.create_table(
        "knowledge_state_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("knowledge_state_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("score_before", sa.Float(), nullable=False),
        sa.Column("score_after", sa.Float(), nullable=False),
        sa.Column("impact", sa.Float(), nullable=False),
        sa.Column("was_correct", sa.Boolean(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "score_after >= 0 AND score_after <= 100",
            name="ck_knowledge_state_events_score_after",
        ),
        sa.CheckConstraint(
            "score_before >= 0 AND score_before <= 100",
            name="ck_knowledge_state_events_score_before",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_state_id"],
            ["student_knowledge_states.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "knowledge_point_id",
            "source_type",
            "source_id",
            name="uq_knowledge_state_events_source",
        ),
    )
    for column in (
        "knowledge_state_id",
        "project_id",
        "user_id",
        "knowledge_point_id",
        "event_type",
        "source_type",
        "source_id",
    ):
        op.create_index(
            op.f(f"ix_knowledge_state_events_{column}"),
            "knowledge_state_events",
            [column],
        )


def downgrade() -> None:
    """Remove profile and knowledge-state history support."""
    op.drop_table("knowledge_state_events")
    op.drop_table("learner_profile_revisions")
    op.drop_constraint(
        "fk_practice_records_knowledge_point_id",
        "practice_records",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_practice_records_knowledge_point_id"),
        table_name="practice_records",
    )
    op.drop_column("practice_records", "knowledge_point_id")
