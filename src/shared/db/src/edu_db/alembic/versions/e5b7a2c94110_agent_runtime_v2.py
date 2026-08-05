"""agent runtime v2

Revision ID: e5b7a2c94110
Revises: f4a7c2d9e510
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e5b7a2c94110"
down_revision: str | None = "f4a7c2d9e510"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("failure_code", sa.String(), nullable=True))
    op.add_column("agent_runs", sa.Column("request_meta", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column(
        "agent_runs",
        sa.Column(
            "orchestration_version",
            sa.String(),
            nullable=False,
            server_default="orchestration-v2",
        ),
    )
    op.add_column("agent_runs", sa.Column("context_snapshot_id", sa.String(), nullable=True))
    op.add_column("agent_runs", sa.Column("budget", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("agent_runs", sa.Column("usage", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("agent_runs", sa.Column("versions", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column(
        "agent_runs",
        sa.Column("last_event_sequence", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("agent_runs", sa.Column("idempotency_key", sa.String(), nullable=True))
    op.create_index("ix_agent_runs_failure_code", "agent_runs", ["failure_code"])
    op.create_unique_constraint(
        "uq_agent_runs_owner_idempotency",
        "agent_runs",
        ["user_id", "project_id", "idempotency_key"],
    )

    op.add_column(
        "agent_events",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        WITH ranked AS (
          SELECT id, ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY created_at, id) AS seq
          FROM agent_events
        )
        UPDATE agent_events SET sequence = ranked.seq FROM ranked WHERE agent_events.id = ranked.id
        """
    )
    op.alter_column("agent_events", "sequence", nullable=False)
    op.create_index("ix_agent_events_sequence", "agent_events", ["sequence"])
    op.create_unique_constraint(
        "uq_agent_events_sequence", "agent_events", ["run_id", "sequence"]
    )

    for name, column in (
        ("schema_version", sa.Column("schema_version", sa.String(), nullable=False, server_default="1.0")),
        ("artifact_version", sa.Column("artifact_version", sa.Integer(), nullable=False, server_default="1")),
        ("content_hash", sa.Column("content_hash", sa.String(), nullable=True)),
        ("source_snapshot_id", sa.Column("source_snapshot_id", sa.String(), nullable=True)),
        ("dependency_hash", sa.Column("dependency_hash", sa.String(), nullable=True)),
        ("validation_status", sa.Column("validation_status", sa.String(), nullable=False, server_default="valid")),
    ):
        op.add_column("agent_artifacts", column)
    op.create_index("ix_agent_artifacts_content_hash", "agent_artifacts", ["content_hash"])
    op.create_index("ix_agent_artifacts_validation_status", "agent_artifacts", ["validation_status"])

    op.create_table(
        "agent_run_steps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("depends_on", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("input_artifact_versions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("output_artifact_versions", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.UniqueConstraint("run_id", "node_id", name="uq_agent_run_steps_node"),
    )
    op.create_index("ix_agent_run_steps_run_id", "agent_run_steps", ["run_id"])
    op.create_index("ix_agent_run_steps_node_id", "agent_run_steps", ["node_id"])
    op.create_index("ix_agent_run_steps_agent_name", "agent_run_steps", ["agent_name"])
    op.create_index("ix_agent_run_steps_status", "agent_run_steps", ["status"])
    op.create_index("ix_agent_run_steps_error_code", "agent_run_steps", ["error_code"])

    op.create_table(
        "agent_run_feedback",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_agent_run_feedback_rating"),
    )
    op.create_index("ix_agent_run_feedback_run_id", "agent_run_feedback", ["run_id"])
    op.create_index("ix_agent_run_feedback_user_id", "agent_run_feedback", ["user_id"])
    op.create_index("ix_agent_run_feedback_action", "agent_run_feedback", ["action"])
    op.create_index("ix_agent_run_feedback_created_at", "agent_run_feedback", ["created_at"])

def downgrade() -> None:
    op.drop_table("agent_run_feedback")
    op.drop_table("agent_run_steps")
    op.drop_constraint("uq_agent_events_sequence", "agent_events", type_="unique")
    op.drop_index("ix_agent_events_sequence", table_name="agent_events")
    op.drop_column("agent_events", "sequence")
    op.drop_index("ix_agent_artifacts_validation_status", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_content_hash", table_name="agent_artifacts")
    for name in (
        "validation_status",
        "dependency_hash",
        "source_snapshot_id",
        "content_hash",
        "artifact_version",
        "schema_version",
    ):
        op.drop_column("agent_artifacts", name)
    op.drop_constraint("uq_agent_runs_owner_idempotency", "agent_runs", type_="unique")
    op.drop_index("ix_agent_runs_failure_code", table_name="agent_runs")
    for name in (
        "idempotency_key",
        "last_event_sequence",
        "usage",
        "versions",
        "budget",
        "context_snapshot_id",
        "orchestration_version",
        "failure_code",
        "request_meta",
    ):
        op.drop_column("agent_runs", name)
