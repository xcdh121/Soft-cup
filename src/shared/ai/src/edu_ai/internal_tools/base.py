from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from edu_core.schemas.agent_orchestration import AgentEvidence
from edu_core.schemas.internal_tools import ToolExecutionContext


class InternalToolOutput(BaseModel):
    data: dict[str, Any] | list[Any]
    summary: str
    evidence_refs: list[AgentEvidence] = Field(default_factory=list)


ToolHandler = Callable[
    [BaseModel, ToolExecutionContext],
    InternalToolOutput | Awaitable[InternalToolOutput],
]
