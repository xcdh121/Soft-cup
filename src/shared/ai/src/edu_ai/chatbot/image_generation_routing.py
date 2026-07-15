"""Deterministic routing helpers for tutor image-generation requests."""

import re
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


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip().lower()
    if isinstance(content, list):
        return " ".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, dict)
        ).strip().lower()
    return str(content or "").strip().lower()


def _resource_package_called_since_last_user_message(messages: list[Any]) -> bool:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return False
        if (
            isinstance(message, ToolMessage)
            and message.name == "resource_package_generate"
        ):
            return True
        if isinstance(message, AIMessage) and any(
            tool_call.get("name") == "resource_package_generate"
            for tool_call in message.tool_calls
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
            if isinstance(messages[index], HumanMessage)
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

    normalized_reply = user_text.strip().strip("\uFF0C\u3002\uFF01\uFF1F,.!?")
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
            if isinstance(message, AIMessage)
        ),
        None,
    )
    if previous_assistant is None:
        return False
    assistant_text = _message_text(previous_assistant)
    return any(term in assistant_text for term in _IMAGE_TERMS) and any(
        term in assistant_text for term in _IMAGE_GENERATION_TERMS
    )


def extract_image_topic(messages: list[Any]) -> str | None:
    """Extract the requested subject from the user turn or the prior offer."""
    last_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], HumanMessage)
        ),
        None,
    )
    if last_user_index is None:
        return None

    candidates = [_message_text(messages[last_user_index])]
    candidates.extend(
        _message_text(message)
        for message in reversed(messages[:last_user_index])
        if isinstance(message, AIMessage)
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
            topic = match.group(1).strip(
                " \t\r\n,.!?\uFF0C\u3002\uFF01\uFF1F"
            )
            if topic:
                return topic
    return None
