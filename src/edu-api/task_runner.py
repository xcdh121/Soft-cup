import asyncio
from contextlib import contextmanager
from threading import Thread
from typing import Any
from uuid import uuid4

from edu_ai.agents.flashcard_agent import FlashcardAgent
from edu_ai.agents.mind_map_agent import MindMapAgent
from edu_ai.agents.note_agent import NoteAgent
from edu_ai.agents.quiz_agent import QuizAgent
from edu_ai.agents.topic_graph_agent import TopicGraphAgent
from edu_core.document_parser import LocalDocumentParser
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


class TaskRunnerService:
    def __init__(
        self,
        *,
        storage_root: str,
        llm_model: str,
        llm_api_key: str = "",
        llm_base_url: str | None = None,
        embedding_model: str,
        embedding_api_key: str = "",
        embedding_base_url: str | None = None,
        search_service: Any,
    ) -> None:
        self.storage = LocalStorageService(storage_root)
        self.parser = LocalDocumentParser()
        self.search_service = search_service
        self.llm_config = LlmProviderConfig(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            temperature=0.25,
        )
        self.embeddings = create_embeddings(
            EmbeddingProviderConfig(
                model=embedding_model,
                api_key=embedding_api_key,
                base_url=embedding_base_url,
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

        with self._get_db_session() as db:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document or not document.original_blob_name:
                raise ValueError(f"Document {document_id} not found")

            file_content = self.storage.read_bytes(document.original_blob_name)
            content, summary = await asyncio.to_thread(
                self.parser.parse, document.file_name, file_content
            )

            processed_path = self.storage.build_processed_text_path(project_id, document_id)
            self.storage.write_text(processed_path, content)

            document.processed_text_blob_name = processed_path
            document.summary = summary
            document.status = DocumentStatus.PROCESSED.value

            db.query(DocumentSegment).filter(
                DocumentSegment.document_id == document_id
            ).delete()

            chunks = self.split_markdown_with_headers(content)
            segments = []
            for chunk in chunks:
                segment = DocumentSegment(
                    id=str(uuid4()),
                    document_id=document_id,
                    content=chunk,
                    content_type="text",
                )
                segments.append(segment)
            db.add_all(segments)
            db.flush()

            if segments:
                embeddings = await self.embeddings.aembed_documents([s.content for s in segments])
                for segment, embedding in zip(segments, embeddings, strict=False):
                    segment.embedding_vector = embedding

            document.status = DocumentStatus.INDEXED.value
            db.commit()

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
