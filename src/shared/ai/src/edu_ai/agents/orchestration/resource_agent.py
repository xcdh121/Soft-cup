from typing import TYPE_CHECKING, Any

from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent

if TYPE_CHECKING:
    from edu_core.schemas.flashcards import FlashcardGroupDto
    from edu_core.schemas.mind_maps import MindMapDto
    from edu_core.schemas.notes import NoteDto
    from edu_core.schemas.quizzes import QuizDto
    from edu_core.services.flashcard_groups import FlashcardGroupService
    from edu_core.services.mind_maps import MindMapService
    from edu_core.services.notes import NoteService
    from edu_core.services.quizzes import QuizService


class ResourceAgent(BaseOrchestrationAgent):
    agent_name = AgentName.RESOURCE
    artifact_key = "recommendations"

    def __init__(
        self,
        flashcard_group_service: "FlashcardGroupService | None" = None,
        quiz_service: "QuizService | None" = None,
        note_service: "NoteService | None" = None,
        mind_map_service: "MindMapService | None" = None,
    ) -> None:
        self.flashcard_group_service = flashcard_group_service
        self.quiz_service = quiz_service
        self.note_service = note_service
        self.mind_map_service = mind_map_service

    async def run(self, context: AgentRunContext) -> AgentResult:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        requested_resource_types = self._normalize_resource_types(
            context.meta.get("requested_resource_types", [])
        )
        if (
            not diagnosis.get("related_knowledge_points")
            and not requested_resource_types
        ):
            return AgentResult(
                agent_name=self.agent_name,
                status=RunStatus.COMPLETED,
                summary="Skipped strong resource recommendation because diagnosis evidence is insufficient.",
                result={"recommendations": []},
                reason_codes=["insufficient_evidence"],
                reason_text=[
                    "Recommendation generation requires a diagnosis with evidence-backed knowledge points."
                ],
                confidence=0.2,
                field_status=FieldStatus.MISSING,
                fallback_used=True,
                fallback_reason="insufficient_evidence",
            )

        resource_types = self._select_resource_types(context)
        topic = self._build_generation_topic(context)
        queued_resources = self._queue_resources(context, resource_types, topic)
        recommendations = self._build_recommendations(queued_resources, context)

        fallback_used = False
        fallback_reason = None
        if not recommendations:
            fallback_used = True
            fallback_reason = "resource_generation_unavailable"
            recommendations = self._build_fallback_recommendations(context)

        reason_codes = ["resource_generation_queued"]
        reason_text = [
            "Queued resource generation through the existing resource services."
        ]
        confidence = 0.8 if diagnosis.get("related_knowledge_points") else 0.55
        if fallback_used:
            reason_codes = ["resource_generation_unavailable"]
            reason_text = [
                "Resource generation services were unavailable, so existing resources or practice were recommended."
            ]
            confidence = 0.55 if recommendations else 0.2

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary=f"Generated {len(recommendations)} recommendations.",
            result={"recommendations": recommendations},
            reason_codes=reason_codes,
            reason_text=reason_text,
            confidence=confidence,
            field_status=FieldStatus.INFERRED
            if fallback_used
            else FieldStatus.CONFIRMED,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

    def _select_resource_types(self, context: AgentRunContext) -> list[str]:
        requested_types = self._normalize_resource_types(
            context.meta.get("requested_resource_types", [])
        )
        requested_types = [
            resource_type
            for resource_type in requested_types
            if resource_type in self._available_resource_types()
        ]
        if requested_types:
            return self._dedupe(requested_types)

        profile = context.artifacts.get("profile", {}).get("profile_summary", {})
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        weak_points = diagnosis.get("related_knowledge_points", [])
        preferred_types = self._normalize_resource_types(
            profile.get("preferred_resource_type", [])
        )

        selected: list[str] = ["note", "quiz"]
        for resource_type in preferred_types:
            if resource_type in self._available_resource_types():
                selected.append(resource_type)

        if len(weak_points) >= 2 and "flashcards" not in selected:
            selected.append("flashcards")

        return self._dedupe(selected)

    def _build_generation_topic(self, context: AgentRunContext) -> str:
        requested_topic = context.meta.get("requested_topic")
        if requested_topic:
            return str(requested_topic)

        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        related_points = diagnosis.get("related_knowledge_points") or []
        if related_points:
            first_point = related_points[0]
            if first_point.get("id"):
                return str(first_point["id"])
        if diagnosis.get("summary"):
            return str(diagnosis["summary"])
        if context.goal:
            return context.goal
        return "general reinforcement"

    def _queue_resources(
        self,
        context: AgentRunContext,
        resource_types: list[str],
        topic: str,
    ) -> list[dict[str, Any]]:
        queued_resources = []
        for resource_type in resource_types:
            resource = self._queue_resource(context, resource_type, topic)
            if resource:
                queued_resources.append(resource)
        return queued_resources

    def _queue_resource(
        self,
        context: AgentRunContext,
        resource_type: str,
        topic: str,
    ) -> dict[str, Any] | None:
        if resource_type == "note" and self.note_service:
            custom_instructions = self._build_custom_instructions(context)
            note = self.note_service.create_note(
                project_id=context.project_id,
                title=self._build_title("note", topic),
                description="ResourceAgent queued note generation",
                content="",
            )
            stream_in_package = (
                context.trigger.type == "resource_package"
                and bool(context.meta.get("stream_note_in_package"))
            )
            if not stream_in_package:
                self.note_service.queue_generation(
                    note_id=note.id,
                    project_id=context.project_id,
                    topic=topic,
                    custom_instructions=custom_instructions,
                    user_id=context.student_id,
                )
            return {
                **self._queued_resource("note", note, note.id, note.title),
                "topic": topic,
                "custom_instructions": custom_instructions,
                "stream_on_client": False,
                "stream_in_package": stream_in_package,
            }

        if resource_type == "quiz" and self.quiz_service:
            quiz = self.quiz_service.create_quiz(
                project_id=context.project_id,
                name=self._build_title("quiz", topic),
                description="ResourceAgent queued quiz generation",
            )
            quiz_count = context.meta.get("quiz_count")
            custom_instructions = self._build_custom_instructions(context)
            stream_in_package = (
                context.trigger.type == "resource_package"
                and bool(context.meta.get("stream_quiz_in_package"))
            )
            if not stream_in_package:
                self.quiz_service.queue_generation(
                    quiz_id=quiz.id,
                    project_id=context.project_id,
                    topic=topic,
                    custom_instructions=custom_instructions,
                    count=quiz_count
                    if isinstance(quiz_count, int) and quiz_count > 0
                    else 5,
                    user_id=context.student_id,
                )
            return {
                **self._queued_resource("quiz", quiz, quiz.id, quiz.name),
                "topic": topic,
                "custom_instructions": custom_instructions,
                "count": quiz_count
                if isinstance(quiz_count, int) and quiz_count > 0
                else 5,
                "stream_in_package": stream_in_package,
            }

        if resource_type == "flashcards" and self.flashcard_group_service:
            group = self.flashcard_group_service.create_flashcard_group(
                project_id=context.project_id,
                name=self._build_title("flashcards", topic),
                description="ResourceAgent queued flashcard generation",
            )
            flashcard_count = context.meta.get("flashcard_count")
            difficulty = context.meta.get("difficulty")
            custom_instructions = self._build_custom_instructions(context)
            stream_in_package = (
                context.trigger.type == "resource_package"
                and bool(context.meta.get("stream_flashcards_in_package"))
            )
            resolved_count = (
                flashcard_count
                if isinstance(flashcard_count, int) and flashcard_count > 0
                else 8
            )
            if not stream_in_package:
                self.flashcard_group_service.queue_generation(
                    group_id=group.id,
                    project_id=context.project_id,
                    topic=topic,
                    custom_instructions=custom_instructions,
                    count=resolved_count,
                    difficulty=str(difficulty) if difficulty else None,
                    user_id=context.student_id,
                )
            return {
                **self._queued_resource(
                    "flashcards", group, group.id, group.name
                ),
                "topic": topic,
                "custom_instructions": custom_instructions,
                "count": resolved_count,
                "difficulty": str(difficulty) if difficulty else None,
                "stream_in_package": stream_in_package,
            }

        if resource_type == "mind_map" and self.mind_map_service:
            mind_map = self.mind_map_service.create_mind_map(
                user_id=context.student_id,
                project_id=context.project_id,
                title=self._build_title("mind_map", topic),
                description="ResourceAgent queued mind map generation",
            )
            self.mind_map_service.queue_generation(
                user_id=context.student_id,
                project_id=context.project_id,
                mind_map_id=mind_map.id,
                topic=topic,
                custom_instructions=self._build_custom_instructions(context),
            )
            return self._queued_resource(
                "mind_map", mind_map, mind_map.id, mind_map.title
            )

        return None

    def _build_recommendations(
        self,
        queued_resources: list[dict[str, Any]],
        context: AgentRunContext,
    ) -> list[dict[str, Any]]:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        weak_points = diagnosis.get("related_knowledge_points", [])
        profile = context.artifacts.get("profile", {}).get("profile_summary", {})
        preferred_types = set(
            self._normalize_resource_types(
                profile.get("resource_preference")
                or profile.get("preferred_resource_type", [])
            )
        )
        learning_goal = profile.get("learning_goal")
        recommendations = []
        for index, resource in enumerate(queued_resources, start=1):
            reason_codes = ["generation_queued"]
            reason_text = [
                "A new resource was queued through the project generation services."
            ]
            if weak_points:
                reason_codes.append("weak_mastery")
                reason_text.append(
                    "The resource targets an evidence-backed weak knowledge point."
                )
            if resource["resource_type"] in preferred_types:
                reason_codes.append("profile_preference_match")
                reason_text.append(
                    "The resource type matches the learner's saved resource preference."
                )
            if learning_goal:
                reason_codes.append("learning_goal_alignment")
                reason_text.append(
                    f"The recommendation supports the saved learning goal: {learning_goal}."
                )
            recommendations.append(
                {
                    "id": f"{context.run_id}_rec_{index:03d}",
                    "recommendation_type": resource["resource_type"],
                    "target_id": resource["id"],
                    "title": resource["title"],
                    "reason_codes": reason_codes,
                    "reason_text": reason_text,
                    "score": round(0.9 - (index - 1) * 0.05, 2),
                    "recommended_by": self.agent_name.value,
                    "topic": resource.get("topic"),
                    "custom_instructions": resource.get("custom_instructions"),
                    "stream_on_client": bool(resource.get("stream_on_client")),
                    "stream_in_package": bool(resource.get("stream_in_package")),
                }
            )
        return recommendations

    def _build_fallback_recommendations(
        self,
        context: AgentRunContext,
    ) -> list[dict[str, Any]]:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        related_points = diagnosis.get("related_knowledge_points", [])
        resources = context.context.generated_resources
        recommendations = []

        for index, resource in enumerate(resources[:5], start=1):
            recommendations.append(
                {
                    "id": f"{context.run_id}_rec_{index:03d}",
                    "recommendation_type": resource.get("resource_type", "resource"),
                    "target_id": resource.get("id"),
                    "title": resource.get("title", "Learning resource"),
                    "reason_codes": [
                        "weak_mastery",
                        "available_resource",
                    ],
                    "reason_text": [
                        "The related knowledge point has low mastery.",
                        "An existing project resource is available.",
                    ],
                    "score": round(0.75 - (index - 1) * 0.05, 2),
                    "recommended_by": self.agent_name.value,
                    "recommendation_mode": "fallback",
                }
            )

        if not recommendations and related_points:
            first_point = related_points[0]
            recommendations.append(
                {
                    "id": f"{context.run_id}_rec_001",
                    "recommendation_type": "practice",
                    "target_id": first_point["id"],
                    "title": "Complete targeted weak-point practice",
                    "reason_codes": ["weak_mastery", "no_existing_resource"],
                    "reason_text": [
                        "The related knowledge point has low mastery.",
                        "No matching generated resource is currently available.",
                    ],
                    "score": 0.6,
                    "recommended_by": self.agent_name.value,
                    "recommendation_mode": "fallback",
                }
            )
        return recommendations

    def _normalize_resource_types(self, values: Any) -> list[str]:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            return []

        aliases = {
            "flashcard": "flashcards",
            "flashcard_group": "flashcards",
            "flashcard_group_generation": "flashcards",
            "mindmap": "mind_map",
            "mind-map": "mind_map",
            "lecture_note": "note",
            "practice_set": "quiz",
        }
        normalized = []
        for value in values:
            key = str(value).strip().lower()
            exact = aliases.get(key, key)
            if exact in {
                "note",
                "mind_map",
                "quiz",
                "flashcards",
                "video_recommendations",
                "programming_questions",
                "pptx",
            }:
                normalized.append(exact)
                continue

            keyword_aliases = (
                (("视频", "video"), "video_recommendations"),
                (("思维导图", "图解", "diagram", "visual", "mind map"), "mind_map"),
                (("闪卡", "卡片", "flashcard"), "flashcards"),
                (("刷题", "练习", "题目", "practice", "quiz", "exercise"), "quiz"),
                (
                    ("编程", "代码", "实操", "programming", "coding"),
                    "programming_questions",
                ),
                (
                    ("笔记", "教材", "阅读", "文档", "note", "reading", "document"),
                    "note",
                ),
                (("ppt", "演示"), "pptx"),
            )
            matches = [
                resource_type
                for keywords, resource_type in keyword_aliases
                if any(keyword in key for keyword in keywords)
            ]
            normalized.extend(matches or [exact])
        return self._dedupe(normalized)

    def _available_resource_types(self) -> set[str]:
        return {"note", "mind_map", "quiz", "flashcards"}

    def _dedupe(self, values: list[str]) -> list[str]:
        seen = set()
        deduped = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _build_title(self, resource_type: str, topic: str) -> str:
        labels = {
            "note": "Reinforcement note",
            "mind_map": "Reinforcement mind map",
            "quiz": "Reinforcement quiz",
            "flashcards": "Reinforcement flashcards",
        }
        return f"{labels.get(resource_type, 'Learning resource')}: {topic}"

    def _build_custom_instructions(self, context: AgentRunContext) -> str:
        requested_instructions = str(
            context.meta.get("requested_instructions") or ""
        ).strip()
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        summary = diagnosis.get("summary")
        difficulty = str(context.meta.get("difficulty") or "").strip()

        parts: list[str] = []
        if requested_instructions:
            parts.append(requested_instructions)
        if summary:
            parts.append(f"Generate the resource based on this diagnosis: {summary}")
        else:
            parts.append("Generate a reinforcement resource based on the current learning diagnosis.")
        if difficulty:
            parts.append(f"Target difficulty: {difficulty}")
        return "\n".join(parts)

    def _queued_resource(
        self,
        resource_type: str,
        dto: "NoteDto | QuizDto | FlashcardGroupDto | MindMapDto",
        resource_id: str,
        title: str,
    ) -> dict[str, Any]:
        return {
            "resource_type": resource_type,
            "id": resource_id,
            "title": title,
            "resource": dto,
        }
