from datetime import datetime, timezone

from edu_core.schemas.agent_orchestration import (
    AgentEvidence,
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.internal_tools import ToolRunner, build_context_tool_registry
from edu_ai.skills import SkillRunner, build_skill_registry
from edu_core.schemas.internal_tools import ToolExecutionContext


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

        primary_id = None
        primary_topic = None
        if weak_points:
            primary_id = str(weak_points[0].get("knowledge_point_id"))
            primary_topic = str(details.get(primary_id, {}).get("topic", primary_id))
        elif context.context.knowledge_states:
            state = min(
                context.context.knowledge_states,
                key=lambda item: float(item.get("mastery_score", 0)),
            )
            primary_id = str(state.get("knowledge_point_id", state.get("id", "")))
            primary_topic = str(state.get("topic", state.get("name", primary_id)))

        tool_runner = ToolRunner(
            build_context_tool_registry(context.context),
            permission_checker=lambda tool_context: (
                tool_context.user_id == context.student_id
                and tool_context.project_id == context.project_id
            ),
        )
        skill_runner = SkillRunner(build_skill_registry(), tool_runner)
        calls = [
            ("get_knowledge_states", {"knowledge_point_ids": [primary_id] if primary_id else [], "limit": 50}),
            ("get_recent_practice_records", {"knowledge_point_ids": [primary_id] if primary_id else [], "limit": 20}),
            ("get_knowledge_graph", {"knowledge_point_ids": [primary_id] if primary_id else []}),
        ]
        if primary_topic and context.context.documents:
            calls.append(("search_course_materials", {"query": primary_topic, "limit": 5}))
        skill_execution = await skill_runner.execute_plan(
            "root_cause_diagnosis",
            ToolExecutionContext(
                run_id=context.run_id,
                request_id=f"req_{context.run_id}",
                user_id=context.student_id,
                project_id=context.project_id,
                agent_name=self.agent_name,
                skill_id="root_cause_diagnosis",
                user_roles=list(context.meta.get("user_roles", ["learner"])),
                locale=str(context.meta.get("locale", "zh-CN")),
            ),
            calls,
        )
        tool_evidences = [evidence for audit in tool_runner.audits for evidence in audit.evidence_refs]

        if weak_points:
            primary = weak_points[0]
            point_id = primary["knowledge_point_id"]
            detail = details.get(point_id, {})
            evidence_confidence = float(detail.get("confidence", 0.65))
            confidence = min(0.85, evidence_confidence)
            if not matched_patterns:
                confidence = min(confidence, 0.65)

            prerequisite_relations = []
            for point in context.context.knowledge_points:
                if point.get("id") == point_id:
                    prerequisite_relations = (
                        point.get("prerequisite_relations", []) or []
                    )
                    if not prerequisite_relations:
                        prerequisite_relations = [
                            {
                                "id": None,
                                "source_knowledge_point_id": prerequisite_id,
                                "strength": 1.0,
                            }
                            for prerequisite_id in (
                                point.get("prerequisite_ids", []) or []
                            )
                        ]
                    break
            state_by_id = {
                str(item.get("knowledge_point_id")): item
                for item in context.context.knowledge_states
            }
            prerequisite_causes = []
            for relation in prerequisite_relations:
                prerequisite_id = str(
                    relation.get("source_knowledge_point_id", "")
                )
                prerequisite_state = state_by_id.get(str(prerequisite_id), {})
                mastery = float(prerequisite_state.get("mastery_score", 0)) / 100
                evidence = float(prerequisite_state.get("confidence", 0.4))
                strength = float(relation.get("strength", 1.0))
                freshness = self._freshness_factor(
                    prerequisite_state.get("last_practiced_at")
                )
                cause_score = (
                    (1 - mastery) * strength * evidence * freshness
                )
                if mastery < 0.70:
                    prerequisite_causes.append(
                        {
                            "type": "weak_prerequisite",
                            "knowledge_point_id": prerequisite_id,
                            "relation_id": relation.get("id"),
                            "confidence": round(min(0.85, cause_score), 3),
                            "reason_text": (
                                f"先修知识点 {prerequisite_id} 当前掌握度为"
                                f"{mastery:.0%}，关系强度为{strength:.0%}，"
                                "可能影响当前知识点。"
                            ),
                        }
                    )
            prerequisite_causes.sort(
                key=lambda item: item["confidence"], reverse=True
            )
            root_causes = [
                *prerequisite_causes[:2],
                {
                    "type": "weak_mastery",
                    "knowledge_point_id": point_id,
                    "label": "Insufficient mastery of the knowledge point",
                    "confidence": confidence,
                    "reason_text": "近期练习证据显示当前知识点掌握不足。",
                },
            ][:3]
            diagnosis = {
                "summary": (
                    "The current primary weak point is "
                    f"{detail.get('topic', point_id)}. Prioritize concept repair and practice feedback."
                ),
                "root_causes": root_causes,
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
                "evidences": [
                    {
                        "source_type": "knowledge_state",
                        "source_id": point_id,
                        "knowledge_point_id": point_id,
                        "contribution_score": confidence,
                    }
                ],
            }
            reason_codes = ["weak_mastery"]
            evidences = list({(item.source_type, item.source_id): item for item in [
                AgentEvidence(source_type="knowledge_state", source_id=point_id),
                *tool_evidences,
            ]}.values())
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

        if skill_execution.status == "failed":
            fallback_used = True
            fallback_reason = skill_execution.fallback_reason or "tool_skill_failed"
            confidence = min(confidence, 0.65)
        skill_execution.confidence = confidence
        skill_execution.fallback_used = fallback_used
        skill_execution.fallback_reason = fallback_reason
        skill_execution.output_artifact_key = self.artifact_key

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
            skill_executions=[skill_execution],
            tool_call_ids=[item.id for item in skill_execution.tool_calls],
            input_artifact_keys=["knowledge_state", "collective_insight"],
            output_artifact_keys=[self.artifact_key],
            tool_call_audits=tool_runner.audits,
        )

    @staticmethod
    def _freshness_factor(last_practiced_at: object) -> float:
        if not last_practiced_at:
            return 0.5
        try:
            practiced = datetime.fromisoformat(str(last_practiced_at))
            if practiced.tzinfo is None:
                practiced = practiced.replace(tzinfo=timezone.utc)
            age_days = max(
                0.0,
                (datetime.now(timezone.utc) - practiced).total_seconds()
                / 86400.0,
            )
            return 1 / (1 + age_days / 30)
        except ValueError:
            return 0.5

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
