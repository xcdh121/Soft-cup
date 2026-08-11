"""Deterministic routing helpers for tutor image-generation requests."""

import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

_IMAGE_TERMS = (
    "图片",
    "图像",
    "插图",
    "配图",
    "海报",
    "示意图",
    "image",
    "illustration",
    "poster",
)
_IMAGE_GENERATION_TERMS = (
    "生成",
    "画",
    "绘制",
    "制作",
    "创建",
    "generate",
    "draw",
    "create",
    "make",
)
_AFFIRMATIVE_REPLIES = {
    "好",
    "好的",
    "可以",
    "行",
    "需要",
    "是",
    "是的",
    "生成吧",
    "画吧",
    "yes",
    "ok",
    "okay",
    "sure",
    "please do",
}

_PROGRAMMING_TERMS = (
    "编程题",
    "代码题",
    "程序设计题",
    "编程练习",
    "coding question",
    "coding exercise",
    "programming question",
    "programming exercise",
)
_PROGRAMMING_GENERATION_TERMS = (
    "生成",
    "出题",
    "出一道",
    "出几道",
    "创建",
    "制作",
    "设计",
    "generate",
    "create",
    "write",
)


@dataclass(frozen=True)
class ForcedResourceGeneration:
    """A resource generation request that must not depend on model tool choice."""

    resource_types: tuple[str, ...]
    topic: str | None


def _message_text(message: Any) -> str:
    content = (
        message.get("content", "")
        if isinstance(message, dict)
        else getattr(message, "content", "")
    )
    if isinstance(content, str):
        return content.strip().lower()
    if isinstance(content, list):
        return (
            " ".join(
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict)
            )
            .strip()
            .lower()
        )
    return str(content or "").strip().lower()


def _message_role(message: Any) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, ToolMessage):
        return "tool"
    if isinstance(message, dict):
        return str(message.get("role") or "").lower()
    return ""


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    if isinstance(message, AIMessage):
        return list(message.tool_calls)
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls") or []
        return [item for item in tool_calls if isinstance(item, dict)]
    return []


def _resource_package_called_since_last_user_message(messages: list[Any]) -> bool:
    for message in reversed(messages):
        role = _message_role(message)
        if role == "user":
            return False
        if (
            role == "tool"
            and (
                message.get("name")
                if isinstance(message, dict)
                else getattr(message, "name", None)
            )
            == "resource_package_generate"
        ):
            return True
        if role == "assistant" and any(
            tool_call.get("name") == "resource_package_generate"
            for tool_call in _message_tool_calls(message)
        ):
            return True
    return False


def should_force_image_generation(messages: list[Any]) -> bool:
    """Recognize direct and affirmative image-generation turns deterministically."""
    if _resource_package_called_since_last_user_message(messages):
        return False

    last_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if _message_role(messages[index]) == "user"
        ),
        None,
    )
    if last_user_index is None:
        return False

    user_text = _message_text(messages[last_user_index])
    has_image_term = any(term in user_text for term in _IMAGE_TERMS)
    has_generation_term = any(term in user_text for term in _IMAGE_GENERATION_TERMS)
    if has_image_term and has_generation_term:
        return True

    normalized_reply = user_text.strip().strip("\uff0c\u3002\uff01\uff1f,.!?")
    is_affirmative = normalized_reply in _AFFIRMATIVE_REPLIES or any(
        phrase in normalized_reply
        for phrase in ("生成吧", "画吧", "请生成", "开始生成", "please generate")
    )
    if not is_affirmative:
        return False
    previous_assistant = next(
        (
            message
            for message in reversed(messages[:last_user_index])
            if _message_role(message) == "assistant"
        ),
        None,
    )
    if previous_assistant is None:
        return False
    assistant_text = _message_text(previous_assistant)
    return any(term in assistant_text for term in _IMAGE_TERMS) and any(
        term in assistant_text for term in _IMAGE_GENERATION_TERMS
    )


