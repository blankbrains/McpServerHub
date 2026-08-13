"""通知 API — 站内通知中心。"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.core.alerts import (
    alert_preferences_payload,
    alert_rule_definition,
    evaluate_user_alerts_safely,
)
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import AlertPreferenceModel, NotificationModel
from mcp_hub.logging_config import get_logger

router = APIRouter(tags=["notifications"])
logger = get_logger(__name__)


class AlertPreferenceUpdate(BaseModel):
    """User-controlled alert switch and threshold."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    threshold: float = Field(ge=0)


@router.get("/notifications")
async def list_notifications(
    user_id: str = Depends(get_current_user),
    unread_only: bool = Query(True),
    status: Literal["all", "active", "resolved", "suppressed"] = Query("active"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """获取当前用户的通知列表（未读优先）。"""
    await evaluate_user_alerts_safely(user_id)
    async with async_session_factory() as session:
        stmt = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if unread_only:
            stmt = stmt.where(NotificationModel.is_read == False)  # noqa: E712
        if status != "all":
            stmt = stmt.where(NotificationModel.status == status)

        # 总数（使用 SQL COUNT，避免全量加载）
        total_stmt = select(func.count()).select_from(NotificationModel).where(
            NotificationModel.user_id == user_id
        )
        if unread_only:
            total_stmt = total_stmt.where(NotificationModel.is_read == False)  # noqa: E712
        if status != "all":
            total_stmt = total_stmt.where(NotificationModel.status == status)
        total_result = await session.execute(total_stmt)
        unread_result = await session.execute(
            select(func.count())
            .select_from(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.is_read == False,  # noqa: E712
                NotificationModel.status == "active",
            )
        )
        total = total_result.scalar() or 0
        unread_count = unread_result.scalar() or 0

        stmt = stmt.order_by(NotificationModel.is_read.asc(), NotificationModel.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        items: list[dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "id": r.id,
                    "type": r.type,
                    "title": r.title,
                    "message": r.message,
                    "server_id": r.server_id,
                    "link": r.link,
                    "is_read": r.is_read,
                    "alert_rule": r.alert_rule or "",
                    "severity": r.severity or "warning",
                    "status": r.status or "active",
                    "occurrence_count": int(r.occurrence_count or 1),
                    "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else "",
                    "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else "",
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else "",
                    "observed_value": r.observed_value or "",
                    "created_at": str(r.created_at) if r.created_at else "",
                }
            )

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


@router.get("/notifications/settings")
async def get_notification_settings(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Return effective alert settings for the current user."""
    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(AlertPreferenceModel).where(
                        AlertPreferenceModel.user_id == user_id
                    )
                )
            ).scalars()
        )
    return {
        "success": True,
        "data": {"rules": alert_preferences_payload({row.rule: row for row in rows})},
    }


@router.patch("/notifications/settings/{rule}")
async def update_notification_setting(
    rule: str,
    data: AlertPreferenceUpdate,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Update one user-scoped alert setting and reconcile its current state."""
    try:
        definition = alert_rule_definition(rule)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not definition.minimum_threshold <= data.threshold <= definition.maximum_threshold:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{rule} 阈值必须在 {definition.minimum_threshold:g} 至 "
                f"{definition.maximum_threshold:g} {definition.unit}之间"
            ),
        )
    async with async_session_factory() as session:
        preference = await session.scalar(
            select(AlertPreferenceModel).where(
                AlertPreferenceModel.user_id == user_id,
                AlertPreferenceModel.rule == rule,
            )
        )
        if preference is None:
            preference = AlertPreferenceModel(
                user_id=user_id,
                rule=rule,
                enabled=data.enabled,
                threshold=data.threshold,
            )
            session.add(preference)
        else:
            preference.enabled = data.enabled
            preference.threshold = data.threshold
        await session.commit()
    await evaluate_user_alerts_safely(user_id)
    return {
        "success": True,
        "data": {
            "rule": rule,
            "enabled": data.enabled,
            "threshold": data.threshold,
        },
    }


@router.post("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: int,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """标记单条通知为已读。"""
    async with async_session_factory() as session:
        await session.execute(
            update(NotificationModel)
            .where(NotificationModel.id == notif_id, NotificationModel.user_id == user_id)
            .values(is_read=True)
        )
        await session.commit()
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_read(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """标记所有通知为已读。"""
    async with async_session_factory() as session:
        await session.execute(
            update(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        await session.commit()
    return {"success": True}


@router.delete("/notifications/{notif_id}")
async def delete_notification(
    notif_id: int,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """删除普通通知，或忽略当前活动告警直到其恢复。"""
    async with async_session_factory() as session:
        notification = await session.scalar(
            select(NotificationModel).where(
                NotificationModel.id == notif_id,
                NotificationModel.user_id == user_id,
            )
        )
        if notification is None:
            raise HTTPException(status_code=404, detail="通知不存在")
        if notification.type == "alert" and notification.status == "active":
            notification.status = "suppressed"
            notification.is_read = True
            await session.commit()
            return {
                "success": True,
                "data": {"dismissed": True},
                "message": "告警已忽略，恢复后才会再次提醒",
            }
        await session.delete(notification)
        await session.commit()
    return {"success": True, "message": "通知已删除"}


@router.get("/notifications/unread-count")
async def unread_count(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """获取未读通知数量（供导航栏铃铛使用）。"""
    await evaluate_user_alerts_safely(user_id)
    async with async_session_factory() as session:
        count = (
            await session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.user_id == user_id,
                    NotificationModel.is_read == False,  # noqa: E712
                    NotificationModel.status == "active",
                )
            )
        ) or 0
    return {"success": True, "data": {"count": count}}


async def create_notification(
    user_id: str,
    notif_type: str,
    title: str,
    message: str = "",
    server_id: str = "",
    link: str = "",
) -> None:
    """内部函数：创建一条通知。不抛异常。"""
    try:
        async with async_session_factory() as session:
            session.add(
                NotificationModel(
                    user_id=user_id,
                    type=notif_type,
                    title=title,
                    message=message,
                    server_id=server_id,
                    link=link,
                    status="active",
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning("notif.create_failed", user_id=user_id, error=str(e))
