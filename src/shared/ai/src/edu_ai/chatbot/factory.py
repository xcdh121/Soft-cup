import json
from contextlib import suppress
from typing import Any

from edu_ai.chatbot.context import (
    ChatbotContext,
    ChatbotState,
    build_tutor_personalization_prompt,
)
from edu_ai.prompts.prompts_utils import render_prompt
from edu_ai.tools.flashcard import tools as flashcard_tools
from edu_ai.tools.mind_map import tools as mind_map_tools
from edu_ai.tools.note import tools as note_tools
from edu_ai.tools.quiz import tools as quiz_tools
from edu_ai.tools.rag import tools as rag_tools
from edu_ai.tools.resource_package import tools as resource_package_tools
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRequest,
    after_model,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime


@wrap_tool_call
async def capture_sources_from_rag(request, handler):
    """Capture sources when RAG search tool is used."""
    # Execute the tool
    result = await handler(request)

    # Check if this was a search_project_documents call
    if request.tool.name == "search_project_documents" and isinstance(
        result, ToolMessage
    ):
        with suppress(Exception):
            # Parse the content to extract sources
            content = (
                json.loads(result.content)
                if isinstance(result.content, str)
                else result.content
            )
            sources = content.get("sources", [])

            # Store sources in state
            if sources:
                request.state["sources"] = sources
                # Also store in additional_kwargs so we can access it in the stream
                if (
                    not hasattr(result, "additional_kwargs")
                    or result.additional_kwargs is None
                ):
                    result.additional_kwargs = {}
                result.additional_kwargs["sources"] = sources

            # Return just the content string to the agent
            result.content = content.get("content", result.content)

    return result


# Cache system prompts by language for performance
_prompt_cache = {}

_NOTE_CREATION_TOOLS = {"note_create", "note_create_scoped"}
_NOTE_TOOLS_BLOCKED_AFTER_CREATION = {
    *_NOTE_CREATION_TOOLS,
    "note_list",
    "note_get",
}


def _note_created_since_last_user_message(messages: list[Any]) -> bool:
    """Return whether this agent turn has already queued a note creation."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, ToolMessage) and message.name in _NOTE_CREATION_TOOLS:
            return True
        if isinstance(message, AIMessage) and any(
            tool_call.get("name") in _NOTE_CREATION_TOOLS
            for tool_call in message.tool_calls
        ):
            return True
    return False


@wrap_model_call
async def stop_note_chain_after_creation(request: ModelRequest, handler):
    """Prevent redundant note creation/list/get calls in the same user turn."""
    if _note_created_since_last_user_message(request.messages):
        tools = [
            tool
            for tool in request.tools
            if isinstance(tool, dict)
            or getattr(tool, "name", None) not in _NOTE_TOOLS_BLOCKED_AFTER_CREATION
        ]
        request = request.override(tools=tools)

    return await handler(request)


def get_instructions(language: str = "English") -> str:
    """Load and render the system prompt template."""
    return render_prompt("system_prompt", language=language)


@dynamic_prompt
async def dynamic_system_prompt(request: ModelRequest) -> str:
    """Generate dynamic system prompt."""
    language = request.runtime.context.language or "English"

    if language not in _prompt_cache:
        _prompt_cache[language] = get_instructions(language)
    return _prompt_cache[language] + build_tutor_personalization_prompt(
        request.runtime.context
    )


@after_model(state_schema=ChatbotState)
def ensure_sources_in_stream(
    state: ChatbotState, runtime: Runtime[ChatbotContext]
) -> dict[str, Any] | None:
    """Ensure sources are included in the model node update for streaming."""
    sources = state.get("sources", [])
    return {"sources": sources} if sources else None


def make_chatbot(llm: BaseChatModel):
    # Chat-created content must use the unified resource-package pipeline so it
    # is visible from one results page and has one stable package link. Keep the
    # dedicated tools available for browsing/updating existing legacy content,
    # but do not expose their separate creation paths to the chat agent.
    dedicated_creation_tools = {
        "flashcards_create",
        "quiz_create",
        "note_create",
        "mindmap_create",
    }
    content_management_tools = [
        tool
        for tool in [
            *flashcard_tools,
            *quiz_tools,
            *note_tools,
            *mind_map_tools,
        ]
        if getattr(tool, "name", None) not in dedicated_creation_tools
    ]
    tools = [
        *rag_tools,
        *content_management_tools,
        *resource_package_tools,
    ]

    return create_agent(
        model=llm,
        tools=tools,
        middleware=[
            capture_sources_from_rag,
            dynamic_system_prompt,
            stop_note_chain_after_creation,
            ensure_sources_in_stream,
        ],
        state_schema=ChatbotState,
        context_schema=ChatbotContext,
    )
