"""Provision defaults and run non-secret production integration smoke checks."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from config import get_settings
from default_courses import ensure_default_courses
from dependencies import get_xfyun_image_understanding_client
from edu_db.models import Course, User
from edu_db.session import get_session_factory, init_db
from edu_core.services import UserService
from routers.auth import RegisterRequest, register
from xfyun_handwriting import XfyunHandwritingClient, XfyunHandwritingConfig
from routers.speech import get_xfyun_iat_url
from websockets.asyncio.client import connect


def provision_courses() -> None:
    init_db(os.environ["DATABASE_URL"])
    session_factory = get_session_factory()
    with session_factory() as db:
        user_ids = [user_id for (user_id,) in db.query(User.id).all()]

    for user_id in user_ids:
        ensure_default_courses(user_id)

    with session_factory() as db:
        verified = sum(
            1
            for user_id in user_ids
            if db.query(Course)
            .filter(
                Course.owner_id == user_id,
                Course.code.in_(("DSA-MVP", "ML-DEMO")),
            )
            .count()
            == 2
        )
    print(f"default_courses: users={len(user_ids)} verified={verified}")


async def check_integrations() -> None:
    settings = get_settings()
    checks = {
        "iat": settings.xfyun_iat_enabled
        and bool(
            settings.xfyun_iat_app_id
            and settings.xfyun_iat_api_key
            and settings.xfyun_iat_api_secret
        ),
        "handwriting": settings.xfyun_handwriting_enabled
        and bool(settings.xfyun_handwriting_app_id and settings.xfyun_handwriting_api_key),
        "image_understanding": settings.xfyun_image_understanding_enabled
        and bool(
            settings.xfyun_image_understanding_app_id
            and settings.xfyun_image_understanding_api_key
            and settings.xfyun_image_understanding_api_secret
        ),
        "pdf_ocr": settings.xfyun_pdf_ocr_enabled
        and bool(settings.xfyun_pdf_ocr_app_id and settings.xfyun_pdf_ocr_secret),
        "translation": settings.xfyun_translation_enabled
        and bool(
            settings.xfyun_translation_app_id
            and settings.xfyun_translation_api_key
            and settings.xfyun_translation_api_secret
        ),
        "image_generation": settings.xfyun_image_generation_enabled
        and bool(
            settings.xfyun_image_generation_app_id
            and settings.xfyun_image_generation_api_key
            and settings.xfyun_image_generation_api_secret
        ),
    }
    print(f"configured: {checks}")

    try:
        signed_iat = await get_xfyun_iat_url(None, settings)
        async with connect(
            signed_iat.url,
            open_timeout=15,
            close_timeout=5,
        ):
            print("iat_websocket_smoke: ok")
    except Exception as exc:
        print(f"iat_websocket_smoke: failed type={type(exc).__name__} detail={exc}")

    image_path = Path("/app/src/source/4.jpg")
    if not image_path.is_file():
        print("provider_smoke: skipped (sample image unavailable)")
        return
    image = image_path.read_bytes()

    handwriting = XfyunHandwritingClient(
        XfyunHandwritingConfig(
            enabled=settings.xfyun_handwriting_enabled,
            app_id=settings.xfyun_handwriting_app_id,
            api_key=settings.xfyun_handwriting_api_key,
            base_url=settings.xfyun_handwriting_base_url,
            timeout_seconds=settings.xfyun_handwriting_timeout_seconds,
        )
    )
    try:
        result = await handwriting.recognize(image)
        print(f"handwriting_smoke: ok text_length={len(result.get('text', ''))}")
    except Exception as exc:
        print(f"handwriting_smoke: failed type={type(exc).__name__} detail={exc}")

    image_understanding = get_xfyun_image_understanding_client(settings)
    try:
        answer = await image_understanding.understand(
            image,
            question="请用一句话描述这张图片。",
            uid="production-smoke-check",
        )
        print(f"image_understanding_smoke: ok response_length={len(answer)}")
    except Exception as exc:
        print(
            "image_understanding_smoke: failed "
            f"type={type(exc).__name__} detail={exc}"
        )


async def check_registration_defaults() -> None:
    username = f"smoke-{uuid4().hex[:12]}"
    user_id: str | None = None
    try:
        response = await register(
            RegisterRequest(
                username=username,
                password=f"Smoke-{uuid4().hex}",
                name="Production Smoke Check",
            )
        )
        user_id = response.user.id
        session_factory = get_session_factory()
        with session_factory() as db:
            course_count = (
                db.query(Course)
                .filter(
                    Course.owner_id == user_id,
                    Course.code.in_(("DSA-MVP", "ML-DEMO")),
                )
                .count()
            )
        print(f"registration_default_courses_smoke: count={course_count}")
        if course_count != 2:
            raise RuntimeError("registration did not provision both default courses")
    finally:
        if user_id:
            UserService().delete_user(user_id)


if __name__ == "__main__":
    provision_courses()
    asyncio.run(check_registration_defaults())
    asyncio.run(check_integrations())
