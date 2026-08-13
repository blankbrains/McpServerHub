"""Notification ownership and deletion regression tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from mcp_hub.api.routes_notifications import (
    delete_notification,
    list_notifications,
    mark_all_read,
    router,
    unread_count,
)
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import Base, NotificationModel


async def _prepare_notifications() -> tuple[int, int]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await session.execute(delete(NotificationModel))
        session.add_all(
            [
                NotificationModel(user_id="alice", type="system", title="Alice notice"),
                NotificationModel(user_id="bob", type="alert", title="Bob alert"),
            ]
        )
        await session.commit()
        result = await session.execute(
            select(NotificationModel.id, NotificationModel.user_id).order_by(NotificationModel.id)
        )
        ids = {user_id: notification_id for notification_id, user_id in result.fetchall()}
    return ids["alice"], ids["bob"]


async def test_delete_notification_is_scoped_to_current_user() -> None:
    alice_notification, bob_notification = await _prepare_notifications()

    result = await delete_notification(alice_notification, user_id="alice")

    assert result["success"] is True
    async with async_session_factory() as session:
        remaining_users = set((await session.execute(select(NotificationModel.user_id))).scalars())
    assert remaining_users == {"bob"}

    with pytest.raises(HTTPException, match="通知不存在"):
        await delete_notification(bob_notification, user_id="alice")


async def test_dismissing_an_active_alert_keeps_it_hidden_until_reconciled() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await session.execute(delete(NotificationModel))
        alert = NotificationModel(
            user_id="alice",
            type="alert",
            title="Active alert",
            alert_key="gateway_offline:test-device",
            status="active",
            is_read=False,
        )
        session.add(alert)
        await session.commit()
        alert_id = alert.id

    result = await delete_notification(alert_id, user_id="alice")
    assert result["data"] == {"dismissed": True}

    async with async_session_factory() as session:
        persisted = await session.get(NotificationModel, alert_id)
        assert persisted is not None
        assert persisted.status == "suppressed"
        assert persisted.is_read is True

    response = await list_notifications(
        user_id="alice",
        unread_only=True,
        status="active",
        page=1,
        page_size=50,
    )
    assert response["data"]["items"] == []


async def test_audit_records_stay_out_of_user_notifications() -> None:
    _alice_notification, _bob_notification = await _prepare_notifications()
    async with async_session_factory() as session:
        audit = NotificationModel(
            user_id="alice",
            type="audit",
            title="修改用户角色",
            is_read=False,
            status="active",
        )
        session.add(audit)
        await session.commit()
        audit_id = audit.id

    listed = await list_notifications(
        user_id="alice",
        unread_only=False,
        status="all",
        page=1,
        page_size=50,
    )
    assert [item["type"] for item in listed["data"]["items"]] == ["system"]

    count = await unread_count(user_id="alice")
    assert count["data"]["count"] == 1

    await mark_all_read(user_id="alice")
    async with async_session_factory() as session:
        persisted_audit = await session.get(NotificationModel, audit_id)
        assert persisted_audit is not None
        assert persisted_audit.is_read is False

    with pytest.raises(HTTPException, match="通知不存在"):
        await delete_notification(audit_id, user_id="alice")


def test_delete_notification_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.delete("/api/v1/notifications/1")

    assert response.status_code == 401
