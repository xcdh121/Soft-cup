"""FastAPI dependencies for self-hosted JWT authentication."""

import jwt
from config import get_settings
from edu_core.exceptions import NotFoundError
from edu_core.schemas.users import UserDto
from edu_core.services import UserService
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


def _auth_secret() -> str:
    secret = get_settings().auth_jwt_secret
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_JWT_SECRET must be configured with at least 32 characters",
        )
    return secret


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserDto:
    """Validate an application-issued JWT and load its active user."""
    settings = get_settings()

    if settings.allow_dev_auth_bypass:
        return UserService().get_or_create_user_from_token(
            user_id="dev-local-user",
            username="dev-local-user",
            name="Local Dev User",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials, _auth_secret())
        user = UserService().get_user(str(payload["sub"]))
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, NotFoundError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(current_user: UserDto = Depends(get_current_user)) -> UserDto:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> UserDto | None:
    if get_settings().allow_dev_auth_bypass:
        return get_current_user(credentials)
    if not credentials:
        return None
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
