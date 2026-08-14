import unittest
from types import SimpleNamespace
from unittest.mock import patch

from edu_ai.agents.flashcard_agent import FlashcardAgent
from edu_ai.agents.note_agent import NoteAgent
from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_ai.agents.quiz_agent import QuizAgent
from edu_ai.agents.utils import ModelUsage, generate_stream
from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    OrchestrationRunRequest,
    RunStatus,
)
from edu_db.models import (
    Base,
    Flashcard,
    FlashcardGroup,
    Note,
    Project,
    Quiz,
    QuizQuestion,
    User,
)
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
        contents = (
            '{"title":"Transactions","content":"# Atomicity',
            "\\n\\nA transaction",
            ' is all-or-nothing."}',
        )
        for index, content in enumerate(contents):
            yield SimpleNamespace(
                content=content,
                usage_metadata={"input_tokens": 120, "output_tokens": 45}
                if index == len(contents) - 1
                else None,
                response_metadata={"model_name": "test-model"}
                if index == len(contents) - 1
                else None,
            )


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
    async def test_note_agent_persists_each_content_snapshot(self):
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
                        id="user-note-stream",
                        username="note-stream",
                        name="Note Stream",
                        email="note-stream@example.com",
                    ),
                    Project(
                        id="project-note-stream",
                        owner_id="user-note-stream",
                        name="Streaming project",
                        language_code="en",
                    ),
                    Note(
                        id="note-stream",
                        project_id="project-note-stream",
                        title="Pending note",
                        content="",
                    ),
                ]
            )
            db.commit()

        async def fake_generate_stream(**_kwargs):
            yield {"content": "Hello"}
            yield {
                "title": "Streaming note",
                "description": "Incremental note",
                "content": "Hello world",
            }

        persisted_contents = []
        with (
            patch(
                "edu_ai.agents.utils.get_session_factory",
                return_value=session_factory,
            ),
            patch(
                "edu_ai.agents.note_agent.generate_stream",
                new=fake_generate_stream,
            ),
        ):
            async for event in NoteAgent(
                search_service=_SearchService(),
                llm=_StreamingLlm(),
            ).generate_and_save_stream(
                project_id="project-note-stream",
                note_id="note-stream",
                topic="streaming",
            ):
                if event["event"] == "note_delta":
                    with session_factory() as db:
                        persisted_contents.append(
                            db.query(Note)
                            .filter(Note.id == "note-stream")
                            .one()
                            .content
                        )

        self.assertEqual(persisted_contents, ["Hello", "Hello world"])
        engine.dispose()

    async def test_flashcard_agent_persists_each_card_before_event(self):
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
                        id="user-card-stream",
                        username="card-stream",
                        name="Card Stream",
                        email="card-stream@example.com",
                    ),
                    Project(
                        id="project-card-stream",
                        owner_id="user-card-stream",
                        name="Streaming project",
                        language_code="en",
                    ),
                    FlashcardGroup(
                        id="group-stream",
                        project_id="project-card-stream",
                        name="Pending cards",
                    ),
                ]
            )
            db.commit()

        first = {
            "question": "What is a list?",
            "answer": "A linear collection",
            "difficulty_level": "easy",
        }
        second = {
            "question": "What is an index?",
            "answer": "A position",
            "difficulty_level": "easy",
        }

        async def fake_generate_stream(**_kwargs):
            yield {"flashcards": [first, second]}
            yield {
                "name": "Lists cards",
                "description": "Incremental cards",
                "flashcards": [first, second],
            }

        persisted_counts = []
        with (
            patch(
                "edu_ai.agents.utils.get_session_factory",
                return_value=session_factory,
            ),
            patch(
                "edu_ai.agents.flashcard_agent.generate_stream",
                new=fake_generate_stream,
            ),
        ):
            async for event in FlashcardAgent(
                search_service=_SearchService(),
                llm=_StreamingLlm(),
            ).generate_and_save_stream(
                project_id="project-card-stream",
                group_id="group-stream",
                topic="lists",
                count=2,
            ):
                if event["event"] == "flashcard_created":
                    with session_factory() as db:
                        persisted_counts.append(
                            db.query(Flashcard)
                            .filter(Flashcard.group_id == "group-stream")
                            .count()
                        )

        self.assertEqual(persisted_counts, [1, 2])
        engine.dispose()

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
        persisted_counts = []
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
                if event["event"] == "quiz_question_created":
                    with session_factory() as db:
                        persisted_counts.append(
                            db.query(QuizQuestion)
                            .filter(QuizQuestion.quiz_id == "quiz-stream")
                            .count()
                        )

        self.assertEqual(
            [event["event"] for event in events],
            ["quiz_question_created", "quiz_question_created", "quiz_completed"],
        )
        self.assertEqual(persisted_counts, [1, 2])
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

    async def test_stream_reports_terminal_model_usage(self):
        usages: list[ModelUsage] = []

        async for _ in generate_stream(
            llm=_StreamingLlm(),
            search_service=_SearchService(),
            output_model=_Output,
            prompt_template="note_prompt",
            project_id="project-1",
            topic="transactions",
            language_code="en",
            usage_sink=usages.append,
        ):
            pass

        self.assertEqual(len(usages), 1)
        self.assertEqual(usages[0].model_name, "test-model")
        self.assertEqual(usages[0].input_tokens, 120)
        self.assertEqual(usages[0].output_tokens, 45)

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

        profile_events = [
            event for event in events if event.agent_name == AgentName.PROFILE
        ]
        self.assertEqual(profile_events[0].status, RunStatus.RUNNING)
        self.assertEqual(profile_events[0].payload["phase"], "started")
        self.assertEqual(profile_events[1].status, RunStatus.COMPLETED)
        self.assertEqual(profile_events[1].payload["phase"], "completed")


if __name__ == "__main__":
    unittest.main()
