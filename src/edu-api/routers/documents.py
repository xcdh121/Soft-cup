"""Router for document CRUD operations."""

import asyncio
import logging

from auth import get_current_user
from dependencies import (
    get_document_service,
    get_document_upload_service,
    get_queue_service,
    get_search_service,
    get_settings_dep,
    get_usage_service,
)
from edu_core.exceptions import NotFoundError
from edu_core.model_providers import LlmProviderConfig, create_chat_model
from edu_core.schemas.documents import (
    CourseBookDto,
    DocumentCitationDto,
    DocumentDto,
    DocumentPageContextDto,
    DocumentQuestionResponseDto,
    DocumentStatus,
)
import mimetypes
from edu_core.schemas.users import UserDto
from edu_core.services import (
    DocumentService,
    DocumentUploadService,
    SearchService,
    UsageService,
)
from edu_queue.schemas import DocumentProcessingData, QueueTaskMessage, TaskType
from edu_queue.service import QueueService
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from routers.schemas import (
    DocumentCreate,
    DocumentQuestionRequest,
    DocumentUpdate,
    DocumentPreviewDto,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/documents", tags=["documents"])
course_books_router = APIRouter(
    prefix="/api/v1/projects/{project_id}/course-books", tags=["course-books"]
)
logger = logging.getLogger(__name__)


def _document_title(document: DocumentDto) -> str:
    display_title = document.metadata.get("display_title")
    if isinstance(display_title, str) and display_title:
        return display_title
    return document.file_name


def _message_content(response) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    return str(content)


def _build_question_prompt(
    *,
    document: DocumentDto,
    request: DocumentQuestionRequest,
    page_context: DocumentPageContextDto | None,
    search_results,
) -> str:
    selected_text = request.selected_text.strip() if request.selected_text else ""
    page_context_text = page_context.content[:4000] if page_context else ""
    rag_blocks = []
    for index, result in enumerate(search_results, start=1):
        page = f", page {result.page_number}" if result.page_number else ""
        rag_blocks.append(
            f"[{index}] {result.title}{page}\n{result.content[:1500]}"
        )
    rag_context = "\n\n".join(rag_blocks) or "No additional RAG context was found."
    page_label = request.page_number if request.page_number else "unknown"

    return (
        "You are an AI study assistant embedded in a PDF reader. "
        "Answer in Chinese unless the question clearly asks for another language. "
        "Explain the selected passage first when selected text is provided. "
        "Use the page context and retrieved course material to answer accurately. "
        "When useful, mention source page numbers in plain text.\n\n"
        f"Document: {_document_title(document)}\n"
        f"Current page: {page_label}\n\n"
        f"Selected text:\n{selected_text or 'None'}\n\n"
        f"Current page context:\n{page_context_text or 'None'}\n\n"
        f"Retrieved course context:\n{rag_context}\n\n"
        f"Student question:\n{request.question}\n"
    )


def _build_citations(
    *,
    document: DocumentDto,
    request: DocumentQuestionRequest,
    page_context: DocumentPageContextDto | None,
    search_results,
) -> list[DocumentCitationDto]:
    citations: list[DocumentCitationDto] = []
    seen: set[tuple[str, str | None, int | None]] = set()
    title = _document_title(document)

    if page_context and page_context.segments:
        first_segment = page_context.segments[0]
        key = (document.id, first_segment.id, page_context.page_number)
        seen.add(key)
        citations.append(
            DocumentCitationDto(
                document_id=document.id,
                segment_id=first_segment.id,
                title=title,
                page_number=page_context.page_number,
                excerpt=(request.selected_text or page_context.content[:500] or None),
            )
        )

    for result in search_results:
        segment_id = result.segment_id or result.id
        key = (result.document_id, segment_id, result.page_number)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            DocumentCitationDto(
                document_id=result.document_id,
                segment_id=segment_id,
                title=result.title,
                page_number=result.page_number,
                score=result.score,
                excerpt=result.content[:500],
            )
        )

    return citations


