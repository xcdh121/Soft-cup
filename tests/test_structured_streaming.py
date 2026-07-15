import unittest
from types import SimpleNamespace
from unittest.mock import patch

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_ai.agents.quiz_agent import QuizAgent
from edu_ai.agents.utils import generate_stream
from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    OrchestrationRunRequest,
    RunStatus,
)
from edu_db.models import Base, Project, Quiz, QuizQuestion, User
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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
    async def test_quiz_agent_emits_each_stable_question_before_completion(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as db:
            db.add_all(
                [
                    User(
                        id="user-quiz-stream",
                        username="quiz-stream",
                        name="Quiz Stream",
                        email="quiz-stream@example.com",
                    ),
                    Project(
                        id="project-quiz-stream",
                        owner_id="user-quiz-stream",
                        name="Streaming project",
                        language_code="en",
                    ),
                    Quiz(
                        id="quiz-stream",
                        project_id="project-quiz-stream",
                        name="Pending quiz",
                    ),
                ]
            )
            db.commit()

        first = {
            "question_text": "What is a list?",
            "option_a": "A linear collection",
            "option_b": "A tree",
            "option_c": "A graph",
            "option_d": "A heap",
            "correct_option": "a",
            "explanation": "Lists are linear.",
            "difficulty_level": "easy",
        }
        second = {
            "question_text": "What is an index?",
            "option_a": "A position",
            "option_b": "A node",
            "option_c": "An edge",
            "option_d": "A hash",
            "correct_option": "a",
            "explanation": "An index identifies a position.",
            "difficulty_level": "easy",
        }

        async def fake_generate_stream(**_kwargs):
            yield {"questions": [first, second]}
            yield {
                "name": "Lists quiz",
                "description": "Incremental quiz",
                "questions": [first, second],
            }

        events = []
        with (
            patch(
                "edu_ai.agents.utils.get_session_factory",
                return_value=session_factory,
            ),
            patch(
                "edu_ai.agents.quiz_agent.generate_stream",
                new=fake_generate_stream,
            ),
        ):
            async for event in QuizAgent(
                search_service=_SearchService(),
                llm=_StreamingLlm(),
            ).generate_and_save_stream(
                project_id="project-quiz-stream",
                quiz_id="quiz-stream",
                topic="lists",
                count=2,
            ):
                events.append(event)

        self.assertEqual(
            [event["event"] for event in events],
            ["quiz_question_created", "quiz_question_created", "quiz_completed"],
        )
        with session_factory() as db:
            self.assertEqual(
                db.query(QuizQuestion)
                .filter(QuizQuestion.quiz_id == "quiz-stream")
                .count(),
                2,
            )
        engine.dispose()

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
