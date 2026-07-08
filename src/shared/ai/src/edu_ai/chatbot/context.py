from typing import Any

from langchain.agents import AgentState
from pydantic import BaseModel, ConfigDict


class ChatbotContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: str
    language: str
    project_id: str
    search: Any
    queue: Any
    usage: object = (
        None  # Optional usage service (can be None or any usage service type)
    )
    llm: Any = None
    resource_packages: Any = None


class ChatbotState(AgentState):
    sources: list[dict[str, Any]]
