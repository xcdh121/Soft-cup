from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class CollectiveInsightAgent(BaseOrchestrationAgent):
    agent_name = AgentName.COLLECTIVE_INSIGHT
    artifact_key = "collective_insight"

    async def run(self, context: AgentRunContext) -> AgentResult:
        knowledge_state = context.artifacts.get("knowledge_state", {})
        weak_points = knowledge_state.get("knowledge_state_summary", {}).get(
            "weak_points", []
        )

        matched_patterns = []
        interventions = []
        for point in weak_points:
            point_id = point.get("knowledge_point_id", "unknown")
            matched_patterns.append(
                {
                    "pattern_code": f"{point_id}_common_misconception",
                    "knowledge_point_id": point_id,
                    "match_score": 0.72,
                }
            )
            interventions.append(
                {
                    "type": "resource",
                    "target_form": "practice_set",
                    "knowledge_point_id": point_id,
                    "evidence_level": "low",
                }
            )

        result = {
            "matched_patterns": matched_patterns,
            "effective_interventions": interventions,
        }

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="已匹配群体错因模式"
            if matched_patterns
            else "未匹配到群体错因模式",
            result=result,
            reason_codes=["collective_pattern_match"]
            if matched_patterns
            else ["collective_pattern_missing"],
            reason_text=["第一版使用稳定 stub，后续接入真实群体错因库"],
        )
