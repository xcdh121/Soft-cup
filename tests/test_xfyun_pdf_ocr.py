import base64
import hashlib
import hmac
import unittest

import httpx
from xfyun_pdf_ocr import (
    XfyunPdfOcrClient,
    XfyunPdfOcrConfig,
    XfyunPdfOcrError,
    _build_auth_headers,
)


class XfyunPdfOcrClientTests(unittest.IsolatedAsyncioTestCase):
    def test_auth_headers_match_documented_algorithm(self):
        headers = _build_auth_headers(
            app_id="app-1", secret="secret-key", current_time=1_500_000_000
        )

        auth = hashlib.md5(b"app-11500000000", usedforsecurity=False).hexdigest()
        expected = base64.b64encode(
            hmac.new(b"secret-key", auth.encode(), hashlib.sha1).digest()
        ).decode()
        self.assertEqual(
            headers,
            {
                "appId": "app-1",
                "timestamp": "1500000000",
                "signature": expected,
            },
        )

    async def test_start_task_uploads_pdf_and_normalizes_response(self):
        captured: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(
                200,
                json={
                    "flag": True,
                    "code": 0,
                    "desc": "成功",
                    "data": {
                        "taskNo": "25082744936879",
                        "status": "CREATE",
                        "tip": "任务创建成功",
                    },
                },
            )

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(
                enabled=True,
                app_id="app-1",
                secret="secret-key",
                base_url="https://example.test/pdfOcr",
            ),
            transport=httpx.MockTransport(handler),
        )
        result = await client.start_task(
            b"%PDF-test", filename="课程.pdf", export_format="markdown"
        )

        request = captured["request"]
        self.assertEqual(request.url.path, "/pdfOcr/start")
        self.assertIn(b'name="exportFormat"', request.content)
        self.assertIn(b"markdown", request.content)
        self.assertIn(b"%PDF-test", request.content)
        self.assertEqual(result["task_no"], "25082744936879")
        self.assertEqual(result["status"], "CREATE")

    async def test_status_normalizes_page_results(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.params["taskNo"], "task-1")
            return httpx.Response(
                200,
                json={
                    "flag": True,
                    "code": 0,
                    "data": {
                        "taskNo": "task-1",
                        "exportFormat": "word",
                        "status": "FINISH",
                        "downUrl": "https://example.test/result.docx",
                        "pageList": [
                            {
                                "pageNum": "1",
                                "sourceUrl": "https://example.test/1.jpg",
                                "downUrl": "https://example.test/1.docx",
                                "status": "FINISH",
                            }
                        ],
                    },
                },
            )

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(enabled=True, app_id="app", secret="secret"),
            transport=httpx.MockTransport(handler),
        )
        result = await client.get_status("task-1")

        self.assertEqual(result["download_url"], "https://example.test/result.docx")
        self.assertEqual(result["pages"][0]["page_number"], 1)

    async def test_provider_error_is_exposed(self):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"flag": False, "code": 10001, "desc": "签名认证失败"}
            )

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(enabled=True, app_id="app", secret="bad"),
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(XfyunPdfOcrError, "10001"):
            await client.get_status("task-1")


if __name__ == "__main__":
    unittest.main()
