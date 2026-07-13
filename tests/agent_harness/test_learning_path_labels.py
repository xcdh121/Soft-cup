import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from edu_ai.agents.orchestration.planner_agent import PlannerAgent
from edu_core.schemas.agent_orchestration import AgentContextData, AgentRunContext
from edu_core.services.agent_orchestration import DatabaseOrchestrationStore


class _KnowledgePointQuery:
    def __init__(self, points):
        self.points = points

    def filter(self, _condition):
        return self

    def all(self):
        return self.points


class _KnowledgePointDb:
    def __init__(self, points):
        self.points = points

    def query(self, _model):
        return _KnowledgePointQuery(self.points)


def test_planner_replaces_knowledge_point_ids_with_names():
    knowledge_point_id = "d957c745-2aee-4564-9b48-e2ffab6581a4"

    resolved = PlannerAgent._resolve_knowledge_point_labels(
        {"based_on_knowledge_points": [knowledge_point_id]},
        [{"id": knowledge_point_id, "name": "二叉树遍历"}],
    )

    assert resolved["based_on_knowledge_points"] == ["二叉树遍历"]


def test_store_resolves_ids_in_legacy_learning_paths():
    knowledge_point_id = "07b491f3-f262-4e3e-917a-04ab7d649115"
    db = _KnowledgePointDb([SimpleNamespace(id=knowledge_point_id, name="动态规划")])

    resolved = DatabaseOrchestrationStore._resolve_knowledge_point_labels(
        {
            "title": "历史计划",
            "based_on_knowledge_points": [knowledge_point_id, "已有名称"],
        },
        db,
    )

    assert resolved["based_on_knowledge_points"] == ["动态规划", "已有名称"]


def test_llm_learning_path_emits_partial_snapshots():
    knowledge_point_id = "d957c745-2aee-4564-9b48-e2ffab6581a4"
    final_path = {
        "title": "二叉树强化路径",
        "estimated_minutes": 40,
        "path_steps": [
            {
                "step_no": 1,
                "type": "practice",
                "target_id": knowledge_point_id,
                "title": "练习二叉树遍历",
                "reason": "当前掌握度较低",
            }
        ],
        "based_on_profile_fields": [],
        "based_on_knowledge_points": [knowledge_point_id],
        "adjust_reasons": ["优先巩固薄弱点"],
    }

    async def fake_generate_stream(**_kwargs):
        yield {"title": "二叉"}
        yield final_path

    async def run_test():
        snapshots = []

        async def collect(payload):
            snapshots.append(payload)

        context = AgentRunContext(
            run_id="run_1",
            project_id="project_1",
            student_id="student_1",
            goal="learning_path",
            context=AgentContextData(
                course={"language_code": "zh-CN"},
                knowledge_points=[{"id": knowledge_point_id, "name": "二叉树遍历"}],
            ),
        )
        agent = PlannerAgent()
        agent.llm = object()
        with patch(
            "edu_ai.agents.orchestration.planner_agent.generate_stream",
            new=fake_generate_stream,
        ):
            result = await agent._build_llm_learning_path(context, partial_sink=collect)

        assert snapshots[0]["learning_path"]["title"] == "二叉"
        assert snapshots[-1]["learning_path"]["based_on_knowledge_points"] == [
            "二叉树遍历"
        ]
        assert result == final_path

    asyncio.run(run_test())
