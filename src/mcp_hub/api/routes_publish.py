"""发布 API — 含安全检查。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.core.registry import Registry
from mcp_hub.core.security_scanner import SecurityScanner
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    ServerModel,
    TelemetryContributionConsentModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserServerModel,
)

router = APIRouter(tags=["publish"])
_MINIMUM_CONTRIBUTORS = 5
_FEEDBACK_WINDOW_DAYS = 30


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cohort_label(count: int) -> str:
    if count >= 100:
        return "100+"
    if count >= 25:
        return "25-99"
    if count >= 10:
        return "10-24"
    return "5-9"


def _activity_band(total_calls: int) -> str:
    if total_calls >= 500:
        return "high"
    if total_calls >= 50:
        return "moderate"
    return "low"


def _success_rate_band(ok_calls: int, total_calls: int) -> str:
    if total_calls <= 0:
        return "unavailable"
    percentage = ok_calls / total_calls * 100
    lower_bound = min(int(percentage // 5) * 5, 95)
    return f"{lower_bound}-{lower_bound + 4}%"


def _latency_band(avg_duration_ms: float) -> str:
    if avg_duration_ms < 100:
        return "under_100ms"
    if avg_duration_ms < 500:
        return "100_to_499ms"
    if avg_duration_ms < 2000:
        return "500ms_to_1.9s"
    return "2s_or_more"


async def _safe_local_aliases(
    server: ServerModel,
) -> set[str]:
    """Return only local names that uniquely resolve to this market entry."""
    candidates = {
        value
        for value in (
            server.id,
            server.id.rsplit("/", 1)[-1],
            server.name,
            server.display_name,
        )
        if value
    }
    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(ServerModel).where(
                        (ServerModel.id.in_(candidates))
                        | (ServerModel.name.in_(candidates))
                        | (ServerModel.display_name.in_(candidates))
                    )
                )
            ).scalars()
        )

    safe_aliases: set[str] = set()
    for candidate in candidates:
        owners = {
            row.id
            for row in rows
            if candidate
            in {
                row.id,
                row.id.rsplit("/", 1)[-1],
                row.name or "",
                row.display_name or "",
            }
        }
        if owners == {server.id}:
            safe_aliases.add(candidate)
    return safe_aliases


class PublishRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "tools"
    install_type: str = "npx"
    install_command: str = ""
    homepage: str = ""
    tags: list[str] = Field(default_factory=list)


@router.post("/publish")
async def publish_server(
    req: PublishRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """发布 MCP Server（含自动安全扫描）。"""
    server_id = f"@{req.name}" if not req.name.startswith("@") else req.name

    # 安全检查
    scanner = SecurityScanner()
    scan_data = {
        "id": server_id,
        "name": req.name,
        "description": req.description,
        "install_command": req.install_command,
        "install_type": req.install_type,
        "author": user_id,
    }
    report = await scanner.scan(scan_data)
    if report.score < 50:
        return {
            "success": False,
            "error": (
                f"安全评分 {report.score}/100（{report.level}），发布被阻止。"
                "请修复安装命令中的安全问题后再试。"
            ),
            "security_report": {
                "score": report.score,
                "level": report.level,
                "findings": [{"title": f.title, "severity": f.severity} for f in report.findings],
            },
        }

    registry = Registry()
    result_id = await registry.register_server(
        {
            "id": server_id,
            "name": req.name,
            "description": req.description,
            "categories": [req.category],
            "tags": req.tags,
            "install_type": req.install_type,
            "install_command": req.install_command,
            "homepage": req.homepage,
            "security_level": report.level,
            "author": user_id if user_id != "api-user" else "",
        }
    )
    return {
        "success": True,
        "data": {"id": result_id},
        "security": {"score": report.score, "level": report.level},
    }


@router.get("/publish/mine")
async def my_published_servers(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前用户发布的 Server。"""
    if user_id == "api-user":
        return {"success": True, "data": []}
    registry = Registry()
    servers = await registry.get_by_author(user_id)
    return {"success": True, "data": servers}


