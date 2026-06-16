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
    confidence: float = 0.0
    trend: str = "stable"
    status: str = "not_started"
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
    created_at: datetime


class KnowledgeStateRefreshDto(BaseModel):
    """Summary of an automatic knowledge-state refresh."""

    processed_count: int
    already_processed_count: int
    unmatched_count: int
    updated_states: list[KnowledgeStateDto] = Field(default_factory=list)
