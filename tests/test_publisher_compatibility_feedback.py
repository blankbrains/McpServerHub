"""Privacy and ownership regression tests for publisher compatibility feedback."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, update

from mcp_hub.api.routes_publish import publisher_compatibility_feedback
from mcp_hub.api.routes_telemetry import (
    TelemetryContributionConsentUpdate,
    get_telemetry_contribution_consent,
    update_telemetry_contribution_consent,
)
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    Base,
    ServerModel,
    TelemetryContributionConsentModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserServerModel,
)

_LOCAL_NAME = "publisher-feedback-weather"
_SERVER_ID = f"@publisher/{_LOCAL_NAME}"
_AMBIGUOUS_SERVER_ID = f"@another/{_LOCAL_NAME}"
_PUBLISHER = "publisher-owner"
_CONTRIBUTORS = [f"feedback-user-{index}" for index in range(6)]


def _device_token_hash(device_id: str) -> str:
    return hashlib.sha256(f"publisher-feedback:{device_id}".encode()).hexdigest()


async def _prepare_feedback_data(
    *,
    ambiguous: bool = False,
    active_contributor_count: int = len(_CONTRIBUTORS),
) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await session.execute(
            delete(TelemetryEventModel).where(
                TelemetryEventModel.server_id.in_([_SERVER_ID, _LOCAL_NAME])
            )
        )
        await session.execute(
            delete(TelemetryInventoryModel).where(
                TelemetryInventoryModel.server_name == _LOCAL_NAME
            )
        )
        await session.execute(
            delete(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id.in_(
                    [f"feedback-device-{index}" for index in range(6)]
                )
            )
        )
        await session.execute(
            delete(TelemetryContributionConsentModel).where(
                TelemetryContributionConsentModel.user_id.in_(_CONTRIBUTORS + [_PUBLISHER])
            )
        )
        await session.execute(
            delete(UserServerModel).where(
                UserServerModel.server_id == _SERVER_ID,
                UserServerModel.user_id.in_(_CONTRIBUTORS + [_PUBLISHER]),
            )
        )
        await session.execute(
            delete(ServerModel).where(
                ServerModel.id.in_([_SERVER_ID, _AMBIGUOUS_SERVER_ID])
            )
        )
        session.add(
            ServerModel(
                id=_SERVER_ID,
                name=_LOCAL_NAME,
                display_name="Publisher Weather",
                author=_PUBLISHER,
            )
        )
        if ambiguous:
            session.add(
                ServerModel(
                    id=_AMBIGUOUS_SERVER_ID,
                    name=_LOCAL_NAME,
                    display_name="Another Weather",
                    author="another-owner",
                )
            )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for index, contributor in enumerate(_CONTRIBUTORS):
            device_id = f"feedback-device-{index}"
            session.add_all(
                [
                    UserServerModel(
                        user_id=contributor,
                        server_id=_SERVER_ID,
                        matched=True,
                    ),
                    TelemetryContributionConsentModel(
                        user_id=contributor,
                        enabled=True,
                    ),
                    TelemetryDeviceModel(
                        id=device_id,
                        user_id=contributor,
                        name=f"private-device-{index}",
                        agent_type="codex" if index < 5 else "cursor",
                        token_hash=_device_token_hash(device_id),
                    ),
                    TelemetryInventoryModel(
                        user_id=contributor,
                        device_id=device_id,
                        server_name=_LOCAL_NAME,
                        config_hash=f"{index + 10:x}" * 64,
                        active=True,
                        discovered_at=now,
                        last_seen_at=now,
                    ),
                ]
            )
            if index < active_contributor_count:
                session.add(
                    TelemetryEventModel(
                        id=f"feedback-event-{index:02d}",
                        user_id=contributor,
                        device_id=device_id,
                        event_type="tool_call",
                        server_id=_LOCAL_NAME,
                        tool_name="private-tool",
                        status="ok" if index != 1 else "error",
                        duration_ms=100 + index,
                        occurred_at=now,
                    )
                )
        # The publisher's own telemetry never counts toward the external cohort.
        session.add_all(
            [
                UserServerModel(user_id=_PUBLISHER, server_id=_SERVER_ID, matched=True),
                TelemetryContributionConsentModel(user_id=_PUBLISHER, enabled=True),
            ]
        )
        await session.commit()


async def test_contribution_consent_is_disabled_by_default_and_revocable() -> None:
    user_id = "feedback-consent-user"
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await session.execute(
            delete(TelemetryContributionConsentModel).where(
                TelemetryContributionConsentModel.user_id == user_id
            )
        )
        await session.commit()

    assert (await get_telemetry_contribution_consent(user_id=user_id))["data"] == {
        "enabled": False
    }
    enabled = await update_telemetry_contribution_consent(
        TelemetryContributionConsentUpdate(enabled=True),
        user_id=user_id,
    )
    assert enabled["data"] == {"enabled": True}
    disabled = await update_telemetry_contribution_consent(
        TelemetryContributionConsentUpdate(enabled=False),
        user_id=user_id,
    )
    assert disabled["data"] == {"enabled": False}


async def test_publisher_feedback_requires_opt_in_unique_mapping_and_k_anonymity() -> None:
    await _prepare_feedback_data()

    response = await publisher_compatibility_feedback(
        _SERVER_ID,
        user_id=_PUBLISHER,
    )
    data = response["data"]
    serialized = json.dumps(data, ensure_ascii=False)

    assert data["available"] is True
    assert data["days"] == 30
    assert data["contributor_cohort"] == "5-9"
    assert data["summary"] == {
        "activity": "low",
        "success_rate_band": "80-84%",
        "latency_band": "100_to_499ms",
    }
    assert data["agents"] == [
        {
            "agent_type": "codex",
            "contributor_cohort": "5-9",
            "activity": "low",
            "success_rate_band": "80-84%",
            "latency_band": "100_to_499ms",
        }
    ]
    for contributor in _CONTRIBUTORS:
        assert contributor not in serialized
    for forbidden in (
        "private-device",
        "private-tool",
        "device_id",
        "user_id",
        "tool_name",
        "total_calls",
        "avg_duration_ms",
    ):
        assert forbidden not in serialized

    await update_telemetry_contribution_consent(
        TelemetryContributionConsentUpdate(enabled=False),
        user_id=_CONTRIBUTORS[0],
    )
    await update_telemetry_contribution_consent(
        TelemetryContributionConsentUpdate(enabled=False),
        user_id=_CONTRIBUTORS[1],
    )
    revoked = await publisher_compatibility_feedback(
        _SERVER_ID,
        user_id=_PUBLISHER,
    )
    assert revoked["data"] == {
        "server_id": _SERVER_ID,
        "days": 30,
        "available": False,
        "minimum_contributors": 5,
        "contributor_cohort": "",
    }


async def test_publisher_feedback_rejects_non_owner_and_ambiguous_local_names() -> None:
    await _prepare_feedback_data()

    with pytest.raises(HTTPException) as exc_info:
        await publisher_compatibility_feedback(
            _SERVER_ID,
            user_id="not-the-publisher",
        )
    assert exc_info.value.status_code == 403

    await _prepare_feedback_data(ambiguous=True)
    response = await publisher_compatibility_feedback(
        _SERVER_ID,
        user_id=_PUBLISHER,
    )
    assert response["data"]["available"] is False


async def test_publisher_feedback_requires_five_contributors_with_actual_calls() -> None:
    await _prepare_feedback_data(active_contributor_count=4)

    response = await publisher_compatibility_feedback(
        _SERVER_ID,
        user_id=_PUBLISHER,
    )

    assert response["data"] == {
        "server_id": _SERVER_ID,
        "days": 30,
        "available": False,
        "minimum_contributors": 5,
        "contributor_cohort": "",
    }


async def test_publisher_feedback_requires_active_inventory_on_the_calling_device() -> None:
    await _prepare_feedback_data()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    alternate_ids = [f"feedback-secondary-device-{index}" for index in range(6)]

    async with async_session_factory() as session:
        await session.execute(
            delete(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id.in_(alternate_ids)
            )
        )
        for index, contributor in enumerate(_CONTRIBUTORS):
            alternate_id = alternate_ids[index]
            session.add(
                TelemetryDeviceModel(
                    id=alternate_id,
                    user_id=contributor,
                    name=f"secondary-device-{index}",
                    agent_type="codex",
                    token_hash=_device_token_hash(alternate_id),
                )
            )
            await session.execute(
                update(TelemetryEventModel)
                .where(TelemetryEventModel.id == f"feedback-event-{index:02d}")
                .values(device_id=alternate_id, occurred_at=now)
            )
        await session.commit()

    response = await publisher_compatibility_feedback(
        _SERVER_ID,
        user_id=_PUBLISHER,
    )

    assert response["data"] == {
        "server_id": _SERVER_ID,
        "days": 30,
        "available": False,
        "minimum_contributors": 5,
        "contributor_cohort": "",
    }
