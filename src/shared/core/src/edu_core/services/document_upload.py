"""Service for uploading documents to local storage."""

from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from edu_db.models import Document
from edu_db.session import get_session_factory

from edu_core.schemas.documents import DocumentStatus
from edu_core.storage import LocalStorageService


class DocumentUploadService:
    """Service for uploading documents to local storage."""

    def __init__(
        self,
        database_url: str,
        storage_root: str,
    ) -> None:
        """Initialize the document upload service.

        Args:
            database_url: Database connection URL
            storage_root: Local storage root directory
        """
        self.database_url = database_url
        self.storage = LocalStorageService(storage_root)

    def get_supported_types(self) -> list[str]:
        """Get list of supported document types.

        Returns:
            List of supported file extensions
        """
        return [
            "pdf",
            "tiff",
            "jpg",
            "jpeg",
            "jpe",
            "png",
            "bmp",
            "heif",
            "heic",
            "docx",
            "xlsx",
            "pptx",
            "txt",
            "html",
            "md",
            "rtf",
            "eml",
            "msg",
            "xml",
        ]

    def upload_document(
        self, file_content: bytes, filename: str, project_id: str, owner_id: str
    ) -> str:
        """Upload document to local storage and create database record.

        Args:
            file_content: The file content as bytes
            filename: Name of the file
            project_id: The project ID
            owner_id: The owner's user ID

        Returns:
            ID of the created document

        Raises:
            Exception: If upload fails
        """
        with self._get_db_session() as db:
            try:
                # Step 1: Create document record
                document_id = self._create_document_record(
                    db=db,
                    file_content=file_content,
                    filename=filename,
                    project_id=project_id,
                    owner_id=owner_id,
                )

                # Step 2: Persist file to local storage
                raw_blob_name = self._upload_to_storage(
                    file_content=file_content,
                    filename=filename,
                    project_id=project_id,
                    document_id=document_id,
                )

                # Step 3: Update document with storage reference
                self._update_document_blob_reference(
                    db=db, document_id=document_id, raw_blob_name=raw_blob_name
                )

                return document_id
            except Exception:
                raise

    def _create_document_record(
        self,
        db,
        file_content: bytes,
        filename: str,
        project_id: str,
        owner_id: str,
    ) -> str:
        """Create initial document record in database.

        Args:
            db: Database session
            file_content: The file content as bytes
            filename: Name of the file
            project_id: The project ID
            owner_id: The owner's user ID

        Returns:
            ID of the created document
        """
        document = Document(
            id=str(uuid4()),
            owner_id=owner_id,
            project_id=project_id,
            file_name=filename,
            file_type=self._get_file_type(filename),
            file_size=len(file_content),
            status=DocumentStatus.UPLOADED.value,
            uploaded_at=datetime.now(),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document.id

    def _upload_to_storage(
        self, file_content: bytes, filename: str, project_id: str, document_id: str
    ) -> str:
        """Upload document to local storage.

        Args:
            file_content: The file content as bytes
            filename: Name of the file
            project_id: The project ID
            document_id: The document ID

        Returns:
            Relative path where the document was stored
        """
        stored_path = self.storage.build_document_path(project_id, document_id, filename)
        self.storage.write_bytes(stored_path, file_content)
        return stored_path

    @staticmethod
    def _get_file_type(filename: str) -> str:
        """Extract file type from filename.

        Args:
            filename: Name of the file

        Returns:
            File extension or 'unknown'
        """
        return filename.split(".")[-1].lower() if "." in filename else "unknown"

    @staticmethod
    def _update_document_blob_reference(
        db, document_id: str, raw_blob_name: str
    ) -> None:
        """Update document with storage reference and set status to processing.

        Args:
            db: Database session
            document_id: The document ID
            raw_blob_name: The blob name in storage
        """
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.original_blob_name = raw_blob_name
            document.status = DocumentStatus.PROCESSING.value
            db.commit()

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

    def get_blob_name(self, project_id: str, document_id: str, filename: str) -> str:
        """Get stored relative path for a document.

        Args:
            project_id: The project ID
            document_id: The document ID
            filename: The filename

        Returns:
            The stored relative path
        """
        return self.storage.build_document_path(project_id, document_id, filename)
