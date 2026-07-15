"""Client for XFYun Machine Translation (New)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class XfyunTranslationConfig:
    enabled: bool = False
    app_id: str = ""
    api_key: str = ""
    api_secret: str = ""
    base_url: str = "https://itrans.xf-yun.com/v1/its"
    timeout_seconds: float = 30.0


class XfyunTranslationError(RuntimeError):
    """Raised when the translation service rejects or malforms a request."""


def _build_auth_params(
    *,
    base_url: str,
    api_key: str,
    api_secret: str,
    current_date: datetime | None = None,
) -> dict[str, str]:
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


def _decode_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise XfyunTranslationError("讯飞返回了无效的翻译响应")
    header = payload.get("header")
    if not isinstance(header, dict):
        raise XfyunTranslationError("讯飞返回的翻译响应缺少状态信息")
    code = header.get("code")
    if str(code) != "0":
        message = str(header.get("message") or "讯飞文档翻译失败")
        raise XfyunTranslationError(f"{message} (错误码 {code})")

    try:
        encoded = payload["payload"]["result"]["text"]
        decoded = base64.b64decode(encoded).decode("utf-8")
        result = json.loads(decoded)
        translation = result["trans_result"]
        source = str(translation["src"])
        target = str(translation["dst"])
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise XfyunTranslationError("讯飞返回了无法解析的翻译结果") from exc
    return {
        "source_text": source,
        "translated_text": target,
        "from_language": str(result.get("from") or ""),
        "to_language": str(result.get("to") or ""),
        "sid": header.get("sid"),
    }


class XfyunTranslationClient:
    def __init__(
        self,
        config: XfyunTranslationConfig,
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

    async def translate(
        self,
        text: str,
        *,
        from_language: str,
        to_language: str,
        resource_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_enabled:
            raise XfyunTranslationError("文档翻译服务尚未配置")
        if not text.strip():
            raise XfyunTranslationError("待翻译内容不能为空")
        if len(text) > 5_000:
            raise XfyunTranslationError("单次翻译内容不能超过 5000 个字符")
        if from_language == to_language:
            raise XfyunTranslationError("源语言与目标语言不能相同")

        header: dict[str, Any] = {"app_id": self.config.app_id, "status": 3}
        if resource_id:
            header["res_id"] = resource_id
        request_body = {
            "header": header,
            "parameter": {
                "its": {
                    "from": from_language,
                    "to": to_language,
                    "result": {},
                }
            },
            "payload": {
                "input_data": {
                    "encoding": "utf8",
                    "status": 3,
                    "text": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                }
            },
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self.config.base_url,
                    params=_build_auth_params(
                        base_url=self.config.base_url,
                        api_key=self.config.api_key,
                        api_secret=self.config.api_secret,
                    ),
                    json=request_body,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise XfyunTranslationError("文档翻译请求超时, 请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise XfyunTranslationError("暂时无法连接文档翻译服务") from exc

        try:
            return _decode_result(response.json())
        except ValueError as exc:
            raise XfyunTranslationError("讯飞返回了无法解析的响应") from exc
