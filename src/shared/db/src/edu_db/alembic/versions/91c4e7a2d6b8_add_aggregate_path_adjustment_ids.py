"""Record every intervention outcome used by a path adjustment.

Revision ID: 91c4e7a2d6b8
Revises: 6f4a2b9c1d80
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "91c4e7a2d6b8"
down_revision: str | Sequence[str] | None = "6f4a2b9c1d80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_paths",
        sa.Column(
            "adjust_trigger_ids",
            sa.JSON(),
            server_default="[]",
            nullable=False,
        ),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE learning_paths
            SET adjust_trigger_ids = json_build_array(adjust_trigger_id)
            WHERE adjust_trigger_id IS NOT NULL
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            UPDATE learning_paths
            SET adjust_trigger_ids = json_array(adjust_trigger_id)
            WHERE adjust_trigger_id IS NOT NULL
            """
        )


def downgrade() -> None:
    op.drop_column("learning_paths", "adjust_trigger_ids")
