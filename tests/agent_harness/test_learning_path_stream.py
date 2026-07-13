import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from edu_core.schemas.agent_orchestration import (
    AgentEvent,
    AgentEventType,
    AgentName,
    LearningPathResponse,
    RunStatus,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "edu-api"))

from routers.learning_paths import generate_learning_path_stream


class _StreamingLearningPathService:
    async def generate_learning_path(self, **kwargs):
        await kwargs["event_sink"](
            AgentEvent(
                event_type=AgentEventType.AGENT_STEP,
                run_id="run_1",
                agent_name=AgentName.PLANNER,
                status=RunStatus.RUNNING,
                summary="PlannerAgent started.",
                timestamp=datetime.now(UTC),
            )
        )
        return LearningPathResponse(
            path_id="path_1",
            run_id="run_1",
            project_id=kwargs["project_id"],
            learning_path={"based_on_knowledge_points": ["动态规划"]},
            created_at=datetime.now(UTC),
        )


class LearningPathStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_contains_progress_and_completed_result(self):
        response = await generate_learning_path_stream(
            project_id="project_1",
            request=None,
            current_user=SimpleNamespace(id="student_1"),
            service=_StreamingLearningPathService(),
        )

        body = b"".join([chunk async for chunk in response.body_iterator]).decode()
        events = [
            json.loads(block.removeprefix("data: "))
            for block in body.strip().split("\n\n")
        ]

        self.assertEqual(events[0]["event"], "progress")
        self.assertEqual(events[0]["agent_name"], "PlannerAgent")
        self.assertEqual(events[-1]["event"], "completed")
        self.assertEqual(events[-1]["result"]["path_id"], "path_1")


if __name__ == "__main__":
    unittest.main()
