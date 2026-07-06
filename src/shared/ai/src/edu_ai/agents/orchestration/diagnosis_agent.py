from edu_core.schemas.agent_orchestration import (
    AgentEvidence,
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class DiagnosisAgent(BaseOrchestrationAgent):
    agent_name = AgentName.DIAGNOSIS
    artifact_key = "diagnosis"

    async def run(self, context: AgentRunContext) -> AgentResult:
        knowledge_state = context.artifacts.get("knowledge_state", {})
        collective = context.artifacts.get("collective_insight", {})
        weak_points = knowledge_state.get("knowledge_state_summary", {}).get(
            "weak_points", []
        )
        details = knowledge_state.get("knowledge_state_details", {})
        matched_patterns = collective.get("matched_patterns", [])

        if weak_points:
            primary = weak_points[0]
            point_id = primary["knowledge_point_id"]
            detail = details.get(point_id, {})
            evidence_confidence = float(detail.get("confidence", 0.65))
            confidence = min(0.85, evidence_confidence)
            if not matched_patterns:
                confidence = min(confidence, 0.65)

            diagnosis = {
                "summary": (
                    "The current primary weak point is "
                    f"{detail.get('topic', point_id)}. Prioritize concept repair and practice feedback."
                ),
                "root_causes": [
                    {
                        "type": "weak_mastery",
                        "label": "Insufficient mastery of the knowledge point",
                        "confidence": confidence,
                    }
                ],
                "related_knowledge_points": [
                    {
                        "id": point["knowledge_point_id"],
                        "mastery": round(point["mastery_score"] / 100, 2),
                    }
                    for point in weak_points
                ],
                "collective_support": matched_patterns[0] if matched_patterns else None,
                "explanation": self._build_explanation(
                    primary, detail, matched_patterns
                ),
            }
            reason_codes = ["weak_mastery"]
            evidences = [
                AgentEvidence(source_type="knowledge_state", source_id=point_id)
            ]
            fallback_used = not bool(matched_patterns)
            fallback_reason = (
                "collective_insight_unavailable" if fallback_used else None
            )
            field_status = FieldStatus.INFERRED
        else:
            diagnosis = {
                "summary": (
                    "There is not enough evidence to produce a strong diagnosis. "
                    "Continue practice to collect more evidence."
                ),
                "root_causes": [],
                "related_knowledge_points": [],
                "collective_support": None,
                "explanation": [
                    "No weak knowledge point could be confirmed from knowledge states or practice records."
                ],
            }
            reason_codes = ["insufficient_evidence"]
            evidences = []
            confidence = 0.2
            fallback_used = True
            fallback_reason = "insufficient_evidence"
            field_status = FieldStatus.MISSING

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="Generated root-cause diagnosis.",
            result={"diagnosis": diagnosis},
            reason_codes=reason_codes,
            reason_text=diagnosis["explanation"],
            evidences=evidences,
            next_actions=["generate_recommendations", "generate_learning_path"]
            if evidences
            else [],
            confidence=confidence,
            field_status=field_status,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

    def _build_explanation(
        self, primary: dict, detail: dict, matched_patterns: list[dict]
    ) -> list[str]:
        explanation = [
            f"Mastery score is {primary['mastery_score']}, below the reinforcement threshold."
        ]
        if detail:
            explanation.append(
                "Recent practice evidence: "
                f"{detail.get('attempt_count', 0)} attempts, {detail.get('correct_count', 0)} correct."
            )
        if matched_patterns:
            explanation.append("A collective misconception pattern also supports this diagnosis.")
        return explanation
