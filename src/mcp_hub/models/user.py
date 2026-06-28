"""用户数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

UserRole = Literal["user", "publisher", "admin"]


class User(BaseModel):
    id: str  # GitHub username
    display_name: str = ""
    avatar_url: str = ""
    github_id: str = ""
    email: str = ""
    role: UserRole = "user"
    created_at: str = ""
    last_login: str = ""


class UserCreate(BaseModel):
    code: str  # GitHub OAuth code
