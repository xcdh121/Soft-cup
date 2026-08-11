"""Merge the agent-runtime, avatar, and explainable-BKT migration heads.

Revision ID: c7a1d4e9b320
Revises: 91c4e7a2d6b8, a6d9e3f1b742, f6c8d3e15220
"""

from collections.abc import Sequence

revision: str = "c7a1d4e9b320"
down_revision: str | Sequence[str] | None = (
    "91c4e7a2d6b8",
    "a6d9e3f1b742",
    "f6c8d3e15220",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
