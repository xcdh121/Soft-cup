from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from edu_core.schemas.internal_tools import (
    ToolCallAudit,
    ToolCallRequest,
    ToolCallResult,
    ToolExecutionContext,
)

from edu_ai.internal_tools.registry import ToolRegistry


SENSITIVE_KEYS = {
    "user_id", "student_id", "project_id", "authorization", "api_key",
    "access_token", "password", "secret", "cookie", "context",
}
AuditSink = Callable[[ToolCallAudit], None | Awaitable[None]]
PermissionChecker = Callable[[ToolExecutionContext], bool | Awaitable[bool]]


class ToolRunner:
    """The only execution path for model-visible internal tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        permission_checker: PermissionChecker | None = None,
        audit_sink: AuditSink | None = None,
        max_result_chars: int = 12_000,
    ) -> None:
        self.registry = registry
        self.permission_checker = permission_checker or (lambda _context: True)
        self.audit_sink = audit_sink
        self.max_result_chars = max_result_chars
        self.audits: list[ToolCallAudit] = []
        self._idempotency_cache: dict[str, ToolCallResult] = {}

    async def execute(
        self, request: ToolCallRequest, context: ToolExecutionContext
    ) -> ToolCallResult:
        started_at = datetime.now(timezone.utc)
        started = monotonic()
        try:
            tool = self.registry.get(request.tool_name)
        except KeyError:
            failed = ToolCallResult(
                call_id=request.call_id, tool_name=request.tool_name, status="failed",
                summary="工具不存在或未启用。", error_code="TOOL_NOT_FOUND",
                retryable=False, duration_ms=0,
            )
            audit = ToolCallAudit(
                id=request.call_id, run_id=context.run_id,
                agent_name=context.agent_name, skill_id=context.skill_id,
                tool_name=request.tool_name, tool_version="unknown",
                status="failed", risk_level="read", approval_status="not_required",
                arguments=self._sanitize(request.arguments),
                result_summary={"summary": failed.summary}, error_code=failed.error_code,
                started_at=started_at, completed_at=datetime.now(timezone.utc), duration_ms=0,
            )
            self.audits.append(audit)
            if self.audit_sink:
                emitted = self.audit_sink(audit)
                if inspect.isawaitable(emitted):
                    await emitted
            return failed
        definition = tool.definition
        approval_status = "not_required"
        safe_arguments = self._sanitize(request.arguments)

        def result(status: str, summary: str, **kwargs: Any) -> ToolCallResult:
            return ToolCallResult(
                call_id=request.call_id,
                tool_name=request.tool_name,
                status=status,
                summary=summary,
                duration_ms=max(0, int((monotonic() - started) * 1000)),
                **kwargs,
            )

        try:
            forbidden = SENSITIVE_KEYS.intersection(
                key.casefold() for key in request.arguments
            )
            if forbidden:
                return await self._finish(
                    request, context, definition, started_at, safe_arguments,
                    approval_status, result("denied", "工具参数包含服务器专属字段。", error_code="CONTEXT_INJECTION_DENIED"),
                )
            if context.agent_name not in definition.allowed_agents:
                return await self._finish(
                    request, context, definition, started_at, safe_arguments,
                    approval_status, result("denied", "当前智能体无权调用此工具。", error_code="AGENT_NOT_ALLOWED"),
                )
            allowed = self.permission_checker(context)
            if inspect.isawaitable(allowed):
                allowed = await allowed
            if not allowed:
                return await self._finish(
                    request, context, definition, started_at, safe_arguments,
                    approval_status, result("denied", "用户无权访问该项目。", error_code="PROJECT_ACCESS_DENIED"),
                )

            approval_required = definition.approval_policy == "always" or (
                definition.approval_policy == "conditional"
                and definition.risk_level in {"write", "destructive"}
            )
            if approval_required and request.call_id not in context.approved_tool_calls:
                approval_status = "required"
                return await self._finish(
                    request, context, definition, started_at, safe_arguments,
                    approval_status, result("denied", "该操作需要用户确认。", error_code="APPROVAL_REQUIRED"),
                )
            if approval_required:
                approval_status = "approved"

            idempotency_key = request.idempotency_key
            if definition.risk_level != "read":
                idempotency_key = idempotency_key or self._derive_key(request, context)
                cached = self._idempotency_cache.get(idempotency_key)
                if cached:
                    cached_result = cached.model_copy(
                        update={"call_id": request.call_id, "duration_ms": 0}
                    )
                    return await self._finish(
                        request, context, definition, started_at, safe_arguments,
                        approval_status, cached_result, idempotency_key=idempotency_key,
                    )

            arguments = definition.input_model.model_validate(request.arguments)
            invocation = tool.handler(arguments, context)
            if not inspect.isawaitable(invocation):
                immediate_value = invocation
                async def immediate():
                    return immediate_value
                invocation = immediate()
            output = await asyncio.wait_for(invocation, timeout=definition.timeout_seconds)
            validated = definition.output_model.model_validate(output.data)
            data = self._limit_result(validated.model_dump(mode="json"))
            completed = result(
                "completed", output.summary, data=data,
                evidence_refs=output.evidence_refs,
            )
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = completed
            return await self._finish(
                request, context, definition, started_at, safe_arguments,
                approval_status, completed, idempotency_key=idempotency_key,
            )
        except ValidationError as exc:
            return await self._finish(
                request, context, definition, started_at, safe_arguments,
                approval_status,
                result("failed", "工具参数校验失败。", error_code="INVALID_ARGUMENTS", retryable=False),
                error_message=str(exc),
            )
        except TimeoutError:
            return await self._finish(
                request, context, definition, started_at, safe_arguments,
                approval_status,
                result("timeout", "工具执行超时。", error_code="TOOL_TIMEOUT", retryable=True),
            )
        except Exception as exc:
            return await self._finish(
                request, context, definition, started_at, safe_arguments,
                approval_status,
                result("failed", "工具执行失败。", error_code="TOOL_EXECUTION_FAILED", retryable=False),
                error_message=str(exc),
            )

    async def _finish(
        self, request, context, definition, started_at, arguments,
        approval_status, result, *, idempotency_key=None, error_message=None,
    ):
        audit = ToolCallAudit(
            id=request.call_id,
            run_id=context.run_id,
            agent_name=context.agent_name,
            skill_id=context.skill_id,
            tool_name=definition.tool_name,
            tool_version=definition.version,
            status=result.status,
            risk_level=definition.risk_level,
            approval_status=approval_status,
            arguments=arguments,
            result_summary={"summary": result.summary},
            evidence_refs=result.evidence_refs,
            idempotency_key=idempotency_key or request.idempotency_key,
            error_code=result.error_code,
            error_message=error_message,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=result.duration_ms,
        )
        if definition.audit_enabled:
            self.audits.append(audit)
            if self.audit_sink:
                emitted = self.audit_sink(audit)
                if inspect.isawaitable(emitted):
                    await emitted
        return result

    @staticmethod
    def _derive_key(request: ToolCallRequest, context: ToolExecutionContext) -> str:
        payload = json.dumps(
            [context.user_id, context.project_id, request.tool_name, request.arguments],
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def _sanitize(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "[REDACTED]" if key.casefold() in SENSITIVE_KEYS else cls._sanitize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._sanitize(item) for item in value[:50]]
        if isinstance(value, str) and len(value) > 500:
            return value[:500] + "…"
        return value

    def _limit_result(self, data: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(data, ensure_ascii=False, default=str)
        if len(encoded) <= self.max_result_chars:
            return data
        return {"truncated": True, "preview": encoded[: self.max_result_chars]}
