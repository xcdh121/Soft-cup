from edu_core.schemas.agent_orchestration import (
    AgentEvidence,
    AgentName,
    AgentResult,
    AgentRunContext,
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
            diagnosis = {
                "summary": f"学生当前主要薄弱点是 {detail.get('topic', point_id)}，需要优先补强概念理解和练习反馈",
                "root_causes": [
                    {
                        "type": "weak_mastery",
                        "label": "知识点掌握度不足",
                        "confidence": detail.get("confidence", 0.7),
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
                "explanation": self._build_explanation(primary, detail, matched_patterns),
            }
            reason_codes = ["weak_mastery"]
            evidences = [
                AgentEvidence(source_type="knowledge_state", source_id=point_id)
            ]
        else:
            diagnosis = {
                "summary": "暂未发现明显薄弱知识点，建议继续完成练习以积累诊断证据",
                "root_causes": [],
                "related_knowledge_points": [],
                "collective_support": None,
                "explanation": ["当前练习记录或知识状态不足，诊断结果为低置信度"],
            }
            reason_codes = ["insufficient_evidence"]
            evidences = []

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="已生成根因诊断",
            result={"diagnosis": diagnosis},
            reason_codes=reason_codes,
            reason_text=diagnosis["explanation"],
            evidences=evidences,
            next_actions=["generate_recommendations", "generate_learning_path"],
        )

    def _build_explanation(
        self, primary: dict, detail: dict, matched_patterns: list[dict]
    ) -> list[str]:
        explanation = [
            f"相关知识点掌握度为 {primary['mastery_score']}，低于补强阈值",
        ]
        if detail:
            explanation.append(
                f"累计练习 {detail.get('attempt_count', 0)} 次，答对 {detail.get('correct_count', 0)} 次"
            )
        if matched_patterns:
            explanation.append("与群体常见错因模式存在匹配")
        return explanation
