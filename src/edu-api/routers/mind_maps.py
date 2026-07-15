"""Router for mind map operations."""

import json
from collections.abc import AsyncGenerator

from auth import get_current_user
from dependencies import (
    get_mind_map_service,
    get_task_runner,
    get_usage_service,
)
from task_runner import TaskRunnerService
from edu_core.exceptions import NotFoundError
from edu_core.schemas.mind_maps import MindMapDto
from edu_core.schemas.users import UserDto
from edu_core.services import MindMapService, UsageService
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from routers.schemas import MindMapCreate

router = APIRouter(prefix="/api/v1/projects/{project_id}/mind-maps", tags=["mind-maps"])


class GenerationProgressUpdate(BaseModel):
    """Progress update for generation streaming."""

    status: str = Field(..., description="Status: searching, generating, saving, done")
    message: str = Field(..., description="Progress message")
    mind_map_id: str | None = Field(None, description="Mind map ID if available")
    error: str | None = Field(None, description="Error message if any")


@router.get("", response_model=list[MindMapDto])
async def list_mind_maps(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: MindMapService = Depends(get_mind_map_service),
):
    """List all mind maps for a project."""
    try:
        return service.list_mind_maps(
            project_id=project_id,
            user_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{mind_map_id}", response_model=MindMapDto)
async def get_mind_map(
    project_id: str,
    mind_map_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: MindMapService = Depends(get_mind_map_service),
):
    """Get a mind map by ID."""
    try:
        return service.get_mind_map(
            mind_map_id=mind_map_id,
            project_id=project_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=MindMapDto, status_code=201)
async def create_mind_map(
    project_id: str,
    request: MindMapCreate,
    current_user: UserDto = Depends(get_current_user),
    service: MindMapService = Depends(get_mind_map_service),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Generate/create a mind map.

    Note: AI generation is not yet implemented in edu-shared service.
    This endpoint creates a basic mind map structure.
    """
    # Check usage limit before processing
    usage_service.check_and_increment(current_user.id, "mindmap_generation")

    try:
        # For now, create a basic mind map
        # TODO: Implement AI generation using search_service and agent_config
        return service.create_mind_map(
            user_id=current_user.id,
            project_id=project_id,
            title=request.title,
            description=request.description,
            map_data={"nodes": [], "edges": []},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream", status_code=200)
async def create_mind_map_stream(
    project_id: str,
    request: MindMapCreate,
    current_user: UserDto = Depends(get_current_user),
    service: MindMapService = Depends(get_mind_map_service),
    usage_service: UsageService = Depends(get_usage_service),
    task_runner: TaskRunnerService = Depends(get_task_runner),
):
    """Generate a mind map and stream valid node/edge batches."""

    # Check usage limit before processing
    usage_service.check_and_increment(current_user.id, "mindmap_generation")

    async def generate_stream() -> AsyncGenerator[bytes]:
        """Generate streaming progress updates"""
        try:
            mind_map = service.create_mind_map(
                user_id=current_user.id,
                project_id=project_id,
                title=request.title or "Generating...",
                description=request.description or "Mind map is being generated",
                map_data={"nodes": [], "edges": []},
            )
            started = {"event": "generation_started", "status": "generating",
                       "message": "Generating mind map", "mind_map_id": mind_map.id}
            yield f"data: {json.dumps(started)}\n\n".encode()
            async for event in task_runner.stream_mind_map({
                "project_id": project_id, "mind_map_id": mind_map.id,
                "user_id": current_user.id,
                "topic": request.title or request.custom_instructions or "",
                "custom_instructions": request.custom_instructions or request.description,
            }):
                completed = event.get("event") == "mind_map_completed"
                payload = {"status": "done" if completed else "generating",
                           "message": "Mind map generated" if completed else "Generating mind map",
                           **event}
                yield f"data: {json.dumps(payload)}\n\n".encode()

        except NotFoundError as e:
            payload = {"event": "generation_failed", "status": "done",
                       "message": "Mind map generation failed", "error": str(e)}
            yield f"data: {json.dumps(payload)}\n\n".encode()
        except Exception as e:
            payload = {"event": "generation_failed", "status": "done",
                       "message": "Mind map generation failed", "error": str(e)}
            yield f"data: {json.dumps(payload)}\n\n".encode()

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


@router.post("/{mind_map_id}/generate/stream", status_code=200)
async def regenerate_mind_map_stream(
    project_id: str,
    mind_map_id: str,
    request: MindMapCreate,
    current_user: UserDto = Depends(get_current_user),
    service: MindMapService = Depends(get_mind_map_service),
    usage_service: UsageService = Depends(get_usage_service),
    task_runner: TaskRunnerService = Depends(get_task_runner),
):
    """Regenerate an existing mind map while streaming node/edge batches."""
    usage_service.check_and_increment(current_user.id, "mindmap_generation")

    async def generate_stream() -> AsyncGenerator[bytes]:
        try:
            service.get_mind_map(
                mind_map_id=mind_map_id,
                project_id=project_id,
                user_id=current_user.id,
            )
            started = {
                "event": "generation_started",
                "status": "generating",
                "message": "Generating mind map",
                "mind_map_id": mind_map_id,
            }
            yield f"data: {json.dumps(started)}\n\n".encode()
            async for event in task_runner.stream_mind_map({
                "project_id": project_id,
                "mind_map_id": mind_map_id,
                "user_id": current_user.id,
                "topic": request.title or request.custom_instructions or "",
                "custom_instructions": request.custom_instructions or request.description,
            }):
                completed = event.get("event") == "mind_map_completed"
                payload = {
                    "status": "done" if completed else "generating",
                    "message": "Mind map generated" if completed else "Generating mind map",
                    **event,
                }
                yield f"data: {json.dumps(payload)}\n\n".encode()
        except Exception as exc:
            payload = {
                "event": "generation_failed",
                "status": "done",
                "message": "Mind map generation failed",
                "error": str(exc),
            }
            yield f"data: {json.dumps(payload)}\n\n".encode()

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
