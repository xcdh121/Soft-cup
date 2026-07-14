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
        self.assertFalse(hasattr(fake_model, "with_structured_output"))


if __name__ == "__main__":
    unittest.main()
