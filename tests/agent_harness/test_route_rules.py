import unittest

from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentName,
    AgentRunContext,
)


class RouteRulesTest(unittest.TestCase):
    def _context(self, goal: str, context: AgentContextData) -> AgentRunContext:
        return AgentRunContext(
            run_id="run_test",
            project_id="project_1",
            student_id="student_1",
            goal=goal,
            context=context,
        )

    def test_diagnosis_skips_collective_when_insights_missing(self):
        supervisor = SupervisorAgent()
        context = self._context(
            "diagnosis",
            AgentContextData(
                practice_records=[
                    {"id": "p1", "topic": "gradient", "was_correct": False}
                ]
            ),
        )

        preflight = supervisor._preflight(context)
        route = supervisor._decide_route(preflight, context)

        self.assertEqual(
            route,
            [AgentName.PROFILE, AgentName.KT, AgentName.DIAGNOSIS],
        )
        self.assertIn("collective_insight_unavailable", preflight.degrade_mode)

    def test_recommendations_generates_diagnosis_before_resource_agent(self):
        supervisor = SupervisorAgent()
        context = self._context(
            "recommendations",
            AgentContextData(
                knowledge_states=[
                    {"knowledge_point_id": "kp_1", "mastery_score": 40}
                ],
                generated_resources=[{"id": "r1", "title": "Existing"}],
            ),
        )

        preflight = supervisor._preflight(context)
        route = supervisor._decide_route(preflight, context)

        self.assertEqual(
            route,
            [AgentName.PROFILE, AgentName.KT, AgentName.DIAGNOSIS, AgentName.RESOURCE],
        )

    def test_recommendations_reuses_provided_diagnosis(self):
        supervisor = SupervisorAgent()
        context = self._context(
            "recommendations",
            AgentContextData(
                knowledge_states=[
                    {"knowledge_point_id": "kp_1", "mastery_score": 40}
                ],
            ),
        )
        context.artifacts["diagnosis"] = {
            "diagnosis": {"related_knowledge_points": [{"id": "kp_1"}]}
        }

        preflight = supervisor._preflight(context)
        route = supervisor._decide_route(preflight, context)

        self.assertEqual(route, [AgentName.RESOURCE])

    def test_learning_path_uses_rule_planner_route_without_resource_requirement(self):
        supervisor = SupervisorAgent()
        context = self._context(
            "learning_path",
            AgentContextData(
                knowledge_states=[
                    {"knowledge_point_id": "kp_1", "mastery_score": 40}
                ],
            ),
        )

        preflight = supervisor._preflight(context)
        route = supervisor._decide_route(preflight, context)

        self.assertEqual(
            route,
            [AgentName.PROFILE, AgentName.KT, AgentName.DIAGNOSIS, AgentName.PLANNER],
        )
