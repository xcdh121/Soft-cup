import unittest

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.agents.orchestration.executor import OrchestrationExecutor
from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    ExecutionPlan,
    PlanNode,
    RetryClass,
    RetryPolicy,
    RunStatus,
)


class StubAgent(BaseOrchestrationAgent):
    artifact_key = "stub"

    def __init__(self, name, failures=0):
        self.agent_name = name
        self.failures = failures
        self.calls = 0

    async def run(self, context):
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("transient")
        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="done",
        )


class ExecutorV2Tests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        return AgentRunContext(
            run_id="run-test",
            project_id="project-test",
            student_id="student-test",
        )

    async def test_transient_failure_retries(self):
        agent = StubAgent(AgentName.PROFILE, failures=1)
        plan = ExecutionPlan(
            nodes=[
                PlanNode(
                    node_id="profile",
                    agent_name=AgentName.PROFILE,
                    retry_policy=RetryPolicy(
                        max_attempts=2,
                        retry_class=RetryClass.TRANSIENT,
                        initial_delay_seconds=0,
                    ),
                )
            ]
        )
        outcome = await OrchestrationExecutor().execute(
            plan, self.context(), {AgentName.PROFILE: agent}
        )
        self.assertEqual(RunStatus.COMPLETED, outcome.status)
        self.assertEqual(2, agent.calls)

    async def test_optional_failure_is_partial_and_keeps_other_results(self):
        good = StubAgent(AgentName.PROFILE)
        failing = StubAgent(AgentName.MEDIA, failures=1)
        plan = ExecutionPlan(
            nodes=[
                PlanNode(node_id="profile", agent_name=AgentName.PROFILE),
                PlanNode(
                    node_id="media",
                    agent_name=AgentName.MEDIA,
                    optional=True,
                ),
            ]
        )
        outcome = await OrchestrationExecutor().execute(
            plan,
            self.context(),
            {AgentName.PROFILE: good, AgentName.MEDIA: failing},
        )
        self.assertEqual(RunStatus.PARTIALLY_COMPLETED, outcome.status)
        self.assertIn("profile", outcome.results)
        self.assertIn("media", outcome.errors)

    async def test_cancellation_stops_before_next_boundary(self):
        agent = StubAgent(AgentName.PROFILE)
        outcome = await OrchestrationExecutor().execute(
            ExecutionPlan(
                nodes=[PlanNode(node_id="profile", agent_name=AgentName.PROFILE)]
            ),
            self.context(),
            {AgentName.PROFILE: agent},
            cancellation_check=lambda: True,
        )
        self.assertEqual(RunStatus.CANCELLED, outcome.status)
        self.assertEqual(0, agent.calls)


if __name__ == "__main__":
    unittest.main()
