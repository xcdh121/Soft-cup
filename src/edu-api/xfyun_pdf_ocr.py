"""Client for XFYun's asynchronous PDF OCR service."""

from __future__ import annotations

import base64
import hmac
import time
from dataclasses import dataclass
from hashlib import md5, sha1
from typing import Any, Literal

import httpx

PdfExportFormat = Literal["word", "markdown", "json"]


@dataclass(frozen=True)
class XfyunPdfOcrConfig:
    """Server-side credentials and transport settings for PDF OCR."""

    enabled: bool = False
    app_id: str = ""
    secret: str = ""
    base_url: str = "https://iocr.xfyun.cn/ocrzdq/v1/pdfOcr"
    timeout_seconds: float = 120.0


class XfyunPdfOcrError(RuntimeError):
    """Raised when XFYun rejects a PDF OCR request."""


def _build_auth_headers(
    *, app_id: str, secret: str, current_time: int | None = None
) -> dict[str, str]:
    timestamp = str(current_time if current_time is not None else int(time.time()))
    # The provider specification requires MD5 followed by HMAC-SHA1.
    auth = md5(
        f"{app_id}{timestamp}".encode("utf-8"), usedforsecurity=False
    ).hexdigest()
    signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), auth.encode("utf-8"), sha1).digest()
    ).decode("ascii")
    return {"appId": app_id, "timestamp": timestamp, "signature": signature}


def _response_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise XfyunPdfOcrError("讯飞返回了无效的响应")
    code = payload.get("code")
    if payload.get("flag") is not True or str(code) != "0":
        description = str(payload.get("desc") or "讯飞 PDF 文档识别失败")
        error_code = code if code is not None else "unknown"
        raise XfyunPdfOcrError(f"{description}（错误码 {error_code}）")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise XfyunPdfOcrError("讯飞返回了无效的任务数据")
    return data


def _normalize_task(data: dict[str, Any]) -> dict[str, Any]:
    task_no = str(data.get("taskNo") or "").strip()
    status = str(data.get("status") or "").upper()
    if not task_no or not status:
        raise XfyunPdfOcrError("讯飞返回的任务信息不完整")

    pages: list[dict[str, Any]] = []
    for page in data.get("pageList") or []:
        if not isinstance(page, dict):
            continue
        page_number = page.get("pageNum")
        try:
            page_number = int(page_number) if page_number is not None else None
        except (TypeError, ValueError):
            page_number = None
        pages.append(
            {
                "page_number": page_number,
                "source_url": page.get("sourceUrl"),
                "download_url": page.get("downUrl"),
                "status": str(page.get("status") or "").upper(),
                "tip": page.get("tip"),
            }
        )

    return {
        "task_no": task_no,
        "export_format": data.get("exportFormat"),
        "status": status,
        "download_url": data.get("downUrl"),
        "tip": data.get("tip"),
        "pages": pages,
    }


class XfyunPdfOcrClient:
    """Submit PDF files and query recognition task status."""

    def __init__(
        self,
        config: XfyunPdfOcrConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    @property
    def is_enabled(self) -> bool:
        return bool(self.config.enabled and self.config.app_id and self.config.secret)

    def _headers(self) -> dict[str, str]:
        if not self.is_enabled:
            raise XfyunPdfOcrError("PDF 文档识别服务尚未配置")
        return _build_auth_headers(
            app_id=self.config.app_id,
            secret=self.config.secret,
        )

    async def start_task(
        self,
        content: bytes,
        *,
        filename: str,
        export_format: PdfExportFormat,
    ) -> dict[str, Any]:
        if export_format not in {"word", "markdown", "json"}:
            raise XfyunPdfOcrError("不支持的导出格式")
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self.config.base_url.rstrip('/')}/start",
                    headers=self._headers(),
                    files={"file": (filename, content, "application/pdf")},
                    data={"exportFormat": export_format},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise XfyunPdfOcrError("PDF 上传或任务创建超时，请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise XfyunPdfOcrError("暂时无法连接 PDF 文档识别服务") from exc

        try:
            return _normalize_task(_response_data(response.json()))
        except ValueError as exc:
            raise XfyunPdfOcrError("讯飞返回了无法解析的响应") from exc

    async def get_status(self, task_no: str) -> dict[str, Any]:
        if not task_no.strip():
            raise XfyunPdfOcrError("任务号不能为空")
        try:
            async with httpx.AsyncClient(
                timeout=min(self.config.timeout_seconds, 30.0),
                transport=self._transport,
            ) as client:
                response = await client.get(
                    f"{self.config.base_url.rstrip('/')}/status",
                    headers=self._headers(),
                    params={"taskNo": task_no},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise XfyunPdfOcrError("查询识别进度超时，请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise XfyunPdfOcrError("暂时无法查询 PDF 文档识别进度") from exc

        try:
            return _normalize_task(_response_data(response.json()))
        except ValueError as exc:
            raise XfyunPdfOcrError("讯飞返回了无法解析的响应") from exc
