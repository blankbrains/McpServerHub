"""监控大屏 API — 聚合所有 Server 的运行状态、资源位置、性能指标。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select

from mcp_hub.api.dependencies import get_optional_user
from mcp_hub.core.registry import Registry
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserServerModel,
)

router = APIRouter(tags=["monitor"])


@router.get("/monitor/dashboard")
async def monitor_dashboard(
    user_id: str | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Return current-user MCP status and usage from device telemetry."""
    if not user_id:
        return {
            "success": True,
            "data": {
                "summary": {
                    "total_servers": 0,
                    "running": 0,
                    "stopped": 0,
                    "offline": 0,
                    "error": 0,
                    "healthy": 0,
                    "total_calls_7d": 0,
                    "total_token_consumption": 0,
                    "avg_reliability": 0,
                },
                "servers": [],
            },
        }

    registry = Registry()
    servers = await registry.get_all()
    tracked_info: dict[str, bool] = {}
    telemetry_stats: dict[str, dict[str, int]] = {}
    inventory_by_server: dict[str, list[TelemetryInventoryModel]] = {}
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    online_since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3)

    async with async_session_factory() as session:
        tracked_result = await session.execute(
            select(UserServerModel.server_id, UserServerModel.enabled).where(
                UserServerModel.user_id == user_id
            )
        )
        for row in tracked_result.fetchall():
            tracked_info[row[0]] = row[1] if row[1] is not None else True

        stats_result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                func.coalesce(
                    func.sum(
                        case(
                            (TelemetryEventModel.event_type == "tool_call", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("call_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                TelemetryEventModel.event_type == "tool_call",
                                TelemetryEventModel.input_tokens
                                + TelemetryEventModel.output_tokens,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("token_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (TelemetryEventModel.event_type == "tool_call")
                                & (TelemetryEventModel.status == "ok"),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("ok_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (TelemetryEventModel.event_type == "tool_call")
                                & (TelemetryEventModel.status == "error"),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("error_count"),
                func.coalesce(
                    func.max(
                        case(
                            (
                                TelemetryEventModel.event_type == "resource_sample",
                                TelemetryEventModel.process_uptime_seconds,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("uptime_seconds"),
            )
            .where(
                TelemetryEventModel.user_id == user_id,
                TelemetryEventModel.occurred_at >= since,
                TelemetryEventModel.server_id != "",
            )
            .group_by(TelemetryEventModel.server_id)
        )
        for row in stats_result.fetchall():
            telemetry_stats[row.server_id] = {
                "call_count": int(row.call_count or 0),
                "token_count": int(row.token_count or 0),
                "ok_count": int(row.ok_count or 0),
                "error_count": int(row.error_count or 0),
                "uptime_seconds": int(row.uptime_seconds or 0),
            }

        inventory_result = await session.execute(
            select(TelemetryInventoryModel).where(
                TelemetryInventoryModel.user_id == user_id,
                TelemetryInventoryModel.active == True,  # noqa: E712
            )
        )
        for inventory in inventory_result.scalars():
            inventory_by_server.setdefault(inventory.server_name, []).append(inventory)

    server_by_id = {server["id"]: server for server in servers}
    relevant = [
        server_by_id[server_id] for server_id in tracked_info if server_id in server_by_id
    ]
    items: list[dict[str, Any]] = []
    total_calls_all = 0
    total_tokens_all = 0

    for server in relevant:
        sid = server["id"]
        stats = telemetry_stats.get(
            sid,
            {
                "call_count": 0,
                "token_count": 0,
                "ok_count": 0,
                "error_count": 0,
                "uptime_seconds": 0,
            },
        )
        inventory_rows = inventory_by_server.get(sid, [])
        online_rows = [
            row for row in inventory_rows if row.last_seen_at >= online_since
        ]
        running = any(bool(row.running) for row in online_rows)
        if running:
            status = "running"
        elif online_rows:
            status = "stopped"
        elif inventory_rows:
            status = "offline"
        else:
            status = "not_connected"

        calls = stats["call_count"]
        tokens = stats["token_count"]
        total_calls_all += calls
        total_tokens_all += tokens
        score = round(stats["ok_count"] / calls * 100) if calls else 0

        items.append(
            {
                "server_id": sid,
                "name": server.get("name", sid.split("/")[-1]),
                "description": server.get("description", ""),
                "status": status,
                "running": running,
                "enabled": tracked_info.get(sid, True),
                "pid": None,
                "location": "本地 Agent",
                "uptime_seconds": stats["uptime_seconds"],
                "reliability_score": score,
                "total_checks": calls,
                "last_check_status": (
                    "error"
                    if stats["error_count"]
                    else "ok"
                    if calls
                    else ""
                ),
                "token_consumption": tokens,
                "call_count_7d": calls,
                "rating": server.get("rating", 0),
                "version": server.get("version", "?"),
                "security_level": server.get("security_level", "unreviewed"),
                "install_command": server.get("install_command", ""),
            }
        )

    running_count = sum(1 for item in items if item["running"])
    stopped_count = sum(1 for item in items if item["status"] == "stopped")
    offline_count = sum(
        1 for item in items if item["status"] in {"offline", "not_connected"}
    )
    error_count = sum(
        1 for stats in telemetry_stats.values() if stats["error_count"] > 0
    )
    healthy_count = sum(1 for item in items if item["last_check_status"] == "ok")

    summary = {
        "total_servers": len(relevant),
        "running": running_count,
        "stopped": stopped_count,
        "offline": offline_count,
        "error": error_count,
        "healthy": healthy_count,
        "total_calls_7d": total_calls_all,
        "total_token_consumption": total_tokens_all,
        "avg_reliability": round(sum(i["reliability_score"] for i in items) / len(items), 1)
        if items
        else 0,
    }

    items.sort(key=lambda x: x["reliability_score"], reverse=True)

    return {
        "success": True,
        "data": {
            "summary": summary,
            "servers": items,
        },
    }
