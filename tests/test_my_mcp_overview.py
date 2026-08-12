"""Unified My MCP overview and private local tracking regression tests."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select

from mcp_hub.api.routes_my_mcp import (
    TrackLocalServerRequest,
    get_my_mcp_overview,
    track_my_mcp_server,
)
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import (
    Base,
    ServerModel,
    TelemetryDeviceModel,
    TelemetryEventModel,
    TelemetryInventoryModel,
    UserServerModel,
)

_WEATHER = "@overview/weather"
_FILES = "@overview/files"
_DUPLICATE_ONE = "@overview/duplicate-one"
_DUPLICATE_TWO = "@overview/duplicate-two"
_DEVICE_IDS = (
    "overview-alice-laptop",
    "overview-alice-desktop",
    "overview-alice-discovery",
    "overview-bob-device",
)


async def _prepare_overview_data() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    server_names = [
        _WEATHER,
        _FILES,
        _DUPLICATE_ONE,
        _DUPLICATE_TWO,
        "weather",
        "private-db",
        "legacy-oauth",
        "discovery-only",
        "ambiguous",
        "event-only-private",
    ]
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await session.execute(
            delete(TelemetryEventModel).where(
                TelemetryEventModel.server_id.in_(server_names)
            )
        )
        await session.execute(
            delete(TelemetryInventoryModel).where(
                TelemetryInventoryModel.server_name.in_(server_names)
            )
        )
        await session.execute(
            delete(TelemetryDeviceModel).where(
                TelemetryDeviceModel.id.in_(_DEVICE_IDS)
            )
        )
        await session.execute(
            delete(UserServerModel).where(
                UserServerModel.server_id.in_(
                    [_WEATHER, _FILES, "private-db", "legacy-oauth"]
                )
            )
        )
        await session.execute(
            delete(ServerModel).where(
                ServerModel.id.in_(
                    [_WEATHER, _FILES, _DUPLICATE_ONE, _DUPLICATE_TWO]
                )
            )
        )
        session.add_all(
            [
                ServerModel(
                    id=_WEATHER,
                    name="weather",
                    display_name="Weather",
                    description="Listed weather tools",
                    security_level="verified",
                ),
                ServerModel(
                    id=_FILES,
                    name="files",
                    display_name="Files",
                    description="Listed file tools",
                    security_level="reviewed",
                ),
                ServerModel(
                    id=_DUPLICATE_ONE,
                    name="ambiguous",
                    display_name="Ambiguous One",
                    security_level="reviewed",
                ),
                ServerModel(
                    id=_DUPLICATE_TWO,
                    name="ambiguous",
                    display_name="Ambiguous Two",
                    security_level="reviewed",
                ),
                UserServerModel(
                    user_id="overview-alice",
                    server_id=_WEATHER,
                    matched=True,
                ),
                UserServerModel(
                    user_id="overview-alice",
                    server_id=_FILES,
                    matched=True,
                    enabled=False,
                ),
                TelemetryDeviceModel(
                    id=_DEVICE_IDS[0],
                    user_id="overview-alice",
                    name="Alice Laptop",
                    agent_type="codex",
                    token_hash="1" * 64,
                    gateway_first_seen_at=now,
                    gateway_last_seen_at=now,
                ),
                TelemetryDeviceModel(
                    id=_DEVICE_IDS[1],
                    user_id="overview-alice",
                    name="Alice Desktop",
                    agent_type="claude-code",
                    token_hash="2" * 64,
                    gateway_first_seen_at=now,
                    gateway_last_seen_at=now,
                ),
                TelemetryDeviceModel(
                    id=_DEVICE_IDS[2],
                    user_id="overview-alice",
                    name="Alice Discovery",
                    agent_type="cursor",
                    token_hash="4" * 64,
                ),
                TelemetryDeviceModel(
                    id=_DEVICE_IDS[3],
                    user_id="overview-bob",
                    name="Bob Laptop",
                    agent_type="codex",
                    token_hash="3" * 64,
                    gateway_first_seen_at=now,
                    gateway_last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[0],
                    server_name="weather",
                    config_hash="a" * 64,
                    running=True,
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[1],
                    server_name="weather",
                    config_hash="b" * 64,
                    running=True,
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[0],
                    server_name="private-db",
                    config_hash="c" * 64,
                    running=False,
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[0],
                    server_name="legacy-oauth",
                    config_hash="d" * 64,
                    running=False,
                    enabled=False,
                    configuration_error="unsupported_or_invalid",
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[2],
                    server_name="discovery-only",
                    config_hash="e" * 64,
                    running=False,
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[2],
                    server_name="ambiguous",
                    config_hash="f" * 64,
                    running=False,
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryInventoryModel(
                    user_id="overview-bob",
                    device_id=_DEVICE_IDS[3],
                    server_name="weather",
                    config_hash="z" * 64,
                    running=True,
                    discovered_at=now,
                    last_seen_at=now,
                ),
                TelemetryEventModel(
                    id="overview-alice-weather-call",
                    user_id="overview-alice",
                    device_id=_DEVICE_IDS[0],
                    event_type="tool_call",
                    server_id="weather",
                    tool_name="forecast",
                    status="ok",
                    input_tokens=3,
                    output_tokens=2,
                    occurred_at=now,
                ),
                TelemetryEventModel(
                    id="overview-bob-weather-call",
                    user_id="overview-bob",
                    device_id=_DEVICE_IDS[3],
                    event_type="tool_call",
                    server_id="weather",
                    tool_name="forecast",
                    status="error",
                    input_tokens=100,
                    output_tokens=100,
                    occurred_at=now,
                ),
            ]
        )
        await session.commit()


async def test_my_mcp_overview_unifies_status_without_publishing_local_servers() -> None:
    await _prepare_overview_data()

    result = await get_my_mcp_overview(days=7, user_id="overview-alice")
    servers = {
        item["server_id"]: item for item in result["data"]["servers"]
    }

    assert result["data"]["summary"] == {
        "total": 6,
        "discovered": 5,
        "tracked": 2,
        "connected": 2,
        "needs_attention": 3,
        "conflicts": 1,
    }
    weather = servers[_WEATHER]
    assert weather["market_status"] == "listed"
    assert weather["tracking_status"] == "tracked"
    assert weather["gateway_status"] == "connected"
    assert weather["runtime_status"] == "running"
    assert weather["call_status"] == "called"
    assert weather["config_status"] == "conflict"
    assert weather["device_count"] == 2
    assert weather["call_count_7d"] == 1
    assert weather["token_consumption"] == 5
    assert weather["success_rate"] == 100.0
    assert weather["primary_action"]["code"] == "compare_configuration"

    private = servers["private-db"]
    assert private["market_status"] == "unlisted"
    assert private["tracking_status"] == "untracked"
    assert private["gateway_status"] == "connected"
    assert private["primary_action"]["code"] == "track"
    assert private["devices"][0]["device_name"] == "Alice Laptop"

    retained = servers["legacy-oauth"]
    assert retained["gateway_status"] == "direct_retained"
    assert retained["needs_attention"] is True
    assert retained["primary_action"]["code"] == "diagnose"

    discovery_only = servers["discovery-only"]
    assert discovery_only["discovered"] is True
    assert discovery_only["gateway_status"] == "not_connected"
    assert discovery_only["tracking_status"] == "untracked"
    assert discovery_only["needs_attention"] is False

    ambiguous = servers["ambiguous"]
    assert ambiguous["entity_id"] == "local:ambiguous"
    assert ambiguous["market_status"] == "unlisted"
    assert ambiguous["market_id"] is None
    assert ambiguous["tracking_status"] == "untracked"
    assert ambiguous["primary_action"]["code"] == "track"

    files = servers[_FILES]
    assert files["tracking_status"] == "tracked"
    assert files["gateway_status"] == "not_connected"
    assert files["enabled"] is False
    assert files["primary_action"]["code"] == "view_setup"

    serialized = str(result)
    assert "overview-bob-device" not in serialized
    assert "DATABASE_URL" not in serialized
    assert "Authorization" not in serialized

    async with async_session_factory() as session:
        assert await session.get(ServerModel, "private-db") is None


async def test_my_mcp_overview_is_user_scoped() -> None:
    await _prepare_overview_data()

    alice = await get_my_mcp_overview(days=7, user_id="overview-alice")
    bob = await get_my_mcp_overview(days=7, user_id="overview-bob")

    alice_weather = next(
        item for item in alice["data"]["servers"] if item["server_id"] == _WEATHER
    )
    bob_weather = next(
        item for item in bob["data"]["servers"] if item["server_id"] == _WEATHER
    )
    assert alice_weather["device_count"] == 2
    assert alice_weather["call_count_7d"] == 1
    assert bob_weather["device_count"] == 1
    assert bob_weather["call_count_7d"] == 1
    assert bob_weather["token_consumption"] == 200
    assert "private-db" not in {
        item["server_id"] for item in bob["data"]["servers"]
    }


async def test_tracking_private_local_server_does_not_publish_market_entry() -> None:
    await _prepare_overview_data()

    result = await track_my_mcp_server(
        TrackLocalServerRequest(server_id="private-db"),
        user_id="overview-alice",
    )

    assert result["data"] == {
        "server_id": "private-db",
        "tracked": True,
        "matched": False,
        "published": False,
    }
    async with async_session_factory() as session:
        tracked = await session.scalar(
            select(UserServerModel).where(
                UserServerModel.user_id == "overview-alice",
                UserServerModel.server_id == "private-db",
            )
        )
        assert tracked is not None
        assert tracked.matched is False
        assert await session.get(ServerModel, "private-db") is None

    overview = await get_my_mcp_overview(days=7, user_id="overview-alice")
    private = next(
        item
        for item in overview["data"]["servers"]
        if item["server_id"] == "private-db"
    )
    assert private["tracking_status"] == "tracked"
    assert private["market_status"] == "unlisted"


async def test_tracking_market_server_records_matched_state() -> None:
    await _prepare_overview_data()
    async with async_session_factory() as session:
        await session.execute(
            delete(UserServerModel).where(
                UserServerModel.user_id == "overview-alice",
                UserServerModel.server_id == _FILES,
            )
        )
        await session.commit()

    result = await track_my_mcp_server(
        TrackLocalServerRequest(server_id=_FILES),
        user_id="overview-alice",
    )

    assert result["data"]["matched"] is True
    async with async_session_factory() as session:
        tracked = await session.scalar(
            select(UserServerModel).where(
                UserServerModel.user_id == "overview-alice",
                UserServerModel.server_id == _FILES,
            )
        )
        assert tracked is not None
        assert tracked.matched is True


async def test_tracking_existing_private_server_preserves_matched_state() -> None:
    await _prepare_overview_data()
    async with async_session_factory() as session:
        session.add(
            UserServerModel(
                user_id="overview-alice",
                server_id="private-db",
                matched=False,
            )
        )
        await session.commit()

    result = await track_my_mcp_server(
        TrackLocalServerRequest(server_id="private-db"),
        user_id="overview-alice",
    )

    assert result["data"]["matched"] is False


async def test_event_only_private_server_has_no_invalid_track_action() -> None:
    await _prepare_overview_data()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_factory() as session:
        session.add(
            TelemetryEventModel(
                id="overview-alice-event-only",
                user_id="overview-alice",
                device_id=_DEVICE_IDS[0],
                event_type="tool_call",
                server_id="event-only-private",
                tool_name="run",
                status="ok",
                occurred_at=now,
            )
        )
        await session.commit()

    overview = await get_my_mcp_overview(days=7, user_id="overview-alice")
    event_only = next(
        item
        for item in overview["data"]["servers"]
        if item["server_id"] == "event-only-private"
    )
    assert event_only["discovered"] is False
    assert event_only["gateway_status"] == "connected"
    assert event_only["primary_action"]["code"] == "view_monitoring"

    try:
        await track_my_mcp_server(
            TrackLocalServerRequest(server_id="event-only-private"),
            user_id="overview-alice",
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("event-only private Server must not be guessed into tracking")


async def test_tracking_rejects_unknown_private_server_name() -> None:
    await _prepare_overview_data()

    try:
        await track_my_mcp_server(
            TrackLocalServerRequest(server_id="guessed-private-server"),
            user_id="overview-alice",
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("unknown private Server must not be tracked")
