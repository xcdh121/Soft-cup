from typing import TYPE_CHECKING, Any

from edu_core.services.search import SearchService
from edu_queue.service import ArqQueueService, QueueService
from langchain.agents import AgentState
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass


class ChatbotContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: str
    language: str
    project_id: str
    search: "SearchService"
    queue: "QueueService | ArqQueueService"
    usage: object = (
        None  # Optional usage service (can be None or any usage service type)
    )
    llm: "BaseChatModel | None" = (
        None  # Optional LLM instance for content generation tools
    )


class ChatbotState(AgentState):
    sources: list[dict[str, Any]]
