import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from edu_core.services.chats import ChatService
from edu_db.models import Base, Chat, ChatMessage, ChatMessagePart
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

API_SRC = Path(__file__).resolve().parents[1] / "src" / "edu-api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from task_runner import TaskRunnerService  # noqa: E402


class ChatTitleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_list_chats_backfills_older_unnamed_chat(self):
        with self.session_factory() as db:
            db.add(
                Chat(
                    id="chat-1",
                    project_id="project-1",
                    user_id="user-1",
                    title=None,
                )
            )
            db.add(
                ChatMessage(
                    id="message-1",
                    chat_id="chat-1",
                    role="user",
                )
            )
            db.add(
                ChatMessagePart(
                    id="part-1",
                    message_id="message-1",
                    part_type="text",
                    order=0,
                    text_content="请详细讲解二叉树的前序、中序和后序遍历方法。",
                )
            )
            db.commit()

        service = ChatService.__new__(ChatService)
        with patch(
            "edu_core.services.chats.get_session_factory",
            return_value=self.session_factory,
        ):
            chats = service.list_chats("project-1", "user-1")

        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0].title, "请详细讲解二叉树的前序、中序和后序遍历方法")
        with self.session_factory() as db:
            self.assertEqual(
                db.get(Chat, "chat-1").title,
                "请详细讲解二叉树的前序、中序和后序遍历方法",
            )

    def test_get_chat_backfills_title_for_current_chat(self):
        with self.session_factory() as db:
            db.add(
                Chat(
                    id="current-chat",
                    project_id="project-1",
                    user_id="user-1",
                    title=None,
                )
            )
            db.add(
                ChatMessage(
                    id="current-message",
                    chat_id="current-chat",
                    role="user",
                )
            )
            db.add(
                ChatMessagePart(
                    id="current-part",
                    message_id="current-message",
                    part_type="text",
                    order=0,
                    text_content="解释动态规划的状态转移方程。",
                )
            )
            db.commit()

        service = ChatService.__new__(ChatService)
        with patch(
            "edu_core.services.chats.get_session_factory",
            return_value=self.session_factory,
        ):
            chat = service.get_chat(
                "current-chat", "user-1", include_messages=True
            )

        self.assertEqual(chat.title, "解释动态规划的状态转移方程")

    async def test_title_task_generates_and_persists_title(self):
        with self.session_factory() as db:
            db.add(
                Chat(
                    id="chat-2",
                    project_id="project-1",
                    user_id="user-1",
                    title=None,
                )
            )
            db.commit()

        model = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value=SimpleNamespace(content="“二叉树遍历方法。”")
            )
        )
        runner = TaskRunnerService.__new__(TaskRunnerService)
        runner.llm_config = object()
        payload = {
            "chat_id": "chat-2",
            "project_id": "project-1",
            "user_id": "user-1",
            "user_message": "二叉树如何遍历?",
            "ai_response": "可以使用前序、中序和后序遍历。",
        }

        with (
            patch("task_runner.create_chat_model", return_value=model),
            patch(
                "task_runner.get_session_factory",
                return_value=self.session_factory,
            ),
        ):
            await runner._generate_chat_title(payload)

        with self.session_factory() as db:
            self.assertEqual(db.get(Chat, "chat-2").title, "二叉树遍历方法")

    async def test_title_task_does_not_overwrite_manual_title(self):
        with self.session_factory() as db:
            db.add(
                Chat(
                    id="chat-3",
                    project_id="project-1",
                    user_id="user-1",
                    title="我的自定义标题",
                )
            )
            db.commit()

        model = SimpleNamespace(
            ainvoke=AsyncMock(return_value=SimpleNamespace(content="自动标题"))
        )
        runner = TaskRunnerService.__new__(TaskRunnerService)
        runner.llm_config = object()
        payload = {
            "chat_id": "chat-3",
            "project_id": "project-1",
            "user_id": "user-1",
            "user_message": "测试消息",
            "ai_response": "测试回答",
        }

        with (
            patch("task_runner.create_chat_model", return_value=model),
            patch(
                "task_runner.get_session_factory",
                return_value=self.session_factory,
            ),
        ):
            await runner._generate_chat_title(payload)

        with self.session_factory() as db:
            self.assertEqual(db.get(Chat, "chat-3").title, "我的自定义标题")


if __name__ == "__main__":
    unittest.main()
