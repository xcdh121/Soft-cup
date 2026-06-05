from dataclasses import dataclass

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


@dataclass(slots=True)
class LlmProviderConfig:
    model: str
    api_key: str = ""
    base_url: str | None = None
    temperature: float = 0.25


@dataclass(slots=True)
class EmbeddingProviderConfig:
    model: str
    api_key: str = ""
    base_url: str | None = None


def _normalize_api_key(api_key: str) -> str:
    return api_key or "local-dev-key"


def create_chat_model(
    config: LlmProviderConfig,
    *,
    streaming: bool = False,
    temperature: float | None = None,
) -> BaseChatModel:
    kwargs = {
        "model": config.model,
        "api_key": _normalize_api_key(config.api_key),
        "streaming": streaming,
        "temperature": config.temperature if temperature is None else temperature,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return ChatOpenAI(**kwargs)


def create_embeddings(config: EmbeddingProviderConfig) -> Embeddings:
    kwargs = {
        "model": config.model,
        "api_key": _normalize_api_key(config.api_key),
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return OpenAIEmbeddings(**kwargs)
