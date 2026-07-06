from collections import defaultdict

from edu_core.schemas.agent_orchestration import (
    AgentEvidence,
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
    Trend,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class KTAgent(BaseOrchestrationAgent):
    agent_name = AgentName.KT
    artifact_key = "knowledge_state"

    async def run(self, context: AgentRunContext) -> AgentResult:
        explicit_states = context.context.knowledge_states
        inferred_from_practice = False
        if explicit_states:
            summary = self._summarize_explicit_states(explicit_states)
            details = {
                state["knowledge_point_id"]: state
                for state in explicit_states
                if state.get("knowledge_point_id")
            }
        else:
            inferred_from_practice = True
            summary, details = self._infer_from_practice_records(
                context.context.practice_records
            )

        result = {
            "knowledge_state_summary": summary,
            "knowledge_state_details": details,
        }
        weak_points = summary["weak_points"]

        if not explicit_states and not context.context.practice_records:
            return AgentResult(
                agent_name=self.agent_name,
                status=RunStatus.COMPLETED,
                summary="Knowledge state evidence is missing.",
                result=result,
                reason_codes=["insufficient_evidence"],
                reason_text=[
                    "No explicit knowledge states or practice records were available."
                ],
                confidence=0.2,
                field_status=FieldStatus.MISSING,
                fallback_used=True,
                fallback_reason="insufficient_evidence",
            )

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary=f"Identified {len(weak_points)} weak knowledge points.",
            result=result,
            reason_codes=["weak_mastery"] if weak_points else ["no_weak_point_found"],
            reason_text=[
                "Weak points were identified from explicit knowledge states or recent practice records."
            ],
            evidences=[
                AgentEvidence(
                    source_type="knowledge_state"
                    if explicit_states
                    else "practice_record",
                    source_id=item["knowledge_point_id"],
                )
                for item in weak_points
            ],
            confidence=0.55 if inferred_from_practice else 0.8,
            field_status=FieldStatus.INFERRED
            if inferred_from_practice
            else FieldStatus.CONFIRMED,
            fallback_used=inferred_from_practice,
            fallback_reason="knowledge_states_partial" if inferred_from_practice else None,
        )

    def _summarize_explicit_states(
        self, states: list[dict]
    ) -> tuple[dict, dict[str, dict]]:
        weak_points = []
        strong_points = []
        scores = []
        for state in states:
            score = int(state.get("mastery_score", 0))
            scores.append(score)
            point = {
                "knowledge_point_id": state.get("knowledge_point_id"),
                "mastery_score": score,
                "trend": state.get("trend", Trend.STABLE.value),
                "status": state.get("status", "struggling" if score < 70 else "ok"),
            }
            if score < 70:
                weak_points.append(point)
            elif score >= 85:
                strong_points.append(point)

        overall = round(sum(scores) / len(scores)) if scores else 0
        return {
            "weak_points": weak_points,
            "strong_points": strong_points,
            "overall_mastery": overall,
        }

    def _infer_from_practice_records(
        self, records: list[dict]
    ) -> tuple[dict, dict[str, dict]]:
        stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
        for record in records:
            topic = record.get("topic") or "general"
            stats[topic]["total"] += 1
            if record.get("was_correct"):
                stats[topic]["correct"] += 1

        weak_points = []
        strong_points = []
        details = {}
        scores = []
        for topic, topic_stats in stats.items():
            total = topic_stats["total"]
            correct = topic_stats["correct"]
            score = round((correct / total) * 100) if total else 0
            scores.append(score)
            point_id = self._topic_to_point_id(topic)
            point = {
                "knowledge_point_id": point_id,
                "mastery_score": score,
                "trend": Trend.DOWN.value if score < 70 else Trend.STABLE.value,
                "status": "struggling" if score < 70 else "ok",
            }
            details[point_id] = {
                "mastery_score": score,
                "confidence": min(0.95, round(0.5 + total * 0.08, 2)),
                "trend": point["trend"],
                "attempt_count": total,
                "correct_count": correct,
                "topic": topic,
            }
            if score < 70:
                weak_points.append(point)
            elif score >= 85:
                strong_points.append(point)

        overall = round(sum(scores) / len(scores)) if scores else 0
        return {
            "weak_points": weak_points,
            "strong_points": strong_points,
            "overall_mastery": overall,
        }, details

    def _topic_to_point_id(self, topic: str) -> str:
        normalized = "".join(
            char.lower() if char.isalnum() else "_" for char in topic.strip()
        ).strip("_")
        return f"kp_{normalized or 'general'}"
