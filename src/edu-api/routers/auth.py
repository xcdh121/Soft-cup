"""Self-hosted username/password authentication endpoints."""

import re
from pathlib import Path
from uuid import uuid4

from auth import get_current_user
from config import get_settings
from default_courses import ensure_default_courses
from edu_core.schemas.users import UserDto
from edu_core.services import BillingService, UserService
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from security import (
    create_access_token,
    hash_password,
    normalize_username,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_TYPES = {
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (
        ".webp",
        lambda data: len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP",
    ),
}
AVATAR_NAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp)$")
AVATAR_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserDto


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


def _issue_token(user: UserDto) -> AuthResponse:
    settings = get_settings()
    if len(settings.auth_jwt_secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_JWT_SECRET must be configured with at least 32 characters",
        )
    token, expires_in = create_access_token(
        user_id=user.id,
        username=user.username,
        secret=settings.auth_jwt_secret,
        expires_minutes=settings.auth_access_token_expire_minutes,
    )
    return AuthResponse(access_token=token, expires_in=expires_in, user=user)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest) -> AuthResponse:
    settings = get_settings()
    if not settings.auth_allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    admin_usernames = {
        username.strip().casefold()
        for username in settings.auth_admin_usernames.split(",")
        if username.strip()
    }
    is_admin = payload.username in admin_usernames
    try:
        user = UserService().create_local_user(
            username=payload.username,
            name=payload.name,
            password_hash=hash_password(payload.password),
            is_admin=is_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if not user.is_admin:
        ensure_default_courses(user.id)
        BillingService().ensure_trial_entitlement(user_id=user.id)
    return _issue_token(user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: CredentialsRequest) -> AuthResponse:
    record = UserService().get_user_auth_record(payload.username)
    if not record or not verify_password(payload.password, record[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账户名或密码错误",
        )
    user = record[0]
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    if not user.is_admin:
        ensure_default_courses(user.id)
    return _issue_token(user)


@router.get("/me", response_model=UserDto)
async def get_current_user_info(
    current_user: UserDto = Depends(get_current_user),
) -> UserDto:
    return current_user


@router.patch("/me", response_model=UserDto)
async def update_current_user_profile(
    payload: UpdateProfileRequest,
    current_user: UserDto = Depends(get_current_user),
) -> UserDto:
    return UserService().update_profile(current_user.id, name=payload.name)


@router.post("/me/avatar", response_model=UserDto)
async def upload_current_user_avatar(
    file: UploadFile = File(...),
    current_user: UserDto = Depends(get_current_user),
) -> UserDto:
    avatar_type = AVATAR_TYPES.get(file.content_type or "")
    if not avatar_type:
        raise HTTPException(status_code=415, detail="头像仅支持 JPG、PNG 或 WebP 图片")

    content = await file.read(MAX_AVATAR_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="头像文件不能为空")
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="头像文件不能超过 5MB")

    extension, has_valid_signature = avatar_type
    if not has_valid_signature(content):
        raise HTTPException(status_code=415, detail="头像文件内容与图片格式不符")

    avatar_directory = Path(get_settings().storage_root) / "avatars"
    avatar_directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    avatar_path = avatar_directory / filename
    avatar_path.write_bytes(content)
    avatar_url = f"/api/v1/auth/avatars/{filename}"

    try:
        updated_user = UserService().update_profile(
            current_user.id,
            avatar_url=avatar_url,
        )
    except Exception:
        avatar_path.unlink(missing_ok=True)
        raise

    if current_user.avatar_url:
        old_filename = current_user.avatar_url.rsplit("/", 1)[-1]
        if AVATAR_NAME.fullmatch(old_filename) and old_filename != filename:
            (avatar_directory / old_filename).unlink(missing_ok=True)

    return updated_user


@router.get("/avatars/{filename}", include_in_schema=False)
async def get_avatar(filename: str):
    if not AVATAR_NAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="头像不存在")

    path = Path(get_settings().storage_root) / "avatars" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="头像不存在")

    return FileResponse(
        path,
        media_type=AVATAR_MEDIA_TYPES[path.suffix],
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
