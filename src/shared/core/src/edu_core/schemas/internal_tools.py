from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from edu_core.schemas.agent_orchestration import AgentEvidence, AgentName


ToolCategory = Literal[
    "learner", "knowledge", "practice", "retrieval", "generation", "planning"
]
RiskLevel = Literal["read", "generate", "write", "destructive"]
ApprovalPolicy = Literal["never", "conditional", "always"]
ToolCallStatus = Literal["completed", "failed", "denied", "timeout"]


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    version: str = "1.0"
    display_name: str
    description: str
    category: ToolCategory
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    allowed_agents: list[AgentName]
    risk_level: RiskLevel
    approval_policy: ApprovalPolicy
    timeout_seconds: float = Field(15, gt=0, le=120)
    idempotent: bool = True
    audit_enabled: bool = True
    result_visibility: Literal["hidden", "summary", "details"] = "summary"


class ToolExecutionContext(BaseModel):
    run_id: str
    request_id: str
    user_id: str
    project_id: str
    agent_name: AgentName
    skill_id: str
    user_roles: list[str] = Field(default_factory=list)
    locale: str = "zh-CN"
    approved_tool_calls: list[str] = Field(default_factory=list)


class ToolCallRequest(BaseModel):
    call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ToolCallResult(BaseModel):
    call_id: str
    tool_name: str
    status: ToolCallStatus
    data: dict[str, Any] | list[Any] | None = None
    summary: str
    evidence_refs: list[AgentEvidence] = Field(default_factory=list)
    error_code: str | None = None
    retryable: bool = False
    duration_ms: int


class ToolCallAudit(BaseModel):
    id: str
    run_id: str
    skill_execution_id: str | None = None
    agent_name: AgentName
    skill_id: str | None = None
    tool_name: str
    tool_version: str
    status: ToolCallStatus | Literal["running"]
    risk_level: RiskLevel
    approval_status: Literal["not_required", "approved", "required", "denied"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[AgentEvidence] = Field(default_factory=list)
    idempotency_key: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None


class ToolCallSummary(BaseModel):
    id: str
    tool_name: str
    display_name: str
    status: ToolCallStatus | Literal["running"]
    result_summary: str
    evidence_count: int = 0
    duration_ms: int | None = None
    ui_visibility: Literal["hidden", "summary", "details"] = "summary"
