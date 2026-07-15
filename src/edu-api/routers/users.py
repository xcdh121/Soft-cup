"""Router for user operations."""

from auth import get_current_user, require_admin
from dependencies import get_user_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.users import UserDto
from edu_core.services import UserService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from security import hash_password, normalize_username

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class AdminCreateUserRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return normalize_username(value)


@router.post("", response_model=UserDto, status_code=201)
async def create_user(
    payload: AdminCreateUserRequest,
    _current_user: UserDto = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    """Create a local account as an administrator."""
    try:
        return service.create_local_user(
            username=payload.username,
            password_hash=hash_password(payload.password),
            name=payload.name,
            is_admin=payload.is_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{user_id}", response_model=UserDto)
async def get_user(
    user_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Get a user by ID."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You can only view your own account")
    try:
        return service.get_user(user_id=user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[UserDto])
async def list_users(
    current_user: UserDto = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    """List all users."""
    try:
        return service.list_users()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    current_user: UserDto = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    """Delete a user."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Administrators cannot delete themselves")
    try:
        service.delete_user(user_id=user_id)
        return None
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
