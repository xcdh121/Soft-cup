from datetime import datetime

from edu_core.schemas.resource_packages import GeneratedResourceDto
from pydantic import BaseModel, Field


class CourseResourceDto(BaseModel):
    """Course resource data returned by the API."""

    id: str = Field(..., description="Unique ID of the course resource")
    course_id: str = Field(..., description="ID of the parent course")
    chapter_id: str | None = Field(None, description="Optional chapter ID")
    document_id: str | None = Field(None, description="Optional source document ID")
    document_project_id: str | None = Field(
        None, description="Project ID that owns the source document"
    )
    generated_resource_id: str | None = Field(
        None, description="Optional generated resource ID"
    )
    generated_resource: GeneratedResourceDto | None = Field(
        None, description="Resolved generated resource content"
    )
    resource_type: str = Field(..., description="Resource type")
    title: str = Field(..., description="Resource title")
    description: str | None = Field(None, description="Resource description")
    source_type: str = Field(..., description="Resource source type")
    source_url: str | None = Field(None, description="Optional external source URL")
    difficulty_level: str = Field(..., description="Resource difficulty")
    estimated_minutes: int | None = Field(None, description="Estimated study time")
    license_info: str | None = Field(None, description="Resource license")
    target_audiences: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    knowledge_point_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
