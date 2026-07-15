from datetime import datetime

from pydantic import BaseModel, Field


class UsageLimitDto(BaseModel):
    """DTO for usage limit information."""

    used: int = Field(description="Number of operations used today")
    limit: int = Field(description="Maximum number of operations allowed per day")


class ToolUsageDto(BaseModel):
    """Aggregated usage for a tool invoked by the authenticated user today."""

    tool_name: str = Field(description="Stable tool identifier")
    total: int = Field(description="Number of invocations today")
    successful: int = Field(description="Number of successful invocations today")
    failed: int = Field(description="Number of failed invocations today")
    last_used_at: datetime | None = Field(
        default=None,
        description="Timestamp of the most recent invocation today",
    )


class UsageDto(BaseModel):
    """DTO for user usage statistics."""

    chat_messages: UsageLimitDto = Field(description="Chat message usage statistics")
    flashcard_generations: UsageLimitDto = Field(
        description="Flashcard generation usage statistics"
    )
    quiz_generations: UsageLimitDto = Field(
        description="Quiz generation usage statistics"
    )
    mindmap_generations: UsageLimitDto = Field(
        description="Mind map generation usage statistics"
    )
    document_uploads: UsageLimitDto = Field(
        description="Document upload usage statistics"
    )
    tool_usage: list[ToolUsageDto] = Field(
        default_factory=list,
        description="Usage for every tool invoked by the user today",
    )
