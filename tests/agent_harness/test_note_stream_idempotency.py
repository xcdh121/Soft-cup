import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "edu-api"))

from routers.notes import _note_stream_locks, _stream_note_events


class _FakeNoteService:
    def __init__(self):
        self.content = ""

    def get_note(self, *, note_id, project_id):
        return SimpleNamespace(
            id=note_id,
            project_id=project_id,
            title="Generated note",
            description="Generated once",
            content=self.content,
        )


class _FakeTaskRunner:
    def __init__(self, note_service):
        self.note_service = note_service
        self.calls = 0

    async def stream_note(self, payload):
        self.calls += 1
        await asyncio.sleep(0.01)
        yield {
            "event": "note_delta",
            "note_id": payload["note_id"],
            "delta": "Hello",
            "content": "Hello",
        }
        self.note_service.content = "Hello world"
        yield {
            "event": "note_completed",
            "note_id": payload["note_id"],
            "title": "Generated note",
            "description": "Generated once",
            "content": self.note_service.content,
        }


class NoteStreamIdempotencyTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _note_stream_locks.clear()

    async def test_concurrent_requests_generate_the_note_only_once(self):
        service = _FakeNoteService()
        task_runner = _FakeTaskRunner(service)
        request = SimpleNamespace(topic="sorting", custom_instructions=None)

        async def collect():
            return [
                event
                async for event in _stream_note_events(
                    project_id="project_1",
                    note_id="note_1",
                    request=request,
                    service=service,
                    task_runner=task_runner,
                )
            ]

        first, second = await asyncio.gather(collect(), collect())

        self.assertEqual(task_runner.calls, 1)
        self.assertEqual(first[-1]["event"], "note_completed")
        self.assertEqual(second[-1]["event"], "note_completed")
        self.assertTrue(second[-1]["cached"])


if __name__ == "__main__":
    unittest.main()
