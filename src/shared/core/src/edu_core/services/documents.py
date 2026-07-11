"""CRUD service for managing documents."""

from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from edu_db.models import CourseResource, Document, DocumentSegment, Project
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.documents import (
    CourseBookDto,
    DocumentDto,
    DocumentPageContextDto,
    DocumentPageSegmentDto,
    DocumentStatus,
)


class DocumentService:
    """Service for managing documents."""

    def __init__(self) -> None:
        """Initialize the document service."""
        pass

    def create_document(
        self,
        owner_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
        project_id: str | None = None,
        status: DocumentStatus = DocumentStatus.UPLOADED,
        summary: str | None = None,
    ) -> DocumentDto:
        """Create a new document.

        Args:
            owner_id: The document owner's user ID
            file_name: The file name
            file_type: The file type/extension
            file_size: The file size in bytes
            project_id: Optional project ID
            status: Document status (default: UPLOADED)
            summary: Optional document summary
            original_blob_name: Optional original blob storage name
            processed_text_blob_name: Optional processed text blob storage name

        Returns:
            Created DocumentDto
        """
        with self._get_db_session() as db:
            try:
                document = Document(
                    id=str(uuid4()),
                    owner_id=owner_id,
                    project_id=project_id,
                    file_name=file_name,
                    file_type=file_type,
                    file_size=file_size,
                    status=status.value
                    if isinstance(status, DocumentStatus)
                    else status,
                    summary=summary,
                    original_blob_name=None,
                    processed_text_blob_name=None,
                    uploaded_at=datetime.now(),
                    processed_at=None,
                )
                db.add(document)
                db.commit()
                db.refresh(document)

                return self._model_to_dto(document)
            except Exception:
                db.rollback()
                raise

    def get_document(
        self, document_id: str, owner_id: str, project_id: str | None = None
    ) -> DocumentDto:
        """Get a document by ID.

        Args:
            document_id: The document ID
            owner_id: The document owner's user ID

        Returns:
            DocumentDto

        Raises:
            NotFoundError: If document not found
        """
        with self._get_db_session() as db:
            try:
                document = (
                    db.query(Document)
                    .filter(
                        Document.id == document_id,
                        Document.owner_id == owner_id,
                        *(
                            [Document.project_id == project_id]
                            if project_id is not None
                            else []
                        ),
                    )
                    .first()
                )
                if not document:
                    raise NotFoundError(f"Document {document_id} not found")

                return self._model_to_dto(document)
            except NotFoundError:
                raise
            except Exception:
                raise

    def get_page_context(
        self,
        *,
        document_id: str,
        owner_id: str,
        project_id: str,
        page_number: int,
    ) -> DocumentPageContextDto:
        with self._get_db_session() as db:
            document = self._get_owned_document(db, document_id, owner_id, project_id)
            segments = (
                db.query(DocumentSegment)
                .filter(
                    DocumentSegment.document_id == document.id,
                    DocumentSegment.page_number == page_number,
                )
                .order_by(DocumentSegment.chunk_index, DocumentSegment.created_at)
                .all()
            )
            segment_dtos = [
                DocumentPageSegmentDto(
                    id=segment.id,
                    page_number=segment.page_number,
                    chunk_index=segment.chunk_index,
                    content=segment.content,
                )
                for segment in segments
            ]
            return DocumentPageContextDto(
                document_id=document.id,
                project_id=project_id,
                page_number=page_number,
                content="\n\n".join(segment.content for segment in segments),
                segments=segment_dtos,
            )

    def list_course_books(self, owner_id: str, project_id: str) -> list[CourseBookDto]:
        with self._get_db_session() as db:
            project = (
                db.query(Project)
                .filter(Project.id == project_id, Project.owner_id == owner_id)
                .first()
            )
            if not project:
                raise NotFoundError(f"Project {project_id} not found")
            if not project.course_id:
                return []

            resources = (
                db.query(CourseResource)
                .join(Document, CourseResource.document_id == Document.id)
                .filter(
                    CourseResource.course_id == project.course_id,
                    CourseResource.document_id.isnot(None),
                    Document.owner_id == owner_id,
                    Document.project_id == project_id,
                )
                .order_by(CourseResource.chapter_id, CourseResource.created_at)
                .all()
            )

            books: list[CourseBookDto] = []
            for resource in resources:
                if not resource.document:
                    continue
                document = resource.document
                document_metadata = document.extra_metadata or {}
                resource_metadata = resource.extra_metadata or {}
                title = (
                    resource.title
                    or document_metadata.get("display_title")
                    or document.file_name
                )
                books.append(
                    CourseBookDto(
                        resource_id=resource.id,
                        document_id=document.id,
                        chapter_id=resource.chapter_id,
                        title=title,
                        author=document_metadata.get("author"),
                        cover_url=document_metadata.get("cover_url")
                        or document_metadata.get("cover_image_path"),
                        file_url=(
                            f"/api/v1/projects/{project_id}/documents/"
                            f"{document.id}/file"
                        ),
                        status=DocumentStatus(document.status),
                        license=resource.license_info
                        or document_metadata.get("license")
                        or document_metadata.get("license_info"),
                        source_url=resource.source_url
                        or document_metadata.get("source_url"),
                        start_page=self._coerce_int(resource_metadata.get("start_page")),
                        end_page=self._coerce_int(resource_metadata.get("end_page")),
                        metadata={
                            **document_metadata,
                            **resource_metadata,
                        },
                    )
                )
            return books

    def list_documents(
        self, owner_id: str, project_id: str | None = None
    ) -> list[DocumentDto]:
        """List all documents for a user or project.

        Args:
            owner_id: The document owner's user ID
            project_id: Optional project ID to filter by

        Returns:
            List of DocumentDto instances
        """
        with self._get_db_session() as db:
            try:
                query = db.query(Document).filter(Document.owner_id == owner_id)
                if project_id:
                    query = query.filter(Document.project_id == project_id)
                documents = query.order_by(Document.uploaded_at.desc()).all()
                return [self._model_to_dto(doc) for doc in documents]
            except Exception:
                raise

    def update_document(
        self,
        document_id: str,
        owner_id: str,
        file_name: str | None = None,
        status: DocumentStatus | None = None,
        summary: str | None = None,
        processed_at: datetime | None = None,
        project_id: str | None = None,
    ) -> DocumentDto:
        """Update a document.

        Args:
            document_id: The document ID
            owner_id: The document owner's user ID
            file_name: Optional new file name
            status: Optional new status
            summary: Optional new summary
            processed_at: Optional processed timestamp
            project_id: Optional new project ID

        Returns:
            Updated DocumentDto

        Raises:
            NotFoundError: If document not found
        """
        with self._get_db_session() as db:
            try:
                document = (
                    db.query(Document)
                    .filter(Document.id == document_id, Document.owner_id == owner_id)
                    .first()
                )
                if not document:
                    raise NotFoundError(f"Document {document_id} not found")

                if file_name is not None:
                    document.file_name = file_name
                if status is not None:
                    document.status = (
                        status.value if isinstance(status, DocumentStatus) else status
                    )
                if summary is not None:
                    document.summary = summary
                if processed_at is not None:
                    document.processed_at = processed_at
                if project_id is not None:
                    document.project_id = project_id

                db.commit()
                db.refresh(document)

                return self._model_to_dto(document)
            except NotFoundError:
                raise
            except Exception:
                db.rollback()
                raise

    def delete_document(self, document_id: str, owner_id: str) -> None:
        """Delete a document.

        Args:
            document_id: The document ID
            owner_id: The document owner's user ID

        Raises:
            NotFoundError: If document not found
        """
        with self._get_db_session() as db:
            try:
                document = (
                    db.query(Document)
                    .filter(Document.id == document_id, Document.owner_id == owner_id)
                    .first()
                )
                if not document:
                    raise NotFoundError(f"Document {document_id} not found")

                db.delete(document)
                db.commit()
            except NotFoundError:
                raise
            except Exception:
                db.rollback()
                raise

    def _model_to_dto(self, document: Document) -> DocumentDto:
        """Convert Document model to DocumentDto."""
        return DocumentDto(
            id=document.id,
            owner_id=document.owner_id,
            project_id=document.project_id,
            file_name=document.file_name,
            file_type=document.file_type,
            file_size=document.file_size,
            status=DocumentStatus(document.status),
            summary=document.summary,
            metadata=document.extra_metadata or {},
            uploaded_at=document.uploaded_at,
            processed_at=document.processed_at,
        )

    @staticmethod
    def _get_owned_document(
        db, document_id: str, owner_id: str, project_id: str | None = None
    ) -> Document:
        query = db.query(Document).filter(
            Document.id == document_id,
            Document.owner_id == owner_id,
        )
        if project_id is not None:
            query = query.filter(Document.project_id == project_id)
        document = query.first()
        if not document:
            raise NotFoundError(f"Document {document_id} not found")
        return document

    @staticmethod
    def _coerce_int(value) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    @contextmanager
    def _get_db_session(self):
        """Context manager for database sessions."""
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
