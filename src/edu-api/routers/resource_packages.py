import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from auth import get_current_user
from code_execution import CodeExecutionError, execute_code
from config import Settings
from dependencies import get_resource_package_service, get_settings_dep
from edu_core.schemas.resource_packages import (
    GeneratedResourceDto,
    ProgrammingGradeDto,
    ProgrammingRunDto,
    ResourcePackageDto,
    ResourcePackageStreamEventDto,
)
from edu_core.services.resource_packages import ResourcePackageService
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from routers.schemas import (
    GenerateResourcePackageRequest,
    ImportResourceRequest,
    ProgrammingGradeRequest,
    ProgrammingRunRequest,
    UpdateGeneratedResourceRequest,
)

logger = logging.getLogger(__name__)
_BACKGROUND_RESOURCE_PACKAGE_TASKS: set[asyncio.Task[Any]] = set()


def _track_resource_package_task(task: asyncio.Task[Any]) -> None:
    """Keep generation alive after the start request returns its package URL."""
    _BACKGROUND_RESOURCE_PACKAGE_TASKS.add(task)

    def finish(completed_task: asyncio.Task[Any]) -> None:
        _BACKGROUND_RESOURCE_PACKAGE_TASKS.discard(completed_task)
        if completed_task.cancelled():
            return
        try:
            completed_task.result()
        except Exception:
            logger.exception("Background resource-package generation failed")

    task.add_done_callback(finish)

resource_packages_router = APIRouter(
    prefix="/api/v1/projects/{project_id}/resource-packages",
    tags=["Resource Packages"],
)


