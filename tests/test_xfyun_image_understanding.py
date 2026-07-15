import base64
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

from edu_core.services.chats import ChatService
from edu_core.storage import LocalStorageService
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
        chat_service = SimpleNamespace(
            upload_chat_file=Mock(
                return_value=(
                    "projects/project-1/chat-files/chat-1/image-id-question.png"
                )
            )
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
            project_id="project-1",
            chat_id="chat-1",
            user_id="user-1",
            chat_service=chat_service,
            image_client=image_client,
        )

        self.assertEqual(parts[0], {"type": "text", "text": "请讲解这道题"})
        self.assertEqual(parts[1]["type"], "file")
        self.assertEqual(parts[1]["file_name"], "question.png")
        self.assertEqual(
            parts[1]["file_url"],
            "/api/v1/projects/project-1/chats/chat-1/files/image-id-question.png",
        )
        self.assertTrue(parts[2]["text"].startswith("[图片理解上下文:question.png]"))
        self.assertIn("二次函数", parts[2]["text"])
        image_client.understand.assert_awaited_once()
        chat_service.upload_chat_file.assert_called_once_with(
            b"png-bytes",
            "question.png",
            "project-1",
            "chat-1",
        )
        self.assertIn(
            "请讲解这道题",
            image_client.understand.await_args.kwargs["question"],
        )

    async def test_chat_rejects_pdf_that_bypasses_upload_endpoint(self):
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
                project_id="project-1",
                chat_id="chat-1",
                user_id="user-1",
                chat_service=SimpleNamespace(upload_chat_file=Mock()),
                image_client=SimpleNamespace(is_enabled=True),
            )

        self.assertEqual(context.exception.status_code, 400)

    async def test_chat_accepts_a_persisted_pdf_with_ocr_context(self):
        file_path = SimpleNamespace(is_file=Mock(return_value=True))
        chat_service = SimpleNamespace(resolve_chat_file=Mock(return_value=file_path))
        body = ChatCompletionRequest.model_validate(
            {
                "parts": [
                    {
                        "type": "file",
                        "mediaType": "application/pdf",
                        "filename": "notes.pdf",
                        "url": (
                            "/api/v1/projects/project-1/chats/chat-1/files/"
                            "file-id-notes.pdf"
                        ),
                    },
                    {
                        "type": "text",
                        "text": "[PDF识别上下文:notes.pdf]\n第一章 函数",
                    },
                ]
            }
        )

        parts = await _prepare_chat_parts(
            body,
            project_id="project-1",
            chat_id="chat-1",
            user_id="user-1",
            chat_service=chat_service,
            image_client=SimpleNamespace(is_enabled=True),
        )

        self.assertEqual(parts[0]["file_type"], "application/pdf")
        self.assertIn("第一章 函数", parts[1]["text"])
        chat_service.resolve_chat_file.assert_called_once_with(
            project_id="project-1",
            chat_id="chat-1",
            file_key="file-id-notes.pdf",
        )

    def test_chat_service_persists_lightweight_image_metadata(self):
        service = ChatService.__new__(ChatService)
        db = SimpleNamespace(add=Mock())

        parts, text_parts = service._process_user_message_parts(
            [
                {
                    "type": "file",
                    "file_name": "question.png",
                    "file_type": "image/png",
                    "file_url": (
                        "/api/v1/projects/project-1/chats/chat-1/files/"
                        "image-id-question.png"
                    ),
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
        self.assertEqual(
            parts[0].file_url,
            "/api/v1/projects/project-1/chats/chat-1/files/image-id-question.png",
        )
        self.assertEqual(text_parts, ["[图片理解上下文:question.png]\n一道函数题"])
        self.assertEqual(db.add.call_count, 2)

    def test_chat_file_storage_sanitizes_names_and_blocks_traversal(self):
        service = ChatService.__new__(ChatService)
        with tempfile.TemporaryDirectory() as storage_root:
            service.storage = LocalStorageService(storage_root)
            relative_path = service.upload_chat_file(
                b"image-bytes",
                "../question.png",
                "project-1",
                "chat-1",
            )

            self.assertNotIn("..", relative_path)
            file_key = relative_path.rsplit("/", 1)[-1]
            self.assertEqual(
                service.resolve_chat_file(
                    project_id="project-1",
                    chat_id="chat-1",
                    file_key=file_key,
                ).read_bytes(),
                b"image-bytes",
            )
            with self.assertRaises(ValueError):
                service.resolve_chat_file(
                    project_id="project-1",
                    chat_id="chat-1",
                    file_key="../question.png",
                )


if __name__ == "__main__":
    unittest.main()
