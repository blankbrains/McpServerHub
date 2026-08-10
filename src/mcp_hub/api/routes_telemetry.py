"""本地 MCP Agent 遥测设备与事件 API。"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, case, func, select, update
from sqlalchemy.exc import IntegrityError

from mcp_hub.agent_types import DEFAULT_AGENT_TYPE, normalize_agent_type
from mcp_hub.api.dependencies import get_current_user
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UsageStatsModel,
)
from mcp_hub.logging_config import get_logger

router = APIRouter(tags=["telemetry"])
logger = get_logger(__name__)
_MAX_EVENT_BATCH = 100


class DeviceCreateRequest(BaseModel):
    """创建本地 Agent 设备凭证的输入。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    agent_type: str = Field(default=DEFAULT_AGENT_TYPE, max_length=32)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("设备名称不能为空")
        return normalized

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, value: str) -> str:
        return normalize_agent_type(value)


class TelemetryEventInput(BaseModel):
    """无敏感载荷的最小化遥测事件。"""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    event_type: Literal[
        "heartbeat",
        "server_lifecycle",
        "tool_call",
        "protocol_call",
        "resource_sample",
        "error_event",
    ]
    session_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    server_id: str = Field(default="", max_length=255)
    tool_name: str = Field(default="", max_length=255)
    operation: str = Field(default="", max_length=64)
    status: Literal["ok", "error", "warning"] = "ok"
    error_code: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_.-]*$")
    duration_ms: int = Field(default=0, ge=0, le=86_400_000)
    input_tokens: int = Field(default=0, ge=0, le=10_000_000)
    output_tokens: int = Field(default=0, ge=0, le=10_000_000)
    input_bytes: int = Field(default=0, ge=0, le=1_000_000_000)
    output_bytes: int = Field(default=0, ge=0, le=1_000_000_000)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_bytes: int | None = Field(default=None, ge=0, le=2**63 - 1)
    process_uptime_seconds: int | None = Field(default=None, ge=0, le=10 * 365 * 86400)
    queue_depth: int | None = Field(default=None, ge=0, le=10_000_000)
    server_version: str = Field(default="", max_length=50)
    transport: Literal["stdio", "sse", "http", "streamable-http"] = "stdio"
    occurred_at: datetime


class TelemetryBatchRequest(BaseModel):
    """Agent 批量上报请求。"""

    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEventInput] = Field(min_length=1, max_length=_MAX_EVENT_BATCH)


