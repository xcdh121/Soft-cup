"""Server-side client for XFYun Spark text-to-image generation."""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

SUPPORTED_RESOLUTIONS = {
    (512, 512),
    (640, 360),
    (640, 480),
    (640, 640),
    (680, 512),
    (512, 680),
    (768, 768),
    (720, 1280),
    (1280, 720),
    (1024, 1024),
}


@dataclass(frozen=True, slots=True)
class XfyunImageGenerationConfig:
    enabled: bool = False
    app_id: str = ""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti"
    timeout_seconds: float = 120.0
    default_width: int = 512
    default_height: int = 512


class XfyunImageGenerationError(RuntimeError):
    """Raised when the image-generation service rejects or malforms a request."""


def build_auth_params(
    *,
    base_url: str,
    api_key: str,
    api_secret: str,
    current_date: datetime | None = None,
) -> dict[str, str]:
    """Build the HMAC-SHA256 query parameters required by XFYun."""
    parsed = urlsplit(base_url)
    host = parsed.netloc
    path = parsed.path or "/"
    date = format_datetime(current_date or datetime.now(UTC), usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nPOST {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
        "ascii"
    )
    return {"authorization": authorization, "host": host, "date": date}


def _decode_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise XfyunImageGenerationError("讯飞返回了无效的图片生成响应")
    header = payload.get("header")
    if not isinstance(header, dict):
        raise XfyunImageGenerationError("讯飞图片生成响应缺少状态信息")
    code = header.get("code")
    if str(code) != "0":
        message = str(header.get("message") or "讯飞图片生成失败")
        raise XfyunImageGenerationError(f"{message} (错误码 {code})")

    try:
        choices = payload["payload"]["choices"]
        encoded = choices["text"][0]["content"]
        image_bytes = base64.b64decode(encoded, validate=True)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise XfyunImageGenerationError("讯飞返回了无法解析的图片结果") from exc
    if not image_bytes:
        raise XfyunImageGenerationError("讯飞返回的图片内容为空")
    return {
        "image_bytes": image_bytes,
        "sid": header.get("sid"),
        "status": choices.get("status"),
        "seq": choices.get("seq"),
    }


class XfyunImageGenerationClient:
    def __init__(
        self,
        config: XfyunImageGenerationConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    @property
    def is_enabled(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.app_id
            and self.config.api_key
            and self.config.api_secret
        )

    async def generate(
        self,
        prompt: str,
        *,
        width: int | None = None,
        height: int | None = None,
        uid: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled:
            raise XfyunImageGenerationError("讯飞图片生成服务尚未配置")
        prompt = prompt.strip()
        if not prompt:
            raise XfyunImageGenerationError("图片描述不能为空")
        if len(prompt) > 1000:
            raise XfyunImageGenerationError("图片描述不能超过 1000 个字符")

        resolved_width = width or self.config.default_width
        resolved_height = height or self.config.default_height
        if (resolved_width, resolved_height) not in SUPPORTED_RESOLUTIONS:
            raise XfyunImageGenerationError(
                f"不支持的图片分辨率: {resolved_width}x{resolved_height}"
            )

        header: dict[str, str] = {"app_id": self.config.app_id}
        if uid:
            header["uid"] = uid[:32]
        request_body = {
            "header": header,
            "parameter": {
                "chat": {
                    "domain": "general",
                    "width": resolved_width,
                    "height": resolved_height,
                }
            },
            "payload": {"message": {"text": [{"role": "user", "content": prompt}]}},
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self.config.base_url,
                    params=build_auth_params(
                        base_url=self.config.base_url,
                        api_key=self.config.api_key,
                        api_secret=self.config.api_secret,
                    ),
                    json=request_body,
                    headers={"Content-Type": "application/json;charset=UTF-8"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise XfyunImageGenerationError("图片生成请求超时, 请稍后重试") from exc
        except httpx.HTTPStatusError as exc:
            try:
                message = str(exc.response.json().get("message") or "")
            except (ValueError, AttributeError):
                message = ""
            detail = f": {message}" if message else ""
            raise XfyunImageGenerationError(
                f"讯飞图片生成鉴权或请求失败 (HTTP {exc.response.status_code}){detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise XfyunImageGenerationError("暂时无法连接讯飞图片生成服务") from exc

        try:
            result = _decode_response(response.json())
        except ValueError as exc:
            raise XfyunImageGenerationError("讯飞返回了无法解析的响应") from exc
        return {
            **result,
            "width": resolved_width,
            "height": resolved_height,
        }
