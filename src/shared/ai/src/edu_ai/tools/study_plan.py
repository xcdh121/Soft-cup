"""Study-plan tools for the tutor agent."""

import asyncio
import json

from edu_ai.chatbot.context import ChatbotContext
from langchain.tools import tool
from langgraph.prebuilt import ToolRuntime


@tool(
    "study_plan_get_latest",
    description=(
        "Get the learner's latest personalized study plan from the current "
        "project's Personalized Learning > Study Plan page. Use this whenever "
        "the learner asks to view, recall, explain, or summarize their current "
        "study plan. This only reads the existing plan and never generates a new one."
    ),
)
async def get_latest_study_plan(
    runtime: ToolRuntime[ChatbotContext],
) -> str:
    """Return the same latest learning path shown on the study-plan page."""
    ctx = runtime.context
    service = ctx.learning_paths
    if service is None:
        raise RuntimeError("Study plan lookup is not configured")

    plan = await asyncio.to_thread(
        service.get_latest_learning_path,
        ctx.user_id,
        ctx.project_id,
    )
    page_url = f"/dashboard/p/{ctx.project_id}/study-plan"
    if plan is None:
        return json.dumps(
            {
                "status": "not_found",
                "message": "当前项目还没有个性化学习计划。",
                "study_plan_url": page_url,
            },
            ensure_ascii=False,
        )

    result = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else dict(plan)
    return json.dumps(
        {
            "status": "available",
            **result,
            "study_plan_url": page_url,
        },
        ensure_ascii=False,
        default=str,
    )


tools = [get_latest_study_plan]
