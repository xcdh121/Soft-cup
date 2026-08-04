"""Add billing, entitlements, admin audit and observability fields.

Revision ID: e8c4a1f2b790
Revises: 5c2f8a1d7e40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8c4a1f2b790"
down_revision: str | Sequence[str] | None = "5c2f8a1d7e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("current_agent_name", sa.String(), nullable=True))
    op.add_column("agent_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("model_name", sa.String(), nullable=True))
    op.add_column("agent_runs", sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("agent_runs", sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False))
    op.add_column("agent_runs", sa.Column("estimated_cost_micros", sa.Integer(), server_default="0", nullable=False))
    op.add_column("agent_runs", sa.Column("trace_id", sa.String(), nullable=True))
    op.add_column("agent_runs", sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_runs", sa.Column("retry_of_run_id", sa.String(), nullable=True))
    op.add_column("agent_runs", sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_runs", sa.Column("handled_by", sa.String(), nullable=True))
    op.create_foreign_key("fk_agent_runs_retry_of", "agent_runs", "agent_runs", ["retry_of_run_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_agent_runs_handled_by", "agent_runs", "users", ["handled_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_agent_runs_current_agent_name", "agent_runs", ["current_agent_name"])
    op.create_index("ix_agent_runs_heartbeat_at", "agent_runs", ["heartbeat_at"])
    op.create_unique_constraint("uq_agent_runs_trace_id", "agent_runs", ["trace_id"])

    op.add_column("courses", sa.Column("visibility", sa.String(), server_default="private", nullable=False))
    op.add_column("courses", sa.Column("publish_status", sa.String(), server_default="draft", nullable=False))
    op.add_column("courses", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("courses", sa.Column("published_by", sa.String(), nullable=True))
    op.add_column("courses", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("courses", sa.Column("cover_url", sa.String(), nullable=True))
    op.create_foreign_key("fk_courses_published_by", "courses", "users", ["published_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_courses_visibility", "courses", ["visibility"])
    op.create_index("ix_courses_publish_status", "courses", ["publish_status"])

    op.create_table(
        "billing_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="CNY", nullable=False),
        sa.Column("duration_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("quotas", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_plans_code", "billing_plans", ["code"])
    op.create_index("ix_billing_plans_is_active", "billing_plans", ["is_active"])

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_no", sa.String(), nullable=False, unique=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="CNY", nullable=False),
        sa.Column("provider", sa.String(), server_default="manual", nullable=False),
        sa.Column("provider_transaction_id", sa.String(), nullable=True, unique=True),
        sa.Column("status", sa.String(), server_default="created", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_amount_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("refund_reason", sa.Text(), nullable=True),
        sa.Column("exception_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_orders_order_no", "payment_orders", ["order_no"])
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])
    op.create_index("ix_payment_orders_provider", "payment_orders", ["provider"])
    op.create_index("ix_payment_orders_user_created", "payment_orders", ["user_id", "created_at"])
    op.create_index("ix_payment_orders_status_created", "payment_orders", ["status", "created_at"])

    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("payment_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload_digest", sa.String(), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_events_order_id", "payment_events", ["order_id"])
    op.create_index("ix_payment_events_event_type", "payment_events", ["event_type"])

    op.create_table(
        "user_entitlements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("payment_orders.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("billing_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by_admin_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("grant_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_entitlements_user_id", "user_entitlements", ["user_id"])
    op.create_index("ix_user_entitlements_status", "user_entitlements", ["status"])
    op.create_index("ix_user_entitlements_active", "user_entitlements", ["user_id", "status", "ends_at"])

    op.create_table(
        "quota_buckets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entitlement_id", sa.String(), sa.ForeignKey("user_entitlements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("granted", sa.Integer(), nullable=False),
        sa.Column("used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entitlement_id", "resource_type", name="uq_quota_bucket_resource"),
        sa.CheckConstraint("granted >= 0 AND used >= 0 AND reserved >= 0", name="ck_quota_non_negative"),
        sa.CheckConstraint("used + reserved <= granted", name="ck_quota_within_grant"),
    )
    op.create_index("ix_quota_buckets_user_id", "quota_buckets", ["user_id"])
    op.create_index("ix_quota_buckets_resource_type", "quota_buckets", ["resource_type"])
    op.create_index("ix_quota_bucket_consumption", "quota_buckets", ["user_id", "resource_type", "expires_at"])

    op.create_table(
        "quota_ledger",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bucket_id", sa.String(), sa.ForeignKey("quota_buckets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("business_type", sa.String(), nullable=True),
        sa.Column("business_id", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True),
        sa.Column("operator_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quota_ledger_user_id", "quota_ledger", ["user_id"])
    op.create_index("ix_quota_ledger_bucket_id", "quota_ledger", ["bucket_id"])
    op.create_index("ix_quota_ledger_resource_type", "quota_ledger", ["resource_type"])
    op.create_index("ix_quota_ledger_operation", "quota_ledger", ["operation"])
    op.create_index("ix_quota_ledger_created_at", "quota_ledger", ["created_at"])

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("admin_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_audit_logs_admin_user_id", "admin_audit_logs", ["admin_user_id"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])
    op.create_index("ix_admin_audit_action_created", "admin_audit_logs", ["action", "created_at"])
    op.create_index("ix_admin_audit_target", "admin_audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
    op.drop_table("quota_ledger")
    op.drop_table("quota_buckets")
    op.drop_table("user_entitlements")
    op.drop_table("payment_events")
    op.drop_table("payment_orders")
    op.drop_table("billing_plans")

    op.drop_index("ix_courses_publish_status", table_name="courses")
    op.drop_index("ix_courses_visibility", table_name="courses")
    op.drop_constraint("fk_courses_published_by", "courses", type_="foreignkey")
    for column in ("cover_url", "version", "published_by", "published_at", "publish_status", "visibility"):
        op.drop_column("courses", column)

    op.drop_constraint("uq_agent_runs_trace_id", "agent_runs", type_="unique")
    op.drop_index("ix_agent_runs_heartbeat_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_current_agent_name", table_name="agent_runs")
    op.drop_constraint("fk_agent_runs_handled_by", "agent_runs", type_="foreignkey")
    op.drop_constraint("fk_agent_runs_retry_of", "agent_runs", type_="foreignkey")
    for column in (
        "handled_by", "handled_at", "retry_of_run_id", "cancellation_requested_at",
        "trace_id", "estimated_cost_micros", "output_tokens", "input_tokens",
        "model_name", "duration_ms", "heartbeat_at", "current_agent_name",
    ):
        op.drop_column("agent_runs", column)
