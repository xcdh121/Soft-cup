from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class CollectiveInsightAgent(BaseOrchestrationAgent):
    agent_name = AgentName.COLLECTIVE_INSIGHT
    artifact_key = "collective_insight"

    async def run(self, context: AgentRunContext) -> AgentResult:
        if context.context.collective_insights:
            result = self._from_context_insights(context.context.collective_insights)
            matched_patterns = result["matched_patterns"]
            return AgentResult(
                agent_name=self.agent_name,
                status=RunStatus.COMPLETED,
                summary=f"Matched {len(matched_patterns)} collective insight patterns.",
                result=result,
                reason_codes=["collective_pattern_match"]
                if matched_patterns
                else ["collective_pattern_missing"],
                reason_text=[
                    "Collective insight evidence was loaded from shared context."
                ],
                confidence=0.75 if matched_patterns else 0.5,
                field_status=FieldStatus.CONFIRMED,
            )

        result = self._stub_from_weak_points(context)
        matched_patterns = result["matched_patterns"]
        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="Collective insight data is unavailable; used low-evidence stub patterns.",
            result=result,
            reason_codes=["collective_insight_unavailable"],
            reason_text=[
                "No collective insight store was available, so generated stable low-evidence patterns from weak points."
            ],
            confidence=0.4 if matched_patterns else 0.2,
            field_status=FieldStatus.INFERRED if matched_patterns else FieldStatus.MISSING,
            fallback_used=True,
            fallback_reason="collective_insight_unavailable",
        )

    def _from_context_insights(self, insights: list[dict]) -> dict:
        matched_patterns = []
        interventions = []
        for insight in insights:
            matched_patterns.append(
                {
                    "pattern_code": insight.get("pattern_code", "collective_pattern"),
                    "knowledge_point_id": insight.get("knowledge_point_id"),
                    "match_score": insight.get("match_score", 0.7),
                }
            )
            if insight.get("intervention"):
                interventions.append(insight["intervention"])
        return {
            "matched_patterns": matched_patterns,
            "effective_interventions": interventions,
        }

    def _stub_from_weak_points(self, context: AgentRunContext) -> dict:
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
                    "match_score": 0.55,
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

        return {
            "matched_patterns": matched_patterns,
            "effective_interventions": interventions,
        }
