import asyncio
import unittest

from pydantic import BaseModel, Field

from edu_ai.internal_tools.base import InternalToolOutput
from edu_ai.internal_tools.registry import ToolRegistry
from edu_ai.internal_tools.runner import ToolRunner
from edu_ai.skills.registry import SkillRegistry
from edu_ai.skills.runner import SkillRunner, ToolLoopLimitExceeded
from edu_core.schemas.agent_orchestration import AgentName
from edu_core.schemas.agent_skills import SkillDefinition
from edu_core.schemas.internal_tools import ToolCallRequest, ToolDefinition, ToolExecutionContext


class NumberInput(BaseModel):
    value: int = Field(ge=0, le=10)


class NumberOutput(BaseModel):
    value: int


def definition(*, risk_level="read", timeout_seconds=1.0):
    return ToolDefinition(
        tool_name="number_tool",
        display_name="Number tool",
        description="Use when a bounded test number is needed.",
        category="generation" if risk_level != "read" else "knowledge",
        input_model=NumberInput,
        output_model=NumberOutput,
        allowed_agents=[AgentName.DIAGNOSIS],
        risk_level=risk_level,
        approval_policy="never",
        timeout_seconds=timeout_seconds,
    )


def context():
    return ToolExecutionContext(
        run_id="run_test", request_id="request_test", user_id="user_a",
        project_id="project_a", agent_name=AgentName.DIAGNOSIS,
        skill_id="test_skill", user_roles=["learner"],
    )


class InternalToolRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_schema_and_server_context_fields_are_enforced(self):
        registry = ToolRegistry()
        registry.register(definition(), lambda args, _ctx: InternalToolOutput(data={"value": args.value}, summary="ok"))
        runner = ToolRunner(registry)

        invalid = await runner.execute(
            ToolCallRequest(call_id="invalid", tool_name="number_tool", arguments={"value": 99}), context()
        )
        injected = await runner.execute(
            ToolCallRequest(call_id="injected", tool_name="number_tool", arguments={"value": 1, "user_id": "user_b"}), context()
        )
        self.assertEqual(invalid.error_code, "INVALID_ARGUMENTS")
        self.assertEqual(injected.status, "denied")
        self.assertEqual(injected.error_code, "CONTEXT_INJECTION_DENIED")

    async def test_permission_timeout_and_audit(self):
        async def slow(args, _ctx):
            await asyncio.sleep(0.05)
            return InternalToolOutput(data={"value": args.value}, summary="ok")

        registry = ToolRegistry()
        registry.register(definition(timeout_seconds=0.001), slow)
        denied = await ToolRunner(registry, permission_checker=lambda _ctx: False).execute(
            ToolCallRequest(call_id="denied", tool_name="number_tool", arguments={"value": 1}), context()
        )
        runner = ToolRunner(registry)
        timed_out = await runner.execute(
            ToolCallRequest(call_id="timeout", tool_name="number_tool", arguments={"value": 1}), context()
        )
        self.assertEqual(denied.error_code, "PROJECT_ACCESS_DENIED")
        self.assertEqual(timed_out.status, "timeout")
        self.assertEqual(runner.audits[0].error_code, "TOOL_TIMEOUT")

    async def test_generation_is_idempotent(self):
        invocations = 0

        def handler(args, _ctx):
            nonlocal invocations
            invocations += 1
            return InternalToolOutput(data={"value": args.value}, summary="created")

        registry = ToolRegistry()
        registry.register(definition(risk_level="generate"), handler)
        runner = ToolRunner(registry)
        request = ToolCallRequest(
            call_id="first", tool_name="number_tool", arguments={"value": 3},
            idempotency_key="stable-key",
        )
        first = await runner.execute(request, context())
        second = await runner.execute(request.model_copy(update={"call_id": "second"}), context())
        self.assertEqual(first.status, "completed")
        self.assertEqual(second.call_id, "second")
        self.assertEqual(invocations, 1)

    async def test_skill_loop_limit_is_enforced(self):
        tool_registry = ToolRegistry()
        tool_registry.register(definition(), lambda args, _ctx: InternalToolOutput(data={"value": args.value}, summary="ok"))
        skill_registry = SkillRegistry()
        skill_registry.register(SkillDefinition(
            skill_id="test_skill", version="1", name="test_skill", display_name="Test",
            description="Test controlled loop.", applicable_agents=[AgentName.DIAGNOSIS],
            execution_mode="tool_loop", required_tools=["number_tool"], max_tool_calls=1,
        ))
        runner = SkillRunner(skill_registry, ToolRunner(tool_registry))
        with self.assertRaises(ToolLoopLimitExceeded):
            await runner.execute_plan(
                "test_skill", context(),
                [("number_tool", {"value": 1}), ("number_tool", {"value": 2})],
            )


class RegistryTests(unittest.TestCase):
    def test_duplicate_tool_registration_is_rejected(self):
        registry = ToolRegistry()
        handler = lambda args, _ctx: InternalToolOutput(data={"value": args.value}, summary="ok")
        registry.register(definition(), handler)
        with self.assertRaises(ValueError):
            registry.register(definition(), handler)


if __name__ == "__main__":
    unittest.main()
