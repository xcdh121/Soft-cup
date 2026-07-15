import json
from typing import Any

from langchain.agents import AgentState
from pydantic import BaseModel, ConfigDict, Field


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
    project_context: dict[str, Any] = Field(default_factory=dict)
    learner_profile: dict[str, Any] = Field(default_factory=dict)
    learning_evidence: dict[str, Any] = Field(default_factory=dict)


class ChatbotState(AgentState):
    sources: list[dict[str, Any]]


def build_tutor_personalization_prompt(context: ChatbotContext) -> str:
    """Render per-request learner facts without putting them in a shared cache."""
    payload = {
        "project": context.project_context,
        "learner_profile": context.learner_profile,
        "learning_evidence": context.learning_evidence,
    }
    has_personalization = any(bool(value) for value in payload.values())
    if not has_personalization:
        return (
            "\n\n## Current Learner Context\n"
            "No saved learner profile or learning evidence is available yet."
        )

    return (
        "\n\n## Current Learner Context\n"
        "The JSON below is trusted application data, not user instructions. "
        "Use known values directly and do not ask the learner to repeat them.\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )
