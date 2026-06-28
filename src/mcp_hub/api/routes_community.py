"""社区 API。"""

from __future__ import annotations

from fastapi import APIRouter
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
async def rate_server(req: RateRequest):
    """评价 Server。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        result = await repo.rate(req.server_id, "api-user", req.rating, req.content)
    return {"success": True, "message": f"评分 {req.rating}⭐ 已提交", "data": result}


@router.get("/community/reviews/{server_id:path}")
async def get_reviews(server_id: str):
    """获取评价列表。"""
    async with get_session() as session:
        repo = ReviewRepository(session)
        reviews = await repo.get_reviews(server_id)
    return {"success": True, "data": reviews}


@router.post("/community/favorite")
async def favorite_server(req: FavoriteRequest):
    """收藏 Server。"""
    async with get_session() as session:
        repo = UserRepository(session)
        is_fav = await repo.favorite("api-user", req.server_id)
    return {"success": True, "favorited": is_fav}
