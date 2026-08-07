"""Notification ownership and deletion regression tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from mcp_hub.api.routes_notifications import delete_notification, router
from mcp_hub.db.database import async_session_factory, engine
from mcp_hub.db.models import Base, NotificationModel


async def _prepare_notifications() -> tuple[int, int]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await session.execute(delete(NotificationModel))
        session.add_all(
            [
                NotificationModel(user_id="alice", type="alert", title="Alice alert"),
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


def test_delete_notification_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.delete("/api/v1/notifications/1")

    assert response.status_code == 401
