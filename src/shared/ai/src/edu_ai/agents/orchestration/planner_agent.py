from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class PlannerAgent(BaseOrchestrationAgent):
    agent_name = AgentName.PLANNER
    artifact_key = "learning_path"

    async def run(self, context: AgentRunContext) -> AgentResult:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        recommendations = context.artifacts.get("recommendations", {}).get(
            "recommendations", []
        )
        profile = context.artifacts.get("profile", {}).get("profile_summary", {})
        related_points = diagnosis.get("related_knowledge_points", [])

        path_steps = []
        for index, recommendation in enumerate(recommendations, start=1):
            path_steps.append(
                {
                    "step_no": index,
                    "type": recommendation.get("recommendation_type", "resource"),
                    "target_id": recommendation.get("target_id"),
                    "title": recommendation.get("title"),
                    "reason": recommendation.get("reason_text", [""])[0],
                }
            )

        if related_points:
            path_steps.append(
                {
                    "step_no": len(path_steps) + 1,
                    "type": "practice",
                    "target_id": related_points[0]["id"],
                    "title": "完成补强后的验证练习",
                    "reason": "验证薄弱知识点是否得到修正",
                }
            )

        learning_path = {
            "title": "个性化补强学习路径",
            "estimated_minutes": max(30, len(path_steps) * 20),
            "path_steps": path_steps,
            "based_on_profile_fields": [
                key for key, value in profile.items() if value not in (None, [], "unknown")
            ],
            "based_on_knowledge_points": [point["id"] for point in related_points],
            "adjust_reasons": ["薄弱知识点优先", "结合当前可用资源"],
        }

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="已生成步骤化学习路径",
            result={"learning_path": learning_path},
            reason_codes=["learning_path_generated"],
            reason_text=["基于诊断和推荐结果生成路径"],
        )
