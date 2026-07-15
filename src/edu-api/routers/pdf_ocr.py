"""Project-scoped XFYun PDF OCR endpoints."""
# ruff: noqa: RUF001

from io import BytesIO
from typing import Literal

from auth import get_current_user
from dependencies import get_project_service, get_xfyun_pdf_ocr_client
from edu_core.exceptions import NotFoundError
from edu_core.schemas.users import UserDto
from edu_core.services import ProjectService
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from xfyun_pdf_ocr import (
    MAX_OCR_TEXT_CHARS,
    XfyunPdfOcrClient,
    XfyunPdfOcrError,
)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/pdf-ocr",
    tags=["pdf-ocr"],
)

MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PDF_PAGES = 100


class PdfOcrPageDto(BaseModel):
    page_number: int | None = None
    source_url: str | None = None
    download_url: str | None = None
    status: str
    tip: str | None = None


class PdfOcrTaskDto(BaseModel):
    task_no: str
    export_format: str | None = None
    status: str
    download_url: str | None = None
    tip: str | None = None
    pages: list[PdfOcrPageDto] = Field(default_factory=list)


class PdfOcrTextDto(BaseModel):
    content_text: str
    truncated: bool = False


def _ensure_project_access(
    *, project_id: str, current_user: UserDto, project_service: ProjectService
) -> None:
    try:
        project_service.get_project(project_id=project_id, owner_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks", response_model=PdfOcrTaskDto)
async def start_pdf_ocr_task(
    project_id: str,
    file: UploadFile = File(...),
    export_format: Literal["word", "markdown", "json"] = Form("word"),
    current_user: UserDto = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client: XfyunPdfOcrClient = Depends(get_xfyun_pdf_ocr_client),
) -> PdfOcrTaskDto:
    """Validate a PDF and submit it to XFYun for asynchronous recognition."""
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
    )
    filename = file.filename or "document.pdf"
    if file.content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="仅支持 PDF 文件")

    content = await file.read(MAX_PDF_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="上传的 PDF 文件为空")
    if len(content) > MAX_PDF_BYTES:
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
    if page_count > MAX_PDF_PAGES:
        raise HTTPException(
            status_code=400,
            detail=f"单个 PDF 最多支持 {MAX_PDF_PAGES} 页，当前文件共 {page_count} 页",
        )

    try:
        result = await client.start_task(
            content,
            filename=filename,
            export_format=export_format,
        )
    except XfyunPdfOcrError as exc:
        raise HTTPException(
            status_code=503 if not client.is_enabled else 502,
            detail=str(exc),
        ) from exc
    return PdfOcrTaskDto.model_validate(result)


@router.get("/tasks/{task_no}", response_model=PdfOcrTaskDto)
async def get_pdf_ocr_task(
    project_id: str,
    task_no: str,
    current_user: UserDto = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client: XfyunPdfOcrClient = Depends(get_xfyun_pdf_ocr_client),
) -> PdfOcrTaskDto:
    """Query one XFYun PDF OCR task. Clients should call no more than every 5s."""
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
    )
    try:
        result = await client.get_status(task_no)
    except XfyunPdfOcrError as exc:
        raise HTTPException(
            status_code=503 if not client.is_enabled else 502,
            detail=str(exc),
        ) from exc
    return PdfOcrTaskDto.model_validate(result)


@router.get("/tasks/{task_no}/text", response_model=PdfOcrTextDto)
async def get_pdf_ocr_text(
    project_id: str,
    task_no: str,
    current_user: UserDto = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service),
    client: XfyunPdfOcrClient = Depends(get_xfyun_pdf_ocr_client),
) -> PdfOcrTextDto:
    """Return recognized Markdown/text for use as grounded AI tutor context."""
    _ensure_project_access(
        project_id=project_id,
        current_user=current_user,
        project_service=project_service,
    )
    try:
        result = await client.get_status(task_no)
        status = result["status"]
        if status not in {"FINISH", "ANY_FAILED"}:
            if status in {"FAILED", "STOP"}:
                raise HTTPException(
                    status_code=409,
                    detail=result.get("tip") or "PDF 文档识别失败",
                )
            raise HTTPException(status_code=409, detail="PDF 文档仍在识别中")

        urls = [result.get("download_url")]
        if not result.get("download_url"):
            urls.extend(page.get("download_url") for page in result.get("pages", []))
        download_urls = list(dict.fromkeys(url for url in urls if url))
        if not download_urls:
            raise XfyunPdfOcrError("PDF 识别完成，但没有可下载的文字结果")

        chunks: list[str] = []
        truncated = False
        for download_url in download_urls:
            text, was_truncated = await client.download_text(download_url)
            chunks.append(text)
            truncated = truncated or was_truncated
        content_text = "\n\n".join(chunks)
        if len(content_text) > MAX_OCR_TEXT_CHARS:
            content_text = (
                content_text[:MAX_OCR_TEXT_CHARS].rstrip()
                + "\n\n[文档内容较长，AI 导师上下文已截断]"
            )
            truncated = True
        return PdfOcrTextDto(content_text=content_text, truncated=truncated)
    except HTTPException:
        raise
    except XfyunPdfOcrError as exc:
        raise HTTPException(
            status_code=503 if not client.is_enabled else 502,
            detail=str(exc),
        ) from exc
