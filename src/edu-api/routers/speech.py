"""Router for speech-related helper endpoints."""

import base64
import hmac
from email.utils import formatdate
from hashlib import sha256
from urllib.parse import urlencode

from auth import get_current_user
from config import Settings
from dependencies import get_settings_dep
from edu_core.schemas.users import UserDto
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])


class XfyunIatUrlDto(BaseModel):
    """Signed WebSocket connection details for XFYun IAT."""

    url: str
    app_id: str
    expires_in_seconds: int


@router.get("/xfyun-iat-url", response_model=XfyunIatUrlDto)
async def get_xfyun_iat_url(
    _current_user: UserDto = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> XfyunIatUrlDto:
    """Create a short-lived signed WebSocket URL for XFYun IAT."""
    if not settings.xfyun_iat_enabled:
        raise HTTPException(status_code=503, detail="XFYun IAT is not enabled")
    if not (
        settings.xfyun_iat_app_id
        and settings.xfyun_iat_api_key
        and settings.xfyun_iat_api_secret
    ):
        raise HTTPException(status_code=503, detail="XFYun IAT is not configured")

    host = settings.xfyun_iat_host
    path = settings.xfyun_iat_path if settings.xfyun_iat_path.startswith("/") else f"/{settings.xfyun_iat_path}"
    date = formatdate(usegmt=True)
    request_line = f"GET {path} HTTP/1.1"
    signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
    signature_sha = hmac.new(
        settings.xfyun_iat_api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{settings.xfyun_iat_api_key}", '
        'algorithm="hmac-sha256", '
        'headers="host date request-line", '
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(
        authorization_origin.encode("utf-8")
    ).decode("utf-8")
    query = urlencode(
        {
            "authorization": authorization,
            "date": date,
            "host": host,
        }
    )

    return XfyunIatUrlDto(
        url=f"wss://{host}{path}?{query}",
        app_id=settings.xfyun_iat_app_id,
        expires_in_seconds=300,
    )
