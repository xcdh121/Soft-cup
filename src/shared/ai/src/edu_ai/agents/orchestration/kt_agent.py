from collections import defaultdict

from edu_core.schemas.agent_orchestration import (
    AgentEvidence,
    AgentName,
    AgentResult,
    AgentRunContext,
    RunStatus,
    Trend,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class KTAgent(BaseOrchestrationAgent):
    agent_name = AgentName.KT
    artifact_key = "knowledge_state"

    async def run(self, context: AgentRunContext) -> AgentResult:
        explicit_states = context.context.knowledge_states
        if explicit_states:
            summary = self._summarize_explicit_states(explicit_states)
            details = {
                state["knowledge_point_id"]: state
                for state in explicit_states
                if state.get("knowledge_point_id")
            }
        else:
            summary, details = self._infer_from_practice_records(
                context.context.practice_records
            )

        result = {
            "knowledge_state_summary": summary,
            "knowledge_state_details": details,
        }
        weak_points = summary["weak_points"]

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary=f"已识别 {len(weak_points)} 个薄弱知识点",
            result=result,
            reason_codes=["weak_mastery"] if weak_points else ["no_weak_point_found"],
            reason_text=["根据知识状态或练习记录识别薄弱点"],
            evidences=[
                AgentEvidence(
                    source_type="knowledge_state",
                    source_id=item["knowledge_point_id"],
                )
                for item in weak_points
            ],
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
