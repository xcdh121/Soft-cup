import base64
import json
import unittest
from datetime import UTC, datetime

import httpx
from xfyun_translation import (
    XfyunTranslationClient,
    XfyunTranslationConfig,
    XfyunTranslationError,
    _build_auth_params,
)


class XfyunTranslationClientTests(unittest.IsolatedAsyncioTestCase):
    def test_auth_params_use_documented_hmac_shape(self):
        params = _build_auth_params(
            base_url="https://itrans.xf-yun.com/v1/its",
            api_key="key-1",
            api_secret="secret-1",
            current_date=datetime(2021, 11, 18, 3, 5, 18, tzinfo=UTC),
        )

        authorization = base64.b64decode(params["authorization"]).decode("utf-8")
        self.assertEqual(params["host"], "itrans.xf-yun.com")
        self.assertEqual(params["date"], "Thu, 18 Nov 2021 03:05:18 GMT")
        self.assertIn('api_key="key-1"', authorization)
        self.assertIn('headers="host date request-line"', authorization)
        self.assertIn('signature="', authorization)

    async def test_translate_encodes_text_and_decodes_result(self):
        captured: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            body = json.loads(request.content)
            source = base64.b64decode(body["payload"]["input_data"]["text"]).decode(
                "utf-8"
            )
            self.assertEqual(source, "这是测试")
            result = {
                "trans_result": {"src": source, "dst": "This is a test"},
                "from": "cn",
                "to": "en",
            }
            return httpx.Response(
                200,
                json={
                    "header": {"code": 0, "message": "success", "sid": "sid-1"},
                    "payload": {
                        "result": {
                            "text": base64.b64encode(
                                json.dumps(result, ensure_ascii=False).encode("utf-8")
                            ).decode("ascii")
                        }
                    },
                },
            )

        client = XfyunTranslationClient(
            XfyunTranslationConfig(
                enabled=True,
                app_id="app-1",
                api_key="key-1",
                api_secret="secret-1",
                base_url="https://example.test/v1/its",
            ),
            transport=httpx.MockTransport(handler),
        )
        result = await client.translate(
            "这是测试", from_language="cn", to_language="en"
        )

        request = captured["request"]
        self.assertEqual(request.url.path, "/v1/its")
        self.assertIn("authorization", request.url.params)
        self.assertEqual(result["translated_text"], "This is a test")
        self.assertEqual(result["sid"], "sid-1")

    async def test_translate_surfaces_provider_error(self):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"header": {"code": 10005, "message": "invalid parameter"}},
            )

        client = XfyunTranslationClient(
            XfyunTranslationConfig(
                enabled=True,
                app_id="app",
                api_key="key",
                api_secret="secret",
            ),
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(XfyunTranslationError, "10005"):
            await client.translate("text", from_language="en", to_language="cn")


if __name__ == "__main__":
    unittest.main()
