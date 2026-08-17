import asyncio
import json
import unittest
from types import SimpleNamespace

from edu_ai.tools.resource_package import generate_resource_package


class ResourcePackageToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_progress_link_when_package_starts(self):
        finish_generation = asyncio.Event()

        class SlowResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                await kwargs["event_sink"](
                    SimpleNamespace(
                        event="package_started",
                        package_id="package-running",
                        payload={"status": "generating", "resource_count": 2},
                    )
                )
                await finish_generation.wait()
                return SimpleNamespace(
                    id="package-running",
                    status="completed",
                    completed_resource_count=2,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=SlowResourcePackageService(),
        )

        try:
            result_text = await asyncio.wait_for(
                generate_resource_package.coroutine(
                    topic="Lists",
                    resource_types=["lecture_note", "practice_set"],
                    runtime=SimpleNamespace(context=context),
                ),
                timeout=0.5,
            )
            result = json.loads(result_text)

            self.assertEqual(result["package_id"], "package-running")
            self.assertEqual(result["status"], "generating")
            self.assertEqual(result["resource_count"], 2)
            self.assertIn("packageId=package-running", result["resource_package_url"])
        finally:
            finish_generation.set()
            await asyncio.sleep(0)

    async def test_generates_ppt_package_and_returns_result_link(self):
        calls: list[dict] = []

        class FakeResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    id="package-1",
                    status="completed",
                    completed_resource_count=1,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FakeResourcePackageService(),
        )
        runtime = SimpleNamespace(context=context)

        result_text = await generate_resource_package.coroutine(
            topic="空间复杂度",
            resource_types=["pptx", "pptx"],
            difficulty_level="intermediate",
            goal="用于期末复习",
            custom_instructions="使用中文并包含示例",
            runtime=runtime,
        )
        result = json.loads(result_text)

        self.assertEqual(result["package_id"], "package-1")
        self.assertEqual(result["resource_types"], ["pptx"])
        self.assertEqual(
            result["resource_package_url"],
            "/dashboard/p/project-1/resource-packages?packageId=package-1",
        )
        self.assertEqual(calls[0]["user_id"], "user-1")
        self.assertEqual(calls[0]["project_id"], "project-1")
        self.assertEqual(calls[0]["payload"]["resource_types"], ["pptx"])
        self.assertEqual(
            calls[0]["payload"]["generation_params"]["launch_context"],
            "personalized tutor recommendation",
        )

    async def test_generates_image_package_and_returns_result_link(self):
        calls: list[dict] = []

        class FakeResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    id="image-package-1",
                    status="completed",
                    completed_resource_count=1,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FakeResourcePackageService(),
        )
        result_text = await generate_resource_package.coroutine(
            topic="二叉树遍历",
            resource_types=["image"],
            runtime=SimpleNamespace(context=context),
        )
        result = json.loads(result_text)

        self.assertEqual(result["package_id"], "image-package-1")
        self.assertEqual(result["resource_types"], ["image"])
        self.assertEqual(calls[0]["payload"]["resource_types"], ["image"])
        self.assertIn("packageId=image-package-1", result["resource_package_url"])

    async def test_derives_recommendation_from_saved_profile_and_weak_point(self):
        calls: list[dict] = []

        class FakeResourcePackageService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    id="package-personalized",
                    status="completed",
                    completed_resource_count=2,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FakeResourcePackageService(),
            project_context={"course_name": "数据结构"},
            learner_profile={
                "id": "profile-1",
                "fields": {
                    "current_course": "数据结构",
                    "learning_goal": "准备期末考试",
                    "resource_preference": ["视频", "刷题"],
                    "preferred_knowledge_points": ["图的遍历"],
                },
            },
            learning_evidence={
                "overall_mastery": 42,
                "recent_accuracy": 0.4,
                "weak_points": [
                    {
                        "id": "kp-graph",
                        "name": "图的遍历",
                        "mastery_score": 35,
                    }
                ],
            },
        )

        result_text = await generate_resource_package.coroutine(
            runtime=SimpleNamespace(context=context)
        )
        result = json.loads(result_text)
        payload = calls[0]["payload"]

        self.assertEqual(payload["profile_id"], "profile-1")
        self.assertEqual(payload["target_topic"], "图的遍历")
        self.assertEqual(payload["target_goal"], "准备期末考试")
        self.assertEqual(
            payload["resource_types"],
            ["video_recommendations", "practice_set"],
        )
        self.assertEqual(payload["difficulty_level"], "beginner")
        self.assertEqual(payload["knowledge_point_ids"], ["kp-graph"])
        self.assertEqual(payload["generation_mode"], "recommended")
        self.assertEqual(result["target_topic"], "图的遍历")
        self.assertEqual(
            payload["generation_params"]["personalization_basis"]["profile_fields"][
                "resource_preference"
            ],
            ["视频", "刷题"],
        )

    def test_runtime_is_hidden_from_model_tool_schema(self):
        fields = generate_resource_package.tool_call_schema.model_fields

        self.assertNotIn("runtime", fields)
        self.assertIn("resource_types", fields)

    async def test_explicit_single_note_uses_fast_generation_path(self):
        calls: list[dict] = []

        class FastNoteService:
            async def generate_resource_package(self, **kwargs):
                calls.append(kwargs)
                await kwargs["event_sink"](
                    SimpleNamespace(
                        event="package_started",
                        package_id="package-note-fast",
                        payload={"status": "generating", "resource_count": 1},
                    )
                )
                return SimpleNamespace(
                    id="package-note-fast",
                    status="completed",
                    completed_resource_count=1,
                    failed_resource_count=0,
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            resource_packages=FastNoteService(),
            learner_profile={},
            learning_evidence={},
            project_context={},
        )
        result_text = await generate_resource_package.coroutine(
            topic="最短路径",
            resource_types=["lecture_note"],
            runtime=SimpleNamespace(context=context),
        )
        result = json.loads(result_text)

        self.assertEqual(result["package_id"], "package-note-fast")
        self.assertIsNone(result["preview_url"])
        self.assertEqual(calls[0]["payload"]["target_topic"], "最短路径")
        self.assertEqual(calls[0]["payload"]["generation_mode"], "manual")
