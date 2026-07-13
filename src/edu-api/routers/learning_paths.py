import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import suppress

from auth import get_current_user
from dependencies import get_agent_orchestration_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.agent_orchestration import (
    LearningPathGenerateRequest,
    LearningPathResponse,
)
from edu_core.schemas.users import UserDto
from edu_core.services import AgentOrchestrationService
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/learning-paths", tags=["learning-paths"]
)


@router.get("/latest", response_model=LearningPathResponse | None)
async def get_latest_learning_path(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        return service.get_latest_learning_path(current_user.id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("", response_model=list[LearningPathResponse])
async def list_learning_paths(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        return service.list_learning_paths(current_user.id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/generate",
    response_model=LearningPathResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_learning_path(
    project_id: str,
    request: LearningPathGenerateRequest | None = None,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        return await service.generate_learning_path(
            user_id=current_user.id,
            project_id=project_id,
            diagnosis_id=request.diagnosis_id if request else None,
            trigger=request.trigger if request else None,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate/stream")
async def generate_learning_path_stream(
    project_id: str,
    request: LearningPathGenerateRequest | None = None,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    """Generate a learning path while streaming orchestration progress events."""

    async def generate_stream() -> AsyncGenerator[bytes]:
        queue = asyncio.Queue()
        task = asyncio.create_task(
            service.generate_learning_path(
                user_id=current_user.id,
                project_id=project_id,
                diagnosis_id=request.diagnosis_id if request else None,
                trigger=request.trigger if request else None,
                event_sink=queue.put,
            )
        )
        try:
            while not task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                payload = {
                    "event": "progress",
                    "message": event.summary,
                    **event.model_dump(mode="json"),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()

            result = await task
            payload = {
                "event": "completed",
                "status": "completed",
                "message": "学习计划生成完成。",
                "result": result.model_dump(mode="json"),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
        except Exception as exc:
            payload = {
                "event": "failed",
                "status": "failed",
                "message": "学习计划生成失败。",
                "error": str(exc),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
