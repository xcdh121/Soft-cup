import asyncio
from contextlib import contextmanager
import logging
from threading import Thread
from typing import Any
from uuid import uuid4

from edu_ai.agents.flashcard_agent import FlashcardAgent
from edu_ai.agents.mind_map_agent import MindMapAgent
from edu_ai.agents.note_agent import NoteAgent
from edu_ai.agents.quiz_agent import QuizAgent
from edu_ai.agents.topic_graph_agent import TopicGraphAgent
from edu_core.document_parser import LocalDocumentParser, ParsedPage
from edu_core.model_providers import (
    EmbeddingProviderConfig,
    LlmProviderConfig,
    create_chat_model,
    create_embeddings,
)
from edu_core.schemas.documents import DocumentStatus
from edu_core.storage import LocalStorageService
from edu_db.models import Document, DocumentSegment
from edu_db.session import get_session_factory
from edu_queue.schemas import QueueTaskMessage, TaskType
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class TaskRunnerService:
    def __init__(
        self,
        *,
        storage_root: str,
        llm_model: str,
        llm_api_key: str = "",
        llm_base_url: str | None = None,
        embedding_model: str,
        embedding_provider: str = "openai",
        embedding_api_key: str = "",
        embedding_api_secret: str = "",
        embedding_app_id: str = "",
        embedding_base_url: str | None = None,
        embedding_domain: str = "query",
        embedding_dimensions: int = 3072,
        search_service: Any,
    ) -> None:
        self.storage = LocalStorageService(storage_root)
        self.parser = LocalDocumentParser()
        self.search_service = search_service
        self.embedding_provider = embedding_provider
        self.embedding_api_key = embedding_api_key
        self.embedding_base_url = embedding_base_url
        self.embedding_app_id = embedding_app_id
        self.embedding_api_secret = embedding_api_secret
        self.llm_config = LlmProviderConfig(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            temperature=0.25,
        )
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

    def dispatch(self, message: QueueTaskMessage) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._dispatch_async(message))
            return

        error: Exception | None = None

        def run() -> None:
            nonlocal error
            try:
                asyncio.run(self._dispatch_async(message))
            except Exception as exc:  # pragma: no cover
                error = exc

        thread = Thread(target=run, daemon=False)
        thread.start()
        thread.join()
        if error:
            raise error

    async def _dispatch_async(self, message: QueueTaskMessage) -> None:
        task_type = TaskType(message["type"])
        payload = message["data"]

        if task_type == TaskType.DOCUMENT_PROCESSING:
            await self._process_document(payload)
        elif task_type == TaskType.FLASHCARD_GENERATION:
            await self._run_flashcards(payload)
        elif task_type == TaskType.QUIZ_GENERATION:
            await self._run_quiz(payload)
        elif task_type == TaskType.NOTE_GENERATION:
            await self._run_note(payload)
        elif task_type == TaskType.MIND_MAP_GENERATION:
            await self._run_mind_map(payload)
        elif task_type == TaskType.CHAT_TITLE_GENERATION:
            return
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

    def _make_topic_graph_agent(self):
        llm = create_chat_model(self.llm_config, streaming=False)
        return llm, TopicGraphAgent(
            search_service=self.search_service,
            llm=llm,
            text_storage=self.storage,
        )

    def _make_streaming_agent_dependencies(self):
        llm = create_chat_model(self.llm_config, streaming=True)
        topic_llm = create_chat_model(self.llm_config, streaming=False)
        topic_graph_agent = TopicGraphAgent(
            search_service=self.search_service,
            llm=topic_llm,
            text_storage=self.storage,
        )
        return llm, topic_graph_agent

    async def stream_note(self, payload: dict[str, Any]):
        llm, topic_graph_agent = self._make_streaming_agent_dependencies()
        agent = NoteAgent(self.search_service, llm, topic_graph_agent)
        async for event in agent.generate_and_save_stream(
            project_id=payload["project_id"], topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            note_id=payload["note_id"],
        ):
            yield event

    async def stream_mind_map(self, payload: dict[str, Any]):
        llm, topic_graph_agent = self._make_streaming_agent_dependencies()
        agent = MindMapAgent(self.search_service, llm, topic_graph_agent)
        async for event in agent.generate_and_save_stream(
            project_id=payload["project_id"], topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            mind_map_id=payload["mind_map_id"], user_id=payload["user_id"],
        ):
            yield event

    async def stream_flashcards(self, payload: dict[str, Any]):
        llm, topic_graph_agent = self._make_streaming_agent_dependencies()
        agent = FlashcardAgent(self.search_service, llm, topic_graph_agent)
        async for event in agent.generate_and_save_stream(
            project_id=payload["project_id"], topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            group_id=payload["group_id"], count=payload.get("count"),
            difficulty=payload.get("difficulty"),
        ):
            yield event

    async def _run_flashcards(self, payload: dict[str, Any]) -> None:
        llm, topic_graph_agent = self._make_topic_graph_agent()
        agent = FlashcardAgent(self.search_service, llm, topic_graph_agent)
        await agent.generate_and_save(
            project_id=payload["project_id"],
            topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            group_id=payload["group_id"],
            count=payload.get("count"),
            difficulty=payload.get("difficulty"),
        )

    async def _run_quiz(self, payload: dict[str, Any]) -> None:
        llm, topic_graph_agent = self._make_topic_graph_agent()
        agent = QuizAgent(self.search_service, llm, topic_graph_agent)
        await agent.generate_and_save(
            project_id=payload["project_id"],
            topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            quiz_id=payload["quiz_id"],
            count=payload.get("count"),
        )

    async def _run_note(self, payload: dict[str, Any]) -> None:
        llm, topic_graph_agent = self._make_topic_graph_agent()
        agent = NoteAgent(self.search_service, llm, topic_graph_agent)
        await agent.generate_and_save(
            project_id=payload["project_id"],
            topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            note_id=payload["note_id"],
        )

    async def _run_mind_map(self, payload: dict[str, Any]) -> None:
        llm, topic_graph_agent = self._make_topic_graph_agent()
        agent = MindMapAgent(self.search_service, llm, topic_graph_agent)
        await agent.generate_and_save(
            project_id=payload["project_id"],
            topic=payload.get("topic"),
            custom_instructions=payload.get("custom_instructions"),
            mind_map_id=payload.get("mind_map_id"),
            user_id=payload["user_id"],
        )

    async def _process_document(self, payload: dict[str, Any]) -> None:
        document_id = payload["document_id"]
        project_id = payload["project_id"]
        segment_payloads: list[tuple[str, str]] = []

        try:
            with self._get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document or not document.original_blob_name:
                    raise ValueError(f"Document {document_id} not found")

                file_content = self.storage.read_bytes(document.original_blob_name)
                parsed = await asyncio.to_thread(
                    self.parser.parse, document.file_name, file_content
                )
                content = parsed.full_text

                processed_path = self.storage.build_processed_text_path(
                    project_id, document_id
                )
                self.storage.write_text(processed_path, content)

                document.processed_text_blob_name = processed_path
                document.summary = parsed.summary
                document.extra_metadata = {
                    **(document.extra_metadata or {}),
                    "page_count": len(parsed.pages),
                }
                document.status = DocumentStatus.PROCESSED.value

                db.query(DocumentSegment).filter(
                    DocumentSegment.document_id == document_id
                ).delete()

                chunks = self.split_parsed_pages(parsed.pages)
                segments = []
                for page_number, chunk_index, chunk in chunks:
                    segment_id = str(uuid4())
                    segment = DocumentSegment(
                        id=segment_id,
                        document_id=document_id,
                        content=chunk,
                        content_type="text",
                        page_number=page_number,
                        chunk_index=chunk_index,
                    )
                    segments.append(segment)
                    segment_payloads.append((segment_id, chunk))
                db.add_all(segments)
                db.commit()
        except Exception:
            logger.exception("Document processing failed: %s", document_id)
            self._mark_document_failed(document_id)
            return

        if not segment_payloads or not self._embedding_is_configured():
            return

        try:
            embeddings = await self.embeddings.aembed_documents(
                [content for _, content in segment_payloads]
            )
            segment_embeddings = {
                segment_id: embedding
                for (segment_id, _), embedding in zip(
                    segment_payloads, embeddings, strict=False
                )
            }
            with self._get_db_session() as db:
                stored_segments = (
                    db.query(DocumentSegment)
                    .filter(DocumentSegment.id.in_(segment_embeddings))
                    .all()
                )
                for segment in stored_segments:
                    segment.embedding_vector = segment_embeddings[segment.id]
                document = db.query(Document).filter(Document.id == document_id).first()
                if document and document.status != DocumentStatus.FAILED.value:
                    document.status = DocumentStatus.INDEXED.value
                db.commit()
        except Exception:
            logger.exception(
                "Document %s parsed, but embedding generation failed",
                document_id,
            )

    @classmethod
    def split_parsed_pages(cls, pages: list[ParsedPage]) -> list[tuple[int, int, str]]:
        segments: list[tuple[int, int, str]] = []
        for page in pages:
            chunks = cls.split_markdown_with_headers(page.text)
            for chunk_index, chunk in enumerate(chunks):
                segments.append((page.page_number, chunk_index, chunk))
        return segments

    @staticmethod
    def split_markdown_with_headers(
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[str]:
        pages = [p.strip() for p in text.split("<!-- PageBreak -->") if p.strip()]

        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
        )
        chunker = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

        chunks: list[str] = []
        for page in pages or [text]:
            sections = header_splitter.split_text(page)
            try:
                chunks.extend([d.page_content for d in chunker.split_documents(sections)])
            except AttributeError:
                for sec in sections:
                    chunks.extend(chunker.split_text(sec.page_content))
        return chunks

    def _embedding_is_configured(self) -> bool:
        provider = self.embedding_provider.lower()
        if provider == "xfyun":
            return all(
                [
                    self.embedding_app_id,
                    self.embedding_api_key,
                    self.embedding_api_secret,
                ]
            )
        return bool(self.embedding_api_key or self.embedding_base_url)

    def _mark_document_failed(self, document_id: str) -> None:
        try:
            with self._get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.status = DocumentStatus.FAILED.value
                    db.commit()
        except Exception:
            logger.exception("Failed to mark document as failed: %s", document_id)

    @contextmanager
    def _get_db_session(self):
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