class InventoryServerInput(BaseModel):
    """Redacted local MCP Server configuration identity."""

    model_config = ConfigDict(extra="forbid")

    server_name: str = Field(min_length=1, max_length=255)
    transport: Literal["stdio", "sse", "http", "streamable-http"] = "stdio"
    command_name: str = Field(default="", max_length=255)
    env_keys: list[str] = Field(default_factory=list, max_length=100)
    header_keys: list[str] = Field(default_factory=list, max_length=100)
    config_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    server_version: str = Field(default="", max_length=50)
    protocol_version: str = Field(default="", max_length=32)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    tool_count: int = Field(default=0, ge=0, le=100_000)
    running: bool = False
    enabled: bool = True

    @field_validator("env_keys", "header_keys", "capabilities")
    @classmethod
    def validate_safe_names(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if any(len(item) > 100 for item in normalized):
            raise ValueError("清单字段名称过长")
        return normalized


class InventoryErrorInput(BaseModel):
    """Non-sensitive configuration error category."""

    model_config = ConfigDict(extra="forbid")

    server_id: str = Field(default="", max_length=255)
    error_code: str = Field(default="configuration_error", max_length=64)


class InventorySnapshotRequest(BaseModel):
    """Complete redacted inventory for one authenticated device."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    gateway_version: str = Field(default="", max_length=50)
    runtime_version: str = Field(default="", max_length=50)
    platform: str = Field(default="", max_length=50, pattern=r"^[A-Za-z0-9_.-]*$")
    architecture: str = Field(default="", max_length=50, pattern=r"^[A-Za-z0-9_.-]*$")
    servers: list[InventoryServerInput] = Field(default_factory=list, max_length=500)
    configuration_errors: list[InventoryErrorInput] = Field(default_factory=list, max_length=500)
    reported_at: datetime


@dataclass(frozen=True)
class TelemetryIdentity:
    """经设备令牌验证的 Agent 身份。"""

    device_id: str
    user_id: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize_device(device: TelemetryDeviceModel) -> dict[str, str | None]:
    return {
        "id": device.id,
        "name": device.name,
        "agent_type": device.agent_type or DEFAULT_AGENT_TYPE,
        "gateway_version": device.gateway_version or "",
        "runtime_version": device.runtime_version or "",
        "platform": device.platform or "",
        "architecture": device.architecture or "",
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
    }


def _resolve_agent_filter(agent_type: str) -> str | None:
    if not agent_type.strip():
        return None
    try:
        return normalize_agent_type(agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _decode_string_list(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


async def get_telemetry_identity(
    authorization: str | None = Header(None),
) -> TelemetryIdentity:
    """校验设备令牌，浏览器 JWT 不能用于遥测写入。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要设备遥测令牌")
    token = authorization[7:].strip()
    if not token.startswith("mcpht_"):
        raise HTTPException(status_code=401, detail="设备遥测令牌无效")

    async with async_session_factory() as session:
        device = await session.scalar(
            select(TelemetryDeviceModel).where(
                TelemetryDeviceModel.token_hash == _hash_token(token),
                TelemetryDeviceModel.revoked_at.is_(None),
            )
        )
        if device is None:
            raise HTTPException(status_code=401, detail="设备遥测令牌无效或已撤销")
        device.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        return TelemetryIdentity(device_id=device.id, user_id=device.user_id)


@router.post("/telemetry/devices")
async def create_telemetry_device(
    data: DeviceCreateRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """为当前用户创建一枚仅能上报遥测的本地 Agent 凭证。"""
    token = f"mcpht_{secrets.token_urlsafe(32)}"
    device = TelemetryDeviceModel(
        id=uuid.uuid4().hex,
        user_id=user_id,
        name=data.name,
        agent_type=data.agent_type,
        token_hash=_hash_token(token),
    )
    async with async_session_factory() as session:
        session.add(device)
        await session.commit()
        await session.refresh(device)

    return {
        "success": True,
        "data": {
            "device": _serialize_device(device),
            "token": token,
        },
    }


@router.get("/telemetry/devices")
async def list_telemetry_devices(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """列出当前用户的设备，不返回令牌或哈希。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(TelemetryDeviceModel)
            .where(TelemetryDeviceModel.user_id == user_id)
            .order_by(TelemetryDeviceModel.created_at.desc())
        )
        devices = list(result.scalars())

    return {"success": True, "data": [_serialize_device(device) for device in devices]}


@router.post("/telemetry/devices/{device_id}/revoke")
async def revoke_telemetry_device(
    device_id: str,
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """撤销当前用户的设备令牌，后续事件将被拒绝。"""
    async with async_session_factory() as session:
        device = await session.scalar(
            select(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id == device_id,
                TelemetryDeviceModel.user_id == user_id,
            )
        )
        if device is None:
            raise HTTPException(status_code=404, detail="设备不存在")
        if device.revoked_at is None:
            device.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            await session.refresh(device)

    return {"success": True, "data": _serialize_device(device)}


@router.post("/telemetry/events")
async def ingest_telemetry_events(
    data: TelemetryBatchRequest,
    identity: TelemetryIdentity = Depends(get_telemetry_identity),
) -> dict[str, Any]:
    """接收设备批量遥测，按事件 ID 幂等写入。"""
    saved = 0
    duplicates = 0
    async with async_session_factory() as session:
        for event in data.events:
            occurred_at = event.occurred_at
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            stored_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
            try:
                async with session.begin_nested():
                    session.add(
                        TelemetryEventModel(
                            id=event.event_id,
                            user_id=identity.user_id,
                            device_id=identity.device_id,
                            event_type=event.event_type,
                            session_id=event.session_id,
                            server_id=event.server_id,
                            tool_name=event.tool_name,
                            operation=event.operation,
                            status=event.status,
                            error_code=event.error_code,
                            duration_ms=event.duration_ms,
                            input_tokens=event.input_tokens,
                            output_tokens=event.output_tokens,
                            input_bytes=event.input_bytes,
                            output_bytes=event.output_bytes,
                            cpu_percent=event.cpu_percent,
                            memory_bytes=event.memory_bytes,
                            process_uptime_seconds=event.process_uptime_seconds,
                            queue_depth=event.queue_depth,
                            server_version=event.server_version,
                            transport=event.transport,
                            occurred_at=stored_at,
                        )
                    )
                    await session.flush()
                    if event.event_type == "tool_call":
                        session.add(
                            UsageStatsModel(
                                server_id=event.server_id,
                                user_id=identity.user_id,
                                tool_name=event.tool_name,
                                status=event.status,
                                duration_ms=event.duration_ms,
                                token_count=event.input_tokens + event.output_tokens,
                                source_event_id=event.event_id,
                                created_at=stored_at,
                            )
                        )
                        await session.flush()
                saved += 1
            except IntegrityError:
                duplicates += 1
        await session.commit()

    return {
        "success": True,
        "data": {"saved": saved, "duplicates": duplicates},
    }


@router.post("/telemetry/inventory")
async def ingest_telemetry_inventory(
    data: InventorySnapshotRequest,
    identity: TelemetryIdentity = Depends(get_telemetry_identity),
) -> dict[str, Any]:
    """Replace one device's active inventory without storing secrets or full commands."""
    reported_at = data.reported_at
    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=timezone.utc)
    observed_at = reported_at.astimezone(timezone.utc).replace(tzinfo=None)
    errors = {error.server_id: error.error_code for error in data.configuration_errors}

    async with async_session_factory() as session:
        device = await session.scalar(
            select(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id == identity.device_id,
                TelemetryDeviceModel.user_id == identity.user_id,
            )
        )
        if device is not None:
            device.gateway_version = data.gateway_version
            device.runtime_version = data.runtime_version
            device.platform = data.platform
            device.architecture = data.architecture
        await session.execute(
            update(TelemetryInventoryModel)
            .where(TelemetryInventoryModel.device_id == identity.device_id)
            .values(active=False, last_seen_at=observed_at)
        )
        existing_result = await session.execute(
            select(TelemetryInventoryModel).where(
                TelemetryInventoryModel.device_id == identity.device_id
            )
        )
        existing = {row.server_name: row for row in existing_result.scalars()}

        for server in data.servers:
            row = existing.get(server.server_name)
            values = {
                "user_id": identity.user_id,
                "device_id": identity.device_id,
                "transport": server.transport,
                "command_name": server.command_name,
                "env_keys": json.dumps(server.env_keys, ensure_ascii=False),
                "header_keys": json.dumps(server.header_keys, ensure_ascii=False),
                "config_hash": server.config_hash,
                "server_version": server.server_version,
                "protocol_version": server.protocol_version,
                "capabilities": json.dumps(
                    sorted(set(server.capabilities)),
                    ensure_ascii=False,
                ),
                "tool_count": server.tool_count,
                "running": server.running,
                "enabled": server.enabled,
                "active": True,
                "configuration_error": errors.get(server.server_name, ""),
                "discovered_at": observed_at,
                "last_seen_at": observed_at,
            }
            if row is None:
                session.add(
                    TelemetryInventoryModel(
                        server_name=server.server_name,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        server_names = {server.server_name for server in data.servers}
        for error in data.configuration_errors:
            if not error.server_id or error.server_id in server_names:
                continue
            row = existing.get(error.server_id)
            error_hash = hashlib.sha256(
                f"configuration-error:{error.server_id}:{error.error_code}".encode()
            ).hexdigest()
            values = {
                "user_id": identity.user_id,
                "device_id": identity.device_id,
                "transport": "stdio",
                "command_name": "",
                "env_keys": "[]",
                "header_keys": "[]",
                "config_hash": error_hash,
                "protocol_version": "",
                "enabled": False,
                "active": True,
                "configuration_error": error.error_code,
                "discovered_at": observed_at,
                "last_seen_at": observed_at,
            }
            if row is None:
                session.add(
                    TelemetryInventoryModel(
                        server_name=error.server_id,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        await session.commit()

    return {
        "success": True,
        "data": {
            "snapshot_id": data.event_id,
            "server_count": len(data.servers),
            "configuration_error_count": len(data.configuration_errors),
        },
    }


def _time_window(days: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


@router.get("/telemetry/summary")
async def get_telemetry_summary(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """返回当前用户的真实 Agent 遥测聚合。"""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    call_filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        call_filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        calls_row = (
            await session.execute(
                select(
                    func.count(TelemetryEventModel.id),
                    func.coalesce(
                        func.sum(case((TelemetryEventModel.status == "ok", 1), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                        0,
                    ),
                    func.coalesce(func.sum(TelemetryEventModel.duration_ms), 0),
                    func.coalesce(func.sum(TelemetryEventModel.input_tokens), 0),
                    func.coalesce(func.sum(TelemetryEventModel.output_tokens), 0),
                    func.coalesce(func.sum(TelemetryEventModel.input_bytes), 0),
                    func.coalesce(func.sum(TelemetryEventModel.output_bytes), 0),
                    func.count(func.distinct(TelemetryEventModel.device_id)),
                    func.count(func.distinct(TelemetryEventModel.server_id)),
                    func.count(func.distinct(TelemetryEventModel.session_id)),
                    func.min(TelemetryEventModel.occurred_at),
                    func.max(TelemetryEventModel.occurred_at),
                )
                .select_from(TelemetryEventModel)
                .join(
                    TelemetryDeviceModel,
                    TelemetryDeviceModel.id == TelemetryEventModel.device_id,
                )
                .where(*call_filters)
            )
        ).one()

        last_seen_query = select(func.max(TelemetryDeviceModel.last_seen_at)).where(
            TelemetryDeviceModel.user_id == user_id,
            TelemetryDeviceModel.revoked_at.is_(None),
        )
        active_devices_query = select(func.count(TelemetryDeviceModel.id)).where(
            TelemetryDeviceModel.user_id == user_id,
            TelemetryDeviceModel.revoked_at.is_(None),
            TelemetryDeviceModel.last_seen_at
            >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3),
        )
        if selected_agent:
            last_seen_query = last_seen_query.where(
                TelemetryDeviceModel.agent_type == selected_agent
            )
            active_devices_query = active_devices_query.where(
                TelemetryDeviceModel.agent_type == selected_agent
            )
        last_seen = await session.scalar(last_seen_query)
        active_devices = int(await session.scalar(active_devices_query) or 0)

        queue_filters = [
            TelemetryEventModel.user_id == user_id,
            TelemetryEventModel.occurred_at >= since,
        ]
        if selected_agent:
            queue_filters.append(TelemetryDeviceModel.agent_type == selected_agent)
        max_queue_depth = int(
            await session.scalar(
                select(func.max(TelemetryEventModel.queue_depth))
                .select_from(TelemetryEventModel)
                .join(
                    TelemetryDeviceModel,
                    TelemetryDeviceModel.id == TelemetryEventModel.device_id,
                )
                .where(*queue_filters)
            )
            or 0
        )
        current_queue_depth = int(
            await session.scalar(
                select(TelemetryEventModel.queue_depth)
                .select_from(TelemetryEventModel)
                .join(
                    TelemetryDeviceModel,
                    TelemetryDeviceModel.id == TelemetryEventModel.device_id,
                )
                .where(*queue_filters)
                .order_by(TelemetryEventModel.occurred_at.desc())
                .limit(1)
            )
            or 0
        )

        total_calls = int(calls_row[0] or 0)
        p95_duration = 0
        if total_calls:
            percentile_offset = max(0, math.ceil(total_calls * 0.95) - 1)
            percentile_query = (
                select(TelemetryEventModel.duration_ms)
                .select_from(TelemetryEventModel)
                .join(
                    TelemetryDeviceModel,
                    TelemetryDeviceModel.id == TelemetryEventModel.device_id,
                )
                .where(*call_filters)
                .order_by(TelemetryEventModel.duration_ms)
                .offset(percentile_offset)
                .limit(1)
            )
            p95_duration = int(await session.scalar(percentile_query) or 0)

    ok_calls = int(calls_row[1] or 0)
    error_calls = int(calls_row[2] or 0)
    total_duration = int(calls_row[3] or 0)
    input_tokens = int(calls_row[4] or 0)
    output_tokens = int(calls_row[5] or 0)
    return {
        "success": True,
        "data": {
            "days": days,
            "agent_type": selected_agent,
            "total_calls": total_calls,
            "ok_calls": ok_calls,
            "error_calls": error_calls,
            "success_rate": round(ok_calls / total_calls * 100, 1) if total_calls else 0,
            "avg_duration_ms": round(total_duration / total_calls, 1) if total_calls else 0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_bytes": int(calls_row[6] or 0),
            "output_bytes": int(calls_row[7] or 0),
            "total_bytes": int(calls_row[6] or 0) + int(calls_row[7] or 0),
            "active_devices": active_devices,
            "active_servers": int(calls_row[9] or 0),
            "active_sessions": int(calls_row[10] or 0),
            "p95_duration_ms": p95_duration,
            "current_queue_depth": current_queue_depth,
            "max_queue_depth": max_queue_depth,
            "first_call_at": calls_row[11].isoformat() if calls_row[11] else None,
            "last_call_at": calls_row[12].isoformat() if calls_row[12] else None,
            "last_seen_at": last_seen.isoformat() if last_seen else None,
        },
    }


@router.get("/telemetry/servers")
async def get_telemetry_servers(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """按 Server 聚合当前用户的工具调用遥测。"""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                func.count(TelemetryEventModel.id).label("total_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "ok", 1), else_=0)),
                    0,
                ).label("ok_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                    0,
                ).label("error_calls"),
                func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                    "avg_duration_ms"
                ),
                func.coalesce(
                    func.sum(TelemetryEventModel.input_tokens + TelemetryEventModel.output_tokens),
                    0,
                ).label("total_tokens"),
                func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .group_by(TelemetryEventModel.server_id)
            .order_by(func.count(TelemetryEventModel.id).desc())
            .limit(100)
        )
        rows = result.fetchall()

    servers = []
    for row in rows:
        total_calls = int(row.total_calls or 0)
        ok_calls = int(row.ok_calls or 0)
        servers.append(
            {
                "server_id": row.server_id,
                "total_calls": total_calls,
                "ok_calls": ok_calls,
                "error_calls": int(row.error_calls or 0),
                "success_rate": round(ok_calls / total_calls * 100, 1) if total_calls else 0,
                "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
                "total_tokens": int(row.total_tokens or 0),
                "last_call_at": row.last_call_at.isoformat() if row.last_call_at else None,
            }
        )
    return {
        "success": True,
        "data": {
            "days": days,
            "agent_type": selected_agent,
            "servers": servers,
        },
    }


@router.get("/telemetry/agents")
async def get_telemetry_agents(
    days: int = Query(7, ge=1, le=365),
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """按已授权 Agent 类型汇总当前用户的真实遥测。"""
    since = _time_window(days)
    event_join = and_(
        TelemetryEventModel.device_id == TelemetryDeviceModel.id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    )
    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryDeviceModel.agent_type,
                func.count(TelemetryEventModel.id).label("total_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "ok", 1), else_=0)),
                    0,
                ).label("ok_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                    0,
                ).label("error_calls"),
                func.coalesce(
                    func.sum(TelemetryEventModel.input_tokens + TelemetryEventModel.output_tokens),
                    0,
                ).label("total_tokens"),
                func.count(func.distinct(TelemetryDeviceModel.id)).label("device_count"),
                func.max(TelemetryDeviceModel.last_seen_at).label("last_seen_at"),
            )
            .select_from(TelemetryDeviceModel)
            .outerjoin(TelemetryEventModel, event_join)
            .where(
                TelemetryDeviceModel.user_id == user_id,
                TelemetryDeviceModel.revoked_at.is_(None),
            )
            .group_by(TelemetryDeviceModel.agent_type)
            .order_by(func.count(TelemetryEventModel.id).desc())
        )
        rows = result.fetchall()

    agents = []
    for row in rows:
        total_calls = int(row.total_calls or 0)
        ok_calls = int(row.ok_calls or 0)
        agents.append(
            {
                "agent_type": row.agent_type or DEFAULT_AGENT_TYPE,
                "total_calls": total_calls,
                "ok_calls": ok_calls,
                "error_calls": int(row.error_calls or 0),
                "success_rate": (round(ok_calls / total_calls * 100, 1) if total_calls else 0),
                "total_tokens": int(row.total_tokens or 0),
                "device_count": int(row.device_count or 0),
                "last_seen_at": (row.last_seen_at.isoformat() if row.last_seen_at else None),
            }
        )
    return {"success": True, "data": {"days": days, "agents": agents}}


@router.get("/telemetry/tools")
async def get_telemetry_tools(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate calls by Server and tool without exposing arguments."""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                TelemetryEventModel.tool_name,
                func.count(TelemetryEventModel.id).label("total_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                    0,
                ).label("error_calls"),
                func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                    "avg_duration_ms"
                ),
                func.coalesce(
                    func.sum(
                        TelemetryEventModel.input_tokens + TelemetryEventModel.output_tokens
                    ),
                    0,
                ).label("total_tokens"),
                func.coalesce(
                    func.sum(TelemetryEventModel.input_bytes + TelemetryEventModel.output_bytes),
                    0,
                ).label("total_bytes"),
                func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .group_by(TelemetryEventModel.server_id, TelemetryEventModel.tool_name)
            .order_by(func.count(TelemetryEventModel.id).desc())
            .limit(200)
        )
        rows = result.fetchall()

    tools = []
    for row in rows:
        total_calls = int(row.total_calls or 0)
        error_calls = int(row.error_calls or 0)
        tools.append(
            {
                "server_id": row.server_id,
                "tool_name": row.tool_name,
                "total_calls": total_calls,
                "error_calls": error_calls,
                "success_rate": (
                    round((total_calls - error_calls) / total_calls * 100, 1)
                    if total_calls
                    else 0
                ),
                "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
                "total_tokens": int(row.total_tokens or 0),
                "total_bytes": int(row.total_bytes or 0),
                "last_call_at": row.last_call_at.isoformat() if row.last_call_at else None,
            }
        )
    return {"success": True, "data": {"days": days, "tools": tools}}


@router.get("/telemetry/operations")
async def get_telemetry_operations(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate tool, resource and prompt protocol operations."""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type.in_(["tool_call", "protocol_call"]),
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryEventModel.operation,
                func.count(TelemetryEventModel.id).label("total_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                    0,
                ).label("error_calls"),
                func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                    "avg_duration_ms"
                ),
                func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .group_by(TelemetryEventModel.operation)
            .order_by(func.count(TelemetryEventModel.id).desc())
        )
        rows = result.fetchall()

    return {
        "success": True,
        "data": {
            "days": days,
            "operations": [
                {
                    "operation": row.operation or "unknown",
                    "total_calls": int(row.total_calls or 0),
                    "error_calls": int(row.error_calls or 0),
                    "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
                    "last_call_at": (
                        row.last_call_at.isoformat() if row.last_call_at else None
                    ),
                }
                for row in rows
            ],
        },
    }


@router.get("/telemetry/timeseries")
async def get_telemetry_timeseries(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Return daily call, error, latency and Token trends."""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)
    bucket = func.date(TelemetryEventModel.occurred_at).label("bucket")

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                bucket,
                func.count(TelemetryEventModel.id).label("total_calls"),
                func.coalesce(
                    func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                    0,
                ).label("error_calls"),
                func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                    "avg_duration_ms"
                ),
                func.coalesce(
                    func.sum(
                        TelemetryEventModel.input_tokens + TelemetryEventModel.output_tokens
                    ),
                    0,
                ).label("total_tokens"),
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .group_by(bucket)
            .order_by(bucket)
        )
        rows = result.fetchall()

    return {
        "success": True,
        "data": {
            "days": days,
            "points": [
                {
                    "date": str(row.bucket),
                    "total_calls": int(row.total_calls or 0),
                    "error_calls": int(row.error_calls or 0),
                    "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
                    "total_tokens": int(row.total_tokens or 0),
                }
                for row in rows
            ],
        },
    }


@router.get("/telemetry/resources")
async def get_telemetry_resources(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate sampled local CPU, memory and process uptime by Server."""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "resource_sample",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                func.count(TelemetryEventModel.id).label("sample_count"),
                func.coalesce(func.avg(TelemetryEventModel.cpu_percent), 0).label("avg_cpu"),
                func.coalesce(func.max(TelemetryEventModel.cpu_percent), 0).label("max_cpu"),
                func.coalesce(func.avg(TelemetryEventModel.memory_bytes), 0).label(
                    "avg_memory"
                ),
                func.coalesce(func.max(TelemetryEventModel.memory_bytes), 0).label(
                    "max_memory"
                ),
                func.coalesce(func.max(TelemetryEventModel.process_uptime_seconds), 0).label(
                    "process_uptime_seconds"
                ),
                func.max(TelemetryEventModel.occurred_at).label("last_sample_at"),
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .group_by(TelemetryEventModel.server_id)
            .order_by(func.max(TelemetryEventModel.memory_bytes).desc())
        )
        rows = result.fetchall()

    return {
        "success": True,
        "data": {
            "days": days,
            "resources": [
                {
                    "server_id": row.server_id,
                    "sample_count": int(row.sample_count or 0),
                    "avg_cpu_percent": round(float(row.avg_cpu or 0), 1),
                    "max_cpu_percent": round(float(row.max_cpu or 0), 1),
                    "avg_memory_bytes": int(row.avg_memory or 0),
                    "max_memory_bytes": int(row.max_memory or 0),
                    "process_uptime_seconds": int(row.process_uptime_seconds or 0),
                    "last_sample_at": (
                        row.last_sample_at.isoformat() if row.last_sample_at else None
                    ),
                }
                for row in rows
            ],
        },
    }


@router.get("/telemetry/errors")
async def get_telemetry_errors(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate non-sensitive error categories."""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.status == "error",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                TelemetryEventModel.error_code,
                func.count(TelemetryEventModel.id).label("error_count"),
                func.max(TelemetryEventModel.occurred_at).label("last_seen_at"),
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .group_by(TelemetryEventModel.server_id, TelemetryEventModel.error_code)
            .order_by(func.count(TelemetryEventModel.id).desc())
            .limit(100)
        )
        rows = result.fetchall()

    return {
        "success": True,
        "data": {
            "days": days,
            "errors": [
                {
                    "server_id": row.server_id,
                    "error_code": row.error_code or "unknown",
                    "count": int(row.error_count or 0),
                    "last_seen_at": (
                        row.last_seen_at.isoformat() if row.last_seen_at else None
                    ),
                }
                for row in rows
            ],
        },
    }


@router.get("/telemetry/lifecycle")
async def get_telemetry_lifecycle(
    days: int = Query(7, ge=1, le=365),
    agent_type: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Return recent MCP Server start, stop, failure and exit events."""
    since = _time_window(days)
    selected_agent = _resolve_agent_filter(agent_type)
    filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "server_lifecycle",
        TelemetryEventModel.occurred_at >= since,
    ]
    if selected_agent:
        filters.append(TelemetryDeviceModel.agent_type == selected_agent)

    async with async_session_factory() as session:
        result = await session.execute(
            select(
                TelemetryEventModel.server_id,
                TelemetryEventModel.operation,
                TelemetryEventModel.status,
                TelemetryEventModel.duration_ms,
                TelemetryEventModel.error_code,
                TelemetryEventModel.server_version,
                TelemetryEventModel.occurred_at,
            )
            .select_from(TelemetryEventModel)
            .join(
                TelemetryDeviceModel,
                TelemetryDeviceModel.id == TelemetryEventModel.device_id,
            )
            .where(*filters)
            .order_by(TelemetryEventModel.occurred_at.desc())
            .limit(100)
        )
        rows = result.fetchall()

    return {
        "success": True,
        "data": {
            "days": days,
            "events": [
                {
                    "server_id": row.server_id,
                    "operation": row.operation or "unknown",
                    "status": row.status or "warning",
                    "duration_ms": int(row.duration_ms or 0),
                    "error_code": row.error_code or "",
                    "server_version": row.server_version or "",
                    "occurred_at": row.occurred_at.isoformat(),
                }
                for row in rows
            ],
        },
    }


@router.get("/telemetry/inventory")
async def get_telemetry_inventory(
    user_id: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the current user's device-reported local MCP inventory."""
    online_since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=3)
    async with async_session_factory() as session:
        device_result = await session.execute(
            select(TelemetryDeviceModel)
            .where(
                TelemetryDeviceModel.user_id == user_id,
                TelemetryDeviceModel.revoked_at.is_(None),
            )
            .order_by(TelemetryDeviceModel.created_at)
        )
        devices = list(device_result.scalars())
        inventory_result = await session.execute(
            select(TelemetryInventoryModel).where(
                TelemetryInventoryModel.user_id == user_id,
                TelemetryInventoryModel.active == True,  # noqa: E712
            )
        )
        inventory_rows = list(inventory_result.scalars())

    inventory_by_device: dict[str, list[TelemetryInventoryModel]] = {}
    for row in inventory_rows:
        inventory_by_device.setdefault(row.device_id, []).append(row)

    serialized_devices: list[dict[str, Any]] = []
    all_server_names: set[str] = set()
    for device in devices:
        rows = sorted(
            inventory_by_device.get(device.id, []),
            key=lambda row: row.server_name,
        )
        all_server_names.update(row.server_name for row in rows)
        serialized_devices.append(
            {
                **_serialize_device(device),
                "online": bool(device.last_seen_at and device.last_seen_at >= online_since),
                "server_count": len(rows),
                "servers": [
                    {
                        "server_name": row.server_name,
                        "transport": row.transport,
                        "command_name": row.command_name,
                        "env_keys": _decode_string_list(row.env_keys),
                        "header_keys": _decode_string_list(row.header_keys),
                        "config_hash": row.config_hash,
                        "server_version": row.server_version or "",
                        "protocol_version": row.protocol_version or "",
                        "capabilities": _decode_string_list(row.capabilities),
                        "tool_count": int(row.tool_count or 0),
                        "running": bool(row.running),
                        "enabled": bool(row.enabled),
                        "configuration_error": row.configuration_error,
                        "last_seen_at": row.last_seen_at.isoformat(),
                    }
                    for row in rows
                ],
            }
        )

    device_labels = {
        device["id"]: f"{device['agent_type']} · {device['name']}"
        for device in serialized_devices
    }
    comparisons = []
    conflicts = []
    for server_name in sorted(all_server_names):
        matching_rows = [row for row in inventory_rows if row.server_name == server_name]
        present_ids = {row.device_id for row in matching_rows}
        hashes = {row.config_hash for row in matching_rows}
        comparisons.append(
            {
                "server_name": server_name,
                "present_in": [
                    device_labels[device_id]
                    for device_id in device_labels
                    if device_id in present_ids
                ],
                "absent_in": [
                    device_labels[device_id]
                    for device_id in device_labels
                    if device_id not in present_ids
                ],
                "has_conflict": len(hashes) > 1,
            }
        )
        if len(hashes) > 1:
            conflicts.append(
                {
                    "server_name": server_name,
                    "devices": [
                        {
                            "device": device_labels.get(row.device_id, row.device_id),
                            "command_name": row.command_name,
                            "env_keys": _decode_string_list(row.env_keys),
                            "config_hash": row.config_hash,
                        }
                        for row in matching_rows
                    ],
                }
            )

    return {
        "success": True,
        "data": {
            "total_devices": len(serialized_devices),
            "online_devices": sum(1 for device in serialized_devices if device["online"]),
            "total_unique_servers": len(all_server_names),
            "devices": serialized_devices,
            "compare": comparisons,
            "conflicts": conflicts,
        },
    }
