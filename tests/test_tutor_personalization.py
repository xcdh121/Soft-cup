import unittest

from edu_ai.chatbot.context import (
    ChatbotContext,
    build_tutor_personalization_prompt,
)


class TutorPersonalizationPromptTests(unittest.TestCase):
    def test_prompt_contains_saved_profile_and_learning_evidence(self):
        context = ChatbotContext(
            user_id="user-1",
            language="zh-CN",
            project_id="project-1",
            search=None,
            queue=None,
            project_context={"course_name": "数据结构"},
            learner_profile={
                "id": "profile-1",
                "fields": {
                    "learning_goal": "准备期末考试",
                    "resource_preference": ["笔记", "刷题"],
                },
            },
            learning_evidence={
                "overall_mastery": 46,
                "weak_points": [
                    {
                        "id": "kp-graph",
                        "name": "图的遍历",
                        "mastery_score": 32,
                    }
                ],
            },
        )

        prompt = build_tutor_personalization_prompt(context)

        self.assertIn("准备期末考试", prompt)
        self.assertIn("笔记", prompt)
        self.assertIn("图的遍历", prompt)
        self.assertIn("do not ask the learner to repeat", prompt)

    def test_prompt_explicitly_reports_when_no_profile_is_available(self):
        context = ChatbotContext(
            user_id="user-1",
            language="zh-CN",
            project_id="project-1",
            search=None,
            queue=None,
        )

        prompt = build_tutor_personalization_prompt(context)

        self.assertIn("No saved learner profile", prompt)