@router.get("/publish/mine/{server_id:path}/compatibility-feedback")
async def publisher_compatibility_feedback(
    server_id: str,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Return k-anonymous, opt-in compatibility signals for one owned Server."""
    since = _utc_now_naive() - timedelta(days=_FEEDBACK_WINDOW_DAYS)
    async with async_session_factory() as session:
        server = await session.get(ServerModel, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server 不存在")
    if server.author != user_id:
        raise HTTPException(status_code=403, detail="只能查看自己发布的 Server")

    safe_aliases = await _safe_local_aliases(server)
    async with async_session_factory() as session:
        eligible_events = (
            select(
                TelemetryEventModel.id,
                TelemetryEventModel.user_id,
            )
            .select_from(TelemetryEventModel)
            .join(
                UserServerModel,
                (UserServerModel.user_id == TelemetryEventModel.user_id)
                & (UserServerModel.server_id == server_id),
            )
            .join(
                TelemetryContributionConsentModel,
                TelemetryContributionConsentModel.user_id
                == TelemetryEventModel.user_id,
            )
            .join(
                TelemetryInventoryModel,
                (TelemetryInventoryModel.user_id == TelemetryEventModel.user_id)
                & (TelemetryInventoryModel.device_id == TelemetryEventModel.device_id)
                & (TelemetryInventoryModel.server_name == TelemetryEventModel.server_id)
                & TelemetryInventoryModel.active.is_(True),
            )
            .where(
                UserServerModel.user_id != user_id,
                UserServerModel.matched.is_(True),
                TelemetryContributionConsentModel.enabled.is_(True),
                TelemetryEventModel.server_id.in_(safe_aliases),
                TelemetryEventModel.event_type == "tool_call",
                TelemetryEventModel.occurred_at >= since,
            )
            .distinct()
            .subquery()
        )
        contributor_events = (
            select(eligible_events.c.user_id).distinct().subquery()
        )
        contributor_count = int(
            await session.scalar(select(func.count()).select_from(contributor_events)) or 0
        )
        available = contributor_count >= _MINIMUM_CONTRIBUTORS
        payload: dict[str, Any] = {
            "server_id": server_id,
            "days": _FEEDBACK_WINDOW_DAYS,
            "available": available,
            "minimum_contributors": _MINIMUM_CONTRIBUTORS,
            "contributor_cohort": _cohort_label(contributor_count) if available else "",
        }
        if not available:
            return {"success": True, "data": payload}

        event_filters = [
            TelemetryEventModel.id.in_(select(eligible_events.c.id)),
        ]
        summary = (
            await session.execute(
                select(
                    func.count(TelemetryEventModel.id).label("total_calls"),
                    func.coalesce(
                        func.sum(case((TelemetryEventModel.status == "ok", 1), else_=0)),
                        0,
                    ).label("ok_calls"),
                    func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                        "avg_duration_ms"
                    ),
                ).where(*event_filters)
            )
        ).one()
        agent_rows = (
            await session.execute(
                select(
                    TelemetryDeviceModel.agent_type,
                    func.count(func.distinct(TelemetryEventModel.user_id)).label(
                        "contributor_count"
                    ),
                    func.count(TelemetryEventModel.id).label("total_calls"),
                    func.coalesce(
                        func.sum(case((TelemetryEventModel.status == "ok", 1), else_=0)),
                        0,
                    ).label("ok_calls"),
                    func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                        "avg_duration_ms"
                    ),
                )
                .select_from(TelemetryEventModel)
                .join(
                    TelemetryDeviceModel,
                    (TelemetryDeviceModel.id == TelemetryEventModel.device_id)
                    & (TelemetryDeviceModel.user_id == TelemetryEventModel.user_id),
                )
                .where(*event_filters)
                .group_by(TelemetryDeviceModel.agent_type)
                .having(
                    func.count(func.distinct(TelemetryEventModel.user_id))
                    >= _MINIMUM_CONTRIBUTORS
                )
                .order_by(func.count(TelemetryEventModel.id).desc())
            )
        ).all()
        total_calls = int(summary.total_calls or 0)
        ok_calls = int(summary.ok_calls or 0)
        payload["summary"] = {
            "activity": _activity_band(total_calls),
            "success_rate_band": _success_rate_band(ok_calls, total_calls),
            "latency_band": _latency_band(float(summary.avg_duration_ms or 0)),
        }
        payload["agents"] = [
            {
                "agent_type": row.agent_type or "generic",
                "contributor_cohort": _cohort_label(int(row.contributor_count or 0)),
                "activity": _activity_band(int(row.total_calls or 0)),
                "success_rate_band": _success_rate_band(
                    int(row.ok_calls or 0),
                    int(row.total_calls or 0),
                ),
                "latency_band": _latency_band(float(row.avg_duration_ms or 0)),
            }
            for row in agent_rows
        ]
    return {"success": True, "data": payload}


@router.post("/publish/unpublish/{server_id:path}")
async def unpublish_server(
    server_id: str,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """下架自己发布的 Server。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        return {"success": False, "error": "Server 不存在"}
    if server.get("author", "") != user_id and user_id != "api-user":
        return {"success": False, "error": "只能下架自己发布的 Server"}
    ok = await registry.unpublish_server(server_id)
    return {"success": ok, "message": "已下架" if ok else "下架失败"}
