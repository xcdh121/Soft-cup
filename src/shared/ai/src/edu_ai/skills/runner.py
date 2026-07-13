from __future__ import annotations

import asyncio
import json
from time import monotonic
from uuid import uuid4

from edu_core.schemas.agent_skills import SkillExecutionSummary
from edu_core.schemas.internal_tools import ToolCallRequest, ToolCallSummary, ToolExecutionContext

from edu_ai.internal_tools.runner import ToolRunner
from edu_ai.skills.registry import SkillRegistry


class ToolLoopLimitExceeded(RuntimeError):
    pass


class RepeatedToolCall(RuntimeError):
    pass


class SkillRunner:
    def __init__(self, registry: SkillRegistry, tool_runner: ToolRunner) -> None:
        self.registry = registry
        self.tool_runner = tool_runner

    async def execute_plan(
        self,
        skill_id: str,
        context: ToolExecutionContext,
        calls: list[tuple[str, dict]],
    ) -> SkillExecutionSummary:
        skill = self.registry.get(skill_id)
        if context.agent_name not in skill.applicable_agents:
            raise PermissionError(f"{context.agent_name} cannot execute {skill_id}")
        missing = [name for name in skill.required_tools if not self.tool_runner.registry.has(name)]
        if missing:
            raise RuntimeError(f"Required tools unavailable: {', '.join(missing)}")
        if len(calls) > skill.max_tool_calls:
            raise ToolLoopLimitExceeded(skill_id)

        started = monotonic()
        execution_id = f"skill_{uuid4().hex}"
        seen: set[str] = set()
        summaries: list[ToolCallSummary] = []
        evidence_count = 0

        async def run_calls():
            nonlocal evidence_count
            for tool_name, arguments in calls:
                fingerprint = json.dumps([tool_name, arguments], sort_keys=True, ensure_ascii=False)
                if fingerprint in seen:
                    raise RepeatedToolCall(tool_name)
                seen.add(fingerprint)
                call_id = f"call_{uuid4().hex}"
                result = await self.tool_runner.execute(
                    ToolCallRequest(call_id=call_id, tool_name=tool_name, arguments=arguments), context
                )
                definition = self.tool_runner.registry.get(tool_name).definition
                evidence_count += len(result.evidence_refs)
                summaries.append(ToolCallSummary(
                    id=call_id, tool_name=tool_name, display_name=definition.display_name,
                    status=result.status, result_summary=result.summary,
                    evidence_count=len(result.evidence_refs), duration_ms=result.duration_ms,
                    ui_visibility=definition.result_visibility,
                ))
                if tool_name in skill.required_tools and result.status != "completed":
                    raise RuntimeError(f"Required tool failed: {tool_name}")

        try:
            await asyncio.wait_for(run_calls(), timeout=skill.timeout_seconds)
            status = "completed"
            summary = f"{skill.display_name}完成，共调用 {len(summaries)} 个工具，获得 {evidence_count} 条证据引用。"
            error_code = None
            error_message = None
        except Exception as exc:
            status = "failed"
            summary = f"{skill.display_name}未完成，已转入保守回退。"
            error_code = type(exc).__name__
            error_message = str(exc)

        return SkillExecutionSummary(
            id=execution_id, agent_name=context.agent_name, skill_id=skill.skill_id,
            display_name=skill.display_name, version=skill.version, status=status,
            summary=summary, duration_ms=int((monotonic() - started) * 1000),
            input_summary={"tool_call_count": len(calls), "source_ids": [context.project_id]},
            output_summary={"evidence_count": evidence_count},
            fallback_used=status == "failed", fallback_reason=error_code if status == "failed" else None,
            error_code=error_code, error_message=error_message, tool_calls=summaries,
        )
