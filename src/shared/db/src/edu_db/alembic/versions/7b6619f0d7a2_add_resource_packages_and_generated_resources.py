"""add_resource_packages_and_generated_resources

Revision ID: 7b6619f0d7a2
Revises: 12d284c3be7b
Create Date: 2026-06-02 18:20:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b6619f0d7a2"
down_revision: Union[str, Sequence[str], None] = "12d284c3be7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "resource_packages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=True),
        sa.Column("learning_path_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("generation_mode", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("target_topic", sa.String(), nullable=False),
        sa.Column("target_goal", sa.Text(), nullable=True),
        sa.Column("difficulty_level", sa.String(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("knowledge_point_ids", sa.JSON(), nullable=False),
        sa.Column("weak_knowledge_point_ids", sa.JSON(), nullable=False),
        sa.Column("preferred_resource_types", sa.JSON(), nullable=False),
        sa.Column("generation_params", sa.JSON(), nullable=False),
        sa.Column("agent_trace", sa.JSON(), nullable=False),
        sa.Column("resource_count", sa.Integer(), nullable=False),
        sa.Column("completed_resource_count", sa.Integer(), nullable=False),
        sa.Column("failed_resource_count", sa.Integer(), nullable=False),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_resource_packages_project_id"),
        "resource_packages",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_packages_user_id"),
        "resource_packages",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_packages_title"),
        "resource_packages",
        ["title"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_packages_status"),
        "resource_packages",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_packages_target_topic"),
        "resource_packages",
        ["target_topic"],
        unique=False,
    )

    op.create_table(
        "generated_resources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("resource_package_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("file_url", sa.String(), nullable=True),
        sa.Column("preview_url", sa.String(), nullable=True),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("knowledge_point_ids", sa.JSON(), nullable=False),
        sa.Column("difficulty_level", sa.String(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generation_order", sa.Integer(), nullable=False),
        sa.Column("generator_agent", sa.String(), nullable=True),
        sa.Column("generation_reason", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resource_package_id"], ["resource_packages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generated_resources_resource_package_id"),
        "generated_resources",
        ["resource_package_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_resources_project_id"),
        "generated_resources",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_resources_user_id"),
        "generated_resources",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_resources_resource_type"),
        "generated_resources",
        ["resource_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_resources_title"),
        "generated_resources",
        ["title"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_resources_status"),
        "generated_resources",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_resources_generation_order"),
        "generated_resources",
        ["generation_order"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_generated_resources_generation_order"),
        table_name="generated_resources",
    )
    op.drop_index(
        op.f("ix_generated_resources_status"),
        table_name="generated_resources",
    )
    op.drop_index(
        op.f("ix_generated_resources_title"),
        table_name="generated_resources",
    )
    op.drop_index(
        op.f("ix_generated_resources_resource_type"),
        table_name="generated_resources",
    )
    op.drop_index(
        op.f("ix_generated_resources_user_id"),
        table_name="generated_resources",
    )
    op.drop_index(
        op.f("ix_generated_resources_project_id"),
        table_name="generated_resources",
    )
    op.drop_index(
        op.f("ix_generated_resources_resource_package_id"),
        table_name="generated_resources",
    )
    op.drop_table("generated_resources")

    op.drop_index(
        op.f("ix_resource_packages_target_topic"),
        table_name="resource_packages",
    )
    op.drop_index(op.f("ix_resource_packages_status"), table_name="resource_packages")
    op.drop_index(op.f("ix_resource_packages_title"), table_name="resource_packages")
    op.drop_index(
        op.f("ix_resource_packages_user_id"), table_name="resource_packages"
    )
    op.drop_index(
        op.f("ix_resource_packages_project_id"), table_name="resource_packages"
    )
    op.drop_table("resource_packages")
