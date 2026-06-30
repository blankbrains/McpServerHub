"""SQLAlchemy ORM 数据模型。"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from mcp_hub.db.database import Base


class ServerModel(Base):
    __tablename__ = "servers"

    id = Column(String(255), primary_key=True)  # @org/server-name
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), default="")
    icon_url = Column(Text, nullable=True)  # SVG data URL
    description = Column(Text, default="")
    author = Column(String(255), default="")
    publisher_type = Column(String(50), default="individual")
    publisher_verified = Column(Boolean, default=False)
    current_version = Column(String(50), default="")
    latest_version = Column(String(50), default="")
    categories = Column(Text, default="[]")  # JSON array
    tags = Column(Text, default="[]")  # JSON array
    install_type = Column(String(50), default="")
    install_package = Column(String(255), default="")
    install_command = Column(String(500), default="")
    config_template = Column(Text, default="{}")
    homepage = Column(String(500), default="")
    license = Column(String(50), default="MIT")
    security_level = Column(String(50), default="unreviewed")
    security_audit_at = Column(DateTime, nullable=True)
    network_access = Column(Boolean, default=False)
    file_access = Column(Boolean, default=False)
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0)
    status = Column(String(50), default="not_installed")
    auto_restart = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReviewModel(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(String(255), ForeignKey("servers.id"), nullable=False)
    user_id = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=True)
    rating = Column(Integer, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("server_id", "user_id", name="uq_review_server_user"),
    )


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(255), primary_key=True)  # GitHub username
    display_name = Column(String(255), default="")
    avatar_url = Column(String(500), default="")
    github_id = Column(String(255), default="")
    email = Column(String(255), default="")
    role = Column(String(50), default="user")
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, server_default=func.now())


class FavoriteModel(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    server_id = Column(String(255), ForeignKey("servers.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "server_id", name="uq_favorite_user_server"),
    )


class HealthLogModel(Base):
    __tablename__ = "health_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(String(255), ForeignKey("servers.id"), nullable=False)
    check_type = Column(String(50), nullable=False)  # L1_process / L2_connection / L3_functional
    status = Column(String(50), nullable=False)  # ok / warning / error
    message = Column(Text, default="")
    response_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class EventModel(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(255), nullable=False)
    publisher = Column(String(255), nullable=False)
    payload = Column(Text, default="{}")
    created_at = Column(DateTime, server_default=func.now())


class InstallHistoryModel(Base):
    __tablename__ = "install_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(String(255), ForeignKey("servers.id"), nullable=False)
    version = Column(String(50), default="")
    action = Column(String(50), nullable=False)  # install / update / rollback / uninstall
    status = Column(String(50), default="success")
    created_at = Column(DateTime, server_default=func.now())


class SubscriptionModel(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(String(255), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class UsageStatsModel(Base):
    """MCP Server 调用统计 — 记录每次 tool call。"""
    __tablename__ = "usage_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(String(255), nullable=False, index=True)
    tool_name = Column(String(255), default="")
    status = Column(String(50), default="ok")  # ok / error
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class UserServerModel(Base):
    """用户跟踪的 Server 配置 — 用户隔离存储。"""
    __tablename__ = "user_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    server_id = Column(String(255), nullable=False)
    matched = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    agent = Column(String(50), default="")
    group_name = Column(String(100), default="")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "server_id", name="uq_user_server"),
    )