@router.post("/upload", status_code=201)
async def upload_document(
    project_id: str,
    files: list[UploadFile] = File(...),
    current_user: UserDto = Depends(get_current_user),
    upload_service: DocumentUploadService = Depends(get_document_upload_service),
    queue_service: QueueService = Depends(get_queue_service),
    usage_service: UsageService = Depends(get_usage_service),
):
    """Upload one or more documents. Processing happens asynchronously in background."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    # Check usage limit for each file upload
    for _ in files:
        usage_service.check_and_increment(current_user.id, "document_upload")

    # Validate file types
    allowed_types = upload_service.get_supported_types()
    document_ids = []

    for file in files:
        if not file.filename:
            raise HTTPException(
                status_code=400, detail="File with empty filename provided"
            )

        file_extension = (
            file.filename.split(".")[-1].lower() if "." in file.filename else ""
        )

        if file_extension not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{file_extension}' for file '{file.filename}'. Allowed types: {', '.join(allowed_types)}",
            )

    try:
        # Read all files concurrently
        async def read_file(file: UploadFile) -> tuple[str, bytes]:
            if not file.filename:
                raise ValueError("File with empty filename provided")
            content = await file.read()
            return file.filename, content

        file_data = await asyncio.gather(*[read_file(file) for file in files])

        # Upload all documents concurrently
        async def upload_single_document(filename: str, content: bytes) -> str:
            document_id = await asyncio.to_thread(
                upload_service.upload_document,
                file_content=content,
                filename=filename,
                project_id=project_id,
                owner_id=current_user.id,
            )
            return document_id

        document_ids = await asyncio.gather(
            *[
                upload_single_document(filename, content)
                for filename, content in file_data
            ]
        )

        # Queue processing tasks for all documents
        for document_id in document_ids:
            task_message: QueueTaskMessage = {
                "type": TaskType.DOCUMENT_PROCESSING,
                "data": DocumentProcessingData(
                    document_id=document_id,
                    project_id=project_id,
                    user_id=current_user.id,
                ),
            }
            queue_service.send_message(task_message)

        return {"document_ids": document_ids}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to upload documents: {e!s}"
        )


@router.post("", response_model=DocumentDto, status_code=201)
async def create_document(
    project_id: str,
    document: DocumentCreate,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Create a new document."""
    try:
        return service.create_document(
            owner_id=current_user.id,
            file_name=document.file_name,
            file_type=document.file_type,
            file_size=document.file_size,
            project_id=project_id,
            status=DocumentStatus.UPLOADED,
            summary=document.summary,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentDto)
