from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from edu_ai.agents.orchestration import SupervisorAgent
from edu_ai.agents.orchestration.executor import OrchestrationExecutor
from edu_ai.agents.orchestration.resource_agent import ResourceAgent
from edu_core.exceptions import NotFoundError
from edu_core.model_providers import LlmProviderConfig
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEvent,
    AgentRunDetail,
    AgentRunFeedbackRequest,
    AgentRunContext,
    AgentRunStepDetail,
    AgentTrigger,
    DiagnosisResponse,
    LearningPathResponse,
    OrchestrationRunRequest,
    RecommendationsResponse,
    RunStatus,
    SupervisorRunResult,
    ExecutionPlan,
    AgentEventType,
    NodeStatus,
)
from edu_db.models import (
    AgentArtifact as AgentArtifactModel,
    AgentEvent as AgentEventModel,
    AgentRun,
    AgentRunFeedback,
    AgentRunStep,
    AgentToolCall,
    CollectiveInsight,
    Diagnosis,
    Document,
    GeneratedResource,
    KnowledgePoint,
    KnowledgePointRelation,
    LearnerProfile,
    LearningPath,
    LearningEvidenceEvent,
    PracticeRecord,
    Project,
    Recommendation,
    ResourcePackage,
    StudentKnowledgeState,
    SkillExecution,
)
from edu_db.session import get_session_factory
from pydantic import BaseModel

ARTIFACT_AGENT_NAMES = {
    "profile": "ProfileAgent",
    "knowledge_state": "KTAgent",
    "collective_insight": "CollectiveInsightAgent",
    "diagnosis": "DiagnosisAgent",
    "recommendations": "ResourceAgent",
    "learning_path": "PlannerAgent",
    "content_resources": "ContentAgent",
    "assessment_resources": "AssessmentAgent",
    "media_resources": "MediaAgent",
    "evaluation": "Evaluator",
}


class InMemoryOrchestrationStore:
    def __init__(self) -> None:
        self.diagnoses: dict[str, DiagnosisResponse] = {}
        self.diagnosis_by_run_id: dict[str, str] = {}
        self.events_by_run_id: dict[str, list[AgentEvent]] = {}
        self.recommendations_by_project: dict[str, list[RecommendationsResponse]] = {}
        self.learning_paths_by_project: dict[str, list[LearningPathResponse]] = {}

    def save_run_events(self, result: SupervisorRunResult) -> None:
        self.events_by_run_id[result.run_id] = result.events

    def save_diagnosis(self, diagnosis: DiagnosisResponse) -> None:
        self.diagnoses[diagnosis.diagnosis_id] = diagnosis
        self.diagnosis_by_run_id[diagnosis.run_id] = diagnosis.diagnosis_id

    def get_diagnosis(self, diagnosis_id: str) -> DiagnosisResponse | None:
        return self.diagnoses.get(diagnosis_id)

    def get_events_for_diagnosis(self, diagnosis_id: str) -> list[AgentEvent] | None:
        diagnosis = self.get_diagnosis(diagnosis_id)
        if not diagnosis:
            return None
        return self.events_by_run_id.get(diagnosis.run_id, [])

    def save_recommendations(self, response: RecommendationsResponse) -> None:
        self.recommendations_by_project.setdefault(response.project_id, []).insert(
            0, response
        )

    def list_recommendations(self, project_id: str) -> list[dict]:
        if not self.recommendations_by_project.get(project_id):
            return []
        return self.recommendations_by_project[project_id][0].recommendations

    def save_learning_path(self, response: LearningPathResponse) -> None:
        self.learning_paths_by_project.setdefault(response.project_id, []).insert(
            0, response
        )

    def get_latest_learning_path(self, project_id: str) -> LearningPathResponse | None:
        paths = self.learning_paths_by_project.get(project_id, [])
        return paths[0] if paths else None

    def list_learning_paths(self, project_id: str) -> list[LearningPathResponse]:
        return self.learning_paths_by_project.get(project_id, [])


ORCHESTRATION_STORE = InMemoryOrchestrationStore()


