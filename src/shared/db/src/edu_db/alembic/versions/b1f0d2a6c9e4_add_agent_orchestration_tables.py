"""add agent orchestration tables

Revision ID: b1f0d2a6c9e4
Revises: 7b6619f0d7a2
Create Date: 2026-06-15 23:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1f0d2a6c9e4"
down_revision: str | Sequence[str] | None = "7b6619f0d7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("trigger", sa.JSON(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("final_result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])
    op.create_index("ix_agent_runs_goal", "agent_runs", ["goal"])
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_events_agent_name", "agent_events", ["agent_name"])
    op.create_index("ix_agent_events_created_at", "agent_events", ["created_at"])
    op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"])
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("ix_agent_events_status", "agent_events", ["status"])

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("artifact_key", sa.String(), nullable=False),
        sa.Column("artifact", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_artifacts_agent_name", "agent_artifacts", ["agent_name"])
    op.create_index("ix_agent_artifacts_artifact_key", "agent_artifacts", ["artifact_key"])
    op.create_index("ix_agent_artifacts_created_at", "agent_artifacts", ["created_at"])
    op.create_index("ix_agent_artifacts_run_id", "agent_artifacts", ["run_id"])

    op.create_table(
        "diagnoses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("diagnosis", sa.JSON(), nullable=False),
        sa.Column("next_actions", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnoses_created_at", "diagnoses", ["created_at"])
    op.create_index("ix_diagnoses_project_id", "diagnoses", ["project_id"])
    op.create_index("ix_diagnoses_run_id", "diagnoses", ["run_id"])
    op.create_index("ix_diagnoses_status", "diagnoses", ["status"])
    op.create_index("ix_diagnoses_user_id", "diagnoses", ["user_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("diagnosis_id", sa.String(), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("recommendation_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("reason_text", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("recommended_by", sa.String(), nullable=True),
        sa.Column("feedback", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])
    op.create_index("ix_recommendations_diagnosis_id", "recommendations", ["diagnosis_id"])
    op.create_index("ix_recommendations_project_id", "recommendations", ["project_id"])
    op.create_index(
        "ix_recommendations_recommendation_type",
        "recommendations",
        ["recommendation_type"],
    )
    op.create_index("ix_recommendations_run_id", "recommendations", ["run_id"])
    op.create_index("ix_recommendations_target_id", "recommendations", ["target_id"])
    op.create_index("ix_recommendations_title", "recommendations", ["title"])
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])

    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("diagnosis_id", sa.String(), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("based_on_recommendation_ids", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_paths_created_at", "learning_paths", ["created_at"])
    op.create_index("ix_learning_paths_diagnosis_id", "learning_paths", ["diagnosis_id"])
    op.create_index("ix_learning_paths_project_id", "learning_paths", ["project_id"])
    op.create_index("ix_learning_paths_run_id", "learning_paths", ["run_id"])
    op.create_index("ix_learning_paths_user_id", "learning_paths", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_paths_user_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_run_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_project_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_diagnosis_id", table_name="learning_paths")
    op.drop_index("ix_learning_paths_created_at", table_name="learning_paths")
    op.drop_table("learning_paths")

    op.drop_index("ix_recommendations_user_id", table_name="recommendations")
    op.drop_index("ix_recommendations_title", table_name="recommendations")
    op.drop_index("ix_recommendations_target_id", table_name="recommendations")
    op.drop_index("ix_recommendations_run_id", table_name="recommendations")
    op.drop_index("ix_recommendations_recommendation_type", table_name="recommendations")
    op.drop_index("ix_recommendations_project_id", table_name="recommendations")
    op.drop_index("ix_recommendations_diagnosis_id", table_name="recommendations")
    op.drop_index("ix_recommendations_created_at", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_diagnoses_user_id", table_name="diagnoses")
    op.drop_index("ix_diagnoses_status", table_name="diagnoses")
    op.drop_index("ix_diagnoses_run_id", table_name="diagnoses")
    op.drop_index("ix_diagnoses_project_id", table_name="diagnoses")
    op.drop_index("ix_diagnoses_created_at", table_name="diagnoses")
    op.drop_table("diagnoses")

    op.drop_index("ix_agent_artifacts_run_id", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_created_at", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_artifact_key", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_agent_name", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")

    op.drop_index("ix_agent_events_status", table_name="agent_events")
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_index("ix_agent_events_event_type", table_name="agent_events")
    op.drop_index("ix_agent_events_created_at", table_name="agent_events")
    op.drop_index("ix_agent_events_agent_name", table_name="agent_events")
    op.drop_table("agent_events")

    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_goal", table_name="agent_runs")
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")
