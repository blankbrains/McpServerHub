"""社区 API — 评分 / 评价 / 收藏 / 删除评价。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.db.database import get_session
from mcp_hub.db.repositories import ReviewRepository, UserRepository

router = APIRouter(tags=["community"])


class RateRequest(BaseModel):
    server_id: str
    rating: int = Field(default=5, ge=1, le=5)
    content: str = ""
    parent_id: int | None = None


class FavoriteRequest(BaseModel):
    server_id: str


@router.post("/community/rate")
async def rate_server(
    req: RateRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """评价 Server。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        result = await repo.rate(req.server_id, user_id, req.rating, req.content, req.parent_id)
    return {"success": True, "message": f"评分 {req.rating} 星已提交", "data": result}


@router.get("/community/reviews/{server_id:path}")
async def get_reviews(server_id: str) -> dict[str, Any]:
    """获取评价列表。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        reviews = await repo.get_reviews(server_id)
    return {"success": True, "data": reviews}


@router.post("/community/review/delete/{review_id}")
async def delete_review(
    review_id: int,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """删除评价（仅评价作者可删除——服务器端验证）。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        result = await repo.delete_review(review_id, user_id, "user")
    return result


@router.post("/community/favorite")
async def favorite_server(
    req: FavoriteRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """收藏 Server。"""
    async with get_session() as session:
        repo = UserRepository(session)
        is_fav = await repo.favorite(user_id, req.server_id)
    return {"success": True, "favorited": is_fav}


@router.get("/community/favorites")
async def list_favorite_servers(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前用户收藏的 Server。"""
    async with get_session() as session:
        repo = UserRepository(session)
        servers = await repo.get_favorites(user_id)
    return {"success": True, "data": servers}
