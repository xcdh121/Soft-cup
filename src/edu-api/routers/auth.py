"""Self-hosted username/password authentication endpoints."""

from auth import get_current_user
from config import get_settings
from default_courses import ensure_default_courses
from edu_core.schemas.users import UserDto
from edu_core.services import BillingService, UserService
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from security import (
    create_access_token,
    hash_password,
    normalize_username,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
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
