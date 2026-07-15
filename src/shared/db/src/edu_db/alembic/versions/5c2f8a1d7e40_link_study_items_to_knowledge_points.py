"""Link quiz questions and flashcards to knowledge points.

Revision ID: 5c2f8a1d7e40
Revises: 1b7d4e9a6c20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c2f8a1d7e40"
down_revision: str | Sequence[str] | None = "1b7d4e9a6c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "flashcards", sa.Column("knowledge_point_id", sa.String(), nullable=True)
    )
    op.create_index(
        op.f("ix_flashcards_knowledge_point_id"),
        "flashcards",
        ["knowledge_point_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_flashcards_knowledge_point_id",
        "flashcards",
        "knowledge_points",
        ["knowledge_point_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "quiz_questions",
        sa.Column("knowledge_point_id", sa.String(), nullable=True),
    )
    op.create_index(
        op.f("ix_quiz_questions_knowledge_point_id"),
        "quiz_questions",
        ["knowledge_point_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_quiz_questions_knowledge_point_id",
        "quiz_questions",
        "knowledge_points",
        ["knowledge_point_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_quiz_questions_knowledge_point_id",
        "quiz_questions",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_quiz_questions_knowledge_point_id"),
        table_name="quiz_questions",
    )
    op.drop_column("quiz_questions", "knowledge_point_id")

    op.drop_constraint(
        "fk_flashcards_knowledge_point_id", "flashcards", type_="foreignkey"
    )
    op.drop_index(op.f("ix_flashcards_knowledge_point_id"), table_name="flashcards")
    op.drop_column("flashcards", "knowledge_point_id")
