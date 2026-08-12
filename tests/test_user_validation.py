"""Opt-in user validation funnel privacy and behavior regression tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from mcp_hub.api.routes_admin import admin_user_validation_analytics
from mcp_hub.api.routes_telemetry import (
    DeviceCreateRequest,
    InventorySnapshotRequest,
    TelemetryBatchRequest,
    TelemetryEventInput,
    UserValidationAssessmentUpdate,
    UserValidationEnrollmentUpdate,
    UserValidationStageInput,
    create_telemetry_device,
    get_telemetry_identity,
    get_user_validation,
    ingest_telemetry_events,
    ingest_telemetry_inventory,
    record_user_validation_stage,
    update_user_validation_assessment,
    update_user_validation_enrollment,
)
from mcp_hub.core.user_validation import validation_stage_id
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    Base,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserValidationAssessmentModel,
    UserValidationEnrollmentModel,
    UserValidationEventModel,
)

_USER_ID = "validation-study-user"
_OTHER_USER_ID = "validation-study-other"


async def _prepare_validation_data() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        user_ids = [_USER_ID, _OTHER_USER_ID]
        device_ids = ["validation-device-primary", "validation-device-other"]
        await session.execute(
            delete(UserValidationEventModel).where(
                UserValidationEventModel.user_id.in_(user_ids)
            )
        )
        await session.execute(
            delete(UserValidationAssessmentModel).where(
                UserValidationAssessmentModel.user_id.in_(user_ids)
            )
        )
        await session.execute(
            delete(UserValidationEnrollmentModel).where(
                UserValidationEnrollmentModel.user_id.in_(user_ids)
            )
        )
        await session.execute(
            delete(TelemetryEventModel).where(
                TelemetryEventModel.device_id.in_(device_ids)
            )
        )
        await session.execute(
            delete(TelemetryInventoryModel).where(
                TelemetryInventoryModel.device_id.in_(device_ids)
            )
        )
        await session.execute(
            delete(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id.in_(device_ids)
            )
        )
        await session.commit()


def _inventory_snapshot(
    event_id: str,
    *,
    source: str,
) -> InventorySnapshotRequest:
    return InventorySnapshotRequest(
        event_id=event_id,
        source=source,
        session_id="validation-session-0001",
        gateway_version="0.3.0",
        runtime_version="3.13.0",
        platform="windows",
        architecture="amd64",
        servers=[],
        configuration_errors=[],
        reported_at=datetime.now(timezone.utc),
    )


async def _enrolled_device() -> tuple[dict[str, object], object]:
    await update_user_validation_enrollment(
        UserValidationEnrollmentUpdate(
            enabled=True,
            participant_role="individual_user",
        ),
        user_id=_USER_ID,
    )
    created = await create_telemetry_device(
        DeviceCreateRequest(name="Validation workstation", agent_type="codex"),
        _USER_ID,
    )
    identity = await get_telemetry_identity(f"Bearer {created['data']['token']}")
    return created, identity


async def test_validation_requires_explicit_enrollment_and_deletes_on_withdrawal() -> None:
    await _prepare_validation_data()
    created = await create_telemetry_device(
        DeviceCreateRequest(name="Existing workstation", agent_type="codex"),
        _USER_ID,
    )
    device_id = str(created["data"]["device"]["id"])

    before = await get_user_validation(user_id=_USER_ID)
    assert before["data"] == {
        "enrolled": False,
        "participant_role": "individual_user",
        "stages": [],
        "assessment": None,
    }

    enrolled = await update_user_validation_enrollment(
        UserValidationEnrollmentUpdate(
            enabled=True,
            participant_role="server_publisher",
        ),
        user_id=_USER_ID,
    )
    assert enrolled["data"]["participant_role"] == "server_publisher"
    assert enrolled["data"]["stages"] == []
    assert "device_id" not in str(enrolled["data"])

    await update_user_validation_assessment(
        UserValidationAssessmentUpdate(
            connection_state_understood=True,
            verify_without_logs=False,
            recovery_succeeded=True,
        ),
        user_id=_USER_ID,
    )
    withdrawn = await update_user_validation_enrollment(
        UserValidationEnrollmentUpdate(enabled=False),
        user_id=_USER_ID,
    )
    assert withdrawn["data"] == before["data"]

    async with async_session_factory() as session:
        assert await session.get(TelemetryDeviceModel, device_id) is not None
        assert await session.get(UserValidationEnrollmentModel, _USER_ID) is None
        assert await session.get(UserValidationAssessmentModel, _USER_ID) is None
        event_count = await session.scalar(
            select_count(UserValidationEventModel, _USER_ID)
        )
    assert event_count == 0


async def test_validation_starts_at_explicit_enrollment_without_replaying_history() -> None:
    await _prepare_validation_data()
    created = await create_telemetry_device(
        DeviceCreateRequest(name="Existing workstation", agent_type="codex"),
        _USER_ID,
    )
    identity = await get_telemetry_identity(f"Bearer {created['data']['token']}")
    await ingest_telemetry_events(
        TelemetryBatchRequest(
            source="gateway",
            session_id="validation-legacy-session",
            events=[
                TelemetryEventInput(
                    event_id="validation-legacy-call",
                    event_type="tool_call",
                    occurred_at=datetime.now(timezone.utc),
                )
            ],
        ),
        identity,
    )

    enrolled = await update_user_validation_enrollment(
        UserValidationEnrollmentUpdate(enabled=True),
        user_id=_USER_ID,
    )
    assert enrolled["data"]["stages"] == []

    await ingest_telemetry_events(
        TelemetryBatchRequest(
            source="gateway",
            session_id="validation-new-session",
            events=[
                TelemetryEventInput(
                    event_id="validation-post-enrollment-call",
                    event_type="tool_call",
                    occurred_at=datetime.now(timezone.utc),
                )
            ],
        ),
        identity,
    )
    progress = await get_user_validation(user_id=_USER_ID)
    assert {item["stage"] for item in progress["data"]["stages"]} == {
        "gateway_first_seen",
        "first_tool_call",
    }


async def test_validation_records_only_authoritative_or_allowed_stages() -> None:
    await _prepare_validation_data()
    _created, identity = await _enrolled_device()

    await ingest_telemetry_inventory(
        _inventory_snapshot("validation-setup-snapshot", source="setup"),
        identity,
    )
    await ingest_telemetry_inventory(
        _inventory_snapshot("validation-gateway-snapshot", source="gateway"),
        identity,
    )
    await ingest_telemetry_events(
        TelemetryBatchRequest(
            source="gateway",
            session_id="validation-gateway-session",
            events=[
                TelemetryEventInput(
                    event_id="validation-tool-call-0001",
                    event_type="tool_call",
                    server_id="@validation/weather",
                    tool_name="private-tool",
                    status="ok",
                    occurred_at=datetime.now(timezone.utc),
                )
            ],
        ),
        identity,
    )
    direct = await record_user_validation_stage(
        UserValidationStageInput(stage="verify_succeeded", source="verify"),
        identity,
    )
    duplicate = await record_user_validation_stage(
        UserValidationStageInput(stage="verify_succeeded", source="verify"),
        identity,
    )
    assert direct["data"] == {"saved": True, "stage": "verify_succeeded"}
    assert duplicate["data"] == {"saved": False, "stage": "verify_succeeded"}

    with pytest.raises(HTTPException) as exc_info:
        await record_user_validation_stage(
            UserValidationStageInput(stage="verify_succeeded", source="setup"),
            identity,
        )
    assert exc_info.value.status_code == 422

    progress = await get_user_validation(user_id=_USER_ID)
    stages = {item["stage"] for item in progress["data"]["stages"]}
    assert {
        "device_created",
        "setup_completed",
        "gateway_first_seen",
        "first_tool_call",
        "verify_succeeded",
    } <= stages
    assert "private-tool" not in str(progress["data"])
    assert "@validation/weather" not in str(progress["data"])
    async with async_session_factory() as session:
        events = list(
            (
                await session.execute(
                    select(UserValidationEventModel).where(
                        UserValidationEventModel.user_id == _USER_ID
                    )
                )
            ).scalars()
        )
    assert events
    assert all(not hasattr(event, "device_id") for event in events)


def test_validation_stage_id_is_bounded_and_does_not_expose_user_id() -> None:
    user_id = "user-" + "x" * 250
    event_id = validation_stage_id(user_id, "disconnect_completed")

    assert len(event_id) <= 96
    assert user_id not in event_id


async def test_validation_assessment_requires_enrollment() -> None:
    await _prepare_validation_data()

    with pytest.raises(HTTPException) as exc_info:
        await update_user_validation_assessment(
            UserValidationAssessmentUpdate(
                connection_state_understood=True,
                verify_without_logs=True,
                recovery_succeeded=True,
            ),
            user_id=_USER_ID,
        )
    assert exc_info.value.status_code == 409


async def test_admin_validation_analytics_is_aggregate_only() -> None:
    await _prepare_validation_data()
    _created, identity = await _enrolled_device()
    await ingest_telemetry_inventory(
        _inventory_snapshot("validation-analytics-setup", source="setup"),
        identity,
    )
    await ingest_telemetry_events(
        TelemetryBatchRequest(
            source="gateway",
            session_id="validation-analytics-gateway",
            events=[
                TelemetryEventInput(
                    event_id="validation-analytics-call",
                    event_type="tool_call",
                    occurred_at=datetime.now(timezone.utc),
                )
            ],
        ),
        identity,
    )
    await update_user_validation_assessment(
        UserValidationAssessmentUpdate(
            connection_state_understood=True,
            verify_without_logs=True,
            recovery_succeeded=False,
        ),
        user_id=_USER_ID,
    )

    result = await admin_user_validation_analytics(days=30, admin_user="admin")
    data = result["data"]

    assert data["participants"]["total"] == 1
    assert data["participants"]["by_role"]["individual_user"] == 1
    assert data["stages"]["device_created"] == 1
    assert data["stages"]["setup_completed"] == 1
    assert data["stages"]["first_tool_call"] == 1
    assert data["metrics"]["connection_state_understood"] == {
        "responses": 1,
        "yes": 1,
        "rate": 100.0,
    }
    assert data["metrics"]["recovery_succeeded"]["rate"] == 0
    assert _USER_ID not in str(data)
    assert "device_id" not in str(data)


async def test_admin_validation_analytics_uses_a_consistent_enrollment_cohort() -> None:
    await _prepare_validation_data()
    _created, identity = await _enrolled_device()
    await ingest_telemetry_inventory(
        _inventory_snapshot("validation-cohort-setup", source="setup"),
        identity,
    )
    await update_user_validation_assessment(
        UserValidationAssessmentUpdate(
            connection_state_understood=True,
            verify_without_logs=True,
            recovery_succeeded=True,
        ),
        user_id=_USER_ID,
    )
    async with async_session_factory() as session:
        enrollment = await session.get(UserValidationEnrollmentModel, _USER_ID)
        assessment = await session.get(UserValidationAssessmentModel, _USER_ID)
        assert enrollment is not None
        assert assessment is not None
        old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=31)
        enrollment.enrolled_at = old_time
        assessment.updated_at = old_time
        await session.commit()

    result = await admin_user_validation_analytics(days=30, admin_user="admin")
    data = result["data"]
    assert data["participants"]["total"] == 0
    assert data["stages"]["setup_completed"] == 0
    assert data["metrics"]["connection_state_understood"] == {
        "responses": 0,
        "yes": 0,
        "rate": 0,
    }


def select_count(model: type[UserValidationEventModel], user_id: str):
    """Keep SQL imports scoped to the test helper."""
    from sqlalchemy import func, select

    return select(func.count()).select_from(model).where(model.user_id == user_id)
