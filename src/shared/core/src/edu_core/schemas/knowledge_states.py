from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeStateDto(BaseModel):
    """A learner's current state for a knowledge point."""

    id: str | None = None
    user_id: str
    project_id: str
    knowledge_point_id: str
    knowledge_point_name: str
    chapter_id: str | None = None
    mastery_score: float = 0.0
    mastery_probability: float = 0.0
    p_correct_next: float = 0.0
    confidence: float = 0.0
    evidence_confidence: float = 0.0
    trend: str = "stable"
    status: str = "not_started"
    algorithm: str = "legacy_ewma"
    model_version: str = "legacy-rule-v1"
    parameter_set_id: str | None = None
    threshold_version: str = "threshold-v1"
    effective_event_count: float = 0.0
    last_event_id: str | None = None
    last_verified_at: datetime | None = None
    state_version: int = 0
    status_reason_codes: list[str] = Field(default_factory=list)
    latest_explanation: dict | None = None
    attempt_count: int = 0
    correct_count: int = 0
    evidence: list[dict] = Field(default_factory=list)
    last_practiced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KnowledgeStateEventDto(BaseModel):
    """One event that changed a knowledge state."""

    model_config = {"from_attributes": True}

    id: str
    knowledge_state_id: str
    project_id: str
    user_id: str
    knowledge_point_id: str
    event_type: str
    source_type: str
    source_id: str
    score_before: float
    score_after: float
    impact: float
    was_correct: bool | None = None
    evidence: dict = Field(default_factory=dict)
    algorithm: str = "legacy_ewma"
    model_version: str = "legacy-rule-v1"
    parameter_set_id: str | None = None
    prior_mastery: float | None = None
    prior_after_forgetting: float | None = None
    posterior_after_observation: float | None = None
    posterior_after_learning: float | None = None
    p_correct_before: float | None = None
    p_correct_next: float | None = None
    observed_score: float | None = None
    event_weight: float = 1.0
    effective_parameters: dict = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    explanation_summary: str | None = None
    occurred_at: datetime
    processed_at: datetime
    state_version: int = 1
    shadow_results: dict = Field(default_factory=dict)
    created_at: datetime


class KnowledgeStateRefreshDto(BaseModel):
    """Summary of an automatic knowledge-state refresh."""

    processed_count: int
    already_processed_count: int
    unmatched_count: int
    updated_states: list[KnowledgeStateDto] = Field(default_factory=list)


class KnowledgeGraphNodeDto(BaseModel):
    """Knowledge graph node enriched with the learner's state."""

    id: str
    label: str
    chapter_id: str | None = None
    difficulty_level: str
    position: int
    tags: list[str] = Field(default_factory=list)
    mastery_score: float = 0.0
    mastery_probability: float = 0.0
    p_correct_next: float = 0.0
    confidence: float = 0.0
    evidence_confidence: float = 0.0
    trend: str = "stable"
    status: str = "not_started"
    algorithm: str = "legacy_ewma"
    model_version: str = "legacy-rule-v1"


class KnowledgeGraphEdgeDto(BaseModel):
    """Knowledge graph edge between two knowledge points."""

    id: str
    source: str
    target: str
    relation_type: str
    strength: float
    description: str | None = None


class KnowledgeGraphDto(BaseModel):
    """Project knowledge graph returned to the frontend."""

    project_id: str
    course_id: str
    nodes: list[KnowledgeGraphNodeDto] = Field(default_factory=list)
    edges: list[KnowledgeGraphEdgeDto] = Field(default_factory=list)
