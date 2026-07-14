import unittest
from contextlib import ExitStack
from unittest.mock import patch

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
            self.patches.enter_context(
                patch(target, return_value=self.session_factory)
            )

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


if __name__ == "__main__":
    unittest.main()
