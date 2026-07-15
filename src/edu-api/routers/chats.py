"""Router for chat CRUD operations."""
# ruff: noqa: RUF001

import asyncio
import base64
import binascii
import mimetypes
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any
from urllib.parse import quote, unquote

from auth import get_current_user
from dependencies import (
    get_chat_service,
    get_usage_service,
    get_xfyun_image_understanding_client,
)
from edu_core.exceptions import NotFoundError
from edu_core.schemas.chats import (
    ChatDetailDto,
    ChatDto,
)
from edu_core.schemas.users import UserDto
from edu_core.services import ChatService, UsageService
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from xfyun_image_understanding import (
    XfyunImageUnderstandingClient,
    XfyunImageUnderstandingError,
)

from routers.schemas import (
    ChatCompletionRequest,
    ChatCreate,
    ChatUpdate,
    FilePart,
    TextPart,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/chats", tags=["chats"])

MAX_VISION_IMAGE_BYTES = 4 * 1024 * 1024
MAX_CHAT_PDF_BYTES = 100 * 1024 * 1024
MAX_CHAT_PDF_PAGES = 100
SUPPORTED_VISION_IMAGE_TYPES = {"image/jpeg", "image/png"}
VISION_CONTEXT_PREFIX = "[图片理解上下文:"


def _decode_image_data_url(part: FilePart) -> bytes:
    """Validate and decode an image attachment without fetching remote URLs."""
    media_type = part.media_type.lower().strip()
    if media_type not in SUPPORTED_VISION_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="AI 导师图片理解目前仅支持 JPG、JPEG 和 PNG",
        )
    if not part.url.startswith("data:") or "," not in part.url:
        raise HTTPException(status_code=400, detail="图片附件必须使用 data URL 上传")

    metadata, encoded = part.url.split(",", 1)
    expected_prefix = f"data:{media_type};base64"
    if metadata.lower() != expected_prefix:
        raise HTTPException(status_code=400, detail="图片类型与附件内容不匹配")
    try:
        image = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="图片附件编码无效") from exc
    if not image:
        raise HTTPException(status_code=400, detail="图片附件内容为空")
    if len(image) > MAX_VISION_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片大小不能超过 4 MB")
    return image


async def _prepare_chat_parts(
    body: ChatCompletionRequest,
    *,
    project_id: str,
    chat_id: str,
    user_id: str,
    chat_service: ChatService,
    image_client: XfyunImageUnderstandingClient,
) -> list[dict[str, Any]]:
    """Turn attachments into persisted files and grounded text-only context."""
    user_question = "\n".join(
        part.text.strip()
        for part in body.parts
        if isinstance(part, TextPart) and part.text.strip()
    )
    processed_parts: list[dict[str, Any]] = []

    for part in body.parts:
        if isinstance(part, TextPart):
            processed_parts.append(part.model_dump())
            continue

        media_type = part.media_type.lower().strip()
        if media_type == "application/pdf":
            expected_prefix = f"/api/v1/projects/{project_id}/chats/{chat_id}/files/"
            if not part.url.startswith(expected_prefix):
                raise HTTPException(
                    status_code=400,
                    detail="PDF 附件必须先通过 AI 导师上传接口处理",
                )
            file_key = unquote(part.url.removeprefix(expected_prefix))
            try:
                storage_path = chat_service.resolve_chat_file(
                    project_id=project_id,
                    chat_id=chat_id,
                    file_key=file_key,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="PDF 附件地址无效") from exc
            if not storage_path.is_file():
                raise HTTPException(status_code=400, detail="PDF 附件不存在或已失效")
            processed_parts.append(
                {
                    "type": "file",
                    "file_name": part.filename or file_key,
                    "file_type": "application/pdf",
                    "file_url": part.url,
                }
            )
            continue

        image = _decode_image_data_url(part)
        filename = part.filename or "image"
        vision_question = (
            "请为 AI 导师准确、详细地分析这张图片。识别其中的文字、数学公式、"
            "图表、对象、空间关系和关键信息; 不要猜测看不清的内容。"
        )
        if user_question:
            vision_question += f"\n用户希望解决的问题: {user_question}"
        try:
            description = await image_client.understand(
                image,
                question=vision_question,
                uid=user_id,
            )
        except XfyunImageUnderstandingError as exc:
            status_code = 503 if not image_client.is_enabled else 502
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

        relative_path = await asyncio.to_thread(
            chat_service.upload_chat_file,
            image,
            filename,
            project_id,
            chat_id,
        )
        file_key = relative_path.rsplit("/", 1)[-1]
        file_url = (
            f"/api/v1/projects/{project_id}/chats/{chat_id}/files/"
            f"{quote(file_key, safe='')}"
        )

        processed_parts.append(
            {
                "type": "file",
                "file_name": filename,
                "file_type": part.media_type,
                "file_url": file_url,
            }
        )
        processed_parts.append(
            {
                "type": "text",
                "text": f"{VISION_CONTEXT_PREFIX}{filename}]\n{description}",
            }
        )

    return processed_parts


