import json
import unittest

import httpx
from edu_core.services.baidu_search import BaiduSearchClient, BaiduSearchConfig
from edu_core.services.chats import ChatService
from edu_core.services.resource_packages import ResourcePackageService


class BaiduSearchClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_prefetches_web_results_for_deterministic_grounding(self):
        class FakeBaiduSearchClient:
            is_enabled = True

            async def search_web(self, query: str):
                self.query = query
                return {
                    "provider": "baidu_ai_search",
                    "results": [
                        {
                            "id": "https://www.moe.gov.cn/guide",
                            "title": "人工智能教育指南",
                            "url": "https://www.moe.gov.cn/guide",
                            "snippet": "指南强调人工智能通识教育。",
                            "source": "moe.gov.cn",
                            "published_at": "2026-08-01",
                        }
                    ],
                }

        client = FakeBaiduSearchClient()
        service = ChatService.__new__(ChatService)
        service.web_search_client = client

        sources, context = await service._prefetch_web_search("人工智能教育")

        self.assertEqual(client.query, "人工智能教育")
        self.assertEqual(sources[0]["url"], "https://www.moe.gov.cn/guide")
        self.assertIn("指南强调人工智能通识教育", context)
        self.assertIn("引用对应网址", context)

    async def test_search_web_builds_request_and_normalizes_sources(self):
        captured: dict = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "request_id": "web-request-1",
                    "references": [
                        {
                            "title": "教育部发布人工智能教育指南",
                            "content": "指南提出加强人工智能通识教育。",
                            "date": "2026-08-01",
                            "url": "https://www.moe.gov.cn/example",
                        },
                        {
                            "title": "Unsafe result",
                            "content": "must be ignored",
                            "url": "javascript:alert(1)",
                        },
                    ],
                },
            )

        client = BaiduSearchClient(
            BaiduSearchConfig(api_key="secret-key", web_top_k=5),
            transport=httpx.MockTransport(handler),
        )

        result = await client.search_web("人工智能教育政策", recency="month")

        self.assertEqual(
            captured["body"]["resource_type_filter"],
            [{"type": "web", "top_k": 5}],
        )
        self.assertEqual(captured["body"]["search_recency_filter"], "month")
        self.assertTrue(captured["body"]["safe_search"])
        self.assertNotIn("search_filter", captured["body"])
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["source"], "moe.gov.cn")
        self.assertEqual(
            result["results"][0]["snippet"],
            "指南提出加强人工智能通识教育。",
        )

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

    async def test_search_videos_retries_without_exact_site_filter(self):
        requests: list[dict] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            requests.append(body)
            if len(requests) == 1:
                return httpx.Response(200, json={"references": []})
            return httpx.Response(
                200,
                json={
                    "request_id": "fallback-request",
                    "references": [
                        {
                            "title": "二叉树教程",
                            "url": "https://www.bilibili.com/video/BV-fallback",
                        }
                    ],
                },
            )

        client = BaiduSearchClient(
            BaiduSearchConfig(api_key="secret-key", sites=("bilibili.com",)),
            transport=httpx.MockTransport(handler),
        )

        result = await client.search_videos("二叉树")

        self.assertEqual(len(requests), 2)
        self.assertIn("search_filter", requests[0])
        self.assertNotIn("search_filter", requests[1])
        self.assertEqual(requests[1]["messages"][0]["content"], "二叉树 教程")
        self.assertEqual(result["search_query"], "二叉树 教程")
        self.assertEqual(result["videos"][0]["title"], "二叉树教程")

    async def test_search_videos_falls_back_to_web_classified_video_pages(self):
        requests: list[dict] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            requests.append(body)
            if len(requests) < 3:
                return httpx.Response(200, json={"references": []})
            return httpx.Response(
                200,
                json={
                    "request_id": "web-fallback-request",
                    "references": [
                        {
                            "title": "二叉树遍历动画教程",
                            "url": "https://www.bilibili.com/video/BV-web-fallback",
                            "content": "前序、中序和后序遍历",
                        }
                    ],
                },
            )

        client = BaiduSearchClient(
            BaiduSearchConfig(api_key="secret-key", sites=("bilibili.com",)),
            transport=httpx.MockTransport(handler),
        )

        result = await client.search_videos("二叉树")

        self.assertEqual(len(requests), 3)
        self.assertEqual(
            requests[2]["resource_type_filter"],
            [{"type": "web", "top_k": 6}],
        )
        self.assertEqual(result["search_query"], "二叉树 教程 视频")
        self.assertEqual(len(result["videos"]), 1)

    async def test_search_videos_replaces_baidu_cache_with_bilibili_cover(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.bilibili.com":
                self.assertEqual(request.url.params["bvid"], "BV1EP4y1v7ns")
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "data": {
                            "pic": "http://i2.hdslb.com/bfs/archive/cover.png"
                        },
                    },
                )
            return httpx.Response(
                200,
                json={
                    "references": [
                        {
                            "title": "动态规划",
                            "type": "video",
                            "url": "http://www.bilibili.com/video/BV1EP4y1v7ns?p=19",
                            "image": "https://t15.baidu.com/it/cached-cover",
                        }
                    ]
                },
            )

        client = BaiduSearchClient(
            BaiduSearchConfig(api_key="secret-key"),
            transport=httpx.MockTransport(handler),
        )

        result = await client.search_videos("动态规划")

        self.assertEqual(
            result["videos"][0]["thumbnail_url"],
            "https://i2.hdslb.com/bfs/archive/cover.png",
        )

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
