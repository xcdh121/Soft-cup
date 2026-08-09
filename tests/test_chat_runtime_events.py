import unittest
from datetime import datetime

from edu_core.schemas.chats import (
    StreamingChatMessage,
    TextPartDto,
    ToolCallPartDto,
)
from edu_core.services.chats import ChatService


class ChatRuntimeEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_exposes_six_server_observed_stages(self):
        service = ChatService.__new__(ChatService)

        async def fake_send_streaming_message(chat_id, _user_id, _parts):
            yield StreamingChatMessage(
                id="assistant-1",
                chat_id=chat_id,
                role="assistant",
                created_at=datetime.now(),
                parts=[],
                done=False,
                status="thinking",
            )
            yield StreamingChatMessage(
                id="assistant-1",
                chat_id=chat_id,
                role="assistant",
                created_at=datetime.now(),
                parts=[
                    TextPartDto(id="text-1", text_content="资源包已开始生成"),
                    ToolCallPartDto(
                        id="tool-1",
                        tool_call_id="call-1",
                        tool_name="resource_package_generate",
                        tool_input={"resource_types": ["programming_questions"]},
                        tool_output={"status": "generating"},
                        tool_state="output-available",
                    ),
                ],
                done=True,
            )

        service.send_streaming_message = fake_send_streaming_message
        events = [
            event
            async for event in service.stream_chat_events(
                "chat-1", "user-1", [{"type": "text", "text": "生成编程题"}]
            )
        ]
        runtime_events = [
            event.runtime_event for event in events if event.runtime_event is not None
        ]
        latest_by_id = {event.id: event for event in runtime_events}

        self.assertEqual(
            set(latest_by_id),
            {"coordinator", "context", "intent", "retrieval", "tool", "answer"},
        )
        self.assertEqual(latest_by_id["retrieval"].status, "skipped")
        self.assertEqual(latest_by_id["tool"].status, "completed")
        self.assertEqual(latest_by_id["answer"].status, "completed")


if __name__ == "__main__":
    unittest.main()
