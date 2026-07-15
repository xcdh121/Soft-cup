"""add_course_library_and_learner_models

Revision ID: a4c8e2f91b6d
Revises: 7b6619f0d7a2
Create Date: 2026-06-09 19:30:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c8e2f91b6d"
down_revision: Union[str, Sequence[str], None] = "7b6619f0d7a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the structured course library and learner foundation."""
    op.create_table(
        "courses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_courses_owner_id"), "courses", ["owner_id"])
    op.create_index(op.f("ix_courses_code"), "courses", ["code"])
    op.create_index(op.f("ix_courses_name"), "courses", ["name"])
    op.create_index(op.f("ix_courses_status"), "courses", ["status"])

    op.add_column("projects", sa.Column("course_id", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_projects_course_id"), "projects", ["course_id"], unique=False
    )
    op.create_foreign_key(
        "fk_projects_course_id_courses",
        "projects",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "course_chapters",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("course_id", sa.String(), nullable=False),
        sa.Column("parent_chapter_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("learning_objectives", sa.JSON(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
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
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="ck_course_chapters_estimated_minutes",
        ),
        sa.CheckConstraint("position >= 0", name="ck_course_chapters_position"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_chapter_id"], ["course_chapters.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_course_chapters_course_id"), "course_chapters", ["course_id"]
    )
    op.create_index(
        op.f("ix_course_chapters_parent_chapter_id"),
        "course_chapters",
        ["parent_chapter_id"],
    )
    op.create_index(op.f("ix_course_chapters_title"), "course_chapters", ["title"])
    op.create_index(
        op.f("ix_course_chapters_position"), "course_chapters", ["position"]
    )

    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("course_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("difficulty_level", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name="ck_knowledge_points_position"),
        sa.ForeignKeyConstraint(
            ["chapter_id"], ["course_chapters.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "name", name="uq_knowledge_points_course_name"
        ),
    )
    op.create_index(
        op.f("ix_knowledge_points_course_id"), "knowledge_points", ["course_id"]
    )
    op.create_index(
        op.f("ix_knowledge_points_chapter_id"), "knowledge_points", ["chapter_id"]
    )
    op.create_index(op.f("ix_knowledge_points_name"), "knowledge_points", ["name"])
    op.create_index(
        op.f("ix_knowledge_points_difficulty_level"),
        "knowledge_points",
        ["difficulty_level"],
    )
    op.create_index(
        op.f("ix_knowledge_points_position"), "knowledge_points", ["position"]
    )

    op.create_table(
        "knowledge_point_relations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("course_id", sa.String(), nullable=False),
        sa.Column("source_knowledge_point_id", sa.String(), nullable=False),
        sa.Column("target_knowledge_point_id", sa.String(), nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_knowledge_point_id <> target_knowledge_point_id",
            name="ck_knowledge_point_relations_not_self",
        ),
        sa.CheckConstraint(
            "strength >= 0 AND strength <= 1",
            name="ck_knowledge_point_relations_strength",
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_knowledge_point_id"],
            ["knowledge_points.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_knowledge_point_id"],
            ["knowledge_points.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_knowledge_point_id",
            "target_knowledge_point_id",
            "relation_type",
            name="uq_knowledge_point_relations_edge",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_point_relations_course_id"),
        "knowledge_point_relations",
        ["course_id"],
    )
    op.create_index(
        op.f("ix_knowledge_point_relations_source_knowledge_point_id"),
        "knowledge_point_relations",
        ["source_knowledge_point_id"],
    )
    op.create_index(
        op.f("ix_knowledge_point_relations_target_knowledge_point_id"),
        "knowledge_point_relations",
        ["target_knowledge_point_id"],
    )
    op.create_index(
        op.f("ix_knowledge_point_relations_relation_type"),
        "knowledge_point_relations",
        ["relation_type"],
    )

    op.create_table(
        "course_resources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("course_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("generated_resource_id", sa.String(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("difficulty_level", sa.String(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("license_info", sa.Text(), nullable=True),
        sa.Column("target_audiences", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="ck_course_resources_estimated_minutes",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"], ["course_chapters.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["generated_resource_id"],
            ["generated_resources.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_course_resources_course_id"), "course_resources", ["course_id"]
    )
    op.create_index(
        op.f("ix_course_resources_chapter_id"), "course_resources", ["chapter_id"]
    )
    op.create_index(
        op.f("ix_course_resources_document_id"), "course_resources", ["document_id"]
    )
    op.create_index(
        op.f("ix_course_resources_generated_resource_id"),
        "course_resources",
        ["generated_resource_id"],
    )
    op.create_index(
        op.f("ix_course_resources_resource_type"),
        "course_resources",
        ["resource_type"],
    )
    op.create_index(op.f("ix_course_resources_title"), "course_resources", ["title"])
    op.create_index(
        op.f("ix_course_resources_source_type"), "course_resources", ["source_type"]
    )
    op.create_index(
        op.f("ix_course_resources_difficulty_level"),
        "course_resources",
        ["difficulty_level"],
    )

    op.create_table(
        "course_resource_knowledge_points",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("course_resource_id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_course_resource_knowledge_points_relevance",
        ),
        sa.ForeignKeyConstraint(
            ["course_resource_id"], ["course_resources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_resource_id",
            "knowledge_point_id",
            name="uq_course_resource_knowledge_points_pair",
        ),
    )
    op.create_index(
        op.f("ix_course_resource_knowledge_points_course_resource_id"),
        "course_resource_knowledge_points",
        ["course_resource_id"],
    )
    op.create_index(
        op.f("ix_course_resource_knowledge_points_knowledge_point_id"),
        "course_resource_knowledge_points",
        ["knowledge_point_id"],
    )

    op.create_table(
        "learner_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("profile_data", sa.JSON(), nullable=False),
        sa.Column("completeness_score", sa.Float(), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "completeness_score >= 0 AND completeness_score <= 1",
            name="ck_learner_profiles_completeness",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "project_id", name="uq_learner_profiles_user_project"
        ),
    )
    op.create_index(
        op.f("ix_learner_profiles_user_id"), "learner_profiles", ["user_id"]
    )
    op.create_index(
        op.f("ix_learner_profiles_project_id"), "learner_profiles", ["project_id"]
    )
    op.create_index(
        op.f("ix_learner_profiles_status"), "learner_profiles", ["status"]
    )

    op.create_table(
        "student_knowledge_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("trend", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "attempt_count >= 0 AND correct_count >= 0 "
            "AND correct_count <= attempt_count",
            name="ck_student_knowledge_states_counts",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_student_knowledge_states_confidence",
        ),
        sa.CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 100",
            name="ck_student_knowledge_states_mastery",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "knowledge_point_id",
            name="uq_student_knowledge_states_user_point",
        ),
    )
    op.create_index(
        op.f("ix_student_knowledge_states_user_id"),
        "student_knowledge_states",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_student_knowledge_states_knowledge_point_id"),
        "student_knowledge_states",
        ["knowledge_point_id"],
    )
    op.create_index(
        op.f("ix_student_knowledge_states_trend"),
        "student_knowledge_states",
        ["trend"],
    )
    op.create_index(
        op.f("ix_student_knowledge_states_status"),
        "student_knowledge_states",
        ["status"],
    )


def downgrade() -> None:
    """Remove the structured course library and learner foundation."""
    op.drop_table("student_knowledge_states")
    op.drop_table("learner_profiles")
    op.drop_table("course_resource_knowledge_points")
    op.drop_table("course_resources")
    op.drop_table("knowledge_point_relations")
    op.drop_table("knowledge_points")
    op.drop_table("course_chapters")
    op.drop_constraint(
        "fk_projects_course_id_courses", "projects", type_="foreignkey"
    )
    op.drop_index(op.f("ix_projects_course_id"), table_name="projects")
    op.drop_column("projects", "course_id")
    op.drop_table("courses")
