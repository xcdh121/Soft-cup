import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from config import Settings
from edu_core.schemas.quizzes import QuizQuestionDto
from routers.quizzes import (
    AiExplanationRequest,
    QuizAnalysisRequest,
    QuizAnswer,
    generate_question_ai_explanation,
    stream_quiz_result_analysis,
)


class _QuizService:
    def get_quiz_question(self, *, question_id: str, quiz_id: str, project_id: str):
        return self.list_quiz_questions(quiz_id=quiz_id, project_id=project_id)[0]

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
        with patch(
            "routers.quizzes.create_chat_model", return_value=model
        ) as create_model:
            response = await stream_quiz_result_analysis(
                project_id="project_1",
                quiz_id="quiz_1",
                request=QuizAnalysisRequest(
                    answers=[QuizAnswer(question_id="question_1", selected_option="B")]
                ),
                current_user=SimpleNamespace(id="student_1"),
                service=_QuizService(),
                settings=Settings(
                    llm_api_key="test-key",
                    llm_model="test-pro-model",
                    quiz_llm_model="test-flash-model",
                ),
            )

        body = b"".join([chunk async for chunk in response.body_iterator]).decode()
        events = [
            json.loads(block.removeprefix("data: "))
            for block in body.strip().split("\n\n")
        ]

        self.assertEqual(events[0], {"type": "model", "model": "test-flash-model"})
        self.assertEqual(create_model.call_args.args[0].model, "test-flash-model")
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

    async def test_question_explanation_uses_quiz_flash_model(self):
        model = _StreamingModel()
        with patch(
            "routers.quizzes.create_chat_model", return_value=model
        ) as create_model:
            response = await generate_question_ai_explanation(
                project_id="project_1",
                quiz_id="quiz_1",
                question_id="question_1",
                request=AiExplanationRequest(),
                current_user=SimpleNamespace(id="student_1"),
                service=_QuizService(),
                settings=Settings(
                    llm_api_key="test-key",
                    llm_model="test-pro-model",
                    quiz_llm_model="test-flash-model",
                ),
            )

        body = b"".join([chunk async for chunk in response.body_iterator]).decode()
        first_event = json.loads(body.split("\n\n", 1)[0].removeprefix("data: "))

        self.assertEqual(first_event, {"type": "model", "model": "test-flash-model"})
        self.assertEqual(create_model.call_args.args[0].model, "test-flash-model")


if __name__ == "__main__":
    unittest.main()
