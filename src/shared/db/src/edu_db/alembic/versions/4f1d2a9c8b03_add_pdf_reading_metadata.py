"""add_pdf_reading_metadata

Revision ID: 4f1d2a9c8b03
Revises: d4a8c2e7f901
Create Date: 2026-07-08 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f1d2a9c8b03"
down_revision: Union[str, Sequence[str], None] = "d4a8c2e7f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("documents", sa.Column("metadata", sa.JSON(), nullable=True))
    op.add_column(
        "document_segments", sa.Column("page_number", sa.Integer(), nullable=True)
    )
    op.add_column(
        "document_segments",
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "ix_document_segments_document_page",
        "document_segments",
        ["document_id", "page_number"],
    )
    op.create_index(
        "ix_document_segments_page_number",
        "document_segments",
        ["page_number"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_document_segments_page_number", table_name="document_segments")
    op.drop_index("ix_document_segments_document_page", table_name="document_segments")
    op.drop_column("document_segments", "chunk_index")
    op.drop_column("document_segments", "page_number")
    op.drop_column("documents", "metadata")
