"""RAG search service for document retrieval."""

from contextlib import contextmanager
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from edu_db.models import Document, Project
from edu_db.session import get_session_factory
from langchain_core.documents import Document as LangchainDocument
from langchain_postgres import PGEngine, PGVectorStore

from edu_core.exceptions import NotFoundError
from edu_core.model_providers import EmbeddingProviderConfig, create_embeddings
from edu_core.schemas.search import SearchResultItem


class SearchService:
    """Service for RAG-based document search using LangChain PGVectorStore."""

    def __init__(
        self,
        database_url: str,
        embedding_model: str,
        embedding_provider: str = "openai",
        embedding_api_key: str = "",
        embedding_api_secret: str = "",
        embedding_app_id: str = "",
        embedding_base_url: str | None = None,
        embedding_domain: str = "query",
        embedding_dimensions: int = 3072,
    ) -> None:
        """Initialize the search service.

        Args:
            database_url: PostgreSQL database connection URL
            embeddings: LangChain embeddings service for vector operations
        """
        self.database_url = database_url

        self.embeddings = create_embeddings(
            EmbeddingProviderConfig(
                provider=embedding_provider,
                model=embedding_model,
                api_key=embedding_api_key,
                api_secret=embedding_api_secret,
                app_id=embedding_app_id,
                base_url=embedding_base_url,
                domain=embedding_domain,
                dimensions=embedding_dimensions,
            )
        )
        self._vector_store: PGVectorStore | None = None

    async def search_documents(
        self,
        query: str,
        project_id: str,
        top_k: int = 5,
    ) -> list[SearchResultItem]:
        """Search documents using vector similarity search.

        Args:
            query: The search query
            project_id: The project ID to search within
            top_k: Number of results to return

        Returns:
            List of SearchResultItem instances

        Raises:
            NotFoundError: If project not found
        """
        with self._get_db_session() as db:
            try:
                # Get project and validate it exists
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project:
                    raise NotFoundError(f"Project {project_id} not found")

                # Get document IDs for the project
                document_ids = [str(doc.id) for doc in project.documents]
                if not document_ids:
                    return []

                # Get or create vector store
                vector_store = await self._get_vector_store()

                # Perform vector search
                similar_docs = await vector_store.asimilarity_search_with_score(
                    query, k=top_k, filter={"document_id": {"$in": document_ids}}
                )

                # Format and return typed results
                return self._format_search_results(similar_docs, db)
            except NotFoundError:
                raise
            except Exception:
                raise

    async def _get_vector_store(self) -> PGVectorStore:
        """Get or create PGVectorStore instance.

        Returns:
            PGVectorStore instance
        """
        if self._vector_store is not None:
            return self._vector_store

        # Convert psycopg2 URL to asyncpg URL
        async_url = self.database_url.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

        # Remove unsupported query parameters - asyncpg handles SSL differently
        parsed = urlparse(async_url)
        query_params = parse_qs(parsed.query)

        # Remove parameters that asyncpg doesn't support
        query_params.pop("sslmode", None)
        query_params.pop("channel_binding", None)

        # Rebuild URL without unsupported parameters
        new_query = urlencode(query_params, doseq=True)
        async_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

        pg_engine = PGEngine.from_connection_string(url=async_url)

        self._vector_store = await PGVectorStore.create(
            pg_engine,
            table_name="document_segments",
            embedding_service=self.embeddings,
            id_column="id",
            content_column="content",
            embedding_column="embedding_vector",
            metadata_columns=["id", "document_id", "page_number", "chunk_index"],
        )

        return self._vector_store

    def _format_search_results(
        self,
        similar_docs: list[tuple[LangchainDocument, float]],
        db,
    ) -> list[SearchResultItem]:
        """Format search results with validated typed models.

        Args:
            similar_docs: List of tuples containing (document, score)
            db: Database session for querying document metadata

        Returns:
            List of SearchResultItem instances
        """
        if not similar_docs:
            return []

        doc_ids = list(
            {
                doc.metadata.get("document_id", "")
                for doc, _score in similar_docs
                if doc.metadata.get("document_id")
            }
        )
        documents = db.query(Document).filter(Document.id.in_(doc_ids)).all()
        doc_map = {str(d.id): d for d in documents}

        results = []
        for doc, score in similar_docs:
            doc_id = doc.metadata.get("document_id", "")
            if not doc_id or not doc.page_content.strip():
                continue

            doc_meta = doc_map.get(str(doc_id))
            segment_id = doc.metadata.get("id", doc_id)
            page_number = self._coerce_int(doc.metadata.get("page_number"))
            title = doc_meta.file_name if doc_meta else "Unknown Document"
            if doc_meta and isinstance(doc_meta.extra_metadata, dict):
                title = doc_meta.extra_metadata.get("display_title") or title

            try:
                # Normalize score (lower is better in similarity search, so invert)
                normalized_score = max(0.0, min(1.0, 1.0 - score))

                result = SearchResultItem(
                    id=segment_id,
                    segment_id=segment_id,
                    document_id=doc_id,
                    title=title,
                    content=doc.page_content[:1500],
                    score=normalized_score,
                    page_number=page_number,
                )
                results.append(result)
            except Exception:
                # Skip invalid results
                continue

        return results

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