async def get_document(
    project_id: str,
    document_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Get a document by ID."""
    try:
        return service.get_document(
            document_id=document_id,
            owner_id=current_user.id,
            project_id=project_id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{document_id}/file")
async def get_document_file(
    project_id: str,
    document_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
    upload_service: DocumentUploadService = Depends(get_document_upload_service),
):
    """Serve the original uploaded document from local storage."""
    try:
        document = service.get_document(
            document_id=document_id,
            owner_id=current_user.id,
            project_id=project_id,
        )
        relative_path = upload_service.get_blob_name(
            project_id=project_id,
            document_id=document_id,
            filename=document.file_name,
        )
        storage_path = upload_service.storage.resolve(relative_path)
        if not storage_path.exists():
            raise HTTPException(status_code=404, detail="Document file not found")

        content_type, _ = mimetypes.guess_type(document.file_name)
        return FileResponse(
            path=storage_path,
            filename=document.file_name,
            media_type=content_type or "application/octet-stream",
            content_disposition_type="inline",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{document_id}/preview", response_model=DocumentPreviewDto)
async def get_document_preview(
    project_id: str,
    document_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
    upload_service: DocumentUploadService = Depends(get_document_upload_service),
):
    """Get a preview URL for a document."""
    try:
        document = service.get_document(
            document_id=document_id,
            owner_id=current_user.id,
            project_id=project_id,
        )
        url = f"/api/v1/projects/{project_id}/documents/{document_id}/file"
        return DocumentPreviewDto(url=url)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[DocumentDto])
async def list_documents(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """List all documents for a project."""
    try:
        return service.list_documents(owner_id=current_user.id, project_id=project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{document_id}/pages/{page_number}/context",
    response_model=DocumentPageContextDto,
)
async def get_document_page_context(
    project_id: str,
    document_id: str,
    page_number: int,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    try:
        return service.get_page_context(
            document_id=document_id,
            owner_id=current_user.id,
            project_id=project_id,
            page_number=page_number,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/process", status_code=202)
async def process_document(
    project_id: str,
    document_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
    queue_service: QueueService = Depends(get_queue_service),
):
    try:
        service.get_document(
            document_id=document_id,
            owner_id=current_user.id,
            project_id=project_id,
        )
        service.update_document(
            document_id=document_id,
            owner_id=current_user.id,
            status=DocumentStatus.PROCESSING,
            project_id=project_id,
        )
        task_message: QueueTaskMessage = {
            "type": TaskType.DOCUMENT_PROCESSING,
            "data": DocumentProcessingData(
                document_id=document_id,
                project_id=project_id,
                user_id=current_user.id,
            ),
        }
        queue_service.send_message(task_message)
        return {"document_id": document_id, "status": DocumentStatus.PROCESSING.value}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/ask", response_model=DocumentQuestionResponseDto)
async def ask_document_question(
    project_id: str,
    document_id: str,
    request: DocumentQuestionRequest,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
    search_service: SearchService = Depends(get_search_service),
    settings=Depends(get_settings_dep),
):
    try:
        document = service.get_document(
            document_id=document_id,
            owner_id=current_user.id,
            project_id=project_id,
        )
        page_context = None
        if request.page_number:
            page_context = service.get_page_context(
                document_id=document_id,
                owner_id=current_user.id,
                project_id=project_id,
                page_number=request.page_number,
            )

        search_query = "\n".join(
            part
            for part in (request.selected_text, request.question)
            if part and part.strip()
        )
        search_results = []
        if search_query.strip():
            try:
                search_results = await search_service.search_documents(
                    query=search_query,
                    project_id=project_id,
                    top_k=request.top_k,
                )
            except Exception:
                logger.exception(
                    "Document question RAG search failed for document %s",
                    document_id,
                )

        if not settings.llm_api_key:
            raise HTTPException(
                status_code=503,
                detail="未配置 LLM_API_KEY，无法使用 PDF AI 问答。",
            )

        prompt = _build_question_prompt(
            document=document,
            request=request,
            page_context=page_context,
            search_results=search_results,
        )
        try:
            llm = create_chat_model(
                LlmProviderConfig(
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    temperature=0.2,
                ),
                streaming=False,
            )
            response = await llm.ainvoke(prompt)
        except Exception as e:
            logger.exception(
                "Document question LLM call failed for document %s",
                document_id,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "AI 问答生成失败，请检查 LLM_MODEL、LLM_API_KEY、"
                    f"LLM_BASE_URL 是否可用。原始错误：{e}"
                ),
            ) from e

        return DocumentQuestionResponseDto(
            answer=_message_content(response),
            citations=_build_citations(
                document=document,
                request=request,
                page_context=page_context,
                search_results=search_results,
            ),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{document_id}", response_model=DocumentDto)
async def update_document(
    project_id: str,
    document_id: str,
    document: DocumentUpdate,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Update a document."""
    try:
        return service.update_document(
            document_id=document_id,
            owner_id=current_user.id,
            file_name=document.file_name,
            summary=document.summary,
            project_id=project_id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    project_id: str,
    document_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Delete a document."""
    try:
        service.delete_document(document_id=document_id, owner_id=current_user.id)
        return None
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@course_books_router.get("", response_model=list[CourseBookDto])
async def list_course_books(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    try:
        return service.list_course_books(owner_id=current_user.id, project_id=project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
