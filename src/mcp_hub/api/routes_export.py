"""导出/分享 API。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import case, func, select

from mcp_hub import __version__
from mcp_hub.api.dependencies import get_current_user
from mcp_hub.api.routes_config import download_config
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import TelemetryDeviceModel, TelemetryEventModel

router = APIRouter(tags=["export"])


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_attachment(content: dict[str, object], filename: str) -> Response:
    return Response(
        content=json.dumps(content, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/config")
async def export_config(
    share: bool = False,
    user_id: str = Depends(get_current_user),
) -> Response:
    """导出当前用户启用的配置；share=true 时附带非敏感分享元数据。"""
    source = await download_config(agent="generic", user_id=user_id)
    config = json.loads(bytes(source.body))
    server_configs = config.get("mcpServers", {})

    if share:
        config["_meta"] = {
            "exported_by": "mcp-hub",
            "version": __version__,
            "server_count": len(server_configs) if isinstance(server_configs, dict) else 0,
        }

    fn = "mcp-hub-share.json" if share else "mcp-hub-config.json"
    return _json_attachment(
        config,
        fn,
    )


@router.get("/export/telemetry-report")
async def export_telemetry_report(
    days: int = Query(7, ge=1, le=365),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Export the current account's privacy-preserving telemetry aggregates."""
    generated_at = _utc_now_naive()
    since = generated_at - timedelta(days=days)
    call_filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type == "tool_call",
        TelemetryEventModel.occurred_at >= since,
    ]
    error_filters = [
        TelemetryEventModel.user_id == user_id,
        TelemetryEventModel.event_type.in_(["tool_call", "protocol_call", "server_lifecycle"]),
        TelemetryEventModel.status == "error",
        TelemetryEventModel.server_id != "",
        TelemetryEventModel.occurred_at >= since,
    ]

    async with async_session_factory() as session:
        summary_row = (
            await session.execute(
                select(
                    func.count(TelemetryEventModel.id).label("total_calls"),
                    func.coalesce(
                        func.sum(case((TelemetryEventModel.status == "ok", 1), else_=0)),
                        0,
                    ).label("ok_calls"),
                    func.coalesce(
                        func.sum(case((TelemetryEventModel.status == "error", 1), else_=0)),
                        0,
                    ).label("error_calls"),
                    func.coalesce(func.sum(TelemetryEventModel.duration_ms), 0).label(
                        "total_duration_ms"
                    ),
                    func.coalesce(
                        func.sum(
                            TelemetryEventModel.input_tokens
                            + TelemetryEventModel.output_tokens
                        ),
                        0,
                    ).label("total_tokens"),
                    func.count(func.distinct(TelemetryEventModel.server_id)).label(
                        "active_servers"
                    ),
                    func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
                ).where(*call_filters)
            )
        ).one()
        server_rows = (
            await session.execute(
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
                        func.sum(
                            TelemetryEventModel.input_tokens
                            + TelemetryEventModel.output_tokens
                        ),
                        0,
                    ).label("total_tokens"),
                    func.max(TelemetryEventModel.occurred_at).label("last_call_at"),
                )
                .where(*call_filters, TelemetryEventModel.server_id != "")
                .group_by(TelemetryEventModel.server_id)
                .order_by(func.count(TelemetryEventModel.id).desc())
                .limit(200)
            )
        ).all()
        agent_rows = (
            await session.execute(
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
                    func.coalesce(func.avg(TelemetryEventModel.duration_ms), 0).label(
                        "avg_duration_ms"
                    ),
                    func.coalesce(
                        func.sum(
                            TelemetryEventModel.input_tokens
                            + TelemetryEventModel.output_tokens
                        ),
                        0,
                    ).label("total_tokens"),
                )
                .select_from(TelemetryEventModel)
                .join(
                    TelemetryDeviceModel,
                    TelemetryDeviceModel.id == TelemetryEventModel.device_id,
                )
                .where(*call_filters)
                .group_by(TelemetryDeviceModel.agent_type)
                .order_by(func.count(TelemetryEventModel.id).desc())
            )
        ).all()
        error_rows = (
            await session.execute(
                select(
                    TelemetryEventModel.event_type,
                    TelemetryEventModel.server_id,
                    TelemetryEventModel.error_code,
                    func.count(TelemetryEventModel.id).label("error_count"),
                    func.max(TelemetryEventModel.occurred_at).label("last_seen_at"),
                )
                .where(*error_filters)
                .group_by(
                    TelemetryEventModel.event_type,
                    TelemetryEventModel.server_id,
                    TelemetryEventModel.error_code,
                )
                .order_by(func.count(TelemetryEventModel.id).desc())
                .limit(100)
            )
        ).all()

    total_calls = int(summary_row.total_calls or 0)
    ok_calls = int(summary_row.ok_calls or 0)
    report = {
        "report_type": "mcp_hub_account_telemetry",
        "schema_version": 1,
        "period": {
            "days": days,
            "started_at": since.isoformat(),
            "generated_at": generated_at.isoformat(),
        },
        "summary": {
            "total_calls": total_calls,
            "ok_calls": ok_calls,
            "error_calls": int(summary_row.error_calls or 0),
            "success_rate": round(ok_calls / total_calls * 100, 1) if total_calls else 0,
            "avg_duration_ms": round(
                int(summary_row.total_duration_ms or 0) / total_calls,
                1,
            )
            if total_calls
            else 0,
            "total_tokens": int(summary_row.total_tokens or 0),
            "active_servers": int(summary_row.active_servers or 0),
            "last_call_at": (
                summary_row.last_call_at.isoformat() if summary_row.last_call_at else None
            ),
        },
        "servers": [
            {
                "server_id": row.server_id,
                "total_calls": int(row.total_calls or 0),
                "ok_calls": int(row.ok_calls or 0),
                "error_calls": int(row.error_calls or 0),
                "success_rate": (
                    round(int(row.ok_calls or 0) / int(row.total_calls or 0) * 100, 1)
                    if row.total_calls
                    else 0
                ),
                "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
                "total_tokens": int(row.total_tokens or 0),
                "last_call_at": row.last_call_at.isoformat() if row.last_call_at else None,
            }
            for row in server_rows
        ],
        "agents": [
            {
                "agent_type": row.agent_type or "generic",
                "total_calls": int(row.total_calls or 0),
                "ok_calls": int(row.ok_calls or 0),
                "error_calls": int(row.error_calls or 0),
                "success_rate": (
                    round(int(row.ok_calls or 0) / int(row.total_calls or 0) * 100, 1)
                    if row.total_calls
                    else 0
                ),
                "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
                "total_tokens": int(row.total_tokens or 0),
            }
            for row in agent_rows
        ],
        "errors": [
            {
                "event_type": row.event_type,
                "server_id": row.server_id,
                "error_code": row.error_code or "unknown",
                "count": int(row.error_count or 0),
                "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
            }
            for row in error_rows
        ],
        "privacy": {
            "scope": "current_account_only",
            "excluded_fields": [
                "user_id",
                "device_id",
                "device_name",
                "session_id",
                "tool_name",
                "request_content",
                "response_content",
                "command",
                "arguments",
                "environment_variable_values",
                "request_headers",
                "authentication_tokens",
            ],
        },
    }
    return _json_attachment(report, f"mcp-hub-telemetry-report-{days}d.json")
