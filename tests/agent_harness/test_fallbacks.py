import unittest

from edu_ai.agents.orchestration.planner_agent import PlannerAgent
from edu_ai.agents.orchestration.resource_agent import ResourceAgent
from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEventType,
    AgentRunContext,
    OrchestrationRunRequest,
)


class FallbackRulesTest(unittest.IsolatedAsyncioTestCase):
    async def test_diagnosis_with_no_evidence_stays_low_confidence(self):
        result = await SupervisorAgent().run(
            OrchestrationRunRequest(
                project_id="project_1",
                student_id="student_1",
                goal="diagnosis",
                context=AgentContextData(),
            )
        )

        diagnosis_result = next(
            item for item in result.agent_results if item.agent_name == "DiagnosisAgent"
        )

        self.assertEqual(diagnosis_result.fallback_reason, "insufficient_evidence")
        self.assertLessEqual(diagnosis_result.confidence, 0.2)
        self.assertEqual(
            result.final_result["diagnosis"]["root_causes"],
            [],
        )

    async def test_resource_generation_unavailable_uses_existing_resource_fallback(self):
        context = AgentRunContext(
            run_id="run_resource",
            project_id="project_1",
            student_id="student_1",
            goal="recommendations",
            context=AgentContextData(
                generated_resources=[
                    {
                        "id": "resource_1",
                        "title": "Existing explanation",
                        "resource_type": "note",
                    }
                ]
            ),
            artifacts={
                "diagnosis": {
                    "diagnosis": {
                        "related_knowledge_points": [{"id": "kp_gradient"}]
                    }
                }
            },
        )

        result = await ResourceAgent().run(context)

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.fallback_reason, "resource_generation_unavailable")
        self.assertEqual(
            result.result["recommendations"][0]["recommendation_mode"],
            "fallback",
        )

    async def test_planner_without_llm_uses_rule_fallback(self):
        context = AgentRunContext(
            run_id="run_planner",
            project_id="project_1",
            student_id="student_1",
            goal="learning_path",
            artifacts={
                "diagnosis": {
                    "diagnosis": {
                        "related_knowledge_points": [{"id": "kp_gradient"}]
                    }
                },
                "recommendations": {
                    "recommendations": [
                        {
                            "recommendation_type": "note",
                            "target_id": "resource_1",
                            "title": "Existing explanation",
                            "reason_text": ["Weak point support"],
                        }
                    ]
                },
            },
        )

        result = await PlannerAgent().run(context)

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.fallback_reason, "planner_rule_fallback")

    async def test_fallback_event_is_recorded(self):
        result = await SupervisorAgent().run(
            OrchestrationRunRequest(
                project_id="project_1",
                student_id="student_1",
                goal="diagnosis",
                context=AgentContextData(),
            )
        )

        event_types = [event.event_type for event in result.events]

        self.assertIn(AgentEventType.FALLBACK_APPLIED, event_types)
