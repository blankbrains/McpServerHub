"""管理后台 API — 平台运营者查看/管理用户、Server、调用数据。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import Response
from sqlalchemy import case, func, select, text, union_all
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from mcp_hub.api.dependencies import get_admin_user
from mcp_hub.core.user_validation import (
    VALIDATION_PARTICIPANT_ROLES,
    VALIDATION_STAGES,
)
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    FavoriteModel,
    NotificationModel,
    ReviewModel,
    ServerModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UsageStatsModel,
    UserModel,
    UserServerModel,
    UserValidationAssessmentModel,
    UserValidationEnrollmentModel,
    UserValidationEventModel,
)

router = APIRouter(tags=["admin"])


def _activity_since(days: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


def _activity_subquery() -> Subquery:
    """Unify current Gateway telemetry with legacy usage rows without double counting.

    Modern Gateway events also create a compatibility ``usage_stats`` row with
    ``source_event_id``. Those rows are excluded here because the telemetry
    event is the authoritative record. Older rows without that link remain
    visible until they age out.
    """
    return union_all(
        select(
            TelemetryEventModel.user_id.label("user_id"),
            TelemetryEventModel.server_id.label("server_id"),
            TelemetryEventModel.tool_name.label("tool_name"),
            TelemetryEventModel.status.label("status"),
            TelemetryEventModel.duration_ms.label("duration_ms"),
            (
                func.coalesce(TelemetryEventModel.input_tokens, 0)
                + func.coalesce(TelemetryEventModel.output_tokens, 0)
            ).label("token_count"),
            TelemetryEventModel.occurred_at.label("occurred_at"),
        ).where(TelemetryEventModel.event_type == "tool_call"),
        select(
            UsageStatsModel.user_id.label("user_id"),
            UsageStatsModel.server_id.label("server_id"),
            UsageStatsModel.tool_name.label("tool_name"),
            UsageStatsModel.status.label("status"),
            UsageStatsModel.duration_ms.label("duration_ms"),
            func.coalesce(UsageStatsModel.token_count, 0).label("token_count"),
            UsageStatsModel.created_at.label("occurred_at"),
        ).where(UsageStatsModel.source_event_id.is_(None)),
    ).subquery("activity")


def _activity_time_filter(activity: Subquery, days: int) -> ColumnElement[bool]:
    """Return a UTC window against the unified activity relation."""
    return activity.c.occurred_at >= _activity_since(days)


def _gateway_online_cutoff() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3)


def _category_filter(category: str) -> ColumnElement[bool]:
    """Match one exact string item in the JSON-encoded categories array."""
    escaped = (
        category.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace('"', '\\"')
    )
    return ServerModel.categories.ilike(f'%"{escaped}"%', escape="\\")


def _csv_cell(value: Any) -> str:
    """Prevent spreadsheet formula execution when exported CSV is opened."""
    text_value = "" if value is None else str(value)
    if text_value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text_value}"
    return text_value


# ── 审计日志 ──────────────────────────────────────────────


def _audit_record(user_id: str, action: str, detail: str = "") -> NotificationModel:
    return NotificationModel(
        user_id=user_id,
        type="audit",
        title=action,
        message=detail,
        is_read=True,
        status="resolved",
    )


# ── 1. 平台概览 ───────────────────────────────────────────


@router.get("/admin/overview")
async def admin_overview(
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:

    async with async_session_factory() as session:
        activity = _activity_subquery()
        activity_7d = _activity_time_filter(activity, 7)
        activity_30d = _activity_time_filter(activity, 30)

        # 基础统计
        total_users = (
            await session.execute(select(func.count()).select_from(UserModel))
        ).scalar() or 0
        total_servers = (
            await session.execute(select(func.count()).select_from(ServerModel))
        ).scalar() or 0
        total_installs = (
            await session.execute(select(func.count()).select_from(UserServerModel))
        ).scalar() or 0
        total_calls = (
            await session.execute(select(func.count()).select_from(activity))
        ).scalar() or 0
        total_tokens = (
            await session.execute(select(func.sum(activity.c.token_count)).select_from(activity))
        ).scalar() or 0
        active_users_7d = (
            await session.execute(
                select(func.count(func.distinct(activity.c.user_id)))
                .select_from(activity)
                .where(activity_7d)
            )
        ).scalar() or 0

        device_total = (
            await session.execute(select(func.count()).select_from(TelemetryDeviceModel))
        ).scalar() or 0
        online_devices = (
            await session.execute(
                select(func.count())
                .select_from(TelemetryDeviceModel)
                .where(
                    TelemetryDeviceModel.revoked_at.is_(None),
                    TelemetryDeviceModel.gateway_last_seen_at >= _gateway_online_cutoff(),
                )
            )
        ).scalar() or 0
        connected_devices = (
            await session.execute(
                select(func.count())
                .select_from(TelemetryDeviceModel)
                .where(
                    TelemetryDeviceModel.gateway_first_seen_at.is_not(None),
                )
            )
        ).scalar() or 0

        # 每日趋势
        date_func = func.date(activity.c.occurred_at)
        trend_result = await session.execute(
            select(
                date_func.label("day"),
                func.count().label("calls"),
                func.sum(activity.c.token_count).label("tokens"),
            )
            .select_from(activity)
            .where(activity_30d)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        daily_trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0}
            for r in trend_result.fetchall()
        ]

        # Top 10 活跃 Server：按统一活动口径的 7 日调用量排序。
        # 安装数单独通过子查询补充，避免把“安装最多”误称为“活跃最多”。
        install_counts = (
            select(
                UserServerModel.server_id,
                func.count().label("installs"),
            )
            .group_by(UserServerModel.server_id)
            .subquery("install_counts")
        )
        top_servers_result = await session.execute(
            select(
                activity.c.server_id,
                func.count().label("calls_7d"),
                func.coalesce(install_counts.c.installs, 0).label("installs"),
            )
            .select_from(activity)
            .outerjoin(install_counts, activity.c.server_id == install_counts.c.server_id)
            .where(activity_7d)
            .group_by(activity.c.server_id, install_counts.c.installs)
            .order_by(text("calls_7d DESC"))
            .limit(10)
        )
        top_servers = []
        for server_row in top_servers_result.fetchall():
            sid = server_row[0]
            srv = await session.execute(select(ServerModel.name).where(ServerModel.id == sid))
            srv_name = srv.scalar() or sid
            top_servers.append(
                {
                    "id": sid,
                    "name": srv_name,
                    "installs": server_row[2] or 0,
                    "calls_7d": server_row[1] or 0,
                }
            )

        # Top 10 用户
        top_users_result = await session.execute(
            select(
                activity.c.user_id,
                func.count().label("calls"),
                func.sum(activity.c.token_count).label("tokens"),
            )
            .select_from(activity)
            .where(activity_7d)
            .group_by(activity.c.user_id)
            .order_by(text("calls DESC"))
            .limit(10)
        )
        top_users = []
        for user_row in top_users_result.fetchall():
            uid = user_row[0]
            usr = await session.execute(select(UserModel.display_name).where(UserModel.id == uid))
            name = usr.scalar() or uid
            top_users.append(
                {
                    "user_id": uid,
                    "display_name": name,
                    "calls_7d": user_row[1] or 0,
                    "tokens_7d": user_row[2] or 0,
                }
            )

    return {
        "success": True,
        "data": {
            "stats": {
                "total_users": total_users,
                "total_servers": total_servers,
                "total_installs": total_installs,
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "active_users_7d": active_users_7d,
            "total_devices": int(device_total),
            "online_devices": int(online_devices),
            "connected_devices": int(connected_devices),
        },
            "daily_trend": daily_trend,
            "top_servers": top_servers,
            "top_users": top_users,
        },
    }


# ── 2. 用户列表 ───────────────────────────────────────────


@router.get("/admin/users")
async def admin_users(
    admin_user: str = Depends(get_admin_user),
    q: Annotated[str, Query(max_length=200)] = "",
    role: Annotated[str, Query(max_length=20)] = "",
    sort: Annotated[str, Query(max_length=20)] = "calls",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:

    async with async_session_factory() as session:
        if role not in ("", "user", "admin"):
            return {"success": False, "error": "role 必须是 user 或 admin"}
        if sort not in {"calls", "installs", "created"}:
            return {"success": False, "error": "sort 必须是 calls、installs 或 created"}
        activity = _activity_subquery()
        activity_7d = _activity_time_filter(activity, 7)

        # 子查询：7 日调用统计
        stats_sub = (
            select(
                activity.c.user_id,
                func.count().label("calls_7d"),
                func.sum(activity.c.token_count).label("tokens_7d"),
                func.max(activity.c.occurred_at).label("last_active"),
            )
            .select_from(activity)
            .where(activity_7d)
            .group_by(activity.c.user_id)
        ).alias("stats")

        # 总数
        count_stmt = select(func.count()).select_from(UserModel)
        if q:
            count_stmt = count_stmt.where(
                (UserModel.id.ilike(f"%{q}%")) | (UserModel.display_name.ilike(f"%{q}%"))
            )
        if role:
            count_stmt = count_stmt.where(UserModel.role == role)
        total = (await session.execute(count_stmt)).scalar() or 0

        # 主查询
        main_stmt = (
            select(
                UserModel.id,
                UserModel.display_name,
                UserModel.avatar_url,
                UserModel.role,
                UserModel.created_at,
                UserModel.last_login,
                func.count(func.distinct(UserServerModel.server_id)).label("server_count"),
                func.count(func.distinct(TelemetryDeviceModel.id)).label("device_count"),
                func.count(
                    func.distinct(
                        case(
                            (
                                TelemetryDeviceModel.revoked_at.is_(None)
                                & (
                                    TelemetryDeviceModel.gateway_last_seen_at
                                    >= _gateway_online_cutoff()
                                ),
                                TelemetryDeviceModel.id,
                            ),
                            else_=None,
                        )
                    )
                ).label("online_device_count"),
                func.coalesce(stats_sub.c.calls_7d, 0).label("calls_7d"),
                func.coalesce(stats_sub.c.tokens_7d, 0).label("tokens_7d"),
                func.coalesce(stats_sub.c.last_active, UserModel.last_login).label("last_active"),
            )
            .select_from(UserModel)
            .outerjoin(UserServerModel, UserModel.id == UserServerModel.user_id)
            .outerjoin(TelemetryDeviceModel, UserModel.id == TelemetryDeviceModel.user_id)
            .outerjoin(stats_sub, UserModel.id == stats_sub.c.user_id)
        )
        if q:
            main_stmt = main_stmt.where(
                (UserModel.id.ilike(f"%{q}%")) | (UserModel.display_name.ilike(f"%{q}%"))
            )
        if role:
            main_stmt = main_stmt.where(UserModel.role == role)
        main_stmt = main_stmt.group_by(
            UserModel.id,
            UserModel.display_name,
            UserModel.avatar_url,
            UserModel.role,
            UserModel.created_at,
            UserModel.last_login,
            stats_sub.c.calls_7d,
            stats_sub.c.tokens_7d,
            stats_sub.c.last_active,
        )

        # 排序
        if sort == "installs":
            main_stmt = main_stmt.order_by(text("server_count DESC"))
        elif sort == "created":
            main_stmt = main_stmt.order_by(UserModel.created_at.desc())
        else:
            main_stmt = main_stmt.order_by(text("calls_7d DESC"))

        main_stmt = main_stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(main_stmt)
        rows = result.fetchall()

        users = []
        for r in rows:
            users.append(
                {
                    "user_id": r[0],
                    "display_name": r[1] or r[0],
                    "avatar_url": r[2] or "",
                    "role": r[3] or "user",
                    "created_at": str(r[4]) if r[4] else "",
                    "last_login": str(r[5]) if r[5] else "",
                    "server_count": r[6] or 0,
                    "device_count": r[7] or 0,
                    "online_device_count": r[8] or 0,
                    "calls_7d": r[9] or 0,
                    "tokens_7d": r[10] or 0,
                    "last_active": str(r[11]) if r[11] else "",
                }
            )

    return {
        "success": True,
        "data": users,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── 3. 用户详情 ───────────────────────────────────────────


@router.get("/admin/users/{user_id}")
async def admin_user_detail(
    user_id: str,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:

    async with async_session_factory() as session:
        activity = _activity_subquery()
        activity_7d = _activity_time_filter(activity, 7)
        activity_30d = _activity_time_filter(activity, 30)

        # 用户基本信息
        usr_result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        usr = usr_result.scalar_one_or_none()
        if not usr:
            return {"success": False, "error": "用户不存在"}

        profile = {
            "id": usr.id,
            "display_name": usr.display_name or usr.id,
            "avatar_url": usr.avatar_url or "",
            "email": usr.email or "",
            "role": usr.role or "user",
            "created_at": str(usr.created_at) if usr.created_at else "",
            "last_login": str(usr.last_login) if usr.last_login else "",
        }

        # 统计
        srv_count = (
            await session.execute(
                select(func.count())
                .select_from(UserServerModel)
                .where(UserServerModel.user_id == user_id)
            )
        ).scalar() or 0
        total_calls = (
            await session.execute(
                select(func.count())
                .select_from(activity)
                .where(activity.c.user_id == user_id)
            )
        ).scalar() or 0
        total_tokens = (
            await session.execute(
                select(func.sum(activity.c.token_count))
                .select_from(activity)
                .where(activity.c.user_id == user_id)
            )
        ).scalar() or 0
        fav_count = (
            await session.execute(
                select(func.count())
                .select_from(FavoriteModel)
                .where(FavoriteModel.user_id == user_id)
            )
        ).scalar() or 0

        device_result = await session.execute(
            select(TelemetryDeviceModel)
            .where(TelemetryDeviceModel.user_id == user_id)
            .order_by(TelemetryDeviceModel.created_at.desc())
        )
        device_rows = list(device_result.scalars())
        inventory_counts = await session.execute(
            select(
                TelemetryInventoryModel.device_id,
                func.count().label("server_count"),
            )
            .where(
                TelemetryInventoryModel.user_id == user_id,
                TelemetryInventoryModel.active == True,  # noqa: E712
            )
            .group_by(TelemetryInventoryModel.device_id)
        )
        inventory_by_device = {
            row.device_id: int(row.server_count or 0)
            for row in inventory_counts.fetchall()
        }
        online_cutoff = _gateway_online_cutoff()
        devices = [
            {
                "id": device.id,
                "name": device.name,
                "agent_type": device.agent_type,
                "gateway_version": device.gateway_version or "",
                "platform": device.platform or "",
                "online": bool(
                    device.revoked_at is None
                    and device.gateway_last_seen_at is not None
                    and device.gateway_last_seen_at >= online_cutoff
                ),
                "connected": device.gateway_first_seen_at is not None,
                "revoked": device.revoked_at is not None,
                "last_seen_at": (
                    device.gateway_last_seen_at.isoformat()
                    if device.gateway_last_seen_at
                    else None
                ),
                "first_call_at": (
                    device.first_call_at.isoformat() if device.first_call_at else None
                ),
                "server_count": inventory_by_device.get(device.id, 0),
            }
            for device in device_rows
        ]

        # Server 列表
        srv_result = await session.execute(
            select(UserServerModel.server_id, UserServerModel.enabled)
            .where(UserServerModel.user_id == user_id)
            .limit(20)
        )
        servers = []
        for row in srv_result.fetchall():
            sid = row[0]
            srv_calls = (
                await session.execute(
                    select(func.count())
                    .select_from(activity)
                    .where(
                        activity.c.server_id == sid,
                        activity.c.user_id == user_id,
                        activity_7d,
                    )
                )
            ).scalar() or 0
            srv_tokens = (
                await session.execute(
                    select(func.sum(activity.c.token_count))
                    .select_from(activity)
                    .where(
                        activity.c.server_id == sid,
                        activity.c.user_id == user_id,
                        activity_7d,
                    )
                )
            ).scalar() or 0
            servers.append(
                {
                    "server_id": sid,
                    "name": sid.split("/")[-1],
                    "calls_7d": srv_calls,
                    "tokens_7d": srv_tokens or 0,
                    "enabled": row[1] if row[1] is not None else True,
                }
            )

        # 每日趋势
        date_func = func.date(activity.c.occurred_at)
        trend_result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(activity.c.token_count))
            .select_from(activity)
            .where(activity.c.user_id == user_id, activity_30d)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        daily_trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0}
            for r in trend_result.fetchall()
        ]

        # Top 5 工具
        tools_result = await session.execute(
            select(activity.c.tool_name, func.count().label("cnt"))
            .select_from(activity)
            .where(activity.c.user_id == user_id, activity_30d)
            .group_by(activity.c.tool_name)
            .order_by(text("cnt DESC"))
            .limit(5)
        )
        top_tools = [
            {"tool_name": r[0] or "unknown", "count": r[1]} for r in tools_result.fetchall()
        ]

    return {
        "success": True,
        "data": {
            "profile": profile,
            "stats": {
                "server_count": srv_count,
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "favorite_count": fav_count,
                "device_count": len(devices),
                "online_device_count": sum(1 for device in devices if device["online"]),
                "connected_device_count": sum(1 for device in devices if device["connected"]),
            },
            "devices": devices,
            "servers": servers,
            "daily_trend": daily_trend,
            "top_tools": top_tools,
        },
    }


# ── 4. 用户 Server 列表 ────────────────────────────────────


@router.get("/admin/users/{user_id}/servers")
async def admin_user_servers(
    user_id: str,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel).where(UserServerModel.user_id == user_id).limit(50)
        )
        servers = []
        for row in result.scalars().all():
            srv = await session.execute(
                select(ServerModel.name).where(ServerModel.id == row.server_id)
            )
            servers.append(
                {
                    "server_id": row.server_id,
                    "name": srv.scalar() or row.server_id,
                    "enabled": row.enabled if row.enabled is not None else True,
                    "agent": row.agent or "",
                }
            )
    return {"success": True, "data": servers}


# ── 5. 用户每日趋势 ───────────────────────────────────────


@router.get("/admin/users/{user_id}/usage/daily")
async def admin_user_daily(
    user_id: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        activity = _activity_subquery()
        time_f = _activity_time_filter(activity, days)
        date_func = func.date(activity.c.occurred_at)
        result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(activity.c.token_count))
            .select_from(activity)
            .where(activity.c.user_id == user_id, time_f)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0} for r in result.fetchall()
        ]
    return {"success": True, "data": trend}


# ── 6. 修改角色 ───────────────────────────────────────────


@router.patch("/admin/users/{user_id}/role")
async def admin_update_role(
    user_id: str,
    data: dict[str, Any] = Body(...),
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    role = data.get("role", "")
    if role not in ("user", "admin"):
        return {"success": False, "error": "角色只能是 user 或 admin"}

    async with async_session_factory() as session:
        admin_result = await session.execute(
            select(UserModel)
            .where(UserModel.role == "admin")
            .order_by(UserModel.id)
            .with_for_update()
        )
        administrators = list(admin_result.scalars())
        target_user = next((user for user in administrators if user.id == user_id), None)
        if target_user is None:
            target_user = await session.scalar(
                select(UserModel).where(UserModel.id == user_id).with_for_update()
            )
        if not target_user:
            return {"success": False, "error": "用户不存在"}
        if user_id == admin_user and role != "admin":
            return {"success": False, "error": "不能降级当前登录的管理员账号"}
        if target_user.role == "admin" and role == "user" and len(administrators) <= 1:
            return {"success": False, "error": "平台至少需要保留一名管理员"}
        target_user.role = role
        session.add(_audit_record(admin_user, f"修改用户角色: {user_id} → {role}"))
        await session.commit()

    return {"success": True, "message": f"已将 {user_id} 的角色修改为 {role}"}


# ── 7. Server 列表 ────────────────────────────────────────


@router.get("/admin/servers")
async def admin_servers(
    admin_user: str = Depends(get_admin_user),
    q: Annotated[str, Query(max_length=200)] = "",
    category: Annotated[str, Query(max_length=100)] = "",
    security_level: Annotated[str, Query(max_length=20)] = "",
    sort: Annotated[str, Query(max_length=20)] = "installs",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:

    async with async_session_factory() as session:
        if security_level not in ("", "verified", "reviewed", "unreviewed", "blocked"):
            return {"success": False, "error": "无效的安全等级"}
        if sort not in {"installs", "calls", "rating"}:
            return {"success": False, "error": "sort 必须是 installs、calls 或 rating"}
        activity = _activity_subquery()
        activity_7d = _activity_time_filter(activity, 7)
        install_counts = (
            select(
                UserServerModel.server_id.label("server_id"),
                func.count().label("install_count"),
            )
            .group_by(UserServerModel.server_id)
            .subquery("install_counts")
        )
        calls_subquery = (
            select(
                activity.c.server_id.label("server_id"),
                func.count().label("calls_7d"),
            )
            .select_from(activity)
            .where(activity_7d)
            .group_by(activity.c.server_id)
            .subquery()
        )

        count_stmt = select(func.count()).select_from(ServerModel)
        if q:
            count_stmt = count_stmt.where(
                (ServerModel.id.ilike(f"%{q}%")) | (ServerModel.name.ilike(f"%{q}%"))
            )
        if category:
            count_stmt = count_stmt.where(_category_filter(category))
        if security_level:
            count_stmt = count_stmt.where(ServerModel.security_level == security_level)
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(ServerModel)
            .outerjoin(calls_subquery, calls_subquery.c.server_id == ServerModel.id)
            .outerjoin(install_counts, install_counts.c.server_id == ServerModel.id)
        )
        if q:
            stmt = stmt.where((ServerModel.id.ilike(f"%{q}%")) | (ServerModel.name.ilike(f"%{q}%")))
        if category:
            stmt = stmt.where(_category_filter(category))
        if security_level:
            stmt = stmt.where(ServerModel.security_level == security_level)

        if sort == "rating":
            stmt = stmt.order_by(ServerModel.rating.desc())
        elif sort == "calls":
            stmt = stmt.order_by(func.coalesce(calls_subquery.c.calls_7d, 0).desc())
        else:
            stmt = stmt.order_by(func.coalesce(install_counts.c.install_count, 0).desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        servers = []
        for s in rows:
            install_count = (
                await session.execute(
                    select(func.count())
                    .select_from(UserServerModel)
                    .where(UserServerModel.server_id == s.id)
                )
            ).scalar() or 0
            calls_7d = (
                await session.execute(
                    select(func.count())
                    .select_from(activity)
                    .where(activity.c.server_id == s.id, activity_7d)
                )
            ).scalar() or 0
            tokens_7d = (
                await session.execute(
                    select(func.sum(activity.c.token_count))
                    .select_from(activity)
                    .where(activity.c.server_id == s.id, activity_7d)
                )
            ).scalar() or 0
            import json

            try:
                cats = json.loads(s.categories) if s.categories else []
            except Exception:
                cats = []
            servers.append(
                {
                    "server_id": s.id,
                    "name": s.name or s.id,
                    "categories": cats,
                    "install_count": install_count,
                    "calls_7d": calls_7d,
                    "tokens_7d": tokens_7d or 0,
                    "rating": s.rating or 0,
                    "security_level": s.security_level or "unreviewed",
                    "market_visible": s.market_visible is not False,
                    "download_count": s.download_count or 0,
                }
            )

    return {
        "success": True,
        "data": servers,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── 8-10. Server 详情 + 用户 + 趋势 ────────────────────────


async def admin_server_detail(
    server_id: str,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        srv = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        s = srv.scalar_one_or_none()
        if not s:
            return {"success": False, "error": "Server 不存在"}

        activity = _activity_subquery()
        activity_7d = _activity_time_filter(activity, 7)
        activity_30d = _activity_time_filter(activity, 30)

        install_count = (
            await session.execute(
                select(func.count())
                .select_from(UserServerModel)
                .where(UserServerModel.server_id == server_id)
            )
        ).scalar() or 0
        calls_7d = (
            await session.execute(
                select(func.count())
                .select_from(activity)
                .where(activity.c.server_id == server_id, activity_7d)
            )
        ).scalar() or 0
        tokens_7d = (
            await session.execute(
                select(func.sum(activity.c.token_count))
                .select_from(activity)
                .where(activity.c.server_id == server_id, activity_7d)
            )
        ).scalar() or 0

        import json

        try:
            cats = json.loads(s.categories) if s.categories else []
        except Exception:
            cats = []

        # 安装用户
        users_result = await session.execute(
            select(UserServerModel.user_id).where(UserServerModel.server_id == server_id).limit(20)
        )
        install_users = []
        for row in users_result.fetchall():
            uid = row[0]
            usr = await session.execute(select(UserModel.display_name).where(UserModel.id == uid))
            uc = (
                await session.execute(
                    select(func.count())
                    .select_from(activity)
                    .where(
                        activity.c.server_id == server_id,
                        activity.c.user_id == uid,
                        activity_7d,
                    )
                )
            ).scalar() or 0
            install_users.append(
                {"user_id": uid, "display_name": usr.scalar() or uid, "calls_7d": uc}
            )

        # 趋势
        date_func = func.date(activity.c.occurred_at)
        trend_result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(activity.c.token_count))
            .select_from(activity)
            .where(activity.c.server_id == server_id, activity_30d)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        daily_trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0}
            for r in trend_result.fetchall()
        ]

        # Top 5 工具
        tools_result = await session.execute(
            select(activity.c.tool_name, func.count().label("cnt"))
            .select_from(activity)
            .where(activity.c.server_id == server_id, activity_30d)
            .group_by(activity.c.tool_name)
            .order_by(text("cnt DESC"))
            .limit(5)
        )
        top_tools = [
            {"tool_name": r[0] or "unknown", "count": r[1]} for r in tools_result.fetchall()
        ]

    return {
        "success": True,
        "data": {
            "server": {
                "server_id": s.id,
                "name": s.name or s.id,
                "description": s.description or "",
                "categories": cats,
                "rating": s.rating or 0,
                "security_level": s.security_level or "unreviewed",
                "market_visible": s.market_visible is not False,
                "download_count": s.download_count or 0,
                "version": s.current_version or "",
                "homepage": s.homepage or "",
                "author": s.author or "",
            },
            "stats": {
                "install_count": install_count,
                "calls_7d": calls_7d,
                "tokens_7d": tokens_7d or 0,
            },
            "install_users": install_users,
            "daily_trend": daily_trend,
            "top_tools": top_tools,
        },
    }


@router.get("/admin/servers/{server_id:path}/users")
async def admin_server_users(
    server_id: str,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel).where(UserServerModel.server_id == server_id).limit(50)
        )
        users = []
        for row in result.scalars().all():
            usr = await session.execute(
                select(UserModel.display_name).where(UserModel.id == row.user_id)
            )
            users.append(
                {
                    "user_id": row.user_id,
                    "display_name": usr.scalar() or row.user_id,
                    "enabled": row.enabled if row.enabled is not None else True,
                }
            )
    return {"success": True, "data": users}


@router.get("/admin/servers/{server_id:path}/usage/daily")
async def admin_server_daily(
    server_id: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        activity = _activity_subquery()
        time_f = _activity_time_filter(activity, days)
        date_func = func.date(activity.c.occurred_at)
        result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(activity.c.token_count))
            .select_from(activity)
            .where(activity.c.server_id == server_id, time_f)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0} for r in result.fetchall()
        ]
    return {"success": True, "data": trend}


# 注册通用详情路由时必须晚于上面的 /users 和 /usage/daily，
# 否则 path 转换器会抢先吞掉这些更具体的 GET 路径。
router.get("/admin/servers/{server_id:path}")(admin_server_detail)


# ── 11-13. 使用分析 ───────────────────────────────────────


@router.get("/admin/analytics/daily")
async def admin_analytics_daily(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        activity = _activity_subquery()
        time_f = _activity_time_filter(activity, days)
        date_func = func.date(activity.c.occurred_at)
        result = await session.execute(
            select(
                date_func.label("day"),
                func.count().label("calls"),
                func.sum(activity.c.token_count).label("tokens"),
                func.count(func.distinct(activity.c.user_id)).label("users"),
                func.count(func.distinct(activity.c.server_id)).label("servers"),
            )
            .select_from(activity)
            .where(time_f)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        trend = [
            {
                "date": str(r[0]),
                "calls": r[1] or 0,
                "tokens": r[2] or 0,
                "active_users": r[3] or 0,
                "active_servers": r[4] or 0,
            }
            for r in result.fetchall()
        ]
    return {"success": True, "data": trend}


@router.get("/admin/analytics/user-validation")
async def admin_user_validation_analytics(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """Return aggregate opt-in study progress without participant identities."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    async with async_session_factory() as session:
        enrollments_result = await session.execute(
            select(
                UserValidationEnrollmentModel.user_id,
                UserValidationEnrollmentModel.participant_role,
            ).where(UserValidationEnrollmentModel.enrolled_at >= since)
        )
        enrollments = list(enrollments_result)
        cohort_user_ids = {user_id for user_id, _role in enrollments}
        event_result = await session.execute(
            select(
                UserValidationEventModel.user_id,
                UserValidationEventModel.stage,
                UserValidationEventModel.occurred_at,
            ).where(
                UserValidationEventModel.occurred_at >= since,
                UserValidationEventModel.user_id.in_(cohort_user_ids),
            )
        )
        event_rows = list(event_result)
        assessment_result = await session.execute(
            select(
                UserValidationAssessmentModel.connection_state_understood,
                UserValidationAssessmentModel.verify_without_logs,
                UserValidationAssessmentModel.recovery_succeeded,
            ).where(
                UserValidationAssessmentModel.user_id.in_(cohort_user_ids),
                UserValidationAssessmentModel.updated_at >= since,
            )
        )
        assessments = list(assessment_result)

    participants_by_role = {
        role: sum(1 for _user_id, participant_role in enrollments if participant_role == role)
        for role in VALIDATION_PARTICIPANT_ROLES
    }
    participants_by_stage: dict[str, set[str]] = {
        stage: set() for stage in VALIDATION_STAGES
    }
    milestones: dict[str, dict[str, datetime]] = {}
    for user_id, stage, occurred_at in event_rows:
        if stage not in participants_by_stage:
            continue
        participants_by_stage[stage].add(user_id)
        milestones.setdefault(user_id, {}).setdefault(stage, occurred_at)

    first_call_minutes = [
        (values["first_tool_call"] - values["device_created"]).total_seconds() / 60
        for values in milestones.values()
        if "device_created" in values
        and "first_tool_call" in values
        and values["first_tool_call"] >= values["device_created"]
    ]
    first_call_minutes.sort()
    midpoint = len(first_call_minutes) // 2
    median_first_call_minutes: float | None
    if not first_call_minutes:
        median_first_call_minutes = None
    elif len(first_call_minutes) % 2:
        median_first_call_minutes = round(first_call_minutes[midpoint], 1)
    else:
        median_first_call_minutes = round(
            (first_call_minutes[midpoint - 1] + first_call_minutes[midpoint]) / 2,
            1,
        )

    def positive_rate(column: int) -> dict[str, int | float]:
        values = [
            assessment[column]
            for assessment in assessments
            if assessment[column] is not None
        ]
        yes_count = sum(1 for value in values if value)
        return {
            "responses": len(values),
            "yes": yes_count,
            "rate": round(yes_count / len(values) * 100, 1) if values else 0,
        }

    return {
        "success": True,
        "data": {
            "days": days,
            "participants": {
                "total": len(enrollments),
                "by_role": participants_by_role,
                "targets": {
                    "individual_user": 5,
                    "server_publisher": 2,
                    "team_admin": 2,
                },
            },
            "stages": {
                stage: len(participants_by_stage[stage]) for stage in VALIDATION_STAGES
            },
            "metrics": {
                "first_call_median_minutes": median_first_call_minutes,
                "connection_state_understood": positive_rate(0),
                "verify_without_logs": positive_rate(1),
                "recovery_succeeded": positive_rate(2),
            },
        },
    }


