import json
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from edu_db.models import (
    CourseChapter,
    CourseResource,
    Document,
    GeneratedResource,
    KnowledgePoint,
    Project,
    ResourcePackage,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.model_providers import LlmProviderConfig, create_chat_model
from edu_core.schemas.agent_orchestration import AgentTrigger
from edu_core.schemas.resource_packages import (
    GeneratedResourceDto,
    ResourcePackageDto,
    ResourcePackageStreamEventDto,
)
from edu_core.storage import LocalStorageService
from edu_core.services.baidu_search import BaiduSearchClient
from edu_core.services.xfyun_ppt import XfyunPptClient, XfyunPptError

if TYPE_CHECKING:
    from edu_core.schemas.agent_orchestration import AgentEvent, DiagnosisResponse
    from edu_core.services.agent_orchestration import AgentOrchestrationService
    from edu_core.services.flashcard_groups import FlashcardGroupService
    from edu_core.services.mind_maps import MindMapService
    from edu_core.services.notes import NoteService
    from edu_core.services.quizzes import QuizService


class ResourcePackageService:
    """Service for generating and managing resource packages."""

    def __init__(
        self,
        *,
        storage_root: str = "./.localdata",
        agent_orchestration_service: "AgentOrchestrationService | None" = None,
        note_service: "NoteService | None" = None,
        quiz_service: "QuizService | None" = None,
        flashcard_group_service: "FlashcardGroupService | None" = None,
        mind_map_service: "MindMapService | None" = None,
        xfyun_ppt_client: XfyunPptClient | None = None,
        baidu_search_client: BaiduSearchClient | None = None,
        llm_config: LlmProviderConfig | None = None,
    ) -> None:
        self.storage = LocalStorageService(storage_root)
        self.agent_orchestration_service = agent_orchestration_service
        self.note_service = note_service
        self.quiz_service = quiz_service
        self.flashcard_group_service = flashcard_group_service
        self.mind_map_service = mind_map_service
        self.xfyun_ppt_client = xfyun_ppt_client
        self.baidu_search_client = baidu_search_client
        self.llm_config = llm_config

    def list_resource_packages(
        self,
        user_id: str,
        project_id: str,
        status: str | None = None,
        generation_mode: str | None = None,
        target_topic: str | None = None,
    ) -> list[ResourcePackageDto]:
        with self._get_db_session() as db:
            query = db.query(ResourcePackage).filter(
                ResourcePackage.user_id == user_id,
                ResourcePackage.project_id == project_id,
            )
            if status:
                query = query.filter(ResourcePackage.status == status)
            if generation_mode:
                query = query.filter(ResourcePackage.generation_mode == generation_mode)
            if target_topic:
                query = query.filter(ResourcePackage.target_topic.ilike(f"%{target_topic}%"))

            packages = query.order_by(ResourcePackage.created_at.desc()).all()
            return [self._model_to_dto(package) for package in packages]

    def get_resource_package(
        self, user_id: str, project_id: str, package_id: str
    ) -> ResourcePackageDto:
        with self._get_db_session() as db:
            package = self._get_package_or_raise(db, user_id, project_id, package_id)
            return self._model_to_dto(package)

    def list_generated_resources(
        self, user_id: str, project_id: str, package_id: str
    ) -> list[GeneratedResourceDto]:
        with self._get_db_session() as db:
            package = self._get_package_or_raise(db, user_id, project_id, package_id)
            return [self._resource_to_dto(resource) for resource in package.resources]

    def get_generated_resource(
        self, user_id: str, project_id: str, resource_id: str
    ) -> GeneratedResourceDto:
        with self._get_db_session() as db:
            resource = (
                db.query(GeneratedResource)
                .filter(
                    GeneratedResource.id == resource_id,
                    GeneratedResource.project_id == project_id,
                    GeneratedResource.user_id == user_id,
                )
                .first()
            )
            if not resource:
                raise NotFoundError(f"Generated resource {resource_id} not found")
            return self._resource_to_dto(resource)

    async def generate_resource_package(
        self,
        user_id: str,
        project_id: str,
        payload: dict,
        event_sink: Callable[[ResourcePackageStreamEventDto], Awaitable[None]] | None = None,
    ) -> ResourcePackageDto:
        with self._get_db_session() as db:
            project = (
                db.query(Project)
                .filter(Project.id == project_id, Project.owner_id == user_id)
                .first()
            )
            if not project:
                raise NotFoundError(f"Project {project_id} not found")

            source_document_ids = payload.get("source_document_ids") or []
            documents = []
            if source_document_ids:
                documents = (
                    db.query(Document)
                    .filter(
                        Document.project_id == project_id,
                        Document.id.in_(source_document_ids),
                    )
                    .all()
                )

            chapter_ids = self._merge_distinct(payload.get("chapter_ids") or [])
            chapters, chapter_points, chapter_resources = self._load_chapter_scope(
                db, project, chapter_ids
            )
            chapter_context = self._build_chapter_context(
                chapters, chapter_points, chapter_resources
            )
            scoped_instructions = self._build_scoped_instructions(
                payload.get("custom_instructions"), chapters
            )

            resource_types = payload.get("resource_types") or [
                "lecture_note",
                "mind_map",
                "practice_set",
                "ppt_outline",
                "programming_questions",
                "code_lab",
            ]
            now = datetime.now(timezone.utc)
            package_id = str(uuid4())
            target_topic = payload["target_topic"]
            target_goal = payload.get("target_goal")
            difficulty_level = payload.get("difficulty_level", "intermediate")
            generation_params = {
                "custom_instructions": payload.get("custom_instructions"),
                "chapter_ids": chapter_ids,
                "chapter_titles": [chapter.title for chapter in chapters],
                **(payload.get("generation_params") or {}),
            }

            diagnosis = await self._get_or_create_diagnosis(
                user_id=user_id,
                project_id=project_id,
                package_id=package_id,
                target_topic=target_topic,
                difficulty_level=difficulty_level,
                custom_instructions=scoped_instructions,
                resource_types=resource_types,
                generation_params=generation_params,
                diagnosis_id=payload.get("diagnosis_id"),
                event_sink=event_sink,
            )
            diagnosis_trace = self._get_diagnosis_trace(diagnosis)

            knowledge_point_ids = self._merge_distinct(
                payload.get("knowledge_point_ids") or [],
                [point.id for point in chapter_points],
                self._extract_knowledge_point_ids(diagnosis),
            )
            weak_points = self._merge_distinct(
                payload.get("weak_knowledge_point_ids") or [],
                self._extract_weak_point_ids(diagnosis),
            )
            generation_params = {
                **generation_params,
                "diagnosis_id": diagnosis.diagnosis_id,
                "learning_path": diagnosis.learning_path or {},
                "recommendations": diagnosis.recommendations,
            }

            package = ResourcePackage(
                id=package_id,
                project_id=project_id,
                user_id=user_id,
                profile_id=payload.get("profile_id"),
                learning_path_id=payload.get("learning_path_id"),
                title=payload.get("title") or f"{target_topic} resource package",
                description=payload.get("description")
                or f"Personalized package for {target_topic}",
                generation_mode=payload.get("generation_mode", "manual"),
                status="generating",
                target_topic=target_topic,
                target_goal=target_goal,
                difficulty_level=difficulty_level,
                estimated_minutes=payload.get("estimated_minutes"),
                source_document_ids=source_document_ids,
                knowledge_point_ids=knowledge_point_ids,
                weak_knowledge_point_ids=weak_points,
                preferred_resource_types=resource_types,
                generation_params=generation_params,
                agent_trace=[],
                resource_count=len(resource_types),
                completed_resource_count=0,
                failed_resource_count=0,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            db.add(package)
            db.flush()

            agent_trace = self._build_agent_trace_from_events(
                package_id=package_id,
                diagnosis=diagnosis,
                events=diagnosis_trace,
            )
            self._append_agent_event(
                agent_trace,
                package_id,
                "package_status_changed",
                {"status": "generating"},
            )
            package.agent_trace = agent_trace
            db.commit()
            await self._publish_stream_event(
                event_sink, package_id, "package_started",
                {"status": "generating", "resource_count": len(resource_types)},
            )

            source_context = self._combine_source_context(
                self._build_document_context(documents), chapter_context
            )
            recommendation_pool = list(diagnosis.recommendations)

            completed = 0
            failed = 0
            for order, resource_type in enumerate(resource_types):
                self._append_agent_event(
                    agent_trace,
                    package_id,
                    "resource_started",
                    {"resource_type": resource_type, "order": order},
                )
                await self._publish_stream_event(
                    event_sink, package_id, "resource_started",
                    {"resource_type": resource_type, "order": order},
                )

                try:
                    generated, resource_status = await self._generate_package_resource(
                        user_id=user_id,
                        project_id=project_id,
                        resource_type=resource_type,
                        topic=target_topic,
                        goal=target_goal,
                        difficulty_level=difficulty_level,
                        document_context=source_context,
                        knowledge_point_ids=knowledge_point_ids,
                        weak_points=weak_points,
                        custom_instructions=scoped_instructions,
                        documents=documents,
                        generation_params=generation_params,
                        recommendations=recommendation_pool,
                    )
                    error_message = None
                    completed += 1
                except Exception as exc:
                    generated = self._build_failed_resource_content(
                        resource_type=resource_type,
                        topic=target_topic,
                        error_message=str(exc),
                    )
                    resource_status = "failed"
                    error_message = str(exc)
                    failed += 1

                resource = GeneratedResource(
                    id=str(uuid4()),
                    resource_package_id=package_id,
                    project_id=project_id,
                    user_id=user_id,
                    resource_type=resource_type,
                    title=generated["title"],
                    summary=generated.get("summary"),
                    status=resource_status,
                    format=generated["format"],
                    content_text=generated.get("content_text"),
                    content_json=generated.get("content_json"),
                    file_url=generated.get("file_url"),
                    preview_url=generated.get("preview_url"),
                    cover_image_url=generated.get("cover_image_url"),
                    error_message=error_message,
                    source_document_ids=source_document_ids,
                    knowledge_point_ids=knowledge_point_ids,
                    difficulty_level=difficulty_level,
                    estimated_minutes=generated.get("estimated_minutes"),
                    version=1,
                    generation_order=order,
                    generator_agent=generated.get("generator_agent"),
                    generation_reason=generated.get("generation_reason"),
                    created_at=now,
                    updated_at=now,
                    completed_at=now if resource_status == "completed" else None,
                )
                db.add(resource)

                self._append_agent_event(
                    agent_trace,
                    package_id,
                    (
                        "resource_completed"
                        if resource_status == "completed"
                        else "resource_failed"
                        if resource_status == "failed"
                        else "resource_generating"
                    ),
                    {
                        "resource_id": resource.id,
                        "resource_type": resource_type,
                        "title": generated["title"],
                        "error_message": error_message,
                    },
                )
                package.completed_resource_count = completed
                package.failed_resource_count = failed
                package.agent_trace = agent_trace
                package.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(resource)
                resource_event = (
                    "resource_completed"
                    if resource_status == "completed"
                    else "resource_failed"
                    if resource_status == "failed"
                    else "resource_generating"
                )
                await self._publish_stream_event(
                    event_sink,
                    package_id,
                    resource_event,
                    {"resource": self._resource_to_dto(resource).model_dump(mode="json")},
                )

            package.status = "completed" if failed == 0 else "failed"
            package.completed_resource_count = completed
            package.failed_resource_count = failed
            package.completed_at = now
            self._append_agent_event(
                agent_trace,
                package_id,
                "package_status_changed",
                {"status": package.status},
            )
            package.agent_trace = agent_trace

            db.commit()
            db.refresh(package)
            await self._publish_stream_event(
                event_sink, package_id, "package_completed",
                {"status": package.status,
                 "completed_resource_count": completed,
                 "failed_resource_count": failed},
            )
            return self._model_to_dto(package)

    def update_generated_resource(
        self, user_id: str, project_id: str, resource_id: str, payload: dict
    ) -> GeneratedResourceDto:
        with self._get_db_session() as db:
            resource = (
                db.query(GeneratedResource)
                .filter(
                    GeneratedResource.id == resource_id,
                    GeneratedResource.project_id == project_id,
                    GeneratedResource.user_id == user_id,
                )
                .first()
            )
            if not resource:
                raise NotFoundError(f"Generated resource {resource_id} not found")

            for field in (
                "title",
                "summary",
                "status",
                "content_text",
                "content_json",
                "generation_order",
                "generation_reason",
            ):
                if field in payload and payload[field] is not None:
                    setattr(resource, field, payload[field])

            resource.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(resource)
            return self._resource_to_dto(resource)

    def delete_resource_package(self, user_id: str, project_id: str, package_id: str) -> None:
        with self._get_db_session() as db:
            package = self._get_package_or_raise(db, user_id, project_id, package_id)
            db.delete(package)
            db.commit()

    async def regenerate_generated_resource(
        self, user_id: str, project_id: str, resource_id: str
    ) -> GeneratedResourceDto:
        with self._get_db_session() as db:
            resource = (
                db.query(GeneratedResource)
                .filter(
                    GeneratedResource.id == resource_id,
                    GeneratedResource.project_id == project_id,
                    GeneratedResource.user_id == user_id,
                )
                .first()
            )
            if not resource:
                raise NotFoundError(f"Generated resource {resource_id} not found")

            package = resource.resource_package
            documents = (
                db.query(Document)
                .filter(
                    Document.project_id == project_id,
                    Document.id.in_(resource.source_document_ids or []),
                )
                .all()
            )
            chapter_ids = self._merge_distinct(
                (package.generation_params or {}).get("chapter_ids") or []
            )
            chapters, chapter_points, chapter_resources = self._load_chapter_scope(
                db, resource.resource_package.project, chapter_ids
            )
            document_context = self._combine_source_context(
                self._build_document_context(documents),
                self._build_chapter_context(
                    chapters, chapter_points, chapter_resources
                ),
            )
            scoped_instructions = self._build_scoped_instructions(
                (package.generation_params or {}).get("custom_instructions"), chapters
            )
            generated = await self._generate_resource_content_async(
                resource_type=resource.resource_type,
                topic=package.target_topic,
                goal=package.target_goal,
                difficulty_level=resource.difficulty_level,
                document_context=document_context,
                knowledge_point_ids=resource.knowledge_point_ids or [],
                weak_points=package.weak_knowledge_point_ids or [],
                custom_instructions=scoped_instructions,
                documents=documents,
                generation_params=package.generation_params or {},
            )

            resource.title = generated["title"]
            resource.summary = generated.get("summary")
            resource.format = generated["format"]
            resource.content_text = generated.get("content_text")
            resource.content_json = generated.get("content_json")
            resource.file_url = generated.get("file_url")
            resource.preview_url = generated.get("preview_url")
            resource.cover_image_url = generated.get("cover_image_url")
            resource.generator_agent = generated.get("generator_agent")
            resource.generation_reason = generated.get("generation_reason")
            resource.error_message = None
            resource.status = "completed"
            resource.version += 1
            resource.updated_at = datetime.now(timezone.utc)
            resource.completed_at = resource.updated_at

            trace = package.agent_trace or []
            self._append_agent_event(
                trace,
                package.id,
                "resource_completed",
                {
                    "resource_id": resource.id,
                    "resource_type": resource.resource_type,
                    "title": resource.title,
                    "version": resource.version,
                },
            )
            package.agent_trace = trace
            package.updated_at = resource.updated_at

            db.commit()
            db.refresh(resource)
            return self._resource_to_dto(resource)

    async def stream_resource_package_events(
        self, user_id: str, project_id: str, package_id: str
    ):
        package = self.get_resource_package(user_id, project_id, package_id)
        for event in package.agent_trace:
            yield ResourcePackageStreamEventDto(
                event=event["event"],
                package_id=package_id,
                timestamp=datetime.fromisoformat(event["timestamp"]),
                payload=event["payload"],
            )

    async def _publish_stream_event(
        self,
        sink: Callable[[ResourcePackageStreamEventDto], Awaitable[None]] | None,
        package_id: str,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        if sink is None:
            return
        await sink(ResourcePackageStreamEventDto(
            event=event,
            package_id=package_id,
            timestamp=datetime.now(timezone.utc),
            payload=payload,
        ))

    def _get_package_or_raise(self, db, user_id: str, project_id: str, package_id: str):
        package = (
            db.query(ResourcePackage)
            .filter(
                ResourcePackage.id == package_id,
                ResourcePackage.project_id == project_id,
                ResourcePackage.user_id == user_id,
            )
            .first()
        )
        if not package:
            raise NotFoundError(f"Resource package {package_id} not found")
        return package

    def _append_agent_event(
        self, events: list[dict], package_id: str, event: str, payload: dict
    ) -> None:
        events.append(
            {
                "event": event,
                "package_id": package_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
        )

    async def _get_or_create_diagnosis(
        self,
        *,
        user_id: str,
        project_id: str,
        package_id: str,
        target_topic: str,
        difficulty_level: str,
        custom_instructions: str | None,
        resource_types: list[str],
        generation_params: dict[str, Any],
        diagnosis_id: str | None,
        event_sink: Callable[[ResourcePackageStreamEventDto], Awaitable[None]] | None,
    ) -> "DiagnosisResponse":
        if not self.agent_orchestration_service:
            raise RuntimeError("Agent orchestration service is required")

        diagnosis = None
        if diagnosis_id:
            diagnosis = self.agent_orchestration_service.get_diagnosis(diagnosis_id)
            if diagnosis.project_id != project_id or diagnosis.student_id != user_id:
                raise NotFoundError(f"Diagnosis {diagnosis_id} not found")

        orchestration_types = [
            resource_type
            for resource_type in (
                self._to_orchestration_resource_type(resource_type)
                for resource_type in resource_types
            )
            if resource_type is not None
        ]

        async def forward_agent_event(agent_event: Any) -> None:
            await self._publish_stream_event(
                event_sink,
                package_id,
                "agent_step",
                {
                    "event_type": agent_event.event_type.value,
                    "agent_name": agent_event.agent_name.value
                    if agent_event.agent_name
                    else None,
                    "status": agent_event.status.value,
                    "summary": agent_event.summary,
                    **agent_event.payload,
                },
            )

        trigger = AgentTrigger(type="resource_package", id=package_id)
        meta = {
            "requested_topic": target_topic,
            "requested_instructions": custom_instructions,
            "requested_resource_types": orchestration_types,
            "difficulty": difficulty_level,
            "quiz_count": generation_params.get("quiz_count"),
            "flashcard_count": generation_params.get("flashcard_count"),
            "launch_context": generation_params.get("launch_context"),
        }
        if diagnosis is None:
            diagnosis = await self.agent_orchestration_service.generate_diagnosis(
                user_id=user_id,
                project_id=project_id,
                trigger=trigger,
                meta=meta,
                event_sink=forward_agent_event,
            )

        recommendations = (
            await self.agent_orchestration_service.generate_recommendations(
                user_id=user_id,
                project_id=project_id,
                diagnosis_id=diagnosis.diagnosis_id,
                trigger=trigger,
                meta=meta,
                event_sink=forward_agent_event,
            )
        )
        diagnosis.recommendations = recommendations.recommendations
        return diagnosis

    def _get_diagnosis_trace(self, diagnosis: "DiagnosisResponse") -> list["AgentEvent"]:
        if not self.agent_orchestration_service:
            return []
        try:
            return self.agent_orchestration_service.get_diagnosis_trace(
                diagnosis.diagnosis_id
            )
        except NotFoundError:
            return []

    def _build_agent_trace_from_events(
        self,
        *,
        package_id: str,
        diagnosis: "DiagnosisResponse",
        events: list["AgentEvent"],
    ) -> list[dict[str, Any]]:
        trace = []
        for event in events:
            trace.append(
                {
                    "event": event.event_type.value,
                    "package_id": package_id,
                    "timestamp": event.timestamp.isoformat(),
                    "payload": {
                        "agent": event.agent_name.value if event.agent_name else None,
                        "status": event.status.value,
                        "summary": event.summary,
                        **(event.payload or {}),
                    },
                }
            )
        self._append_agent_event(
            trace,
            package_id,
            "diagnosis_linked",
            {"diagnosis_id": diagnosis.diagnosis_id, "run_id": diagnosis.run_id},
        )
        return trace

    def _extract_knowledge_point_ids(self, diagnosis: "DiagnosisResponse") -> list[str]:
        related_points = (diagnosis.diagnosis or {}).get("related_knowledge_points") or []
        result = []
        for point in related_points:
            point_id = point.get("id")
            if point_id:
                result.append(str(point_id))
        return result

    def _extract_weak_point_ids(self, diagnosis: "DiagnosisResponse") -> list[str]:
        return self._extract_knowledge_point_ids(diagnosis)

    def _merge_distinct(self, *values: list[str]) -> list[str]:
        merged: list[str] = []
        seen = set()
        for items in values:
            for item in items:
                key = str(item).strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(key)
        return merged

    def _to_orchestration_resource_type(self, resource_type: str) -> str | None:
        mapping = {
            "lecture_note": "note",
            "practice_set": "quiz",
            "flashcards": "flashcards",
            "mind_map": "mind_map",
        }
        return mapping.get(resource_type)

    async def _generate_package_resource(
        self,
        *,
        user_id: str,
        project_id: str,
        resource_type: str,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        document_context: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        custom_instructions: str | None,
        documents: list[Document],
        generation_params: dict[str, Any],
        recommendations: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str]:
        recommendation = self._take_matching_recommendation(recommendations, resource_type)
        if recommendation is not None:
            return (
                self._build_generated_resource_reference(
                    project_id=project_id,
                    resource_type=resource_type,
                    recommendation=recommendation,
                    difficulty_level=difficulty_level,
                    custom_instructions=custom_instructions,
                ),
                "generating",
            )

        generated = await self._generate_resource_content_async(
            resource_type=resource_type,
            topic=topic,
            goal=goal,
            difficulty_level=difficulty_level,
            document_context=document_context,
            knowledge_point_ids=knowledge_point_ids,
            weak_points=weak_points,
            custom_instructions=custom_instructions,
            documents=documents,
            generation_params=generation_params,
        )
        return generated, "completed"

    def _take_matching_recommendation(
        self,
        recommendations: list[dict[str, Any]],
        resource_type: str,
    ) -> dict[str, Any] | None:
        orchestration_type = self._to_orchestration_resource_type(resource_type)
        if orchestration_type is None:
            return None

        for index, recommendation in enumerate(recommendations):
            if recommendation.get("recommendation_type") == orchestration_type:
                return recommendations.pop(index)
        return None

    def _build_generated_resource_reference(
        self,
        *,
        project_id: str,
        resource_type: str,
        recommendation: dict[str, Any],
        difficulty_level: str,
        custom_instructions: str | None,
    ) -> dict[str, Any]:
        reference_type = {
            "lecture_note": "note",
            "practice_set": "quiz",
            "flashcards": "flashcards",
            "mind_map": "mind_map",
        }[resource_type]

        return {
            "title": recommendation.get("title") or "Queued resource",
            "summary": (
                "Queued through the orchestration pipeline. Open the linked resource "
                "or wait for the worker to finish generation."
            ),
            "format": f"{reference_type}-ref",
            "generator_agent": "ResourceAgent",
            "generation_reason": "Generated through the shared multi-agent orchestration flow.",
            "estimated_minutes": self._estimate_minutes(resource_type),
            "preview_url": self._build_preview_url(
                project_id=project_id,
                resource_type=resource_type,
                target_id=str(recommendation.get("target_id") or ""),
            ),
            "content_json": {
                "target_id": recommendation.get("target_id"),
                "target_type": reference_type,
                "project_id": project_id,
                "reason_text": recommendation.get("reason_text", []),
                "topic": recommendation.get("topic"),
                "custom_instructions": recommendation.get("custom_instructions")
                or custom_instructions,
                "stream_on_client": bool(recommendation.get("stream_on_client")),
            },
            "content_text": None,
        }

    def _estimate_minutes(self, resource_type: str) -> int:
        defaults = {
            "lecture_note": 25,
            "practice_set": 30,
            "flashcards": 20,
            "mind_map": 15,
            "ppt_outline": 20,
            "pptx": 25,
            "programming_questions": 35,
            "code_lab": 40,
            "reading_material": 18,
            "video_script": 12,
            "video_recommendations": 15,
        }
        return defaults.get(resource_type, 15)

    def _build_preview_url(
        self, *, project_id: str, resource_type: str, target_id: str
    ) -> str | None:
        if not target_id:
            return None

        routes = {
            "lecture_note": f"/dashboard/p/{project_id}/n/{target_id}",
            "practice_set": f"/dashboard/p/{project_id}/q/{target_id}",
            "flashcards": f"/dashboard/p/{project_id}/f/{target_id}",
            "mind_map": f"/dashboard/p/{project_id}/m/{target_id}",
        }
        return routes.get(resource_type)

    def _build_document_context(self, documents: list[Document]) -> str:
        if not documents:
            return "No source documents were selected."

        lines = []
        for doc in documents:
            summary = doc.summary or "No summary available."
            lines.append(f"- {doc.file_name}: {summary}")
        return "\n".join(lines)

    def _load_chapter_scope(
        self, db, project: Project, chapter_ids: list[str]
    ) -> tuple[list[CourseChapter], list[KnowledgePoint], list[CourseResource]]:
        if not chapter_ids:
            return [], [], []
        if not project.course_id:
            raise ValueError("Project must be associated with a course before selecting chapters")

        chapters = (
            db.query(CourseChapter)
            .filter(
                CourseChapter.course_id == project.course_id,
                CourseChapter.id.in_(chapter_ids),
            )
            .order_by(CourseChapter.position, CourseChapter.created_at)
            .all()
        )
        if len(chapters) != len(chapter_ids):
            raise NotFoundError("One or more selected chapters are not in the project's course")

        points = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.course_id == project.course_id,
                KnowledgePoint.chapter_id.in_(chapter_ids),
            )
            .order_by(KnowledgePoint.position, KnowledgePoint.created_at)
            .all()
        )
        resources = (
            db.query(CourseResource)
            .filter(
                CourseResource.course_id == project.course_id,
                CourseResource.chapter_id.in_(chapter_ids),
            )
            .order_by(CourseResource.created_at)
            .all()
        )
        return chapters, points, resources

    def _build_chapter_context(
        self,
        chapters: list[CourseChapter],
        points: list[KnowledgePoint],
        resources: list[CourseResource],
    ) -> str:
        if not chapters:
            return ""

        points_by_chapter: dict[str, list[KnowledgePoint]] = {}
        for point in points:
            if point.chapter_id:
                points_by_chapter.setdefault(point.chapter_id, []).append(point)
        resources_by_chapter: dict[str, list[CourseResource]] = {}
        for resource in resources:
            if resource.chapter_id:
                resources_by_chapter.setdefault(resource.chapter_id, []).append(resource)

        sections: list[str] = []
        for chapter in chapters:
            lines = [f"## Course chapter: {chapter.title}"]
            if chapter.description:
                lines.append(chapter.description)
            if chapter.learning_objectives:
                lines.append(
                    "Learning objectives: " + "; ".join(chapter.learning_objectives)
                )
            chapter_points = points_by_chapter.get(chapter.id, [])
            if chapter_points:
                lines.append("Knowledge points:")
                lines.extend(
                    f"- {point.name}: {point.description or 'No description.'}"
                    for point in chapter_points
                )
            chapter_resources = resources_by_chapter.get(chapter.id, [])
            if chapter_resources:
                lines.append("Course materials:")
                lines.extend(
                    f"- {resource.title}: {resource.description or resource.source_url or 'No description.'}"
                    for resource in chapter_resources
                )
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    def _combine_source_context(
        self, document_context: str, chapter_context: str
    ) -> str:
        contexts = []
        if chapter_context:
            contexts.append(chapter_context)
        if document_context and document_context != "No source documents were selected.":
            contexts.append(document_context)
        return "\n\n".join(contexts) or "No source context was selected."

    def _build_scoped_instructions(
        self, custom_instructions: str | None, chapters: list[CourseChapter]
    ) -> str | None:
        parts = []
        if custom_instructions and custom_instructions.strip():
            parts.append(custom_instructions.strip())
        if chapters:
            parts.append(
                "Generate strictly around these selected course chapters: "
                + ", ".join(chapter.title for chapter in chapters)
            )
        return "\n\n".join(parts) or None

    async def _generate_resource_content_async(
        self,
        *,
        resource_type: str,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        document_context: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        custom_instructions: str | None,
        documents: list[Document],
        generation_params: dict[str, Any],
    ) -> dict:
        if resource_type == "programming_questions":
            return await self._generate_programming_questions(
                topic=topic,
                goal=goal,
                difficulty_level=difficulty_level,
                document_context=document_context,
                knowledge_point_ids=knowledge_point_ids,
                weak_points=weak_points,
                custom_instructions=custom_instructions,
                generation_params=generation_params,
            )

        if resource_type == "video_recommendations":
            if not self.baidu_search_client or not self.baidu_search_client.is_enabled:
                raise ValueError("Baidu AI Search is not configured")
            search_result = await self.baidu_search_client.search_videos(topic)
            videos = search_result["videos"]
            return {
                "title": f"{topic} 视频推荐",
                "summary": f"通过百度搜索找到 {len(videos)} 个相关视频资源。",
                "format": "video-links",
                "content_json": search_result,
                "cover_image_url": videos[0].get("thumbnail_url"),
                "generator_agent": "ResourceAgent",
                "generation_reason": "根据学习主题检索公开的视频资源链接。",
                "estimated_minutes": 15,
            }

        if resource_type == "ppt_outline":
            xfyun_result = await self._generate_xfyun_outline(
                topic=topic,
                goal=goal,
                document_context=document_context,
                custom_instructions=custom_instructions,
                documents=documents,
                generation_params=generation_params,
            )
            if xfyun_result is not None:
                return xfyun_result

        if resource_type == "pptx":
            xfyun_result = await self._generate_xfyun_pptx(
                topic=topic,
                goal=goal,
                difficulty_level=difficulty_level,
                document_context=document_context,
                knowledge_point_ids=knowledge_point_ids,
                weak_points=weak_points,
                custom_instructions=custom_instructions,
                documents=documents,
                generation_params=generation_params,
            )
            if xfyun_result is not None:
                return xfyun_result

        return self._generate_resource_content(
            resource_type=resource_type,
            topic=topic,
            goal=goal,
            difficulty_level=difficulty_level,
            document_context=document_context,
            knowledge_point_ids=knowledge_point_ids,
            weak_points=weak_points,
            custom_instructions=custom_instructions,
        )

    async def _generate_programming_questions(
        self,
        *,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        document_context: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        custom_instructions: str | None,
        generation_params: dict[str, Any],
    ) -> dict[str, Any]:
        count = self._get_programming_question_count(generation_params)
        fallback_reason = "Generated with a local fallback because the LLM was unavailable."
        if self.llm_config and self.llm_config.api_key:
            try:
                model = create_chat_model(
                    self.llm_config,
                    streaming=False,
                    temperature=0.35,
                ).bind(max_tokens=3500)
                messages = [
                    (
                        "system",
                        (
                            "You are a senior computer science teacher. "
                            "Generate concise, original programming assessment "
                            "questions as strict JSON only."
                        ),
                    ),
                    (
                        "user",
                        self._build_programming_questions_prompt(
                            topic=topic,
                            goal=goal,
                            difficulty_level=difficulty_level,
                            document_context=document_context,
                            knowledge_point_ids=knowledge_point_ids,
                            weak_points=weak_points,
                            custom_instructions=custom_instructions,
                            count=count,
                        ),
                    ),
                ]
                response = await model.ainvoke(messages)
                payload = self._extract_json_payload(str(response.content))
                content_json = self._normalize_programming_questions_payload(
                    payload,
                    topic=topic,
                    difficulty_level=difficulty_level,
                    count=count,
                )
                return self._build_programming_questions_resource(
                    topic=topic,
                    difficulty_level=difficulty_level,
                    content_json=content_json,
                    generated_by="DeepSeek",
                    reason="Generated from the configured OpenAI-compatible LLM endpoint.",
                )
            except Exception as exc:
                fallback_reason = (
                    "Generated with a local fallback because LLM generation failed: "
                    f"{exc}"
                )

        content_json = self._build_fallback_programming_questions(
            topic=topic,
            goal=goal,
            difficulty_level=difficulty_level,
            knowledge_point_ids=knowledge_point_ids,
            weak_points=weak_points,
            count=count,
        )
        return self._build_programming_questions_resource(
            topic=topic,
            difficulty_level=difficulty_level,
            content_json=content_json,
            generated_by="PracticeAgent",
            reason=fallback_reason,
        )

    def _get_programming_question_count(
        self, generation_params: dict[str, Any]
    ) -> int:
        raw_count = generation_params.get("programming_question_count", 3)
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 3
        return max(3, min(5, count))

    def _build_programming_questions_prompt(
        self,
        *,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        document_context: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        custom_instructions: str | None,
        count: int,
    ) -> str:
        return json.dumps(
            {
                "task": "Generate programming assessment questions.",
                "language": "Chinese",
                "topic": topic,
                "learning_goal": goal,
                "difficulty_level": difficulty_level,
                "question_count": count,
                "knowledge_point_ids": knowledge_point_ids,
                "weak_points": weak_points,
                "custom_instructions": custom_instructions,
                "source_context": document_context[:3500],
                "output_schema": {
                    "topic": "string",
                    "difficulty_level": "string",
                    "questions": [
                        {
                            "id": "q1",
                            "title": "string",
                            "description": "string",
                            "input_format": "string",
                            "output_format": "string",
                            "constraints": ["string"],
                            "examples": [
                                {
                                    "input": "string",
                                    "output": "string",
                                    "explanation": "string",
                                }
                            ],
                            "starter_code": "string",
                            "reference_solution": "string",
                            "hints": ["string"],
                            "knowledge_points": ["string"],
                            "difficulty": "beginner|intermediate|advanced",
                        }
                    ],
                },
                "rules": [
                    "Return only one JSON object.",
                    "Create 3 to 5 questions, matching question_count exactly.",
                    "Each question should be solvable in Python.",
                    "Keep descriptions suitable for a learning evaluation page.",
                ],
            },
            ensure_ascii=False,
        )

    def _extract_json_payload(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(stripped[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("LLM did not return a JSON object")

    def _normalize_programming_questions_payload(
        self,
        payload: dict[str, Any],
        *,
        topic: str,
        difficulty_level: str,
        count: int,
    ) -> dict[str, Any]:
        raw_questions = payload.get("questions")
        if not isinstance(raw_questions, list):
            raise ValueError("Programming question payload has no questions list")

        questions: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_questions[:count], start=1):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or f"{topic} programming question {index}")
            description = str(raw.get("description") or raw.get("problem") or "")
            if not description.strip():
                continue
            questions.append(
                {
                    "id": str(raw.get("id") or f"q{index}"),
                    "title": title,
                    "description": description,
                    "input_format": str(raw.get("input_format") or "See description."),
                    "output_format": str(raw.get("output_format") or "See description."),
                    "constraints": self._string_list(raw.get("constraints")),
                    "examples": self._normalize_examples(raw.get("examples")),
                    "starter_code": str(
                        raw.get("starter_code")
                        or "def solve(input_data):\n    # TODO\n    return None\n"
                    ),
                    "reference_solution": str(raw.get("reference_solution") or ""),
                    "hints": self._string_list(raw.get("hints")),
                    "knowledge_points": self._string_list(raw.get("knowledge_points")),
                    "difficulty": str(raw.get("difficulty") or difficulty_level),
                }
            )

        if len(questions) < 3:
            raise ValueError("Programming question payload contains fewer than 3 questions")

        return {
            "topic": str(payload.get("topic") or topic),
            "difficulty_level": str(payload.get("difficulty_level") or difficulty_level),
            "questions": questions[:count],
        }

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _normalize_examples(self, value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        examples = []
        for item in value[:2]:
            if not isinstance(item, dict):
                continue
            examples.append(
                {
                    "input": str(item.get("input") or ""),
                    "output": str(item.get("output") or ""),
                    "explanation": str(item.get("explanation") or ""),
                }
            )
        return examples

    def _build_programming_questions_resource(
        self,
        *,
        topic: str,
        difficulty_level: str,
        content_json: dict[str, Any],
        generated_by: str,
        reason: str,
    ) -> dict[str, Any]:
        questions = content_json.get("questions") or []
        return {
            "title": f"{topic} programming questions",
            "summary": f"{len(questions)} coding problems for learning evaluation.",
            "format": "json",
            "generator_agent": generated_by,
            "generation_reason": reason,
            "estimated_minutes": 35,
            "content_json": content_json,
        }

    def _build_fallback_programming_questions(
        self,
        *,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        count: int,
    ) -> dict[str, Any]:
        focus = goal or f"Practice core ideas of {topic}."
        knowledge_points = knowledge_point_ids or [topic]
        weak_text = ", ".join(weak_points) if weak_points else topic
        templates = [
            ("Implement the Core Operation", "Write a function that models the core operation in the topic."),
            ("Handle Boundary Cases", "Extend the solution to cover empty, minimal, and repeated inputs."),
            ("Optimize the First Solution", "Improve a straightforward implementation and explain the complexity."),
            ("Trace and Fix a Bug", "Given a flawed approach, identify the issue and implement a corrected version."),
            ("Design a Small Evaluator", "Build a helper that checks whether a candidate answer satisfies the rules."),
        ]
        questions = []
        for index, (title, description) in enumerate(templates[:count], start=1):
            questions.append(
                {
                    "id": f"q{index}",
                    "title": f"{topic}: {title}",
                    "description": f"{description} Learning goal: {focus}",
                    "input_format": "Read input_data as a string or structured Python value.",
                    "output_format": "Return the computed answer from solve(input_data).",
                    "constraints": [
                        "Keep the solution deterministic.",
                        "State time and space complexity after implementation.",
                    ],
                    "examples": [
                        {
                            "input": "sample input",
                            "output": "sample output",
                            "explanation": f"Use this example to verify the {topic} logic.",
                        }
                    ],
                    "starter_code": "def solve(input_data):\n    # TODO: implement\n    return None\n",
                    "reference_solution": "def solve(input_data):\n    return input_data\n",
                    "hints": [
                        f"Focus on {weak_text}.",
                        "Start with a clear state definition before coding.",
                    ],
                    "knowledge_points": knowledge_points,
                    "difficulty": difficulty_level,
                }
            )
        return {
            "topic": topic,
            "difficulty_level": difficulty_level,
            "questions": questions,
        }

    async def _generate_xfyun_outline(
        self,
        *,
        topic: str,
        goal: str | None,
        document_context: str,
        custom_instructions: str | None,
        documents: list[Document],
        generation_params: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.xfyun_ppt_client or not self.xfyun_ppt_client.is_enabled:
            return None

        query = self._build_xfyun_query(
            topic=topic,
            goal=goal,
            document_context=document_context,
            custom_instructions=custom_instructions,
        )
        options = self._get_xfyun_generation_options(generation_params)
        source_file = self._resolve_source_file(documents)
        try:
            if source_file is not None:
                response = await self.xfyun_ppt_client.create_outline_by_doc(
                    query=query,
                    language=options.get("language"),
                    search=options.get("search"),
                    business_id=options.get("business_id"),
                    file_path=source_file,
                    file_name=source_file.name,
                )
            else:
                response = await self.xfyun_ppt_client.create_outline(
                    query=query,
                    language=options.get("language"),
                    search=options.get("search"),
                    business_id=options.get("business_id"),
                )
        except XfyunPptError:
            raise
        data = response.get("data") or {}
        outline = data.get("outline") or {}
        return {
            "title": outline.get("title") or f"{topic} PPT outline",
            "summary": outline.get("subTitle") or f"XFYun generated outline for {topic}.",
            "format": "json",
            "generator_agent": "XfyunPptAgent",
            "generation_reason": "Generated with the XFYun PPT outline API.",
            "estimated_minutes": 20,
            "content_text": self._outline_to_markdown(outline),
            "content_json": {
                "provider": "xfyun",
                "sid": data.get("sid"),
                "outline": outline,
                "raw_response": data,
            },
        }

    async def _generate_xfyun_pptx(
        self,
        *,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        document_context: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        custom_instructions: str | None,
        documents: list[Document],
        generation_params: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.xfyun_ppt_client or not self.xfyun_ppt_client.is_enabled:
            return None

        query = self._build_xfyun_query(
            topic=topic,
            goal=goal,
            document_context=document_context,
            custom_instructions=custom_instructions,
            difficulty_level=difficulty_level,
            knowledge_point_ids=knowledge_point_ids,
            weak_points=weak_points,
        )
        options = self._get_xfyun_generation_options(generation_params)
        source_file = self._resolve_source_file(documents)

        provided_outline = options.get("outline")
        use_outline = bool(options.get("use_outline_generation")) or bool(provided_outline)

        if use_outline:
            outline = provided_outline
            if outline is None:
                outline_result = await self._generate_xfyun_outline(
                    topic=topic,
                    goal=goal,
                    document_context=document_context,
                    custom_instructions=custom_instructions,
                    documents=documents,
                    generation_params=generation_params,
                )
                outline = ((outline_result or {}).get("content_json") or {}).get("outline")
            if not outline:
                raise XfyunPptError("XFYun outline generation did not return an outline.")
            create_response = await self.xfyun_ppt_client.create_ppt_by_outline(
                outline=outline,
                query=query,
                template_id=options.get("template_id"),
                author=options.get("author"),
                language=options.get("language"),
                search=options.get("search"),
                is_card_note=options.get("is_card_note"),
                is_figure=options.get("is_figure"),
                ai_image=options.get("ai_image"),
                business_id=options.get("business_id"),
            )
        else:
            create_response = await self.xfyun_ppt_client.create(
                query=query,
                template_id=options.get("template_id"),
                author=options.get("author"),
                language=options.get("language"),
                search=options.get("search"),
                is_card_note=options.get("is_card_note"),
                is_figure=options.get("is_figure"),
                ai_image=options.get("ai_image"),
                business_id=options.get("business_id"),
                file_path=source_file,
                file_name=source_file.name if source_file is not None else None,
                file_url=options.get("file_url"),
            )

        create_data = create_response.get("data") or {}
        sid = create_data.get("sid")
        if not sid:
            raise XfyunPptError("XFYun PPT creation response did not include sid.")

        progress_response = await self.xfyun_ppt_client.wait_for_completion(sid)
        progress_data = progress_response.get("data") or {}

        return {
            "title": create_data.get("title") or f"{topic} PPTX draft",
            "summary": create_data.get("subTitle") or f"XFYun generated presentation for {topic}.",
            "format": "pptx-url",
            "generator_agent": "XfyunPptAgent",
            "generation_reason": "Generated with the XFYun PPT creation API.",
            "estimated_minutes": 25,
            "file_url": progress_data.get("pptUrl"),
            "preview_url": progress_data.get("pptUrl"),
            "cover_image_url": create_data.get("coverImgSrc"),
            "content_json": {
                "provider": "xfyun",
                "sid": sid,
                "title": create_data.get("title"),
                "subTitle": create_data.get("subTitle"),
                "coverImgSrc": create_data.get("coverImgSrc"),
                "outline": create_data.get("outline"),
                "pptStatus": progress_data.get("pptStatus"),
                "aiImageStatus": progress_data.get("aiImageStatus"),
                "cardNoteStatus": progress_data.get("cardNoteStatus"),
                "totalPages": progress_data.get("totalPages"),
                "donePages": progress_data.get("donePages"),
                "pptUrl": progress_data.get("pptUrl"),
                "errMsg": progress_data.get("errMsg"),
            },
            "content_text": self._build_pptx_summary_text(create_data, progress_data),
        }

    def _generate_resource_content(
        self,
        *,
        resource_type: str,
        topic: str,
        goal: str | None,
        difficulty_level: str,
        document_context: str,
        knowledge_point_ids: list[str],
        weak_points: list[str],
        custom_instructions: str | None,
    ) -> dict:
        goal_text = goal or f"Understand the essentials of {topic}."
        weak_text = ", ".join(weak_points) if weak_points else "No explicit weak points."
        knowledge_text = ", ".join(knowledge_point_ids) if knowledge_point_ids else "No tagged knowledge points."
        instruction_text = custom_instructions or "No extra instructions."

        common_reason = (
            f"Generated for topic '{topic}' with goal '{goal_text}', "
            f"difficulty '{difficulty_level}', and weak points '{weak_text}'."
        )

        if resource_type == "lecture_note":
            return {
                "title": f"{topic} explained for {difficulty_level} learners",
                "summary": f"A structured lecture note focused on {topic}.",
                "format": "markdown",
                "generator_agent": "ContentAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 25,
                "content_text": (
                    f"# {topic}\n\n"
                    f"## Learning goal\n{goal_text}\n\n"
                    f"## Key knowledge points\n{knowledge_text}\n\n"
                    f"## Source context\n{document_context}\n\n"
                    f"## Core explanation\n"
                    f"- Define the concept clearly.\n"
                    f"- Connect it to the selected course material.\n"
                    f"- Highlight why it matters in practice.\n\n"
                    f"## Weak point reminders\n{weak_text}\n\n"
                    f"## Custom instructions applied\n{instruction_text}\n"
                ),
            }

        if resource_type == "mind_map":
            return {
                "title": f"{topic} mind map",
                "summary": f"A concept map for quickly reviewing {topic}.",
                "format": "json",
                "generator_agent": "MediaAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 15,
                "content_json": {
                    "root": topic,
                    "nodes": [
                        {"id": "root", "label": topic},
                        {"id": "goal", "label": "Learning goal"},
                        {"id": "basics", "label": "Core concepts"},
                        {"id": "practice", "label": "Practice focus"},
                    ],
                    "edges": [
                        {"source": "root", "target": "goal"},
                        {"source": "root", "target": "basics"},
                        {"source": "root", "target": "practice"},
                    ],
                    "notes": {
                        "goal": goal_text,
                        "weak_points": weak_points,
                        "knowledge_points": knowledge_point_ids,
                    },
                },
            }

        if resource_type == "practice_set":
            return {
                "title": f"{topic} layered practice set",
                "summary": f"Practice questions arranged by difficulty for {topic}.",
                "format": "json",
                "generator_agent": "AssessmentAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 30,
                "content_json": {
                    "topic": topic,
                    "difficulty_level": difficulty_level,
                    "questions": [
                        {
                            "level": "basic",
                            "question": f"What is the core idea behind {topic}?",
                        },
                        {
                            "level": "intermediate",
                            "question": f"How would you apply {topic} to solve a realistic problem?",
                        },
                        {
                            "level": "advanced",
                            "question": f"What trade-offs appear when using {topic} in a full system?",
                        },
                    ],
                },
            }

        if resource_type == "flashcards":
            return {
                "title": f"{topic} flashcards",
                "summary": f"Flashcards focused on the key points of {topic}.",
                "format": "json",
                "generator_agent": "ResourceAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 20,
                "content_json": {
                    "topic": topic,
                    "difficulty_level": difficulty_level,
                    "cards": [
                        {
                            "question": f"What is the central concept behind {topic}?",
                            "answer": f"Summarize the most important principle of {topic}.",
                        },
                        {
                            "question": f"What common mistake should learners avoid in {topic}?",
                            "answer": f"Review the weak points: {weak_text}.",
                        },
                    ],
                },
            }

        if resource_type == "ppt_outline":
            return {
                "title": f"{topic} PPT outline",
                "summary": f"A slide-by-slide outline for presenting {topic}.",
                "format": "markdown",
                "generator_agent": "MediaAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 20,
                "content_text": (
                    f"# {topic} PPT Outline\n\n"
                    "1. Opening and learning objective\n"
                    "2. Why this topic matters\n"
                    "3. Core concepts\n"
                    "4. Example walkthrough\n"
                    "5. Common mistakes and weak points\n"
                    "6. Practice suggestions\n"
                    "7. Summary and next step\n"
                ),
            }

        if resource_type == "pptx":
            return {
                "title": f"{topic} PPTX draft",
                "summary": f"A presentation draft structure for {topic}.",
                "format": "json",
                "generator_agent": "MediaAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 25,
                "content_json": {
                    "title": f"{topic} presentation deck",
                    "theme": "teaching",
                    "slides": [
                        {
                            "page": 1,
                            "title": "Topic introduction",
                            "bullets": [
                                f"What {topic} is",
                                "Why this topic matters",
                                f"Learning goal: {goal_text}",
                            ],
                        },
                        {
                            "page": 2,
                            "title": "Core concepts",
                            "bullets": [
                                "Key definitions",
                                "Main relationships",
                                f"Knowledge points: {knowledge_text}",
                            ],
                        },
                        {
                            "page": 3,
                            "title": "Worked example",
                            "bullets": [
                                "Scenario setup",
                                "Step-by-step walkthrough",
                                "Common mistakes to avoid",
                            ],
                        },
                        {
                            "page": 4,
                            "title": "Practice and recap",
                            "bullets": [
                                "Suggested exercises",
                                f"Weak point reminders: {weak_text}",
                                "Summary and next steps",
                            ],
                        },
                    ],
                    "export_status": "draft_only",
                    "notes": "Structured PPTX content is ready for rendering/export in the UI.",
                },
            }

        if resource_type == "code_lab":
            return {
                "title": f"{topic} code lab",
                "summary": f"A hands-on coding exercise for {topic}.",
                "format": "markdown",
                "generator_agent": "PracticeAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 40,
                "content_text": (
                    f"# {topic} Code Lab\n\n"
                    f"## Objective\nBuild a small exercise around {topic}.\n\n"
                    "## Steps\n"
                    "1. Read the requirement.\n"
                    "2. Implement the core logic.\n"
                    "3. Run through a sample input/output.\n"
                    "4. Reflect on common failure cases.\n\n"
                    "## Starter snippet\n"
                    "```python\n"
                    "def solve(input_data):\n"
                    "    # TODO: implement the core logic\n"
                    "    return input_data\n"
                    "```\n"
                ),
            }

        if resource_type == "programming_questions":
            content_json = self._build_fallback_programming_questions(
                topic=topic,
                goal=goal,
                difficulty_level=difficulty_level,
                knowledge_point_ids=knowledge_point_ids,
                weak_points=weak_points,
                count=3,
            )
            return self._build_programming_questions_resource(
                topic=topic,
                difficulty_level=difficulty_level,
                content_json=content_json,
                generated_by="PracticeAgent",
                reason="Generated with the local programming question template.",
            )

        if resource_type == "reading_material":
            return {
                "title": f"{topic} reading guide",
                "summary": f"An extended reading guide for {topic}.",
                "format": "markdown",
                "generator_agent": "ResourceAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 18,
                "content_text": (
                    f"# {topic} Reading Guide\n\n"
                    f"Use the following source context:\n{document_context}\n"
                ),
            }

        if resource_type == "video_script":
            return {
                "title": f"{topic} short video script",
                "summary": f"A scene-by-scene script for explaining {topic}.",
                "format": "markdown",
                "generator_agent": "MediaAgent",
                "generation_reason": common_reason,
                "estimated_minutes": 12,
                "content_text": (
                    f"# {topic} Video Script\n\n"
                    "Scene 1: Hook the learner with the practical problem.\n"
                    "Scene 2: Explain the concept visually.\n"
                    "Scene 3: Show one worked example.\n"
                    "Scene 4: Reinforce key mistakes to avoid.\n"
                ),
            }

        return {
            "title": f"{topic} resource",
            "summary": f"Generated resource for {topic}.",
            "format": "markdown",
            "generator_agent": "ContentAgent",
            "generation_reason": common_reason,
            "estimated_minutes": 10,
            "content_text": f"Generated fallback content for {topic}.",
        }

    def _build_failed_resource_content(
        self, *, resource_type: str, topic: str, error_message: str
    ) -> dict[str, Any]:
        return {
            "title": f"{topic} {resource_type}",
            "summary": f"Failed to generate {resource_type} for {topic}.",
            "format": "error",
            "generator_agent": "ResourcePackageService",
            "generation_reason": "Resource generation failed.",
            "estimated_minutes": None,
            "content_text": error_message,
        }

    def _build_xfyun_query(
        self,
        *,
        topic: str,
        goal: str | None,
        document_context: str,
        custom_instructions: str | None,
        difficulty_level: str | None = None,
        knowledge_point_ids: list[str] | None = None,
        weak_points: list[str] | None = None,
    ) -> str:
        parts = [f"主题：{topic}"]
        if goal:
            parts.append(f"目标：{goal}")
        if difficulty_level:
            parts.append(f"难度：{difficulty_level}")
        if knowledge_point_ids:
            parts.append(f"知识点：{', '.join(knowledge_point_ids)}")
        if weak_points:
            parts.append(f"薄弱点：{', '.join(weak_points)}")
        if custom_instructions:
            parts.append(f"额外要求：{custom_instructions}")
        if document_context and document_context != "No source documents were selected.":
            parts.append(f"资料摘要：{document_context}")
        return "\n".join(parts)

    def _get_xfyun_generation_options(
        self, generation_params: dict[str, Any]
    ) -> dict[str, Any]:
        nested = generation_params.get("xfyun_ppt") or {}
        if not isinstance(nested, dict):
            nested = {}

        def pick(key: str, default=None):
            if key in nested:
                return nested[key]
            return generation_params.get(key, default)

        return {
            "template_id": pick("template_id"),
            "author": pick("author"),
            "language": pick("language"),
            "search": pick("search"),
            "is_card_note": pick("is_card_note"),
            "is_figure": pick("is_figure"),
            "ai_image": pick("ai_image"),
            "business_id": pick("business_id"),
            "file_url": pick("file_url"),
            "outline": pick("outline"),
            "use_outline_generation": bool(pick("use_outline_generation", False)),
        }

    def _resolve_source_file(self, documents: list[Document]) -> Path | None:
        for document in documents:
            if not document.original_blob_name:
                continue
            try:
                path = self.storage.resolve(document.original_blob_name)
            except ValueError:
                continue
            if path.exists():
                return path
        return None

    def _outline_to_markdown(self, outline: dict[str, Any]) -> str:
        lines = [f"# {outline.get('title') or 'PPT Outline'}", ""]
        counter = 1
        for chapter in outline.get("chapters") or []:
            chapter_title = chapter.get("chapterTitle") or f"Chapter {counter}"
            lines.append(f"{counter}. {chapter_title}")
            counter += 1
            for child in chapter.get("chapterContents") or []:
                child_title = child.get("chapterTitle")
                if child_title:
                    lines.append(f"{counter}. {child_title}")
                    counter += 1
        return "\n".join(lines)

    def _build_pptx_summary_text(
        self, create_data: dict[str, Any], progress_data: dict[str, Any]
    ) -> str:
        lines = [
            f"标题：{create_data.get('title') or '未命名'}",
            f"副标题：{create_data.get('subTitle') or '无'}",
            f"PPT 状态：{progress_data.get('pptStatus') or 'unknown'}",
            f"总页数：{progress_data.get('totalPages') or 'unknown'}",
            f"已完成页数：{progress_data.get('donePages') or 'unknown'}",
        ]
        if progress_data.get("pptUrl"):
            lines.append(f"下载地址：{progress_data['pptUrl']}")
        if progress_data.get("errMsg"):
            lines.append(f"错误信息：{progress_data['errMsg']}")
        return "\n".join(lines)

    def _resource_to_dto(self, resource: GeneratedResource) -> GeneratedResourceDto:
        return GeneratedResourceDto.model_validate(resource)

    def _model_to_dto(self, package: ResourcePackage) -> ResourcePackageDto:
        dto = ResourcePackageDto.model_validate(package)
        dto.resources = [self._resource_to_dto(resource) for resource in package.resources]
        return dto

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
