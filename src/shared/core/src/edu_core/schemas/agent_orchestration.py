from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    SUPERVISOR = "SupervisorAgent"
    PROFILE = "ProfileAgent"
    KT = "KTAgent"
    COLLECTIVE_INSIGHT = "CollectiveInsightAgent"
    DIAGNOSIS = "DiagnosisAgent"
    RESOURCE = "ResourceAgent"
    PLANNER = "PlannerAgent"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FieldStatus(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    MISSING = "missing"


class Trend(StrEnum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class AgentEventType(StrEnum):
    RUN_STARTED = "run_started"
    AGENT_STEP = "agent_step"
    ARTIFACT_UPDATED = "artifact_updated"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class AgentTrigger(BaseModel):
    type: str = Field("manual", description="Trigger type")
    id: str | None = Field(None, description="Trigger object ID")


class AgentContextData(BaseModel):
    learner_profile: dict[str, Any] | None = None
    knowledge_states: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_state_details: dict[str, dict[str, Any]] = Field(default_factory=dict)
    course: dict[str, Any] | None = None
    chapters: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_points: list[dict[str, Any]] = Field(default_factory=list)
    practice_records: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    resource_packages: list[dict[str, Any]] = Field(default_factory=list)
    generated_resources: list[dict[str, Any]] = Field(default_factory=list)
    collective_insights: list[dict[str, Any]] = Field(default_factory=list)


class AgentRunContext(BaseModel):
    run_id: str
    project_id: str
    student_id: str
    goal: Literal["diagnosis", "recommendations", "learning_path"] = "diagnosis"
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)
    context: AgentContextData = Field(default_factory=AgentContextData)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class AgentEvidence(BaseModel):
    source_type: str
    source_id: str


class AgentResult(BaseModel):
    agent_name: AgentName
    status: RunStatus
    summary: str
    result: dict[str, Any] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    reason_text: list[str] = Field(default_factory=list)
    evidences: list[AgentEvidence] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    event_type: AgentEventType
    run_id: str
    agent_name: AgentName | None = None
    status: RunStatus
    summary: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrationRunRequest(BaseModel):
    project_id: str
    student_id: str
    goal: Literal["diagnosis", "recommendations", "learning_path"] = "diagnosis"
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)
    context: AgentContextData = Field(default_factory=AgentContextData)
    meta: dict[str, Any] = Field(default_factory=dict)


class SupervisorRunResult(BaseModel):
    run_id: str
    status: RunStatus
    context: AgentRunContext
    agent_results: list[AgentResult] = Field(default_factory=list)
    events: list[AgentEvent] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)


class DiagnosisCreateRequest(BaseModel):
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)


class DiagnosisResponse(BaseModel):
    diagnosis_id: str
    run_id: str
    project_id: str
    student_id: str
    status: RunStatus
    diagnosis: dict[str, Any]
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    learning_path: dict[str, Any] | None = None
    next_actions: list[str] = Field(default_factory=list)
    created_at: datetime


class RecommendationGenerateRequest(BaseModel):
    diagnosis_id: str | None = None
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)


class RecommendationsResponse(BaseModel):
    run_id: str
    project_id: str
    recommendations: list[dict[str, Any]]
    based_on_diagnosis_id: str | None = None
    created_at: datetime


class LearningPathGenerateRequest(BaseModel):
    diagnosis_id: str | None = None
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)


class LearningPathResponse(BaseModel):
    path_id: str
    run_id: str
    project_id: str
    learning_path: dict[str, Any]
    based_on_diagnosis_id: str | None = None
    based_on_recommendation_ids: list[str] = Field(default_factory=list)
    created_at: datetime
