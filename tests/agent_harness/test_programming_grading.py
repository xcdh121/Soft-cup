import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from edu_core.model_providers import LlmProviderConfig
from edu_core.services.resource_packages import ResourcePackageService


class ProgrammingGradingTest(unittest.IsolatedAsyncioTestCase):
    async def test_grading_uses_plain_json_for_compatible_providers(self):
        class FakeModel:
            def __init__(self):
                self.prompt = ""

            async def ainvoke(self, prompt):
                self.prompt = prompt
                return SimpleNamespace(
                    content="""
                    {
                      "score": 82,
                      "passed": true,
                      "verdict": "accepted",
                      "summary": "The solution is correct.",
                      "strengths": ["Correct algorithm"],
                      "issues": [],
                      "suggestions": ["Add comments"],
                      "complexity_analysis": "O(n) time and O(1) space",
                      "grading_mode": "ai"
                    }
                    """
                )

        fake_model = FakeModel()
        service = ResourcePackageService(
            llm_config=LlmProviderConfig(model="compatible-model", api_key="test")
        )
        service.get_generated_resource = MagicMock(
            return_value=SimpleNamespace(
                resource_type="programming_questions",
                content_json={
                    "questions": [
                        {
                            "id": "q1",
                            "title": "Sum two numbers",
                            "description": "Read two integers and print their sum.",
                        }
                    ]
                },
            )
        )

        with patch(
            "edu_core.services.resource_packages.create_chat_model",
            return_value=fake_model,
        ):
            result = await service.grade_programming_answer(
                user_id="user-1",
                project_id="project-1",
                resource_id="resource-1",
                question_id="q1",
                answer="std::cout << a + b;",
                language="cpp",
            )

        self.assertEqual(result.score, 82)
        self.assertTrue(result.passed)
        self.assertIn('"programming_language": "cpp"', fake_model.prompt)
        self.assertIn("必须使用简体中文", fake_model.prompt)
        self.assertFalse(hasattr(fake_model, "with_structured_output"))

    async def test_grading_normalizes_model_verdict_before_validation(self):
        class FakeModel:
            async def ainvoke(self, prompt):
                return SimpleNamespace(
                    content="""
                    {
                      "score": 82,
                      "passed": false,
                      "verdict": "correct",
                      "summary": "The solution is correct.",
                      "strengths": ["Correct algorithm"],
                      "issues": [],
                      "suggestions": ["Add comments"],
                      "complexity_analysis": "O(n) time and O(1) space",
                      "grading_mode": "ai"
                    }
                    """
                )

        service = ResourcePackageService(
            llm_config=LlmProviderConfig(model="compatible-model", api_key="test")
        )
        service.get_generated_resource = MagicMock(
            return_value=SimpleNamespace(
                resource_type="programming_questions",
                content_json={
                    "questions": [
                        {
                            "id": "q1",
                            "title": "Sum two numbers",
                            "description": "Read two integers and print their sum.",
                        }
                    ]
                },
            )
        )

        with patch(
            "edu_core.services.resource_packages.create_chat_model",
            return_value=FakeModel(),
        ):
            result = await service.grade_programming_answer(
                user_id="user-1",
                project_id="project-1",
                resource_id="resource-1",
                question_id="q1",
                answer="std::cout << a + b;",
                language="cpp",
            )

        self.assertEqual(result.score, 82)
        self.assertTrue(result.passed)
        self.assertEqual(result.verdict, "accepted")

    async def test_test_judge_result_is_authoritative_for_score_and_verdict(self):
        class FakeModel:
            async def ainvoke(self, prompt):
                return SimpleNamespace(
                    content="""
                    {
                      "score": 95,
                      "summary": "代码思路清晰, 但测试输出不正确。",
                      "strengths": ["输入处理清晰"],
                      "issues": ["未通过全部测试案例"],
                      "suggestions": ["核对边界条件"],
                      "complexity_analysis": "时间复杂度 O(n), 空间复杂度 O(1)"
                    }
                    """
                )

        service = ResourcePackageService(
            llm_config=LlmProviderConfig(model="compatible-model", api_key="test")
        )
        service.get_generated_resource = MagicMock(
            return_value=SimpleNamespace(
                resource_type="programming_questions",
                content_json={
                    "questions": [
                        {"id": "q1", "title": "求和", "description": "输出两数之和"}
                    ]
                },
            )
        )
        with patch(
            "edu_core.services.resource_packages.create_chat_model",
            return_value=FakeModel(),
        ):
            result = await service.grade_programming_answer(
                user_id="user-1",
                project_id="project-1",
                resource_id="resource-1",
                question_id="q1",
                answer="print(0)",
                judge_result={
                    "verdict": "WA",
                    "message": "输出与预期结果不一致。",
                    "passed_cases": 2,
                    "total_cases": 4,
                    "test_results": [],
                },
            )

        self.assertEqual(result.score, 50)
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "incorrect")
        self.assertEqual(result.judge_verdict, "WA")
        self.assertEqual(result.grading_mode, "tests_and_ai")


if __name__ == "__main__":
    unittest.main()
