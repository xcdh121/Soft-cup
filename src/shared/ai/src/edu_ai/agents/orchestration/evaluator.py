from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from .base import BaseOrchestrationAgent


class Evaluator(BaseOrchestrationAgent):
    agent_name = AgentName.EVALUATOR
    artifact_key = "evaluation"

    async def run(self, context: AgentRunContext) -> AgentResult:
        path = context.artifacts.get("learning_path", {}).get("learning_path") or {}
        steps = path.get("path_steps") or path.get("steps") or []
        recommendations = context.artifacts.get("recommendations", {}).get(
            "recommendations", []
        )
        known_resources = {
            str(item.get("target_id"))
            for item in recommendations
            if item.get("target_id")
        } | {
            str(item.get("id"))
            for item in context.context.generated_resources
            if item.get("id")
        }
        missing_resources = []
        total_minutes = 0
        for step in steps:
            resource_id = step.get("resource_id") or step.get("target_id")
            if resource_id and str(resource_id) not in known_resources:
                missing_resources.append(str(resource_id))
            total_minutes += int(
                step.get("estimated_minutes") or step.get("duration_minutes") or 0
            )
        budget_minutes = int(context.meta.get("time_budget_minutes") or 0)
        checks = {
            "resource_ids_valid": not missing_resources,
            "positive_duration": all(
                int(step.get("estimated_minutes") or step.get("duration_minutes") or 0) > 0
                for step in steps
            ) if steps else False,
            "within_time_budget": not budget_minutes or total_minutes <= budget_minutes,
        }
        passed = all(checks.values())
        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="Learning artifacts passed quality evaluation."
            if passed
            else "Learning artifacts require targeted rework.",
            result={
                "passed": passed,
                "checks": checks,
                "missing_resource_ids": missing_resources,
                "rework_nodes": ["PlannerAgent"] if not passed else [],
                "max_rework_count": 1,
            },
            reason_codes=["quality_gate_passed" if passed else "quality_gate_failed"],
            confidence=1.0,
            field_status=FieldStatus.CONFIRMED,
            input_artifact_keys=["learning_path", "recommendations"],
            output_artifact_keys=[self.artifact_key],
        )
