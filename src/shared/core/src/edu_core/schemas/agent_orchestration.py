from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AgentName(StrEnum):
    SUPERVISOR = "SupervisorAgent"
    PROFILE = "ProfileAgent"
    KT = "KTAgent"
    COLLECTIVE_INSIGHT = "CollectiveInsightAgent"
    DIAGNOSIS = "DiagnosisAgent"
    RESOURCE = "ResourceAgent"
    PLANNER = "PlannerAgent"
    CONTENT = "ContentAgent"
    ASSESSMENT = "AssessmentAgent"
    MEDIA = "MediaAgent"
    EVALUATOR = "Evaluator"


class RunStatus(StrEnum):
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class NodeStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetryClass(StrEnum):
    NEVER = "never"
    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limit"


class RetryPolicy(BaseModel):
    max_attempts: int = Field(1, ge=1, le=5)
    retry_class: RetryClass = RetryClass.NEVER
    initial_delay_seconds: float = Field(0.25, ge=0.0, le=60.0)
    max_delay_seconds: float = Field(5.0, ge=0.0, le=300.0)
    jitter_ratio: float = Field(0.1, ge=0.0, le=1.0)


class BudgetPolicy(BaseModel):
    max_nodes: int = Field(12, ge=1, le=50)
    max_tool_calls: int = Field(24, ge=0, le=200)
    max_input_tokens: int = Field(100_000, ge=0)
    max_output_tokens: int = Field(30_000, ge=0)
    max_cost_micros: int = Field(5_000_000, ge=0)
    max_duration_seconds: int = Field(900, ge=1, le=86_400)
    max_rework_count: int = Field(1, ge=0, le=3)


class PlanNode(BaseModel):
    node_id: str = Field(min_length=1, max_length=100)
    agent_name: AgentName
    depends_on: list[str] = Field(default_factory=list)
    optional: bool = False
    timeout_seconds: int = Field(60, ge=1, le=3600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    schema_version: str = "2.0"
    orchestration_version: str = "orchestration-v2"
    nodes: list[PlanNode]
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)

    @model_validator(mode="after")
    def validate_dag(self):
        if len(self.nodes) > self.budget.max_nodes:
            raise ValueError("execution plan exceeds node budget")
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("execution plan contains duplicate node ids")
        known = set(ids)
        for node in self.nodes:
            missing = set(node.depends_on) - known
            if missing:
                raise ValueError(
                    f"node {node.node_id} has missing dependencies: {sorted(missing)}"
                )
            if node.node_id in node.depends_on:
                raise ValueError(f"node {node.node_id} depends on itself")

        graph = {node.node_id: node.depends_on for node in self.nodes}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("execution plan contains a dependency cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in graph[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        return self


class FieldStatus(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    MISSING = "missing"


class InputReadinessStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    MISSING = "missing"


class Trend(StrEnum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class AgentEventType(StrEnum):
    RUN_QUEUED = "run_queued"
    RUN_STARTED = "run_started"
    ROUTE_DECIDED = "route_decided"
    AGENT_STEP = "agent_step"
    AGENT_SKIPPED = "agent_skipped"
    ARTIFACT_UPDATED = "artifact_updated"
    FALLBACK_APPLIED = "fallback_applied"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCEL_REQUESTED = "run_cancel_requested"
    RUN_CANCELLED = "run_cancelled"
    RUN_PARTIALLY_COMPLETED = "run_partially_completed"
    STEP_STARTED = "step_started"
    STEP_RETRYING = "step_retrying"
    STEP_WAITING_EXTERNAL = "step_waiting_external"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    SKILL_STARTED = "skill_started"
    SKILL_COMPLETED = "skill_completed"
    SKILL_FAILED = "skill_failed"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    TOOL_APPROVAL_REQUIRED = "tool_approval_required"


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
    recent_feedback_summary: dict[str, Any] = Field(default_factory=dict)
    evaluation_report_summary: dict[str, Any] = Field(default_factory=dict)


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
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    field_status: FieldStatus = FieldStatus.INFERRED
    fallback_used: bool = False
    fallback_reason: str | None = None
    skill_executions: list[Any] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    input_artifact_keys: list[str] = Field(default_factory=list)
    output_artifact_keys: list[str] = Field(default_factory=list)
    tool_call_audits: list[Any] = Field(default_factory=list, exclude=True)
    model_name: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_micros: int = Field(default=0, ge=0)


class SupervisorPreflight(BaseModel):
    goal: Literal["diagnosis", "recommendations", "learning_path"]
    input_readiness: dict[str, InputReadinessStatus]
    degrade_mode: list[str] = Field(default_factory=list)
    route_plan: list[AgentName] = Field(default_factory=list)
    selected_skills: dict[str, list[str]] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    event_type: AgentEventType
    run_id: str
    agent_name: AgentName | None = None
    status: RunStatus
    summary: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    sequence: int | None = Field(default=None, ge=1)


class OrchestrationRunRequest(BaseModel):
    project_id: str
    student_id: str
    goal: Literal["diagnosis", "recommendations", "learning_path"] = "diagnosis"
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)
    context: AgentContextData = Field(default_factory=AgentContextData)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)


class AgentRunCreateRequest(BaseModel):
    goal: Literal["diagnosis", "recommendations", "learning_path"] = "diagnosis"
    trigger: AgentTrigger = Field(default_factory=AgentTrigger)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)


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


class AgentRunDetail(BaseModel):
    run_id: str
    project_id: str
    goal: str
    status: str
    final_result: dict[str, Any] = Field(default_factory=dict)
    current_agent_name: str | None = None
    heartbeat_at: datetime | None = None
    duration_ms: int | None = None
    model_name: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_micros: int = 0
    trace_id: str | None = None
    retry_of_run_id: str | None = None
    orchestration_version: str = "orchestration-v1"
    versions: dict[str, str] = Field(default_factory=dict)
    failure_code: str | None = None
    last_event_sequence: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class AgentRunStepDetail(BaseModel):
    step_id: str
    run_id: str
    node_id: str
    agent_name: str
    status: NodeStatus
    depends_on: list[str] = Field(default_factory=list)
    attempt_count: int = 0
    max_attempts: int = 1
    optional: bool = False
    input_artifact_versions: dict[str, int] = Field(default_factory=dict)
    output_artifact_versions: dict[str, int] = Field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    heartbeat_at: datetime | None = None
    duration_ms: int | None = None


class AgentRunFeedbackRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    action: str | None = None
    comment: str | None = Field(default=None, max_length=2000)


class AgentRunRetryRequest(BaseModel):
    mode: Literal["resume_failed", "restart"] = "resume_failed"
