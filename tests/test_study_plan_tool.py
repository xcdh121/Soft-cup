import json
import unittest
from types import SimpleNamespace

from edu_ai.tools.study_plan import get_latest_study_plan


class StudyPlanToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_latest_plan_from_current_project(self):
        calls = []

        class FakeLearningPathService:
            def get_latest_learning_path(self, user_id, project_id):
                calls.append((user_id, project_id))
                return SimpleNamespace(
                    model_dump=lambda **_: {
                        "path_id": "path-1",
                        "project_id": project_id,
                        "learning_path": {
                            "title": "数据结构复习计划",
                            "estimated_minutes": 90,
                            "path_steps": [{"step_no": 1, "title": "复习图的遍历"}],
                        },
                        "created_at": "2026-07-15T08:00:00Z",
                    }
                )

        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            learning_paths=FakeLearningPathService(),
        )
        result_text = await get_latest_study_plan.coroutine(
            runtime=SimpleNamespace(context=context)
        )
        result = json.loads(result_text)

        self.assertEqual(calls, [("user-1", "project-1")])
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["path_id"], "path-1")
        self.assertEqual(
            result["learning_path"]["path_steps"][0]["title"],
            "复习图的遍历",
        )
        self.assertEqual(
            result["study_plan_url"],
            "/dashboard/p/project-1/study-plan",
        )

    async def test_returns_page_link_when_no_plan_exists(self):
        service = SimpleNamespace(get_latest_learning_path=lambda *_: None)
        context = SimpleNamespace(
            user_id="user-1",
            project_id="project-1",
            learning_paths=service,
        )

        result_text = await get_latest_study_plan.coroutine(
            runtime=SimpleNamespace(context=context)
        )
        result = json.loads(result_text)

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(
            result["study_plan_url"],
            "/dashboard/p/project-1/study-plan",
        )

    def test_runtime_is_hidden_from_model_tool_schema(self):
        self.assertNotIn("runtime", get_latest_study_plan.tool_call_schema.model_fields)
