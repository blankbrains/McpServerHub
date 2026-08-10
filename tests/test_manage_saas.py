"""SaaS management boundaries must never mutate Hub-host process state."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from mcp_hub.api import routes_manage


class _FakeResult:
    def scalar_one_or_none(self) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.execute = AsyncMock(return_value=_FakeResult())
        self.commit = AsyncMock()

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def add(self, value: object) -> None:
        self.added.append(value)


class _FakeRegistry:
    def __init__(self) -> None:
        self.update_status = AsyncMock()
        self.increment_download = AsyncMock()

    async def get_by_id(self, server_id: str) -> dict[str, object]:
        return {
            "id": server_id,
            "display_name": "Example",
            "install_command": "uvx example-mcp",
            "version": "1.0.0",
        }


async def test_install_only_tracks_current_user_without_global_status_mutation(
    monkeypatch,
) -> None:
    registry = _FakeRegistry()
    sessions: list[_FakeSession] = []

    def session_factory() -> _FakeSession:
        session = _FakeSession()
        sessions.append(session)
        return session

    monkeypatch.setattr(routes_manage, "Registry", lambda: registry)
    monkeypatch.setattr("mcp_hub.db.database.async_session_factory", session_factory)
    monkeypatch.setattr(routes_manage, "AGENT_CONFIGS", {})

    result = await routes_manage.install_server(
        routes_manage.InstallRequest(server_id="@example/server"),
        user_id="user-a",
    )

    assert result["success"] is True
    registry.update_status.assert_not_awaited()
    registry.increment_download.assert_awaited_once_with("@example/server")
    assert len(sessions) == 2
    assert sessions[0].added
    history_params = sessions[1].execute.await_args.args[1]
    assert history_params["uid"] == "user-a"


async def test_uninstall_only_removes_current_user_tracking(
    monkeypatch,
) -> None:
    registry = _FakeRegistry()
    session = _FakeSession()

    monkeypatch.setattr(routes_manage, "Registry", lambda: registry)
    monkeypatch.setattr(
        "mcp_hub.db.database.async_session_factory",
        lambda: session,
    )
    monkeypatch.setattr(
        routes_manage,
        "get_process_manager",
        lambda: (_ for _ in ()).throw(AssertionError("must not access Hub process manager")),
    )
    monkeypatch.setattr(
        routes_manage,
        "asyncio",
        SimpleNamespace(
            create_subprocess_exec=AsyncMock(
                side_effect=AssertionError("must not execute pip uninstall")
            )
        ),
        raising=False,
    )

    result = await routes_manage.uninstall_server(
        "@example/server",
        user_id="user-a",
    )

    assert result["success"] is True
    assert "你的配置" in result["message"]
    registry.update_status.assert_not_awaited()
    session.execute.assert_awaited_once()
    assert session.added
    session.commit.assert_awaited_once()
