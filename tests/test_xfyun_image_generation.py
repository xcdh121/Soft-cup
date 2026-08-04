import base64
import json
import unittest
from datetime import UTC, datetime

import httpx
from edu_core.services.xfyun_image_generation import (
    XfyunImageGenerationClient,
    XfyunImageGenerationConfig,
    XfyunImageGenerationError,
    build_auth_params,
)


class XfyunImageGenerationClientTests(unittest.IsolatedAsyncioTestCase):
    def test_auth_params_use_documented_request_line(self):
        params = build_auth_params(
            base_url="https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti",
            api_key="key-1",
            api_secret="secret-1",
            current_date=datetime(2023, 5, 22, 5, 44, 14, tzinfo=UTC),
        )

        authorization = base64.b64decode(params["authorization"]).decode("utf-8")
        self.assertEqual(params["host"], "spark-api.cn-huabei-1.xf-yun.com")
        self.assertEqual(params["date"], "Mon, 22 May 2023 05:44:14 GMT")
        self.assertIn('api_key="key-1"', authorization)
        self.assertIn('headers="host date request-line"', authorization)
        self.assertIn('signature="', authorization)

    async def test_generate_sends_single_user_message_and_preserves_bytes(self):
        image_bytes = b"\x89PNG\r\n\x1a\noriginal-provider-bytes"
        captured: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "header": {
                        "code": 0,
                        "message": "Success",
                        "sid": "sid-1",
                        "status": 2,
                    },
                    "payload": {
                        "choices": {
                            "status": 2,
                            "seq": 0,
                            "text": [
                                {
                                    "content": base64.b64encode(image_bytes).decode(
                                        "ascii"
                                    ),
                                    "index": 0,
                                    "role": "assistant",
                                }
                            ],
                        }
                    },
                },
            )

        client = XfyunImageGenerationClient(
            XfyunImageGenerationConfig(
                enabled=True,
                app_id="app-1",
                api_key="key-1",
                api_secret="secret-1",
                base_url="https://example.test/v2.1/tti",
            ),
            transport=httpx.MockTransport(handler),
        )
        result = await client.generate("帮我画一座山", width=640, height=360, uid="u-1")

        request = captured["request"]
        body = captured["body"]
        self.assertEqual(request.url.path, "/v2.1/tti")
        self.assertIn("authorization", request.url.params)
        self.assertEqual(body["header"], {"app_id": "app-1", "uid": "u-1"})
        self.assertEqual(
            body["parameter"]["chat"],
            {"domain": "general", "width": 640, "height": 360},
        )
        self.assertEqual(
            body["payload"]["message"]["text"],
            [{"role": "user", "content": "帮我画一座山"}],
        )
        self.assertEqual(result["image_bytes"], image_bytes)
        self.assertEqual(result["sid"], "sid-1")

    async def test_generate_rejects_unsupported_resolution(self):
        client = XfyunImageGenerationClient(
            XfyunImageGenerationConfig(
                enabled=True,
                app_id="app",
                api_key="key",
                api_secret="secret",
            )
        )
        with self.assertRaisesRegex(XfyunImageGenerationError, "不支持的图片分辨率"):
            await client.generate("山", width=100, height=100)

    async def test_generate_surfaces_provider_error_code(self):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"header": {"code": 10022, "message": "sensitive image"}},
            )

        client = XfyunImageGenerationClient(
            XfyunImageGenerationConfig(
                enabled=True,
                app_id="app",
                api_key="key",
                api_secret="secret",
            ),
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(XfyunImageGenerationError, "10022"):
            await client.generate("山")


if __name__ == "__main__":
    unittest.main()