def should_force_programming_generation(messages: list[Any]) -> bool:
    """Recognize explicit and affirmative programming-question requests."""
    if _resource_package_called_since_last_user_message(messages):
        return False

    last_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if _message_role(messages[index]) == "user"
        ),
        None,
    )
    if last_user_index is None:
        return False

    user_text = _message_text(messages[last_user_index])
    has_programming_term = any(term in user_text for term in _PROGRAMMING_TERMS)
    has_generation_term = any(
        term in user_text for term in _PROGRAMMING_GENERATION_TERMS
    )
    if has_programming_term and has_generation_term:
        return True

    normalized_reply = user_text.strip().strip("\uff0c\u3002\uff01\uff1f,.!?")
    if normalized_reply not in _AFFIRMATIVE_REPLIES:
        return False
    previous_assistant = next(
        (
            message
            for message in reversed(messages[:last_user_index])
            if _message_role(message) == "assistant"
        ),
        None,
    )
    if previous_assistant is None:
        return False
    assistant_text = _message_text(previous_assistant)
    return any(term in assistant_text for term in _PROGRAMMING_TERMS)


def extract_image_topic(messages: list[Any]) -> str | None:
    """Extract the requested subject from the user turn or the prior offer."""
    last_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if _message_role(messages[index]) == "user"
        ),
        None,
    )
    if last_user_index is None:
        return None

    candidates = [_message_text(messages[last_user_index])]
    candidates.extend(
        _message_text(message)
        for message in reversed(messages[:last_user_index])
        if _message_role(message) == "assistant"
    )
    patterns = (
        r"(?:关于|有关)\s*(.+?)(?:的)?(?:图片|图像|插图|配图|海报|示意图)",
        r"(?:生成|画|绘制|制作|创建)(?:一张|一个)?\s*(.+?)(?:的)?"
        r"(?:图片|图像|插图|配图|海报|示意图)",
        r"(?:image|illustration|poster)\s+(?:about|of)\s+(.+?)(?:[?.!]|$)",
    )
    for candidate in candidates:
        for pattern in patterns:
            match = re.search(pattern, candidate, flags=re.IGNORECASE)
            if not match:
                continue
            topic = match.group(1).strip(" \t\r\n,.!?\uff0c\u3002\uff01\uff1f")
            if topic:
                return topic
    return None


def extract_programming_topic(messages: list[Any]) -> str | None:
    """Extract the requested programming topic from the latest relevant turn."""
    last_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if _message_role(messages[index]) == "user"
        ),
        None,
    )
    if last_user_index is None:
        return None

    candidates = [_message_text(messages[last_user_index])]
    candidates.extend(
        _message_text(message)
        for message in reversed(messages[:last_user_index])
        if _message_role(message) == "assistant"
    )
    patterns = (
        r"(?:为|针对)\s*(.+?)(?:生成|创建|制作|设计|出)(?:一份|一套|一些|几道|一道)?"
        r"\s*(?:编程题|代码题|程序设计题|编程练习)",
        r"(?:关于|有关)\s*(.+?)(?:的)?(?:编程题|代码题|程序设计题|编程练习)",
        r"(?:生成|创建|制作|设计|出题|出一道|出几道)(?:一份|一套|一些|几道|一道)?"
        r"\s*(?:关于)?\s*(.+?)(?:的)?(?:编程题|代码题|程序设计题|编程练习)",
        r"(?:coding|programming)\s+(?:questions?|exercises?)\s+(?:about|on)\s+"
        r"(.+?)(?:[?.!]|$)",
    )
    for candidate in candidates:
        for pattern in patterns:
            match = re.search(pattern, candidate, flags=re.IGNORECASE)
            if not match:
                continue
            topic = match.group(1).strip(" \t\r\n,.!?\uff0c\u3002\uff01\uff1f")
            if topic:
                return topic
    return None


def resolve_forced_resource_generation(
    messages: list[Any],
) -> ForcedResourceGeneration | None:
    """Resolve deterministic resource requests before invoking the chat model."""
    if should_force_image_generation(messages):
        return ForcedResourceGeneration(
            resource_types=("image",),
            topic=extract_image_topic(messages),
        )
    if should_force_programming_generation(messages):
        return ForcedResourceGeneration(
            resource_types=("programming_questions",),
            topic=extract_programming_topic(messages),
        )
    return None
