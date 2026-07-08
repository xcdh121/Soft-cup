import json
import unittest
from types import SimpleNamespace

from edu_ai.tools.resource_package import generate_resource_package


class ResourcePackageToolTests(unittest.IsolatedAsyncioTestCase):
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
            "/dashboard/p/project-1/resource-packages",
        )
        self.assertEqual(calls[0]["user_id"], "user-1")
        self.assertEqual(calls[0]["project_id"], "project-1")
        self.assertEqual(calls[0]["payload"]["resource_types"], ["pptx"])
        self.assertEqual(
            calls[0]["payload"]["generation_params"]["launch_context"],
            "project overview chat",
        )

    def test_runtime_is_hidden_from_model_tool_schema(self):
        fields = generate_resource_package.tool_call_schema.model_fields

        self.assertNotIn("runtime", fields)
        self.assertIn("resource_types", fields)
