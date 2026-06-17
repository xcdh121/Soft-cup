import asyncio
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


class XfyunPptError(RuntimeError):
    """Raised when the XFYun PPT API returns an error."""


@dataclass(slots=True)
class XfyunPptConfig:
    app_id: str = ""
    secret: str = ""
    base_url: str = "https://zwapi.xfyun.cn"
    business_id: str = ""
    default_author: str = "EduAgent"
    default_language: str = "cn"
    default_search: bool = False
    default_is_card_note: bool = False
    default_is_figure: bool = False
    default_ai_image: str = "normal"
    poll_interval_seconds: float = 3.0
    poll_timeout_seconds: float = 180.0
    enabled: bool = False


class XfyunPptClient:
    """Thin async client for the XFYun PPT generation API."""

    def __init__(self, config: XfyunPptConfig) -> None:
        self.config = config

    @property
    def is_enabled(self) -> bool:
        return (
            self.config.enabled
            and bool(self.config.app_id)
            and bool(self.config.secret)
        )

    async def list_templates(
        self,
        *,
        style: str | None = None,
        color: str | None = None,
        industry: str | None = None,
        page_num: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        payload = {
            "style": style,
            "color": color,
            "industry": industry,
            "pageNum": page_num,
            "pageSize": page_size,
        }
        payload = {key: value for key, value in payload.items() if value not in (None, "")}
        return await self._request(
            "POST",
            "/api/ppt/v2/template/list",
            json_body=payload,
        )

    async def create(
        self,
        *,
        query: str | None = None,
        template_id: str | None = None,
        author: str | None = None,
        language: str | None = None,
        search: bool | None = None,
        is_card_note: bool | None = None,
        is_figure: bool | None = None,
        ai_image: str | None = None,
        business_id: str | None = None,
        file_path: Path | None = None,
        file_name: str | None = None,
        file_url: str | None = None,
    ) -> dict[str, Any]:
        form_data = self._build_generation_form(
            query=query,
            template_id=template_id,
            author=author,
            language=language,
            search=search,
            is_card_note=is_card_note,
            is_figure=is_figure,
            ai_image=ai_image,
            business_id=business_id,
            file_name=file_name,
            file_url=file_url,
        )
        return await self._multipart_request(
            "/api/ppt/v2/create",
            data=form_data,
            file_path=file_path,
            file_field="file",
            file_name=file_name,
        )

    async def create_outline(
        self,
        *,
        query: str,
        language: str | None = None,
        search: bool | None = None,
        business_id: str | None = None,
    ) -> dict[str, Any]:
        data = {
            "query": query,
            "language": language or self.config.default_language,
            "search": self._bool_to_str(
                self.config.default_search if search is None else search
            ),
        }
        if business_id or self.config.business_id:
            data["businessId"] = business_id or self.config.business_id
        return await self._multipart_request("/api/ppt/v2/createOutline", data=data)

    async def create_outline_by_doc(
        self,
        *,
        query: str | None = None,
        language: str | None = None,
        search: bool | None = None,
        business_id: str | None = None,
        file_path: Path | None = None,
        file_name: str | None = None,
        file_url: str | None = None,
    ) -> dict[str, Any]:
        data = {
            "query": query,
            "language": language or self.config.default_language,
            "search": self._bool_to_str(
                self.config.default_search if search is None else search
            ),
            "fileName": file_name,
            "fileUrl": file_url,
        }
        if business_id or self.config.business_id:
            data["businessId"] = business_id or self.config.business_id
        data = {key: value for key, value in data.items() if value not in (None, "")}
        return await self._multipart_request(
            "/api/ppt/v2/createOutlineByDoc",
            data=data,
            file_path=file_path,
            file_field="file",
            file_name=file_name,
        )

    async def create_ppt_by_outline(
        self,
        *,
        outline: dict[str, Any],
        query: str | None = None,
        template_id: str | None = None,
        author: str | None = None,
        language: str | None = None,
        search: bool | None = None,
        is_card_note: bool | None = None,
        is_figure: bool | None = None,
        ai_image: str | None = None,
        business_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "outline": outline,
            "query": query or "",
            "templateId": template_id,
            "author": author or self.config.default_author,
            "language": language or self.config.default_language,
            "search": self.config.default_search if search is None else search,
            "isCardNote": (
                self.config.default_is_card_note
                if is_card_note is None
                else is_card_note
            ),
            "isFigure": (
                self.config.default_is_figure if is_figure is None else is_figure
            ),
            "aiImage": ai_image or self.config.default_ai_image,
        }
        if business_id or self.config.business_id:
            payload["businessId"] = business_id or self.config.business_id
        payload = {
            key: value
            for key, value in payload.items()
            if value is not None and value != ""
        }
        return await self._request(
            "POST",
            "/api/ppt/v2/createPptByOutline",
            json_body=payload,
        )

    async def get_progress(self, sid: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/ppt/v2/progress?sid={sid}")

    async def wait_for_completion(self, sid: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.poll_timeout_seconds
        last_payload: dict[str, Any] | None = None

        while time.monotonic() < deadline:
            last_payload = await self.get_progress(sid)
            data = last_payload.get("data") or {}
            ppt_status = str(data.get("pptStatus") or "").lower()
            if ppt_status == "done" and data.get("pptUrl"):
                return last_payload
            if ppt_status in {"build_failed", "failed"}:
                err_msg = data.get("errMsg") or last_payload.get("desc") or "unknown error"
                raise XfyunPptError(f"XFYun PPT generation failed: {err_msg}")
            await self._sleep()

        raise XfyunPptError(
            f"Timed out waiting for XFYun PPT generation sid={sid}. "
            f"Last response: {json.dumps(last_payload or {}, ensure_ascii=False)}"
        )

    async def _sleep(self) -> None:
        await asyncio.sleep(self.config.poll_interval_seconds)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        headers = self._build_headers()
        async with httpx.AsyncClient(timeout=self.config.poll_timeout_seconds) as client:
            response = await client.request(method, url, headers=headers, json=json_body)
        response.raise_for_status()
        payload = response.json()
        self._raise_if_api_error(payload)
        return payload

    async def _multipart_request(
        self,
        path: str,
        *,
        data: dict[str, Any],
        file_path: Path | None = None,
        file_field: str = "file",
        file_name: str | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        headers = self._build_headers()
        files = None
        if file_path is not None:
            resolved_name = file_name or file_path.name
            files = {
                file_field: (
                    resolved_name,
                    file_path.read_bytes(),
                    "application/octet-stream",
                )
            }

        clean_data = {
            key: value for key, value in data.items() if value is not None and value != ""
        }
        async with httpx.AsyncClient(timeout=self.config.poll_timeout_seconds) as client:
            response = await client.post(url, headers=headers, data=clean_data, files=files)
        response.raise_for_status()
        payload = response.json()
        self._raise_if_api_error(payload)
        return payload

    def _build_generation_form(
        self,
        *,
        query: str | None,
        template_id: str | None,
        author: str | None,
        language: str | None,
        search: bool | None,
        is_card_note: bool | None,
        is_figure: bool | None,
        ai_image: str | None,
        business_id: str | None,
        file_name: str | None,
        file_url: str | None,
    ) -> dict[str, Any]:
        data = {
            "query": query,
            "templateId": template_id,
            "author": author or self.config.default_author,
            "language": language or self.config.default_language,
            "search": self._bool_to_str(
                self.config.default_search if search is None else search
            ),
            "isCardNote": self._bool_to_str(
                self.config.default_is_card_note
                if is_card_note is None
                else is_card_note
            ),
            "isFigure": self._bool_to_str(
                self.config.default_is_figure if is_figure is None else is_figure
            ),
            "aiImage": ai_image or self.config.default_ai_image,
            "fileName": file_name,
            "fileUrl": file_url,
        }
        if business_id or self.config.business_id:
            data["businessId"] = business_id or self.config.business_id
        return data

    def _build_headers(self) -> dict[str, str]:
        timestamp = str(int(time.time()))
        signature = self._get_signature(
            app_id=self.config.app_id,
            secret=self.config.secret,
            timestamp=timestamp,
        )
        return {
            "appId": self.config.app_id,
            "timestamp": timestamp,
            "signature": signature,
        }

    def _build_url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    @staticmethod
    def _bool_to_str(value: bool) -> str:
        return "true" if value else "false"

    @staticmethod
    def _get_signature(*, app_id: str, secret: str, timestamp: str) -> str:
        auth = hashlib.md5(f"{app_id}{timestamp}".encode("utf-8")).hexdigest()
        digest = hmac.new(
            secret.encode("utf-8"),
            auth.encode("utf-8"),
            digestmod=hashlib.sha1,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _raise_if_api_error(payload: dict[str, Any]) -> None:
        code = payload.get("code", 0)
        if code not in (0, "0", None):
            desc = payload.get("desc") or payload.get("message") or "unknown error"
            raise XfyunPptError(f"XFYun PPT API error {code}: {desc}")
