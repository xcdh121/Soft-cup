"""RAG search service for project PDFs and the structured course library."""

import json
import logging
import re
from contextlib import contextmanager
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from edu_db.models import (
    CourseChapter,
    CourseResource,
    Document,
    DocumentSegment,
    KnowledgePoint,
    Project,
)
from edu_db.session import get_session_factory
from langchain_core.documents import Document as LangchainDocument
from langchain_postgres import PGEngine, PGVectorStore
from sqlalchemy import or_

from edu_core.exceptions import NotFoundError
from edu_core.model_providers import EmbeddingProviderConfig, create_embeddings
from edu_core.schemas.search import SearchResultItem

logger = logging.getLogger(__name__)


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

                # Project PDFs and the structured course library are independent
                # sources. Search both and merge them into one result set.
                document_ids = [str(doc.id) for doc in project.documents]
                pdf_results: list[SearchResultItem] = []
                if document_ids:
                    try:
                        vector_store = await self._get_vector_store()
                        similar_docs = await vector_store.asimilarity_search_with_score(
                            query,
                            k=top_k,
                            filter={"document_id": {"$in": document_ids}},
                        )
                        pdf_results = self._format_search_results(similar_docs, db)
                    except Exception:
                        # A failed embedding provider must not make already parsed
                        # PDFs invisible to chat.
                        logger.exception(
                            "Vector search failed for project %s; using lexical PDF search",
                            project_id,
                        )

                    lexical_results = self._search_pdf_segments_lexically(
                        db, query=query, document_ids=document_ids, limit=top_k
                    )
                    pdf_results = self._deduplicate_results(
                        [*pdf_results, *lexical_results]
                    )

                course_results = self._search_course_library(
                    db, query=query, course_id=project.course_id, limit=top_k
                )
                return self._merge_source_results(
                    pdf_results, course_results, top_k=top_k
                )
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

    def _search_pdf_segments_lexically(
        self, db, *, query: str, document_ids: list[str], limit: int
    ) -> list[SearchResultItem]:
        """Search parsed PDF text when vectors are missing or unavailable."""
        terms = self._query_terms(query)
        if not terms:
            return []

        predicates = [DocumentSegment.content.ilike(f"%{term}%") for term in terms]
        candidates = (
            db.query(DocumentSegment, Document)
            .join(Document, DocumentSegment.document_id == Document.id)
            .filter(
                DocumentSegment.document_id.in_(document_ids),
                or_(*predicates),
            )
            .limit(max(limit * 20, 50))
            .all()
        )
        ranked = sorted(
            candidates,
            key=lambda row: self._lexical_score(
                query, terms, row[0].content, row[1].file_name
            ),
            reverse=True,
        )
        return [
            SearchResultItem(
                id=str(segment.id),
                segment_id=str(segment.id),
                document_id=str(document.id),
                title=document.file_name,
                content=segment.content[:1500],
                score=self._lexical_score(
                    query, terms, segment.content, document.file_name
                ),
                page_number=self._coerce_int(segment.page_number),
            )
            for segment, document in ranked[:limit]
            if segment.content and segment.content.strip()
        ]

    def _search_course_library(
        self, db, *, query: str, course_id: str | None, limit: int
    ) -> list[SearchResultItem]:
        """Search chapters, knowledge points and resources linked to a course."""
        if not course_id:
            return []
        terms = self._query_terms(query)
        if not terms:
            return []

        candidates: list[tuple[float, SearchResultItem]] = []
        chapters = db.query(CourseChapter).filter(CourseChapter.course_id == course_id).all()
        for chapter in chapters:
            content = "\n".join(
                part
                for part in [
                    f"课程章节: {chapter.title}",
                    chapter.description or "",
                    "学习目标: " + "; ".join(chapter.learning_objectives or []),
                ]
                if part
            )
            score = self._lexical_score(query, terms, content, chapter.title)
            if score > 0:
                candidates.append(
                    (
                        score,
                        SearchResultItem(
                            id=f"course-chapter:{chapter.id}",
                            segment_id=None,
                            document_id=f"course-chapter:{chapter.id}",
                            title=f"课程资料库 · {chapter.title}",
                            content=content[:1500],
                            score=score,
                        ),
                    )
                )

        points = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        for point in points:
            chapter_title = point.chapter.title if point.chapter else ""
            content = "\n".join(
                part
                for part in [
                    f"课程知识点: {point.name}",
                    f"所属章节: {chapter_title}" if chapter_title else "",
                    point.description or "",
                    "标签: " + "、".join(point.tags or []),
                ]
                if part
            )
            score = self._lexical_score(query, terms, content, point.name)
            if score > 0:
                candidates.append(
                    (
                        score,
                        SearchResultItem(
                            id=f"knowledge-point:{point.id}",
                            segment_id=None,
                            document_id=f"knowledge-point:{point.id}",
                            title=f"课程资料库 · {point.name}",
                            content=content[:1500],
                            score=score,
                        ),
                    )
                )

        resources = db.query(CourseResource).filter(CourseResource.course_id == course_id).all()
        for resource in resources:
            metadata = json.dumps(
                resource.extra_metadata or {}, ensure_ascii=False, default=str
            )
            point_names = [
                link.knowledge_point.name
                for link in resource.knowledge_point_links
                if link.knowledge_point
            ]
            content = "\n".join(
                part
                for part in [
                    f"课程资源: {resource.title}",
                    resource.description or "",
                    "关联知识点: " + "、".join(point_names),
                    f"资源类型: {resource.resource_type}",
                    metadata if metadata != "{}" else "",
                ]
                if part
            )
            score = self._lexical_score(query, terms, content, resource.title)
            if score > 0:
                candidates.append(
                    (
                        score,
                        SearchResultItem(
                            id=f"course-resource:{resource.id}",
                            segment_id=None,
                            document_id=f"course-resource:{resource.id}",
                            title=f"课程资料库 · {resource.title}",
                            content=content[:1500],
                            score=score,
                        ),
                    )
                )

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in candidates[:limit]]

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        terms: list[str] = []
        for token in re.findall(r"[a-z0-9_+#.-]{2,}|[\u4e00-\u9fff]+", normalized):
            terms.append(token)
            if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
                terms.extend(token[index : index + 2] for index in range(len(token) - 1))
        return list(dict.fromkeys(term for term in terms if term.strip()))[:20]

    @staticmethod
    def _lexical_score(query: str, terms: list[str], content: str, title: str = "") -> float:
        content_lower = (content or "").lower()
        title_lower = (title or "").lower()
        query_lower = query.strip().lower()
        score = 0.0
        if query_lower and query_lower in content_lower:
            score += 0.5
        if query_lower and query_lower in title_lower:
            score += 0.35
        for term in terms:
            if term in content_lower:
                score += 0.04
            if term in title_lower:
                score += 0.08
        return min(score, 1.0)

    @staticmethod
    def _deduplicate_results(results: list[SearchResultItem]) -> list[SearchResultItem]:
        unique: dict[str, SearchResultItem] = {}
        for result in results:
            existing = unique.get(result.id)
            if existing is None or result.score > existing.score:
                unique[result.id] = result
        return sorted(unique.values(), key=lambda item: item.score, reverse=True)

    @staticmethod
    def _merge_source_results(
        pdf_results: list[SearchResultItem],
        course_results: list[SearchResultItem],
        *,
        top_k: int,
    ) -> list[SearchResultItem]:
        """Keep both sources represented when both have relevant matches."""
        pdf_results = sorted(pdf_results, key=lambda item: item.score, reverse=True)
        course_results = sorted(course_results, key=lambda item: item.score, reverse=True)
        if not pdf_results:
            return course_results[:top_k]
        if not course_results:
            return pdf_results[:top_k]

        course_slots = max(1, top_k // 2)
        pdf_slots = max(1, top_k - course_slots)
        selected = [*pdf_results[:pdf_slots], *course_results[:course_slots]]
        remaining = [*pdf_results[pdf_slots:], *course_results[course_slots:]]
        selected.extend(
            sorted(remaining, key=lambda item: item.score, reverse=True)[
                : max(0, top_k - len(selected))
            ]
        )
        return sorted(selected[:top_k], key=lambda item: item.score, reverse=True)

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
