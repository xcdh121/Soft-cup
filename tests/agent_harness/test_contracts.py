import unittest

from edu_ai.agents.orchestration.diagnosis_agent import DiagnosisAgent
from edu_ai.agents.orchestration.kt_agent import KTAgent
from edu_ai.agents.orchestration.profile_agent import ProfileAgent
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentRunContext,
    FieldStatus,
)


class AgentContractTest(unittest.IsolatedAsyncioTestCase):
    def _context(self) -> AgentRunContext:
        return AgentRunContext(
            run_id="run_contract",
            project_id="project_1",
            student_id="student_1",
            context=AgentContextData(
                learner_profile={"profile_data": {"learning_style": "visual"}},
                practice_records=[
                    {"id": "p1", "topic": "gradient", "was_correct": False},
                    {"id": "p2", "topic": "gradient", "was_correct": True},
                ],
            ),
        )

    async def test_agent_results_include_mvp_contract_fields(self):
        context = self._context()
        profile = await ProfileAgent().run(context)
        kt = await KTAgent().run(context)
        context.artifacts["knowledge_state"] = kt.result
        diagnosis = await DiagnosisAgent().run(context)

        for result in (profile, kt, diagnosis):
            self.assertGreaterEqual(result.confidence, 0)
            self.assertLessEqual(result.confidence, 1)
            self.assertIn(
                result.field_status,
                {
                    FieldStatus.CONFIRMED,
                    FieldStatus.INFERRED,
                    FieldStatus.MISSING,
                },
            )
            if result.fallback_used:
                self.assertIsNotNone(result.fallback_reason)
