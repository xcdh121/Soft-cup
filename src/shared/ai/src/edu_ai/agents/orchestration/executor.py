"""Fault-isolated executor for validated orchestration DAGs."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic

from edu_core.schemas.agent_orchestration import (
    AgentEvent,
    AgentEventType,
    AgentName,
    AgentResult,
    AgentRunContext,
    ExecutionPlan,
    NodeStatus,
    RetryClass,
    RunStatus,
)

from .base import BaseOrchestrationAgent


EventSink = Callable[[AgentEvent], Awaitable[None]]
CancellationCheck = Callable[[], Awaitable[bool] | bool]
ArtifactSink = Callable[[str, AgentResult], Awaitable[None]]


@dataclass
class ExecutorOutcome:
    status: RunStatus
    results: dict[str, AgentResult] = field(default_factory=dict)
    node_statuses: dict[str, NodeStatus] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class OrchestrationExecutor:
    """Execute ready nodes concurrently while honoring retry and budget policy."""

    async def execute(
        self,
        plan: ExecutionPlan,
        context: AgentRunContext,
        agents: dict[AgentName, BaseOrchestrationAgent],
        *,
        event_sink: EventSink | None = None,
        cancellation_check: CancellationCheck | None = None,
        artifact_sink: ArtifactSink | None = None,
    ) -> ExecutorOutcome:
        node_map = {node.node_id: node for node in plan.nodes}
        statuses = {node.node_id: NodeStatus.QUEUED for node in plan.nodes}
        results: dict[str, AgentResult] = {}
        errors: dict[str, str] = {}
        started = monotonic()

        while any(status == NodeStatus.QUEUED for status in statuses.values()):
            if await self._is_cancelled(cancellation_check):
                for node_id, status in statuses.items():
                    if status in {NodeStatus.QUEUED, NodeStatus.RUNNING}:
                        statuses[node_id] = NodeStatus.CANCELLED
                return ExecutorOutcome(RunStatus.CANCELLED, results, statuses, errors)
            if monotonic() - started > plan.budget.max_duration_seconds:
                raise TimeoutError("run budget exceeded")

            ready = [
                node
                for node in plan.nodes
                if statuses[node.node_id] == NodeStatus.QUEUED
                and all(
                    statuses[dependency] in {NodeStatus.COMPLETED, NodeStatus.SKIPPED}
                    for dependency in node.depends_on
                )
            ]
            blocked = [
                node
                for node in plan.nodes
                if statuses[node.node_id] == NodeStatus.QUEUED
                and any(statuses[d] in {NodeStatus.FAILED, NodeStatus.CANCELLED} for d in node.depends_on)
            ]
            for node in blocked:
                statuses[node.node_id] = NodeStatus.SKIPPED
            if not ready:
                if blocked:
                    continue
                raise RuntimeError("validated execution plan made no progress")

            batch = await asyncio.gather(
                *[
                    self._execute_node(
                        node,
                        context,
                        agents,
                        event_sink=event_sink,
                        cancellation_check=cancellation_check,
                        artifact_sink=artifact_sink,
                    )
                    for node in ready
                ],
                return_exceptions=True,
            )
            for node, item in zip(ready, batch, strict=True):
                if isinstance(item, asyncio.CancelledError):
                    statuses[node.node_id] = NodeStatus.CANCELLED
                    continue
                if isinstance(item, BaseException):
                    statuses[node.node_id] = NodeStatus.FAILED
                    errors[node.node_id] = str(item)
                    if not node.optional:
                        for other_id, status in statuses.items():
                            if status == NodeStatus.QUEUED:
                                statuses[other_id] = NodeStatus.SKIPPED
                        return ExecutorOutcome(RunStatus.FAILED, results, statuses, errors)
                else:
                    statuses[node.node_id] = NodeStatus.COMPLETED
                    results[node.node_id] = item
                    agent = agents[node.agent_name]
                    context.artifacts[agent.artifact_key] = item.result

            tool_call_count = sum(
                len(skill.tool_calls)
                for result in results.values()
                for skill in result.skill_executions
            )
            if tool_call_count > plan.budget.max_tool_calls:
                raise RuntimeError("tool call budget exceeded")

        terminal = RunStatus.PARTIALLY_COMPLETED if errors else RunStatus.COMPLETED
        return ExecutorOutcome(terminal, results, statuses, errors)

    async def _execute_node(
        self,
        node,
        context: AgentRunContext,
        agents: dict[AgentName, BaseOrchestrationAgent],
        *,
        event_sink: EventSink | None,
        cancellation_check: CancellationCheck | None,
        artifact_sink: ArtifactSink | None,
    ) -> AgentResult:
        agent = agents.get(node.agent_name)
        if not agent:
            raise ValueError(f"unknown agent: {node.agent_name.value}")
        policy = node.retry_policy
        for attempt in range(1, policy.max_attempts + 1):
            if await self._is_cancelled(cancellation_check):
                raise asyncio.CancelledError()
            await self._emit(
                event_sink,
                context,
                AgentEventType.STEP_STARTED,
                node.agent_name,
                RunStatus.RUNNING,
                f"{node.agent_name.value} started.",
                {"node_id": node.node_id, "attempt": attempt, "phase": "running"},
            )
            try:
                result = await asyncio.wait_for(
                    agent.run(context), timeout=node.timeout_seconds
                )
                if artifact_sink:
                    await artifact_sink(agent.artifact_key, result)
                await self._emit_agent_audit(event_sink, context, result)
                await self._emit(
                    event_sink,
                    context,
                    AgentEventType.STEP_COMPLETED,
                    node.agent_name,
                    RunStatus.COMPLETED,
                    result.summary,
                    {"node_id": node.node_id, "attempt": attempt, "phase": "completed"},
                )
                return result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                retryable = policy.retry_class != RetryClass.NEVER
                if not retryable or attempt >= policy.max_attempts:
                    await self._emit(
                        event_sink,
                        context,
                        AgentEventType.STEP_FAILED,
                        node.agent_name,
                        RunStatus.FAILED,
                        f"{node.agent_name.value} failed.",
                        {
                            "node_id": node.node_id,
                            "attempt": attempt,
                            "error_code": "node_timeout"
                            if isinstance(exc, TimeoutError)
                            else "node_error",
                            "error_summary": str(exc)[:500],
                        },
                    )
                    raise
                await self._emit(
                    event_sink,
                    context,
                    AgentEventType.STEP_RETRYING,
                    node.agent_name,
                    RunStatus.RUNNING,
                    f"Retrying {node.agent_name.value}.",
                    {"node_id": node.node_id, "attempt": attempt + 1},
                )
                delay = min(
                    policy.max_delay_seconds,
                    policy.initial_delay_seconds * (2 ** (attempt - 1)),
                )
                delay *= 1 + random.uniform(-policy.jitter_ratio, policy.jitter_ratio)
                await asyncio.sleep(max(0.0, delay))
        raise RuntimeError("unreachable retry state")

    async def _emit_agent_audit(
        self,
        sink: EventSink | None,
        context: AgentRunContext,
        result: AgentResult,
    ) -> None:
        for skill in result.skill_executions:
            for tool_call in skill.tool_calls:
                completed = tool_call.status == "completed"
                await self._emit(
                    sink,
                    context,
                    AgentEventType.TOOL_CALL_COMPLETED
                    if completed
                    else AgentEventType.TOOL_CALL_FAILED,
                    result.agent_name,
                    RunStatus.COMPLETED if completed else RunStatus.FAILED,
                    tool_call.result_summary,
                    {
                        "skill_id": skill.skill_id,
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.tool_name,
                        "tool_display_name": tool_call.display_name,
                        "phase": tool_call.status,
                        "evidence_count": tool_call.evidence_count,
                        "duration_ms": tool_call.duration_ms,
                        "ui_visibility": tool_call.ui_visibility,
                    },
                )
            skill_completed = skill.status == "completed"
            await self._emit(
                sink,
                context,
                AgentEventType.SKILL_COMPLETED
                if skill_completed
                else AgentEventType.SKILL_FAILED,
                result.agent_name,
                RunStatus.COMPLETED if skill_completed else RunStatus.FAILED,
                skill.summary,
                {
                    "skill_id": skill.skill_id,
                    "skill_display_name": skill.display_name,
                    "phase": skill.status,
                    "confidence": skill.confidence,
                    "fallback_used": skill.fallback_used,
                    "duration_ms": skill.duration_ms,
                    "ui_visibility": "details",
                },
            )
        if result.fallback_used:
            await self._emit(
                sink,
                context,
                AgentEventType.FALLBACK_APPLIED,
                result.agent_name,
                RunStatus.COMPLETED,
                f"Fallback applied by {result.agent_name.value}.",
                {
                    "fallback_reason": result.fallback_reason,
                    "reason_codes": result.reason_codes,
                    "confidence": result.confidence,
                },
            )
        await self._emit(
            sink,
            context,
            AgentEventType.ARTIFACT_UPDATED,
            result.agent_name,
            RunStatus.COMPLETED,
            f"Updated artifact: {result.output_artifact_keys[0] if result.output_artifact_keys else 'result'}",
            {
                "artifact_key": result.output_artifact_keys[0]
                if result.output_artifact_keys
                else None
            },
        )

    async def _emit(
        self,
        sink: EventSink | None,
        context: AgentRunContext,
        event_type: AgentEventType,
        agent_name: AgentName,
        status: RunStatus,
        summary: str,
        payload: dict,
    ) -> None:
        if not sink:
            return
        await sink(
            AgentEvent(
                event_type=event_type,
                run_id=context.run_id,
                agent_name=agent_name,
                status=status,
                summary=summary,
                timestamp=datetime.now(timezone.utc),
                payload=payload,
            )
        )

    @staticmethod
    async def _is_cancelled(check: CancellationCheck | None) -> bool:
        if not check:
            return False
        value = check()
        if asyncio.iscoroutine(value):
            value = await value
        return bool(value)
