import base64
import json
import unittest
from urllib.parse import parse_qs

import httpx
from xfyun_handwriting import (
    XfyunHandwritingClient,
    XfyunHandwritingConfig,
    XfyunHandwritingError,
    _build_auth_headers,
)


class XfyunHandwritingClientTests(unittest.IsolatedAsyncioTestCase):
    def test_auth_headers_contain_documented_parameters_and_checksum(self):
        headers = _build_auth_headers(
            app_id="app-1",
            api_key="secret-key",
            language="cn|en",
            include_location=False,
            current_time=1_500_000_000,
        )

        parameters = json.loads(base64.b64decode(headers["X-Param"]))
        self.assertEqual(parameters, {"language": "cn|en", "location": "false"})
        self.assertEqual(headers["X-Appid"], "app-1")
        self.assertEqual(headers["X-CurTime"], "1500000000")
        self.assertEqual(len(headers["X-CheckSum"]), 32)

    async def test_recognize_sends_form_image_and_normalizes_lines(self):
        captured: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["form"] = parse_qs(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "sid": "ocr-session-1",
                    "data": {
                        "block": [
                            {
                                "line": [
                                    {
                                        "confidence": "0.98",
                                        "word": [
                                            {"content": "人工"},
                                            {"content": "智能"},
                                        ],
                                    },
                                    {"word": [{"content": "助力学习"}]},
                                ]
                            }
                        ]
                    },
                },
            )

        client = XfyunHandwritingClient(
            XfyunHandwritingConfig(
                enabled=True,
                app_id="app-1",
                api_key="secret-key",
                base_url="https://example.test/ocr",
            ),
            transport=httpx.MockTransport(handler),
        )

        result = await client.recognize(b"image-bytes")

        self.assertEqual(
            captured["form"]["image"],
            [base64.b64encode(b"image-bytes").decode("ascii")],
        )
        self.assertEqual(captured["headers"]["x-appid"], "app-1")
        self.assertEqual(result["text"], "人工智能\n助力学习")
        self.assertEqual(result["lines"][0]["confidence"], 0.98)
        self.assertEqual(result["sid"], "ocr-session-1")

    async def test_recognize_surfaces_provider_error(self):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"code": "10106", "desc": "invalid parameter|invalid X-Appid"},
            )

        client = XfyunHandwritingClient(
            XfyunHandwritingConfig(
                enabled=True,
                app_id="bad-app",
                api_key="bad-key",
            ),
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaisesRegex(XfyunHandwritingError, "10106"):
            await client.recognize(b"image-bytes")


if __name__ == "__main__":
    unittest.main()
