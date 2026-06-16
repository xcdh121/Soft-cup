from pydantic import BaseModel, Field


class LearningPathStep(BaseModel):
    step_no: int = Field(description="Ordered step number in the learning path.")
    type: str = Field(description="Step type, such as resource or practice.")
    target_id: str | None = Field(
        default=None, description="Target resource or practice identifier."
    )
    title: str = Field(description="User-facing title for the step.")
    reason: str = Field(description="Why this step is part of the learning path.")


class LearningPathContent(BaseModel):
    title: str = Field(description="Title of the generated learning path.")
    estimated_minutes: int = Field(
        description="Estimated total duration in minutes."
    )
    path_steps: list[LearningPathStep] = Field(
        description="Ordered list of actionable learning path steps."
    )
    based_on_profile_fields: list[str] = Field(
        description="Learner profile fields that influenced the plan."
    )
    based_on_knowledge_points: list[str] = Field(
        description="Knowledge points the plan is addressing."
    )
    adjust_reasons: list[str] = Field(
        description="High-level reasons behind the overall plan design."
    )
