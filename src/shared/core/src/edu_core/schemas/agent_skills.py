from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from edu_core.schemas.agent_orchestration import AgentName
from edu_core.schemas.internal_tools import ToolCallSummary


class SkillDefinition(BaseModel):
    skill_id: str
    version: str
    name: str
    display_name: str
    description: str
    status: Literal["active", "experimental", "disabled"] = "active"
    applicable_agents: list[AgentName]
    execution_mode: Literal["deterministic", "llm", "tool_loop", "hybrid"]
    trigger_conditions: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_tools: list[str] = Field(default_factory=list)
    optional_tools: list[str] = Field(default_factory=list)
    prompt_template: str | None = None
    max_tool_calls: int = Field(6, ge=1, le=20)
    timeout_seconds: float = Field(60, gt=0, le=300)
    quality_gates: list[str] = Field(default_factory=list)
    fallback_skill_id: str | None = None
    ui_visibility: Literal["hidden", "summary", "details"] = "summary"
    tags: list[str] = Field(default_factory=list)


class SkillExecutionSummary(BaseModel):
    id: str
    agent_name: AgentName
    skill_id: str
    display_name: str
    version: str
    status: Literal["running", "completed", "failed"]
    summary: str
    confidence: float | None = Field(None, ge=0, le=1)
    fallback_used: bool = False
    fallback_reason: str | None = None
    duration_ms: int | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    output_artifact_key: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
