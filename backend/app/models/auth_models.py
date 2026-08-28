"""Pydantic models for the auth / user-management API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

ROLES = ("user", "superadmin")


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str = ""
    email: str = ""
    role: str = "user"
    is_active: bool = True
    must_change_password: bool = False
    created_at: str = ""
    last_login_at: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(default="", max_length=128)
    email: str = Field(default="", max_length=254)
    role: str = Field(default="user", pattern="^(user|superadmin)$")
    password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = False


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(user|superadmin)$")
    is_active: Optional[bool] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0
    role: str
    username: str
    display_name: str = ""
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    detail: str
