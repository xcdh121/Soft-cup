"""Project-scoped handwriting recognition endpoint."""

from typing import Any, Literal

from auth import get_current_user
from config import Settings
from dependencies import get_project_service, get_settings_dep
from edu_core.exceptions import NotFoundError
from edu_core.schemas.users import UserDto
from edu_core.services import ProjectService
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from xfyun_handwriting import (
    XfyunHandwritingClient,
    XfyunHandwritingConfig,
    XfyunHandwritingError,
)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/handwriting-recognition",
    tags=["handwriting-recognition"],
)

MAX_IMAGE_BYTES = 4 * 1024 * 1024
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/bmp", "image/x-ms-bmp"}


class HandwritingLineDto(BaseModel):
    text: str
    confidence: float | int | None = None
    location: dict[str, Any] | None = None


class HandwritingRecognitionDto(BaseModel):
    text: str
    lines: list[HandwritingLineDto]
    sid: str | None = None


@router.post("/recognize", response_model=HandwritingRecognitionDto)
async def recognize_handwriting(
    project_id: str,
    image: UploadFile = File(...),
    language: Literal["en", "cn|en"] = Form("cn|en"),
    include_location: bool = Form(False),
    current_user: UserDto = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    settings: Settings = Depends(get_settings_dep),
) -> HandwritingRecognitionDto:
    """Recognize handwritten text in a JPG, PNG, or BMP image."""
    try:
        project_service.get_project(project_id=project_id, owner_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if image.content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 JPG、PNG、BMP 图片")

    content = await image.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="上传的图片为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片大小不能超过 4MB")

    client = XfyunHandwritingClient(
        XfyunHandwritingConfig(
            enabled=settings.xfyun_handwriting_enabled,
            app_id=settings.xfyun_handwriting_app_id,
            api_key=settings.xfyun_handwriting_api_key,
            base_url=settings.xfyun_handwriting_base_url,
            timeout_seconds=settings.xfyun_handwriting_timeout_seconds,
        )
    )
    try:
        result = await client.recognize(
            content,
            language=language,
            include_location=include_location,
        )
    except XfyunHandwritingError as exc:
        status_code = 503 if not client.is_enabled else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return HandwritingRecognitionDto.model_validate(result)
