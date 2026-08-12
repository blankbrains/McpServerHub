"""Regression tests for low-noise, user-scoped telemetry alerts."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from mcp_hub.api.routes_notifications import (
    AlertPreferenceUpdate,
    get_notification_settings,
    update_notification_setting,
)
from mcp_hub.core.alerts import evaluate_user_alerts
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    AlertPreferenceModel,
    Base,
    NotificationModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UsageStatsModel,
)

_NOW = datetime(2026, 8, 12, 12, 0, 0)


async def _prepare_alert_data(*user_ids: str) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        for user_id in user_ids:
            await session.execute(
                delete(NotificationModel).where(NotificationModel.user_id == user_id)
            )
            await session.execute(
                delete(AlertPreferenceModel).where(AlertPreferenceModel.user_id == user_id)
            )
            await session.execute(
                delete(TelemetryInventoryModel).where(
                    TelemetryInventoryModel.user_id == user_id
                )
            )
            await session.execute(
                delete(TelemetryEventModel).where(TelemetryEventModel.user_id == user_id)
            )
            await session.execute(
                delete(UsageStatsModel).where(UsageStatsModel.user_id == user_id)
            )
            await session.execute(
                delete(TelemetryDeviceModel).where(TelemetryDeviceModel.user_id == user_id)
            )
        await session.commit()


def _device(user_id: str, suffix: str, **values: object) -> TelemetryDeviceModel:
    return TelemetryDeviceModel(
        id=f"alert-device-{user_id}-{suffix}",
        user_id=user_id,
        name=f"{user_id} {suffix}",
        agent_type="codex",
        token_hash=f"{user_id}-{suffix}".ljust(64, "x")[:64],
        **values,
    )


def _tool_event(
    user_id: str,
    index: int,
    *,
    status: str = "error",
    occurred_at: datetime = _NOW,
    duration_ms: int = 100,
) -> TelemetryEventModel:
    return TelemetryEventModel(
        id=f"alert-event-{user_id}-{index:04d}",
        user_id=user_id,
        device_id=f"alert-device-{user_id}-one",
        event_type="tool_call",
        server_id="@alert/weather",
        tool_name="forecast",
        status=status,
        duration_ms=duration_ms,
        occurred_at=occurred_at,
    )


async def _alerts_for(user_id: str, rule: str) -> list[NotificationModel]:
    async with async_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(NotificationModel).where(
                        NotificationModel.user_id == user_id,
                        NotificationModel.alert_rule == rule,
                    )
                )
            ).scalars()
        )


async def test_tool_error_alert_requires_five_calls_deduplicates_and_recovers() -> None:
    user_id = "alert-rate-user"
    await _prepare_alert_data(user_id)
    async with async_session_factory() as session:
        session.add(_device(user_id, "one"))
        session.add_all(
            [
                _tool_event(user_id, index, occurred_at=_NOW - timedelta(minutes=index))
                for index in range(4)
            ]
        )
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW)
    assert await _alerts_for(user_id, "tool_error_rate") == []

    async with async_session_factory() as session:
        session.add(_tool_event(user_id, 5, occurred_at=_NOW))
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW)
    await evaluate_user_alerts(user_id, now=_NOW + timedelta(seconds=1))
    alerts = await _alerts_for(user_id, "tool_error_rate")
    assert len(alerts) == 1
    assert alerts[0].status == "active"
    assert alerts[0].occurrence_count == 1
    assert alerts[0].is_read is False

    async with async_session_factory() as session:
        session.add_all(
            [
                _tool_event(
                    user_id,
                    10 + index,
                    status="ok",
                    occurred_at=_NOW + timedelta(minutes=index + 1),
                )
                for index in range(15)
            ]
        )
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW + timedelta(minutes=20))
    alerts = await _alerts_for(user_id, "tool_error_rate")
    assert len(alerts) == 1
    assert alerts[0].status == "resolved"
    assert alerts[0].is_read is True
    assert alerts[0].resolved_at is not None


async def test_legacy_usage_errors_and_user_settings_are_isolated() -> None:
    alice = "alert-legacy-alice"
    bob = "alert-legacy-bob"
    await _prepare_alert_data(alice, bob)
    async with async_session_factory() as session:
        session.add_all(
            [
                UsageStatsModel(
                    user_id=alice,
                    server_id="@alert/legacy",
                    tool_name="call",
                    status="error",
                    duration_ms=100,
                    created_at=_NOW - timedelta(minutes=index),
                )
                for index in range(5)
            ]
        )
        session.add_all(
            [
                UsageStatsModel(
                    user_id=bob,
                    server_id="@alert/legacy",
                    tool_name="call",
                    status="ok",
                    duration_ms=100,
                    created_at=_NOW - timedelta(minutes=index),
                )
                for index in range(5)
            ]
        )
        await session.commit()

    await evaluate_user_alerts(alice, now=_NOW)
    await evaluate_user_alerts(bob, now=_NOW)
    assert len(await _alerts_for(alice, "tool_error_rate")) == 1
    assert await _alerts_for(bob, "tool_error_rate") == []

    settings = await get_notification_settings(user_id=alice)
    assert len(settings["data"]["rules"]) == 8
    updated = await update_notification_setting(
        "tool_error_rate",
        AlertPreferenceUpdate(enabled=False, threshold=40),
        user_id=alice,
    )
    assert updated["data"] == {
        "rule": "tool_error_rate",
        "enabled": False,
        "threshold": 40,
    }
    alerts = await _alerts_for(alice, "tool_error_rate")
    assert alerts[0].status == "suppressed"
    assert alerts[0].is_read is True

    with pytest.raises(HTTPException, match="阈值必须在"):
        await update_notification_setting(
            "tool_error_rate",
            AlertPreferenceUpdate(enabled=True, threshold=101),
            user_id=alice,
        )
    with pytest.raises(HTTPException, match="未知告警规则"):
        await update_notification_setting(
            "not-a-rule",
            AlertPreferenceUpdate(enabled=True, threshold=1),
            user_id=alice,
        )


async def test_initialization_alert_requires_consecutive_failures() -> None:
    user_id = "alert-lifecycle-user"
    await _prepare_alert_data(user_id)
    device = _device(user_id, "one")
    async with async_session_factory() as session:
        session.add(device)
        session.add_all(
            [
                TelemetryEventModel(
                    id=f"alert-lifecycle-{index:04d}",
                    user_id=user_id,
                    device_id=device.id,
                    event_type="server_lifecycle",
                    server_id="@alert/lifecycle",
                    operation=operation,
                    status=status,
                    occurred_at=_NOW + timedelta(minutes=index),
                )
                for index, (operation, status) in enumerate(
                    [
                        ("initialization_failed", "error"),
                        ("initialization_failed", "error"),
                        ("started", "ok"),
                    ]
                )
            ]
        )
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW + timedelta(minutes=3))
    assert await _alerts_for(user_id, "server_initialization_failed") == []

    async with async_session_factory() as session:
        session.add_all(
            [
                TelemetryEventModel(
                    id=f"alert-lifecycle-{index:04d}",
                    user_id=user_id,
                    device_id=device.id,
                    event_type="server_lifecycle",
                    server_id="@alert/lifecycle",
                    operation="spawn_failed",
                    status="error",
                    occurred_at=_NOW + timedelta(minutes=index),
                )
                for index in (4, 5)
            ]
        )
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW + timedelta(minutes=6))
    alerts = await _alerts_for(user_id, "server_initialization_failed")
    assert len(alerts) == 1
    assert alerts[0].observed_value == "spawn_failed"


async def test_queue_offline_revocation_version_and_inventory_conflict_alerts() -> None:
    user_id = "alert-device-user"
    await _prepare_alert_data(user_id)
    stale_device = _device(
        user_id,
        "stale",
        gateway_version="0.1.0",
        gateway_first_seen_at=_NOW - timedelta(minutes=10),
        gateway_last_seen_at=_NOW - timedelta(minutes=5),
    )
    revoked_device = _device(
        user_id,
        "revoked",
        gateway_version="0.3.0",
        revoked_at=_NOW - timedelta(minutes=1),
    )
    queue_device = _device(user_id, "one", gateway_version="0.3.0")
    async with async_session_factory() as session:
        session.add_all([stale_device, revoked_device, queue_device])
        session.add_all(
            [
                TelemetryEventModel(
                    id=f"alert-queue-{index:04d}",
                    user_id=user_id,
                    device_id=queue_device.id,
                    event_type="heartbeat",
                    queue_depth=12,
                    occurred_at=_NOW + timedelta(minutes=index),
                )
                for index in (0, 1)
            ]
        )
        session.add_all(
            [
                TelemetryInventoryModel(
                    user_id=user_id,
                    device_id=device_id,
                    server_name="conflicting-server",
                    config_hash=config_hash,
                    discovered_at=_NOW,
                    last_seen_at=_NOW,
                )
                for device_id, config_hash in (
                    (stale_device.id, "a" * 64),
                    (revoked_device.id, "b" * 64),
                )
            ]
        )
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW + timedelta(minutes=2))
    assert len(await _alerts_for(user_id, "gateway_offline")) == 1
    assert len(await _alerts_for(user_id, "device_revoked")) == 1
    assert len(await _alerts_for(user_id, "version_incompatible")) == 1
    assert len(await _alerts_for(user_id, "queue_backlog")) == 1
    assert len(await _alerts_for(user_id, "multi_device_conflict")) == 1

    async with async_session_factory() as session:
        session.add(
            TelemetryEventModel(
                id="alert-queue-recovered",
                user_id=user_id,
                device_id=queue_device.id,
                event_type="heartbeat",
                queue_depth=0,
                occurred_at=_NOW + timedelta(minutes=3),
            )
        )
        await session.commit()

    await evaluate_user_alerts(user_id, now=_NOW + timedelta(minutes=4))
    queue_alerts = await _alerts_for(user_id, "queue_backlog")
    assert queue_alerts[0].status == "resolved"
