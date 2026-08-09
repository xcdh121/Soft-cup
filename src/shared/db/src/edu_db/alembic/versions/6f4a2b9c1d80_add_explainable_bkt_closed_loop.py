"""Add the explainable BKT and intervention closed-loop schema.

Revision ID: 6f4a2b9c1d80
Revises: 5c2f8a1d7e40
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "6f4a2b9c1d80"
down_revision: str | Sequence[str] | None = "5c2f8a1d7e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kt_parameter_sets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("scope_type", sa.String(), server_default="global", nullable=False),
        sa.Column("scope_id", sa.String(), nullable=True),
        sa.Column("initial_mastery", sa.Float(), server_default="0.20", nullable=False),
        sa.Column("learn_probability", sa.Float(), server_default="0.12", nullable=False),
        sa.Column("slip_probability", sa.Float(), server_default="0.10", nullable=False),
        sa.Column("guess_probability", sa.Float(), server_default="0.20", nullable=False),
        sa.Column("forget_probability_daily", sa.Float(), server_default="0.005", nullable=False),
        sa.Column("difficulty_adjustments", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("answer_mode_adjustments", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("expert_reason", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", "scope_type", "scope_id", name="uq_kt_parameter_scope"),
    )
    op.create_index("ix_kt_parameter_sets_version", "kt_parameter_sets", ["version"])
    op.create_index("ix_kt_parameter_sets_scope_type", "kt_parameter_sets", ["scope_type"])
    op.create_index("ix_kt_parameter_sets_scope_id", "kt_parameter_sets", ["scope_id"])
    op.create_index("ix_kt_parameter_sets_status", "kt_parameter_sets", ["status"])
    op.bulk_insert(
        sa.table(
            "kt_parameter_sets",
            sa.column("id", sa.String()),
            sa.column("name", sa.String()),
            sa.column("version", sa.String()),
            sa.column("scope_type", sa.String()),
            sa.column("scope_id", sa.String()),
            sa.column("initial_mastery", sa.Float()),
            sa.column("learn_probability", sa.Float()),
            sa.column("slip_probability", sa.Float()),
            sa.column("guess_probability", sa.Float()),
            sa.column("forget_probability_daily", sa.Float()),
            sa.column("difficulty_adjustments", sa.JSON()),
            sa.column("answer_mode_adjustments", sa.JSON()),
            sa.column("status", sa.String()),
            sa.column("expert_reason", sa.Text()),
            sa.column("effective_from", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": "bkt-default-v1",
                "name": "Expert BKT default",
                "version": "bkt-v1.0",
                "scope_type": "global",
                "scope_id": None,
                "initial_mastery": 0.20,
                "learn_probability": 0.12,
                "slip_probability": 0.10,
                "guess_probability": 0.20,
                "forget_probability_daily": 0.005,
                "difficulty_adjustments": {},
                "answer_mode_adjustments": {},
                "status": "active",
                "expert_reason": (
                    "Initial transparent expert defaults; not fitted from data."
                ),
                "effective_from": datetime.now(timezone.utc),
            }
        ],
    )

    op.create_table(
        "explanations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("object_type", sa.String(), nullable=False),
        sa.Column("object_id", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("threshold_version", sa.String(), server_default="threshold-v1", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "user_id", "object_type", "object_id"):
        op.create_index(f"ix_explanations_{column}", "explanations", [column])

    op.create_table(
        "knowledge_point_kt_parameters",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=False),
        sa.Column("parameter_set_id", sa.String(), nullable=False),
        sa.Column("initial_mastery_override", sa.Float(), nullable=True),
        sa.Column("learn_override", sa.Float(), nullable=True),
        sa.Column("slip_override", sa.Float(), nullable=True),
        sa.Column("guess_override", sa.Float(), nullable=True),
        sa.Column("forget_override", sa.Float(), nullable=True),
        sa.Column("expert_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parameter_set_id"], ["kt_parameter_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_point_id", "parameter_set_id", name="uq_kp_kt_parameter"),
    )
    op.create_index("ix_knowledge_point_kt_parameters_knowledge_point_id", "knowledge_point_kt_parameters", ["knowledge_point_id"])
    op.create_index("ix_knowledge_point_kt_parameters_parameter_set_id", "knowledge_point_kt_parameters", ["parameter_set_id"])

    op.create_table(
        "item_knowledge_point_mappings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1", nullable=False),
        sa.Column("mapping_method", sa.String(), server_default="manual_review", nullable=False),
        sa.Column("mapping_confidence", sa.Float(), server_default="1", nullable=False),
        sa.Column("review_status", sa.String(), server_default="approved", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_type", "item_id", "knowledge_point_id", name="uq_item_kp_mapping"),
    )
    for column in ("item_type", "item_id", "knowledge_point_id", "review_status"):
        op.create_index(f"ix_item_knowledge_point_mappings_{column}", "item_knowledge_point_mappings", [column])

    op.create_table(
        "explanation_evidences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("explanation_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=True),
        sa.Column("contribution_direction", sa.String(), server_default="supporting", nullable=False),
        sa.Column("contribution_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("snapshot", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["explanation_id"], ["explanations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_explanation_evidences_explanation_id", "explanation_evidences", ["explanation_id"])

    # Existing state snapshots remain readable and are explicitly tagged legacy.
    state_columns = [
        sa.Column("mastery_probability", sa.Float(), server_default="0", nullable=False),
        sa.Column("p_correct_next", sa.Float(), server_default="0", nullable=False),
        sa.Column("evidence_confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("algorithm", sa.String(), server_default="legacy_ewma", nullable=False),
        sa.Column("model_version", sa.String(), server_default="legacy-rule-v1", nullable=False),
        sa.Column("parameter_set_id", sa.String(), nullable=True),
        sa.Column("threshold_version", sa.String(), server_default="threshold-v1", nullable=False),
        sa.Column("effective_event_count", sa.Float(), server_default="0", nullable=False),
        sa.Column("last_event_id", sa.String(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lock_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status_reason_codes", sa.JSON(), server_default="[]", nullable=False),
    ]
    for column in state_columns:
        op.add_column("student_knowledge_states", column)
    op.create_index("ix_student_knowledge_states_algorithm", "student_knowledge_states", ["algorithm"])
    op.create_foreign_key("fk_student_knowledge_states_parameter_set_id", "student_knowledge_states", "kt_parameter_sets", ["parameter_set_id"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE student_knowledge_states SET mastery_probability = mastery_score / 100.0, evidence_confidence = confidence, effective_event_count = attempt_count")

    event_columns = [
        sa.Column("algorithm", sa.String(), server_default="legacy_ewma", nullable=False),
        sa.Column("model_version", sa.String(), server_default="legacy-rule-v1", nullable=False),
        sa.Column("parameter_set_id", sa.String(), nullable=True),
        sa.Column("prior_mastery", sa.Float(), nullable=True),
        sa.Column("prior_after_forgetting", sa.Float(), nullable=True),
        sa.Column("posterior_after_observation", sa.Float(), nullable=True),
        sa.Column("posterior_after_learning", sa.Float(), nullable=True),
        sa.Column("p_correct_before", sa.Float(), nullable=True),
        sa.Column("p_correct_next", sa.Float(), nullable=True),
        sa.Column("observed_score", sa.Float(), nullable=True),
        sa.Column("event_weight", sa.Float(), server_default="1", nullable=False),
        sa.Column("effective_parameters", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("reason_codes", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("explanation_summary", sa.Text(), nullable=True),
        sa.Column("source_payload_hash", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("supersedes_event_id", sa.String(), nullable=True),
        sa.Column("state_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("shadow_results", sa.JSON(), server_default="{}", nullable=False),
    ]
    for column in event_columns:
        op.add_column("knowledge_state_events", column)
    op.create_index("ix_knowledge_state_events_algorithm", "knowledge_state_events", ["algorithm"])
    op.create_index("ix_knowledge_state_events_occurred_at", "knowledge_state_events", ["occurred_at"])
    op.create_foreign_key("fk_knowledge_state_events_parameter_set_id", "knowledge_state_events", "kt_parameter_sets", ["parameter_set_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_knowledge_state_events_supersedes_event_id", "knowledge_state_events", "knowledge_state_events", ["supersedes_event_id"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE knowledge_state_events SET prior_mastery = score_before / 100.0, posterior_after_learning = score_after / 100.0, occurred_at = created_at")

    diagnosis_columns = [
        sa.Column("trigger_type", sa.String(), nullable=True),
        sa.Column("trigger_id", sa.String(), nullable=True),
        sa.Column("primary_knowledge_point_id", sa.String(), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=True),
        sa.Column("explanation_id", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("diagnosis_version", sa.String(), server_default="diagnosis-rule-v1", nullable=False),
    ]
    for column in diagnosis_columns:
        op.add_column("diagnoses", column)
    op.create_index("ix_diagnoses_trigger_type", "diagnoses", ["trigger_type"])
    op.create_index("ix_diagnoses_trigger_id", "diagnoses", ["trigger_id"])
    op.create_index("ix_diagnoses_primary_knowledge_point_id", "diagnoses", ["primary_knowledge_point_id"])
    op.create_foreign_key("fk_diagnoses_primary_knowledge_point_id", "diagnoses", "knowledge_points", ["primary_knowledge_point_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_diagnoses_explanation_id", "diagnoses", "explanations", ["explanation_id"], ["id"], ondelete="SET NULL")

    recommendation_columns = [
        sa.Column("explanation_id", sa.String(), nullable=True),
        sa.Column("source_state_event_id", sa.String(), nullable=True),
        sa.Column("expected_outcome", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("verification_plan", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in recommendation_columns:
        op.add_column("recommendations", column)
    op.create_index("ix_recommendations_status", "recommendations", ["status"])
    op.create_foreign_key("fk_recommendations_explanation_id", "recommendations", "explanations", ["explanation_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_recommendations_source_state_event_id", "recommendations", "knowledge_state_events", ["source_state_event_id"], ["id"], ondelete="SET NULL")

    learning_path_columns = [
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("previous_path_id", sa.String(), nullable=True),
        sa.Column("adjust_trigger_type", sa.String(), nullable=True),
        sa.Column("adjust_trigger_id", sa.String(), nullable=True),
        sa.Column("explanation_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
    ]
    for column in learning_path_columns:
        op.add_column("learning_paths", column)
    op.create_index("ix_learning_paths_status", "learning_paths", ["status"])
    op.create_foreign_key("fk_learning_paths_previous_path_id", "learning_paths", "learning_paths", ["previous_path_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_learning_paths_explanation_id", "learning_paths", "explanations", ["explanation_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "learning_path_steps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("learning_path_id", sa.String(), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("knowledge_point_id", sa.String(), nullable=True),
        sa.Column("recommendation_id", sa.String(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("acceptance_condition", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("baseline_mastery", sa.Float(), nullable=True),
        sa.Column("target_mastery", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_event_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["learning_path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learning_path_id", "step_no", name="uq_learning_path_step_no"),
    )
    op.create_index("ix_learning_path_steps_learning_path_id", "learning_path_steps", ["learning_path_id"])
    op.create_index("ix_learning_path_steps_status", "learning_path_steps", ["status"])

    practice_columns = [
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("score", sa.Float(), server_default="0", nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("hint_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("difficulty_snapshot", sa.String(), nullable=True),
        sa.Column("answer_mode", sa.String(), server_default="manual", nullable=False),
        sa.Column("mapping_method", sa.String(), nullable=True),
        sa.Column("mapping_status", sa.String(), server_default="pending", nullable=False),
        sa.Column("mapping_confidence", sa.Float(), nullable=True),
        sa.Column("recommendation_id", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("learning_path_id", sa.String(), nullable=True),
        sa.Column("learning_path_step_id", sa.String(), nullable=True),
        sa.Column("is_verification", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
    ]
    for column in practice_columns:
        op.add_column("practice_records", column)
    for column in ("session_id", "answer_mode", "mapping_status", "resource_id", "is_verification", "occurred_at"):
        op.create_index(f"ix_practice_records_{column}", "practice_records", [column])
    op.create_foreign_key("fk_practice_records_recommendation_id", "practice_records", "recommendations", ["recommendation_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_practice_records_resource_id", "practice_records", "generated_resources", ["resource_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_practice_records_learning_path_id", "practice_records", "learning_paths", ["learning_path_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_practice_records_learning_path_step_id", "practice_records", "learning_path_steps", ["learning_path_step_id"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE practice_records SET score = CASE WHEN was_correct THEN 1 ELSE 0 END, answer_mode = item_type, mapping_status = CASE WHEN knowledge_point_id IS NULL THEN 'pending' ELSE 'resolved' END, mapping_method = CASE WHEN knowledge_point_id IS NULL THEN NULL ELSE 'item_binding' END, mapping_confidence = CASE WHEN knowledge_point_id IS NULL THEN NULL ELSE 1 END, occurred_at = created_at")

    op.create_table(
        "diagnosis_causes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("diagnosis_id", sa.String(), nullable=False),
        sa.Column("parent_cause_id", sa.String(), nullable=True),
        sa.Column("cause_type", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=True),
        sa.Column("relation_id", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("rank", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_cause_id"], ["diagnosis_causes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["relation_id"], ["knowledge_point_relations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnosis_causes_diagnosis_id", "diagnosis_causes", ["diagnosis_id"])
    op.create_index("ix_diagnosis_causes_cause_type", "diagnosis_causes", ["cause_type"])

    op.create_table(
        "recommendation_interactions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("recommendation_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("learning_session_id", sa.String(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("recommendation_id", "user_id", "project_id", "event_type", "occurred_at"):
        op.create_index(f"ix_recommendation_interactions_{column}", "recommendation_interactions", [column])

    op.create_table(
        "intervention_outcomes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("recommendation_id", sa.String(), nullable=False),
        sa.Column("knowledge_point_id", sa.String(), nullable=False),
        sa.Column("baseline_state_event_id", sa.String(), nullable=False),
        sa.Column("verification_event_id", sa.String(), nullable=False),
        sa.Column("mastery_before", sa.Float(), nullable=False),
        sa.Column("mastery_after", sa.Float(), nullable=False),
        sa.Column("mastery_gain", sa.Float(), nullable=False),
        sa.Column("verification_score", sa.Float(), nullable=False),
        sa.Column("target_mastery", sa.Float(), server_default="0.8", nullable=False),
        sa.Column("target_achieved", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("attribution_confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("evaluation_window_hours", sa.Integer(), server_default="72", nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("explanation_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_state_event_id"], ["knowledge_state_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verification_event_id"], ["knowledge_state_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["explanation_id"], ["explanations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verification_event_id"),
    )
    for column in ("project_id", "user_id", "recommendation_id", "knowledge_point_id"):
        op.create_index(f"ix_intervention_outcomes_{column}", "intervention_outcomes", [column])


def downgrade() -> None:
    op.drop_table("intervention_outcomes")
    op.drop_table("recommendation_interactions")
    op.drop_table("diagnosis_causes")

    for column in ("occurred_at", "is_verification", "resource_id", "mapping_status", "answer_mode", "session_id"):
        op.drop_index(f"ix_practice_records_{column}", table_name="practice_records")
    for column in (
        "metadata", "occurred_at", "is_verification", "learning_path_step_id",
        "learning_path_id", "resource_id", "recommendation_id", "mapping_confidence",
        "mapping_status", "mapping_method", "answer_mode", "difficulty_snapshot",
        "hint_count", "response_time_ms", "score", "attempt_no", "session_id",
    ):
        op.drop_column("practice_records", column)

    op.drop_table("learning_path_steps")
    op.drop_index("ix_learning_paths_status", table_name="learning_paths")
    for column in ("replaced_at", "activated_at", "status", "explanation_id", "adjust_trigger_id", "adjust_trigger_type", "previous_path_id", "version"):
        op.drop_column("learning_paths", column)

    op.drop_index("ix_recommendations_status", table_name="recommendations")
    for column in ("valid_until", "status", "verification_plan", "expected_outcome", "source_state_event_id", "explanation_id"):
        op.drop_column("recommendations", column)

    for index in ("ix_diagnoses_primary_knowledge_point_id", "ix_diagnoses_trigger_id", "ix_diagnoses_trigger_type"):
        op.drop_index(index, table_name="diagnoses")
    for column in ("diagnosis_version", "confidence", "explanation_id", "state_version", "primary_knowledge_point_id", "trigger_id", "trigger_type"):
        op.drop_column("diagnoses", column)

    op.drop_index("ix_knowledge_state_events_occurred_at", table_name="knowledge_state_events")
    op.drop_index("ix_knowledge_state_events_algorithm", table_name="knowledge_state_events")
    for column in (
        "shadow_results", "state_version", "supersedes_event_id", "processed_at", "occurred_at",
        "source_payload_hash", "explanation_summary", "reason_codes", "effective_parameters",
        "event_weight", "observed_score", "p_correct_next", "p_correct_before",
        "posterior_after_learning", "posterior_after_observation", "prior_after_forgetting",
        "prior_mastery", "parameter_set_id", "model_version", "algorithm",
    ):
        op.drop_column("knowledge_state_events", column)

    op.drop_index("ix_student_knowledge_states_algorithm", table_name="student_knowledge_states")
    for column in (
        "status_reason_codes", "lock_version", "state_version", "last_verified_at", "last_event_id",
        "effective_event_count", "threshold_version", "parameter_set_id", "model_version",
        "algorithm", "evidence_confidence", "p_correct_next", "mastery_probability",
    ):
        op.drop_column("student_knowledge_states", column)

    op.drop_table("explanation_evidences")
    op.drop_table("item_knowledge_point_mappings")
    op.drop_table("knowledge_point_kt_parameters")
    op.drop_table("explanations")
    op.drop_table("kt_parameter_sets")
