"""Low-noise, user-scoped alert evaluation for local MCP telemetry."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from mcp_hub.core.version_policy import assess_version
from mcp_hub.db.database import async_session_factory
from mcp_hub.db.models import (
    AlertPreferenceModel,
    NotificationModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UsageStatsModel,
)
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AlertRule:
    """Public definition and default policy for one alert family."""

    rule: str
    label: str
    description: str
    default_threshold: float
    minimum_threshold: float
    maximum_threshold: float
    unit: str
    severity: str


ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        "gateway_offline",
        "Gateway 离线",
        "Gateway 曾经接入，但连续超过阈值没有心跳或运行事件。",
        3,
        3,
        1440,
        "分钟",
        "high",
    ),
    AlertRule(
        "server_initialization_failed",
        "Server 连续初始化失败",
        "同一个 Server 在最近窗口内连续多次初始化或启动失败。",
        2,
        2,
        20,
        "次",
        "high",
    ),
    AlertRule(
        "tool_error_rate",
        "工具错误率过高",
        "最近至少 5 次工具调用中，错误比例达到阈值。",
        30,
        1,
        100,
        "%",
        "high",
    ),
    AlertRule(
        "p95_latency",
        "P95 延迟过高",
        "最近至少 5 次工具调用的 P95 延迟达到阈值。",
        2000,
        100,
        86_400_000,
        "毫秒",
        "warning",
    ),
    AlertRule(
        "queue_backlog",
        "遥测队列持续积压",
        "同一设备至少两次心跳显示队列达到阈值，且最新心跳仍未恢复。",
        10,
        1,
        10_000_000,
        "条",
        "high",
    ),
    AlertRule(
        "device_revoked",
        "设备令牌已撤销",
        "设备令牌已被撤销，本地 Gateway 无法继续上报。",
        1,
        1,
        1,
        "状态",
        "high",
    ),
    AlertRule(
        "version_incompatible",
        "Gateway 版本不兼容",
        "Gateway 版本低于 Hub 的最低支持版本。",
        1,
        1,
        1,
        "状态",
        "high",
    ),
    AlertRule(
        "multi_device_conflict",
        "多设备配置冲突",
        "多个设备上报了同名但配置指纹不同的本地 Server。",
        1,
        1,
        1,
        "状态",
        "warning",
    ),
)

ALERT_RULE_BY_NAME = {rule.rule: rule for rule in ALERT_RULES}
_LIFECYCLE_WINDOW = timedelta(minutes=30)
_CALL_WINDOW = timedelta(hours=1)
_QUEUE_WINDOW = timedelta(minutes=15)


def alert_rule_definition(rule: str) -> AlertRule:
    """Return a rule definition or raise a stable validation error."""
    try:
        return ALERT_RULE_BY_NAME[rule]
    except KeyError as exc:
        raise ValueError(f"未知告警规则: {rule}") from exc


def alert_preferences_payload(
    preferences: dict[str, AlertPreferenceModel],
) -> list[dict[str, Any]]:
    """Serialize effective settings without exposing database internals."""
    payload: list[dict[str, Any]] = []
    for definition in ALERT_RULES:
        preference = preferences.get(definition.rule)
        threshold = (
            float(preference.threshold)
            if preference is not None
            else definition.default_threshold
        )
        enabled = preference.enabled if preference is not None else True
        payload.append(
            {
                "rule": definition.rule,
                "label": definition.label,
                "description": definition.description,
                "enabled": bool(enabled),
                "threshold": threshold,
                "default_threshold": definition.default_threshold,
                "minimum_threshold": definition.minimum_threshold,
                "maximum_threshold": definition.maximum_threshold,
                "unit": definition.unit,
                "severity": definition.severity,
            }
        )
    return payload


def _alert_key(rule: str, scope: str) -> str:
    digest = hashlib.sha256(f"{rule}|{scope}".encode()).hexdigest()
    return f"{rule}:{digest[:32]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _p95(values: list[int]) -> int:
    ordered = sorted(max(0, int(value)) for value in values)
    if not ordered:
        return 0
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _preference_values(
    rows: list[AlertPreferenceModel],
) -> dict[str, tuple[bool, float]]:
    return {
        row.rule: (bool(row.enabled), float(row.threshold))
        for row in rows
        if row.rule in ALERT_RULE_BY_NAME
    }


def _rule_enabled(
    preferences: dict[str, tuple[bool, float]],
    definition: AlertRule,
) -> tuple[bool, float]:
    enabled, threshold = preferences.get(
        definition.rule,
        (True, definition.default_threshold),
    )
    return enabled, threshold


async def _sync_alert(
    session: Any,
    *,
    user_id: str,
    definition: AlertRule,
    scope: str,
    active: bool,
    title: str,
    message: str,
    server_id: str,
    link: str,
    observed_value: str,
    now: datetime,
    enabled: bool,
) -> None:
    key = _alert_key(definition.rule, scope)
    alert = await session.scalar(
        select(NotificationModel).where(
            NotificationModel.user_id == user_id,
            NotificationModel.alert_key == key,
        )
    )
    if not enabled:
        if alert is not None and alert.status == "active":
            alert.status = "suppressed"
            alert.is_read = True
            alert.last_seen_at = now
        return

    if active:
        if alert is None:
            session.add(
                NotificationModel(
                    user_id=user_id,
                    type="alert",
                    title=title,
                    message=message,
                    server_id=server_id,
                    link=link,
                    is_read=False,
                    alert_rule=definition.rule,
                    alert_key=key,
                    severity=definition.severity,
                    status="active",
                    occurrence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    observed_value=observed_value,
                )
            )
            return
        if alert.status != "active":
            alert.occurrence_count = int(alert.occurrence_count or 0) + 1
            alert.first_seen_at = now
            alert.resolved_at = None
            alert.is_read = False
        alert.status = "active"
        alert.title = title
        alert.message = message
        alert.server_id = server_id
        alert.link = link
        alert.last_seen_at = now
        alert.observed_value = observed_value
        return

    if alert is not None and alert.status == "active":
        alert.status = "resolved"
        alert.resolved_at = now
        alert.last_seen_at = now
        alert.is_read = True


async def evaluate_user_alerts(
    user_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Evaluate enabled rules and reconcile alert lifecycle for one user."""
    evaluated_at = now or _utc_now()
    async with async_session_factory() as session:
        preference_rows = list(
            (
                await session.execute(
                    select(AlertPreferenceModel).where(
                        AlertPreferenceModel.user_id == user_id
                    )
                )
            ).scalars()
        )
        preferences = _preference_values(preference_rows)
        devices = list(
            (
                await session.execute(
                    select(TelemetryDeviceModel).where(
                        TelemetryDeviceModel.user_id == user_id
                    )
                )
            ).scalars()
        )
        recent_events = list(
            (
                await session.execute(
                    select(TelemetryEventModel).where(
                        TelemetryEventModel.user_id == user_id,
                        TelemetryEventModel.occurred_at
                        >= evaluated_at - max(_LIFECYCLE_WINDOW, _CALL_WINDOW),
                    )
                )
            ).scalars()
        )
        legacy_usage_rows = list(
            (
                await session.execute(
                    select(UsageStatsModel).where(
                        UsageStatsModel.user_id == user_id,
                        UsageStatsModel.created_at.is_not(None),
                        UsageStatsModel.created_at
                        >= evaluated_at - _CALL_WINDOW,
                        UsageStatsModel.source_event_id.is_(None),
                    )
                )
            ).scalars()
        )
        inventory_rows = list(
            (
                await session.execute(
                    select(TelemetryInventoryModel).where(
                        TelemetryInventoryModel.user_id == user_id,
                        TelemetryInventoryModel.active == True,  # noqa: E712
                    )
                )
            ).scalars()
        )

        current: dict[str, list[dict[str, str]]] = defaultdict(list)

        definition = alert_rule_definition("gateway_offline")
        enabled, threshold = _rule_enabled(preferences, definition)
        if enabled:
            cutoff = evaluated_at - timedelta(minutes=threshold)
            for device in devices:
                if (
                    device.gateway_first_seen_at is not None
                    and device.gateway_last_seen_at is not None
                    and device.gateway_last_seen_at < cutoff
                    and device.revoked_at is None
                ):
                    current[definition.rule].append(
                        {
                            "scope": device.id,
                            "title": f"Gateway 离线: {device.name}",
                            "message": (
                                f"{device.agent_type} Gateway 已超过 {threshold:g} 分钟"
                                "没有心跳或运行事件。"
                            ),
                            "server_id": "",
                            "link": "/monitor",
                            "observed_value": device.gateway_last_seen_at.isoformat(),
                        }
                    )

        definition = alert_rule_definition("device_revoked")
        enabled, _threshold = _rule_enabled(preferences, definition)
        if enabled:
            for device in devices:
                if device.revoked_at is not None:
                    current[definition.rule].append(
                        {
                            "scope": device.id,
                            "title": f"设备令牌已撤销: {device.name}",
                            "message": "本地 Gateway 无法继续上报，请创建新设备并重新接入。",
                            "server_id": "",
                            "link": "/monitor",
                            "observed_value": device.revoked_at.isoformat(),
                        }
                    )

        definition = alert_rule_definition("version_incompatible")
        enabled, _threshold = _rule_enabled(preferences, definition)
        if enabled:
            for device in devices:
                assessment = assess_version(device.gateway_version or "")
                if assessment.status in {"upgrade_required", "blocked"}:
                    current[definition.rule].append(
                        {
                            "scope": device.id,
                            "title": f"Gateway 版本不兼容: {device.name}",
                            "message": assessment.message,
                            "server_id": "",
                            "link": "/monitor",
                            "observed_value": device.gateway_version or "",
                        }
                    )

        definition = alert_rule_definition("server_initialization_failed")
        enabled, threshold = _rule_enabled(preferences, definition)
        lifecycle_by_server: dict[str, list[TelemetryEventModel]] = defaultdict(list)
        for event in recent_events:
            if (
                event.event_type == "server_lifecycle"
                and event.operation
                in {"initialization_failed", "spawn_failed", "started"}
                and event.server_id
                and event.occurred_at >= evaluated_at - _LIFECYCLE_WINDOW
            ):
                lifecycle_by_server[event.server_id].append(event)
        if enabled:
            for server_id, events in lifecycle_by_server.items():
                ordered = sorted(events, key=lambda item: item.occurred_at, reverse=True)
                consecutive_failures = 0
                latest_failure: TelemetryEventModel | None = None
                for event in ordered:
                    if (
                        event.status == "error"
                        and event.operation in {"initialization_failed", "spawn_failed"}
                    ):
                        consecutive_failures += 1
                        latest_failure = latest_failure or event
                    else:
                        break
                if consecutive_failures >= int(threshold) and latest_failure is not None:
                    current[definition.rule].append(
                        {
                            "scope": server_id,
                            "title": f"Server 连续初始化失败: {server_id}",
                            "message": (
                                f"最近 30 分钟连续失败 {consecutive_failures} 次，"
                                "请检查本地 Server 配置和 Agent doctor。"
                            ),
                            "server_id": server_id,
                            "link": "/local",
                            "observed_value": (
                                latest_failure.error_code or latest_failure.operation
                            ),
                        }
                    )

        call_samples_by_server: dict[str, list[tuple[datetime, str, int]]] = defaultdict(list)
        for event in recent_events:
            if (
                event.event_type == "tool_call"
                and event.server_id
                and event.occurred_at >= evaluated_at - _CALL_WINDOW
            ):
                call_samples_by_server[event.server_id].append(
                    (
                        event.occurred_at,
                        event.status or "ok",
                        int(event.duration_ms or 0),
                    )
                )
        for usage in legacy_usage_rows:
            if usage.server_id and usage.created_at is not None:
                call_samples_by_server[usage.server_id].append(
                    (
                        usage.created_at,
                        usage.status or "ok",
                        int(usage.duration_ms or 0),
                    )
                )

        definition = alert_rule_definition("tool_error_rate")
        enabled, threshold = _rule_enabled(preferences, definition)
        if enabled:
            for server_id, samples in call_samples_by_server.items():
                sample = sorted(samples, key=lambda item: item[0], reverse=True)[:20]
                errors = sum(1 for _time, status, _duration in sample if status == "error")
                error_rate = errors / len(sample) * 100 if sample else 0
                if len(sample) >= 5 and error_rate >= threshold:
                    current[definition.rule].append(
                        {
                            "scope": server_id,
                            "title": f"工具错误率过高: {server_id}",
                            "message": (
                                f"最近 {len(sample)} 次调用错误率为 {error_rate:.1f}%"
                                f"，已达到 {threshold:g}% 阈值。"
                            ),
                            "server_id": server_id,
                            "link": "/monitor",
                            "observed_value": f"{error_rate:.1f}%",
                        }
                    )

        definition = alert_rule_definition("p95_latency")
        enabled, threshold = _rule_enabled(preferences, definition)
        if enabled:
            for server_id, samples in call_samples_by_server.items():
                sample = sorted(samples, key=lambda item: item[0], reverse=True)[:20]
                p95 = _p95([duration for _time, _status, duration in sample])
                if len(sample) >= 5 and p95 >= threshold:
                    current[definition.rule].append(
                        {
                            "scope": server_id,
                            "title": f"P95 延迟过高: {server_id}",
                            "message": (
                                f"最近 {len(sample)} 次调用 P95 为 {p95}ms，"
                                f"已达到 {threshold:g}ms 阈值。"
                            ),
                            "server_id": server_id,
                            "link": "/monitor",
                            "observed_value": f"{p95}ms",
                        }
                    )

        definition = alert_rule_definition("queue_backlog")
        enabled, threshold = _rule_enabled(preferences, definition)
        if enabled:
            queue_by_device: dict[str, list[TelemetryEventModel]] = defaultdict(list)
            for event in recent_events:
                if (
                    event.event_type == "heartbeat"
                    and event.device_id
                    and event.queue_depth is not None
                    and event.occurred_at >= evaluated_at - _QUEUE_WINDOW
                ):
                    queue_by_device[event.device_id].append(event)
            for device_id, events in queue_by_device.items():
                ordered = sorted(events, key=lambda item: item.occurred_at)
                high_events = [
                    event for event in ordered if int(event.queue_depth or 0) >= threshold
                ]
                if len(high_events) >= 2 and int(ordered[-1].queue_depth or 0) >= threshold:
                    current[definition.rule].append(
                        {
                            "scope": device_id,
                            "title": "遥测队列持续积压",
                            "message": (
                                f"设备最近 {len(high_events)} 次心跳达到 {threshold:g} 条"
                                "以上，最新队列仍未恢复。"
                            ),
                            "server_id": "",
                            "link": "/monitor",
                            "observed_value": str(ordered[-1].queue_depth or 0),
                        }
                    )

        definition = alert_rule_definition("multi_device_conflict")
        enabled, _threshold = _rule_enabled(preferences, definition)
        inventory_by_name: dict[str, set[str]] = defaultdict(set)
        for row in inventory_rows:
            if row.server_name and row.config_hash:
                inventory_by_name[row.server_name].add(row.config_hash)
        if enabled:
            for server_name, hashes in inventory_by_name.items():
                if len(hashes) > 1:
                    current[definition.rule].append(
                        {
                            "scope": server_name,
                            "title": f"多设备配置冲突: {server_name}",
                            "message": "多个本地设备上报了不同配置指纹，请在本地清单中比较。",
                            "server_id": server_name,
                            "link": "/local",
                            "observed_value": f"{len(hashes)} 个配置指纹",
                        }
                    )

        existing_alerts = list(
            (
                await session.execute(
                    select(NotificationModel).where(
                        NotificationModel.user_id == user_id,
                        NotificationModel.type == "alert",
                        NotificationModel.alert_key.is_not(None),
                    )
                )
            ).scalars()
        )
        active_count = 0
        resolved_count = 0
        suppressed_count = 0
        for definition in ALERT_RULES:
            enabled, _threshold = _rule_enabled(preferences, definition)
            observed = current.get(definition.rule, [])
            observed_keys = {
                _alert_key(definition.rule, item["scope"]) for item in observed
            }
            for item in observed:
                await _sync_alert(
                    session,
                    user_id=user_id,
                    definition=definition,
                    scope=item["scope"],
                    active=True,
                    title=item["title"],
                    message=item["message"],
                    server_id=item["server_id"],
                    link=item["link"],
                    observed_value=item["observed_value"],
                    now=evaluated_at,
                    enabled=enabled,
                )
                active_count += 1
            for alert in existing_alerts:
                if alert.alert_rule != definition.rule:
                    continue
                if not enabled:
                    if alert.status == "active":
                        alert.status = "suppressed"
                        alert.last_seen_at = evaluated_at
                        alert.is_read = True
                        suppressed_count += 1
                elif alert.alert_key not in observed_keys and alert.status == "active":
                    alert.status = "resolved"
                    alert.resolved_at = evaluated_at
                    alert.last_seen_at = evaluated_at
                    alert.is_read = True
                    resolved_count += 1
        await session.commit()
    return {
        "active": active_count,
        "resolved": resolved_count,
        "suppressed": suppressed_count,
    }


async def evaluate_user_alerts_safely(user_id: str) -> None:
    """Evaluate alerts without making telemetry or notification reads fail."""
    try:
        await evaluate_user_alerts(user_id)
    except Exception:
        logger.warning("alerts.evaluation_failed", user_id=user_id, exc_info=True)


async def evaluate_all_users_alerts_safely() -> None:
    """Evaluate alert rules for every user with an enrolled telemetry device."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(TelemetryDeviceModel.user_id).distinct()
            )
            user_ids = [str(user_id) for user_id in result.scalars() if user_id]
        for user_id in user_ids:
            await evaluate_user_alerts_safely(user_id)
    except Exception:
        logger.warning("alerts.periodic_evaluation_failed", exc_info=True)
