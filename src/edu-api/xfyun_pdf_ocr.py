"""Client for XFYun's asynchronous PDF OCR service."""
# ruff: noqa: RUF001

from __future__ import annotations

import base64
import hmac
import json
import time
import zipfile
from dataclasses import dataclass
from hashlib import md5, sha1
from io import BytesIO
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


MAX_OCR_RESULT_BYTES = 20 * 1024 * 1024
MAX_OCR_TEXT_CHARS = 120_000


def _decode_result_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise XfyunPdfOcrError("PDF 识别结果使用了不支持的文本编码")


def _json_text(value: Any) -> str:
    """Extract readable OCR text from provider JSON without depending on one schema."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(filter(None, (_json_text(item) for item in value)))
    if not isinstance(value, dict):
        return ""

    preferred_keys = ("content", "text", "markdown", "words", "value")
    preferred = [_json_text(value[key]) for key in preferred_keys if key in value]
    preferred = [item for item in preferred if item]
    if preferred:
        return "\n".join(preferred)
    return "\n".join(filter(None, (_json_text(item) for item in value.values())))


def _extract_result_text(content: bytes, *, filename: str = "") -> str:
    """Read Markdown/text/JSON OCR downloads, including ZIP result bundles."""
    if len(content) > MAX_OCR_RESULT_BYTES:
        raise XfyunPdfOcrError("PDF 识别结果过大，无法加入 AI 导师上下文")

    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                supported = [
                    info
                    for info in archive.infolist()
                    if not info.is_dir()
                    and info.filename.lower().endswith((".md", ".txt", ".json"))
                ]
                preferred_suffix = next(
                    (
                        suffix
                        for suffix in (".md", ".txt", ".json")
                        if any(
                            info.filename.lower().endswith(suffix) for info in supported
                        )
                    ),
                    None,
                )
                candidates = sorted(
                    (
                        info
                        for info in supported
                        if preferred_suffix
                        and info.filename.lower().endswith(preferred_suffix)
                    ),
                    key=lambda info: info.filename,
                )
                chunks: list[str] = []
                total_bytes = 0
                for info in candidates:
                    total_bytes += info.file_size
                    if total_bytes > MAX_OCR_RESULT_BYTES:
                        raise XfyunPdfOcrError(
                            "PDF 识别结果过大，无法加入 AI 导师上下文"
                        )
                    chunks.append(
                        _extract_result_text(archive.read(info), filename=info.filename)
                    )
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise XfyunPdfOcrError("PDF 识别结果压缩包无法读取") from exc
        text = "\n\n".join(chunk for chunk in chunks if chunk.strip())
    else:
        decoded = _decode_result_text(content)
        if filename.lower().endswith(".json") or decoded.lstrip().startswith(
            ("{", "[")
        ):
            try:
                text = _json_text(json.loads(decoded))
            except json.JSONDecodeError:
                text = decoded
        else:
            text = decoded

    text = text.strip()
    if not text:
        raise XfyunPdfOcrError("PDF 识别完成，但没有提取到可用文字")
    return text


def _build_auth_headers(
    *, app_id: str, secret: str, current_time: int | None = None
) -> dict[str, str]:
    timestamp = str(current_time if current_time is not None else int(time.time()))
    # The provider specification requires MD5 followed by HMAC-SHA1.
    auth = md5(f"{app_id}{timestamp}".encode(), usedforsecurity=False).hexdigest()
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

    async def download_text(self, download_url: str) -> tuple[str, bool]:
        """Download an OCR Markdown result and return bounded tutor context."""
        if not download_url.startswith(("https://", "http://")):
            raise XfyunPdfOcrError("PDF 识别结果下载地址无效")
        try:
            async with httpx.AsyncClient(
                timeout=min(self.config.timeout_seconds, 60.0),
                transport=self._transport,
                follow_redirects=True,
            ) as client:
                response = await client.get(download_url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise XfyunPdfOcrError("下载 PDF 识别结果超时，请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise XfyunPdfOcrError("暂时无法下载 PDF 识别结果") from exc

        filename = download_url.split("?", 1)[0].rsplit("/", 1)[-1]
        text = _extract_result_text(response.content, filename=filename)
        truncated = len(text) > MAX_OCR_TEXT_CHARS
        if truncated:
            text = (
                text[:MAX_OCR_TEXT_CHARS].rstrip()
                + "\n\n[文档内容较长，AI 导师上下文已截断]"
            )
        return text, truncated
