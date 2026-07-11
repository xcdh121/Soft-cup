from __future__ import annotations

from dataclasses import dataclass

from edu_core.schemas.internal_tools import ToolDefinition

from edu_ai.internal_tools.base import ToolHandler


@dataclass(frozen=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if definition.tool_name in self._tools:
            raise ValueError(f"Tool already registered: {definition.tool_name}")
        self._tools[definition.tool_name] = RegisteredTool(definition, handler)

    def get(self, tool_name: str) -> RegisteredTool:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {tool_name}") from exc

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]
