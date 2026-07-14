import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

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
                yield f"data: {event.model_dump_json()}\n\n".encode("utf-8")
            await task
        except Exception as exc:
            event = ResourcePackageStreamEventDto(
                event="package_failed",
                package_id="",
                timestamp=datetime.now(timezone.utc),
                payload={"status": "failed", "error": str(exc)},
            )
            yield f"data: {event.model_dump_json()}\n\n".encode("utf-8")

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
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
            yield f"data: {event.model_dump_json()}\n\n".encode("utf-8")

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


generated_resources_router = APIRouter(
    prefix="/api/v1/projects/{project_id}/generated-resources",
    tags=["Generated Resources"],
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
