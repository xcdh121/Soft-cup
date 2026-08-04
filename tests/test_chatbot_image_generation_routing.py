import unittest

from edu_ai.chatbot.image_generation_routing import (
    extract_image_topic,
    should_force_image_generation,
)
from langchain_core.messages import AIMessage, HumanMessage


class ChatbotImageGenerationRoutingTests(unittest.TestCase):
    def test_capability_question_routes_to_image_generation(self):
        self.assertTrue(
            should_force_image_generation([HumanMessage(content="你可以生成图片吗?")])
        )

    def test_affirmative_reply_after_image_offer_routes_to_generation(self):
        self.assertTrue(
            should_force_image_generation(
                [
                    AIMessage(content="是否需要我生成一张课程示意图?"),
                    HumanMessage(content="好的,生成吧"),
                ]
            )
        )

    def test_completed_tool_call_is_not_forced_again(self):
        self.assertFalse(
            should_force_image_generation(
                [
                    HumanMessage(content="生成一张二叉树图片"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "call-1",
                                "name": "resource_package_generate",
                                "args": {"resource_types": ["image"]},
                                "type": "tool_call",
                            }
                        ],
                    ),
                ]
            )
        )

    def test_extracts_topic_from_image_question(self):
        self.assertEqual(
            extract_image_topic(
                [HumanMessage(content="你能生成关于树论的图片吗?")]
            ),
            "树论",
        )


if __name__ == "__main__":
    unittest.main()
