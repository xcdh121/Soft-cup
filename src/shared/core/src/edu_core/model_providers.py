import asyncio
import base64
import hashlib
import hmac
import json
import struct
from dataclasses import dataclass
from email.utils import formatdate
from typing import Any
from urllib.parse import quote, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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
    provider: str = "openai"
    app_id: str = ""
    api_secret: str = ""
    domain: str = "query"
    target_dimensions: int | None = None


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
    if config.provider.lower() == "xfyun":
        return XFYunEmbeddingService(config)

    kwargs = {
        "model": config.model,
        "api_key": _normalize_api_key(config.api_key),
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return OpenAIEmbeddings(**kwargs)


class XFYunEmbeddingService(Embeddings):
    def __init__(self, config: EmbeddingProviderConfig) -> None:
        if not config.base_url:
            raise ValueError("XFYun embedding provider requires a base_url")
        if not config.api_key:
            raise ValueError("XFYun embedding provider requires an api_key")
        if not config.api_secret:
            raise ValueError("XFYun embedding provider requires an api_secret")
        if not config.app_id:
            raise ValueError("XFYun embedding provider requires an app_id")

        self.model = config.model
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.app_id = config.app_id
        self.domain = config.domain or "query"
        self.target_dimensions = config.target_dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.gather(
            *(asyncio.to_thread(self._embed_text, text) for text in texts)
        )

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_text, text)

    def _embed_text(self, text: str) -> list[float]:
        message_text = json.dumps(
            {
                "messages": [
                    {
                        "content": text,
                        "role": "user",
                    }
                ]
            },
            ensure_ascii=False,
        )
        message_text_base64 = base64.b64encode(
            message_text.encode("utf-8")
        ).decode("utf-8")
        payload = {
            "header": {
                "app_id": self.app_id,
                "uid": "edu-agent",
                "status": 3,
            },
            "parameter": {
                "emb": {
                    "domain": self.domain,
                    "feature": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                    },
                }
            },
            "payload": {
                "messages": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "json",
                    "status": 3,
                    "text": message_text_base64,
                }
            },
        }
        request = Request(
            self._build_authenticated_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"XFYun embedding HTTP {exc.code}: {error_body}"
            ) from exc

        data = json.loads(body)
        header = data.get("header", {})
        if header.get("code", 0) != 0:
            message = header.get("message") or header.get("msg") or "Unknown error"
            raise RuntimeError(f"XFYun embedding request failed: {message}")

        embedding = self._extract_embedding(data.get("payload"))
        if not embedding:
            raise RuntimeError("XFYun embedding response did not contain a vector")
        return self._normalize_dimensions(embedding)

    def _build_authenticated_url(self) -> str:
        parsed = urlparse(self.base_url)
        host = parsed.netloc
        path = parsed.path or "/"
        date = formatdate(usegmt=True)

        signature_origin = f"host: {host}\ndate: {date}\nPOST {path} HTTP/1.1"
        digest = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")
        return (
            f"{self.base_url}?host={quote(host)}&date={quote(date)}"
            f"&authorization={quote(authorization)}"
        )

    def _extract_embedding(self, payload: Any) -> list[float] | None:
        if payload is None:
            return None
        if isinstance(payload, list):
            if payload and all(isinstance(item, (int, float)) for item in payload):
                return [float(item) for item in payload]
            for item in payload:
                embedding = self._extract_embedding(item)
                if embedding:
                    return embedding
            return None
        if isinstance(payload, dict):
            for key in ("embedding", "vector", "feature", "text", "values"):
                if key in payload:
                    embedding = self._extract_embedding(payload[key])
                    if embedding:
                        return embedding
            for value in payload.values():
                embedding = self._extract_embedding(value)
                if embedding:
                    return embedding
            return None
        if isinstance(payload, str):
            return self._decode_embedding_string(payload)
        return None

    def _decode_embedding_string(self, value: str) -> list[float] | None:
        stripped = value.strip()
        if not stripped:
            return None

        parsed_text = self._parse_text_embedding(stripped)
        if parsed_text:
            return parsed_text

        try:
            decoded = base64.b64decode(stripped, validate=True)
        except Exception:
            return None

        try:
            decoded_text = decoded.decode("utf-8")
        except UnicodeDecodeError:
            decoded_text = ""

        if decoded_text:
            parsed_decoded = self._parse_text_embedding(decoded_text.strip())
            if parsed_decoded:
                return parsed_decoded

        if len(decoded) % 4 != 0 or not decoded:
            return None

        for fmt in ("<", ">"):
            try:
                values = list(struct.unpack(f"{fmt}{len(decoded) // 4}f", decoded))
            except struct.error:
                continue
            if values and all(abs(item) < 1e6 for item in values):
                return values
        return None

    def _parse_text_embedding(self, value: str) -> list[float] | None:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        embedding = self._extract_embedding(parsed) if parsed is not None else None
        if embedding:
            return embedding

        normalized = value.replace(",", " ").split()
        if normalized and all(self._is_float_like(item) for item in normalized):
            return [float(item) for item in normalized]
        return None

    @staticmethod
    def _is_float_like(value: str) -> bool:
        try:
            float(value)
        except ValueError:
            return False
        return True

    def _normalize_dimensions(self, embedding: list[float]) -> list[float]:
        if not self.target_dimensions:
            return embedding

        if len(embedding) == self.target_dimensions:
            return embedding

        if len(embedding) > self.target_dimensions:
            return embedding[: self.target_dimensions]

        return embedding + [0.0] * (self.target_dimensions - len(embedding))
