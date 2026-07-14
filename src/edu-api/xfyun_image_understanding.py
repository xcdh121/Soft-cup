"""Client for XFYun Spark image-understanding WebSocket API."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlencode, urlparse

from websockets.asyncio.client import connect


@dataclass(frozen=True)
class XfyunImageUnderstandingConfig:
    """Configuration for XFYun Spark's image-understanding endpoint."""

    enabled: bool = False
    app_id: str = ""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
    domain: str = "imagev3"
    timeout_seconds: float = 60.0
    max_tokens: int = 2048


class XfyunImageUnderstandingError(RuntimeError):
    """Raised when image understanding cannot return a usable result."""


def build_authenticated_url(
    base_url: str,
    *,
    api_key: str,
    api_secret: str,
    now: datetime | None = None,
) -> str:
    """Build the signed WebSocket URL required by XFYun."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        raise XfyunImageUnderstandingError("讯飞图片理解地址必须是有效的 ws/wss URL")

    host = parsed.netloc
    path = parsed.path or "/"
    request_date = format_datetime(now or datetime.now(UTC), usegmt=True)
    signature_origin = f"host: {host}\ndate: {request_date}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
        "ascii"
    )
    query = urlencode(
        {"authorization": authorization, "date": request_date, "host": host}
    )
    return f"{parsed.scheme}://{host}{path}?{query}"


def build_request_payload(
    *,
    app_id: str,
    image: bytes,
    question: str,
    domain: str,
    max_tokens: int,
    uid: str | None = None,
) -> dict[str, Any]:
    """Build the documented image-first multimodal request payload."""
    header: dict[str, str] = {"app_id": app_id}
    if uid:
        header["uid"] = uid[:32]
    return {
        "header": header,
        "parameter": {
            "chat": {
                "domain": domain,
                "temperature": 0.2,
                "top_k": 4,
                "max_tokens": max(1, min(max_tokens, 8192)),
            }
        },
        "payload": {
            "message": {
                "text": [
                    {
                        "role": "user",
                        "content": base64.b64encode(image).decode("ascii"),
                        "content_type": "image",
                    },
                    {
                        "role": "user",
                        "content": question,
                        "content_type": "text",
                    },
                ]
            }
        },
    }


class XfyunImageUnderstandingClient:
    """Async client that collects XFYun's streamed vision response."""

    def __init__(
        self,
        config: XfyunImageUnderstandingConfig,
        *,
        connector: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self._connector = connector or connect

    @property
    def is_enabled(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.app_id
            and self.config.api_key
            and self.config.api_secret
        )

    async def understand(
        self,
        image: bytes,
        *,
        question: str,
        uid: str | None = None,
    ) -> str:
        if not self.is_enabled:
            raise XfyunImageUnderstandingError("讯飞图片理解服务尚未配置")
        if not image:
            raise XfyunImageUnderstandingError("图片内容为空")

        url = build_authenticated_url(
            self.config.base_url,
            api_key=self.config.api_key,
            api_secret=self.config.api_secret,
        )
        payload = build_request_payload(
            app_id=self.config.app_id,
            image=image,
            question=question,
            domain=self.config.domain,
            max_tokens=self.config.max_tokens,
            uid=uid,
        )
        chunks: list[str] = []

        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                async with self._connector(url) as websocket:
                    await websocket.send(json.dumps(payload, ensure_ascii=False))
                    while True:
                        raw_message = await websocket.recv()
                        message = json.loads(raw_message)
                        if not isinstance(message, dict):
                            raise XfyunImageUnderstandingError(
                                "讯飞返回了无效的图片理解响应"
                            )
                        header = message.get("header") or {}
                        code = int(header.get("code", 0))
                        if code != 0:
                            detail = header.get("message") or "图片理解失败"
                            raise XfyunImageUnderstandingError(
                                f"{detail} (错误码 {code})"
                            )

                        choices = (message.get("payload") or {}).get("choices") or {}
                        for item in choices.get("text") or []:
                            if isinstance(item, dict) and item.get("content"):
                                chunks.append(str(item["content"]))
                        if choices.get("status") == 2 or header.get("status") == 2:
                            break
        except TimeoutError as exc:
            raise XfyunImageUnderstandingError(
                "讯飞图片理解请求超时, 请稍后重试"
            ) from exc
        except XfyunImageUnderstandingError:
            raise
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise XfyunImageUnderstandingError(
                "讯飞返回了无法解析的图片理解响应"
            ) from exc
        except Exception as exc:
            raise XfyunImageUnderstandingError("暂时无法连接讯飞图片理解服务") from exc

        result = "".join(chunks).strip()
        if not result:
            raise XfyunImageUnderstandingError("讯飞图片理解没有返回内容")
        return result
