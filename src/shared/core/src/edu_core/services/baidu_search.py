from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


class BaiduSearchError(RuntimeError):
    """Raised when the Baidu AI Search API cannot return usable results."""


@dataclass(frozen=True)
class BaiduSearchConfig:
    api_key: str = ""
    base_url: str = "https://qianfan.baidubce.com"
    video_top_k: int = 6
    sites: tuple[str, ...] = ()
    timeout_seconds: float = 15.0


class BaiduSearchClient:
    def __init__(
        self,
        config: BaiduSearchConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport

    @property
    def is_enabled(self) -> bool:
        return bool(self.config.api_key.strip())

    async def search_videos(self, query: str) -> dict[str, Any]:
        if not self.is_enabled:
            raise BaiduSearchError("Baidu AI Search is not configured")

        payload: dict[str, Any] = {
            "messages": [{"content": query, "role": "user"}],
            "edition": "lite",
            "search_source": "baidu_search_v2",
            "resource_type_filter": [
                {"type": "video", "top_k": max(1, min(self.config.video_top_k, 10))}
            ],
        }
        if self.config.sites:
            payload["search_filter"] = {"match": {"site": list(self.config.sites)}}

        endpoint = f"{self.config.base_url.rstrip('/')}/v2/ai_search/web_search"
        headers = {
            "X-Appbuilder-Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BaiduSearchError(f"Baidu AI Search request failed: {exc}") from exc

        references = data.get("references")
        if not isinstance(references, list):
            raise BaiduSearchError("Baidu AI Search returned an invalid response")

        videos = [
            video for item in references if (video := self._normalize_video(item))
        ]
        if not videos:
            raise BaiduSearchError(f"No video results found for '{query}'")

        return {
            "query": query,
            "provider": "baidu_ai_search",
            "request_id": data.get("request_id"),
            "videos": videos,
        }

    def _normalize_video(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None

        video = item.get("video") if isinstance(item.get("video"), dict) else {}
        url = self._first_string(
            item.get("url"),
            video.get("url"),
            video.get("page_url"),
            video.get("play_url"),
        )
        if not url:
            return None

        image = item.get("image") if isinstance(item.get("image"), dict) else {}
        thumbnail_url = self._normalize_media_url(
            self._first_string(
                item.get("image"),
                image.get("url"),
                image.get("src"),
                video.get("cover_url"),
                video.get("cover"),
                video.get("image"),
                video.get("hover_pic"),
            )
        )
        title = self._first_string(
            item.get("title"),
            video.get("title"),
            item.get("web_anchor"),
        )
        return {
            "title": title or url,
            "url": url,
            "thumbnail_url": thumbnail_url,
            "summary": self._first_string(
                item.get("content"), video.get("description")
            ),
            "source": urlparse(url).netloc.removeprefix("www."),
            "published_at": self._first_string(item.get("date"), video.get("date")),
            "duration": self._format_duration(video.get("duration")),
        }

    @staticmethod
    def _normalize_media_url(value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("//"):
            return f"https:{value}"
        if value.startswith("http://"):
            return f"https://{value.removeprefix('http://')}"
        return value

    @staticmethod
    def _format_duration(value: Any) -> str | None:
        if isinstance(value, (int, float)) or (
            isinstance(value, str) and value.isdigit()
        ):
            total_seconds = int(value)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours:d}:{minutes:02d}:{seconds:02d}"
            return f"{minutes:d}:{seconds:02d}"
        return BaiduSearchClient._first_string(value)

    @staticmethod
    def _first_string(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
