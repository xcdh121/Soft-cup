from datetime import datetime

from pydantic import BaseModel, Field


class LearnerProfileDto(BaseModel):
    """Latest learner profile for one user in one project."""

    model_config = {"from_attributes": True}

    id: str
    user_id: str
    project_id: str
    status: str
    profile_data: dict = Field(default_factory=dict)
    completeness_score: float
    last_refreshed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LearnerProfileRevisionDto(BaseModel):
    """One auditable learner-profile field change."""

    model_config = {"from_attributes": True}

    id: str
    profile_id: str
    field_key: str
    old_value: object | None = None
    new_value: object | None = None
    confidence: float | None = None
    source_type: str
    source_id: str | None = None
    created_at: datetime
