"""SQLAlchemy ORM 数据模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from mcp_hub.db.database import Base


class ServerModel(Base):
    __tablename__ = "servers"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # @org/server-name
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    icon_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # SVG data URL
    description: Mapped[str] = mapped_column(Text, default="", nullable=True)
    author: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    publisher_type: Mapped[str] = mapped_column(
        String(50), default="individual", nullable=True
    )
    publisher_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    current_version: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    latest_version: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    categories: Mapped[str] = mapped_column(Text, default="[]", nullable=True)  # JSON array
    tags: Mapped[str] = mapped_column(Text, default="[]", nullable=True)  # JSON array
    install_type: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    install_package: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    install_command: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    config_template: Mapped[str] = mapped_column(Text, default="{}", nullable=True)
    homepage: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    license: Mapped[str] = mapped_column(String(50), default="MIT", nullable=True)
    security_level: Mapped[str] = mapped_column(
        String(50), default="unreviewed", nullable=True
    )
    security_audit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    network_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    file_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="not_installed", nullable=True
    )
    auto_restart: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )


class ReviewModel(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("servers.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    __table_args__ = (UniqueConstraint("server_id", "user_id", name="uq_review_server_user"),)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # GitHub username
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    github_id: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    last_login: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )


class FavoriteModel(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    server_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("servers.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    __table_args__ = (UniqueConstraint("user_id", "server_id", name="uq_favorite_user_server"),)


class HealthLogModel(Base):
    __tablename__ = "health_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("servers.id"), nullable=False, index=True
    )
    check_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # L1_process / L2_connection / L3_functional
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # ok / warning / error
    message: Mapped[str] = mapped_column(Text, default="", nullable=True)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=True
    )


class InstallHistoryModel(Base):
    __tablename__ = "install_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("servers.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # install / update / rollback / uninstall
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=True
    )


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )


class UsageStatsModel(Base):
    """MCP Server 调用统计 — 记录每次 tool call。"""

    __tablename__ = "usage_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), default="", index=True, nullable=True)
    tool_name: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ok", nullable=True)  # ok / error
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    __table_args__ = (
        Index("uq_usage_stats_source_event_id", "source_event_id", unique=True),
    )


class UserServerModel(Base):
    """用户跟踪的 Server 配置 — 用户隔离存储。"""

    __tablename__ = "user_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    server_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    matched: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    agent: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    group_name: Mapped[str] = mapped_column(String(100), default="", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    __table_args__ = (UniqueConstraint("user_id", "server_id", name="uq_user_server"),)


class NotificationModel(Base):
    """用户通知 — 系统事件、Server 告警、版本更新等。"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # alert / update / reply / system
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=True)
    server_id: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    link: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )


class PresetModel(Base):
    """配置方案 — 用户可发布整套 MCP 配置供他人一键导入。"""

    __tablename__ = "presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=True)
    tags: Mapped[str] = mapped_column(String(500), default="", nullable=True)  # 逗号分隔
    servers: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON: [{server_id, command, ...}]
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )


class TelemetryDeviceModel(Base):
    """可撤销的本地 Agent 遥测设备凭证。"""

    __tablename__ = "telemetry_devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="generic", index=True
    )
    gateway_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )
    runtime_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    architecture: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    setup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    gateway_first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    gateway_last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    first_call_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_queue_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_code: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )


class TelemetryEventModel(Base):
    """本地 Agent 上报的最小化遥测事件，不保存请求或响应正文。"""

    __tablename__ = "telemetry_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("telemetry_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        String(64), default="", index=True, nullable=True
    )
    server_id: Mapped[str] = mapped_column(
        String(255), default="", index=True, nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    operation: Mapped[str] = mapped_column(String(64), default="", nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="ok", index=True, nullable=True
    )
    error_code: Mapped[str] = mapped_column(
        String(64), default="", index=True, nullable=True
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    input_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    output_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    server_version: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    transport: Mapped[str] = mapped_column(String(32), default="stdio", nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True, nullable=True
    )


class TelemetryInventoryModel(Base):
    """Privacy-preserving local MCP configuration inventory."""

    __tablename__ = "telemetry_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("telemetry_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    server_name: Mapped[str] = mapped_column(String(255), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), default="stdio", nullable=True)
    command_name: Mapped[str] = mapped_column(String(255), default="", nullable=True)
    env_keys: Mapped[str] = mapped_column(Text, default="[]", nullable=True)
    header_keys: Mapped[str] = mapped_column(Text, default="[]", nullable=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    server_version: Mapped[str] = mapped_column(
        String(50), default="", nullable=True
    )
    protocol_version: Mapped[str] = mapped_column(
        String(32), default="", nullable=True
    )
    capabilities: Mapped[str] = mapped_column(Text, default="[]", nullable=True)
    tool_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=True
    )
    configuration_error: Mapped[str] = mapped_column(
        String(64), default="", nullable=True
    )
    discovered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "server_name",
            name="uq_telemetry_inventory_device_server",
        ),
    )
