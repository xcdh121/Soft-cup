from datetime import datetime

from pydantic import BaseModel, Field


class CourseDto(BaseModel):
    """Course data returned by the API."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique ID of the course")
    owner_id: str = Field(..., description="ID of the user who owns the course")
    code: str | None = Field(None, description="Optional course code")
    name: str = Field(..., description="Course name")
    description: str | None = Field(None, description="Course description")
    status: str = Field(..., description="Course status")
    visibility: str = Field("private", description="private or platform")
    publish_status: str = Field("draft", description="Publication lifecycle")
    published_at: datetime | None = None
    published_by: str | None = None
    version: int = 1
    cover_url: str | None = None
    created_at: datetime = Field(..., description="Course creation time")
    updated_at: datetime = Field(..., description="Course update time")


class CourseChapterDto(BaseModel):
    """Course chapter data returned by the API."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique ID of the chapter")
    course_id: str = Field(..., description="ID of the parent course")
    parent_chapter_id: str | None = Field(
        None, description="Optional parent chapter ID"
    )
    title: str = Field(..., description="Chapter title")
    description: str | None = Field(None, description="Chapter description")
    position: int = Field(..., description="Display order within the course")
    learning_objectives: list[str] = Field(
        default_factory=list, description="Chapter learning objectives"
    )
    estimated_minutes: int | None = Field(
        None, description="Estimated study duration"
    )
    created_at: datetime = Field(..., description="Chapter creation time")
    updated_at: datetime = Field(..., description="Chapter update time")


class KnowledgePointDto(BaseModel):
    """Knowledge point data returned by the API."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique ID of the knowledge point")
    course_id: str = Field(..., description="ID of the parent course")
    chapter_id: str | None = Field(None, description="Optional chapter ID")
    name: str = Field(..., description="Knowledge point name")
    description: str | None = Field(
        None, description="Knowledge point description"
    )
    difficulty_level: str = Field(..., description="Knowledge point difficulty")
    position: int = Field(..., description="Display order within the course")
    tags: list[str] = Field(default_factory=list, description="Knowledge point tags")
    created_at: datetime = Field(..., description="Knowledge point creation time")
    updated_at: datetime = Field(..., description="Knowledge point update time")


class KnowledgePointRelationDto(BaseModel):
    """Directed relation between two knowledge points in a course."""

    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique ID of the relation")
    course_id: str = Field(..., description="ID of the parent course")
    source_knowledge_point_id: str = Field(..., description="Source point ID")
    target_knowledge_point_id: str = Field(..., description="Target point ID")
    relation_type: str = Field(..., description="Relation type")
    strength: float = Field(..., description="Relation strength from 0 to 1")
    description: str | None = Field(None, description="Relation description")
    created_at: datetime = Field(..., description="Relation creation time")
