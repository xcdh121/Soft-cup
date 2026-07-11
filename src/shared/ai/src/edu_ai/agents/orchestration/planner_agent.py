import json
import logging

from edu_core.model_providers import LlmProviderConfig, create_chat_model
from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)
from edu_core.schemas.learning_path_generation import LearningPathContent
from edu_core.schemas.internal_tools import ToolExecutionContext

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.agents.utils import generate
from edu_ai.internal_tools import ToolRunner, build_context_tool_registry
from edu_ai.skills import SkillRunner, build_skill_registry

logger = logging.getLogger(__name__)


class PlannerAgent(BaseOrchestrationAgent):
    agent_name = AgentName.PLANNER
    artifact_key = "learning_path"

    def __init__(self, llm_config: LlmProviderConfig | None = None) -> None:
        self.llm = (
            create_chat_model(llm_config, streaming=False, temperature=0.3)
            if llm_config and llm_config.model
            else None
        )

    async def run(self, context: AgentRunContext) -> AgentResult:
        tool_runner = ToolRunner(
            build_context_tool_registry(context.context),
            permission_checker=lambda tool_context: (
                tool_context.user_id == context.student_id
                and tool_context.project_id == context.project_id
            ),
        )
        skill_execution = await SkillRunner(
            build_skill_registry(), tool_runner
        ).execute_plan(
            "learning_path_design",
            ToolExecutionContext(
                run_id=context.run_id,
                request_id=f"req_{context.run_id}",
                user_id=context.student_id,
                project_id=context.project_id,
                agent_name=self.agent_name,
                skill_id="learning_path_design",
                user_roles=list(context.meta.get("user_roles", ["learner"])),
                locale=str(context.meta.get("locale", "zh-CN")),
            ),
            [
                ("get_knowledge_states", {"limit": 50}),
                ("get_knowledge_graph", {}),
                ("get_learner_profile", {}),
            ],
        )
        learning_path = self._build_rule_learning_path(context)
        generation_mode = "rule"

        if self.llm:
            try:
                learning_path = await self._build_llm_learning_path(context)
                generation_mode = "llm"
            except Exception:
                logger.exception(
                    "LLM learning path generation failed for project %s, falling back to rule planner.",
                    context.project_id,
                )
                generation_mode = "rule_fallback"

        learning_path = self._apply_quality_gates(learning_path)
        skill_execution.confidence = 0.8 if generation_mode == "llm" else 0.6
        skill_execution.fallback_used = (
            skill_execution.status == "failed"
            or generation_mode in {"rule", "rule_fallback"}
        )
        skill_execution.fallback_reason = (
            skill_execution.fallback_reason
            or (
                "planner_rule_fallback"
                if generation_mode in {"rule", "rule_fallback"}
                else None
            )
        )
        skill_execution.output_artifact_key = self.artifact_key

        reason_codes = ["learning_path_generated", generation_mode]
        reason_text = [
            "Generated from diagnosis, recommendations, and learner context."
        ]
        if generation_mode == "llm":
            reason_text.append(
                "LLM organized the final sequence while keeping the output schema constrained."
            )
        elif generation_mode == "rule_fallback":
            reason_text.append(
                "LLM generation was unavailable, so the rule-based planner was used."
            )

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="Generated a structured learning path.",
            result={"learning_path": learning_path},
            reason_codes=reason_codes,
            reason_text=reason_text,
            confidence=0.8 if generation_mode == "llm" else 0.6,
            field_status=FieldStatus.CONFIRMED
            if generation_mode == "llm"
            else FieldStatus.INFERRED,
            fallback_used=generation_mode in {"rule", "rule_fallback"},
            fallback_reason="planner_rule_fallback"
            if generation_mode in {"rule", "rule_fallback"}
            else None,
            skill_executions=[skill_execution],
            tool_call_ids=[item.id for item in skill_execution.tool_calls],
            input_artifact_keys=["profile", "knowledge_state", "diagnosis", "recommendations"],
            output_artifact_keys=[self.artifact_key],
            tool_call_audits=tool_runner.audits,
        )

    @staticmethod
    def _apply_quality_gates(learning_path: dict) -> dict:
        path = dict(learning_path)
        steps = []
        for index, raw_step in enumerate(path.get("path_steps", []), start=1):
            step = dict(raw_step)
            step["step_no"] = index
            step.setdefault("objective", step.get("title", "完成本步骤学习目标"))
            step.setdefault("acceptance_condition", "完成对应练习并达到 80% 正确率。")
            steps.append(step)
        path["path_steps"] = steps
        return path

    def _build_rule_learning_path(self, context: AgentRunContext) -> dict:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        recommendations = context.artifacts.get("recommendations", {}).get(
            "recommendations", []
        )
        profile = context.artifacts.get("profile", {}).get("profile_summary", {})
        related_points = diagnosis.get("related_knowledge_points", [])

        path_steps = []
        for index, recommendation in enumerate(recommendations, start=1):
            reason_text = recommendation.get("reason_text", [])
            primary_reason = reason_text[0] if reason_text else "Recommended next step."
            path_steps.append(
                {
                    "step_no": index,
                    "type": recommendation.get("recommendation_type", "resource"),
                    "target_id": recommendation.get("target_id"),
                    "title": recommendation.get("title") or f"Step {index}",
                    "reason": primary_reason,
                }
            )

        if related_points:
            first_point_id = related_points[0].get("id")
            path_steps.append(
                {
                    "step_no": len(path_steps) + 1,
                    "type": "practice",
                    "target_id": first_point_id,
                    "title": "Practice to verify improvement",
                    "reason": "Use targeted practice to confirm the weak point is improving.",
                }
            )

        return {
            "title": "Personalized reinforcement path",
            "estimated_minutes": max(30, len(path_steps) * 20),
            "path_steps": path_steps,
            "based_on_profile_fields": [
                key
                for key, value in profile.items()
                if value not in (None, [], "unknown")
            ],
            "based_on_knowledge_points": [
                point.get("id") for point in related_points if point.get("id")
            ],
            "adjust_reasons": [
                "Prioritize the weakest knowledge points first.",
                "Sequence available recommendations into an actionable plan.",
            ],
        }

    async def _build_llm_learning_path(self, context: AgentRunContext) -> dict:
        diagnosis = context.artifacts.get("diagnosis", {}).get("diagnosis", {})
        recommendations = context.artifacts.get("recommendations", {}).get(
            "recommendations", []
        )
        profile = context.artifacts.get("profile", {}).get("profile_summary", {})
        knowledge_state = context.artifacts.get("knowledge_state", {})
        course = context.context.course or {}
        weak_points = knowledge_state.get("knowledge_state_summary", {}).get(
            "weak_points", []
        )

        document_content = json.dumps(
            {
                "course": {
                    "id": course.get("id"),
                    "name": course.get("name"),
                    "description": course.get("description"),
                },
                "diagnosis": diagnosis,
                "recommendations": recommendations,
                "profile_summary": profile,
                "weak_points": weak_points,
            },
            ensure_ascii=True,
            indent=2,
        )

        plan_data = await generate(
            llm=self.llm,
            search_service=None,
            output_model=LearningPathContent,
            prompt_template="learning_path",
            project_id=context.project_id,
            topic="Learning Path",
            language_code=course.get("language_code") or "en",
            custom_instructions=(
                "Start with understanding-oriented steps when helpful, then practice, "
                "then include a verification step. Reuse recommendation ids and titles when possible."
            ),
            document_content=document_content,
        )
        return plan_data.model_dump()
