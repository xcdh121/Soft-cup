"""Router for quiz CRUD operations."""

import json
import re
from collections.abc import AsyncGenerator

from auth import get_current_user
from config import Settings
from dependencies import (
    get_quiz_service,
    get_settings_dep,
    get_usage_service,
)
from edu_core.exceptions import NotFoundError
from edu_core.model_providers import LlmProviderConfig, create_chat_model
from edu_core.schemas.quizzes import QuizDto, QuizQuestionDto
from edu_core.schemas.users import UserDto
from edu_core.services import QuizService, UsageService
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from routers.schemas import (
    GenerateRequest,
    QuizCreate,
    QuizQuestionCreate,
    QuizQuestionReorder,
    QuizQuestionUpdate,
    QuizUpdate,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/quizzes", tags=["quizzes"])


@router.post("", response_model=QuizDto, status_code=201)
async def create_quiz(
    project_id: str,
    quiz: QuizCreate,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Create a new quiz."""
    try:
        return service.create_quiz(
            project_id=project_id,
            name=quiz.name,
            description=quiz.description,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{quiz_id}", response_model=QuizDto)
async def get_quiz(
    project_id: str,
    quiz_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Get a quiz by ID."""
    try:
        return service.get_quiz(quiz_id=quiz_id, project_id=project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[QuizDto])
async def list_quizzes(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """List all quizzes for a project."""
    try:
        return service.list_quizzes(project_id=project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{quiz_id}", response_model=QuizDto)
async def update_quiz(
    project_id: str,
    quiz_id: str,
    quiz: QuizUpdate,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Update a quiz."""
    try:
        return service.update_quiz(
            quiz_id=quiz_id,
            project_id=project_id,
            name=quiz.name,
            description=quiz.description,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    project_id: str,
    quiz_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Delete a quiz."""
    try:
        service.delete_quiz(quiz_id=quiz_id, project_id=project_id)
        return None
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GenerationProgressUpdate(BaseModel):
    """Progress update for generation streaming."""

    status: str = Field(..., description="Status: searching, generating, saving, done")
    message: str = Field(..., description="Progress message")
    error: str | None = Field(None, description="Error message if any")


class AiExplanationMessage(BaseModel):
    """One prior message in the question explanation conversation."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=12000)


class AiExplanationRequest(BaseModel):
    """Request for an initial explanation or a follow-up question."""

    question: str | None = Field(None, max_length=2000)
    history: list[AiExplanationMessage] = Field(default_factory=list, max_length=20)


class QuizAnswer(BaseModel):
    question_id: str = Field(min_length=1)
    selected_option: str = Field(pattern="^[A-D]$")


class QuizAnalysisRequest(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1, max_length=200)


class QuizAnalysisNarrative(BaseModel):
    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class QuizAnalysisDto(QuizAnalysisNarrative):
    total: int
    correct: int
    accuracy: int


def _correct_option(question: QuizQuestionDto) -> str | None:
    raw_answer = question.correct_option.strip()
    explicit = re.match(
        r"^(?:选项\s*)?([A-D])(?:\s*[.、:：)）\]-]|$)", raw_answer, re.I
    )
    if explicit:
        return explicit.group(1).upper()
    normalized = re.sub(r"\s+", " ", raw_answer).strip().lower()
    option_texts = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }
    for option, text in option_texts.items():
        if re.sub(r"\s+", " ", text).strip().lower() == normalized:
            return option
    loose = re.match(r"^([A-D])\s+.+$", raw_answer, re.I)
    return loose.group(1).upper() if loose else None


def _json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response does not contain a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("AI response is not a JSON object")
    return payload


@router.post("/{quiz_id}/generate", response_model=QuizDto)
async def generate_quiz(
    project_id: str,
    quiz_id: str,
    request: GenerateRequest,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Queue quiz generation request to be processed by a worker."""
    # Check usage limit before processing
    usage_service.check_and_increment(current_user.id, "quiz_generation")
    try:
        return service.queue_generation(
            quiz_id=quiz_id,
            project_id=project_id,
            topic=request.topic,
            custom_instructions=request.custom_instructions,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{quiz_id}/generate/stream", status_code=200)
async def generate_quiz_stream(
    project_id: str,
    quiz_id: str,
    request: GenerateRequest,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Queue quiz generation request with streaming progress updates."""
    # Check usage limit before processing
    usage_service.check_and_increment(current_user.id, "quiz_generation")

    async def generate_stream() -> AsyncGenerator[bytes]:
        """Generate streaming progress updates"""
        try:
            # Queuing request
            progress = GenerationProgressUpdate(
                status="queuing", message="Queuing quiz generation request..."
            )
            yield f"data: {progress.model_dump_json()}\n\n".encode()

            service.queue_generation(
                quiz_id=quiz_id,
                project_id=project_id,
                topic=request.topic,
                custom_instructions=request.custom_instructions,
                user_id=current_user.id,
            )

            # Done (queued)
            progress = GenerationProgressUpdate(
                status="done", message="Quiz generation request queued successfully"
            )
            yield f"data: {progress.model_dump_json()}\n\n".encode()

        except NotFoundError as e:
            error_progress = GenerationProgressUpdate(
                status="done", message="Error queuing quiz generation", error=str(e)
            )
            yield f"data: {error_progress.model_dump_json()}\n\n".encode()
        except Exception as e:
            error_progress = GenerationProgressUpdate(
                status="done", message="Error queuing quiz generation", error=str(e)
            )
            yield f"data: {error_progress.model_dump_json()}\n\n".encode()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.get("/{quiz_id}/questions", response_model=list[QuizQuestionDto])
async def list_quiz_questions(
    project_id: str,
    quiz_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """List all questions in a quiz."""
    try:
        return service.list_quiz_questions(quiz_id=quiz_id, project_id=project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{quiz_id}/questions", response_model=QuizQuestionDto, status_code=201)
async def create_quiz_question(
    project_id: str,
    quiz_id: str,
    question: QuizQuestionCreate,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Create a new question in a quiz."""
    try:
        return service.create_quiz_question(
            quiz_id=quiz_id,
            project_id=project_id,
            question_text=question.question_text,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_option=question.correct_option,
            explanation=question.explanation,
            difficulty_level=question.difficulty_level,
            position=question.position,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{quiz_id}/questions/{question_id}", response_model=QuizQuestionDto)
async def get_quiz_question(
    project_id: str,
    quiz_id: str,
    question_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Get a question by ID."""
    try:
        return service.get_quiz_question(
            question_id=question_id,
            quiz_id=quiz_id,
            project_id=project_id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{quiz_id}/questions/{question_id}/ai-explanation",
)
async def generate_question_ai_explanation(
    project_id: str,
    quiz_id: str,
    question_id: str,
    request: AiExplanationRequest,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
    settings: Settings = Depends(get_settings_dep),
):
    """Stream an initial explanation or follow-up answer from the configured LLM."""
    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    try:
        question = service.get_quiz_question(
            question_id=question_id,
            quiz_id=quiz_id,
            project_id=project_id,
        )
        model = create_chat_model(
            LlmProviderConfig(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.25,
            )
        ).bind(max_tokens=1200)
        question_context = f"""题目：{question.question_text}
A. {question.option_a}
B. {question.option_b}
C. {question.option_c}
D. {question.option_d}
正确答案：{question.correct_option}"""
        system_prompt = f"""你是一名耐心、严谨的中文教师，正在辅导学生理解一道选择题。

{question_context}

回答必须使用中文、紧扣本题，不要编造题目之外的条件。首次解析应依次包含解题思路、正确选项说明、错误选项分析、相关知识点和记忆提示；追问则直接、有针对性地回答。"""
        user_prompt = request.question or """请生成这道题的完整解析，依次说明：
1. 解题思路；
2. 正确选项为什么正确；
3. 其余选项为什么不正确；
4. 相关知识点与一个便于记忆的小提示。"""
        messages = [
            ("system", system_prompt),
            *[(message.role, message.content) for message in request.history],
            ("user", user_prompt),
        ]

        async def explanation_stream() -> AsyncGenerator[bytes]:
            yield f"data: {json.dumps({'type': 'model', 'model': settings.llm_model}, ensure_ascii=False)}\n\n".encode()
            yield f"data: {json.dumps({'type': 'status', 'message': f'正在解析当前题目 {question_id}'}, ensure_ascii=False)}\n\n".encode()
            try:
                async for chunk in model.astream(messages):
                    content = chunk.content
                    if isinstance(content, str):
                        text = content
                    else:
                        text = "".join(
                            str(item.get("text", ""))
                            if isinstance(item, dict)
                            else str(item)
                            for item in content
                        )
                    if text:
                        payload = json.dumps(
                            {"type": "delta", "content": text},
                            ensure_ascii=False,
                        )
                        yield f"data: {payload}\n\n".encode()
                yield b'data: {"type":"done"}\n\n'
            except Exception as exc:
                payload = json.dumps(
                    {"type": "error", "message": str(exc)},
                    ensure_ascii=False,
                )
                yield f"data: {payload}\n\n".encode()

        return StreamingResponse(
            explanation_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI explanation failed: {e}")


@router.post("/{quiz_id}/analysis", response_model=QuizAnalysisDto)
async def analyze_quiz_result(
    project_id: str,
    quiz_id: str,
    request: QuizAnalysisRequest,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
    settings: Settings = Depends(get_settings_dep),
) -> QuizAnalysisDto:
    """Analyze a completed quiz and return actionable Chinese learning advice."""
    del current_user
    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")
    try:
        questions = service.list_quiz_questions(quiz_id=quiz_id, project_id=project_id)
        answers = {
            answer.question_id: answer.selected_option for answer in request.answers
        }
        attempts = []
        for question in questions:
            selected = answers.get(question.id)
            if selected is None:
                continue
            correct_option = _correct_option(question)
            attempts.append(
                {
                    "question": question.question_text,
                    "selected_option": selected,
                    "correct_option": correct_option or question.correct_option,
                    "is_correct": selected == correct_option,
                    "explanation": question.explanation,
                    "difficulty": question.difficulty_level,
                }
            )
        if not attempts:
            raise HTTPException(status_code=400, detail="没有可分析的作答记录")

        correct = sum(item["is_correct"] for item in attempts)
        total = len(attempts)
        accuracy = round(correct / total * 100)
        prompt = f"""你是一名严谨、鼓励式的中文学习导师。请分析学生本次选择题作答结果，识别掌握较好的方面、需要加强的知识点，并给出可直接执行的复习建议。

要求：
1. 只根据给出的题目和作答数据分析，不编造课程范围外的信息。
2. 建议应具体、简短，并优先针对错题所反映的问题。
3. 只返回一个 JSON 对象，不要 Markdown 代码块，格式为：
{{"summary":"总体分析", "strengths":["优势"], "focus_areas":["薄弱点"], "suggestions":["行动建议"]}}

作答数据：
{json.dumps(attempts, ensure_ascii=False)}"""
        model = create_chat_model(
            LlmProviderConfig(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.2,
            )
        ).bind(max_tokens=1200)
        response = await model.ainvoke(prompt)
        content = response.content
        if isinstance(content, str):
            response_text = content
        else:
            response_text = "".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        narrative = QuizAnalysisNarrative.model_validate(_json_object(response_text))
        return QuizAnalysisDto(
            **narrative.model_dump(),
            total=total,
            correct=correct,
            accuracy=accuracy,
        )
    except HTTPException:
        raise
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI 作答分析暂时不可用") from exc


@router.patch("/{quiz_id}/questions/{question_id}", response_model=QuizQuestionDto)
async def update_quiz_question(
    project_id: str,
    quiz_id: str,
    question_id: str,
    question: QuizQuestionUpdate,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Update a question."""
    try:
        return service.update_quiz_question(
            question_id=question_id,
            quiz_id=quiz_id,
            project_id=project_id,
            question_text=question.question_text,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_option=question.correct_option,
            explanation=question.explanation,
            difficulty_level=question.difficulty_level,
            position=question.position,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{quiz_id}/questions/{question_id}", status_code=204)
async def delete_quiz_question(
    project_id: str,
    quiz_id: str,
    question_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Delete a question."""
    try:
        service.delete_quiz_question(
            question_id=question_id,
            quiz_id=quiz_id,
            project_id=project_id,
        )
        return None
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{quiz_id}/questions/reorder", response_model=list[QuizQuestionDto])
async def reorder_quiz_questions(
    project_id: str,
    quiz_id: str,
    reorder: QuizQuestionReorder,
    current_user: UserDto = Depends(get_current_user),
    service: QuizService = Depends(get_quiz_service),
):
    """Reorder questions in a quiz."""
    try:
        return service.reorder_quiz_questions(
            quiz_id=quiz_id,
            project_id=project_id,
            question_ids=reorder.question_ids,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
