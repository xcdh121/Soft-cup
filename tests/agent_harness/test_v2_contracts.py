import asyncio
import unittest

from edu_core.schemas.agent_artifacts import (
    ArtifactEnvelope,
    DiagnosisClaim,
    LearningPathArtifact,
    LearningPathStep,
    upgrade_legacy_artifact,
)
from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentName,
    AgentResult,
    AgentRunContext,
    BudgetPolicy,
    ExecutionPlan,
    PlanNode,
    RunStatus,
    SupervisorRunResult,
)
from edu_core.services.agent_orchestration import _aggregate_model_usage
from pydantic import ValidationError


class V2ContractTests(unittest.TestCase):
    def test_rejects_cyclic_plan(self):
        with self.assertRaises(ValidationError):
            ExecutionPlan(
                nodes=[
                    PlanNode(node_id="a", agent_name=AgentName.PROFILE, depends_on=["b"]),
                    PlanNode(node_id="b", agent_name=AgentName.KT, depends_on=["a"]),
                ]
            )

    def test_rejects_missing_dependency(self):
        with self.assertRaises(ValidationError):
            ExecutionPlan(
                nodes=[
                    PlanNode(
                        node_id="diagnosis",
                        agent_name=AgentName.DIAGNOSIS,
                        depends_on=["missing"],
                    )
                ]
            )

    def test_rejects_plan_over_budget(self):
        with self.assertRaises(ValidationError):
            ExecutionPlan(
                nodes=[
                    PlanNode(node_id="a", agent_name=AgentName.PROFILE),
                    PlanNode(node_id="b", agent_name=AgentName.KT),
                ],
                budget=BudgetPolicy(max_nodes=1),
            )

    def test_strong_diagnosis_requires_evidence(self):
        with self.assertRaises(ValidationError):
            DiagnosisClaim(
                claim_id="claim-1",
                statement="A certain weakness",
                root_cause="missing prerequisite",
                confidence=0.9,
            )

    def test_learning_path_duration_is_consistent(self):
        with self.assertRaises(ValidationError):
            LearningPathArtifact(
                steps=[
                    LearningPathStep(
                        step_id="s1",
                        title="Review",
                        knowledge_point_id="kp1",
                        estimated_minutes=20,
                    )
                ],
                total_minutes=10,
            )

    def test_legacy_artifact_is_wrapped_and_hashed(self):
        wrapped = upgrade_legacy_artifact(
            {"summary": "legacy"},
            artifact_type="diagnosis",
            producer="DiagnosisAgent",
            source_snapshot_id="snapshot-1",
        )
        validated = ArtifactEnvelope[dict].model_validate(wrapped)
        self.assertEqual("2.0", validated.schema_version)
        self.assertTrue(validated.content_hash)

    def test_agent_model_usage_is_aggregated_for_the_run(self):
        result = SupervisorRunResult(
            run_id="run-1",
            status=RunStatus.COMPLETED,
            context=AgentRunContext(
                run_id="run-1",
                project_id="project-1",
                student_id="user-1",
                context=AgentContextData(),
            ),
            agent_results=[
                AgentResult(
                    agent_name=AgentName.PLANNER,
                    status=RunStatus.COMPLETED,
                    summary="planned",
                    model_name="model-a",
                    input_tokens=120,
                    output_tokens=45,
                    estimated_cost_micros=320,
                )
            ],
        )

        usage = _aggregate_model_usage(result)

        self.assertEqual(usage["model_name"], "model-a")
        self.assertEqual(usage["input_tokens"], 120)
        self.assertEqual(usage["output_tokens"], 45)
        self.assertEqual(usage["estimated_cost_micros"], 320)
        self.assertTrue(usage["token_usage_captured"])


if __name__ == "__main__":
    unittest.main()
