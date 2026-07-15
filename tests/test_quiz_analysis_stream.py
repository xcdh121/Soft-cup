import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from config import Settings
from edu_core.schemas.quizzes import QuizQuestionDto
from routers.quizzes import (
    QuizAnalysisRequest,
    QuizAnswer,
    stream_quiz_result_analysis,
)


class _QuizService:
    def list_quiz_questions(self, *, quiz_id: str, project_id: str):
        return [
            QuizQuestionDto(
                id="question_1",
                quiz_id=quiz_id,
                project_id=project_id,
                question_text="2 + 2 等于多少？",
                option_a="3",
                option_b="4",
                option_c="5",
                option_d="6",
                correct_option="B",
                explanation="基础加法",
                difficulty_level="easy",
                position=0,
                created_at=datetime.now(UTC),
            )
        ]


class _StreamingModel:
    def __init__(self):
        self.prompt = ""

    def bind(self, **_kwargs):
        return self

    async def astream(self, prompt: str):
        self.prompt = prompt
        for text in ("### 总体分析\n", "本次基础知识掌握良好。"):
            yield SimpleNamespace(content=text)


class QuizAnalysisStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_emits_meta_and_text_deltas(self):
        model = _StreamingModel()
        with patch("routers.quizzes.create_chat_model", return_value=model):
            response = await stream_quiz_result_analysis(
                project_id="project_1",
                quiz_id="quiz_1",
                request=QuizAnalysisRequest(
                    answers=[QuizAnswer(question_id="question_1", selected_option="B")]
                ),
                current_user=SimpleNamespace(id="student_1"),
                service=_QuizService(),
                settings=Settings(llm_api_key="test-key", llm_model="test-model"),
            )

        body = b"".join([chunk async for chunk in response.body_iterator]).decode()
        events = [
            json.loads(block.removeprefix("data: "))
            for block in body.strip().split("\n\n")
        ]

        self.assertEqual(events[0], {"type": "model", "model": "test-model"})
        self.assertEqual(
            events[1],
            {"type": "meta", "total": 1, "correct": 1, "accuracy": 100},
        )
        self.assertEqual(
            "".join(event["content"] for event in events if event["type"] == "delta"),
            "### 总体分析\n本次基础知识掌握良好。",
        )
        self.assertEqual(events[-1], {"type": "done"})
        self.assertIn("直接输出中文 Markdown", model.prompt)


if __name__ == "__main__":
    unittest.main()
