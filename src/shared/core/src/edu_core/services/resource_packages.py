from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from edu_db.models import Document, GeneratedResource, Project, ResourcePackage
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.resource_packages import (
    GeneratedResourceDto,
    ResourcePackageDto,
    ResourcePackageStreamEventDto,
)
from edu_core.storage import LocalStorageService
from edu_core.services.xfyun_ppt import XfyunPptClient, XfyunPptError


class ResourcePackageService:
    """Service for generating and managing resource packages."""

    def __init__(
        self,
        *,
        storage_root: str = "./.localdata",
        xfyun_ppt_client: XfyunPptClient | None = None,
    ) -> None:
        self.storage = LocalStorageService(storage_root)
        self.xfyun_ppt_client = xfyun_ppt_client

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

            resource_types = payload.get("resource_types") or [
                "lecture_note",
                "mind_map",
                "practice_set",
                "ppt_outline",
                "code_lab",
            ]
            now = datetime.now(timezone.utc)
            package_id = str(uuid4())
            target_topic = payload["target_topic"]
            target_goal = payload.get("target_goal")
            difficulty_level = payload.get("difficulty_level", "intermediate")
            generation_params = {
                "custom_instructions": payload.get("custom_instructions"),
                **(payload.get("generation_params") or {}),
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
                knowledge_point_ids=payload.get("knowledge_point_ids") or [],
                weak_knowledge_point_ids=payload.get("weak_knowledge_point_ids") or [],
                preferred_resource_types=resource_types,
                generation_params=generation_params,
                agent_trace=[],
                resource_count=len(resource_types),
                completed_resource_count=0,
                failed_resource_count=0,
                created_at=now,
                updated_at=now,
            )
            db.add(package)
            db.flush()

            agent_trace: list[dict] = []
            self._append_agent_event(
                agent_trace,
                package_id,
                "package_status_changed",
                {"status": "generating"},
            )
            self._append_agent_event(
                agent_trace,
                package_id,
                "agent_step",
                {
                    "agent": "ProfileAgent",
                    "message": "Collected generation context from request and selected documents.",
                },
            )

            document_context = self._build_document_context(documents)
            knowledge_point_ids = payload.get("knowledge_point_ids") or []
            weak_points = payload.get("weak_knowledge_point_ids") or []

            completed = 0
            failed = 0
            for order, resource_type in enumerate(resource_types):
                self._append_agent_event(
                    agent_trace,
                    package_id,
                    "resource_started",
                    {"resource_type": resource_type, "order": order},
                )

                try:
                    generated = await self._generate_resource_content_async(
                        resource_type=resource_type,
                        topic=target_topic,
                        goal=target_goal,
                        difficulty_level=difficulty_level,
                        document_context=document_context,
                        knowledge_point_ids=knowledge_point_ids,
                        weak_points=weak_points,
                        custom_instructions=payload.get("custom_instructions"),
                        documents=documents,
                        generation_params=generation_params,
                    )
                    resource_status = "completed"
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
                    "resource_completed" if resource_status == "completed" else "resource_failed",
                    {
                        "resource_id": resource.id,
                        "resource_type": resource_type,
                        "title": generated["title"],
                        "error_message": error_message,
                    },
                )

            package.status = "completed" if failed == 0 else "failed"
            package.completed_resource_count = completed
            package.failed_resource_count = failed
            package.completed_at = now if failed == 0 else None
            self._append_agent_event(
                agent_trace,
                package_id,
                "package_status_changed",
                {"status": package.status},
            )
            package.agent_trace = agent_trace

            db.commit()
            db.refresh(package)
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
            document_context = self._build_document_context(documents)
            generated = await self._generate_resource_content_async(
                resource_type=resource.resource_type,
                topic=package.target_topic,
                goal=package.target_goal,
                difficulty_level=resource.difficulty_level,
                document_context=document_context,
                knowledge_point_ids=resource.knowledge_point_ids or [],
                weak_points=package.weak_knowledge_point_ids or [],
                custom_instructions=(package.generation_params or {}).get(
                    "custom_instructions"
                ),
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

    def _build_document_context(self, documents: list[Document]) -> str:
        if not documents:
            return "No source documents were selected."

        lines = []
        for doc in documents:
            summary = doc.summary or "No summary available."
            lines.append(f"- {doc.file_name}: {summary}")
        return "\n".join(lines)

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
