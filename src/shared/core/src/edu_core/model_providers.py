import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from email.utils import format_datetime
from struct import unpack
from urllib.parse import urlencode, urlparse

import httpx
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
    provider: str = "openai"
    api_key: str = ""
    api_secret: str = ""
    app_id: str = ""
    base_url: str | None = None
    domain: str = "query"
    dimensions: int = 3072


def _normalize_api_key(api_key: str) -> str:
    return api_key or "local-dev-key"


class XfyunEmbeddingError(RuntimeError):
    """Raised when the XFYun embedding API returns an error."""


class DimensionNormalizedEmbeddings(Embeddings):
    """Normalize embedding vectors to the fixed dimension required by storage."""

    def __init__(self, inner: Embeddings, target_dimensions: int) -> None:
        self.inner = inner
        self.target_dimensions = target_dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._normalize(vec) for vec in self.inner.embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._normalize(self.inner.embed_query(text))

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = await self.inner.aembed_documents(texts)
        return [self._normalize(vec) for vec in vectors]

    async def aembed_query(self, text: str) -> list[float]:
        vector = await self.inner.aembed_query(text)
        return self._normalize(vector)

    def _normalize(self, vector: list[float]) -> list[float]:
        length = len(vector)
        if length == self.target_dimensions:
            return vector
        if length < self.target_dimensions:
            return vector + [0.0] * (self.target_dimensions - length)
        raise ValueError(
            f"Embedding dimensions {length} exceed target {self.target_dimensions}"
        )


