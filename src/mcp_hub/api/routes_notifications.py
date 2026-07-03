"""通知 API — 站内通知中心。"""

from __future__ import annotations

from fastapi import APIRouter, Header
from sqlalchemy import func, select, update

from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import NotificationModel
from mcp_hub.logging_config import get_logger

router = APIRouter(tags=["notifications"])
logger = get_logger(__name__)


@router.get("/notifications")
async def list_notifications(
    x_user_id: str = Header("anonymous"),
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 50,
):
    """获取当前用户的通知列表（未读优先）。"""
    async with async_session_factory() as session:
        stmt = select(NotificationModel).where(
            NotificationModel.user_id == x_user_id
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.is_read == False)  # noqa: E712

        # 总数（使用 SQL COUNT，避免全量加载）
        total_result = await session.execute(
            select(func.count()).select_from(NotificationModel).where(
                NotificationModel.user_id == x_user_id
            )
        )
        unread_result = await session.execute(
            select(func.count()).select_from(NotificationModel).where(
                NotificationModel.user_id == x_user_id,
                NotificationModel.is_read == False,  # noqa: E712
            )
        )
        total = total_result.scalar() or 0
        unread_count = unread_result.scalar() or 0

        stmt = stmt.order_by(NotificationModel.is_read.asc(), NotificationModel.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "type": r.type,
                "title": r.title,
                "message": r.message,
                "server_id": r.server_id,
                "link": r.link,
                "is_read": r.is_read,
                "created_at": str(r.created_at) if r.created_at else "",
            })

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "unread_count": unread_count,
            "page": page,
            "page_size": page_size,
        },
    }


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: int, x_user_id: str = Header("anonymous")):
    """标记单条通知为已读。"""
    async with async_session_factory() as session:
        await session.execute(
            update(NotificationModel)
            .where(NotificationModel.id == notif_id, NotificationModel.user_id == x_user_id)
            .values(is_read=True)
        )
        await session.commit()
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_read(x_user_id: str = Header("anonymous")):
    """标记所有通知为已读。"""
    async with async_session_factory() as session:
        await session.execute(
            update(NotificationModel)
            .where(NotificationModel.user_id == x_user_id, NotificationModel.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        await session.commit()
    return {"success": True}


@router.get("/notifications/unread-count")
async def unread_count(x_user_id: str = Header("anonymous")):
    """获取未读通知数量（供导航栏铃铛使用）。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(NotificationModel).where(
                NotificationModel.user_id == x_user_id,
                NotificationModel.is_read == False,  # noqa: E712
            )
        )
        count = len(result.scalars().all())
    return {"success": True, "data": {"count": count}}


async def create_notification(
    user_id: str,
    notif_type: str,
    title: str,
    message: str = "",
    server_id: str = "",
    link: str = "",
):
    """内部函数：创建一条通知。不抛异常。"""
    try:
        async with async_session_factory() as session:
            session.add(NotificationModel(
                user_id=user_id,
                type=notif_type,
                title=title,
                message=message,
                server_id=server_id,
                link=link,
            ))
            await session.commit()
    except Exception as e:
        logger.warning("notif.create_failed", user_id=user_id, error=str(e))
