import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from code_execution import JudgeTestResult, ProgrammingJudgeResult
from edu_core.schemas.resource_packages import ProgrammingGradeDto
from routers.resource_packages import (
    grade_programming_answer,
    submit_programming_answer,
)


class ProgrammingSubmissionTest(unittest.IsolatedAsyncioTestCase):
    async def test_submit_runs_tests_without_calling_ai_grading(self):
        service = MagicMock()
        service.get_generated_resource.return_value = SimpleNamespace(
            resource_type="programming_questions",
            content_json={
                "questions": [
                    {
                        "id": "q1",
                        "test_cases": [
                            {
                                "input": "1 2\n",
                                "expected_output": "3\n",
                                "hidden": False,
                            },
                            {
                                "input": "20 22\n",
                                "expected_output": "42\n",
                                "hidden": True,
                            },
                        ],
                    }
                ]
            },
        )
        judge_result = ProgrammingJudgeResult(
            verdict="WA",
            message="输出与预期结果不一致。",
            passed_cases=1,
            total_cases=2,
            test_results=[
                JudgeTestResult(
                    index=1,
                    passed=True,
                    verdict="AC",
                    input="1 2\n",
                    expected_output="3\n",
                    actual_output="3\n",
                    stderr="",
                    hidden=False,
                ),
                JudgeTestResult(
                    index=2,
                    passed=False,
                    verdict="WA",
                    input=None,
                    expected_output=None,
                    actual_output="0\n",
                    stderr="",
                    hidden=True,
                ),
            ],
        )

        with patch(
            "routers.resource_packages.judge_code",
            new=AsyncMock(return_value=judge_result),
        ) as judge_mock:
            result = await submit_programming_answer(
                project_id="project-1",
                resource_id="resource-1",
                request=SimpleNamespace(
                    question_id="q1", answer="print(0)", language="python"
                ),
                user=SimpleNamespace(id="user-1"),
                service=service,
                settings=SimpleNamespace(
                    code_execution_api_url="http://sandbox/execute",
                    code_execution_api_token="token",
                    code_execution_timeout_seconds=5,
                ),
            )

        self.assertEqual(result.score, 50)
        self.assertFalse(result.passed)
        self.assertEqual(result.judge_verdict, "WA")
        self.assertEqual(len(result.test_results), 2)
        self.assertIsNone(result.test_results[1].input)
        judge_mock.assert_awaited_once()
        self.assertFalse(service.grade_programming_answer.called)

    async def test_ai_analysis_does_not_run_test_judging(self):
        expected = ProgrammingGradeDto(
            score=76,
            passed=True,
            verdict="needs_improvement",
            summary="思路可行, 还可以简化实现。",
            strengths=["输入处理正确"],
            issues=["存在重复逻辑"],
            suggestions=["提取公共函数"],
            complexity_analysis="时间复杂度 O(n), 空间复杂度 O(1)",
        )
        service = MagicMock()
        service.grade_programming_answer = AsyncMock(return_value=expected)

        with patch("routers.resource_packages.judge_code") as judge_mock:
            result = await grade_programming_answer(
                project_id="project-1",
                resource_id="resource-1",
                request=SimpleNamespace(
                    question_id="q1", answer="print(3)", language="python"
                ),
                user=SimpleNamespace(id="user-1"),
                service=service,
            )

        self.assertEqual(result, expected)
        judge_mock.assert_not_called()
        service.grade_programming_answer.assert_awaited_once_with(
            user_id="user-1",
            project_id="project-1",
            resource_id="resource-1",
            question_id="q1",
            answer="print(3)",
            language="python",
        )


if __name__ == "__main__":
    unittest.main()
