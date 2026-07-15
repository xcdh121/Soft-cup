"""Resource package generation tools for the chat agent."""

import asyncio
import json
import logging
from typing import Any, Literal

from edu_ai.chatbot.context import ChatbotContext
from langchain.tools import tool
from langgraph.prebuilt import ToolRuntime

ResourceType = Literal[
    "lecture_note",
    "mind_map",
    "practice_set",
    "flashcards",
    "ppt_outline",
    "pptx",
    "programming_questions",
    "code_lab",
    "reading_material",
    "video_script",
    "video_recommendations",
]
DifficultyLevel = Literal["beginner", "intermediate", "advanced"]
logger = logging.getLogger(__name__)
_BACKGROUND_GENERATION_TASKS: set[asyncio.Task[Any]] = set()


def _track_background_generation(task: asyncio.Task[Any]) -> None:
    """Keep generation alive after the chat tool has returned its progress link."""
    _BACKGROUND_GENERATION_TASKS.add(task)

    def finish(completed_task: asyncio.Task[Any]) -> None:
        _BACKGROUND_GENERATION_TASKS.discard(completed_task)
        if completed_task.cancelled():
            return
        try:
            completed_task.result()
        except Exception:
            logger.exception("Background resource-package generation failed")

    task.add_done_callback(finish)


