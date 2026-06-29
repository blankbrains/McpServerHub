"""社区 API — 评分 / 评价 / 收藏 / 删除评价。"""

from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from mcp_hub.db.database import get_session
from mcp_hub.db.repositories import ReviewRepository, UserRepository

router = APIRouter(tags=["community"])


class RateRequest(BaseModel):
    server_id: str
    rating: int = Field(default=5, ge=1, le=5)
    content: str = ""


class FavoriteRequest(BaseModel):
    server_id: str


@router.post("/community/rate")
async def rate_server(req: RateRequest, x_user_id: str = Header("api-user")):  # noqa: E501
    """评价 Server。
    已登录用户使用 GitHub ID，未登录使用 api-user。
    """
    async with get_session() as session:
        repo = ReviewRepository(session)
        result = await repo.rate(req.server_id, x_user_id, req.rating, req.content)
    return {"success": True, "message": f"评分 {req.rating} 星已提交", "data": result}


@router.get("/community/reviews/{server_id:path}")
async def get_reviews(server_id: str):
    """获取评价列表。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        reviews = await repo.get_reviews(server_id)
    return {"success": True, "data": reviews}


@router.post("/community/review/delete/{review_id}")
async def delete_review(review_id: int, x_user_id: str = Header("api-user"), x_user_role: str = Header("user")):  # noqa: E501
    """删除评价（仅评价作者、Server 发布者和管理员可删除）。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        result = await repo.delete_review(review_id, x_user_id, x_user_role)
    return result


@router.post("/community/favorite")
async def favorite_server(req: FavoriteRequest, x_user_id: str = Header("api-user")):
    """收藏 Server。"""
    async with get_session() as session:
        repo = UserRepository(session)
        is_fav = await repo.favorite(x_user_id, req.server_id)
    return {"success": True, "favorited": is_fav}
