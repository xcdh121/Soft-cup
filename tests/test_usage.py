import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from edu_core.services.usage import UsageService
from edu_db.base import Base
from edu_db.models import (
    AgentRun,
    AgentToolCall,
    Chat,
    ChatMessage,
    ChatMessagePart,
    Project,
    User,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class UsageServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session_patch = patch(
            "edu_core.services.usage.get_session_factory",
            return_value=self.session_factory,
        )
        self.session_patch.start()

        with self.session_factory() as db:
            db.add(User(id="user-1", username="user-1", name="User One"))
            db.add(Project(id="project-1", owner_id="user-1", name="Course"))
            db.commit()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def test_get_usage_combines_chat_and_agent_tool_calls(self):
        now = datetime.now(UTC)
        with self.session_factory() as db:
            chat = Chat(
                id="chat-1",
                project_id="project-1",
                user_id="user-1",
                title="Tutor",
            )
            message = ChatMessage(
                id="message-1",
                chat_id="chat-1",
                role="assistant",
                created_at=now,
            )
            db.add_all(
                [
                    chat,
                    message,
                    ChatMessagePart(
                        id="part-1",
                        message_id="message-1",
                        part_type="tool_call",
                        tool_name="search_project_documents",
                        tool_state="output-available",
                        created_at=now,
                    ),
                    ChatMessagePart(
                        id="part-2",
                        message_id="message-1",
                        part_type="tool_call",
                        tool_name="search_project_documents",
                        tool_state="output-error",
                        created_at=now + timedelta(seconds=1),
                    ),
                    AgentRun(
                        id="run-1",
                        project_id="project-1",
                        user_id="user-1",
                        goal="diagnosis",
                        status="completed",
                    ),
                    AgentToolCall(
                        id="call-1",
                        run_id="run-1",
                        agent_name="diagnosis",
                        tool_name="get_knowledge_states",
                        tool_version="1",
                        status="completed",
                        risk_level="read",
                        approval_status="not_required",
                        started_at=now,
                    ),
                ]
            )
            db.commit()

        usage = UsageService().get_usage("user-1")

        self.assertEqual(
            [item.tool_name for item in usage.tool_usage],
            ["search_project_documents", "get_knowledge_states"],
        )
        search_usage = usage.tool_usage[0]
        self.assertEqual(search_usage.total, 2)
        self.assertEqual(search_usage.successful, 1)
        self.assertEqual(search_usage.failed, 1)
        self.assertEqual(usage.tool_usage[1].successful, 1)

    def test_get_usage_excludes_tool_calls_before_today(self):
        yesterday = datetime.now(UTC) - timedelta(days=1)
        with self.session_factory() as db:
            db.add(
                AgentRun(
                    id="old-run",
                    project_id="project-1",
                    user_id="user-1",
                    goal="diagnosis",
                    status="completed",
                )
            )
            db.add(
                AgentToolCall(
                    id="old-call",
                    run_id="old-run",
                    agent_name="diagnosis",
                    tool_name="get_knowledge_graph",
                    tool_version="1",
                    status="completed",
                    risk_level="read",
                    approval_status="not_required",
                    started_at=yesterday,
                )
            )
            db.commit()

        usage = UsageService().get_usage("user-1")

        self.assertEqual(usage.tool_usage, [])


if __name__ == "__main__":
    unittest.main()
