"""Add manual QR payment reconciliation fields.

Revision ID: f4a7c2d9e510
Revises: e8c4a1f2b790
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4a7c2d9e510"
down_revision: str | Sequence[str] | None = "e8c4a1f2b790"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payment_orders",
        sa.Column("payment_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payment_orders",
        sa.Column("payment_claim_note", sa.String(120), nullable=True),
    )
    op.add_column(
        "payment_orders",
        sa.Column("payment_reference", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_payment_orders_payment_claimed_at",
        "payment_orders",
        ["payment_claimed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_orders_payment_claimed_at", table_name="payment_orders")
    op.drop_column("payment_orders", "payment_reference")
    op.drop_column("payment_orders", "payment_claim_note")
    op.drop_column("payment_orders", "payment_claimed_at")
