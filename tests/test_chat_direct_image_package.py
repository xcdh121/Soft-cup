import json
import unittest
from types import SimpleNamespace

from edu_core.schemas.chats import TextPartDto, ToolCallPartDto
from edu_core.services.chats import ChatService
from langchain_core.messages import HumanMessage


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

        response = await service._create_direct_image_package_response(
            messages=[HumanMessage(content="你能生成关于树论的图片吗?")],
            context=context,
            assistant_message_id="assistant-1",
            chat_id="chat-1",
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


if __name__ == "__main__":
    unittest.main()
