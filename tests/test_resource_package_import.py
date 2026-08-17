import asyncio
import unittest
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

    def test_package_items_start_concurrently_in_local_mode(self):
        service = ResourcePackageService(
            agent_orchestration_service=MagicMock(),
            local_generation_concurrency=2,
        )
        diagnosis = SimpleNamespace(
            diagnosis_id="diagnosis-concurrent",
            run_id="run-concurrent",
            learning_path={},
            recommendations=[],
            diagnosis={},
        )
        started: set[str] = set()
        both_started = asyncio.Event()

        async def fake_diagnosis(**_kwargs):
            return diagnosis

        async def generate_item(**kwargs):
            started.add(kwargs["resource_type"])
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=1)
            resource_type = kwargs["resource_type"]
            return (
                {
                    "title": f"Generated {resource_type}",
                    "summary": "Concurrent generation",
                    "format": "json",
                    "content_json": {"resource_type": resource_type},
                },
                "completed",
            )

        service._get_or_create_diagnosis = fake_diagnosis
        service._get_diagnosis_trace = lambda _diagnosis: []
        service._generate_package_resource = generate_item

        result = asyncio.run(
            service.generate_resource_package(
                user_id="user-1",
                project_id="project-1",
                payload={
                    "target_topic": "Concurrency",
                    "resource_types": ["lecture_note", "mind_map"],
                },
            )
        )

        self.assertEqual(started, {"lecture_note", "mind_map"})
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.completed_resource_count, 2)

    def test_remote_queue_receives_one_idempotent_job_per_resource(self):
        class RemoteQueue:
            is_remote = True

            def __init__(self):
                self.messages = []

            def send_message(self, message):
                self.messages.append(message)
                return f"job-{len(self.messages)}"

        queue = RemoteQueue()
        service = ResourcePackageService(
            agent_orchestration_service=MagicMock(),
            queue_service=queue,
        )
        diagnosis = SimpleNamespace(
            diagnosis_id="diagnosis-queued",
            run_id="run-queued",
            learning_path={},
            recommendations=[],
            diagnosis={},
        )

        async def fake_diagnosis(**_kwargs):
            return diagnosis

        service._get_or_create_diagnosis = fake_diagnosis
        service._get_diagnosis_trace = lambda _diagnosis: []

        result = asyncio.run(
            service.generate_resource_package(
                user_id="user-1",
                project_id="project-1",
                payload={
                    "target_topic": "Queued concurrency",
                    "resource_types": ["lecture_note", "mind_map"],
                },
            )
        )

        self.assertEqual(result.status, "generating")
        self.assertEqual([item.status for item in result.resources], ["pending", "pending"])
        self.assertEqual(len(queue.messages), 2)
        self.assertEqual(
            {message["data"]["resource_id"] for message in queue.messages},
            {resource.id for resource in result.resources},
        )
        self.assertTrue(
            all(
                message["type"].value == "resource_package_item"
                for message in queue.messages
            )
        )

    def test_concurrent_item_failure_does_not_cancel_siblings(self):
        service = ResourcePackageService(
            agent_orchestration_service=MagicMock(),
            local_generation_concurrency=2,
        )
        diagnosis = SimpleNamespace(
            diagnosis_id="diagnosis-failure-isolation",
            run_id="run-failure-isolation",
            learning_path={},
            recommendations=[],
            diagnosis={},
        )

        async def fake_diagnosis(**_kwargs):
            return diagnosis

        async def generate_item(**kwargs):
            if kwargs["resource_type"] == "mind_map":
                raise RuntimeError("mind map provider unavailable")
            return (
                {
                    "title": "Completed note",
                    "summary": "Sibling completed",
                    "format": "markdown",
                    "content_text": "# Completed",
                },
                "completed",
            )

        service._get_or_create_diagnosis = fake_diagnosis
        service._get_diagnosis_trace = lambda _diagnosis: []
        service._generate_package_resource = generate_item

        result = asyncio.run(
            service.generate_resource_package(
                user_id="user-1",
                project_id="project-1",
                payload={
                    "target_topic": "Failure isolation",
                    "resource_types": ["lecture_note", "mind_map"],
                },
            )
        )

        statuses = {item.resource_type: item.status for item in result.resources}
        self.assertEqual(statuses["lecture_note"], "completed")
        self.assertEqual(statuses["mind_map"], "failed")
        self.assertEqual(result.completed_resource_count, 1)
        self.assertEqual(result.failed_resource_count, 1)
        self.assertEqual(result.status, "failed")

    def test_manual_single_note_streams_without_diagnosis_round_trip(self):
        observed_payloads = []

        async def note_streamer(payload):
            observed_payloads.append(payload)
            yield {
                "event": "note_delta",
                "note_id": payload["note_id"],
                "delta": "# Graphs",
                "content": "# Graphs",
            }
            yield {
                "event": "note_completed",
                "note_id": payload["note_id"],
                "title": "Graph algorithms",
                "description": "A direct streamed note",
                "content": "# Graphs\n\nBreadth-first search.",
            }

        orchestration = MagicMock()

        class DirectNoteService:
            def create_note(inner_self, **kwargs):
                note_id = "direct-note-1"
                note = Note(id=note_id, **kwargs)
                with self.session_factory() as db:
                    db.add(note)
                    db.commit()
                return SimpleNamespace(
                    id=note_id,
                    title=kwargs["title"],
                    description=kwargs.get("description"),
                    content=kwargs["content"],
                )

        service = ResourcePackageService(
            agent_orchestration_service=orchestration,
            note_service=DirectNoteService(),
            note_streamer=note_streamer,
        )
        events = []

        async def event_sink(event):
            events.append(event)

        async def generate():
            return await service.generate_resource_package(
                user_id="user-1",
                project_id="project-1",
                payload={
                    "target_topic": "Graph algorithms",
                    "resource_types": ["lecture_note"],
                    "generation_mode": "manual",
                },
                event_sink=event_sink,
            )

        result = asyncio.run(generate())

        self.assertEqual(result.status, "completed")
        self.assertEqual(
            result.resources[0].content_text,
            "# Graphs\n\nBreadth-first search.",
        )
        self.assertTrue(result.generation_params["diagnosis_skipped"])
        self.assertEqual(len(observed_payloads), 1)
        self.assertEqual(
            observed_payloads[0]["document_content"],
            "No source context was selected.",
        )
        self.assertEqual(
            [event.event for event in events].count("resource_delta"),
            2,
        )
        orchestration.generate_diagnosis.assert_not_called()
        orchestration.generate_recommendations.assert_not_called()


if __name__ == "__main__":
    unittest.main()
