from datetime import datetime

from pydantic import BaseModel, Field


class PracticeRecordDto(BaseModel):
    """Practice record data transfer object."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique ID of the practice record")
    user_id: str = Field(..., description="ID of the user")
    project_id: str = Field(..., description="ID of the project")
    knowledge_point_id: str | None = Field(
        None, description="Knowledge point associated with this practice"
    )
    item_type: str = Field(..., description="Type of study resource: flashcard or quiz")
    item_id: str = Field(
        ..., description="ID of the study resource (flashcard or quiz question)"
    )
    topic: str = Field(..., description="Topic extracted from question")
    user_answer: str | None = Field(
        None, description="User's answer (only for quizzes, null for flashcards)"
    )
    correct_answer: str = Field(..., description="The correct answer")
    was_correct: bool = Field(..., description="Whether the user got it right")
    session_id: str | None = None
    attempt_no: int = 1
    score: float = 0.0
    response_time_ms: int | None = None
    hint_count: int = 0
    difficulty_snapshot: str | None = None
    answer_mode: str = "manual"
    mapping_method: str | None = None
    mapping_status: str = "pending"
    mapping_confidence: float | None = None
    recommendation_id: str | None = None
    resource_id: str | None = None
    learning_path_id: str | None = None
    learning_path_step_id: str | None = None
    is_verification: bool = False
    occurred_at: datetime
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(
        ..., description="Date and time the practice record was created"
    )
