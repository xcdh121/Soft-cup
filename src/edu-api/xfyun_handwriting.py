"""Client and response normalization for XFYun handwriting OCR."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from hashlib import md5
from typing import Any

import httpx


@dataclass(frozen=True)
class XfyunHandwritingConfig:
    """Configuration for the legacy XFYun handwriting OCR endpoint."""

    enabled: bool = False
    app_id: str = ""
    api_key: str = ""
    base_url: str = "https://webapi.xfyun.cn/v1/service/v1/ocr/handwriting"
    timeout_seconds: float = 30.0


class XfyunHandwritingError(RuntimeError):
    """Raised when XFYun rejects a request or returns an invalid payload."""


def _build_auth_headers(
    *,
    app_id: str,
    api_key: str,
    language: str,
    include_location: bool,
    current_time: int | None = None,
) -> dict[str, str]:
    timestamp = str(current_time if current_time is not None else int(time.time()))
    parameters = json.dumps(
        {
            "language": language,
            "location": "true" if include_location else "false",
        },
        separators=(",", ":"),
    )
    encoded_parameters = base64.b64encode(parameters.encode("utf-8")).decode("ascii")
    # MD5 is mandated by this legacy API and is not used for password storage.
    checksum = md5(
        f"{api_key}{timestamp}{encoded_parameters}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    return {
        "X-Appid": app_id,
        "X-CurTime": timestamp,
        "X-Param": encoded_parameters,
        "X-CheckSum": checksum,
    }


def _normalize_response(payload: dict[str, Any]) -> dict[str, Any]:
    code = str(payload.get("code", ""))
    if code != "0":
        description = str(payload.get("desc") or "讯飞手写笔记识别失败")
        raise XfyunHandwritingError(f"{description} (错误码 {code or 'unknown'})")

    data = payload.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise XfyunHandwritingError("讯飞返回了无法解析的识别结果") from exc
    if not isinstance(data, dict):
        raise XfyunHandwritingError("讯飞返回了无效的识别结果")

    normalized_lines: list[dict[str, Any]] = []
    for block in data.get("block") or []:
        if not isinstance(block, dict):
            continue
        for line in block.get("line") or []:
            if not isinstance(line, dict):
                continue
            words = line.get("word") or []
            text = "".join(
                str(word.get("content", "")) for word in words if isinstance(word, dict)
            ).strip()
            if not text:
                continue
            confidence = line.get("confidence")
            if isinstance(confidence, str):
                try:
                    confidence = float(confidence)
                except ValueError:
                    confidence = None
            if not isinstance(confidence, int | float):
                confidence = None
            location = line.get("location")
            if not isinstance(location, dict):
                location = None
            normalized_lines.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "location": location,
                }
            )

    return {
        "text": "\n".join(line["text"] for line in normalized_lines),
        "lines": normalized_lines,
        "sid": payload.get("sid"),
    }


class XfyunHandwritingClient:
    """Small async client for XFYun's form-encoded handwriting OCR API."""

    def __init__(
        self,
        config: XfyunHandwritingConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    @property
    def is_enabled(self) -> bool:
        return bool(self.config.enabled and self.config.app_id and self.config.api_key)

    async def recognize(
        self,
        image: bytes,
        *,
        language: str = "cn|en",
        include_location: bool = False,
    ) -> dict[str, Any]:
        if not self.is_enabled:
            raise XfyunHandwritingError("手写笔记识别服务尚未配置")
        if language not in {"en", "cn|en"}:
            raise XfyunHandwritingError("不支持的识别语言")

        headers = _build_auth_headers(
            app_id=self.config.app_id,
            api_key=self.config.api_key,
            language=language,
            include_location=include_location,
        )
        encoded_image = base64.b64encode(image).decode("ascii")

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self.config.base_url,
                    headers=headers,
                    data={"image": encoded_image},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise XfyunHandwritingError("手写笔记识别请求超时, 请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise XfyunHandwritingError("暂时无法连接手写笔记识别服务") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise XfyunHandwritingError("讯飞返回了无法解析的响应") from exc
        if not isinstance(payload, dict):
            raise XfyunHandwritingError("讯飞返回了无效的响应")
        return _normalize_response(payload)
