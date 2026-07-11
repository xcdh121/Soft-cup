"""add skill executions and internal tool call audit

Revision ID: c3a61fd82b10
Revises: 4f1d2a9c8b03
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a61fd82b10"
down_revision: Union[str, Sequence[str], None] = "4f1d2a9c8b03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_executions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=False),
        sa.Column("skill_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=False),
        sa.Column("output_artifact_key", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
    )
    for column in ("run_id", "agent_name", "skill_id", "status"):
        op.create_index(f"ix_skill_executions_{column}", "skill_executions", [column])

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("skill_execution_id", sa.String(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("skill_id", sa.String(), nullable=True),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("tool_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("approval_status", sa.String(), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_execution_id"], ["skill_executions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_tool_calls_idempotency_key"),
    )
    for column in ("run_id", "skill_execution_id", "agent_name", "skill_id", "tool_name", "status"):
        op.create_index(f"ix_agent_tool_calls_{column}", "agent_tool_calls", [column])


def downgrade() -> None:
    op.drop_table("agent_tool_calls")
    op.drop_table("skill_executions")
