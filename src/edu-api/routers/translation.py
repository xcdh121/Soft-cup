"""Project-scoped XFYun document translation endpoint."""

from auth import get_current_user
from config import Settings
from dependencies import get_project_service, get_settings_dep
from edu_core.exceptions import NotFoundError
from edu_core.schemas.users import UserDto
from edu_core.services import ProjectService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from xfyun_translation import (
    XfyunTranslationClient,
    XfyunTranslationConfig,
    XfyunTranslationError,
)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/document-translation",
    tags=["document-translation"],
)

MAX_DOCUMENT_CHARACTERS = 50_000
CHUNK_CHARACTERS = 4_500


class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_DOCUMENT_CHARACTERS)
    from_language: str = Field(..., min_length=2, max_length=8)
    to_language: str = Field(..., min_length=2, max_length=8)
    resource_id: str | None = Field(None, max_length=100)


class TranslationDto(BaseModel):
    source_text: str
    translated_text: str
    from_language: str
    to_language: str
    sid: str | None = None
    chunk_count: int


def _split_text(text: str) -> list[str]:
    """Split long documents near line boundaries within provider limits."""
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= CHUNK_CHARACTERS:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, CHUNK_CHARACTERS + 1)
        if cut < CHUNK_CHARACTERS // 2:
            cut = remaining.rfind("。", 0, CHUNK_CHARACTERS + 1)
            if cut >= CHUNK_CHARACTERS // 2:
                cut += 1
        if cut < CHUNK_CHARACTERS // 2:
            cut = CHUNK_CHARACTERS
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    return chunks


@router.post("/translate", response_model=TranslationDto)
async def translate_document(
    project_id: str,
    request: TranslationRequest,
    current_user: UserDto = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    settings: Settings = Depends(get_settings_dep),
) -> TranslationDto:
    try:
        project_service.get_project(project_id=project_id, owner_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request.from_language == request.to_language:
        raise HTTPException(status_code=400, detail="源语言与目标语言不能相同")

    client = XfyunTranslationClient(
        XfyunTranslationConfig(
            enabled=settings.xfyun_translation_enabled,
            app_id=settings.xfyun_translation_app_id,
            api_key=settings.xfyun_translation_api_key,
            api_secret=settings.xfyun_translation_api_secret,
            base_url=settings.xfyun_translation_base_url,
            timeout_seconds=settings.xfyun_translation_timeout_seconds,
        )
    )
    chunks = _split_text(request.text)
    translated_chunks: list[str] = []
    sid: str | None = None
    try:
        for chunk in chunks:
            result = await client.translate(
                chunk,
                from_language=request.from_language,
                to_language=request.to_language,
                resource_id=request.resource_id,
            )
            translated_chunks.append(result["translated_text"])
            sid = sid or result.get("sid")
    except XfyunTranslationError as exc:
        raise HTTPException(
            status_code=503 if not client.is_enabled else 502,
            detail=str(exc),
        ) from exc

    return TranslationDto(
        source_text=request.text,
        translated_text="".join(translated_chunks),
        from_language=request.from_language,
        to_language=request.to_language,
        sid=sid,
        chunk_count=len(chunks),
    )
