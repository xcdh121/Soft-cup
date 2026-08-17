import asyncio
import unittest
from contextlib import ExitStack
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from edu_core.schemas.chats import ChatMessageDto, TextPartDto, ToolCallPartDto
from edu_core.services.chats import ChatService
from edu_core.services.resource_packages import ResourcePackageService
from edu_core.services.search import SearchService
from edu_db.models import (
    Base,
    Course,
    CourseChapter,
    CourseResource,
    Document,
    DocumentSegment,
    KnowledgePoint,
    Project,
    User,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class ChatSourcesAndNotePackagesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.patches = ExitStack()
        for target in (
            "edu_core.services.search.get_session_factory",
            "edu_core.services.resource_packages.get_session_factory",
        ):
            self.patches.enter_context(patch(target, return_value=self.session_factory))

        with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id="user-1",
                        username="test-user",
                        name="Test",
                        email="test@example.com",
                    ),
                    Course(id="course-1", owner_id="user-1", name="Data Structures"),
                    CourseChapter(
                        id="chapter-1",
                        course_id="course-1",
                        title="Strings",
                        description="String storage and pattern matching",
                        position=1,
                    ),
                    Project(
                        id="project-1",
                        owner_id="user-1",
                        course_id="course-1",
                        name="Data Structures",
                    ),
                    KnowledgePoint(
                        id="kp-1",
                        course_id="course-1",
                        chapter_id="chapter-1",
                        name="KMP string matching",
                        description="Prefix function and next array",
                        tags=["KMP", "string"],
                    ),
                    CourseResource(
                        id="course-resource-1",
                        course_id="course-1",
                        chapter_id="chapter-1",
                        resource_type="reading",
                        title="String algorithms handout",
                        description="BF and KMP examples",
                    ),
                    Document(
                        id="document-1",
                        owner_id="user-1",
                        project_id="project-1",
                        file_name="strings.pdf",
                        file_type="pdf",
                        file_size=100,
                        status="processed",
                    ),
                    DocumentSegment(
                        id="segment-1",
                        document_id="document-1",
                        content="KMP uses a prefix table to avoid repeated comparisons.",
                        page_number=3,
                        chunk_index=0,
                        embedding_vector=None,
                    ),
                ]
            )
            db.commit()

    def tearDown(self):
        self.patches.close()
        self.engine.dispose()

    def test_course_library_and_parsed_pdf_are_both_searchable(self):
        service = SearchService.__new__(SearchService)
        with self.session_factory() as db:
            pdf_results = service._search_pdf_segments_lexically(
                db,
                query="KMP string",
                document_ids=["document-1"],
                limit=5,
            )
            course_results = service._search_course_library(
                db,
                query="KMP string",
                course_id="course-1",
                limit=5,
            )

        merged = service._merge_source_results(pdf_results, course_results, top_k=5)
        self.assertTrue(any(item.document_id == "document-1" for item in merged))
        self.assertTrue(
            any(item.document_id.startswith("knowledge-point:") for item in merged)
        )

    def test_chat_note_is_registered_and_completed_in_resource_package(self):
        service = ResourcePackageService()
        resource = service.register_chat_note(
            user_id="user-1",
            project_id="project-1",
            note_id="note-1",
            topic="String algorithms",
            custom_instructions="Include KMP",
        )

        self.assertEqual(resource.status, "generating")
        self.assertEqual(resource.content_json["target_id"], "note-1")
        service.finish_chat_note(
            project_id="project-1",
            generated_resource_id=resource.id,
            title="String algorithms note",
            description="Generated from chat",
            content="# Strings",
        )

        packages = service.list_resource_packages("user-1", "project-1")
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].status, "completed")
        self.assertEqual(packages[0].completed_resource_count, 1)
        self.assertEqual(packages[0].resources[0].status, "completed")
        self.assertEqual(packages[0].resources[0].content_text, "# Strings")

    def test_chat_note_progress_is_visible_before_package_completion(self):
        service = ResourcePackageService()
        resource = service.register_chat_note(
            user_id="user-1",
            project_id="project-1",
            note_id="note-1",
            topic="String algorithms",
        )

        service.update_chat_note_progress(
            project_id="project-1",
            generated_resource_id=resource.id,
            content="# Strings\n\nA growing explanation",
        )

        package = service.get_resource_package(
            "user-1", "project-1", resource.resource_package_id
        )
        self.assertEqual(package.status, "generating")
        self.assertEqual(package.resources[0].status, "generating")
        self.assertEqual(
            package.resources[0].content_text,
            "# Strings\n\nA growing explanation",
        )

        async def first_stream_event():
            stream = service.stream_resource_package_events(
                "user-1", "project-1", resource.resource_package_id
            )
            try:
                return await anext(stream)
            finally:
                await stream.aclose()

        event = asyncio.run(first_stream_event())
        self.assertEqual(event.event, "package_snapshot")
        self.assertEqual(
            event.payload["package"]["resources"][0]["content_text"],
            "# Strings\n\nA growing explanation",
        )

    def test_explicit_chat_note_starts_worker_without_diagnosis(self):
        calls = []

        class NoteServiceStub:
            @staticmethod
            def create_note(**_kwargs):
                return SimpleNamespace(id="note-fast")

            @staticmethod
            def queue_generation(**kwargs):
                calls.append(kwargs)

        service = ResourcePackageService(note_service=NoteServiceStub())
        resource = service.start_chat_note_generation(
            user_id="user-1",
            project_id="project-1",
            topic="最短路径",
            custom_instructions="包含 Dijkstra 示例",
        )

        self.assertEqual(resource.status, "generating")
        self.assertEqual(resource.content_json["target_id"], "note-fast")
        self.assertEqual(calls[0]["generated_resource_id"], resource.id)
        self.assertEqual(calls[0]["topic"], "最短路径")

    def test_chat_sources_are_deduplicated_by_document_not_segment(self):
        service = ChatService.__new__(ChatService)
        first_source = {
            "id": "segment-1",
            "segment_id": "segment-1",
            "document_id": "document-1",
            "title": "strings.pdf",
            "page_number": 3,
        }
        second_source = {
            **first_source,
            "id": "segment-2",
            "segment_id": "segment-2",
            "page_number": 4,
        }

        with self.session_factory() as db:
            source_ids: set[str] = set()
            first_part = service._create_source_document_part(
                first_source, db, source_ids, 0
            )
            self.assertIsNotNone(first_part)
            self.assertEqual(first_part.source_id, "document-1")
            source_ids.add(first_part.source_id)
            duplicate_part = service._create_source_document_part(
                second_source, db, source_ids, 1
            )

        self.assertIsNone(duplicate_part)

    def test_web_source_keeps_external_url_without_document_route(self):
        service = ChatService.__new__(ChatService)
        web_source = {
            "id": "https://www.moe.gov.cn/example",
            "title": "教育部人工智能教育指南",
            "url": "https://www.moe.gov.cn/example",
            "source": "moe.gov.cn",
            "published_at": "2026-08-01",
            "provider": "baidu_ai_search",
        }

        with self.session_factory() as db:
            part = service._create_source_document_part(web_source, db, set(), 0)

        self.assertIsNotNone(part)
        self.assertEqual(part.source_id, web_source["url"])
        self.assertEqual(part.media_type, "text/html")
        self.assertEqual(part.provider_metadata["url"], web_source["url"])
        self.assertEqual(part.provider_metadata["provider"], "baidu_ai_search")
        self.assertNotIn("document_id", part.provider_metadata)

    def test_enabled_web_search_is_run_before_tutor_generation(self):
        captured: dict = {}

        class FakeWebSearchClient:
            is_enabled = True

            async def search_web(self, query: str):
                captured["query"] = query
                return {
                    "provider": "baidu_ai_search",
                    "results": [
                        {
                            "id": "https://www.moe.gov.cn/guide",
                            "title": "人工智能教育指南",
                            "url": "https://www.moe.gov.cn/guide",
                            "snippet": "文章会生成图片来图解图论知识点。",
                            "source": "moe.gov.cn",
                            "published_at": "2026-08-01",
                        }
                    ],
                }

        class FakeChatbot:
            async def astream(self, state, **kwargs):
                captured["state"] = state
                captured["context"] = kwargs["context"]
                if False:
                    yield None

        service = ChatService.__new__(ChatService)
        service.web_search_client = FakeWebSearchClient()
        service.search_service = None
        service.usage_service = None
        service._queue_service = None
        service.llm_non_streaming = None
        service.resource_package_service = None
        service.learning_path_service = None
        service.chatbot = FakeChatbot()
        message = ChatMessageDto(
            id="message-1",
            chat_id="chat-1",
            role="user",
            created_at=datetime.now(),
            parts=[TextPartDto(text_content="请讲解图论知识点")],
        )

        async def collect(db):
            return [
                chunk
                async for chunk in service._get_response_stream(
                    query="请讲解图论知识点",
                    messages=[message],
                    project_id="project-1",
                    language_code="zh",
                    user_id="user-1",
                    assistant_message_id="assistant-1",
                    db_session=db,
                    web_search_enabled=True,
                )
            ]

        with self.session_factory() as db:
            chunks = asyncio.run(collect(db))

        self.assertEqual(captured["query"], "请讲解图论知识点")
        self.assertEqual(chunks[0].parts[0].source_id, "https://www.moe.gov.cn/guide")
        self.assertEqual(
            chunks[0].parts[0].provider_metadata["url"],
            "https://www.moe.gov.cn/guide",
        )
        latest_content = captured["state"]["messages"][-1]["content"]
        self.assertEqual(latest_content[-1]["text"], "请讲解图论知识点")
        self.assertIn(
            "生成图片来图解图论知识点",
            captured["context"].web_search_context,
        )
        self.assertFalse(captured["context"].web_search_enabled)

    def test_tool_snapshot_does_not_resend_accumulated_text_as_delta(self):
        parts = [
            TextPartDto(id="text-1", text_content="Already streamed"),
            ToolCallPartDto(
                id="tool-part-1",
                tool_call_id="tool-call-1",
                tool_name="resource_package_generate",
                tool_input={},
                tool_state="input-available",
            ),
        ]

        snapshot_parts = ChatService._non_text_stream_parts(parts)

        self.assertEqual(len(snapshot_parts), 1)
        self.assertEqual(snapshot_parts[0].id, "tool-part-1")
        self.assertFalse(any(part.type == "text" for part in snapshot_parts))


if __name__ == "__main__":
    unittest.main()
