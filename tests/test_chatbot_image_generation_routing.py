import unittest

from edu_ai.chatbot.image_generation_routing import (
    extract_image_topic,
    extract_programming_topic,
    resolve_forced_resource_generation,
    should_force_image_generation,
    should_force_programming_generation,
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
            extract_image_topic([HumanMessage(content="你能生成关于树论的图片吗?")]),
            "树论",
        )

    def test_programming_question_request_is_forced(self):
        messages = [HumanMessage(content="请你生成一份关于递归的编程题")]

        self.assertTrue(should_force_programming_generation(messages))
        self.assertEqual(extract_programming_topic(messages), "递归")
        intent = resolve_forced_resource_generation(messages)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.resource_types, ("programming_questions",))
        self.assertEqual(intent.topic, "递归")

    def test_api_chat_history_dictionary_routes_programming_request(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请你生成一份DFS的编程题",
                    }
                ],
            }
        ]

        intent = resolve_forced_resource_generation(messages)

        self.assertIsNotNone(intent)
        self.assertEqual(intent.resource_types, ("programming_questions",))
        self.assertEqual(intent.topic, "dfs")

    def test_programming_explanation_does_not_trigger_generation(self):
        self.assertFalse(
            should_force_programming_generation(
                [HumanMessage(content="请讲解这道递归编程题")]
            )
        )

    def test_graph_theory_explanation_does_not_trigger_image_generation(self):
        messages = [HumanMessage(content="请讲解图论知识点")]

        self.assertFalse(should_force_image_generation(messages))
        self.assertIsNone(resolve_forced_resource_generation(messages))

    def test_pdf_ocr_context_does_not_trigger_image_generation(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "[PDF识别上下文:数据结构与算法.pdf]\n"
                            "![img](data:image/jpeg;base64,abc)\n"
                            "Make use of all bits, then draw the binary search tree."
                        ),
                    }
                ],
            }
        ]

        self.assertFalse(should_force_image_generation(messages))
        self.assertIsNone(resolve_forced_resource_generation(messages))

    def test_explicit_request_still_routes_when_pdf_context_is_attached(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请生成一张归并排序示意图"},
                    {
                        "type": "text",
                        "text": "[PDF识别上下文:讲义.pdf]\n课程正文",
                    },
                ],
            }
        ]

        intent = resolve_forced_resource_generation(messages)

        self.assertIsNotNone(intent)
        self.assertEqual(intent.resource_types, ("image",))
        self.assertEqual(intent.topic, "归并排序")

    def test_affirmative_reply_after_programming_offer_is_forced(self):
        messages = [
            AIMessage(content="要不要为递归生成一套编程题?"),
            HumanMessage(content="好的"),
        ]

        intent = resolve_forced_resource_generation(messages)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.resource_types, ("programming_questions",))
        self.assertEqual(intent.topic, "递归")


if __name__ == "__main__":
    unittest.main()
