"""Router for quiz CRUD operations."""

from collections.abc import AsyncGenerator
import json

from auth import get_current_user
from dependencies import (
    get_quiz_service,
    get_settings_dep,
    get_usage_service,
)
from config import Settings
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
