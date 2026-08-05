from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from .base import BaseOrchestrationAgent


class MediaAgent(BaseOrchestrationAgent):
    agent_name = AgentName.MEDIA
    artifact_key = "media_resources"

    async def run(self, context: AgentRunContext) -> AgentResult:
        recommendations = context.artifacts.get("recommendations", {}).get(
            "recommendations", []
        )
        items = [
            item
            for item in recommendations
            if item.get("recommendation_type") in {"pptx", "video_recommendations"}
        ]
        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary=f"Prepared {len(items)} media resources through registered tools.",
            result={"items": items, "generation_mode": "standard_tool_dispatch"},
            reason_codes=["standard_tool_dispatch"] if items else ["not_requested"],
            confidence=0.9 if items else 0.5,
            field_status=FieldStatus.CONFIRMED if items else FieldStatus.MISSING,
            input_artifact_keys=["recommendations"],
            output_artifact_keys=[self.artifact_key],
        )
