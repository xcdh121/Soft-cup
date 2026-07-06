from datetime import datetime, timezone
from uuid import uuid4

from edu_core.model_providers import LlmProviderConfig
from edu_core.schemas.agent_orchestration import (
    AgentEvent,
    AgentEventType,
    AgentName,
    AgentRunContext,
    InputReadinessStatus,
    OrchestrationRunRequest,
    RunStatus,
    SupervisorPreflight,
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
        resource_agent: ResourceAgent | None = None,
    ) -> None:
        self.agents = agents or [
            ProfileAgent(),
            KTAgent(),
            CollectiveInsightAgent(),
            DiagnosisAgent(),
            resource_agent or ResourceAgent(),
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
        preflight = self._preflight(context)
        route_plan = self._decide_route(preflight)
        preflight.route_plan = route_plan
        context.meta["preflight"] = preflight.model_dump(mode="json")
        events.append(
            self._event(
                AgentEventType.ROUTE_DECIDED,
                run_id,
                RunStatus.COMPLETED,
                "Agent route decided.",
                AgentName.SUPERVISOR,
                {
                    "goal": request.goal,
                    "input_readiness": preflight.input_readiness,
                    "degrade_mode": preflight.degrade_mode,
                    "route_plan": [agent.value for agent in route_plan],
                },
            )
        )
        agent_results = []
        route_set = set(route_plan)
        agents_by_name = {agent.agent_name: agent for agent in self.agents}

        try:
            for agent in self.agents:
                if agent.agent_name not in route_set:
                    events.append(
                        self._event(
                            AgentEventType.AGENT_SKIPPED,
                            run_id,
                            RunStatus.COMPLETED,
                            f"Skipped {agent.agent_name.value}.",
                            agent.agent_name,
                            {
                                "reason": self._skip_reason(
                                    agent.agent_name, preflight, route_plan
                                ),
                                "route_plan": [
                                    route_agent.value for route_agent in route_plan
                                ],
                            },
                        )
                    )

            for agent_name in route_plan:
                agent = agents_by_name.get(agent_name)
                if not agent:
                    events.append(
                        self._event(
                            AgentEventType.AGENT_SKIPPED,
                            run_id,
                            RunStatus.FAILED,
                            f"Configured agent is unavailable: {agent_name.value}.",
                            agent_name,
                            {"reason": "agent_unavailable"},
                        )
                    )
                    continue

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
                            "confidence": result.confidence,
                            "field_status": result.field_status,
                            "fallback_used": result.fallback_used,
                            "fallback_reason": result.fallback_reason,
                        },
                    )
                )
                if result.fallback_used:
                    events.append(
                        self._event(
                            AgentEventType.FALLBACK_APPLIED,
                            run_id,
                            result.status,
                            f"Fallback applied by {result.agent_name.value}.",
                            result.agent_name,
                            {
                                "fallback_reason": result.fallback_reason,
                                "reason_codes": result.reason_codes,
                                "confidence": result.confidence,
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

    def _preflight(self, context: AgentRunContext) -> SupervisorPreflight:
        readiness = {
            "learner_profile": self._readiness(context.context.learner_profile),
            "knowledge_states": self._knowledge_state_readiness(context),
            "practice_records": self._readiness(context.context.practice_records),
            "collective_insights": self._readiness(
                context.context.collective_insights
            ),
            "generated_resources": self._readiness(
                context.context.generated_resources
            ),
            "recent_feedback_summary": self._readiness(
                context.context.recent_feedback_summary
            ),
            "evaluation_report_summary": self._readiness(
                context.context.evaluation_report_summary
            ),
        }
        degrade_mode = []
        if readiness["learner_profile"] == InputReadinessStatus.MISSING:
            degrade_mode.append("profile_missing")
        if readiness["collective_insights"] == InputReadinessStatus.MISSING:
            degrade_mode.append("collective_insight_unavailable")
        if readiness["knowledge_states"] == InputReadinessStatus.PARTIAL:
            degrade_mode.append("knowledge_states_partial")
        if (
            readiness["knowledge_states"] == InputReadinessStatus.MISSING
            and readiness["practice_records"] == InputReadinessStatus.MISSING
        ):
            degrade_mode.append("insufficient_evidence")
        if readiness["generated_resources"] == InputReadinessStatus.MISSING:
            degrade_mode.append("resource_generation_unavailable")

        return SupervisorPreflight(
            goal=context.goal,
            input_readiness=readiness,
            degrade_mode=degrade_mode,
        )

    def _decide_route(self, preflight: SupervisorPreflight) -> list[AgentName]:
        route: list[AgentName]
        if preflight.goal == "diagnosis":
            route = [
                AgentName.PROFILE,
                AgentName.KT,
                AgentName.COLLECTIVE_INSIGHT,
                AgentName.DIAGNOSIS,
            ]
        elif preflight.goal == "recommendations":
            route = [
                AgentName.PROFILE,
                AgentName.KT,
                AgentName.DIAGNOSIS,
                AgentName.RESOURCE,
            ]
        else:
            route = [
                AgentName.PROFILE,
                AgentName.KT,
                AgentName.DIAGNOSIS,
                AgentName.PLANNER,
            ]

        if (
            preflight.input_readiness["collective_insights"]
            == InputReadinessStatus.MISSING
            and AgentName.COLLECTIVE_INSIGHT in route
        ):
            route.remove(AgentName.COLLECTIVE_INSIGHT)

        return route

    def _readiness(self, value) -> InputReadinessStatus:
        if value is None:
            return InputReadinessStatus.MISSING
        if isinstance(value, (list, tuple, set, dict)):
            return (
                InputReadinessStatus.AVAILABLE
                if len(value) > 0
                else InputReadinessStatus.MISSING
            )
        return InputReadinessStatus.AVAILABLE if value else InputReadinessStatus.MISSING

    def _knowledge_state_readiness(
        self, context: AgentRunContext
    ) -> InputReadinessStatus:
        if context.context.knowledge_states:
            return InputReadinessStatus.AVAILABLE
        if context.context.practice_records:
            return InputReadinessStatus.PARTIAL
        return InputReadinessStatus.MISSING

    def _skip_reason(
        self,
        agent_name: AgentName,
        preflight: SupervisorPreflight,
        route_plan: list[AgentName],
    ) -> str:
        if agent_name == AgentName.COLLECTIVE_INSIGHT:
            return "collective_insight_unavailable"
        if agent_name == AgentName.RESOURCE and preflight.goal != "recommendations":
            return "not_required_for_goal"
        if agent_name == AgentName.PLANNER and preflight.goal != "learning_path":
            return "not_required_for_goal"
        if agent_name not in route_plan:
            return "not_required_for_goal"
        return "skipped"

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
