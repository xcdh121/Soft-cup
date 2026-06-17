from typing import TYPE_CHECKING, Any

from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
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
        resource_types = self._select_resource_types(context)
        topic = self._build_generation_topic(context)
        queued_resources = self._queue_resources(context, resource_types, topic)
        recommendations = self._build_recommendations(queued_resources, context)

        if not recommendations:
            recommendations = self._build_fallback_recommendations(context)

        reason_codes = ["resource_generation_queued"]
        reason_text = ["基于诊断结果触发资源生成并生成推荐"]
        if not queued_resources:
            reason_codes = ["resource_recommendation_generated"]
            reason_text = ["基于诊断结果和项目资源生成推荐"]

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary=f"已生成 {len(recommendations)} 条推荐",
            result={"recommendations": recommendations},
            reason_codes=reason_codes,
            reason_text=reason_text,
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
            note = self.note_service.create_note(
                project_id=context.project_id,
                title=self._build_title("note", topic),
                description="ResourceAgent queued note generation",
                content="",
            )
            self.note_service.queue_generation(
                note_id=note.id,
                project_id=context.project_id,
                topic=topic,
                custom_instructions=self._build_custom_instructions(context),
                user_id=context.student_id,
            )
            return self._queued_resource("note", note, note.id, note.title)

        if resource_type == "quiz" and self.quiz_service:
            quiz = self.quiz_service.create_quiz(
                project_id=context.project_id,
                name=self._build_title("quiz", topic),
                description="ResourceAgent queued quiz generation",
            )
            quiz_count = context.meta.get("quiz_count")
            self.quiz_service.queue_generation(
                quiz_id=quiz.id,
                project_id=context.project_id,
                topic=topic,
                custom_instructions=self._build_custom_instructions(context),
                count=quiz_count if isinstance(quiz_count, int) and quiz_count > 0 else 5,
                user_id=context.student_id,
            )
            return self._queued_resource("quiz", quiz, quiz.id, quiz.name)

        if resource_type == "flashcards" and self.flashcard_group_service:
            group = self.flashcard_group_service.create_flashcard_group(
                project_id=context.project_id,
                name=self._build_title("flashcards", topic),
                description="ResourceAgent queued flashcard generation",
            )
            flashcard_count = context.meta.get("flashcard_count")
            difficulty = context.meta.get("difficulty")
            self.flashcard_group_service.queue_generation(
                group_id=group.id,
                project_id=context.project_id,
                topic=topic,
                custom_instructions=self._build_custom_instructions(context),
                count=flashcard_count
                if isinstance(flashcard_count, int) and flashcard_count > 0
                else 8,
                difficulty=str(difficulty) if difficulty else None,
                user_id=context.student_id,
            )
            return self._queued_resource("flashcards", group, group.id, group.name)

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
        recommendations = []
        for index, resource in enumerate(queued_resources, start=1):
            recommendations.append(
                {
                    "id": f"{context.run_id}_rec_{index:03d}",
                    "recommendation_type": resource["resource_type"],
                    "target_id": resource["id"],
                    "title": resource["title"],
                    "reason_codes": [
                        "weak_mastery",
                        "generation_queued",
                        "profile_preference_match",
                    ],
                    "reason_text": [
                        "相关知识点掌握度较低",
                        "已通过现有资源服务创建占位资源并加入生成队列",
                        "资源类型结合学习画像或默认补强策略选择",
                    ],
                    "score": round(0.9 - (index - 1) * 0.05, 2),
                    "recommended_by": self.agent_name.value,
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
                    "title": resource.get("title", "学习资源"),
                    "reason_codes": [
                        "weak_mastery",
                        "available_resource",
                    ],
                    "reason_text": [
                        "相关知识点掌握度较低",
                        "项目中已有可用学习资源",
                    ],
                    "score": round(0.85 - (index - 1) * 0.05, 2),
                    "recommended_by": self.agent_name.value,
                }
            )

        if not recommendations and related_points:
            first_point = related_points[0]
            recommendations.append(
                {
                    "id": f"{context.run_id}_rec_001",
                    "recommendation_type": "practice",
                    "target_id": first_point["id"],
                    "title": "完成薄弱知识点专项练习",
                    "reason_codes": ["weak_mastery", "no_existing_resource"],
                    "reason_text": [
                        "相关知识点掌握度较低",
                        "当前没有匹配的已生成资源，先推荐专项练习",
                    ],
                    "score": 0.78,
                    "recommended_by": self.agent_name.value,
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
            normalized.append(aliases.get(key, key))
        return normalized

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
            "note": "补强笔记",
            "mind_map": "补强思维导图",
            "quiz": "补强测验",
            "flashcards": "补强闪卡",
        }
        return f"{labels.get(resource_type, '学习资源')}：{topic}"

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
            parts.append(f"根据诊断结论生成资源：{summary}")
        else:
            parts.append("根据当前学习诊断生成补强资源")
        if difficulty:
            parts.append(f"目标难度：{difficulty}")
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
