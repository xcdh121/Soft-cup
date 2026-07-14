"""Router for chat CRUD operations."""

import base64
import binascii
from collections.abc import AsyncGenerator
from typing import Any

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
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    user_id: str,
    image_client: XfyunImageUnderstandingClient,
) -> list[dict[str, Any]]:
    """Turn uploaded images into grounded text context for the text-only LLM."""
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

        processed_parts.append(
            {
                "type": "file",
                "file_name": filename,
                "file_type": part.media_type,
                "file_url": "",
            }
        )
        processed_parts.append(
            {
                "type": "text",
                "text": f"{VISION_CONTEXT_PREFIX}{filename}]\n{description}",
            }
        )

    return processed_parts


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
        user_id=user_id,
        image_client=image_client,
    )

    async def generate_stream() -> AsyncGenerator[bytes]:
        """Generate streaming response chunks - each part as a separate SSE event"""
        async for part_event in chat_service.stream_chat_events(
            chat_id, user_id, processed_parts
        ):
            part_json = part_event.model_dump_json()
            yield f"data: {part_json}\n\n".encode("utf-8")

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
