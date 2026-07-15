from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document processing status enum."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentDto(BaseModel):
    model_config = {"from_attributes": True}

    id: str = Field(..., description="Unique ID of the document")
    owner_id: str = Field(..., description="ID of the document owner")
    project_id: str | None = Field(
        None, description="ID of the project the document belongs to"
    )
    file_name: str = Field(..., description="Name of the document file")
    file_type: str = Field(..., description="File extension (pdf, docx, txt, etc.)")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    status: DocumentStatus = Field(
        ...,
        description="Document processing status: uploaded, processing, processed, failed, indexed",
    )
    summary: str | None = Field(
        None, description="Auto-generated summary of the document"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Display and source metadata for system or course documents",
    )
    uploaded_at: datetime = Field(
        ..., description="Date and time the document was uploaded"
    )
    processed_at: datetime | None = Field(
        None, description="Date and time the document was processed"
    )


class DocumentPageSegmentDto(BaseModel):
    id: str = Field(..., description="Document segment ID")
    page_number: int | None = Field(None, description="PDF page number")
    chunk_index: int = Field(..., description="Chunk order within the page")
    content: str = Field(..., description="Segment text content")


class DocumentPageContextDto(BaseModel):
    document_id: str
    project_id: str
    page_number: int
    content: str
    segments: list[DocumentPageSegmentDto] = Field(default_factory=list)


class DocumentCitationDto(BaseModel):
    document_id: str
    segment_id: str | None = None
    title: str
    page_number: int | None = None
    score: float | None = None
    excerpt: str | None = None


class DocumentQuestionResponseDto(BaseModel):
    answer: str
    citations: list[DocumentCitationDto] = Field(default_factory=list)


class CourseBookDto(BaseModel):
    resource_id: str
    document_id: str
    chapter_id: str | None = None
    title: str
    author: str | None = None
    cover_url: str | None = None
    file_url: str
    status: DocumentStatus
    license: str | None = None
    source_url: str | None = None
    start_page: int | None = None
    end_page: int | None = None
    metadata: dict = Field(default_factory=dict)
