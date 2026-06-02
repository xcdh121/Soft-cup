from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ResourcePackageStatus = Literal["draft", "generating", "completed", "failed"]
GeneratedResourceStatus = Literal["pending", "generating", "completed", "failed"]
GenerationMode = Literal["manual", "recommended", "remedial"]
DifficultyLevel = Literal["beginner", "intermediate", "advanced"]
ResourceType = Literal[
    "lecture_note",
    "mind_map",
    "practice_set",
    "ppt_outline",
    "pptx",
    "code_lab",
    "reading_material",
    "video_script",
]


class ResourcePackageStreamEventDto(BaseModel):
    event: str = Field(..., description="Event type")
    package_id: str = Field(..., description="Resource package ID")
    timestamp: datetime = Field(..., description="Event timestamp")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")


class GeneratedResourceDto(BaseModel):
    model_config = {"from_attributes": True}

    id: str = Field(..., description="Generated resource ID")
    resource_package_id: str = Field(..., description="Parent resource package ID")
    project_id: str = Field(..., description="Project ID")
    user_id: str = Field(..., description="User ID")
    resource_type: ResourceType = Field(..., description="Resource type")
    title: str = Field(..., description="Resource title")
    summary: str | None = Field(None, description="Short summary")
    status: GeneratedResourceStatus = Field(..., description="Generation status")
    format: str = Field(..., description="Content format")
    content_text: str | None = Field(None, description="Text content")
    content_json: dict[str, Any] | None = Field(None, description="Structured content")
    file_url: str | None = Field(None, description="Export file URL")
    preview_url: str | None = Field(None, description="Preview URL")
    cover_image_url: str | None = Field(None, description="Cover image URL")
    source_document_ids: list[str] = Field(
        default_factory=list, description="Source document IDs"
    )
    knowledge_point_ids: list[str] = Field(
        default_factory=list, description="Knowledge point IDs"
    )
    difficulty_level: DifficultyLevel = Field(..., description="Difficulty level")
    estimated_minutes: int | None = Field(None, description="Estimated minutes")
    version: int = Field(..., description="Version number")
    generation_order: int = Field(..., description="Display order")
    generator_agent: str | None = Field(None, description="Primary generator agent")
    generation_reason: str | None = Field(None, description="Why this was generated")
    error_message: str | None = Field(None, description="Failure message")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")
    completed_at: datetime | None = Field(None, description="Completion time")


class ResourcePackageDto(BaseModel):
    model_config = {"from_attributes": True}

    id: str = Field(..., description="Resource package ID")
    project_id: str = Field(..., description="Project ID")
    user_id: str = Field(..., description="User ID")
    profile_id: str | None = Field(None, description="Profile ID")
    learning_path_id: str | None = Field(None, description="Learning path ID")
    title: str = Field(..., description="Package title")
    description: str | None = Field(None, description="Package description")
    generation_mode: GenerationMode = Field(..., description="Generation mode")
    status: ResourcePackageStatus = Field(..., description="Package status")
    target_topic: str = Field(..., description="Target topic")
    target_goal: str | None = Field(None, description="Target goal")
    difficulty_level: DifficultyLevel = Field(..., description="Difficulty level")
    estimated_minutes: int | None = Field(None, description="Estimated minutes")
    source_document_ids: list[str] = Field(
        default_factory=list, description="Source document IDs"
    )
    knowledge_point_ids: list[str] = Field(
        default_factory=list, description="Knowledge point IDs"
    )
    weak_knowledge_point_ids: list[str] = Field(
        default_factory=list, description="Weak knowledge point IDs"
    )
    preferred_resource_types: list[ResourceType] = Field(
        default_factory=list, description="Preferred resource types"
    )
    generation_params: dict[str, Any] = Field(
        default_factory=dict, description="Generation params"
    )
    agent_trace: list[dict[str, Any]] = Field(
        default_factory=list, description="Agent trace events"
    )
    resource_count: int = Field(..., description="Total resources")
    completed_resource_count: int = Field(..., description="Completed resource count")
    failed_resource_count: int = Field(..., description="Failed resource count")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")
    completed_at: datetime | None = Field(None, description="Completion time")
    resources: list[GeneratedResourceDto] = Field(
        default_factory=list, description="Resources in the package"
    )
