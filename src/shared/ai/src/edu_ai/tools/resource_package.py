"""Resource package generation tools for the chat agent."""

import json
from typing import Literal

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
    "code_lab",
    "reading_material",
    "video_script",
    "video_recommendations",
]
DifficultyLevel = Literal["beginner", "intermediate", "advanced"]


@tool(
    "resource_package_generate",
    description=(
        "Generate a unified learning resource package for the current project. "
        "Use this when the user requests a PPT/PPTX, a PPT outline, video "
        "recommendations, or several resource types together. For a PPT file, "
        "set resource_types to ['pptx']. For a combined package, include every "
        "requested type. Do not use this for a single note, mind map, quiz, or "
        "flashcard set when its dedicated tool is available."
    ),
)
async def generate_resource_package(
    topic: str,
    resource_types: list[ResourceType],
    runtime: ToolRuntime[ChatbotContext],
    difficulty_level: DifficultyLevel = "intermediate",
    goal: str | None = None,
    custom_instructions: str | None = None,
) -> str:
    """Generate a resource package and return a link to its result page."""
    ctx = runtime.context
    service = ctx.resource_packages
    if service is None:
        raise RuntimeError("Resource package generation is not configured")

    requested_types = list(dict.fromkeys(resource_types))
    if not requested_types:
        raise ValueError("At least one resource type is required")

    package = await service.generate_resource_package(
        user_id=ctx.user_id,
        project_id=ctx.project_id,
        payload={
            "target_topic": topic,
            "target_goal": goal,
            "resource_types": requested_types,
            "difficulty_level": difficulty_level,
            "custom_instructions": custom_instructions,
            "generation_mode": "manual",
            "generation_params": {"launch_context": "project overview chat"},
        },
    )

    return json.dumps(
        {
            "status": package.status,
            "message": "资源包已生成，可前往资源包页面查看。",
            "package_id": package.id,
            "resource_types": requested_types,
            "completed_resource_count": package.completed_resource_count,
            "failed_resource_count": package.failed_resource_count,
            "resource_package_url": (
                f"/dashboard/p/{ctx.project_id}/resource-packages"
            ),
        },
        ensure_ascii=False,
    )


tools = [generate_resource_package]
