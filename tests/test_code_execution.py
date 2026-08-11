import json
import unittest
from unittest.mock import AsyncMock, patch

from code_execution import (
    CodeExecutionError,
    CodeExecutionResult,
    execute_code,
    judge_code,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit: int):
        return self.payload


class CodeExecutionTest(unittest.IsolatedAsyncioTestCase):
    async def test_execute_code_forwards_stdin_and_returns_output(self):
        response = _FakeResponse(
            {
                "language": "python",
                "version": "3.12.0",
                "run": {
                    "stdout": "8\n",
                    "stderr": "",
                    "output": "8\n",
                    "code": 0,
                    "signal": None,
                },
            }
        )

        with patch("code_execution.request.urlopen", return_value=response) as urlopen:
            result = await execute_code(
                api_url="http://sandbox.test/api/v2/execute",
                api_token="secret",
                language="python",
                code="a, b = map(int, input().split()); print(a + b)",
                stdin="3 5\n",
                timeout_seconds=3,
            )

        sent_request = urlopen.call_args.args[0]
        sent_payload = json.loads(sent_request.data)
        self.assertEqual(sent_payload["stdin"], "3 5\n")
        self.assertEqual(sent_payload["language"], "python")
        self.assertEqual(sent_request.headers["Authorization"], "Bearer secret")
        self.assertEqual(result.output, "8\n")
        self.assertEqual(result.exit_code, 0)

    async def test_execute_code_preserves_successful_empty_output(self):
        response = _FakeResponse(
            {
                "language": "python",
                "version": "3.12.0",
                "run": {
                    "stdout": "",
                    "stderr": "",
                    "output": "",
                    "code": 0,
                    "signal": None,
                },
            }
        )

        with patch("code_execution.request.urlopen", return_value=response):
            result = await execute_code(
                api_url="http://sandbox.test/api/v2/execute",
                api_token="",
                language="python",
                code="value = 42",
                stdin="",
                timeout_seconds=3,
            )

        self.assertEqual(result.output, "")
        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(result.signal)

    async def test_execute_code_rejects_success_response_without_job_result(self):
        response = _FakeResponse({"message": "runtime unavailable"})

        with (
            patch("code_execution.request.urlopen", return_value=response),
            self.assertRaisesRegex(CodeExecutionError, "runtime unavailable"),
        ):
            await execute_code(
                api_url="http://sandbox.test/api/v2/execute",
                api_token="",
                language="python",
                code="print(1)",
                stdin="",
                timeout_seconds=3,
            )

    async def test_judge_code_returns_wrong_answer_and_partial_score_data(self):
        executions = [
            CodeExecutionResult("python", "3.12", "3\n", "", "3\n", 0, None),
            CodeExecutionResult("python", "3.12", "9\n", "", "9\n", 0, None),
        ]
        with patch(
            "code_execution.execute_code",
            new=AsyncMock(side_effect=executions),
        ):
            result = await judge_code(
                api_url="http://sandbox.test/api/v2/execute",
                api_token="",
                language="python",
                code="print(1)",
                test_cases=[
                    {"input": "1 2\n", "expected_output": "3\n", "hidden": False},
                    {"input": "4 4\n", "expected_output": "8\n", "hidden": True},
                ],
                timeout_seconds=3,
            )

        self.assertEqual(result.verdict, "WA")
        self.assertEqual(result.passed_cases, 1)
        self.assertEqual(result.total_cases, 2)
        self.assertIsNone(result.test_results[1].input)
        self.assertIsNone(result.test_results[1].expected_output)

    async def test_judge_code_distinguishes_compile_error_and_timeout(self):
        compile_error = CodeExecutionResult(
            "c++", "17", "", "syntax error", "syntax error", 1, None, 1
        )
        timed_out = CodeExecutionResult("python", "3.12", "", "", "", None, "SIGKILL")
        for execution, expected in ((compile_error, "CE"), (timed_out, "TLE")):
            with patch(
                "code_execution.execute_code",
                new=AsyncMock(return_value=execution),
            ):
                result = await judge_code(
                    api_url="http://sandbox.test/api/v2/execute",
                    api_token="",
                    language="python",
                    code="broken",
                    test_cases=[{"input": "", "expected_output": ""}],
                    timeout_seconds=3,
                )
            self.assertEqual(result.verdict, expected)


if __name__ == "__main__":
    unittest.main()
