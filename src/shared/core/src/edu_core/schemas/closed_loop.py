from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RecommendationFeedbackCreate(BaseModel):
    event_type: str
    resource_id: str | None = None
    learning_session_id: str | None = None
    progress: float | None = Field(None, ge=0, le=1)
    duration_ms: int | None = Field(None, ge=0)
    rating: int | None = Field(None, ge=1, le=5)
    reason_code: str | None = None
    occurred_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        allowed = {
            "impression", "clicked", "started", "progressed", "completed",
            "dismissed", "skipped", "rated",
        }
        if value not in allowed:
            raise ValueError(f"event_type must be one of {sorted(allowed)}")
        return value


class RecommendationInteractionDto(RecommendationFeedbackCreate):
    id: str
    recommendation_id: str
    user_id: str
    project_id: str
    occurred_at: datetime


class InterventionOutcomeDto(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    project_id: str
    user_id: str
    recommendation_id: str
    knowledge_point_id: str
    baseline_state_event_id: str
    verification_event_id: str
    mastery_before: float
    mastery_after: float
    mastery_gain: float
    verification_score: float
    target_mastery: float
    target_achieved: bool
    attribution_confidence: float
    evaluation_window_hours: int
    evaluated_at: datetime
    explanation_id: str | None = None


class LearningPathAdjustRequest(BaseModel):
    trigger_type: str = "intervention_outcomes"
    trigger_id: str | None = None
    outcome_ids: list[str] = Field(default_factory=list)


class KTParameterSetCreate(BaseModel):
    name: str
    version: str
    scope_type: str = "global"
    scope_id: str | None = None
    initial_mastery: float = Field(0.20, ge=0, le=1)
    learn_probability: float = Field(0.12, ge=0, le=1)
    slip_probability: float = Field(0.10, ge=0, le=1)
    guess_probability: float = Field(0.20, ge=0, le=1)
    forget_probability_daily: float = Field(0.005, ge=0, le=1)
    difficulty_adjustments: dict = Field(default_factory=dict)
    answer_mode_adjustments: dict = Field(default_factory=dict)
    status: str = "draft"
    expert_reason: str | None = None
    effective_from: datetime | None = None


class KTParameterSetDto(KTParameterSetCreate):
    model_config = {"from_attributes": True}

    id: str
    created_by: str | None = None
    created_at: datetime


class KnowledgePointKTOverrideCreate(BaseModel):
    parameter_set_id: str
    initial_mastery_override: float | None = Field(None, ge=0, le=1)
    learn_override: float | None = Field(None, ge=0, le=1)
    slip_override: float | None = Field(None, ge=0, le=1)
    guess_override: float | None = Field(None, ge=0, le=1)
    forget_override: float | None = Field(None, ge=0, le=1)
    expert_reason: str | None = None


class ItemKnowledgePointMappingCreate(BaseModel):
    item_type: str
    item_id: str
    knowledge_point_id: str
    weight: float = Field(1.0, gt=0, le=1)
    mapping_method: str = "manual_review"
    mapping_confidence: float = Field(1.0, ge=0, le=1)
    review_status: str = "approved"


class KnowledgeStateReplayRequest(BaseModel):
    knowledge_point_id: str | None = None
    dry_run: bool = False


class KnowledgeStateReplayDto(BaseModel):
    processed_records: int
    rebuilt_states: int
    dry_run: bool
    differences: list[dict] = Field(default_factory=list)


class KTMetricDto(BaseModel):
    event_count: int
    brier_score: float | None = None
    log_loss: float | None = None
    expected_calibration_error: float | None = None
    legacy_brier_score: float | None = None
    legacy_log_loss: float | None = None
    legacy_expected_calibration_error: float | None = None
    brier_score_improvement: float | None = None
    log_loss_improvement: float | None = None
    mapping_coverage: float
    low_evidence_ratio: float
