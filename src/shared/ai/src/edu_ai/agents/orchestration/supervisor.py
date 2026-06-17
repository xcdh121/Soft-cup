from datetime import datetime, timezone
from uuid import uuid4

from edu_core.model_providers import LlmProviderConfig
from edu_core.schemas.agent_orchestration import (
    AgentEvent,
    AgentEventType,
    AgentName,
    AgentRunContext,
    OrchestrationRunRequest,
    RunStatus,
    SupervisorRunResult,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent
from edu_ai.agents.orchestration.collective_insight_agent import (
    CollectiveInsightAgent,
)
from edu_ai.agents.orchestration.diagnosis_agent import DiagnosisAgent
from edu_ai.agents.orchestration.kt_agent import KTAgent
from edu_ai.agents.orchestration.planner_agent import PlannerAgent
from edu_ai.agents.orchestration.profile_agent import ProfileAgent
from edu_ai.agents.orchestration.resource_agent import ResourceAgent


class SupervisorAgent:
    def __init__(
        self,
        agents: list[BaseOrchestrationAgent] | None = None,
        llm_config: LlmProviderConfig | None = None,
    ) -> None:
        self.agents = agents or [
            ProfileAgent(),
            KTAgent(),
            CollectiveInsightAgent(),
            DiagnosisAgent(),
            ResourceAgent(),
            PlannerAgent(llm_config=llm_config),
        ]

    async def run(self, request: OrchestrationRunRequest) -> SupervisorRunResult:
        run_id = f"run_{uuid4().hex}"
        context = AgentRunContext(
            run_id=run_id,
            project_id=request.project_id,
            student_id=request.student_id,
            goal=request.goal,
            trigger=request.trigger,
            context=request.context,
            meta={
                "requested_at": self._now().isoformat(),
                **request.meta,
            },
        )
        events = [
            self._event(
                AgentEventType.RUN_STARTED,
                run_id,
                RunStatus.RUNNING,
                "Agent orchestration started.",
                AgentName.SUPERVISOR,
                {"goal": request.goal},
            )
        ]
        agent_results = []

        try:
            for agent in self.agents:
                result = await agent.run(context)
                agent_results.append(result)
                context.artifacts[agent.artifact_key] = result.result
                events.append(
                    self._event(
                        AgentEventType.AGENT_STEP,
                        run_id,
                        result.status,
                        result.summary,
                        result.agent_name,
                        {
                            "reason_codes": result.reason_codes,
                            "next_actions": result.next_actions,
                        },
                    )
                )
                events.append(
                    self._event(
                        AgentEventType.ARTIFACT_UPDATED,
                        run_id,
                        RunStatus.COMPLETED,
                        f"Updated artifact: {agent.artifact_key}",
                        result.agent_name,
                        {"artifact_key": agent.artifact_key},
                    )
                )

            final_result = self._build_final_result(context)
            events.append(
                self._event(
                    AgentEventType.RUN_COMPLETED,
                    run_id,
                    RunStatus.COMPLETED,
                    "Agent orchestration completed.",
                    AgentName.SUPERVISOR,
                    {"artifact_keys": list(context.artifacts.keys())},
                )
            )
            return SupervisorRunResult(
                run_id=run_id,
                status=RunStatus.COMPLETED,
                context=context,
                agent_results=agent_results,
                events=events,
                final_result=final_result,
            )
        except Exception as exc:
            events.append(
                self._event(
                    AgentEventType.RUN_FAILED,
                    run_id,
                    RunStatus.FAILED,
                    "Agent orchestration failed.",
                    AgentName.SUPERVISOR,
                    {"error": str(exc)},
                )
            )
            return SupervisorRunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                context=context,
                agent_results=agent_results,
                events=events,
                final_result={"error": str(exc)},
            )

    def _build_final_result(self, context: AgentRunContext) -> dict:
        return {
            "diagnosis": context.artifacts.get("diagnosis", {}).get("diagnosis", {}),
            "recommendations": context.artifacts.get("recommendations", {}).get(
                "recommendations", []
            ),
            "learning_path": context.artifacts.get("learning_path", {}).get(
                "learning_path"
            ),
        }

    def _event(
        self,
        event_type: AgentEventType,
        run_id: str,
        status: RunStatus,
        summary: str,
        agent_name: AgentName | None,
        payload: dict,
    ) -> AgentEvent:
        return AgentEvent(
            event_type=event_type,
            run_id=run_id,
            agent_name=agent_name,
            status=status,
            summary=summary,
            timestamp=self._now(),
            payload=payload,
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
