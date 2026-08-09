from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from edu_ai.agents.orchestration import SupervisorAgent
from edu_ai.agents.orchestration.resource_agent import ResourceAgent
from edu_core.exceptions import NotFoundError
from edu_core.model_providers import LlmProviderConfig
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEvent,
    AgentRunDetail,
    AgentTrigger,
    DiagnosisResponse,
    LearningPathResponse,
    OrchestrationRunRequest,
    RecommendationsResponse,
    RunStatus,
    SupervisorRunResult,
)
from edu_db.models import (
    AgentArtifact as AgentArtifactModel,
    AgentEvent as AgentEventModel,
    AgentRun,
    AgentToolCall,
    Diagnosis,
    DiagnosisCause,
    Document,
    Explanation,
    ExplanationEvidence,
    GeneratedResource,
    KnowledgePoint,
    KnowledgePointRelation,
    KnowledgeStateEvent,
    LearnerProfile,
    LearningPath,
    LearningPathStep,
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

            for event in result.events:
                db.add(
                    AgentEventModel(
                        id=str(uuid4()),
                        run_id=event.run_id,
                        event_type=event.event_type.value,
                        agent_name=event.agent_name.value if event.agent_name else None,
                        status=event.status.value,
                        summary=event.summary,
                        payload=self._to_json(event.payload),
                        created_at=event.timestamp,
                    )
                )

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
                payload = diagnosis.diagnosis or {}
                related_points = payload.get("related_knowledge_points", [])
                primary_id = (
                    related_points[0].get("id")
                    if related_points
                    else payload.get("primary_knowledge_point_id")
                )
                state = None
                if primary_id:
                    state = (
                        db.query(StudentKnowledgeState)
                        .filter(
                            StudentKnowledgeState.user_id == diagnosis.student_id,
                            StudentKnowledgeState.knowledge_point_id == primary_id,
                        )
                        .first()
                    )
                root_causes = payload.get("root_causes", [])
                confidence = max(
                    [float(item.get("confidence", 0)) for item in root_causes],
                    default=0.2,
                )
                row = Diagnosis(
                        id=diagnosis.diagnosis_id,
                        run_id=diagnosis.run_id,
                        project_id=diagnosis.project_id,
                        user_id=diagnosis.student_id,
                        status=diagnosis.status.value,
                        diagnosis=self._to_json(diagnosis.diagnosis),
                        next_actions=self._to_json(diagnosis.next_actions),
                        trigger_type="agent_run",
                        trigger_id=diagnosis.run_id,
                        primary_knowledge_point_id=primary_id,
                        state_version=state.state_version if state else None,
                        confidence=confidence,
                        diagnosis_version="diagnosis-rule-v1",
                        created_at=diagnosis.created_at,
                    )
                db.add(row)
                db.flush()
                explanation = Explanation(
                    id=str(uuid4()),
                    project_id=diagnosis.project_id,
                    user_id=diagnosis.student_id,
                    object_type="diagnosis",
                    object_id=row.id,
                    summary=payload.get("summary", "已生成学习根因诊断。"),
                    reason_codes=[
                        item.get("type", "insufficient_evidence")
                        for item in root_causes
                    ],
                    model_version=row.diagnosis_version,
                    confidence=confidence,
                )
                db.add(explanation)
                db.flush()
                row.explanation_id = explanation.id
                for rank, cause in enumerate(root_causes[:3], start=1):
                    cause_point_id = cause.get("knowledge_point_id") or primary_id
                    db.add(
                        DiagnosisCause(
                            id=str(uuid4()),
                            diagnosis_id=row.id,
                            cause_type=cause.get("type", "weak_mastery"),
                            knowledge_point_id=cause_point_id,
                            relation_id=cause.get("relation_id"),
                            confidence=float(cause.get("confidence", 0.2)),
                            rank=rank,
                            reason_text=cause.get("reason_text")
                            or cause.get("label")
                            or "可能与当前学习证据有关。",
                        )
                    )
                for order, evidence in enumerate(payload.get("evidences", [])[:10]):
                    db.add(
                        ExplanationEvidence(
                            id=str(uuid4()),
                            explanation_id=explanation.id,
                            source_type=evidence.get("source_type", "diagnosis"),
                            source_id=str(evidence.get("source_id", row.id)),
                            knowledge_point_id=evidence.get("knowledge_point_id")
                            or primary_id,
                            contribution_direction="supporting",
                            contribution_score=float(
                                evidence.get("contribution_score", confidence)
                            ),
                            snapshot=self._to_json(evidence),
                            display_order=order,
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
                primary_id = diagnosis.primary_knowledge_point_id if diagnosis else None
                source_event = None
                if primary_id:
                    source_event = (
                        db.query(KnowledgeStateEvent)
                        .filter(
                            KnowledgeStateEvent.user_id == user_id,
                            KnowledgeStateEvent.knowledge_point_id == primary_id,
                        )
                        .order_by(KnowledgeStateEvent.occurred_at.desc())
                        .first()
                    )
                row = Recommendation(
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
                        source_state_event_id=source_event.id if source_event else None,
                        expected_outcome=self._to_json(
                            recommendation.get(
                                "expected_outcome",
                                {
                                    "knowledge_point_id": primary_id,
                                    "target_mastery": 0.8,
                                },
                            )
                        ),
                        verification_plan=self._to_json(
                            recommendation.get(
                                "verification_plan",
                                {
                                    "strategy": "existing_item_bank",
                                    "knowledge_point_id": primary_id,
                                    "within_hours": 72,
                                },
                            )
                        ),
                        status=recommendation.get("status", "active"),
                        created_at=response.created_at,
                    )
                db.add(row)
                db.flush()
                explanation = Explanation(
                    id=str(uuid4()),
                    project_id=response.project_id,
                    user_id=user_id,
                    object_type="recommendation",
                    object_id=row.id,
                    summary=" ".join(row.reason_text or []) or f"建议：{row.title}",
                    reason_codes=row.reason_codes or [],
                    model_version="recommendation-rule-v1",
                    confidence=float(row.score or 0.5),
                )
                db.add(explanation)
                db.flush()
                row.explanation_id = explanation.id
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

            now = response.created_at
            row = LearningPath(
                    id=response.path_id,
                    run_id=response.run_id,
                    diagnosis_id=response.based_on_diagnosis_id,
                    project_id=response.project_id,
                    user_id=user_id,
                    content=self._to_json(response.learning_path),
                    based_on_recommendation_ids=self._to_json(
                        response.based_on_recommendation_ids
                    ),
                    version=1,
                    status="active",
                    activated_at=now,
                    created_at=response.created_at,
                    updated_at=response.created_at,
                )
            db.add(row)
            db.flush()
            for index, step in enumerate(
                response.learning_path.get("path_steps", []), start=1
            ):
                acceptance = step.get("acceptance_condition") or {
                    "target_mastery": 0.8
                }
                if isinstance(acceptance, str):
                    acceptance = {"description": acceptance}
                db.add(
                    LearningPathStep(
                        id=str(uuid4()),
                        learning_path_id=row.id,
                        step_no=index,
                        step_type=step.get("type", "resource"),
                        target_id=step.get("target_id"),
                        knowledge_point_id=step.get("knowledge_point_id"),
                        recommendation_id=step.get("recommendation_id"),
                        objective=step.get("objective") or step.get("title"),
                        acceptance_condition=self._to_json(acceptance),
                        target_mastery=float(acceptance.get("target_mastery", 0.8)),
                        status="pending",
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
            "explanation_id": recommendation.explanation_id,
            "source_state_event_id": recommendation.source_state_event_id,
            "expected_outcome": recommendation.expected_outcome or {},
            "verification_plan": recommendation.verification_plan or {},
            "status": recommendation.status,
            "valid_until": recommendation.valid_until,
        }

    def _learning_path_to_response(
        self, path: LearningPath, db=None
    ) -> LearningPathResponse:
        content = self._resolve_knowledge_point_labels(path.content, db)
        if db is not None:
            persisted_steps = (
                db.query(LearningPathStep)
                .filter(LearningPathStep.learning_path_id == path.id)
                .order_by(LearningPathStep.step_no)
                .all()
            )
            if persisted_steps:
                content["path_steps"] = [
                    {
                        "id": step.id,
                        "step_no": step.step_no,
                        "type": step.step_type,
                        "target_id": step.target_id,
                        "knowledge_point_id": step.knowledge_point_id,
                        "recommendation_id": step.recommendation_id,
                        "title": step.objective,
                        "objective": step.objective,
                        "acceptance_condition": step.acceptance_condition or {},
                        "baseline_mastery": step.baseline_mastery,
                        "target_mastery": step.target_mastery,
                        "status": step.status,
                    }
                    for step in persisted_steps
                ]
        content = {
            **content,
            "version": path.version,
            "previous_path_id": path.previous_path_id,
            "status": path.status,
            "adjust_trigger_type": path.adjust_trigger_type,
            "adjust_trigger_id": path.adjust_trigger_id,
            "adjust_trigger_ids": path.adjust_trigger_ids or [],
            "explanation_id": path.explanation_id,
        }
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
                started_at=run.started_at,
                completed_at=run.completed_at,
                created_at=run.created_at,
            )

    def get_agent_run_events(self, user_id: str, run_id: str) -> list[AgentEvent]:
        self.get_agent_run(user_id, run_id)
        with self._get_db_session() as db:
            rows = db.query(AgentEventModel).filter(
                AgentEventModel.run_id == run_id
            ).order_by(AgentEventModel.created_at).all()
            return [AgentEvent(
                event_type=row.event_type, run_id=row.run_id,
                agent_name=row.agent_name, status=row.status,
                summary=row.summary, timestamp=row.created_at,
                payload=row.payload or {},
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

        generated_recommendations = result.final_result.get("recommendations", [])

        if diagnosis is None:
            diagnosis = DiagnosisResponse(
                diagnosis_id=f"diag_{uuid4().hex}",
                run_id=result.run_id,
                project_id=project_id,
                student_id=user_id,
                status=result.status,
                diagnosis=result.final_result.get("diagnosis", {}),
                recommendations=generated_recommendations,
                learning_path=learning_path,
                next_actions=[],
                created_at=self._now(),
            )
            self.store.save_diagnosis(diagnosis)

        recommendations = generated_recommendations or diagnosis.recommendations
        if recommendations:
            self.store.save_recommendations(
                RecommendationsResponse(
                    run_id=result.run_id,
                    project_id=project_id,
                    recommendations=recommendations,
                    based_on_diagnosis_id=diagnosis.diagnosis_id,
                    created_at=self._now(),
                )
            )

        learning_path = self._link_learning_path_steps(
            learning_path,
            recommendations,
            diagnosis.diagnosis,
        )
        recommendation_ids = [
            recommendation["id"] for recommendation in recommendations
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

    @staticmethod
    def _link_learning_path_steps(
        learning_path: dict,
        recommendations: list[dict],
        diagnosis: dict,
    ) -> dict:
        """Attach persisted recommendation and knowledge-point IDs to plan steps."""
        linked_path = dict(learning_path)
        related_points = diagnosis.get("related_knowledge_points", [])
        primary_knowledge_point_id = diagnosis.get("primary_knowledge_point_id")
        if not primary_knowledge_point_id and related_points:
            primary_knowledge_point_id = related_points[0].get("id")

        linked_steps = []
        for index, raw_step in enumerate(linked_path.get("path_steps", [])):
            step = dict(raw_step)
            recommendation = (
                recommendations[index] if index < len(recommendations) else None
            )
            if recommendation:
                if not step.get("recommendation_id"):
                    step["recommendation_id"] = recommendation.get("id")
                expected_outcome = recommendation.get("expected_outcome") or {}
                verification_plan = recommendation.get("verification_plan") or {}
                knowledge_point_id = (
                    recommendation.get("knowledge_point_id")
                    or expected_outcome.get("knowledge_point_id")
                    or verification_plan.get("knowledge_point_id")
                    or primary_knowledge_point_id
                )
                if not step.get("knowledge_point_id") and knowledge_point_id:
                    step["knowledge_point_id"] = knowledge_point_id
            linked_steps.append(step)

        linked_path["path_steps"] = linked_steps
        return linked_path

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
                prerequisite_relations: dict[str, list[dict]] = {}
                for relation in relations:
                    if relation.relation_type == "prerequisite":
                        prerequisites.setdefault(
                            relation.target_knowledge_point_id, []
                        ).append(relation.source_knowledge_point_id)
                        prerequisite_relations.setdefault(
                            relation.target_knowledge_point_id, []
                        ).append(
                            {
                                "id": relation.id,
                                "source_knowledge_point_id": (
                                    relation.source_knowledge_point_id
                                ),
                                "strength": float(relation.strength),
                            }
                        )
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
                            "prerequisite_relations": (
                                prerequisite_relations.get(point.id, [])
                            ),
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
