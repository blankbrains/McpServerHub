"""本地 MCP Agent 遥测设备与事件 API。"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from mcp_hub.api.dependencies import get_current_user
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import TelemetryDeviceModel, TelemetryEventModel
from mcp_hub.logging_config import get_logger

router = APIRouter(tags=["telemetry"])
logger = get_logger(__name__)
_MAX_EVENT_BATCH = 100


class DeviceCreateRequest(BaseModel):
    """创建本地 Agent 设备凭证的输入。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("设备名称不能为空")
        return normalized


class TelemetryEventInput(BaseModel):
    """无敏感载荷的最小化遥测事件。"""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    event_type: Literal["heartbeat", "server_lifecycle", "tool_call", "resource_sample", "error_event"]
    server_id: str = Field(default="", max_length=255)
    tool_name: str = Field(default="", max_length=255)
    status: Literal["ok", "error", "warning"] = "ok"
    duration_ms: int = Field(default=0, ge=0, le=86_400_000)
    input_tokens: int = Field(default=0, ge=0, le=10_000_000)
    output_tokens: int = Field(default=0, ge=0, le=10_000_000)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_bytes: int | None = Field(default=None, ge=0, le=2**63 - 1)
    occurred_at: datetime


class TelemetryBatchRequest(BaseModel):
    """Agent 批量上报请求。"""

    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEventInput] = Field(min_length=1, max_length=_MAX_EVENT_BATCH)


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
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
    }


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
):
    """为当前用户创建一枚仅能上报遥测的本地 Agent 凭证。"""
    token = f"mcpht_{secrets.token_urlsafe(32)}"
    device = TelemetryDeviceModel(
        id=uuid.uuid4().hex,
        user_id=user_id,
        name=data.name,
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
):
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
):
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
):
    """接收设备批量遥测，按事件 ID 幂等写入。"""
    saved = 0
    duplicates = 0
    async with async_session_factory() as session:
        for event in data.events:
            occurred_at = event.occurred_at
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            try:
                async with session.begin_nested():
                    session.add(
                        TelemetryEventModel(
                            id=event.event_id,
                            user_id=identity.user_id,
                            device_id=identity.device_id,
                            event_type=event.event_type,
                            server_id=event.server_id,
                            tool_name=event.tool_name,
                            status=event.status,
                            duration_ms=event.duration_ms,
                            input_tokens=event.input_tokens,
                            output_tokens=event.output_tokens,
                            cpu_percent=event.cpu_percent,
                            memory_bytes=event.memory_bytes,
                            occurred_at=occurred_at.astimezone(timezone.utc).replace(tzinfo=None),
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


def _time_window(days: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


@router.get("/telemetry/summary")
async def get_telemetry_summary(
    days: int = Query(7, ge=1, le=365),
    user_id: str = Depends(get_current_user),
):
    """返回当前用户的真实 Agent 遥测聚合。"""
    since = _time_window(days)
    call_filter = (
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    )
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
                    func.count(func.distinct(TelemetryEventModel.device_id)),
                    func.count(func.distinct(TelemetryEventModel.server_id)),
                ).where(*call_filter)
            )
        ).one()

        last_seen = await session.scalar(
            select(func.max(TelemetryDeviceModel.last_seen_at)).where(
                TelemetryDeviceModel.user_id == user_id,
                TelemetryDeviceModel.revoked_at.is_(None),
            )
        )

    total_calls = int(calls_row[0] or 0)
    ok_calls = int(calls_row[1] or 0)
    error_calls = int(calls_row[2] or 0)
    total_duration = int(calls_row[3] or 0)
    input_tokens = int(calls_row[4] or 0)
    output_tokens = int(calls_row[5] or 0)
    return {
        "success": True,
        "data": {
            "days": days,
            "total_calls": total_calls,
            "ok_calls": ok_calls,
            "error_calls": error_calls,
            "success_rate": round(ok_calls / total_calls * 100, 1) if total_calls else 0,
            "avg_duration_ms": round(total_duration / total_calls, 1) if total_calls else 0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "active_devices": int(calls_row[6] or 0),
            "active_servers": int(calls_row[7] or 0),
            "last_seen_at": last_seen.isoformat() if last_seen else None,
        },
    }


@router.get("/telemetry/servers")
async def get_telemetry_servers(
    days: int = Query(7, ge=1, le=365),
    user_id: str = Depends(get_current_user),
):
    """按 Server 聚合当前用户的工具调用遥测。"""
    since = _time_window(days)
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
                func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label("avg_duration_ms"),
                func.coalesce(
                    func.sum(TelemetryEventModel.input_tokens + TelemetryEventModel.output_tokens),
                    0,
                ).label("total_tokens"),
                func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
            )
            .where(
                TelemetryEventModel.user_id == user_id,
                TelemetryEventModel.event_type == "tool_call",
                TelemetryEventModel.occurred_at >= since,
            )
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
    return {"success": True, "data": {"days": days, "servers": servers}}
