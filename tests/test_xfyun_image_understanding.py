import base64
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

from edu_core.services.chats import ChatService
from fastapi import HTTPException

API_SRC = Path(__file__).resolve().parents[1] / "src" / "edu-api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from routers.chats import _prepare_chat_parts  # noqa: E402
from routers.schemas import ChatCompletionRequest  # noqa: E402
from xfyun_image_understanding import (  # noqa: E402
    XfyunImageUnderstandingClient,
    XfyunImageUnderstandingConfig,
    build_authenticated_url,
    build_request_payload,
)


class _FakeWebSocket:
    def __init__(self, responses: list[dict]):
        self.responses = iter(json.dumps(item) for item in responses)
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def recv(self) -> str:
        return next(self.responses)


class _FakeConnection:
    def __init__(self, websocket: _FakeWebSocket):
        self.websocket = websocket

    async def __aenter__(self) -> _FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *_args) -> None:
        return None


class XfyunImageUnderstandingTests(unittest.IsolatedAsyncioTestCase):
    def test_authenticated_url_contains_documented_hmac_fields(self):
        url = build_authenticated_url(
            "wss://spark-api.example.test/v2.1/image",
            api_key="key-1",
            api_secret="secret-1",
            now=datetime(2026, 7, 14, 8, 0, tzinfo=UTC),
        )

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        authorization = base64.b64decode(query["authorization"][0]).decode()

        self.assertEqual(parsed.scheme, "wss")
        self.assertEqual(parsed.path, "/v2.1/image")
        self.assertEqual(query["host"], ["spark-api.example.test"])
        self.assertIn('api_key="key-1"', authorization)
        self.assertIn('algorithm="hmac-sha256"', authorization)
        self.assertIn('headers="host date request-line"', authorization)

    def test_request_payload_places_image_before_question(self):
        payload = build_request_payload(
            app_id="app-1",
            image=b"image-bytes",
            question="这张图讲了什么?",
            domain="imagev3",
            max_tokens=2048,
            uid="user-1",
        )

        messages = payload["payload"]["message"]["text"]
        self.assertEqual(messages[0]["content_type"], "image")
        self.assertEqual(
            messages[0]["content"],
            base64.b64encode(b"image-bytes").decode("ascii"),
        )
        self.assertEqual(messages[1]["content"], "这张图讲了什么?")
        self.assertEqual(payload["parameter"]["chat"]["domain"], "imagev3")

    async def test_understand_collects_streamed_text(self):
        websocket = _FakeWebSocket(
            [
                {
                    "header": {"code": 0, "status": 1},
                    "payload": {
                        "choices": {
                            "status": 1,
                            "text": [{"content": "图片包含"}],
                        }
                    },
                },
                {
                    "header": {"code": 0, "status": 2},
                    "payload": {
                        "choices": {
                            "status": 2,
                            "text": [{"content": "一条抛物线。"}],
                        }
                    },
                },
            ]
        )
        captured_urls: list[str] = []

        def connector(url: str) -> _FakeConnection:
            captured_urls.append(url)
            return _FakeConnection(websocket)

        client = XfyunImageUnderstandingClient(
            XfyunImageUnderstandingConfig(
                enabled=True,
                app_id="app-1",
                api_key="key-1",
                api_secret="secret-1",
            ),
            connector=connector,
        )

        result = await client.understand(
            b"image-bytes",
            question="分析图片",
            uid="user-1",
        )

        self.assertEqual(result, "图片包含一条抛物线。")
        self.assertEqual(len(captured_urls), 1)
        self.assertEqual(websocket.sent[0]["header"]["uid"], "user-1")

    async def test_chat_image_becomes_hidden_vision_context(self):
        image_client = SimpleNamespace(
            is_enabled=True,
            understand=AsyncMock(return_value="图中是一道二次函数题。"),
        )
        body = ChatCompletionRequest.model_validate(
            {
                "parts": [
                    {"type": "text", "text": "请讲解这道题"},
                    {
                        "type": "file",
                        "mediaType": "image/png",
                        "filename": "question.png",
                        "url": "data:image/png;base64,"
                        + base64.b64encode(b"png-bytes").decode("ascii"),
                    },
                ]
            }
        )

        parts = await _prepare_chat_parts(
            body,
            user_id="user-1",
            image_client=image_client,
        )

        self.assertEqual(parts[0], {"type": "text", "text": "请讲解这道题"})
        self.assertEqual(parts[1]["type"], "file")
        self.assertEqual(parts[1]["file_name"], "question.png")
        self.assertEqual(parts[1]["file_url"], "")
        self.assertTrue(parts[2]["text"].startswith("[图片理解上下文:question.png]"))
        self.assertIn("二次函数", parts[2]["text"])
        image_client.understand.assert_awaited_once()
        self.assertIn(
            "请讲解这道题",
            image_client.understand.await_args.kwargs["question"],
        )

    async def test_chat_rejects_unsupported_attachment_type(self):
        body = ChatCompletionRequest.model_validate(
            {
                "parts": [
                    {
                        "type": "file",
                        "mediaType": "application/pdf",
                        "filename": "notes.pdf",
                        "url": "data:application/pdf;base64,AA==",
                    }
                ]
            }
        )

        with self.assertRaises(HTTPException) as context:
            await _prepare_chat_parts(
                body,
                user_id="user-1",
                image_client=SimpleNamespace(is_enabled=True),
            )

        self.assertEqual(context.exception.status_code, 415)

    def test_chat_service_persists_lightweight_image_metadata(self):
        service = ChatService.__new__(ChatService)
        db = SimpleNamespace(add=Mock())

        parts, text_parts = service._process_user_message_parts(
            [
                {
                    "type": "file",
                    "file_name": "question.png",
                    "file_type": "image/png",
                    "file_url": "",
                },
                {
                    "type": "text",
                    "text": "[图片理解上下文:question.png]\n一道函数题",
                },
            ],
            SimpleNamespace(id="message-1"),
            db,
        )

        self.assertEqual(parts[0].file_name, "question.png")
        self.assertEqual(parts[0].file_type, "image/png")
        self.assertEqual(parts[0].file_url, "")
        self.assertEqual(text_parts, ["[图片理解上下文:question.png]\n一道函数题"])
        self.assertEqual(db.add.call_count, 2)


if __name__ == "__main__":
    unittest.main()