@resource_packages_router.get("", response_model=list[ResourcePackageDto])
def list_resource_packages(
    project_id: str,
    status: str | None = Query(None),
    generation_mode: str | None = Query(None),
    target_topic: str | None = Query(None),
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return service.list_resource_packages(
        user_id=user.id,
        project_id=project_id,
        status=status,
        generation_mode=generation_mode,
        target_topic=target_topic,
    )


@resource_packages_router.post(
    "/generate", response_model=ResourcePackageDto, status_code=status.HTTP_201_CREATED
)
async def generate_resource_package(
    project_id: str,
    request: GenerateResourcePackageRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return await service.generate_resource_package(
        user_id=user.id,
        project_id=project_id,
        payload=request.model_dump(),
    )


@resource_packages_router.post(
    "/generate/start",
    response_model=ResourcePackageDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_resource_package_generation(
    project_id: str,
    request: GenerateResourcePackageRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    """Create the durable package, then continue generation in the background."""
    loop = asyncio.get_running_loop()
    package_started: asyncio.Future[str] = loop.create_future()

    async def capture_start(event: ResourcePackageStreamEventDto) -> None:
        if event.event == "package_started" and not package_started.done():
            package_started.set_result(event.package_id)

    task = asyncio.create_task(
        service.generate_resource_package(
            user_id=user.id,
            project_id=project_id,
            payload=request.model_dump(),
            event_sink=capture_start,
        )
    )
    _track_resource_package_task(task)

    await asyncio.wait(
        {task, package_started},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if package_started.done():
        return service.get_resource_package(
            user.id, project_id, package_started.result()
        )
    return task.result()


@resource_packages_router.post(
    "/import", response_model=ResourcePackageDto, status_code=status.HTTP_201_CREATED
)
def import_resource_package(
    project_id: str,
    request: ImportResourceRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    """Persist an AI-assistant OCR or translation result as a resource package."""
    return service.import_resource(
        user_id=user.id,
        project_id=project_id,
        **request.model_dump(),
    )


@resource_packages_router.post("/generate/stream")
async def generate_resource_package_stream(
    project_id: str,
    request: GenerateResourcePackageRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    """Generate a package while streaming per-resource lifecycle events."""

    async def generate_stream() -> AsyncGenerator[bytes]:
        queue: asyncio.Queue[ResourcePackageStreamEventDto] = asyncio.Queue()
        last_package_id = ""
        task = asyncio.create_task(service.generate_resource_package(
            user_id=user.id,
            project_id=project_id,
            payload=request.model_dump(),
            event_sink=queue.put,
        ))
        try:
            while not task.done() or not queue.empty():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                last_package_id = event.package_id or last_package_id
                yield f"data: {event.model_dump_json()}\n\n".encode()
            await task
        except Exception as exc:
            event = ResourcePackageStreamEventDto(
                event="package_failed",
                package_id=last_package_id,
                timestamp=datetime.now(UTC),
                payload={"status": "failed", "error": str(exc)},
            )
            yield f"data: {event.model_dump_json()}\n\n".encode()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@resource_packages_router.get("/{package_id}", response_model=ResourcePackageDto)
def get_resource_package(
    project_id: str,
    package_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return service.get_resource_package(user.id, project_id, package_id)


@resource_packages_router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource_package(
    project_id: str,
    package_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    service.delete_resource_package(user.id, project_id, package_id)
    return None


@resource_packages_router.get(
    "/{package_id}/resources", response_model=list[GeneratedResourceDto]
)
def list_generated_resources(
    project_id: str,
    package_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return service.list_generated_resources(user.id, project_id, package_id)


@resource_packages_router.get("/{package_id}/stream")
async def stream_resource_package(
    project_id: str,
    package_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    async def generate_stream() -> AsyncGenerator[bytes]:
        async for event in service.stream_resource_package_events(
            user.id, project_id, package_id
        ):
            yield f"data: {event.model_dump_json()}\n\n".encode()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


generated_resources_router = APIRouter(
    prefix="/api/v1/projects/{project_id}/generated-resources",
    tags=["Generated Resources"],
)


@generated_resources_router.get("/by-target/note/{target_id}/stream")
async def stream_generated_note_by_target(
    project_id: str,
    target_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    resource = service.get_generated_resource_by_target(
        user.id, project_id, "note", target_id
    )

    async def generate_stream() -> AsyncGenerator[bytes]:
        async for snapshot in service.stream_generated_note_snapshots(
            user.id, project_id, resource.id, target_id
        ):
            yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n".encode()

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@generated_resources_router.get(
    "/by-target/{target_type}/{target_id}", response_model=GeneratedResourceDto
)
def get_generated_resource_by_target(
    project_id: str,
    target_type: str,
    target_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return service.get_generated_resource_by_target(
        user.id, project_id, target_type, target_id
    )


@generated_resources_router.get("/{resource_id}", response_model=GeneratedResourceDto)
def get_generated_resource(
    project_id: str,
    resource_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return service.get_generated_resource(user.id, project_id, resource_id)


@generated_resources_router.patch("/{resource_id}", response_model=GeneratedResourceDto)
def update_generated_resource(
    project_id: str,
    resource_id: str,
    request: UpdateGeneratedResourceRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return service.update_generated_resource(
        user.id, project_id, resource_id, request.model_dump(exclude_none=True)
    )


@generated_resources_router.post(
    "/{resource_id}/programming-grade", response_model=ProgrammingGradeDto
)
async def grade_programming_answer(
    project_id: str,
    resource_id: str,
    request: ProgrammingGradeRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    try:
        return await service.grade_programming_answer(
            user_id=user.id,
            project_id=project_id,
            resource_id=resource_id,
            question_id=request.question_id,
            answer=request.answer,
            language=request.language,
        )
    except RuntimeError as exc:
        logger.exception("AI programming grading failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 判题服务暂时不可用，请稍后重试。",
        ) from exc


@generated_resources_router.post(
    "/{resource_id}/programming-run", response_model=ProgrammingRunDto
)
async def run_programming_answer(
    project_id: str,
    resource_id: str,
    run_request: ProgrammingRunRequest,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
    settings: Settings = Depends(get_settings_dep),
):
    resource = service.get_generated_resource(user.id, project_id, resource_id)
    if resource.resource_type != "programming_questions":
        raise HTTPException(status_code=400, detail="所选资源不是编程题。")

    questions = (resource.content_json or {}).get("questions", [])
    if not any(
        isinstance(question, dict)
        and str(question.get("id")) == run_request.question_id
        for question in questions
    ):
        raise HTTPException(status_code=404, detail="未找到对应的编程题。")
    if not settings.code_execution_api_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="代码运行服务尚未配置，请联系管理员设置 CODE_EXECUTION_API_URL。",
        )

    try:
        result = await execute_code(
            api_url=settings.code_execution_api_url,
            api_token=settings.code_execution_api_token,
            language=run_request.language,
            code=run_request.code,
            stdin=run_request.stdin,
            timeout_seconds=settings.code_execution_timeout_seconds,
        )
    except CodeExecutionError as exc:
        logger.warning("Sandboxed code execution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ProgrammingRunDto(**result.__dict__)


@generated_resources_router.post(
    "/{resource_id}/regenerate", response_model=GeneratedResourceDto
)
async def regenerate_generated_resource(
    project_id: str,
    resource_id: str,
    user=Depends(get_current_user),
    service: ResourcePackageService = Depends(get_resource_package_service),
):
    return await service.regenerate_generated_resource(
        user.id, project_id, resource_id
    )
