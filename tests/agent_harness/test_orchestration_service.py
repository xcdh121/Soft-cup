import unittest
from datetime import UTC, datetime

from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEvent,
    AgentEventType,
    AgentName,
    AgentRunContext,
    RunStatus,
    SupervisorRunResult,
)
from edu_core.services.agent_orchestration import (
    AgentOrchestrationService,
    InMemoryOrchestrationStore,
)


class StubLearningPathService(AgentOrchestrationService):
    def __init__(self, result, store):
        super().__init__(store=store)
        self.result = result
        self.requested_goals = []
        self.event_sink = None

    async def _run_supervisor(
        self,
        user_id,
        project_id,
        goal,
        trigger,
        meta=None,
        event_sink=None,
    ):
        self.requested_goals.append(goal)
        self.event_sink = event_sink
        return self.result


class LearningPathServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_generate_learning_path_runs_planner_and_persists_trace(self):
        now = datetime.now(UTC)
        context = AgentRunContext(
            run_id="run_learning_path",
            project_id="project_1",
            student_id="student_1",
            goal="learning_path",
            context=AgentContextData(),
        )
        planner_event = AgentEvent(
            event_type=AgentEventType.AGENT_STEP,
            run_id=context.run_id,
            agent_name=AgentName.PLANNER,
            status=RunStatus.COMPLETED,
            summary="Generated a structured learning path.",
            timestamp=now,
            payload={"reason_codes": ["learning_path_generated", "llm"]},
        )
        learning_path = {
            "title": "Personalized path",
            "estimated_minutes": 30,
            "path_steps": [],
            "based_on_profile_fields": [],
            "based_on_knowledge_points": [],
            "adjust_reasons": [],
        }
        result = SupervisorRunResult(
            run_id=context.run_id,
            status=RunStatus.COMPLETED,
            context=context,
            events=[planner_event],
            final_result={
                "diagnosis": {"summary": "Needs practice"},
                "recommendations": [],
                "learning_path": learning_path,
            },
        )
        store = InMemoryOrchestrationStore()
        service = StubLearningPathService(result, store)
        streamed_events = []
        event_sink = streamed_events.append

        response = await service.generate_learning_path(
            user_id="student_1",
            project_id="project_1",
            event_sink=event_sink,
        )

        self.assertEqual(service.requested_goals, ["learning_path"])
        self.assertIs(service.event_sink, event_sink)
        self.assertEqual(response.learning_path, learning_path)
        self.assertEqual(response.run_id, context.run_id)
        self.assertIsNotNone(response.based_on_diagnosis_id)
        self.assertEqual(
            store.get_events_for_diagnosis(response.based_on_diagnosis_id),
            [planner_event],
        )
        self.assertEqual(store.get_latest_learning_path("project_1"), response)

    async def test_generate_learning_path_persists_and_links_recommendations(self):
        now = datetime.now(UTC)
        context = AgentRunContext(
            run_id="run_closed_loop_path",
            project_id="project_1",
            student_id="student_1",
            goal="learning_path",
            context=AgentContextData(),
        )
        recommendation = {
            "id": "rec_1",
            "recommendation_type": "quiz",
            "target_id": "quiz_1",
            "title": "Targeted practice",
            "reason_text": ["Weak mastery"],
        }
        learning_path = {
            "title": "Personalized path",
            "estimated_minutes": 30,
            "path_steps": [{"title": "Targeted practice", "type": "quiz"}],
            "based_on_profile_fields": [],
            "based_on_knowledge_points": ["Greedy algorithm"],
            "adjust_reasons": [],
        }
        result = SupervisorRunResult(
            run_id=context.run_id,
            status=RunStatus.COMPLETED,
            context=context,
            events=[],
            final_result={
                "diagnosis": {
                    "summary": "Needs practice",
                    "related_knowledge_points": [
                        {"id": "kp_1", "name": "Greedy algorithm"}
                    ],
                },
                "recommendations": [recommendation],
                "learning_path": learning_path,
            },
        )
        store = InMemoryOrchestrationStore()
        service = StubLearningPathService(result, store)

        response = await service.generate_learning_path(
            user_id="student_1",
            project_id="project_1",
        )

        self.assertEqual(response.based_on_recommendation_ids, ["rec_1"])
        self.assertEqual(store.list_recommendations("project_1"), [recommendation])
        self.assertEqual(
            response.learning_path["path_steps"][0]["recommendation_id"],
            "rec_1",
        )
        self.assertEqual(
            response.learning_path["path_steps"][0]["knowledge_point_id"],
            "kp_1",
        )


if __name__ == "__main__":
    unittest.main()
