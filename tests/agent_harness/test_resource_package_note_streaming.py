import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from edu_core.services.resource_packages import ResourcePackageService


class ResourcePackageNoteStreamingTest(unittest.IsolatedAsyncioTestCase):
    async def test_streamed_note_is_forwarded_and_embedded_once(self):
        calls = 0

        async def note_streamer(payload):
            nonlocal calls
            calls += 1
            self.assertEqual(payload["note_id"], "note_1")
            yield {
                "event": "note_delta",
                "note_id": "note_1",
                "delta": "Hello",
                "content": "Hello",
            }
            yield {
                "event": "note_completed",
                "note_id": "note_1",
                "title": "Sorting note",
                "description": "A streamed note",
                "content": "Hello world",
            }

        note_service = MagicMock()
        note_service.get_note.return_value = SimpleNamespace(
            title="Sorting note",
            description="A streamed note",
            content="Hello world",
        )
        service = ResourcePackageService(
            note_service=note_service,
            note_streamer=note_streamer,
        )
        events = []

        async def event_sink(event):
            events.append(event)

        generated = await service._stream_recommended_note(
            generated={
                "title": "Queued note",
                "summary": None,
                "content_json": {"stream_on_client": True},
            },
            recommendation={
                "target_id": "note_1",
                "topic": "sorting",
                "custom_instructions": "Use examples",
            },
            project_id="project_1",
            package_id="package_1",
            resource_id="resource_1",
            event_sink=event_sink,
        )

        self.assertEqual(calls, 1)
        self.assertEqual(generated["title"], "Sorting note")
        self.assertEqual(generated["content_text"], "Hello world")
        self.assertFalse(generated["content_json"]["stream_on_client"])
        self.assertEqual([event.event for event in events], [
            "resource_delta",
            "resource_delta",
        ])
        self.assertEqual(events[-1].payload["content"], "Hello world")
        self.assertTrue(events[-1].payload["completed"])


if __name__ == "__main__":
    unittest.main()
