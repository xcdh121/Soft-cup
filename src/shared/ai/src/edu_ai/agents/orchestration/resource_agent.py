from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class ResourceAgent(BaseOrchestrationAgent):
    agent_name = AgentName.RESOURCE
    artifact_key = "recommendations"

    async def run(self, context: AgentRunContext) -> AgentResult:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        related_points = diagnosis.get("related_knowledge_points", [])
        resources = context.context.generated_resources
        recommendations = []

        for index, resource in enumerate(resources[:5], start=1):
            recommendations.append(
                {
                    "id": f"{context.run_id}_rec_{index:03d}",
                    "recommendation_type": "resource",
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
                    "score": round(0.9 - (index - 1) * 0.05, 2),
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

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary=f"已生成 {len(recommendations)} 条推荐",
            result={"recommendations": recommendations},
            reason_codes=["resource_recommendation_generated"],
            reason_text=["基于诊断结果和项目资源生成推荐"],
        )
