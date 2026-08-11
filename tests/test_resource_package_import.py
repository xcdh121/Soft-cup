import asyncio
import unittest
from contextlib import suppress
from unittest.mock import patch

from edu_core.services.resource_packages import ResourcePackageService
from edu_db.models import Base, GeneratedResource, Note, Project, ResourcePackage, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class ResourcePackageImportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session_patch = patch(
            "edu_core.services.resource_packages.get_session_factory",
            return_value=self.session_factory,
        )
        self.session_patch.start()
        with self.session_factory() as db:
            db.add(
                User(
                    id="user-1",
                    username="test-user",
                    name="Test",
                    email="test@example.com",
                )
            )
            db.add(Project(id="project-1", owner_id="user-1", name="AI Study"))
            db.commit()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def test_imports_completed_text_resource(self):
        service = ResourcePackageService()

        result = service.import_resource(
            user_id="user-1",
            project_id="project-1",
            title="课堂手写笔记",
            summary="讯飞手写识别结果",
            origin="handwriting",
            resource_type="lecture_note",
            content_format="text",
            content_text="二叉树的遍历方式",
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.resource_count, 1)
        self.assertEqual(result.resources[0].content_text, "二叉树的遍历方式")
        with self.session_factory() as db:
            self.assertEqual(db.query(ResourcePackage).count(), 1)
            self.assertEqual(db.query(GeneratedResource).count(), 1)

    def test_imports_pdf_file_resource(self):
        service = ResourcePackageService()

        result = service.import_resource(
            user_id="user-1",
            project_id="project-1",
            title="PDF 识别文档",
            summary="讯飞 PDF OCR 结果",
            origin="pdf_ocr",
            resource_type="reading_material",
            content_format="word",
            file_url="https://example.test/result.docx",
        )

        self.assertEqual(
            result.resources[0].file_url, "https://example.test/result.docx"
        )

    def test_finds_generation_status_by_linked_target(self):
        with self.session_factory() as db:
            package = ResourcePackage(
                id="package-1",
                project_id="project-1",
                user_id="user-1",
                title="Lists package",
                status="generating",
                target_topic="Lists",
            )
            package.resources.append(
                GeneratedResource(
                    id="resource-1",
                    project_id="project-1",
                    user_id="user-1",
                    resource_type="practice_set",
                    title="Lists quiz",
                    status="generating",
                    content_json={
                        "target_id": "quiz-1",
                        "target_type": "quiz",
                    },
                )
            )
            db.add(package)
            db.commit()

        result = ResourcePackageService().get_generated_resource_by_target(
            "user-1", "project-1", "quiz", "quiz-1"
        )

        self.assertEqual(result.id, "resource-1")
        self.assertEqual(result.status, "generating")

    def test_reconciles_false_note_failure_and_deletes_empty_video_failure(self):
        with self.session_factory() as db:
            db.add(
                Note(
                    id="note-complete",
                    project_id="project-1",
                    title="Completed note",
                    content="# Generated content",
                )
            )
            package = ResourcePackage(
                id="package-reconcile",
                project_id="project-1",
                user_id="user-1",
                title="Recovered package",
                status="failed",
                target_topic="Recovery",
                resource_count=2,
                completed_resource_count=0,
                failed_resource_count=2,
            )
            package.resources.extend(
                [
                    GeneratedResource(
                        id="resource-note-complete",
                        project_id="project-1",
                        user_id="user-1",
                        resource_type="lecture_note",
                        title="Completed note",
                        status="failed",
                        content_json={
                            "target_id": "note-complete",
                            "target_type": "note",
                        },
                        error_message="Interrupted",
                    ),
                    GeneratedResource(
                        id="resource-video-empty",
                        project_id="project-1",
                        user_id="user-1",
                        resource_type="video_recommendations",
                        title="Empty videos",
                        status="failed",
                        content_json={},
                        error_message="No video results found",
                    ),
                ]
            )
            db.add(package)
            db.commit()

        result = ResourcePackageService().reconcile_generated_resources(
            "user-1", "project-1"
        )

        self.assertEqual(result, {"repaired": 1, "deleted": 1})
        with self.session_factory() as db:
            note_resource = db.get(GeneratedResource, "resource-note-complete")
            self.assertIsNotNone(note_resource)
            self.assertEqual(note_resource.status, "completed")
            self.assertIsNone(note_resource.error_message)
            self.assertIsNone(db.get(GeneratedResource, "resource-video-empty"))
            package = db.get(ResourcePackage, "package-reconcile")
            self.assertEqual(package.status, "completed")
            self.assertEqual(package.resource_count, 1)
            self.assertEqual(package.completed_resource_count, 1)
            self.assertEqual(package.failed_resource_count, 0)

    def test_streams_completed_note_snapshot(self):
        with self.session_factory() as db:
            db.add(
                Note(
                    id="note-1",
                    project_id="project-1",
                    title="Lists note",
                    description="Incremental note",
                    content="# Lists\n\nA list is linear.",
                )
            )
            package = ResourcePackage(
                id="package-note",
                project_id="project-1",
                user_id="user-1",
                title="Lists package",
                status="completed",
                target_topic="Lists",
            )
            package.resources.append(
                GeneratedResource(
                    id="resource-note",
                    project_id="project-1",
                    user_id="user-1",
                    resource_type="lecture_note",
                    title="Lists note",
                    status="completed",
                    content_json={
                        "target_id": "note-1",
                        "target_type": "note",
                    },
                )
            )
            db.add(package)
            db.commit()

        async def collect():
            return [
                snapshot
                async for snapshot in ResourcePackageService().stream_generated_note_snapshots(
                    "user-1", "project-1", "resource-note", "note-1"
                )
            ]

        snapshots = asyncio.run(collect())

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["status"], "completed")
        self.assertIn("A list is linear", snapshots[0]["content"])

    def test_package_stream_starts_with_a_durable_snapshot(self):
        with self.session_factory() as db:
            package = ResourcePackage(
                id="package-stream",
                project_id="project-1",
                user_id="user-1",
                title="Streaming package",
                status="completed",
                target_topic="Streams",
                preferred_resource_types=["lecture_note"],
                resource_count=1,
                completed_resource_count=1,
            )
            package.resources.append(
                GeneratedResource(
                    id="resource-stream",
                    project_id="project-1",
                    user_id="user-1",
                    resource_type="lecture_note",
                    title="Streaming note",
                    status="completed",
                    content_text="# Streamed",
                )
            )
            db.add(package)
            db.commit()

        async def collect():
            return [
                event
                async for event in ResourcePackageService().stream_resource_package_events(
                    "user-1", "project-1", "package-stream"
                )
            ]

        events = asyncio.run(collect())

        self.assertEqual(events[-1].event, "package_snapshot")
        snapshot = events[-1].payload["package"]
        self.assertEqual(snapshot["id"], "package-stream")
        self.assertEqual(snapshot["resources"][0]["content_text"], "# Streamed")

    def test_generation_persists_package_before_diagnosis_finishes(self):
        service = ResourcePackageService()

        async def exercise():
            diagnosis_started = asyncio.Event()
            package_started = asyncio.Event()
            events = []

            async def slow_diagnosis(**_kwargs):
                diagnosis_started.set()
                await asyncio.Event().wait()

            async def event_sink(event):
                events.append(event)
                if event.event == "package_started":
                    package_started.set()

            service._get_or_create_diagnosis = slow_diagnosis
            task = asyncio.create_task(
                service.generate_resource_package(
                    user_id="user-1",
                    project_id="project-1",
                    payload={
                        "target_topic": "Immediate navigation",
                        "resource_types": ["lecture_note"],
                    },
                    event_sink=event_sink,
                )
            )
            await asyncio.wait_for(package_started.wait(), timeout=1)
            await asyncio.wait_for(diagnosis_started.wait(), timeout=1)

            package_id = events[0].package_id
            with self.session_factory() as db:
                package = db.query(ResourcePackage).filter_by(id=package_id).one()
                self.assertEqual(package.status, "generating")
                self.assertEqual(package.preferred_resource_types, ["lecture_note"])

            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
