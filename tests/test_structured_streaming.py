import unittest
from types import SimpleNamespace

from pydantic import BaseModel

from edu_ai.agents.utils import generate_stream
from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    OrchestrationRunRequest,
    RunStatus,
)


class _Output(BaseModel):
    title: str
    content: str


class _SearchService:
    async def search_documents(self, **_kwargs):
        return []


class _StreamingLlm:
    async def astream(self, _prompt):
        for content in (
            '{"title":"Transactions","content":"# Atomicity',
            '\\n\\nA transaction',
            ' is all-or-nothing."}',
        ):
            yield SimpleNamespace(content=content)


class _Agent(BaseOrchestrationAgent):
    agent_name = AgentName.PROFILE
    artifact_key = "profile"

    async def run(self, _context):
        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="Profile ready.",
            result={"profile": {}},
        )


class StructuredStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_json_is_exposed_before_the_final_document(self):
        updates = []
        async for update in generate_stream(
            llm=_StreamingLlm(),
            search_service=_SearchService(),
            output_model=_Output,
            prompt_template="note_prompt",
            project_id="project-1",
            topic="transactions",
            language_code="en",
        ):
            updates.append(update)

        self.assertGreaterEqual(len(updates), 2)
        self.assertEqual(
            updates[-1],
            {
                "title": "Transactions",
                "content": "# Atomicity\n\nA transaction is all-or-nothing.",
            },
        )

    async def test_supervisor_publishes_agent_start_and_completion(self):
        events = []
        supervisor = SupervisorAgent(agents=[_Agent()])

        async def collect(event):
            events.append(event)

        await supervisor.run(
            OrchestrationRunRequest(
                project_id="project-1",
                student_id="user-1",
            ),
            event_sink=collect,
        )

        profile_events = [event for event in events if event.agent_name == AgentName.PROFILE]
        self.assertEqual(profile_events[0].status, RunStatus.RUNNING)
        self.assertEqual(profile_events[0].payload["phase"], "started")
        self.assertEqual(profile_events[1].status, RunStatus.COMPLETED)
        self.assertEqual(profile_events[1].payload["phase"], "completed")


if __name__ == "__main__":
    unittest.main()
