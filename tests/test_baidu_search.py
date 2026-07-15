import json
import unittest

import httpx

from edu_core.services.baidu_search import BaiduSearchClient, BaiduSearchConfig
from edu_core.services.resource_packages import ResourcePackageService


class BaiduSearchClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_videos_builds_documented_request_and_normalizes_results(self):
        captured: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "request_id": "request-1",
                    "references": [
                        {
                            "title": "二叉树遍历讲解",
                            "content": "通过动画理解三种遍历方式",
                            "date": "2026-07-01 10:00:00",
                            "type": "video",
                            "url": "https://www.bilibili.com/video/BV123",
                            "image": "https://i0.hdslb.com/cover.jpg",
                        }
                    ],
                },
            )

        client = BaiduSearchClient(
            BaiduSearchConfig(
                api_key="secret-key",
                video_top_k=6,
                sites=("bilibili.com",),
            ),
            transport=httpx.MockTransport(handler),
        )

        result = await client.search_videos("二叉树遍历")

        self.assertEqual(
            captured["headers"]["x-appbuilder-authorization"], "Bearer secret-key"
        )
        self.assertEqual(
            captured["body"]["resource_type_filter"],
            [{"type": "video", "top_k": 6}],
        )
        self.assertEqual(
            captured["body"]["search_filter"],
            {"match": {"site": ["bilibili.com"]}},
        )
        self.assertEqual(result["videos"][0]["source"], "bilibili.com")
        self.assertEqual(
            result["videos"][0]["thumbnail_url"],
            "https://i0.hdslb.com/cover.jpg",
        )

    async def test_search_videos_accepts_nested_video_metadata(self):
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "references": [
                        {
                            "type": "video",
                            "video": {
                                "title": "线性代数",
                                "page_url": "https://example.cn/video/1",
                                "hover_pic": "https://example.cn/cover.png",
                                "duration": "501",
                            },
                        }
                    ]
                },
            )

        client = BaiduSearchClient(
            BaiduSearchConfig(api_key="secret-key"),
            transport=httpx.MockTransport(handler),
        )

        result = await client.search_videos("线性代数")

        self.assertEqual(result["videos"][0]["title"], "线性代数")
        self.assertEqual(result["videos"][0]["source"], "example.cn")
        self.assertEqual(
            result["videos"][0]["thumbnail_url"],
            "https://example.cn/cover.png",
        )
        self.assertEqual(result["videos"][0]["duration"], "8:21")

    async def test_resource_package_builds_video_recommendation_resource(self):
        class FakeBaiduSearchClient:
            is_enabled = True

            async def search_videos(self, query: str):
                return {
                    "query": query,
                    "provider": "baidu_ai_search",
                    "request_id": "request-2",
                    "videos": [
                        {
                            "title": "图解二叉树",
                            "url": "https://www.bilibili.com/video/BV456",
                            "thumbnail_url": "https://i0.hdslb.com/tree.jpg",
                        }
                    ],
                }

        service = ResourcePackageService(
            baidu_search_client=FakeBaiduSearchClient()  # type: ignore[arg-type]
        )

        generated = await service._generate_resource_content_async(
            resource_type="video_recommendations",
            topic="二叉树",
            goal=None,
            difficulty_level="beginner",
            document_context="",
            knowledge_point_ids=[],
            weak_points=[],
            custom_instructions=None,
            documents=[],
            generation_params={},
        )

        self.assertEqual(generated["format"], "video-links")
        self.assertEqual(generated["content_json"]["videos"][0]["title"], "图解二叉树")
        self.assertEqual(
            generated["cover_image_url"], "https://i0.hdslb.com/tree.jpg"
        )
