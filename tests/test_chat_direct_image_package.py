import json
import unittest
from types import SimpleNamespace

from edu_core.schemas.chats import TextPartDto, ToolCallPartDto
from edu_core.services.chats import ChatService


class ChatDirectImagePackageTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_question_returns_answer_and_package_tool_result(self):
        calls: list[dict] = []

        class FakeResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    id="image-package-1",
                    status="completed",
                    completed_resource_count=1,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FakeResourcePackageService(),
            learner_profile={},
            project_context={"course_name": "数据结构"},
            learning_evidence={},
        )
        service = ChatService.__new__(ChatService)

        response = await service._create_direct_resource_package_response(
            context=context,
            assistant_message_id="assistant-1",
            chat_id="chat-1",
            topic="树论",
            resource_types=["image"],
        )

        self.assertTrue(response.done)
        self.assertIsInstance(response.parts[0], TextPartDto)
        self.assertIn("树论", response.parts[0].text_content)
        self.assertIsInstance(response.parts[1], ToolCallPartDto)
        tool_output = json.loads(response.parts[1].tool_output)
        self.assertEqual(tool_output["package_id"], "image-package-1")
        self.assertEqual(tool_output["resource_types"], ["image"])
        self.assertEqual(calls[0]["payload"]["resource_types"], ["image"])
        self.assertEqual(calls[0]["payload"]["target_topic"], "树论")

    async def test_programming_request_returns_package_tool_result(self):
        calls: list[dict] = []

        class FakeResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    id="programming-package-1",
                    status="generating",
                    completed_resource_count=0,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FakeResourcePackageService(),
            learner_profile={},
            project_context={"course_name": "数据结构"},
            learning_evidence={},
        )
        service = ChatService.__new__(ChatService)

        response = await service._create_direct_resource_package_response(
            context=context,
            assistant_message_id="assistant-1",
            chat_id="chat-1",
            topic="递归",
            resource_types=["programming_questions"],
        )

        self.assertIn("递归", response.parts[0].text_content)
        self.assertIn("编程题正在后台生成", response.parts[0].text_content)
        tool_output = json.loads(response.parts[1].tool_output)
        self.assertEqual(tool_output["resource_types"], ["programming_questions"])
        self.assertEqual(
            calls[0]["payload"]["resource_types"], ["programming_questions"]
        )

    async def test_generic_package_request_uses_all_saved_preferences(self):
        calls: list[dict] = []

        class FakeResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    id="personalized-package-1",
                    status="generating",
                    completed_resource_count=0,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FakeResourcePackageService(),
            learner_profile={
                "fields": {"resource_preference": ["笔记", "刷题"]}
            },
            project_context={"course_name": "数据结构"},
            learning_evidence={},
            current_query="帮我生成一份学习递归的资源包",
        )
        service = ChatService.__new__(ChatService)

        response = await service._create_direct_resource_package_response(
            context=context,
            assistant_message_id="assistant-1",
            chat_id="chat-1",
            topic="递归",
            resource_types=[],
        )

        tool_output = json.loads(response.parts[1].tool_output)
        self.assertEqual(
            tool_output["resource_types"], ["practice_set", "lecture_note"]
        )
        self.assertEqual(calls[0]["payload"]["resource_types"], tool_output["resource_types"])


if __name__ == "__main__":
    unittest.main()
