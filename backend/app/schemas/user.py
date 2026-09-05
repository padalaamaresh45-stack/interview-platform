from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=72)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