async def _start_resource_package_generation(
    *, service: Any, user_id: str, project_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Return once the package row exists while generation continues in background."""
    loop = asyncio.get_running_loop()
    package_started: asyncio.Future[dict[str, Any]] = loop.create_future()

    async def capture_start(event: Any) -> None:
        if event.event == "package_started" and not package_started.done():
            package_started.set_result(
                {
                    "id": event.package_id,
                    "status": event.payload.get("status", "generating"),
                    "completed_resource_count": 0,
                    "failed_resource_count": 0,
                }
            )

    generation_task = asyncio.create_task(
        service.generate_resource_package(
            user_id=user_id,
            project_id=project_id,
            payload=payload,
            event_sink=capture_start,
        )
    )
    _track_background_generation(generation_task)

    await asyncio.wait(
        {generation_task, package_started},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if package_started.done():
        return package_started.result()

    # Fast implementations and test doubles may finish without publishing an
    # event. Preserve the synchronous result as a compatible fallback.
    package = generation_task.result()
    return {
        "id": package.id,
        "status": package.status,
        "completed_resource_count": package.completed_resource_count,
        "failed_resource_count": package.failed_resource_count,
    }


def _profile_fields(context: ChatbotContext) -> dict[str, Any]:
    profile = getattr(context, "learner_profile", {}) or {}
    raw_fields = profile.get("fields", profile)
    fields: dict[str, Any] = {}
    for key, raw_value in raw_fields.items():
        value = (
            raw_value.get("value")
            if isinstance(raw_value, dict) and "value" in raw_value
            else raw_value
        )
        if value not in (None, "", [], {}):
            fields[key] = value
    return fields


def _preference_resource_types(fields: dict[str, Any]) -> list[ResourceType]:
    preference = fields.get("resource_preference")
    values = preference if isinstance(preference, list) else [preference]
    preference_text = " ".join(str(value).lower() for value in values if value)
    mappings: tuple[tuple[tuple[str, ...], ResourceType], ...] = (
        (("视频", "video"), "video_recommendations"),
        (("思维导图", "图解", "visual", "diagram", "mind map"), "mind_map"),
        (("闪卡", "卡片", "flashcard"), "flashcards"),
        (("刷题", "练习", "题目", "practice", "quiz", "exercise"), "practice_set"),
        (("编程", "代码", "实操", "programming", "coding"), "programming_questions"),
        (
            ("笔记", "教材", "阅读", "文档", "note", "reading", "document"),
            "lecture_note",
        ),
        (("ppt", "演示"), "pptx"),
    )
    selected = [
        resource_type
        for keywords, resource_type in mappings
        if any(keyword in preference_text for keyword in keywords)
    ]
    if selected:
        return list(dict.fromkeys(selected))

    cognitive_style = str(fields.get("cognitive_style") or "").lower()
    if any(keyword in cognitive_style for keyword in ("视觉", "visual", "图像")):
        return ["mind_map", "lecture_note", "practice_set"]
    if any(keyword in cognitive_style for keyword in ("实践", "动手", "practical")):
        return ["practice_set", "programming_questions", "lecture_note"]
    return ["lecture_note", "mind_map", "practice_set"]


def _resolve_topic(
    topic: str | None, context: ChatbotContext, fields: dict[str, Any]
) -> str:
    explicit_topic = str(topic or "").strip()
    generic_topics = {
        "",
        "个性化资源",
        "个性化推荐",
        "学习资源",
        "personalized resources",
        "resource recommendations",
    }
    if explicit_topic.lower() not in generic_topics:
        return explicit_topic

    evidence = getattr(context, "learning_evidence", {}) or {}
    weak_points = evidence.get("weak_points") or []
    if weak_points and isinstance(weak_points[0], dict):
        weak_topic = weak_points[0].get("name") or weak_points[0].get("id")
        if weak_topic:
            return str(weak_topic)

    current_course = fields.get("current_course")
    if current_course:
        return str(current_course)
    project = getattr(context, "project_context", {}) or {}
    return str(project.get("course_name") or project.get("project_name") or "当前课程")


def _resolve_difficulty(
    difficulty_level: DifficultyLevel | None,
    context: ChatbotContext,
    fields: dict[str, Any],
) -> DifficultyLevel:
    if difficulty_level:
        return difficulty_level

    evidence = getattr(context, "learning_evidence", {}) or {}
    mastery = evidence.get("overall_mastery")
    knowledge_background = fields.get("knowledge_background")
    if mastery is None and isinstance(knowledge_background, dict):
        mastery = knowledge_background.get("average_mastery")
    try:
        numeric_mastery = float(mastery)
    except (TypeError, ValueError):
        return "intermediate"
    if numeric_mastery < 50:
        return "beginner"
    if numeric_mastery >= 80:
        return "advanced"
    return "intermediate"


def _personalization_basis(
    context: ChatbotContext, fields: dict[str, Any]
) -> dict[str, Any]:
    evidence = getattr(context, "learning_evidence", {}) or {}
    weak_points = evidence.get("weak_points") or []
    return {
        "profile_fields": {
            key: fields[key]
            for key in (
                "major_background",
                "current_course",
                "learning_goal",
                "resource_preference",
                "cognitive_style",
                "available_study_time",
            )
            if key in fields
        },
        "weak_points": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "mastery_score": item.get("mastery_score"),
            }
            for item in weak_points[:5]
            if isinstance(item, dict)
        ],
        "overall_mastery": evidence.get("overall_mastery"),
        "recent_accuracy": evidence.get("recent_accuracy"),
    }


@tool(
    "resource_package_generate",
    description=(
        "Generate a unified learning resource package for the current project. "
        "Use this for every request that creates learning content, including a "
        "single note, mind map, quiz/practice set, flashcard set, PPT/PPTX, PPT "
        "outline, video recommendation, or several resource types together. "
        "For requests based on the learner's situation, omit topic, resource_types, "
        "goal, and difficulty_level when they are not explicitly supplied; the tool "
        "will derive them from the saved profile and learning evidence."
    ),
)
async def generate_resource_package(
    runtime: ToolRuntime[ChatbotContext],
    topic: str | None = None,
    resource_types: list[ResourceType] | None = None,
    difficulty_level: DifficultyLevel | None = None,
    goal: str | None = None,
    custom_instructions: str | None = None,
) -> str:
    """Generate a resource package and return a link to its result page."""
    ctx = runtime.context
    service = ctx.resource_packages
    if service is None:
        raise RuntimeError("Resource package generation is not configured")

    fields = _profile_fields(ctx)
    requested_types = list(
        dict.fromkeys(resource_types or _preference_resource_types(fields))
    )
    resolved_topic = _resolve_topic(topic, ctx, fields)
    resolved_goal = goal or fields.get("learning_goal")
    resolved_difficulty = _resolve_difficulty(difficulty_level, ctx, fields)
    personalization_basis = _personalization_basis(ctx, fields)
    personalization_instruction = (
        "Personalize this package using the following saved learner context and "
        "learning evidence. Do not invent additional learner traits:\n"
        + json.dumps(personalization_basis, ensure_ascii=False)
    )
    resolved_instructions = "\n\n".join(
        part for part in (custom_instructions, personalization_instruction) if part
    )
    weak_point_ids = [
        str(item["id"])
        for item in personalization_basis["weak_points"]
        if item.get("id")
    ]
    learner_profile = getattr(ctx, "learner_profile", {}) or {}

    package = await _start_resource_package_generation(
        service=service,
        user_id=ctx.user_id,
        project_id=ctx.project_id,
        payload={
            "profile_id": learner_profile.get("id"),
            "target_topic": resolved_topic,
            "target_goal": resolved_goal,
            "resource_types": requested_types,
            "knowledge_point_ids": weak_point_ids,
            "weak_knowledge_point_ids": weak_point_ids,
            "difficulty_level": resolved_difficulty,
            "custom_instructions": resolved_instructions,
            "generation_mode": "recommended",
            "generation_params": {
                "launch_context": "personalized tutor recommendation",
                "personalization_basis": personalization_basis,
            },
        },
    )

    package_id = package["id"]
    package_status = package["status"]
    generating_message = "资源包已开始后台生成，可立即打开进度页面查看。"  # noqa: RUF001
    completed_message = "资源包已生成，可前往资源包页面查看。"  # noqa: RUF001
    return json.dumps(
        {
            "status": package_status,
            "message": (
                generating_message
                if package_status == "generating"
                else completed_message
            ),
            "package_id": package_id,
            "resource_types": requested_types,
            "resource_count": len(requested_types),
            "target_topic": resolved_topic,
            "target_goal": resolved_goal,
            "difficulty_level": resolved_difficulty,
            "personalization_basis": personalization_basis,
            "completed_resource_count": package["completed_resource_count"],
            "failed_resource_count": package["failed_resource_count"],
            "resource_package_url": (
                f"/dashboard/p/{ctx.project_id}/resource-packages"
                f"?packageId={package_id}"
            ),
        },
        ensure_ascii=False,
    )


tools = [generate_resource_package]