class XfyunEmbeddings(Embeddings):
    """Embedding client for XFYun's signed HTTP embedding API."""

    def __init__(
        self,
        *,
        app_id: str,
        api_key: str,
        api_secret: str,
        base_url: str = "https://emb-cn-huabei-1.xf-yun.com/",
        domain: str = "query",
        timeout: float = 60.0,
    ) -> None:
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.domain = domain
        self.timeout = timeout

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text, domain="para") for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text, domain=self.domain or "query")

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [
            await self._aembed_one(text, domain="para")
            for text in texts
        ]

    async def aembed_query(self, text: str) -> list[float]:
        return await self._aembed_one(text, domain=self.domain or "query")

    def _embed_one(self, text: str, *, domain: str) -> list[float]:
        url = self._build_signed_url()
        with httpx.Client(timeout=self.timeout) as client:
            return self._send_with_fallbacks(client, url, text=text, domain=domain)

    async def _aembed_one(self, text: str, *, domain: str) -> list[float]:
        url = self._build_signed_url()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._asend_with_fallbacks(
                client, url, text=text, domain=domain
            )

    def _send_with_fallbacks(
        self,
        client: httpx.Client,
        url: str,
        *,
        text: str,
        domain: str,
    ) -> list[float]:
        last_error: httpx.HTTPStatusError | None = None
        for payload in self._build_payload_candidates(text=text, domain=domain):
            response = client.post(url, json=payload)
            if response.is_success:
                return self._parse_embedding_response(response.json())
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = self._augment_http_error(exc)
                if response.status_code != 400:
                    raise last_error
        if last_error is not None:
            raise last_error
        raise XfyunEmbeddingError("XFYun embedding request failed without a response")

    async def _asend_with_fallbacks(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        text: str,
        domain: str,
    ) -> list[float]:
        last_error: httpx.HTTPStatusError | None = None
        for payload in self._build_payload_candidates(text=text, domain=domain):
            response = await client.post(url, json=payload)
            if response.is_success:
                return self._parse_embedding_response(response.json())
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_error = self._augment_http_error(exc)
                if response.status_code != 400:
                    raise last_error
        if last_error is not None:
            raise last_error
        raise XfyunEmbeddingError("XFYun embedding request failed without a response")

    def _build_signed_url(self) -> str:
        parsed = urlparse(self.base_url)
        host = parsed.netloc
        path = parsed.path or "/"
        date = format_datetime(datetime.now(timezone.utc), usegmt=True)
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
        query = urlencode(
            {
                "host": host,
                "date": date,
                "authorization": authorization,
            }
        )
        return parsed._replace(query=query).geturl()

    def _build_payload(self, *, text: str, domain: str) -> dict:
        body = json.dumps(
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
        encoded_text = base64.b64encode(body.encode("utf-8")).decode("utf-8")
        return {
            "header": {
                "app_id": self.app_id,
                "uid": "edu-agent",
                "status": 3,
            },
            "parameter": {
                "emb": {
                    "domain": domain,
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
                    "text": encoded_text,
                }
            },
        }

    def _build_payload_candidates(self, *, text: str, domain: str) -> list[dict]:
        return [self._build_payload(text=text, domain=domain)]

    @staticmethod
    def _augment_http_error(exc: httpx.HTTPStatusError) -> httpx.HTTPStatusError:
        response = exc.response
        detail = response.text.strip()
        url = exc.request.url
        safe_url = f"{url.scheme}://{url.host}{url.path}"
        message = (
            f"{response.status_code} {response.reason_phrase} for url "
            f"'{safe_url}'"
        )
        if detail:
            message = f"{message}\nResponse body: {detail}"
        return httpx.HTTPStatusError(message, request=exc.request, response=response)

    def _parse_embedding_response(self, data: dict) -> list[float]:
        header = data.get("header", {})
        code = header.get("code", 0)
        if code not in (0, "0", None):
            message = header.get("message") or header.get("desc") or "unknown error"
            sid = header.get("sid")
            raise XfyunEmbeddingError(
                f"XFYun embedding request failed with code {code}: {message} (sid={sid})"
            )

        candidate = self._find_embedding_candidate(data)
        if isinstance(candidate, list):
            return [float(item) for item in candidate]
        if isinstance(candidate, str):
            return self._decode_embedding_text(candidate)
        raise XfyunEmbeddingError("Could not locate embedding vector in XFYun response")

    def _find_embedding_candidate(self, data: dict):
        payload = data.get("payload", {})
        for key in ("feature", "emb", "vector", "embedding"):
            node = payload.get(key)
            if isinstance(node, dict):
                text = node.get("text")
                if text is not None:
                    return text
                if node.get("vector") is not None:
                    return node.get("vector")
                if node.get("embedding") is not None:
                    return node.get("embedding")
        if payload.get("text") is not None:
            return payload.get("text")
        if data.get("vector") is not None:
            return data.get("vector")
        return data.get("embedding")

    @staticmethod
    def _decode_embedding_text(text: str) -> list[float]:
        stripped = text.strip()
        if not stripped:
            raise XfyunEmbeddingError("Received empty embedding payload from XFYun")

        if stripped.startswith("["):
            parsed = json.loads(stripped)
            return [float(item) for item in parsed]

        try:
            decoded = base64.b64decode(stripped, validate=True)
        except Exception:
            parts = [part.strip() for part in stripped.split(",") if part.strip()]
            if parts:
                return [float(part) for part in parts]
            raise XfyunEmbeddingError("Unsupported XFYun embedding payload format")

        if not decoded:
            raise XfyunEmbeddingError("Decoded XFYun embedding payload is empty")

        if len(decoded) % 4 == 0:
            count = len(decoded) // 4
            try:
                return list(unpack(f"<{count}f", decoded))
            except Exception:
                pass

        decoded_text = decoded.decode("utf-8", errors="ignore").strip()
        if decoded_text.startswith("["):
            parsed = json.loads(decoded_text)
            return [float(item) for item in parsed]
        if "," in decoded_text:
            parts = [part.strip() for part in decoded_text.split(",") if part.strip()]
            if parts:
                return [float(part) for part in parts]
        raise XfyunEmbeddingError("Unsupported decoded XFYun embedding payload format")


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
        if not config.app_id:
            raise ValueError("XFYun embeddings require EMBEDDING_APP_ID")
        if not config.api_key:
            raise ValueError("XFYun embeddings require EMBEDDING_API_KEY")
        if not config.api_secret:
            raise ValueError("XFYun embeddings require EMBEDDING_API_SECRET")
        embeddings: Embeddings = XfyunEmbeddings(
            app_id=config.app_id,
            api_key=config.api_key,
            api_secret=config.api_secret,
            base_url=config.base_url or "https://emb-cn-huabei-1.xf-yun.com/",
            domain=config.domain or "query",
        )
        return DimensionNormalizedEmbeddings(embeddings, config.dimensions)

    kwargs = {
        "model": config.model,
        "api_key": _normalize_api_key(config.api_key),
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    embeddings = OpenAIEmbeddings(**kwargs)
    return DimensionNormalizedEmbeddings(embeddings, config.dimensions)