@router.get("/admin/analytics/top-servers")
async def admin_top_servers(
    metric: Annotated[str, Query(max_length=20)] = "calls",
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        if metric not in {"calls", "tokens", "installs"}:
            return {"success": False, "error": "metric 必须是 calls、tokens 或 installs"}

        ranked_rows: list[tuple[str, int, int, int]] = []
        if metric == "installs":
            install_since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            result = await session.execute(
                select(
                    UserServerModel.server_id,
                    func.count().label("installs"),
                )
                .where(UserServerModel.created_at >= install_since)
                .group_by(UserServerModel.server_id)
                .order_by(func.count().desc())
                .limit(limit)
            )
            for row in result.fetchall():
                ranked_rows.append((row[0], 0, 0, int(row[1] or 0)))
        else:
            activity = _activity_subquery()
            time_f = _activity_time_filter(activity, days)
            order_col: ColumnElement[Any] = (
                func.sum(activity.c.token_count)
                if metric == "tokens"
                else func.count()
            )
            result = await session.execute(
                select(
                    activity.c.server_id,
                    func.count().label("calls"),
                    func.sum(activity.c.token_count).label("tokens"),
                )
                .select_from(activity)
                .where(time_f)
                .group_by(activity.c.server_id)
                .order_by(order_col.desc())
                .limit(limit)
            )
            ranked_rows.extend(
                (row[0], int(row[1] or 0), int(row[2] or 0), 0)
                for row in result.fetchall()
            )

        servers: list[dict[str, Any]] = []
        for sid, calls, tokens, installs in ranked_rows:
            srv = await session.execute(select(ServerModel.name).where(ServerModel.id == sid))
            servers.append(
                {
                    "server_id": sid,
                    "name": srv.scalar() or sid,
                    "calls": calls,
                    "tokens": tokens,
                    "installs": installs,
                }
            )
    return {"success": True, "data": servers}


@router.get("/admin/analytics/top-users")
async def admin_top_users(
    metric: Annotated[str, Query(max_length=20)] = "calls",
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        if metric not in {"calls", "tokens"}:
            return {"success": False, "error": "metric 必须是 calls 或 tokens"}
        activity = _activity_subquery()
        time_f = _activity_time_filter(activity, days)
        order_col: ColumnElement[Any] = (
            func.sum(activity.c.token_count)
            if metric == "tokens"
            else func.count()
        )

        result = await session.execute(
            select(
                activity.c.user_id,
                func.count().label("calls"),
                func.sum(activity.c.token_count).label("tokens"),
            )
            .select_from(activity)
            .where(time_f)
            .group_by(activity.c.user_id)
            .order_by(order_col.desc())
            .limit(limit)
        )
        users = []
        for row in result.fetchall():
            uid = row[0]
            usr = await session.execute(select(UserModel.display_name).where(UserModel.id == uid))
            users.append(
                {
                    "user_id": uid,
                    "display_name": usr.scalar() or uid,
                    "calls": row[1] or 0,
                    "tokens": row[2] or 0,
                }
            )
    return {"success": True, "data": users}


# ── 14. 评价审核 ──────────────────────────────────────────


@router.get("/admin/reviews")
async def admin_reviews(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        count_result = await session.execute(select(func.count()).select_from(ReviewModel))
        total = count_result.scalar() or 0

        result = await session.execute(
            select(ReviewModel)
            .order_by(ReviewModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        reviews = []
        for r in result.scalars().all():
            srv = await session.execute(
                select(ServerModel.name).where(ServerModel.id == r.server_id)
            )
            reviews.append(
                {
                    "id": r.id,
                    "server_id": r.server_id,
                    "server_name": srv.scalar() or r.server_id,
                    "user_id": r.user_id,
                    "rating": r.rating,
                    "content": (r.content or "")[:200],
                    "created_at": str(r.created_at) if r.created_at else "",
                }
            )

    return {
        "success": True,
        "data": reviews,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.delete("/admin/reviews/{review_id}")
async def admin_delete_review(
    review_id: int,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        r = await session.execute(select(ReviewModel).where(ReviewModel.id == review_id))
        review = r.scalar_one_or_none()
        if not review:
            return {"success": False, "error": "评价不存在"}
        await session.delete(review)
        session.add(
            _audit_record(
                admin_user,
                f"删除评价 #{review_id}",
                f"server={review.server_id} user={review.user_id}",
            )
        )
        await session.commit()

    return {"success": True, "message": "评价已删除"}


# ── 审计日志 ──────────────────────────────────────────────


@router.get("/admin/audit")
async def admin_audit_log(
    action_type: Annotated[str, Query(max_length=100)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    async with async_session_factory() as session:
        count_stmt = (
            select(func.count())
            .select_from(NotificationModel)
            .where(NotificationModel.type == "audit")
        )
        if action_type:
            count_stmt = count_stmt.where(NotificationModel.title.ilike(f"%{action_type}%"))
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = select(NotificationModel).where(NotificationModel.type == "audit")
        if action_type:
            stmt = stmt.where(NotificationModel.title.ilike(f"%{action_type}%"))
        stmt = stmt.order_by(NotificationModel.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)

        logs = []
        for n in result.scalars().all():
            logs.append(
                {
                    "id": n.id,
                    "user_id": n.user_id,
                    "action": n.title,
                    "detail": n.message or "",
                    "created_at": str(n.created_at) if n.created_at else "",
                }
            )

    return {
        "success": True,
        "data": logs,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── 15. Server 管理操作 ────────────────────────────────────


@router.post("/admin/servers/{server_id:path}/toggle")
async def admin_toggle_server(
    server_id: str,
    data: dict[str, Any] = Body(...),
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """启用/禁用或下架 Server。action: block/unblock/feature"""
    action = data.get("action", "")
    async with async_session_factory() as session:
        srv = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        server = srv.scalar_one_or_none()
        if not server:
            return {"success": False, "error": "Server 不存在"}

        if action == "block":
            server.security_level = "blocked"
            server.market_visible = False
            msg = f"已下架 {server_id}"
        elif action == "unblock":
            server.security_level = "reviewed"
            server.market_visible = True
            msg = f"已恢复 {server_id}"
        else:
            return {"success": False, "error": "action 必须是 block 或 unblock"}
        session.add(
            _audit_record(
                admin_user,
                f"{'下架' if action == 'block' else '恢复'} Server",
                f"server={server_id}",
            )
        )
        await session.commit()

    return {"success": True, "message": msg}


@router.post("/admin/servers/{server_id:path}/security")
async def admin_set_security(
    server_id: str,
    data: dict[str, Any] = Body(...),
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """手动调整 Server 安全等级。level: verified/reviewed/unreviewed/blocked"""
    level = data.get("level", "")
    if level not in ("verified", "reviewed", "unreviewed", "blocked"):
        return {"success": False, "error": "无效的安全等级"}
    async with async_session_factory() as session:
        server = await session.scalar(
            select(ServerModel).where(ServerModel.id == server_id).with_for_update()
        )
        if server is None:
            return {"success": False, "error": "Server 不存在"}
        server.security_level = level
        if level == "blocked":
            server.market_visible = False
        session.add(
            _audit_record(admin_user, f"调整安全等级: {server_id} → {level}")
        )
        await session.commit()
    return {"success": True, "message": f"已将 {server_id} 安全等级设为 {level}"}


# ── 16. 数据导出 ──────────────────────────────────────────


@router.get("/admin/export/users")
async def admin_export_users(
    admin_user: str = Depends(get_admin_user),
) -> Response:
    """导出用户列表为 CSV。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserModel.id, UserModel.display_name, UserModel.role, UserModel.created_at)
        )
        rows = result.fetchall()

    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["user_id", "display_name", "role", "created_at"])
    for r in rows:
        w.writerow(
            [
                _csv_cell(r[0]),
                _csv_cell(r[1]),
                _csv_cell(r[2]),
                _csv_cell(r[3]),
            ]
        )

    return Response(
        content=f"\ufeff{output.getvalue()}",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@router.get("/admin/export/servers")
async def admin_export_servers(
    admin_user: str = Depends(get_admin_user),
) -> Response:
    """导出 Server 列表为 CSV。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(
                ServerModel.id,
                ServerModel.name,
                ServerModel.rating,
                ServerModel.download_count,
                ServerModel.security_level,
            )
        )
        rows = result.fetchall()

    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["server_id", "name", "rating", "downloads", "security"])
    for r in rows:
        w.writerow([_csv_cell(value) for value in r])

    return Response(
        content=f"\ufeff{output.getvalue()}",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=servers.csv"},
    )


# ── 17. 分类管理 ──────────────────────────────────────────


@router.get("/admin/categories")
async def admin_categories(
    admin_user: str = Depends(get_admin_user),
) -> dict[str, Any]:
    """获取所有分类及统计。"""
    cats: list[dict[str, Any]] = [
        {"id": "ai", "name": "AI & 机器学习", "icon": "🤖"},
        {"id": "browser", "name": "浏览器 & Web", "icon": "🌐"},
        {"id": "database", "name": "数据库", "icon": "🗄️"},
        {"id": "developer-tools", "name": "开发者工具", "icon": "🛠️"},
        {"id": "filesystem", "name": "文件系统", "icon": "📁"},
        {"id": "communication", "name": "通信 & 消息", "icon": "💬"},
        {"id": "cloud", "name": "云服务 & DevOps", "icon": "☁️"},
        {"id": "monitoring", "name": "监控 & 调试", "icon": "📊"},
        {"id": "storage", "name": "存储 & 文件", "icon": "💾"},
        {"id": "security", "name": "安全 & 合规", "icon": "🔒"},
        {"id": "finance", "name": "金融 & 支付", "icon": "💰"},
        {"id": "maps", "name": "地图 & 位置", "icon": "🗺️"},
        {"id": "design", "name": "设计 & 媒体", "icon": "🎨"},
        {"id": "social-media", "name": "社交媒体", "icon": "📱"},
        {"id": "productivity", "name": "效率 & 笔记", "icon": "📝"},
        {"id": "apis", "name": "API & 集成", "icon": "🔌"},
        {"id": "tools", "name": "通用 & 其他", "icon": "🧰"},
    ]
    async with async_session_factory() as session:
        for cat in cats:
            r = await session.execute(
                select(func.count())
                .select_from(ServerModel)
                .where(_category_filter(cat["id"]))
            )
            cat["count"] = r.scalar() or 0
    return {"success": True, "data": cats}
