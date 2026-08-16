import base64
import hashlib
import hmac
import io
import unittest
import zipfile
from unittest.mock import AsyncMock, patch

import httpx
from routers.pdf_ocr import router as pdf_ocr_router
from xfyun_pdf_ocr import (
    XfyunPdfOcrClient,
    XfyunPdfOcrConfig,
    XfyunPdfOcrError,
    _build_auth_headers,
)


class XfyunPdfOcrClientTests(unittest.IsolatedAsyncioTestCase):
    def test_router_exposes_tutor_text_result_endpoint(self):
        paths = {route.path for route in pdf_ocr_router.routes}
        self.assertIn(
            "/api/v1/projects/{project_id}/pdf-ocr/tasks/{task_no}/text",
            paths,
        )

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

    async def test_status_retries_once_when_provider_rate_limits(self):
        request_count = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            if request_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "flag": False,
                        "code": 10023,
                        "desc": "rate limited",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "flag": True,
                    "code": 0,
                    "data": {
                        "taskNo": "task-1",
                        "status": "FINISH",
                        "downUrl": "https://example.test/result.md",
                    },
                },
            )

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(enabled=True, app_id="app", secret="secret"),
            transport=httpx.MockTransport(handler),
        )
        with patch("xfyun_pdf_ocr.asyncio.sleep", new_callable=AsyncMock) as sleep:
            result = await client.get_status("task-1")

        self.assertEqual(result["status"], "FINISH")
        self.assertEqual(request_count, 2)
        sleep.assert_awaited_once_with(5.0)

    async def test_status_does_not_retry_non_rate_limit_provider_errors(self):
        request_count = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(
                200,
                json={"flag": False, "code": 10001, "desc": "签名认证失败"},
            )

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(enabled=True, app_id="app", secret="bad"),
            transport=httpx.MockTransport(handler),
        )
        with (
            patch("xfyun_pdf_ocr.asyncio.sleep", new_callable=AsyncMock) as sleep,
            self.assertRaisesRegex(XfyunPdfOcrError, "10001"),
        ):
            await client.get_status("task-1")

        self.assertEqual(request_count, 1)
        sleep.assert_not_awaited()

    async def test_download_text_reads_markdown_result(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/result.md")
            return httpx.Response(200, content="# 第一章\n函数与导数".encode())

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(enabled=True, app_id="app", secret="secret"),
            transport=httpx.MockTransport(handler),
        )
        text, truncated = await client.download_text("https://example.test/result.md")

        self.assertIn("函数与导数", text)
        self.assertFalse(truncated)

    async def test_download_text_reads_markdown_from_zip_bundle(self):
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("result/content.md", "# 扫描讲义\n牛顿第二定律")

        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=bundle.getvalue())

        client = XfyunPdfOcrClient(
            XfyunPdfOcrConfig(enabled=True, app_id="app", secret="secret"),
            transport=httpx.MockTransport(handler),
        )
        text, _ = await client.download_text("https://example.test/result.zip")

        self.assertIn("牛顿第二定律", text)


if __name__ == "__main__":
    unittest.main()
