from types import SimpleNamespace

from edu_ai.agents.orchestration.planner_agent import PlannerAgent
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
