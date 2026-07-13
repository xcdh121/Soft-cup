import asyncio
import logging
from contextlib import contextmanager
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
from edu_core.services.learner_profiles import LearnerProfileService
from edu_core.services.resource_packages import ResourcePackageService
from edu_core.storage import LocalStorageService
from edu_db.models import Chat, Document, DocumentSegment
from edu_db.session import get_session_factory
from edu_queue.schemas import QueueTaskMessage, TaskType
from langchain_core.output_parsers import JsonOutputParser
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

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
            await self._generate_chat_title(payload)
        elif task_type == TaskType.LEARNER_PROFILE_EXTRACTION:
            await self._extract_learner_profile(payload)
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

    async def _generate_chat_title(self, payload: dict[str, Any]) -> None:
        """Generate and persist a title for an unnamed chat's first exchange."""
        user_message = str(payload.get("user_message") or "").strip()
        ai_response = str(payload.get("ai_response") or "").strip()
        fallback_title = self._fallback_chat_title(user_message)
        generated_title = fallback_title

        if user_message:
            prompt = f"""Create a concise, descriptive title for this conversation.

Requirements:
- Use the same language as the user's message.
- Summarize the main topic, not the user's intent to chat.
- Use at most 5 words for space-separated languages, or 20 characters for Chinese.
- Return only the title, without quotes, labels, or punctuation at the end.

User: {user_message[:2000]}
Assistant: {ai_response[:2000]}
"""
            try:
                model = create_chat_model(
                    self.llm_config, streaming=False, temperature=0.1
                )
                response = await model.ainvoke(prompt)
                content = response.content
                if not isinstance(content, str):
                    content = str(content)
                candidate = " ".join(content.strip().split())
                candidate = candidate.removeprefix("Title:").removeprefix(
                    "标题\uFF1A"
                )
                candidate = candidate.strip().strip(
                    '"\'“”\u2018\u2019'
                ).rstrip("。.!\uFF01?\uFF1F")
                if candidate:
                    generated_title = candidate[:60]
            except Exception:
                logger.exception(
                    "Chat title generation failed; using a message-based fallback"
                )

        session_factory = get_session_factory()
        with session_factory() as db:
            chat = (
                db.query(Chat)
                .filter(
                    Chat.id == str(payload["chat_id"]),
                    Chat.project_id == str(payload["project_id"]),
                    Chat.user_id == str(payload["user_id"]),
                )
                .first()
            )
            # Never overwrite a title supplied or edited by the user.
            if chat is None or (chat.title and chat.title.strip()):
                return
            chat.title = generated_title
            db.commit()

    @staticmethod
    def _fallback_chat_title(user_message: str) -> str:
        """Derive a useful title even when the title model is unavailable."""
        compact = " ".join(user_message.strip().split())
        compact = compact.strip('"\'“”\u2018\u2019').rstrip(
            "。.!\uFF01?\uFF1F"
        )
        if not compact:
            return "新聊天"
        if len(compact) <= 30:
            return compact
        return compact[:29].rstrip() + "…"

    async def _extract_learner_profile(self, payload: dict[str, Any]) -> None:
        """Extract stable learner facts from a user-authored chat message."""
        message_text = str(payload.get("message_text") or "").strip()
        if not message_text:
            return

        prompt = f"""You extract learner profile facts from a single message written by a student.

Return JSON only, with this exact top-level shape:
{{"fields": {{"field_key": {{"value": ..., "confidence": 0.0, "status": "confirmed|inferred"}}}}}}

Allowed field keys:
- major_background: academic discipline or professional background
- education_level: education stage or year
- learning_goal: an explicit learning objective
- resource_preference: preferred learning resource formats or methods
- cognitive_style: stable learning/cognitive style only when explicitly stated or strongly evidenced
- available_study_time: stated schedule or available study duration

Rules:
- Extract only facts supported by the student's own words.
- Use status "confirmed" only for an explicit first-person statement.
- Use status "inferred" only for a strong implication and lower confidence.
- Do not infer knowledge mastery, learning progress, practical ability, errors, grades, or learning state.
- Do not invent missing details. If there are no supported facts, return {{"fields": {{}}}}.
- Preserve the student's language in values.

Student message:
{message_text}
"""
        model = create_chat_model(self.llm_config, streaming=False, temperature=0.1)
        response = await model.ainvoke(prompt)
        content = response.content
        if not isinstance(content, str):
            content = str(content)
        parsed = JsonOutputParser().parse(content)
        fields = parsed.get("fields", {}) if isinstance(parsed, dict) else {}
        if not isinstance(fields, dict):
            return
        LearnerProfileService().apply_chat_inferences(
            project_id=str(payload["project_id"]),
            user_id=str(payload["user_id"]),
            message_id=str(payload["message_id"]),
            message_text=message_text,
            inferred_fields=fields,
        )

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
        generated_resource_id = payload.get("generated_resource_id")
        resource_packages = ResourcePackageService()
        try:
            note = await agent.generate_and_save(
                project_id=payload["project_id"],
                topic=payload.get("topic"),
                custom_instructions=payload.get("custom_instructions"),
                note_id=payload["note_id"],
            )
            if generated_resource_id:
                resource_packages.finish_chat_note(
                    project_id=payload["project_id"],
                    generated_resource_id=generated_resource_id,
                    title=note.title,
                    description=note.description,
                    content=note.content,
                )
        except Exception as exc:
            if generated_resource_id:
                resource_packages.finish_chat_note(
                    project_id=payload["project_id"],
                    generated_resource_id=generated_resource_id,
                    error_message=str(exc),
                )
            raise

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