def _validate_chat_pdf(content: bytes) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="上传的 PDF 文件为空")
    if len(content) > MAX_CHAT_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF 文件大小不能超过 100MB")
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise HTTPException(
                status_code=400,
                detail="暂不支持带密码保护或权限加密的 PDF 文件",
            )
        page_count = len(reader.pages)
    except HTTPException:
        raise
    except (PdfReadError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail="PDF 文件损坏或无法读取") from exc
    if page_count == 0:
        raise HTTPException(status_code=400, detail="PDF 文件没有可识别的页面")
    if page_count > MAX_CHAT_PDF_PAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"单个 PDF 最多支持 {MAX_CHAT_PDF_PAGES} 页，当前文件共 {page_count} 页"
            ),
        )


@router.post("", response_model=ChatDto, status_code=201)
async def create_chat(
    project_id: str,
    chat: ChatCreate,
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """Create a new chat."""
    try:
        return service.create_chat(
            project_id=project_id,
            user_id=current_user.id,
            title=chat.title,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{chat_id}", response_model=ChatDetailDto)
async def get_chat(
    project_id: str,
    chat_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """Get a chat by ID with messages and parts."""
    try:
        return service.get_chat(
            chat_id=chat_id, user_id=current_user.id, include_messages=True
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{chat_id}/files", status_code=201)
async def upload_chat_pdf(
    project_id: str,
    chat_id: str,
    file: UploadFile = File(...),
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """Persist a validated PDF before its OCR context is sent to the tutor."""
    try:
        chat = service.get_chat(chat_id=chat_id, user_id=current_user.id)
        if chat.project_id != project_id:
            raise NotFoundError(f"Chat {chat_id} not found")
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = file.filename or "document.pdf"
    if file.content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="AI 导师文档附件仅支持 PDF")
    content = await file.read(MAX_CHAT_PDF_BYTES + 1)
    _validate_chat_pdf(content)
    relative_path = await asyncio.to_thread(
        service.upload_chat_file,
        content,
        filename,
        project_id,
        chat_id,
    )
    file_key = relative_path.rsplit("/", 1)[-1]
    return {
        "file_name": filename,
        "file_type": "application/pdf",
        "file_url": (
            f"/api/v1/projects/{project_id}/chats/{chat_id}/files/"
            f"{quote(file_key, safe='')}"
        ),
    }


@router.get("/{chat_id}/files/{file_key}")
async def get_chat_file(
    project_id: str,
    chat_id: str,
    file_key: str,
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """Serve a persisted chat attachment after checking chat ownership."""
    try:
        chat = service.get_chat(chat_id=chat_id, user_id=current_user.id)
        if chat.project_id != project_id:
            raise NotFoundError(f"Chat {chat_id} not found")
        storage_path = service.resolve_chat_file(
            project_id=project_id,
            chat_id=chat_id,
            file_key=file_key,
        )
        if not storage_path.is_file():
            raise HTTPException(status_code=404, detail="Chat file not found")
        media_type, _ = mimetypes.guess_type(file_key)
        return FileResponse(
            path=storage_path,
            media_type=media_type or "application/octet-stream",
            content_disposition_type="inline",
            headers={
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except (NotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Chat file not found") from exc


@router.get("", response_model=list[ChatDto])
async def list_chats(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """List all chats for a project."""
    try:
        return service.list_chats(project_id=project_id, user_id=current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{chat_id}", response_model=ChatDto)
async def update_chat(
    project_id: str,
    chat_id: str,
    chat: ChatUpdate,
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """Update a chat."""
    try:
        return service.update_chat(
            chat_id=chat_id,
            user_id=current_user.id,
            title=chat.title,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    project_id: str,
    chat_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    """Delete a chat."""
    try:
        service.delete_chat(chat_id=chat_id, user_id=current_user.id)
        return None
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{chat_id}/messages/stream",
    status_code=200,
    summary="Send a streaming message to a chat",
    description="Send a message to a chat with streaming response",
)
async def send_streaming_message(
    project_id: str,
    chat_id: str,
    body: ChatCompletionRequest,
    current_user: UserDto = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    usage_service: UsageService = Depends(get_usage_service),
    image_client: XfyunImageUnderstandingClient = Depends(
        get_xfyun_image_understanding_client
    ),
):
    """Send a streaming message to a chat."""
    user_id = current_user.id

    # Check usage limit before processing
    usage_service.check_and_increment(user_id, "chat_message")

    processed_parts = await _prepare_chat_parts(
        body,
        project_id=project_id,
        chat_id=chat_id,
        user_id=user_id,
        chat_service=chat_service,
        image_client=image_client,
    )

    async def generate_stream() -> AsyncGenerator[bytes]:
        """Generate streaming response chunks - each part as a separate SSE event"""
        async for part_event in chat_service.stream_chat_events(
            chat_id, user_id, processed_parts
        ):
            part_json = part_event.model_dump_json()
            yield f"data: {part_json}\n\n".encode()

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
