from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    register_number: str | None = Field(default=None, max_length=64)
    volunteer_activities: str | None = Field(default=None, max_length=3000)
    achievements: str | None = Field(default=None, max_length=3000)

    @field_validator("full_name")
    @classmethod
    def tidy_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("enter your full name")
        return cleaned

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password is too long")
        if value.isdigit() or value.isalpha():
            raise ValueError("use letters and numbers in your password")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime
    volunteer_activities: str | None = None
    achievements: str | None = None



class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
