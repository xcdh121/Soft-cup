from datetime import datetime

from pydantic import BaseModel, Field


class UserDto(BaseModel):
    id: str = Field(..., description="Unique ID of the user")
    username: str = Field(..., description="Unique account name used to sign in")
    name: str | None = Field(None, description="Name of the user")
    email: str | None = Field(None, description="Email of the user")
    avatar_url: str | None = Field(None, description="URL of the user's avatar")
    is_active: bool = Field(True, description="Whether the account can sign in")
    is_admin: bool = Field(False, description="Whether the account is an administrator")
    created_at: datetime = Field(..., description="Date and time the user was created")
    updated_at: datetime = Field(..., description="Date and time the user was updated")

    model_config = {"from_attributes": True}
