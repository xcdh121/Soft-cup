import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from edu_ai.agents.orchestration.planner_agent import PlannerAgent
from edu_ai.agents.orchestration.resource_agent import ResourceAgent
from edu_ai.agents.orchestration.supervisor import SupervisorAgent
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentEventType,
    AgentRunContext,
    AgentTrigger,
    OrchestrationRunRequest,
)


class FallbackRulesTest(unittest.IsolatedAsyncioTestCase):
    async def test_diagnosis_with_no_evidence_stays_low_confidence(self):
        result = await SupervisorAgent().run(
            OrchestrationRunRequest(
                project_id="project_1",
                student_id="student_1",
                goal="diagnosis",
                context=AgentContextData(),
            )
        )

        diagnosis_result = next(
            item for item in result.agent_results if item.agent_name == "DiagnosisAgent"
        )

        self.assertEqual(diagnosis_result.fallback_reason, "insufficient_evidence")
        self.assertLessEqual(diagnosis_result.confidence, 0.2)
        self.assertEqual(
            result.final_result["diagnosis"]["root_causes"],
            [],
        )

    async def test_resource_generation_unavailable_uses_existing_resource_fallback(self):
        context = AgentRunContext(
            run_id="run_resource",
            project_id="project_1",
            student_id="student_1",
            goal="recommendations",
            context=AgentContextData(
                generated_resources=[
                    {
                        "id": "resource_1",
                        "title": "Existing explanation",
                        "resource_type": "note",
                    }
                ]
            ),
            artifacts={
                "diagnosis": {
                    "diagnosis": {
                        "related_knowledge_points": [{"id": "kp_gradient"}]
                    }
                }
            },
        )

        result = await ResourceAgent().run(context)

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.fallback_reason, "resource_generation_unavailable")
        self.assertEqual(
            result.result["recommendations"][0]["recommendation_mode"],
            "fallback",
        )

    async def test_manual_resource_request_is_queued_without_diagnosis_evidence(self):
        note_service = MagicMock()
        note_service.create_note.return_value = SimpleNamespace(
            id="note_1", title="Requested note"
        )
        context = AgentRunContext(
            run_id="run_manual_resource",
            project_id="project_1",
            student_id="student_1",
            goal="recommendations",
            context=AgentContextData(),
            meta={
                "requested_topic": "sorting",
                "requested_resource_types": ["note"],
            },
            artifacts={
                "diagnosis": {
                    "diagnosis": {"related_knowledge_points": []}
                }
            },
        )

        result = await ResourceAgent(note_service=note_service).run(context)

        note_service.queue_generation.assert_called_once()
        self.assertEqual(
            result.result["recommendations"][0]["target_id"], "note_1"
        )

    async def test_resource_package_note_is_left_for_package_streaming(self):
        note_service = MagicMock()
        note_service.create_note.return_value = SimpleNamespace(
            id="note_stream", title="Streaming note"
        )
        context = AgentRunContext(
            run_id="run_resource_package",
            project_id="project_1",
            student_id="student_1",
            goal="recommendations",
            trigger=AgentTrigger(type="resource_package", id="package_1"),
            context=AgentContextData(),
            meta={
                "requested_topic": "sorting",
                "requested_resource_types": ["note"],
                "stream_note_in_package": True,
            },
            artifacts={"diagnosis": {"diagnosis": {}}},
        )

        result = await ResourceAgent(note_service=note_service).run(context)

        note_service.queue_generation.assert_not_called()
        recommendation = result.result["recommendations"][0]
        self.assertFalse(recommendation["stream_on_client"])
        self.assertTrue(recommendation["stream_in_package"])
        self.assertEqual(recommendation["topic"], "sorting")

    async def test_resource_package_note_falls_back_to_server_queue(self):
        note_service = MagicMock()
        note_service.create_note.return_value = SimpleNamespace(
            id="note_queued", title="Queued note"
        )
        context = AgentRunContext(
            run_id="run_resource_package_without_streamer",
            project_id="project_1",
            student_id="student_1",
            goal="recommendations",
            trigger=AgentTrigger(type="resource_package", id="package_1"),
            context=AgentContextData(),
            meta={
                "requested_topic": "sorting",
                "requested_resource_types": ["note"],
            },
            artifacts={"diagnosis": {"diagnosis": {}}},
        )

        result = await ResourceAgent(note_service=note_service).run(context)

        note_service.queue_generation.assert_called_once()
        recommendation = result.result["recommendations"][0]
        self.assertFalse(recommendation["stream_on_client"])
        self.assertFalse(recommendation["stream_in_package"])

    async def test_resource_package_collections_are_left_for_item_streaming(self):
        quiz_service = MagicMock()
        quiz_service.create_quiz.return_value = SimpleNamespace(
            id="quiz_stream", name="Streaming quiz"
        )
        flashcard_service = MagicMock()
        flashcard_service.create_flashcard_group.return_value = SimpleNamespace(
            id="cards_stream", name="Streaming cards"
        )
        context = AgentRunContext(
            run_id="run_streamed_collections",
            project_id="project_1",
            student_id="student_1",
            goal="recommendations",
            trigger=AgentTrigger(type="resource_package", id="package_1"),
            context=AgentContextData(),
            meta={
                "requested_topic": "lists",
                "requested_resource_types": ["quiz", "flashcards"],
                "stream_quiz_in_package": True,
                "stream_flashcards_in_package": True,
            },
            artifacts={"diagnosis": {"diagnosis": {}}},
        )

        result = await ResourceAgent(
            quiz_service=quiz_service,
            flashcard_group_service=flashcard_service,
        ).run(context)

        quiz_service.queue_generation.assert_not_called()
        flashcard_service.queue_generation.assert_not_called()
        recommendations = result.result["recommendations"]
        self.assertTrue(all(item["stream_in_package"] for item in recommendations))

    async def test_planner_without_llm_uses_rule_fallback(self):
        context = AgentRunContext(
            run_id="run_planner",
            project_id="project_1",
            student_id="student_1",
            goal="learning_path",
            artifacts={
                "diagnosis": {
                    "diagnosis": {
                        "related_knowledge_points": [{"id": "kp_gradient"}]
                    }
                },
                "recommendations": {
                    "recommendations": [
                        {
                            "recommendation_type": "note",
                            "target_id": "resource_1",
                            "title": "Existing explanation",
                            "reason_text": ["Weak point support"],
                        }
                    ]
                },
            },
        )

        result = await PlannerAgent().run(context)

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.fallback_reason, "planner_rule_fallback")

    async def test_fallback_event_is_recorded(self):
        result = await SupervisorAgent().run(
            OrchestrationRunRequest(
                project_id="project_1",
                student_id="student_1",
                goal="diagnosis",
                context=AgentContextData(),
            )
        )

        event_types = [event.event_type for event in result.events]

        self.assertIn(AgentEventType.FALLBACK_APPLIED, event_types)
