"""管理后台 API — 平台运营者查看/管理用户、Server、调用数据。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, Query
from sqlalchemy import func, select, text

from mcp_hub.api.dependencies import get_admin_user, get_current_user
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    FavoriteModel, NotificationModel, ReviewModel, ServerModel,
    UsageStatsModel, UserModel, UserServerModel,
)
from mcp_hub.exceptions import McpHubError
from mcp_hub.logging_config import get_logger

router = APIRouter(tags=["admin"])
logger = get_logger(__name__)


def _time_filter(days: int) -> text:
    return text(f"created_at >= datetime('now', '-{days} days')")


async def _pg_time_filter(session, days: int) -> text:
    bind_url = str(session.get_bind().url)
    if "postgresql" in bind_url:
        return text(f"created_at >= NOW() - INTERVAL '{days} days'")
    return _time_filter(days)


# ── 审计日志 ──────────────────────────────────────────────


async def _audit(user_id: str, action: str, detail: str = "") -> None:
    try:
        async with async_session_factory() as session:
            session.add(NotificationModel(
                user_id=user_id,
                type="audit",
                title=action,
                message=detail,
            ))
            await session.commit()
    except Exception as e:
        logger.warning("admin.audit_failed", error=str(e))


# ── 1. 平台概览 ───────────────────────────────────────────


@router.get("/admin/overview")
async def admin_overview(admin_user: str = Depends(get_admin_user)):

    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        days7 = text("created_at >= NOW() - INTERVAL '7 days'") if is_pg else _time_filter(7)
        days30 = text("created_at >= NOW() - INTERVAL '30 days'") if is_pg else _time_filter(30)

        # 基础统计
        total_users = (await session.execute(select(func.count()).select_from(UserModel))).scalar() or 0
        total_servers = (await session.execute(select(func.count()).select_from(ServerModel))).scalar() or 0
        total_installs = (await session.execute(select(func.count()).select_from(UserServerModel))).scalar() or 0
        total_calls = (await session.execute(select(func.count()).select_from(UsageStatsModel))).scalar() or 0
        total_tokens = (await session.execute(
            select(func.sum(UsageStatsModel.token_count)).select_from(UsageStatsModel)
        )).scalar() or 0
        active_users_7d = (await session.execute(
            select(func.count(func.distinct(UsageStatsModel.user_id)))
            .select_from(UsageStatsModel).where(days7)
        )).scalar() or 0

        # 每日趋势
        date_func = func.date(UsageStatsModel.created_at) if is_pg else func.date(UsageStatsModel.created_at)
        trend_result = await session.execute(
            select(
                date_func.label("day"),
                func.count().label("calls"),
                func.sum(UsageStatsModel.token_count).label("tokens"),
            ).select_from(UsageStatsModel).where(days30)
            .group_by(text("day" if is_pg else "day")).order_by(text("day"))
        )
        daily_trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0}
            for r in trend_result.fetchall()
        ]

        # Top 10 Server
        top_servers_result = await session.execute(
            select(
                UserServerModel.server_id,
                func.count(UserServerModel.server_id).label("installs"),
            ).group_by(UserServerModel.server_id).order_by(text("installs DESC")).limit(10)
        )
        top_servers = []
        for row in top_servers_result.fetchall():
            sid = row[0]
            srv = await session.execute(select(ServerModel.name).where(ServerModel.id == sid))
            srv_name = srv.scalar() or sid
            calls_7d = (await session.execute(
                select(func.count()).select_from(UsageStatsModel)
                .where(UsageStatsModel.server_id == sid).where(days7)
            )).scalar() or 0
            top_servers.append({"id": sid, "name": srv_name, "installs": row[1], "calls_7d": calls_7d})

        # Top 10 用户
        top_users_result = await session.execute(
            select(
                UsageStatsModel.user_id,
                func.count().label("calls"),
                func.sum(UsageStatsModel.token_count).label("tokens"),
            ).select_from(UsageStatsModel).where(days7)
            .group_by(UsageStatsModel.user_id).order_by(text("calls DESC")).limit(10)
        )
        top_users = []
        for row in top_users_result.fetchall():
            uid = row[0]
            usr = await session.execute(select(UserModel.display_name).where(UserModel.id == uid))
            name = usr.scalar() or uid
            top_users.append({"user_id": uid, "display_name": name, "calls_7d": row[1] or 0, "tokens_7d": row[2] or 0})

    return {
        "success": True,
        "data": {
            "stats": {
                "total_users": total_users, "total_servers": total_servers,
                "total_installs": total_installs, "total_calls": total_calls,
                "total_tokens": total_tokens, "active_users_7d": active_users_7d,
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
    q: str = "",
    sort: str = "calls",
    page: int = 1,
    page_size: int = Query(20, le=100),
):

    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        days7 = text("created_at >= NOW() - INTERVAL '7 days'") if is_pg else _time_filter(7)

        # 子查询：7 日调用统计
        stats_sub = (
            select(
                UsageStatsModel.user_id,
                func.count().label("calls_7d"),
                func.sum(UsageStatsModel.token_count).label("tokens_7d"),
                func.max(UsageStatsModel.created_at).label("last_active"),
            ).select_from(UsageStatsModel).where(days7).group_by(UsageStatsModel.user_id)
        ).alias("stats")

        # 总数
        count_stmt = select(func.count()).select_from(UserModel)
        if q:
            count_stmt = count_stmt.where(
                (UserModel.id.ilike(f"%{q}%")) | (UserModel.display_name.ilike(f"%{q}%"))
            )
        total = (await session.execute(count_stmt)).scalar() or 0

        # 主查询
        main_stmt = (
            select(
                UserModel.id, UserModel.display_name, UserModel.avatar_url,
                UserModel.role, UserModel.created_at, UserModel.last_login,
                func.count(func.distinct(UserServerModel.server_id)).label("server_count"),
                func.coalesce(stats_sub.c.calls_7d, 0).label("calls_7d"),
                func.coalesce(stats_sub.c.tokens_7d, 0).label("tokens_7d"),
                func.coalesce(stats_sub.c.last_active, UserModel.last_login).label("last_active"),
            )
            .select_from(UserModel)
            .outerjoin(UserServerModel, UserModel.id == UserServerModel.user_id)
            .outerjoin(stats_sub, UserModel.id == stats_sub.c.user_id)
        )
        if q:
            main_stmt = main_stmt.where(
                (UserModel.id.ilike(f"%{q}%")) | (UserModel.display_name.ilike(f"%{q}%"))
            )
        main_stmt = main_stmt.group_by(
            UserModel.id, stats_sub.c.calls_7d, stats_sub.c.tokens_7d, stats_sub.c.last_active
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
            users.append({
                "user_id": r[0], "display_name": r[1] or r[0], "avatar_url": r[2] or "",
                "role": r[3] or "user", "created_at": str(r[4]) if r[4] else "",
                "last_login": str(r[5]) if r[5] else "",
                "server_count": r[6] or 0, "calls_7d": r[7] or 0,
                "tokens_7d": r[8] or 0, "last_active": str(r[9]) if r[9] else "",
            })

    return {
        "success": True, "data": users,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── 3. 用户详情 ───────────────────────────────────────────


@router.get("/admin/users/{user_id:path}")
async def admin_user_detail(user_id: str, admin_user: str = Depends(get_admin_user)):

    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        days7 = text("created_at >= NOW() - INTERVAL '7 days'") if is_pg else _time_filter(7)
        days30 = text("created_at >= NOW() - INTERVAL '30 days'") if is_pg else _time_filter(30)

        # 用户基本信息
        usr_result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        usr = usr_result.scalar_one_or_none()
        if not usr:
            return {"success": False, "error": "用户不存在"}

        profile = {
            "id": usr.id, "display_name": usr.display_name or usr.id,
            "avatar_url": usr.avatar_url or "", "email": usr.email or "",
            "role": usr.role or "user",
            "created_at": str(usr.created_at) if usr.created_at else "",
            "last_login": str(usr.last_login) if usr.last_login else "",
        }

        # 统计
        srv_count = (await session.execute(
            select(func.count()).select_from(UserServerModel).where(UserServerModel.user_id == user_id)
        )).scalar() or 0
        total_calls = (await session.execute(
            select(func.count()).select_from(UsageStatsModel).where(UsageStatsModel.user_id == user_id)
        )).scalar() or 0
        total_tokens = (await session.execute(
            select(func.sum(UsageStatsModel.token_count)).select_from(UsageStatsModel)
            .where(UsageStatsModel.user_id == user_id)
        )).scalar() or 0
        fav_count = (await session.execute(
            select(func.count()).select_from(FavoriteModel).where(FavoriteModel.user_id == user_id)
        )).scalar() or 0

        # Server 列表
        srv_result = await session.execute(
            select(UserServerModel.server_id, UserServerModel.enabled)
            .where(UserServerModel.user_id == user_id).limit(20)
        )
        servers = []
        for row in srv_result.fetchall():
            sid = row[0]
            srv_calls = (await session.execute(
                select(func.count()).select_from(UsageStatsModel)
                .where(UsageStatsModel.server_id == sid, UsageStatsModel.user_id == user_id)
                .where(days7)
            )).scalar() or 0
            srv_tokens = (await session.execute(
                select(func.sum(UsageStatsModel.token_count)).select_from(UsageStatsModel)
                .where(UsageStatsModel.server_id == sid, UsageStatsModel.user_id == user_id)
                .where(days7)
            )).scalar() or 0
            servers.append({
                "server_id": sid, "name": sid.split("/")[-1],
                "calls_7d": srv_calls, "tokens_7d": srv_tokens or 0,
                "enabled": row[1] if row[1] is not None else True,
            })

        # 每日趋势
        date_func = func.date(UsageStatsModel.created_at) if is_pg else func.date(UsageStatsModel.created_at)
        trend_result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(UsageStatsModel.token_count))
            .select_from(UsageStatsModel)
            .where(UsageStatsModel.user_id == user_id).where(days30)
            .group_by(text("day")).order_by(text("day"))
        )
        daily_trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0}
            for r in trend_result.fetchall()
        ]

        # Top 5 工具
        tools_result = await session.execute(
            select(UsageStatsModel.tool_name, func.count().label("cnt"))
            .select_from(UsageStatsModel)
            .where(UsageStatsModel.user_id == user_id).where(days30)
            .group_by(UsageStatsModel.tool_name).order_by(text("cnt DESC")).limit(5)
        )
        top_tools = [{"tool_name": r[0] or "unknown", "count": r[1]} for r in tools_result.fetchall()]

    return {
        "success": True,
        "data": {
            "profile": profile,
            "stats": {
                "server_count": srv_count, "total_calls": total_calls,
                "total_tokens": total_tokens, "favorite_count": fav_count,
            },
            "servers": servers,
            "daily_trend": daily_trend,
            "top_tools": top_tools,
        },
    }


# ── 4. 用户 Server 列表 ────────────────────────────────────


@router.get("/admin/users/{user_id:path}/servers")
async def admin_user_servers(user_id: str, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel).where(UserServerModel.user_id == user_id).limit(50)
        )
        servers = []
        for row in result.scalars().all():
            srv = await session.execute(select(ServerModel.name).where(ServerModel.id == row.server_id))
            servers.append({
                "server_id": row.server_id,
                "name": srv.scalar() or row.server_id,
                "enabled": row.enabled if row.enabled is not None else True,
                "agent": row.agent or "",
            })
    return {"success": True, "data": servers}


# ── 5. 用户每日趋势 ───────────────────────────────────────


@router.get("/admin/users/{user_id:path}/usage/daily")
async def admin_user_daily(user_id: str, days: int = 30, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        time_f = text(f"created_at >= NOW() - INTERVAL '{days} days'") if is_pg else _time_filter(days)
        date_func = func.date(UsageStatsModel.created_at) if is_pg else func.date(UsageStatsModel.created_at)
        result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(UsageStatsModel.token_count))
            .select_from(UsageStatsModel)
            .where(UsageStatsModel.user_id == user_id).where(time_f)
            .group_by(text("day")).order_by(text("day"))
        )
        trend = [{"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0} for r in result.fetchall()]
    return {"success": True, "data": trend}


# ── 6. 修改角色 ───────────────────────────────────────────


@router.patch("/admin/users/{user_id:path}/role")
async def admin_update_role(user_id: str, data: dict = Body(...), admin_user: str = Depends(get_admin_user)):
    role = data.get("role", "")
    if role not in ("user", "admin"):
        return {"success": False, "error": "角色只能是 user 或 admin"}

    async with async_session_factory() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        if not result.scalar_one_or_none():
            return {"success": False, "error": "用户不存在"}
        await session.execute(text("UPDATE users SET role = :role WHERE id = :uid"), {"role": role, "uid": user_id})
        await session.commit()

    await _audit(admin_user, f"修改用户角色: {user_id} → {role}")
    return {"success": True, "message": f"已将 {user_id} 的角色修改为 {role}"}


# ── 7. Server 列表 ────────────────────────────────────────


@router.get("/admin/servers")
async def admin_servers(
    admin_user: str = Depends(get_admin_user),
    q: str = "", category: str = "",
    sort: str = "installs",
    page: int = 1, page_size: int = Query(20, le=100),
):

    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        days7 = text("created_at >= NOW() - INTERVAL '7 days'") if is_pg else _time_filter(7)

        count_stmt = select(func.count()).select_from(ServerModel)
        if q:
            count_stmt = count_stmt.where(
                (ServerModel.id.ilike(f"%{q}%")) | (ServerModel.name.ilike(f"%{q}%"))
            )
        if category:
            count_stmt = count_stmt.where(ServerModel.categories.ilike(f"%{category}%"))
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = select(ServerModel)
        if q:
            stmt = stmt.where((ServerModel.id.ilike(f"%{q}%")) | (ServerModel.name.ilike(f"%{q}%")))
        if category:
            stmt = stmt.where(ServerModel.categories.ilike(f"%{category}%"))

        if sort == "rating":
            stmt = stmt.order_by(ServerModel.rating.desc())
        elif sort == "calls":
            stmt = stmt.order_by(ServerModel.download_count.desc())
        else:
            stmt = stmt.order_by(ServerModel.download_count.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        servers = []
        for s in rows:
            install_count = (await session.execute(
                select(func.count()).select_from(UserServerModel)
                .where(UserServerModel.server_id == s.id)
            )).scalar() or 0
            calls_7d = (await session.execute(
                select(func.count()).select_from(UsageStatsModel)
                .where(UsageStatsModel.server_id == s.id).where(days7)
            )).scalar() or 0
            tokens_7d = (await session.execute(
                select(func.sum(UsageStatsModel.token_count)).select_from(UsageStatsModel)
                .where(UsageStatsModel.server_id == s.id).where(days7)
            )).scalar() or 0
            import json
            try:
                cats = json.loads(s.categories) if s.categories else []
            except Exception:
                cats = []
            servers.append({
                "server_id": s.id, "name": s.name or s.id,
                "categories": cats, "install_count": install_count,
                "calls_7d": calls_7d, "tokens_7d": tokens_7d or 0,
                "rating": s.rating or 0, "security_level": s.security_level or "unreviewed",
                "download_count": s.download_count or 0,
            })

    return {
        "success": True, "data": servers,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── 8-10. Server 详情 + 用户 + 趋势 ────────────────────────


@router.get("/admin/servers/{server_id:path}")
async def admin_server_detail(server_id: str, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        srv = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        s = srv.scalar_one_or_none()
        if not s:
            return {"success": False, "error": "Server 不存在"}

        is_pg = "postgresql" in str(session.get_bind().url)
        days7 = text("created_at >= NOW() - INTERVAL '7 days'") if is_pg else _time_filter(7)
        days30 = text("created_at >= NOW() - INTERVAL '30 days'") if is_pg else _time_filter(30)

        install_count = (await session.execute(
            select(func.count()).select_from(UserServerModel).where(UserServerModel.server_id == server_id)
        )).scalar() or 0
        calls_7d = (await session.execute(
            select(func.count()).select_from(UsageStatsModel)
            .where(UsageStatsModel.server_id == server_id).where(days7)
        )).scalar() or 0
        tokens_7d = (await session.execute(
            select(func.sum(UsageStatsModel.token_count)).select_from(UsageStatsModel)
            .where(UsageStatsModel.server_id == server_id).where(days7)
        )).scalar() or 0

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
            uc = (await session.execute(
                select(func.count()).select_from(UsageStatsModel)
                .where(UsageStatsModel.server_id == server_id, UsageStatsModel.user_id == uid).where(days7)
            )).scalar() or 0
            install_users.append({"user_id": uid, "display_name": usr.scalar() or uid, "calls_7d": uc})

        # 趋势
        date_func = func.date(UsageStatsModel.created_at) if is_pg else func.date(UsageStatsModel.created_at)
        trend_result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(UsageStatsModel.token_count))
            .select_from(UsageStatsModel).where(UsageStatsModel.server_id == server_id).where(days30)
            .group_by(text("day")).order_by(text("day"))
        )
        daily_trend = [{"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0} for r in trend_result.fetchall()]

        # Top 5 工具
        tools_result = await session.execute(
            select(UsageStatsModel.tool_name, func.count().label("cnt"))
            .select_from(UsageStatsModel).where(UsageStatsModel.server_id == server_id).where(days30)
            .group_by(UsageStatsModel.tool_name).order_by(text("cnt DESC")).limit(5)
        )
        top_tools = [{"tool_name": r[0] or "unknown", "count": r[1]} for r in tools_result.fetchall()]

    return {
        "success": True,
        "data": {
            "server": {
                "server_id": s.id, "name": s.name or s.id, "description": s.description or "",
                "categories": cats, "rating": s.rating or 0, "security_level": s.security_level or "unreviewed",
                "download_count": s.download_count or 0, "version": s.current_version or "",
                "homepage": s.homepage or "", "author": s.author or "",
            },
            "stats": {"install_count": install_count, "calls_7d": calls_7d, "tokens_7d": tokens_7d or 0},
            "install_users": install_users,
            "daily_trend": daily_trend,
            "top_tools": top_tools,
        },
    }


@router.get("/admin/servers/{server_id:path}/users")
async def admin_server_users(server_id: str, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserServerModel).where(UserServerModel.server_id == server_id).limit(50)
        )
        users = []
        for row in result.scalars().all():
            usr = await session.execute(select(UserModel.display_name).where(UserModel.id == row.user_id))
            users.append({
                "user_id": row.user_id,
                "display_name": usr.scalar() or row.user_id,
                "enabled": row.enabled if row.enabled is not None else True,
            })
    return {"success": True, "data": users}


@router.get("/admin/servers/{server_id:path}/usage/daily")
async def admin_server_daily(server_id: str, days: int = 30, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        time_f = text(f"created_at >= NOW() - INTERVAL '{days} days'") if is_pg else _time_filter(days)
        date_func = func.date(UsageStatsModel.created_at) if is_pg else func.date(UsageStatsModel.created_at)
        result = await session.execute(
            select(date_func.label("day"), func.count(), func.sum(UsageStatsModel.token_count))
            .select_from(UsageStatsModel).where(UsageStatsModel.server_id == server_id).where(time_f)
            .group_by(text("day")).order_by(text("day"))
        )
        trend = [{"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0} for r in result.fetchall()]
    return {"success": True, "data": trend}


# ── 11-13. 使用分析 ───────────────────────────────────────


@router.get("/admin/analytics/daily")
async def admin_analytics_daily(days: int = 30, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        time_f = text(f"created_at >= NOW() - INTERVAL '{days} days'") if is_pg else _time_filter(days)
        date_func = func.date(UsageStatsModel.created_at) if is_pg else func.date(UsageStatsModel.created_at)
        result = await session.execute(
            select(
                date_func.label("day"),
                func.count().label("calls"),
                func.sum(UsageStatsModel.token_count).label("tokens"),
                func.count(func.distinct(UsageStatsModel.user_id)).label("users"),
                func.count(func.distinct(UsageStatsModel.server_id)).label("servers"),
            ).select_from(UsageStatsModel).where(time_f)
            .group_by(text("day")).order_by(text("day"))
        )
        trend = [
            {"date": str(r[0]), "calls": r[1] or 0, "tokens": r[2] or 0,
             "active_users": r[3] or 0, "active_servers": r[4] or 0}
            for r in result.fetchall()
        ]
    return {"success": True, "data": trend}


@router.get("/admin/analytics/top-servers")
async def admin_top_servers(
    metric: str = "calls", days: int = 7, limit: int = 10,
    admin_user: str = Depends(get_admin_user),
):
    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        time_f = text(f"created_at >= NOW() - INTERVAL '{days} days'") if is_pg else _time_filter(days)

        if metric == "tokens":
            order_col = func.sum(UsageStatsModel.token_count)
        elif metric == "installs":
            order_col = func.count(UserServerModel.server_id)
        else:
            order_col = func.count()

        result = await session.execute(
            select(
                UsageStatsModel.server_id,
                func.count().label("calls"),
                func.sum(UsageStatsModel.token_count).label("tokens"),
            ).select_from(UsageStatsModel).where(time_f)
            .group_by(UsageStatsModel.server_id).order_by(order_col.desc()).limit(limit)
        )
        servers = []
        for row in result.fetchall():
            sid = row[0]
            srv = await session.execute(select(ServerModel.name).where(ServerModel.id == sid))
            servers.append({
                "server_id": sid, "name": srv.scalar() or sid,
                "calls": row[1] or 0, "tokens": row[2] or 0,
            })
    return {"success": True, "data": servers}


@router.get("/admin/analytics/top-users")
async def admin_top_users(
    metric: str = "calls", days: int = 7, limit: int = 10,
    admin_user: str = Depends(get_admin_user),
):
    async with async_session_factory() as session:
        is_pg = "postgresql" in str(session.get_bind().url)
        time_f = text(f"created_at >= NOW() - INTERVAL '{days} days'") if is_pg else _time_filter(days)

        result = await session.execute(
            select(
                UsageStatsModel.user_id,
                func.count().label("calls"),
                func.sum(UsageStatsModel.token_count).label("tokens"),
            ).select_from(UsageStatsModel).where(time_f)
            .group_by(UsageStatsModel.user_id).order_by(text("calls DESC")).limit(limit)
        )
        users = []
        for row in result.fetchall():
            uid = row[0]
            usr = await session.execute(select(UserModel.display_name).where(UserModel.id == uid))
            users.append({
                "user_id": uid, "display_name": usr.scalar() or uid,
                "calls": row[1] or 0, "tokens": row[2] or 0,
            })
    return {"success": True, "data": users}


# ── 14. 评价审核 ──────────────────────────────────────────


@router.get("/admin/reviews")
async def admin_reviews(
    page: int = 1, page_size: int = Query(20, le=100),
    admin_user: str = Depends(get_admin_user),
):
    async with async_session_factory() as session:
        count_result = await session.execute(select(func.count()).select_from(ReviewModel))
        total = count_result.scalar() or 0

        result = await session.execute(
            select(ReviewModel).order_by(ReviewModel.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        reviews = []
        for r in result.scalars().all():
            srv = await session.execute(select(ServerModel.name).where(ServerModel.id == r.server_id))
            reviews.append({
                "id": r.id, "server_id": r.server_id,
                "server_name": srv.scalar() or r.server_id,
                "user_id": r.user_id, "rating": r.rating,
                "content": (r.content or "")[:200],
                "created_at": str(r.created_at) if r.created_at else "",
            })

    return {
        "success": True, "data": reviews,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


@router.delete("/admin/reviews/{review_id}")
async def admin_delete_review(review_id: int, admin_user: str = Depends(get_admin_user)):
    async with async_session_factory() as session:
        r = await session.execute(select(ReviewModel).where(ReviewModel.id == review_id))
        review = r.scalar_one_or_none()
        if not review:
            return {"success": False, "error": "评价不存在"}
        await session.delete(review)
        await session.commit()

    await _audit(admin_user, f"删除评价 #{review_id}", f"server={review.server_id} user={review.user_id}")
    return {"success": True, "message": "评价已删除"}


# ── 审计日志 ──────────────────────────────────────────────


@router.get("/admin/audit")
async def admin_audit_log(
    action_type: str = "", page: int = 1, page_size: int = Query(50, le=100),
    admin_user: str = Depends(get_admin_user),
):
    async with async_session_factory() as session:
        count_stmt = select(func.count()).select_from(NotificationModel).where(
            NotificationModel.type == "audit"
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
            logs.append({
                "id": n.id, "user_id": n.user_id,
                "action": n.title, "detail": n.message or "",
                "created_at": str(n.created_at) if n.created_at else "",
            })

    return {
        "success": True, "data": logs,
        "meta": {"total": total, "page": page, "page_size": page_size},
    }


# ── 15. Server 管理操作 ────────────────────────────────────


@router.post("/admin/servers/{server_id:path}/toggle")
async def admin_toggle_server(server_id: str, data: dict = Body(...), admin_user: str = Depends(get_admin_user)):
    """启用/禁用或下架 Server。action: block/unblock/feature"""
    action = data.get("action", "")
    async with async_session_factory() as session:
        srv = await session.execute(select(ServerModel).where(ServerModel.id == server_id))
        server = srv.scalar_one_or_none()
        if not server:
            return {"success": False, "error": "Server 不存在"}

        if action == "block":
            server.security_level = "blocked"
            msg = f"已下架 {server_id}"
        elif action == "unblock":
            server.security_level = "reviewed"
            msg = f"已恢复 {server_id}"
        else:
            return {"success": False, "error": "action 必须是 block 或 unblock"}
        await session.commit()

    await _audit(admin_user, f"{'下架' if action == 'block' else '恢复'} Server", f"server={server_id}")
    return {"success": True, "message": msg}


@router.post("/admin/servers/{server_id:path}/security")
async def admin_set_security(server_id: str, data: dict = Body(...), admin_user: str = Depends(get_admin_user)):
    """手动调整 Server 安全等级。level: verified/reviewed/unreviewed/blocked"""
    level = data.get("level", "")
    if level not in ("verified", "reviewed", "unreviewed", "blocked"):
        return {"success": False, "error": "无效的安全等级"}
    async with async_session_factory() as session:
        await session.execute(text("UPDATE servers SET security_level = :lv WHERE id = :sid"), {"lv": level, "sid": server_id})
        await session.commit()
    await _audit(admin_user, f"调整安全等级: {server_id} → {level}")
    return {"success": True, "message": f"已将 {server_id} 安全等级设为 {level}"}


# ── 16. 数据导出 ──────────────────────────────────────────


@router.get("/admin/export/users")
async def admin_export_users(admin_user: str = Depends(get_admin_user)):
    """导出用户列表为 CSV。"""
    async with async_session_factory() as session:
        result = await session.execute(select(UserModel.id, UserModel.display_name, UserModel.role, UserModel.created_at))
        rows = result.fetchall()

    import csv, io
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["user_id", "display_name", "role", "created_at"])
    for r in rows:
        w.writerow([r[0], r[1], r[2], str(r[3]) if r[3] else ""])

    from fastapi.responses import Response
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=users.csv"})


@router.get("/admin/export/servers")
async def admin_export_servers(admin_user: str = Depends(get_admin_user)):
    """导出 Server 列表为 CSV。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ServerModel.id, ServerModel.name, ServerModel.rating, ServerModel.download_count, ServerModel.security_level)
        )
        rows = result.fetchall()

    import csv, io
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["server_id", "name", "rating", "downloads", "security"])
    for r in rows:
        w.writerow([r[0], r[1], r[2], r[3], r[4]])

    from fastapi.responses import Response
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=servers.csv"})


# ── 17. 分类管理 ──────────────────────────────────────────


@router.get("/admin/categories")
async def admin_categories(admin_user: str = Depends(get_admin_user)):
    """获取所有分类及统计。"""
    cats = [
        {"id": "ai", "name": "AI & 机器学习", "icon": "🤖"},
        {"id": "browser", "name": "浏览器 & Web", "icon": "🌐"},
        {"id": "database", "name": "数据库", "icon": "🗄️"},
        {"id": "developer", "name": "开发者工具", "icon": "🛠️"},
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
                select(func.count()).select_from(ServerModel).where(ServerModel.categories.ilike(f"%{cat['id']}%"))
            )
            cat["count"] = r.scalar() or 0
    return {"success": True, "data": cats}