class DatabaseOrchestrationStore:
    def create_run(
        self,
        request: OrchestrationRunRequest,
        plan: ExecutionPlan,
    ) -> str:
        run_id = str(request.meta.get("run_id") or f"run_{uuid4().hex}")
        trace_id = str(request.meta.get("trace_id") or f"trace_{uuid4().hex}")
        snapshot_id = str(
            request.meta.get("context_snapshot_id") or f"snapshot_{uuid4().hex}"
        )
        with self._get_db_session() as db:
            if request.idempotency_key:
                existing = (
                    db.query(AgentRun)
                    .filter(
                        AgentRun.user_id == request.student_id,
                        AgentRun.project_id == request.project_id,
                        AgentRun.idempotency_key == request.idempotency_key,
                    )
                    .first()
                )
                if existing:
                    return existing.id
            run = AgentRun(
                id=run_id,
                project_id=request.project_id,
                user_id=request.student_id,
                goal=request.goal,
                status=RunStatus.QUEUED.value,
                trigger=self._to_json(request.trigger),
                context_snapshot=self._to_json(request.context),
                request_meta=self._to_json(request.meta),
                context_snapshot_id=snapshot_id,
                final_result={},
                orchestration_version=plan.orchestration_version,
                budget=self._to_json(plan.budget),
                usage={},
                versions={
                    "orchestration": plan.orchestration_version,
                    "routing": "policy-router-v2",
                    "prompt": "prompt-catalog-v1",
                    "model": str(request.meta.get("model_version") or "configured-default"),
                    "skill_catalog": "skill-catalog-v1",
                    "tool_catalog": "tool-catalog-v1",
                    "artifact_schema": "2.0",
                },
                last_event_sequence=0,
                idempotency_key=request.idempotency_key,
                trace_id=trace_id,
                heartbeat_at=self._now(),
            )
            db.add(run)
            for position, node in enumerate(plan.nodes):
                db.add(
                    AgentRunStep(
                        id=str(uuid4()),
                        run_id=run_id,
                        node_id=node.node_id,
                        agent_name=node.agent_name.value,
                        position=position,
                        status=NodeStatus.QUEUED.value,
                        depends_on=node.depends_on,
                        optional=node.optional,
                        max_attempts=node.retry_policy.max_attempts,
                        timeout_seconds=node.timeout_seconds,
                    )
                )
            for artifact_key, artifact in request.artifacts.items():
                normalized_artifact = self._to_json(artifact)
                db.add(
                    AgentArtifactModel(
                        id=str(uuid4()),
                        run_id=run_id,
                        agent_name=ARTIFACT_AGENT_NAMES.get(
                            artifact_key, "ExternalInput"
                        ),
                        artifact_key=artifact_key,
                        artifact=normalized_artifact,
                        schema_version="2.0",
                        artifact_version=1,
                        content_hash=self._artifact_hash(normalized_artifact),
                        source_snapshot_id=snapshot_id,
                        validation_status="valid",
                    )
                )
            db.commit()
        return run_id

    def append_event(self, event: AgentEvent) -> AgentEvent:
        """Persist an event before projecting it to SSE consumers."""

        with self._get_db_session() as db:
            run = (
                db.query(AgentRun)
                .filter(AgentRun.id == event.run_id)
                .with_for_update()
                .first()
            )
            if not run:
                raise NotFoundError(f"Agent run {event.run_id} not found")
            sequence = int(run.last_event_sequence or 0) + 1
            event.sequence = sequence
            run.last_event_sequence = sequence
            run.heartbeat_at = event.timestamp
            if event.agent_name and event.agent_name.value != "SupervisorAgent":
                run.current_agent_name = event.agent_name.value
            if event.event_type == AgentEventType.RUN_STARTED:
                run.status = RunStatus.RUNNING.value
                run.started_at = run.started_at or event.timestamp
            elif event.event_type == AgentEventType.RUN_COMPLETED:
                run.status = RunStatus.COMPLETED.value
            elif event.event_type == AgentEventType.RUN_PARTIALLY_COMPLETED:
                run.status = RunStatus.PARTIALLY_COMPLETED.value
            elif event.event_type == AgentEventType.RUN_FAILED:
                run.status = RunStatus.FAILED.value
            elif event.event_type == AgentEventType.RUN_CANCELLED:
                run.status = RunStatus.CANCELLED.value

            db.add(
                AgentEventModel(
                    id=str(uuid4()),
                    run_id=event.run_id,
                    sequence=sequence,
                    event_type=event.event_type.value,
                    agent_name=event.agent_name.value if event.agent_name else None,
                    status=event.status.value,
                    summary=event.summary,
                    payload=self._to_json(event.payload),
                    created_at=event.timestamp,
                )
            )
            self._project_step_event(db, event)
            db.commit()
        return event

    def _project_step_event(self, db, event: AgentEvent) -> None:
        if not event.agent_name or event.agent_name.value == "SupervisorAgent":
            return
        step = (
            db.query(AgentRunStep)
            .filter(
                AgentRunStep.run_id == event.run_id,
                AgentRunStep.agent_name == event.agent_name.value,
            )
            .first()
        )
        if not step:
            return
        phase = str(event.payload.get("phase") or "")
        if event.event_type in {AgentEventType.STEP_STARTED} or (
            event.event_type == AgentEventType.AGENT_STEP
            and phase in {"running", "started"}
        ):
            step.status = NodeStatus.RUNNING.value
            step.attempt_count = max(1, step.attempt_count + 1)
            step.started_at = step.started_at or event.timestamp
            step.heartbeat_at = event.timestamp
        elif event.event_type in {AgentEventType.STEP_COMPLETED} or (
            event.event_type == AgentEventType.AGENT_STEP and phase == "completed"
        ):
            step.status = NodeStatus.COMPLETED.value
            step.completed_at = event.timestamp
            step.heartbeat_at = event.timestamp
            if step.started_at:
                step.duration_ms = max(
                    0, int((event.timestamp - step.started_at).total_seconds() * 1000)
                )
        elif event.event_type in {AgentEventType.STEP_FAILED}:
            step.status = NodeStatus.FAILED.value
            step.error_code = str(event.payload.get("error_code") or "agent_failed")
            step.error_summary = str(event.payload.get("error_summary") or event.summary)[:2000]
            step.completed_at = event.timestamp

    def cancellation_requested(self, run_id: str) -> bool:
        with self._get_db_session() as db:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            return bool(run and run.cancellation_requested_at)

    def complete_run(self, result: SupervisorRunResult) -> None:
        """Persist terminal output while retaining already written events."""

        with self._get_db_session() as db:
            run = db.query(AgentRun).filter(AgentRun.id == result.run_id).first()
            if not run:
                raise NotFoundError(f"Agent run {result.run_id} not found")
            completed_at = self._now()
            run.status = result.status.value
            run.final_result = self._to_json(result.final_result)
            run.error_message = result.final_result.get("error")
            run.failure_code = (
                str(result.final_result.get("failure_code") or "orchestration_failed")
                if result.status == RunStatus.FAILED
                else None
            )
            run.completed_at = completed_at
            run.heartbeat_at = completed_at
            run.current_agent_name = None
            if run.started_at:
                run.duration_ms = max(
                    0, int((completed_at - run.started_at).total_seconds() * 1000)
                )
            for artifact_key, artifact in result.context.artifacts.items():
                normalized_artifact = self._to_json(artifact)
                content_hash = self._artifact_hash(normalized_artifact)
                latest = (
                    db.query(AgentArtifactModel)
                    .filter(
                        AgentArtifactModel.run_id == result.run_id,
                        AgentArtifactModel.artifact_key == artifact_key,
                    )
                    .order_by(AgentArtifactModel.artifact_version.desc())
                    .first()
                )
                if latest and latest.content_hash == content_hash:
                    continue
                db.add(
                    AgentArtifactModel(
                        id=str(uuid4()),
                        run_id=result.run_id,
                        agent_name=ARTIFACT_AGENT_NAMES.get(artifact_key, "UnknownAgent"),
                        artifact_key=artifact_key,
                        artifact=normalized_artifact,
                        schema_version="2.0",
                        artifact_version=(latest.artifact_version + 1) if latest else 1,
                        content_hash=content_hash,
                        source_snapshot_id=run.context_snapshot_id,
                        validation_status="valid",
                    )
                )
            for agent_result in result.agent_results:
                for skill in agent_result.skill_executions:
                    completed_at = self._now()
                    started_at = completed_at
                    if skill.duration_ms:
                        started_at = completed_at - timedelta(
                            milliseconds=skill.duration_ms
                        )
                    if not db.query(SkillExecution).filter(
                        SkillExecution.id == skill.id
                    ).first():
                        db.add(
                            SkillExecution(
                                id=skill.id,
                                run_id=result.run_id,
                                agent_name=skill.agent_name.value,
                                skill_id=skill.skill_id,
                                skill_version=skill.version,
                                status=skill.status,
                                input_summary=self._to_json(skill.input_summary),
                                output_summary=self._to_json(skill.output_summary),
                                output_artifact_key=skill.output_artifact_key,
                                confidence=skill.confidence,
                                fallback_used=skill.fallback_used,
                                fallback_reason=skill.fallback_reason,
                                error_code=skill.error_code,
                                error_message=skill.error_message,
                                started_at=started_at,
                                completed_at=completed_at,
                                duration_ms=skill.duration_ms,
                            )
                        )
                for audit in agent_result.tool_call_audits:
                    if db.query(AgentToolCall).filter(
                        AgentToolCall.id == audit.id
                    ).first():
                        continue
                    db.add(
                        AgentToolCall(
                            id=audit.id,
                            run_id=result.run_id,
                            skill_execution_id=next(
                                (
                                    skill.id
                                    for skill in agent_result.skill_executions
                                    if skill.skill_id == audit.skill_id
                                ),
                                None,
                            ),
                            agent_name=audit.agent_name.value,
                            skill_id=audit.skill_id,
                            tool_name=audit.tool_name,
                            tool_version=audit.tool_version,
                            status=audit.status,
                            risk_level=audit.risk_level,
                            approval_status=audit.approval_status,
                            arguments=self._to_json(audit.arguments),
                            result_summary=self._to_json(audit.result_summary),
                            evidence_refs=self._to_json(audit.evidence_refs),
                            idempotency_key=audit.idempotency_key,
                            error_code=audit.error_code,
                            error_message=audit.error_message,
                            started_at=audit.started_at,
                            completed_at=audit.completed_at,
                            duration_ms=audit.duration_ms,
                        )
                    )
            db.commit()

    def persist_artifact(
        self,
        run_id: str,
        artifact_key: str,
        artifact: dict,
        agent_name: str,
    ) -> None:
        """Durably checkpoint a validated node output before downstream work."""

        normalized_artifact = self._to_json(artifact)
        content_hash = self._artifact_hash(normalized_artifact)
        with self._get_db_session() as db:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not run:
                raise NotFoundError(f"Agent run {run_id} not found")
            latest = (
                db.query(AgentArtifactModel)
                .filter(
                    AgentArtifactModel.run_id == run_id,
                    AgentArtifactModel.artifact_key == artifact_key,
                )
                .order_by(AgentArtifactModel.artifact_version.desc())
                .first()
            )
            if latest and latest.content_hash == content_hash:
                return
            db.add(
                AgentArtifactModel(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_name=agent_name,
                    artifact_key=artifact_key,
                    artifact=normalized_artifact,
                    schema_version="2.0",
                    artifact_version=(latest.artifact_version + 1) if latest else 1,
                    content_hash=content_hash,
                    source_snapshot_id=run.context_snapshot_id,
                    validation_status="valid",
                )
            )
            db.commit()

    @staticmethod
    def _artifact_hash(artifact: dict) -> str:
        encoded = json.dumps(
            artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def mark_cancelled(self, run_id: str) -> None:
        with self._get_db_session() as db:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not run:
                return
            now = self._now()
            run.status = RunStatus.CANCELLED.value
            run.completed_at = now
            run.heartbeat_at = now
            run.current_agent_name = None
            if run.started_at:
                run.duration_ms = max(
                    0, int((now - run.started_at).total_seconds() * 1000)
                )
            db.query(AgentRunStep).filter(
                AgentRunStep.run_id == run_id,
                AgentRunStep.status.in_(["queued", "running", "waiting_external"]),
            ).update(
                {
                    AgentRunStep.status: NodeStatus.CANCELLED.value,
                    AgentRunStep.completed_at: now,
                },
                synchronize_session=False,
            )
            db.commit()

    def save_run_events(self, result: SupervisorRunResult) -> None:
        with self._get_db_session() as db:
            existing = db.query(AgentRun).filter(AgentRun.id == result.run_id).first()
            if not existing:
                db.add(
                    AgentRun(
                        id=result.run_id,
                        project_id=result.context.project_id,
                        user_id=result.context.student_id,
                        goal=result.context.goal,
                        status=result.status.value,
                        trigger=self._to_json(result.context.trigger),
                        context_snapshot=self._to_json(result.context.context),
                        final_result=self._to_json(result.final_result),
                        error_message=result.final_result.get("error"),
                        started_at=result.events[0].timestamp
                        if result.events
                        else self._now(),
                        completed_at=result.events[-1].timestamp
                        if result.events
                        else None,
                    )
                )

            next_sequence = int(existing.last_event_sequence or 0) if existing else 0
            for event in result.events:
                next_sequence += 1
                db.add(
                    AgentEventModel(
                        id=str(uuid4()),
                        run_id=event.run_id,
                        sequence=event.sequence or next_sequence,
                        event_type=event.event_type.value,
                        agent_name=event.agent_name.value if event.agent_name else None,
                        status=event.status.value,
                        summary=event.summary,
                        payload=self._to_json(event.payload),
                        created_at=event.timestamp,
                    )
                )
            if existing:
                existing.last_event_sequence = next_sequence

            for artifact_key, artifact in result.context.artifacts.items():
                db.add(
                    AgentArtifactModel(
                        id=str(uuid4()),
                        run_id=result.run_id,
                        agent_name=ARTIFACT_AGENT_NAMES.get(
                            artifact_key, "UnknownAgent"
                        ),
                        artifact_key=artifact_key,
                        artifact=self._to_json(artifact),
                    )
                )

            for agent_result in result.agent_results:
                for skill in agent_result.skill_executions:
                    completed_at = self._now()
                    started_at = completed_at
                    if skill.duration_ms:
                        started_at = completed_at - timedelta(milliseconds=skill.duration_ms)
                    db.add(
                        SkillExecution(
                            id=skill.id,
                            run_id=result.run_id,
                            agent_name=skill.agent_name.value,
                            skill_id=skill.skill_id,
                            skill_version=skill.version,
                            status=skill.status,
                            input_summary=self._to_json(skill.input_summary),
                            output_summary=self._to_json(skill.output_summary),
                            output_artifact_key=skill.output_artifact_key,
                            confidence=skill.confidence,
                            fallback_used=skill.fallback_used,
                            fallback_reason=skill.fallback_reason,
                            error_code=skill.error_code,
                            error_message=skill.error_message,
                            started_at=started_at,
                            completed_at=completed_at,
                            duration_ms=skill.duration_ms,
                        )
                    )
                for audit in agent_result.tool_call_audits:
                    db.add(
                        AgentToolCall(
                            id=audit.id,
                            run_id=result.run_id,
                            skill_execution_id=next(
                                (
                                    skill.id
                                    for skill in agent_result.skill_executions
                                    if skill.skill_id == audit.skill_id
                                ),
                                None,
                            ),
                            agent_name=audit.agent_name.value,
                            skill_id=audit.skill_id,
                            tool_name=audit.tool_name,
                            tool_version=audit.tool_version,
                            status=audit.status,
                            risk_level=audit.risk_level,
                            approval_status=audit.approval_status,
                            arguments=self._to_json(audit.arguments),
                            result_summary=self._to_json(audit.result_summary),
                            evidence_refs=self._to_json(audit.evidence_refs),
                            idempotency_key=audit.idempotency_key,
                            error_code=audit.error_code,
                            error_message=audit.error_message,
                            started_at=audit.started_at,
                            completed_at=audit.completed_at,
                            duration_ms=audit.duration_ms,
                        )
                    )

            db.commit()

    def save_diagnosis(self, diagnosis: DiagnosisResponse) -> None:
        with self._get_db_session() as db:
            existing = (
                db.query(Diagnosis).filter(Diagnosis.id == diagnosis.diagnosis_id).first()
            )
            if not existing:
                db.add(
                    Diagnosis(
                        id=diagnosis.diagnosis_id,
                        run_id=diagnosis.run_id,
                        project_id=diagnosis.project_id,
                        user_id=diagnosis.student_id,
                        status=diagnosis.status.value,
                        diagnosis=self._to_json(diagnosis.diagnosis),
                        next_actions=self._to_json(diagnosis.next_actions),
                        created_at=diagnosis.created_at,
                    )
                )
            db.commit()

    def get_diagnosis(self, diagnosis_id: str) -> DiagnosisResponse | None:
        with self._get_db_session() as db:
            diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
            if not diagnosis:
                return None

            recommendations = (
                db.query(Recommendation)
                .filter(Recommendation.diagnosis_id == diagnosis.id)
                .order_by(Recommendation.created_at.desc())
                .all()
            )
            recommendation_items = [
                self._recommendation_to_dict(item) for item in recommendations
            ]
            if not recommendation_items:
                artifact = (
                    db.query(AgentArtifactModel)
                    .filter(
                        AgentArtifactModel.run_id == diagnosis.run_id,
                        AgentArtifactModel.artifact_key == "recommendations",
                    )
                    .first()
                )
                recommendation_items = (artifact.artifact or {}).get(
                    "recommendations", []
                ) if artifact else []

            learning_path = (
                db.query(LearningPath)
                .filter(LearningPath.diagnosis_id == diagnosis.id)
                .order_by(LearningPath.created_at.desc())
                .first()
            )
            learning_path_content = learning_path.content if learning_path else None
            if learning_path_content is None:
                artifact = (
                    db.query(AgentArtifactModel)
                    .filter(
                        AgentArtifactModel.run_id == diagnosis.run_id,
                        AgentArtifactModel.artifact_key == "learning_path",
                    )
                    .first()
                )
                learning_path_content = (artifact.artifact or {}).get(
                    "learning_path"
                ) if artifact else None

            return DiagnosisResponse(
                diagnosis_id=diagnosis.id,
                run_id=diagnosis.run_id,
                project_id=diagnosis.project_id,
                student_id=diagnosis.user_id,
                status=diagnosis.status,
                diagnosis=diagnosis.diagnosis,
                recommendations=recommendation_items,
                learning_path=learning_path_content,
                next_actions=diagnosis.next_actions,
                created_at=diagnosis.created_at,
            )

    def get_events_for_diagnosis(self, diagnosis_id: str) -> list[AgentEvent] | None:
        with self._get_db_session() as db:
            diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
            if not diagnosis:
                return None
            events = (
                db.query(AgentEventModel)
                .filter(AgentEventModel.run_id == diagnosis.run_id)
                .order_by(AgentEventModel.created_at.asc())
                .all()
            )
            return [
                AgentEvent(
                    event_type=event.event_type,
                    run_id=event.run_id,
                    agent_name=event.agent_name,
                    status=event.status,
                    summary=event.summary,
                    timestamp=event.created_at,
                    payload=event.payload or {},
                )
                for event in events
            ]

    def save_recommendations(self, response: RecommendationsResponse) -> None:
        with self._get_db_session() as db:
            diagnosis = None
            user_id = None
            if response.based_on_diagnosis_id:
                diagnosis = (
                    db.query(Diagnosis)
                    .filter(Diagnosis.id == response.based_on_diagnosis_id)
                    .first()
                )
                user_id = diagnosis.user_id if diagnosis else None
            if user_id is None:
                run = db.query(AgentRun).filter(AgentRun.id == response.run_id).first()
                user_id = run.user_id if run else None
            if user_id is None:
                return

            for recommendation in response.recommendations:
                recommendation_id = recommendation["id"]
                existing = (
                    db.query(Recommendation)
                    .filter(Recommendation.id == recommendation_id)
                    .first()
                )
                if existing:
                    continue
                db.add(
                    Recommendation(
                        id=recommendation_id,
                        run_id=response.run_id,
                        diagnosis_id=diagnosis.id if diagnosis else None,
                        project_id=response.project_id,
                        user_id=user_id,
                        recommendation_type=recommendation.get(
                            "recommendation_type", "resource"
                        ),
                        target_id=recommendation.get("target_id"),
                        title=recommendation.get("title", "推荐项"),
                        reason_codes=self._to_json(
                            recommendation.get("reason_codes", [])
                        ),
                        reason_text=self._to_json(
                            recommendation.get("reason_text", [])
                        ),
                        score=recommendation.get("score"),
                        recommended_by=recommendation.get("recommended_by"),
                        feedback=recommendation.get("feedback"),
                        created_at=response.created_at,
                    )
                )
            db.commit()

    def list_recommendations(self, project_id: str) -> list[dict]:
        with self._get_db_session() as db:
            recommendations = (
                db.query(Recommendation)
                .filter(Recommendation.project_id == project_id)
                .order_by(Recommendation.created_at.desc())
                .all()
            )
            return [
                self._recommendation_to_dict(item) for item in recommendations
            ]

    def save_learning_path(self, response: LearningPathResponse) -> None:
        with self._get_db_session() as db:
            existing = (
                db.query(LearningPath)
                .filter(LearningPath.id == response.path_id)
                .first()
            )
            if existing:
                return

            user_id = None
            if response.based_on_diagnosis_id:
                diagnosis = (
                    db.query(Diagnosis)
                    .filter(Diagnosis.id == response.based_on_diagnosis_id)
                    .first()
                )
                user_id = diagnosis.user_id if diagnosis else None
            if user_id is None:
                run = db.query(AgentRun).filter(AgentRun.id == response.run_id).first()
                user_id = run.user_id if run else None
            if user_id is None:
                return

            db.add(
                LearningPath(
                    id=response.path_id,
                    run_id=response.run_id,
                    diagnosis_id=response.based_on_diagnosis_id,
                    project_id=response.project_id,
                    user_id=user_id,
                    content=self._to_json(response.learning_path),
                    based_on_recommendation_ids=self._to_json(
                        response.based_on_recommendation_ids
                    ),
                    created_at=response.created_at,
                    updated_at=response.created_at,
                )
            )
            db.commit()

    def get_latest_learning_path(self, project_id: str) -> LearningPathResponse | None:
        with self._get_db_session() as db:
            path = (
                db.query(LearningPath)
                .filter(LearningPath.project_id == project_id)
                .order_by(LearningPath.created_at.desc())
                .first()
            )
            return self._learning_path_to_response(path, db) if path else None

    def list_learning_paths(self, project_id: str) -> list[LearningPathResponse]:
        with self._get_db_session() as db:
            paths = (
                db.query(LearningPath)
                .filter(LearningPath.project_id == project_id)
                .order_by(LearningPath.created_at.desc())
                .all()
            )
            return [self._learning_path_to_response(path, db) for path in paths]

    def _recommendation_to_dict(self, recommendation: Recommendation) -> dict:
        return {
            "id": recommendation.id,
            "recommendation_type": recommendation.recommendation_type,
            "target_id": recommendation.target_id,
            "title": recommendation.title,
            "reason_codes": recommendation.reason_codes,
            "reason_text": recommendation.reason_text,
            "score": recommendation.score,
            "recommended_by": recommendation.recommended_by,
        }

    def _learning_path_to_response(
        self, path: LearningPath, db=None
    ) -> LearningPathResponse:
        content = self._resolve_knowledge_point_labels(path.content, db)
        return LearningPathResponse(
            path_id=path.id,
            run_id=path.run_id,
            project_id=path.project_id,
            learning_path=content,
            based_on_diagnosis_id=path.diagnosis_id,
            based_on_recommendation_ids=path.based_on_recommendation_ids,
            created_at=path.created_at,
        )

    @staticmethod
    def _resolve_knowledge_point_labels(content: dict, db) -> dict:
        """Resolve legacy knowledge point IDs when reading persisted paths."""
        resolved = dict(content or {})
        values = [
            value
            for value in resolved.get("based_on_knowledge_points", [])
            if isinstance(value, str) and value
        ]
        if not db or not values:
            return resolved

        name_by_id = {
            point.id: point.name
            for point in db.query(KnowledgePoint)
            .filter(KnowledgePoint.id.in_(values))
            .all()
        }
        resolved["based_on_knowledge_points"] = [
            name_by_id.get(value, value) for value in values
        ]
        return resolved

    def _to_json(self, value):
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [self._to_json(item) for item in value]
        if isinstance(value, dict):
            return {key: self._to_json(item) for key, item in value.items()}
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @contextmanager
    def _get_db_session(self):
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class AgentOrchestrationService:
    def __init__(
        self,
        supervisor: SupervisorAgent | None = None,
        store: InMemoryOrchestrationStore | DatabaseOrchestrationStore | None = None,
        llm_config: LlmProviderConfig | None = None,
        flashcard_group_service=None,
        quiz_service=None,
        note_service=None,
        mind_map_service=None,
    ) -> None:
        self.supervisor = supervisor or SupervisorAgent(
            llm_config=llm_config,
            resource_agent=ResourceAgent(
                flashcard_group_service=flashcard_group_service,
                quiz_service=quiz_service,
                note_service=note_service,
                mind_map_service=mind_map_service,
            )
        )
        self.store = store or DatabaseOrchestrationStore()

    async def generate_diagnosis(
        self,
        user_id: str,
        project_id: str,
        trigger: AgentTrigger | None = None,
        meta: dict | None = None,
        event_sink: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ) -> DiagnosisResponse:
        result = await self._run_supervisor(
            user_id=user_id,
            project_id=project_id,
            goal="diagnosis",
            trigger=trigger,
            meta=meta,
            event_sink=event_sink,
        )
        self.store.save_run_events(result)

        diagnosis = DiagnosisResponse(
            diagnosis_id=f"diag_{uuid4().hex}",
            run_id=result.run_id,
            project_id=project_id,
            student_id=user_id,
            status=result.status,
            diagnosis=result.final_result.get("diagnosis", {}),
            recommendations=result.final_result.get("recommendations", []),
            learning_path=result.final_result.get("learning_path"),
            next_actions=["generate_recommendations", "generate_learning_path"]
            if result.status == RunStatus.COMPLETED
            else [],
            created_at=self._now(),
        )
        self.store.save_diagnosis(diagnosis)
        return diagnosis

    def get_diagnosis(self, diagnosis_id: str) -> DiagnosisResponse:
        diagnosis = self.store.get_diagnosis(diagnosis_id)
        if not diagnosis:
            raise NotFoundError(f"Diagnosis {diagnosis_id} not found")
        return diagnosis

    def get_diagnosis_trace(self, diagnosis_id: str) -> list[AgentEvent]:
        events = self.store.get_events_for_diagnosis(diagnosis_id)
        if events is None:
            raise NotFoundError(f"Diagnosis {diagnosis_id} not found")
        return events

    def create_agent_run(
        self,
        user_id: str,
        project_id: str,
        request: OrchestrationRunRequest,
    ) -> AgentRunDetail:
        """Create a queryable run and its validated steps before execution."""

        self._ensure_project_access(user_id, project_id)
        if request.student_id != user_id or request.project_id != project_id:
            request = request.model_copy(
                update={"student_id": user_id, "project_id": project_id}
            )
        context = self._load_context(user_id, project_id)
        run_id = str(request.meta.get("run_id") or f"run_{uuid4().hex}")
        hydrated = request.model_copy(
            update={
                "context": context,
                "meta": {
                    **request.meta,
                    "run_id": run_id,
                    "agent_runtime_v2": True,
                },
            }
        )
        plan = self.supervisor.build_execution_plan(hydrated)
        if not isinstance(self.store, DatabaseOrchestrationStore):
            raise RuntimeError("persistent agent runs require the database store")
        persisted_id = self.store.create_run(hydrated, plan)
        return self.get_agent_run(user_id, persisted_id)

    async def execute_agent_run(self, user_id: str, run_id: str) -> None:
        """Execute a previously created run with incremental event persistence."""

        if not isinstance(self.store, DatabaseOrchestrationStore):
            raise RuntimeError("persistent agent runs require the database store")
        with self._get_db_session() as db:
            run = (
                db.query(AgentRun)
                .filter(AgentRun.id == run_id, AgentRun.user_id == user_id)
                .with_for_update()
                .first()
            )
            if not run:
                raise NotFoundError(f"Agent run {run_id} not found")
            now = self._now()
            stale_cutoff = now - timedelta(seconds=120)
            if run.status == RunStatus.RUNNING.value and (
                run.heartbeat_at and run.heartbeat_at >= stale_cutoff
            ):
                return
            if run.status not in {
                RunStatus.QUEUED.value,
                RunStatus.PENDING.value,
                RunStatus.RUNNING.value,
            }:
                return
            recovering = run.status == RunStatus.RUNNING.value
            run.status = RunStatus.RUNNING.value
            run.started_at = run.started_at or now
            run.heartbeat_at = now
            validated_artifacts = self._validated_artifacts(db, run.id)
            completed_agents = [
                step.agent_name
                for step in db.query(AgentRunStep)
                .filter(
                    AgentRunStep.run_id == run.id,
                    AgentRunStep.status == NodeStatus.COMPLETED.value,
                )
                .all()
            ]
            request = OrchestrationRunRequest(
                project_id=run.project_id,
                student_id=run.user_id,
                goal=run.goal,
                trigger=run.trigger or {},
                context=run.context_snapshot or {},
                artifacts=validated_artifacts,
                meta={
                    **(run.request_meta or {}),
                    "run_id": run.id,
                    "trace_id": run.trace_id,
                    "context_snapshot_id": run.context_snapshot_id,
                    "agent_runtime_v2": True,
                    "recovered": recovering,
                    "resume_skip_agents": completed_agents if recovering else [],
                },
                budget=run.budget or {},
            )
            db.commit()

        async def persist_event(event: AgentEvent) -> None:
            self.store.append_event(event)

        async def persist_artifact(artifact_key: str, result) -> None:
            self.store.persist_artifact(
                run_id,
                artifact_key,
                result.result,
                result.agent_name.value,
            )

        try:
            context = AgentRunContext(
                run_id=run_id,
                project_id=request.project_id,
                student_id=request.student_id,
                goal=request.goal,
                trigger=request.trigger,
                context=request.context,
                artifacts=dict(request.artifacts),
                meta=request.meta,
            )
            plan = self.supervisor.build_execution_plan(request)
            await persist_event(
                AgentEvent(
                    event_type=AgentEventType.RUN_STARTED,
                    run_id=run_id,
                    agent_name=None,
                    status=RunStatus.RUNNING,
                    summary="Agent orchestration started.",
                    timestamp=self._now(),
                    payload={
                        "goal": request.goal,
                        "orchestration_version": plan.orchestration_version,
                    },
                )
            )
            await persist_event(
                AgentEvent(
                    event_type=AgentEventType.ROUTE_DECIDED,
                    run_id=run_id,
                    agent_name=None,
                    status=RunStatus.COMPLETED,
                    summary="Validated execution DAG accepted.",
                    timestamp=self._now(),
                    payload={
                        "route_plan": [node.agent_name.value for node in plan.nodes],
                        "node_ids": [node.node_id for node in plan.nodes],
                    },
                )
            )
            agents = {agent.agent_name: agent for agent in self.supervisor.agents}
            outcome = await OrchestrationExecutor().execute(
                plan,
                context,
                agents,
                event_sink=persist_event,
                cancellation_check=lambda: self.store.cancellation_requested(run_id),
                artifact_sink=persist_artifact,
            )
            terminal_event = {
                RunStatus.COMPLETED: AgentEventType.RUN_COMPLETED,
                RunStatus.PARTIALLY_COMPLETED: AgentEventType.RUN_PARTIALLY_COMPLETED,
                RunStatus.CANCELLED: AgentEventType.RUN_CANCELLED,
                RunStatus.FAILED: AgentEventType.RUN_FAILED,
            }[outcome.status]
            await persist_event(
                AgentEvent(
                    event_type=terminal_event,
                    run_id=run_id,
                    agent_name=None,
                    status=outcome.status,
                    summary={
                        RunStatus.COMPLETED: "Agent orchestration completed.",
                        RunStatus.PARTIALLY_COMPLETED: "Agent orchestration partially completed.",
                        RunStatus.CANCELLED: "Agent orchestration cancelled at a safe boundary.",
                        RunStatus.FAILED: "Agent orchestration failed.",
                    }[outcome.status],
                    timestamp=self._now(),
                    payload={
                        "artifact_keys": list(context.artifacts),
                        "failed_nodes": list(outcome.errors),
                    },
                )
            )
            result = SupervisorRunResult(
                run_id=run_id,
                status=outcome.status,
                context=context,
                agent_results=list(outcome.results.values()),
                final_result=self.supervisor._build_final_result(context),
            )
            self.store.complete_run(result)
        except asyncio.CancelledError:
            cancelled_event = AgentEvent(
                event_type=AgentEventType.RUN_CANCELLED,
                run_id=run_id,
                agent_name=None,
                status=RunStatus.CANCELLED,
                summary="Agent run cancelled at a safe collaboration boundary.",
                timestamp=self._now(),
                payload={"reason_code": "user_requested"},
            )
            self.store.append_event(cancelled_event)
            self.store.mark_cancelled(run_id)
        except Exception as exc:
            failed_event = AgentEvent(
                event_type=AgentEventType.RUN_FAILED,
                run_id=run_id,
                agent_name=None,
                status=RunStatus.FAILED,
                summary="Agent run failed.",
                timestamp=self._now(),
                payload={"failure_code": "executor_error", "error_summary": str(exc)[:500]},
            )
            self.store.append_event(failed_event)
            with self._get_db_session() as db:
                failed_run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
                if failed_run:
                    failed_run.status = RunStatus.FAILED.value
                    failed_run.failure_code = "executor_error"
                    failed_run.error_message = str(exc)[:2000]
                    failed_run.completed_at = self._now()
                    db.commit()

    def cancel_agent_run(self, user_id: str, run_id: str) -> AgentRunDetail:
        detail = self.get_agent_run(user_id, run_id)
        if detail.status in {
            RunStatus.COMPLETED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
            RunStatus.PARTIALLY_COMPLETED.value,
        }:
            return detail
        with self._get_db_session() as db:
            run = (
                db.query(AgentRun)
                .filter(AgentRun.id == run_id, AgentRun.user_id == user_id)
                .first()
            )
            if run and run.cancellation_requested_at is None:
                run.cancellation_requested_at = self._now()
                db.commit()
        if isinstance(self.store, DatabaseOrchestrationStore):
            self.store.append_event(
                AgentEvent(
                    event_type=AgentEventType.RUN_CANCEL_REQUESTED,
                    run_id=run_id,
                    status=RunStatus.RUNNING,
                    summary="Cancellation requested; waiting for a safe boundary.",
                    timestamp=self._now(),
                    payload={"reason_code": "user_requested"},
                )
            )
        return self.get_agent_run(user_id, run_id)

    def retry_agent_run(
        self,
        user_id: str,
        run_id: str,
        *,
        mode: str = "resume_failed",
    ) -> AgentRunDetail:
        original = self.get_agent_run(user_id, run_id)
        if original.status not in {
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
            RunStatus.PARTIALLY_COMPLETED.value,
        }:
            raise ValueError("only failed, cancelled, or partial runs can be retried")
        with self._get_db_session() as db:
            old = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            completed_agents = [
                row.agent_name
                for row in db.query(AgentRunStep)
                .filter(
                    AgentRunStep.run_id == old.id,
                    AgentRunStep.status == NodeStatus.COMPLETED.value,
                )
                .all()
            ]
            request = OrchestrationRunRequest(
                project_id=old.project_id,
                student_id=old.user_id,
                goal=old.goal,
                trigger={"type": "retry", "id": old.id},
                artifacts={} if mode == "restart" else self._validated_artifacts(db, old.id),
                meta={
                    "retry_mode": mode,
                    "resume_skip_agents": completed_agents
                    if mode == "resume_failed"
                    else [],
                },
                budget=old.budget or {},
            )
        created = self.create_agent_run(user_id, original.project_id, request)
        with self._get_db_session() as db:
            retried = db.query(AgentRun).filter(AgentRun.id == created.run_id).first()
            retried.retry_of_run_id = run_id
            db.commit()
        return self.get_agent_run(user_id, created.run_id)

    def list_agent_run_steps(
        self, user_id: str, run_id: str
    ) -> list[AgentRunStepDetail]:
        self.get_agent_run(user_id, run_id)
        with self._get_db_session() as db:
            rows = (
                db.query(AgentRunStep)
                .filter(AgentRunStep.run_id == run_id)
                .order_by(AgentRunStep.position)
                .all()
            )
            return [
                AgentRunStepDetail(
                    step_id=row.id,
                    run_id=row.run_id,
                    node_id=row.node_id,
                    agent_name=row.agent_name,
                    status=row.status,
                    depends_on=row.depends_on or [],
                    attempt_count=row.attempt_count,
                    max_attempts=row.max_attempts,
                    optional=row.optional,
                    input_artifact_versions=row.input_artifact_versions or {},
                    output_artifact_versions=row.output_artifact_versions or {},
                    error_code=row.error_code,
                    error_summary=row.error_summary,
                    started_at=row.started_at,
                    completed_at=row.completed_at,
                    heartbeat_at=row.heartbeat_at,
                    duration_ms=row.duration_ms,
                )
                for row in rows
            ]

    def add_agent_run_feedback(
        self,
        user_id: str,
        run_id: str,
        feedback: AgentRunFeedbackRequest,
    ) -> dict:
        run_detail = self.get_agent_run(user_id, run_id)
        with self._get_db_session() as db:
            row = AgentRunFeedback(
                id=str(uuid4()),
                run_id=run_id,
                user_id=user_id,
                rating=feedback.rating,
                action=feedback.action,
                comment=feedback.comment,
            )
            db.add(row)
            db.add(
                LearningEvidenceEvent(
                    id=str(uuid4()),
                    project_id=run_detail.project_id,
                    user_id=user_id,
                    knowledge_point_id=None,
                    event_type="agent_run_feedback",
                    source_type="agent_run",
                    source_id=run_id,
                    idempotency_key=f"agent_run_feedback:{row.id}",
                    occurred_at=datetime.now(timezone.utc),
                    payload={
                        "rating": feedback.rating,
                        "action": feedback.action,
                    },
                )
            )
            db.commit()
            return {"id": row.id, "run_id": run_id, "accepted": True}

    def list_recoverable_runs(self, stale_after_seconds: int = 120) -> list[dict]:
        """Read-only startup audit; a worker may explicitly claim these runs."""

        cutoff = self._now() - timedelta(seconds=max(30, stale_after_seconds))
        with self._get_db_session() as db:
            rows = (
                db.query(AgentRun)
                .filter(
                    AgentRun.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
                    (AgentRun.heartbeat_at.is_(None)) | (AgentRun.heartbeat_at < cutoff),
                )
                .all()
            )
            return [
                {
                    "run_id": run.id,
                    "user_id": run.user_id,
                    "status": run.status,
                    "heartbeat_at": run.heartbeat_at,
                }
                for run in rows
            ]

    @staticmethod
    def _validated_artifacts(db, run_id: str) -> dict:
        rows = (
            db.query(AgentArtifactModel)
            .filter(
                AgentArtifactModel.run_id == run_id,
                AgentArtifactModel.validation_status == "valid",
            )
            .order_by(AgentArtifactModel.artifact_version)
            .all()
        )
        return {row.artifact_key: row.artifact for row in rows}

    def get_agent_run(self, user_id: str, run_id: str) -> AgentRunDetail:
        with self._get_db_session() as db:
            run = db.query(AgentRun).filter(
                AgentRun.id == run_id, AgentRun.user_id == user_id
            ).first()
            if not run:
                raise NotFoundError(f"Agent run {run_id} not found")
            return AgentRunDetail(
                run_id=run.id,
                project_id=run.project_id,
                goal=run.goal,
                status=run.status,
                final_result=run.final_result or {},
                current_agent_name=run.current_agent_name,
                heartbeat_at=run.heartbeat_at,
                duration_ms=run.duration_ms,
                model_name=run.model_name,
                input_tokens=run.input_tokens or 0,
                output_tokens=run.output_tokens or 0,
                estimated_cost_micros=run.estimated_cost_micros or 0,
                trace_id=run.trace_id,
                retry_of_run_id=run.retry_of_run_id,
                orchestration_version=run.orchestration_version,
                versions=run.versions or {},
                failure_code=run.failure_code,
                last_event_sequence=run.last_event_sequence or 0,
                started_at=run.started_at,
                completed_at=run.completed_at,
                created_at=run.created_at,
            )

    def get_agent_run_events(
        self, user_id: str, run_id: str, after_sequence: int = 0
    ) -> list[AgentEvent]:
        self.get_agent_run(user_id, run_id)
        with self._get_db_session() as db:
            rows = db.query(AgentEventModel).filter(
                AgentEventModel.run_id == run_id,
                AgentEventModel.sequence > max(0, after_sequence),
            ).order_by(AgentEventModel.sequence).all()
            return [AgentEvent(
                event_type=row.event_type, run_id=row.run_id,
                agent_name=row.agent_name, status=row.status,
                summary=row.summary, timestamp=row.created_at,
                payload=row.payload or {}, sequence=row.sequence,
            ) for row in rows]

    def get_skill_executions(self, user_id: str, run_id: str) -> list[dict]:
        self.get_agent_run(user_id, run_id)
        with self._get_db_session() as db:
            rows = db.query(SkillExecution).filter(
                SkillExecution.run_id == run_id
            ).order_by(SkillExecution.started_at).all()
            return [{
                "id": row.id, "run_id": row.run_id,
                "agent_name": row.agent_name, "skill_id": row.skill_id,
                "version": row.skill_version, "status": row.status,
                "input_summary": row.input_summary or {},
                "output_summary": row.output_summary or {},
                "confidence": row.confidence, "fallback_used": row.fallback_used,
                "fallback_reason": row.fallback_reason,
                "duration_ms": row.duration_ms,
            } for row in rows]

    def get_tool_calls(self, user_id: str, run_id: str) -> list[dict]:
        self.get_agent_run(user_id, run_id)
        with self._get_db_session() as db:
            rows = db.query(AgentToolCall).filter(
                AgentToolCall.run_id == run_id
            ).order_by(AgentToolCall.started_at).all()
            return [{
                "id": row.id, "run_id": row.run_id,
                "skill_execution_id": row.skill_execution_id,
                "agent_name": row.agent_name, "skill_id": row.skill_id,
                "tool_name": row.tool_name, "version": row.tool_version,
                "status": row.status, "risk_level": row.risk_level,
                "approval_status": row.approval_status,
                "result_summary": row.result_summary or {},
                "evidence_refs": row.evidence_refs or [],
                "error_code": row.error_code, "duration_ms": row.duration_ms,
            } for row in rows]

    def list_recommendations(self, user_id: str, project_id: str) -> list[dict]:
        self._ensure_project_access(user_id, project_id)
        return self.store.list_recommendations(project_id)

    async def generate_recommendations(
        self,
        user_id: str,
        project_id: str,
        diagnosis_id: str | None = None,
        trigger: AgentTrigger | None = None,
        meta: dict | None = None,
        event_sink: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ) -> RecommendationsResponse:
        if diagnosis_id:
            diagnosis = self.get_diagnosis(diagnosis_id)
            self._ensure_diagnosis_access(diagnosis, user_id, project_id)
        else:
            diagnosis = await self.generate_diagnosis(user_id, project_id, trigger)

        result = await self._run_supervisor(
            user_id=user_id,
            project_id=project_id,
            goal="recommendations",
            trigger=trigger,
            meta=meta,
            event_sink=event_sink,
            artifacts={"diagnosis": {"diagnosis": diagnosis.diagnosis}},
        )
        self.store.save_run_events(result)
        response = RecommendationsResponse(
            run_id=result.run_id,
            project_id=project_id,
            recommendations=result.final_result.get("recommendations", []),
            based_on_diagnosis_id=diagnosis.diagnosis_id,
            created_at=self._now(),
        )

        self.store.save_recommendations(response)
        return response

    async def generate_learning_path(
        self,
        user_id: str,
        project_id: str,
        diagnosis_id: str | None = None,
        trigger: AgentTrigger | None = None,
        event_sink: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ) -> LearningPathResponse:
        diagnosis = None
        if diagnosis_id:
            diagnosis = self.get_diagnosis(diagnosis_id)
            self._ensure_diagnosis_access(diagnosis, user_id, project_id)

        result = await self._run_supervisor(
            user_id=user_id,
            project_id=project_id,
            goal="learning_path",
            trigger=trigger,
            meta={"based_on_diagnosis_id": diagnosis.diagnosis_id}
            if diagnosis
            else None,
            event_sink=event_sink,
        )
        self.store.save_run_events(result)

        learning_path = result.final_result.get("learning_path")
        if result.status != RunStatus.COMPLETED or not learning_path:
            error = result.final_result.get("error", "Planner returned no learning path")
            raise RuntimeError(f"Learning path generation failed: {error}")

        if diagnosis is None:
            diagnosis = DiagnosisResponse(
                diagnosis_id=f"diag_{uuid4().hex}",
                run_id=result.run_id,
                project_id=project_id,
                student_id=user_id,
                status=result.status,
                diagnosis=result.final_result.get("diagnosis", {}),
                recommendations=result.final_result.get("recommendations", []),
                learning_path=learning_path,
                next_actions=[],
                created_at=self._now(),
            )
            self.store.save_diagnosis(diagnosis)

        recommendation_ids = [
            recommendation["id"] for recommendation in diagnosis.recommendations
            if recommendation.get("id")
        ]
        response = LearningPathResponse(
            path_id=f"path_{uuid4().hex}",
            run_id=result.run_id,
            project_id=project_id,
            learning_path=learning_path,
            based_on_diagnosis_id=diagnosis.diagnosis_id,
            based_on_recommendation_ids=recommendation_ids,
            created_at=self._now(),
        )
        self.store.save_learning_path(response)
        return response

    def get_latest_learning_path(
        self, user_id: str, project_id: str
    ) -> LearningPathResponse | None:
        self._ensure_project_access(user_id, project_id)
        return self.store.get_latest_learning_path(project_id)

    def list_learning_paths(
        self, user_id: str, project_id: str
    ) -> list[LearningPathResponse]:
        self._ensure_project_access(user_id, project_id)
        return self.store.list_learning_paths(project_id)

    async def _run_supervisor(
        self,
        user_id: str,
        project_id: str,
        goal: str,
        trigger: AgentTrigger | None,
        meta: dict | None = None,
        event_sink: Callable[[AgentEvent], Awaitable[None]] | None = None,
        artifacts: dict | None = None,
    ) -> SupervisorRunResult:
        context = self._load_context(user_id, project_id)
        return await self.supervisor.run(
            OrchestrationRunRequest(
                project_id=project_id,
                student_id=user_id,
                goal=goal,
                trigger=trigger or AgentTrigger(),
                context=context,
                artifacts=artifacts or {},
                meta=meta or {},
            ),
            event_sink=event_sink,
        )

    def _load_context(self, user_id: str, project_id: str) -> AgentContextData:
        with self._get_db_session() as db:
            project = (
                db.query(Project)
                .filter(Project.id == project_id, Project.owner_id == user_id)
                .first()
            )
            if not project:
                raise NotFoundError(f"Project {project_id} not found")

            practice_records = (
                db.query(PracticeRecord)
                .filter(
                    PracticeRecord.user_id == user_id,
                    PracticeRecord.project_id == project_id,
                )
                .order_by(PracticeRecord.created_at.desc())
                .limit(100)
                .all()
            )
            documents = (
                db.query(Document)
                .filter(Document.project_id == project_id)
                .order_by(Document.uploaded_at.desc())
                .limit(50)
                .all()
            )
            resource_packages = (
                db.query(ResourcePackage)
                .filter(
                    ResourcePackage.user_id == user_id,
                    ResourcePackage.project_id == project_id,
                )
                .order_by(ResourcePackage.created_at.desc())
                .limit(20)
                .all()
            )
            generated_resources = (
                db.query(GeneratedResource)
                .filter(
                    GeneratedResource.user_id == user_id,
                    GeneratedResource.project_id == project_id,
                    GeneratedResource.status == "completed",
                )
                .order_by(GeneratedResource.updated_at.desc())
                .limit(20)
                .all()
            )
            recommendation_feedback = (
                db.query(Recommendation)
                .filter(
                    Recommendation.user_id == user_id,
                    Recommendation.project_id == project_id,
                    Recommendation.feedback.isnot(None),
                )
                .order_by(Recommendation.created_at.desc())
                .limit(50)
                .all()
            )
            learner_profile = (
                db.query(LearnerProfile)
                .filter(
                    LearnerProfile.user_id == user_id,
                    LearnerProfile.project_id == project_id,
                )
                .first()
            )
            knowledge_points = []
            knowledge_states = []
            collective_insights = []
            if project.course_id:
                points = (
                    db.query(KnowledgePoint)
                    .filter(KnowledgePoint.course_id == project.course_id)
                    .order_by(KnowledgePoint.position, KnowledgePoint.created_at)
                    .all()
                )
                relations = (
                    db.query(KnowledgePointRelation)
                    .filter(KnowledgePointRelation.course_id == project.course_id)
                    .all()
                )
                prerequisites: dict[str, list[str]] = {}
                for relation in relations:
                    if relation.relation_type == "prerequisite":
                        prerequisites.setdefault(
                            relation.target_knowledge_point_id, []
                        ).append(relation.source_knowledge_point_id)
                state_by_point = {
                    state.knowledge_point_id: state
                    for state in db.query(StudentKnowledgeState)
                    .filter(
                        StudentKnowledgeState.user_id == user_id,
                        StudentKnowledgeState.knowledge_point_id.in_(
                            [point.id for point in points]
                        ),
                    )
                    .all()
                }
                for point in points:
                    state = state_by_point.get(point.id)
                    knowledge_points.append(
                        {
                            "id": point.id,
                            "name": point.name,
                            "description": point.description,
                            "difficulty_level": point.difficulty_level,
                            "tags": point.tags or [],
                            "prerequisite_ids": prerequisites.get(point.id, []),
                        }
                    )
                    knowledge_states.append(
                        {
                            "id": state.id if state else f"state:{point.id}",
                            "knowledge_point_id": point.id,
                            "topic": point.name,
                            "mastery_score": float(state.mastery_score) if state else 0.0,
                            "confidence": float(state.confidence) if state else 0.0,
                            "trend": state.trend if state else "stable",
                            "status": state.status if state else "not_started",
                            "attempt_count": state.attempt_count if state else 0,
                            "correct_count": state.correct_count if state else 0,
                            "last_practiced_at": state.last_practiced_at.isoformat()
                            if state and state.last_practiced_at
                            else None,
                        }
                    )
                current_insights = (
                    db.query(CollectiveInsight)
                    .filter(
                        CollectiveInsight.course_id == project.course_id,
                        CollectiveInsight.sample_size >= 10,
                        CollectiveInsight.expires_at > datetime.now(timezone.utc),
                    )
                    .order_by(CollectiveInsight.created_at.desc())
                    .all()
                )
                seen_insights: set[tuple[str, str]] = set()
                for insight in current_insights:
                    key = (insight.knowledge_point_id, insight.pattern_type)
                    if key in seen_insights:
                        continue
                    seen_insights.add(key)
                    collective_insights.append(
                        {
                            "id": insight.id,
                            "knowledge_point_id": insight.knowledge_point_id,
                            "pattern_type": insight.pattern_type,
                            "sample_size": insight.sample_size,
                            "aggregate": insight.aggregate or {},
                            "version": insight.version,
                        }
                    )

            return AgentContextData(
                learner_profile=(
                    {
                        "id": learner_profile.id,
                        "status": learner_profile.status,
                        "completeness_score": learner_profile.completeness_score,
                        "last_refreshed_at": learner_profile.last_refreshed_at.isoformat()
                        if learner_profile.last_refreshed_at
                        else None,
                        **(learner_profile.profile_data or {}),
                    }
                    if learner_profile
                    else None
                ),
                knowledge_states=knowledge_states,
                knowledge_points=knowledge_points,
                course={
                    "id": project.course_id,
                    "name": project.name,
                    "description": project.description,
                    "language_code": project.language_code,
                },
                practice_records=[
                    {
                        "id": record.id,
                        "knowledge_point_id": record.knowledge_point_id,
                        "item_type": record.item_type,
                        "item_id": record.item_id,
                        "topic": record.topic,
                        "user_answer": record.user_answer,
                        "correct_answer": record.correct_answer,
                        "was_correct": record.was_correct,
                        "created_at": record.created_at.isoformat()
                        if record.created_at
                        else None,
                    }
                    for record in practice_records
                ],
                documents=[
                    {
                        "id": document.id,
                        "file_name": document.file_name,
                        "status": document.status,
                        "summary": document.summary,
                    }
                    for document in documents
                ],
                resource_packages=[
                    {
                        "id": package.id,
                        "title": package.title,
                        "status": package.status,
                        "target_topic": package.target_topic,
                        "preferred_resource_types": package.preferred_resource_types,
                    }
                    for package in resource_packages
                ],
                generated_resources=[
                    {
                        "id": resource.id,
                        "title": resource.title,
                        "resource_type": resource.resource_type,
                        "summary": resource.summary,
                        "knowledge_point_ids": resource.knowledge_point_ids,
                        "estimated_minutes": resource.estimated_minutes,
                    }
                    for resource in generated_resources
                ],
                collective_insights=collective_insights,
                recent_feedback_summary=self._build_recent_feedback_summary(
                    practice_records=practice_records,
                    recommendation_feedback=recommendation_feedback,
                ),
            )

    def _build_recent_feedback_summary(
        self,
        practice_records: list[PracticeRecord],
        recommendation_feedback: list[Recommendation],
    ) -> dict:
        completed_resources = 0
        abandoned_resources = 0
        clicked_resources = 0
        incorrect_by_topic: dict[str, int] = {}

        for recommendation in recommendation_feedback:
            feedback = recommendation.feedback or {}
            signal = str(
                feedback.get("event")
                or feedback.get("action")
                or feedback.get("status")
                or feedback.get("type")
                or ""
            ).lower()
            if signal in {"completed", "complete", "finished"}:
                completed_resources += 1
            elif signal in {"abandoned", "skipped", "dismissed"}:
                abandoned_resources += 1
            elif signal in {"clicked", "opened", "viewed"}:
                clicked_resources += 1

        for record in practice_records:
            if record.was_correct:
                continue
            topic = record.topic or "general"
            incorrect_by_topic[topic] = incorrect_by_topic.get(topic, 0) + 1

        struggled_knowledge_points = [
            self._topic_to_point_id(topic)
            for topic, count in incorrect_by_topic.items()
            if count >= 2
        ]
        rerun_triggers = []
        if struggled_knowledge_points:
            rerun_triggers.append("diagnosis")
        if abandoned_resources >= 2:
            rerun_triggers.append("recommendations")

        attempted = len(practice_records)
        completed = sum(1 for record in practice_records if record.was_correct)
        last_path_completion_rate = round(completed / attempted, 2) if attempted else None
        if last_path_completion_rate is not None and last_path_completion_rate < 0.4:
            rerun_triggers.append("planner")

        return {
            "completed_resources": completed_resources,
            "abandoned_resources": abandoned_resources,
            "clicked_resources": clicked_resources,
            "struggled_knowledge_points": struggled_knowledge_points,
            "last_path_completion_rate": last_path_completion_rate,
            "rerun_triggers": sorted(set(rerun_triggers)),
        }

    def _topic_to_point_id(self, topic: str) -> str:
        normalized = "".join(
            char.lower() if char.isalnum() else "_" for char in topic.strip()
        ).strip("_")
        return f"kp_{normalized or 'general'}"

    def _ensure_project_access(self, user_id: str, project_id: str) -> None:
        with self._get_db_session() as db:
            project = (
                db.query(Project)
                .filter(Project.id == project_id, Project.owner_id == user_id)
                .first()
            )
            if not project:
                raise NotFoundError(f"Project {project_id} not found")

    def _ensure_diagnosis_access(
        self, diagnosis: DiagnosisResponse, user_id: str, project_id: str
    ) -> None:
        if diagnosis.project_id != project_id or diagnosis.student_id != user_id:
            raise NotFoundError(f"Diagnosis {diagnosis.diagnosis_id} not found")

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @contextmanager
    def _get_db_session(self):
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
