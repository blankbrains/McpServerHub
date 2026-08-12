"""Unified current-user view of tracked, discovered, and monitored MCP Servers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_, select

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    ServerModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserServerModel,
)

router = APIRouter(prefix="/my-mcp", tags=["my-mcp"])
_ONLINE_WINDOW = timedelta(minutes=3)


class TrackLocalServerRequest(BaseModel):
    """One explicit request to add a private or market Server to tracking."""

    model_config = ConfigDict(extra="forbid")

    server_id: str = Field(min_length=1, max_length=255)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _market_payload(server: ServerModel | None) -> dict[str, object]:
    if server is None:
        return {
            "market_status": "unlisted",
            "market_id": None,
            "security_level": "unreviewed",
        }
    security_level = server.security_level or "unreviewed"
    return {
        "market_status": "listed",
        "market_id": server.id,
        "security_level": security_level,
    }


def _security_status(server: ServerModel | None) -> str:
    level = (server.security_level or "unreviewed") if server else "unreviewed"
    if level == "blocked":
        return "blocked"
    if level in {"verified", "reviewed"}:
        return "verified"
    return "unreviewed"


def _primary_action(entity: dict[str, Any]) -> dict[str, str]:
    if entity["config_status"] == "conflict":
        return {
            "code": "compare_configuration",
            "label": "比较配置",
            "type": "link",
            "target": "/local",
        }
    if entity["gateway_status"] in {"configuration_error", "direct_retained"}:
        return {
            "code": "diagnose",
            "label": "运行诊断",
            "type": "link",
            "target": "/local",
        }
    if entity["tracking_status"] == "untracked" and (
        entity["market_status"] == "listed" or entity["discovered"]
    ):
        return {
            "code": "track",
            "label": "加入追踪",
            "type": "api",
            "target": "",
        }
    if entity["gateway_status"] == "not_connected":
        return {
            "code": "view_setup",
            "label": "查看接入步骤",
            "type": "link",
            "target": "/guide",
        }
    return {
        "code": "view_monitoring",
        "label": "查看监控",
        "type": "link",
        "target": "/monitor",
    }


@router.get("/overview")
async def get_my_mcp_overview(
    days: int = Query(7, ge=1, le=365),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate current-user market, tracking, Gateway, runtime, and call state."""
    now = _utc_now_naive()
    since = now - timedelta(days=days)
    online_since = now - _ONLINE_WINDOW

    async with async_session_factory() as session:
        tracked_result = await session.execute(
            select(UserServerModel)
            .where(UserServerModel.user_id == user_id)
            .order_by(UserServerModel.created_at)
        )
        tracked_rows = list(tracked_result.scalars())

        inventory_result = await session.execute(
            select(TelemetryInventoryModel, TelemetryDeviceModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryInventoryModel.device_id,
            )
            .where(
                TelemetryInventoryModel.user_id == user_id,
                TelemetryInventoryModel.active == True,  # noqa: E712
                TelemetryDeviceModel.user_id == user_id,
                TelemetryDeviceModel.revoked_at.is_(None),
            )
        )
        inventory_pairs = list(inventory_result.all())

        event_result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                func.count(TelemetryEventModel.id).label("call_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (TelemetryEventModel.status == "ok", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("ok_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (TelemetryEventModel.status == "error", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("error_count"),
                func.coalesce(
                    func.sum(
                        TelemetryEventModel.input_tokens
                        + TelemetryEventModel.output_tokens
                    ),
                    0,
                ).label("token_count"),
                func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
            )
            .where(
                TelemetryEventModel.user_id == user_id,
                TelemetryEventModel.event_type == "tool_call",
                TelemetryEventModel.server_id != "",
                TelemetryEventModel.occurred_at >= since,
            )
            .group_by(TelemetryEventModel.server_id)
        )
        event_rows = list(event_result.all())

        observed_names = {
            row.server_name for row, _device in inventory_pairs
        } | {str(row.server_id) for row in event_rows if row.server_id}
        tracked_ids = {row.server_id for row in tracked_rows}
        lookup_ids = tracked_ids | observed_names
        market_conditions = []
        if lookup_ids:
            market_conditions.append(ServerModel.id.in_(lookup_ids))
        if observed_names:
            market_conditions.extend(
                [
                    ServerModel.name.in_(observed_names),
                    ServerModel.display_name.in_(observed_names),
                ]
            )
        if market_conditions:
            market_result = await session.execute(
                select(ServerModel).where(or_(*market_conditions))
            )
            market_rows = list(market_result.scalars())
        else:
            market_rows = []

    tracked_by_id = {row.server_id: row for row in tracked_rows}
    market_by_id = {row.id: row for row in market_rows}
    tracked_aliases: dict[str, list[str]] = defaultdict(list)
    for server_id in tracked_by_id:
        tracked_aliases[server_id.rsplit("/", 1)[-1]].append(server_id)
    market_aliases: dict[str, list[str]] = defaultdict(list)
    for market in market_rows:
        for alias in {market.name or "", market.display_name or ""} - {""}:
            market_aliases[alias].append(market.id)

    def resolve_observed_name(server_name: str) -> str:
        if server_name in tracked_by_id:
            return server_name
        tracked_matches = tracked_aliases.get(server_name, [])
        if len(tracked_matches) == 1:
            return tracked_matches[0]
        if server_name in market_by_id:
            return server_name
        market_matches = sorted(set(market_aliases.get(server_name, [])))
        if len(market_matches) == 1:
            return market_matches[0]
        return f"local:{server_name}"

    entities: dict[str, dict[str, Any]] = {}

    def ensure_entity(entity_id: str, observed_name: str = "") -> dict[str, Any]:
        existing = entities.get(entity_id)
        if existing is not None:
            if observed_name and observed_name not in existing["local_names"]:
                existing["local_names"].append(observed_name)
            return existing

        tracked = tracked_by_id.get(entity_id)
        market = market_by_id.get(entity_id)
        server_id = entity_id.removeprefix("local:")
        name = (
            market.display_name
            or market.name
            or server_id.rsplit("/", 1)[-1]
            if market
            else server_id
        )
        entity = {
            "entity_id": entity_id,
            "server_id": market.id if market else server_id,
            "name": name,
            "description": (market.description or "") if market else "",
            **_market_payload(market),
            "tracking_status": "tracked" if tracked else "untracked",
            "tracked": tracked is not None,
            "matched": bool(tracked.matched) if tracked else bool(market),
            "enabled": (
                tracked.enabled if tracked and tracked.enabled is not None else True
            ),
            "agent": (tracked.agent or "") if tracked else "",
            "group_name": (tracked.group_name or "") if tracked else "",
            "local_names": [observed_name] if observed_name else [],
            "inventory": [],
            "call_count": 0,
            "ok_count": 0,
            "error_count": 0,
            "token_count": 0,
            "last_call_at": None,
            "security_status": _security_status(market),
        }
        entities[entity_id] = entity
        return entity

    for tracked_id in tracked_by_id:
        ensure_entity(tracked_id)

    for inventory, device in inventory_pairs:
        entity_id = resolve_observed_name(inventory.server_name)
        entity = ensure_entity(entity_id, inventory.server_name)
        entity["inventory"].append(
            {
                "device_id": device.id,
                "device_name": device.name,
                "agent_type": device.agent_type,
                "online": bool(
                    device.gateway_last_seen_at
                    and device.gateway_last_seen_at >= online_since
                ),
                "gateway_seen": device.gateway_first_seen_at is not None,
                "running": bool(inventory.running),
                "enabled": bool(inventory.enabled),
                "config_hash": inventory.config_hash,
                "configuration_error": inventory.configuration_error or "",
                "last_seen_at": inventory.last_seen_at.isoformat(),
            }
        )

    for event in event_rows:
        observed_name = str(event.server_id)
        entity_id = resolve_observed_name(observed_name)
        entity = ensure_entity(entity_id, observed_name)
        entity["call_count"] += int(event.call_count or 0)
        entity["ok_count"] += int(event.ok_count or 0)
        entity["error_count"] += int(event.error_count or 0)
        entity["token_count"] += int(event.token_count or 0)
        if event.last_call_at and (
            entity["last_call_at"] is None
            or event.last_call_at > entity["last_call_at"]
        ):
            entity["last_call_at"] = event.last_call_at

    serialized: list[dict[str, Any]] = []
    for entity in entities.values():
        inventory = entity.pop("inventory")
        errors = [
            str(row["configuration_error"])
            for row in inventory
            if row["configuration_error"]
        ]
        if any(error != "unsupported_or_invalid" for error in errors):
            gateway_status = "configuration_error"
        elif errors:
            gateway_status = "direct_retained"
        elif any(row["gateway_seen"] for row in inventory) or int(entity["call_count"]) > 0:
            gateway_status = "connected"
        else:
            gateway_status = "not_connected"

        online_inventory = [row for row in inventory if row["online"]]
        if any(row["running"] for row in online_inventory):
            runtime_status = "running"
        elif online_inventory:
            runtime_status = "stopped"
        elif inventory:
            runtime_status = "offline"
        else:
            runtime_status = "unknown"

        config_hashes = {
            str(row["config_hash"]) for row in inventory if row["config_hash"]
        }
        config_status = (
            "conflict"
            if len(config_hashes) > 1
            else "consistent"
            if inventory
            else "unknown"
        )
        call_count = int(entity["call_count"])
        ok_count = int(entity["ok_count"])
        needs_attention = bool(
            config_status == "conflict"
            or gateway_status in {"configuration_error", "direct_retained"}
            or entity["security_status"] == "blocked"
            or (
                entity["tracking_status"] == "tracked"
                and gateway_status == "not_connected"
            )
        )
        item = {
            **entity,
            "discovered": bool(inventory),
            "gateway_status": gateway_status,
            "runtime_status": runtime_status,
            "call_status": "called" if call_count else "no_calls",
            "config_status": config_status,
            "device_count": len(inventory),
            "online_device_count": len(online_inventory),
            "devices": inventory,
            "call_count_7d": call_count,
            "token_consumption": int(entity["token_count"]),
            "success_rate": round(ok_count / call_count * 100, 1)
            if call_count
            else 0,
            "last_call_at": (
                entity["last_call_at"].isoformat()
                if entity["last_call_at"]
                else None
            ),
            "needs_attention": needs_attention,
        }
        item["primary_action"] = _primary_action(item)
        serialized.append(item)

    serialized.sort(
        key=lambda item: (
            not item["needs_attention"],
            item["tracking_status"] != "tracked",
            str(item["name"]).lower(),
        )
    )
    return {
        "success": True,
        "data": {
            "days": days,
            "summary": {
                "total": len(serialized),
                "discovered": sum(1 for item in serialized if item["discovered"]),
                "tracked": sum(
                    1 for item in serialized if item["tracking_status"] == "tracked"
                ),
                "connected": sum(
                    1 for item in serialized if item["gateway_status"] == "connected"
                ),
                "needs_attention": sum(
                    1 for item in serialized if item["needs_attention"]
                ),
                "conflicts": sum(
                    1 for item in serialized if item["config_status"] == "conflict"
                ),
            },
            "servers": serialized,
        },
    }


@router.post("/track")
async def track_my_mcp_server(
    data: TrackLocalServerRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Track one market or private local Server without publishing it."""
    server_id = data.server_id.strip()
    async with async_session_factory() as session:
        market = await session.get(ServerModel, server_id)
        local_server = await session.scalar(
            select(TelemetryInventoryModel.id).where(
                TelemetryInventoryModel.user_id == user_id,
                TelemetryInventoryModel.server_name == server_id,
                TelemetryInventoryModel.active == True,  # noqa: E712
            )
        )
        if market is None and local_server is None:
            raise HTTPException(
                status_code=404,
                detail="当前账户未发现此本地 Server，市场中也不存在该条目",
            )
        existing = await session.scalar(
            select(UserServerModel).where(
                UserServerModel.user_id == user_id,
                UserServerModel.server_id == server_id,
            )
        )
        if existing is None:
            session.add(
                UserServerModel(
                    user_id=user_id,
                    server_id=server_id,
                    matched=market is not None,
                    enabled=True,
                )
            )
            await session.commit()
            matched = market is not None
        else:
            matched = bool(existing.matched)
    return {
        "success": True,
        "data": {
            "server_id": server_id,
            "tracked": True,
            "matched": matched,
            "published": False,
        },
    }
