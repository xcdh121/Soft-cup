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
