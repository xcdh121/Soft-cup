import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from edu_core.services.resource_packages import ResourcePackageService


class ResourcePackageNoteStreamingTest(unittest.IsolatedAsyncioTestCase):
    async def test_quiz_questions_are_forwarded_one_at_a_time(self):
        async def quiz_streamer(payload):
            self.assertEqual(payload["quiz_id"], "quiz_1")
            yield {
                "event": "quiz_question_created",
                "quiz_id": "quiz_1",
                "question": {
                    "question_text": "What is a list?",
                    "option_a": "Linear collection",
                    "option_b": "Graph",
                    "option_c": "Tree",
                    "option_d": "Heap",
                    "correct_option": "a",
                    "explanation": "A list is linear.",
                    "difficulty_level": "easy",
                },
            }
            yield {
                "event": "quiz_question_created",
                "quiz_id": "quiz_1",
                "question": {
                    "question_text": "What is indexing?",
                    "option_a": "Lookup by position",
                    "option_b": "Sorting",
                    "option_c": "Deletion",
                    "option_d": "Hashing",
                    "correct_option": "a",
                    "explanation": "Indexes identify positions.",
                    "difficulty_level": "easy",
                },
            }
            yield {
                "event": "quiz_completed",
                "quiz_id": "quiz_1",
                "name": "Lists quiz",
                "count": 2,
            }

        service = ResourcePackageService(quiz_streamer=quiz_streamer)
        events = []

        async def event_sink(event):
            events.append(event)

        service._update_partial_generated_resource = MagicMock()
        generated = await service._stream_recommended_collection(
            generated={
                "title": "Queued quiz",
                "content_json": {"target_id": "quiz_1"},
                "preview_url": "/dashboard/p/project_1/q/quiz_1",
            },
            recommendation={"target_id": "quiz_1", "count": 2},
            resource_type="practice_set",
            project_id="project_1",
            package_id="package_1",
            resource_id="resource_1",
            event_sink=event_sink,
        )

        self.assertEqual(len(events), 4)
        self.assertEqual(len(events[0].payload["content_json"]["questions"]), 0)
        self.assertEqual(
            events[0].payload["preview_url"],
            "/dashboard/p/project_1/q/quiz_1",
        )
        self.assertEqual(len(events[1].payload["content_json"]["questions"]), 1)
        self.assertEqual(len(events[2].payload["content_json"]["questions"]), 2)
        self.assertTrue(events[-1].payload["completed"])
        self.assertEqual(generated["title"], "Lists quiz")
        self.assertEqual(len(generated["content_json"]["questions"]), 2)

    async def test_flashcards_are_forwarded_one_at_a_time(self):
        async def flashcard_streamer(payload):
            self.assertEqual(payload["group_id"], "group_1")
            yield {
                "event": "flashcard_created",
                "group_id": "group_1",
                "flashcard": {"question": "List", "answer": "Linear collection"},
            }
            yield {
                "event": "flashcards_completed",
                "group_id": "group_1",
                "name": "Lists flashcards",
                "count": 1,
            }

        service = ResourcePackageService(flashcard_streamer=flashcard_streamer)
        service._update_partial_generated_resource = MagicMock()
        events = []

        async def event_sink(event):
            events.append(event)

        generated = await service._stream_recommended_collection(
            generated={
                "title": "Queued flashcards",
                "content_json": {"target_id": "group_1"},
            },
            recommendation={"target_id": "group_1", "count": 1},
            resource_type="flashcards",
            project_id="project_1",
            package_id="package_1",
            resource_id="resource_1",
            event_sink=event_sink,
        )

        self.assertEqual(len(events[0].payload["content_json"]["flashcards"]), 0)
        self.assertEqual(len(events[1].payload["content_json"]["flashcards"]), 1)
        self.assertTrue(events[-1].payload["completed"])
        self.assertEqual(len(generated["content_json"]["flashcards"]), 1)

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
        service._update_partial_generated_resource = MagicMock()
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
        self.assertEqual(
            [event.event for event in events],
            [
                "resource_delta",
                "resource_delta",
            ],
        )
        self.assertEqual(events[-1].payload["content"], "Hello world")
        self.assertTrue(events[-1].payload["completed"])
        self.assertEqual(
            [
                call.kwargs["content_text"]
                for call in service._update_partial_generated_resource.call_args_list
            ],
            ["Hello", "Hello world"],
        )


if __name__ == "__main__":
    unittest.main()
