"""评价数据模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Review(BaseModel):
    id: int = 0
    server_id: str
    user_id: str
    rating: int = Field(default=5, ge=1, le=5)
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


class ReviewCreate(BaseModel):
    server_id: str
    rating: int = Field(default=5, ge=1, le=5)
    content: str = ""
