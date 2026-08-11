import unittest

from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEventType,
    OrchestrationRunRequest,
)


class TraceTest(unittest.IsolatedAsyncioTestCase):
    async def test_trace_contains_mvp_events(self):
        result = await SupervisorAgent().run(
            OrchestrationRunRequest(
                project_id="project_1",
                student_id="student_1",
                goal="diagnosis",
                context=AgentContextData(
                    practice_records=[
                        {"id": "p1", "topic": "gradient", "was_correct": False}
                    ]
                ),
            )
        )

        event_types = [event.event_type for event in result.events]

        self.assertIn(AgentEventType.RUN_STARTED, event_types)
        self.assertIn(AgentEventType.ROUTE_DECIDED, event_types)
        self.assertIn(AgentEventType.AGENT_SKIPPED, event_types)
        self.assertIn(AgentEventType.FALLBACK_APPLIED, event_types)
        self.assertIn(AgentEventType.RUN_COMPLETED, event_types)

    async def test_learning_path_trace_exposes_generated_recommendations(self):
        result = await SupervisorAgent().run(
            OrchestrationRunRequest(
                project_id="project_1",
                student_id="student_1",
                goal="learning_path",
                context=AgentContextData(
                    knowledge_points=[
                        {"id": "kp_1", "name": "Greedy algorithm"}
                    ],
                    knowledge_states=[
                        {
                            "knowledge_point_id": "kp_1",
                            "topic": "Greedy algorithm",
                            "mastery_score": 0.35,
                            "confidence": 0.8,
                        }
                    ],
                ),
            )
        )

        recommendation_events = [
            event
            for event in result.events
            if event.event_type == AgentEventType.ARTIFACT_UPDATED
            and event.payload.get("artifact_key") == "recommendations"
        ]

        self.assertEqual(len(recommendation_events), 1)
        self.assertGreater(
            len(recommendation_events[0].payload.get("recommendations", [])), 0
        )
        self.assertGreater(len(result.final_result["recommendations"]), 0)
