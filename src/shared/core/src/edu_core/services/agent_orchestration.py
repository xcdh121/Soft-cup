from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import uuid4

from edu_ai.agents.orchestration import SupervisorAgent
from edu_ai.agents.orchestration.resource_agent import ResourceAgent
from edu_core.exceptions import NotFoundError
from edu_core.model_providers import LlmProviderConfig
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEvent,
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
    Diagnosis,
    Document,
    GeneratedResource,
    LearningPath,
    PracticeRecord,
    Project,
    Recommendation,
    ResourcePackage,
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
            return self._learning_path_to_response(path) if path else None

    def list_learning_paths(self, project_id: str) -> list[LearningPathResponse]:
        with self._get_db_session() as db:
            paths = (
                db.query(LearningPath)
                .filter(LearningPath.project_id == project_id)
                .order_by(LearningPath.created_at.desc())
                .all()
            )
            return [self._learning_path_to_response(path) for path in paths]

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

    def _learning_path_to_response(self, path: LearningPath) -> LearningPathResponse:
        return LearningPathResponse(
            path_id=path.id,
            run_id=path.run_id,
            project_id=path.project_id,
            learning_path=path.content,
            based_on_diagnosis_id=path.diagnosis_id,
            based_on_recommendation_ids=path.based_on_recommendation_ids,
            created_at=path.created_at,
        )

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
    ) -> LearningPathResponse:
        if diagnosis_id:
            diagnosis = self.get_diagnosis(diagnosis_id)
            self._ensure_diagnosis_access(diagnosis, user_id, project_id)
        else:
            diagnosis = await self.generate_diagnosis(user_id, project_id, trigger)

        recommendation_ids = [
            recommendation["id"] for recommendation in diagnosis.recommendations
        ]
        response = LearningPathResponse(
            path_id=f"path_{uuid4().hex}",
            run_id=diagnosis.run_id,
            project_id=project_id,
            learning_path=diagnosis.learning_path or {},
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
    ) -> SupervisorRunResult:
        context = self._load_context(user_id, project_id)
        return await self.supervisor.run(
            OrchestrationRunRequest(
                project_id=project_id,
                student_id=user_id,
                goal=goal,
                trigger=trigger or AgentTrigger(),
                context=context,
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

            return AgentContextData(
                learner_profile=None,
                course={
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "language_code": project.language_code,
                },
                practice_records=[
                    {
                        "id": record.id,
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
