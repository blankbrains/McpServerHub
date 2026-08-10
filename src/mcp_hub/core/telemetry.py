"""本地 MCP Agent 的最小化遥测采集与可靠上报。"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_hub.agent_types import DEFAULT_AGENT_TYPE, normalize_agent_type
from mcp_hub.core.token_analyzer import Tokenizer
from mcp_hub.logging_config import get_logger

logger = get_logger(__name__)

TELEMETRY_TOKEN_ENV = "MCP_HUB_TELEMETRY_TOKEN"
REPORT_URL_ENV = "MCP_HUB_REPORT_URL"
STATE_DIR_ENV = "MCP_HUB_AGENT_STATE_DIR"
AGENT_TYPE_ENV = "MCP_HUB_AGENT_TYPE"
SPOOL_FILENAME = "telemetry-spool.sqlite3"
_BATCH_SIZE = 100
_SPOOL_ENDPOINT_EVENTS = "events"
_SPOOL_ENDPOINT_INVENTORY = "inventory"


def get_agent_state_dir(agent_type: str | None = None) -> Path:
    """返回本地 Agent 状态目录，支持通过环境变量覆盖。"""
    configured = os.environ.get(STATE_DIR_ENV)
    if configured:
        return Path(configured).expanduser()

    configured_agent_type = (
        agent_type if agent_type is not None else os.environ.get(AGENT_TYPE_ENV, DEFAULT_AGENT_TYPE)
    )
    try:
        normalized_agent_type = normalize_agent_type(configured_agent_type)
    except ValueError:
        if agent_type is not None:
            raise
        logger.warning(
            "telemetry.invalid_agent_type",
            agent_type=configured_agent_type,
        )
        normalized_agent_type = DEFAULT_AGENT_TYPE

    return Path.home() / ".config" / "mcp-hub" / normalized_agent_type


def get_spool_path(state_dir: Path | None = None) -> Path:
    """返回遥测 SQLite 队列路径，不创建文件。"""
    return (state_dir or get_agent_state_dir()) / SPOOL_FILENAME


def estimate_payload_tokens(payload: Any) -> int:
    """在本地估算 JSON 载荷 Token，调用方不得上传原始载荷。"""
    try:
        return Tokenizer.count_json(payload)
    except (TypeError, ValueError):
        return 0


def estimate_payload_bytes(payload: Any) -> int:
    """Estimate serialized payload size without retaining the payload."""
    try:
        return len(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        )
    except (TypeError, ValueError):
        return 0


def classify_error(exc: BaseException | None) -> str:
    """Map local exceptions to stable, non-sensitive telemetry categories."""
    if exc is None:
        return ""
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, (BrokenPipeError, ConnectionError)):
        return "connection"
    if isinstance(exc, FileNotFoundError):
        return "command_not_found"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, json.JSONDecodeError):
        return "protocol_invalid_json"
    return exc.__class__.__name__.lower()[:64]


class TelemetrySpool:
    """使用 SQLite 持久化遥测事件，确保网络中断时不丢失数据。"""

    def __init__(self, state_dir: Path | None = None) -> None:
        self.path = get_spool_path(state_dir)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_spool (
                event_id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL DEFAULT 'events',
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {
            str(row[1])
            for row in self._connection.execute("PRAGMA table_info(telemetry_spool)").fetchall()
        }
        if "endpoint" not in columns:
            self._connection.execute(
                "ALTER TABLE telemetry_spool ADD COLUMN endpoint TEXT NOT NULL DEFAULT 'events'"
            )
        self._connection.commit()

    def enqueue(
        self,
        event: Mapping[str, Any],
        *,
        endpoint: str = _SPOOL_ENDPOINT_EVENTS,
    ) -> None:
        """保存一个只含指标的事件，重复事件 ID 被安全忽略。"""
        self._connection.execute(
            """
            INSERT OR IGNORE INTO telemetry_spool (event_id, endpoint, payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(event["event_id"]),
                endpoint,
                json.dumps(dict(event), ensure_ascii=False, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._connection.commit()

    def peek(self, limit: int = _BATCH_SIZE) -> list[dict[str, Any]]:
        """读取最早的待上报事件，不删除。"""
        rows = self._connection.execute(
            "SELECT payload FROM telemetry_spool ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def peek_batch(self, limit: int = _BATCH_SIZE) -> tuple[str, list[dict[str, Any]]]:
        """Read the oldest homogeneous endpoint batch for reliable delivery."""
        first = self._connection.execute(
            "SELECT endpoint FROM telemetry_spool ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if first is None:
            return "", []
        endpoint = str(first[0])
        rows = self._connection.execute(
            """
            SELECT event_id, payload
            FROM telemetry_spool
            WHERE endpoint = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (endpoint, limit if endpoint == _SPOOL_ENDPOINT_EVENTS else 1),
        ).fetchall()
        return endpoint, [
            {"queue_id": str(row[0]), "payload": json.loads(row[1])} for row in rows
        ]

    def remove(self, event_ids: list[str]) -> None:
        """删除已由服务端确认接收的事件。"""
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        self._connection.execute(
            f"DELETE FROM telemetry_spool WHERE event_id IN ({placeholders})",
            event_ids,
        )
        self._connection.commit()

    def count(self) -> int:
        """返回尚未上报的事件数量。"""
        row = self._connection.execute("SELECT COUNT(*) FROM telemetry_spool").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        """关闭本地数据库连接。"""
        self._connection.close()


class TelemetryReporter:
    """将指标先持久化，再以非阻塞批量请求上传至 Hub。"""

    def __init__(self, report_url: str, token: str, state_dir: Path | None = None) -> None:
        self.report_url = report_url.rstrip("/")
        self.token = token
        self.spool = TelemetrySpool(state_dir)
        self.session_id = uuid.uuid4().hex
        self._flush_lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None

    @classmethod
    def from_environment(cls) -> TelemetryReporter | None:
        """仅在 Hub 地址和设备遥测令牌同时存在时启用。"""
        report_url = os.environ.get(REPORT_URL_ENV, "").strip()
        token = os.environ.get(TELEMETRY_TOKEN_ENV, "").strip()
        if not report_url or not token:
            return None
        return cls(report_url, token, get_agent_state_dir())

    async def record(
        self,
        event_type: str,
        *,
        server_id: str = "",
        tool_name: str = "",
        status: str = "ok",
        duration_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        input_bytes: int = 0,
        output_bytes: int = 0,
        cpu_percent: float | None = None,
        memory_bytes: int | None = None,
        process_uptime_seconds: int | None = None,
        queue_depth: int | None = None,
        operation: str = "",
        error_code: str = "",
        server_version: str = "",
        transport: str = "stdio",
    ) -> None:
        """记录事件并调度上传，任何本地或网络错误都不影响 MCP 调用。"""
        event = {
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "session_id": self.session_id,
            "server_id": server_id,
            "tool_name": tool_name,
            "operation": operation,
            "status": status,
            "error_code": error_code,
            "duration_ms": max(0, int(duration_ms)),
            "input_tokens": max(0, int(input_tokens)),
            "output_tokens": max(0, int(output_tokens)),
            "input_bytes": max(0, int(input_bytes)),
            "output_bytes": max(0, int(output_bytes)),
            "cpu_percent": cpu_percent,
            "memory_bytes": memory_bytes,
            "process_uptime_seconds": process_uptime_seconds,
            "queue_depth": (
                max(0, int(queue_depth))
                if queue_depth is not None
                else self.spool.count() + 1
            ),
            "server_version": server_version,
            "transport": transport,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.spool.enqueue(event)
        except (OSError, sqlite3.Error) as exc:
            logger.warning("telemetry.spool_write_failed", error=str(exc))
            return

        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self.flush())

    async def report_inventory(
        self,
        servers: list[dict[str, Any]],
        configuration_errors: list[dict[str, str]] | None = None,
    ) -> None:
        """Reliably report a redacted local configuration snapshot."""
        event_id = uuid.uuid4().hex
        payload = {
            "event_id": event_id,
            "servers": servers,
            "configuration_errors": [
                {
                    "server_id": str(error.get("server_id", "")),
                    "error_code": str(error.get("error_code") or "configuration_error"),
                }
                for error in (configuration_errors or [])
            ],
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.spool.enqueue(payload, endpoint=_SPOOL_ENDPOINT_INVENTORY)
        except (OSError, sqlite3.Error) as exc:
            logger.warning("telemetry.inventory_spool_write_failed", error=str(exc))
            return
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self.flush())

    async def flush(self) -> None:
        """上传一批队列数据；失败时保留队列供下次重试。"""
        async with self._flush_lock:
            while True:
                try:
                    endpoint, batch = self.spool.peek_batch()
                except (OSError, sqlite3.Error) as exc:
                    logger.warning("telemetry.spool_read_failed", error=str(exc))
                    return
                if not batch:
                    return

                try:
                    import httpx

                    if endpoint == _SPOOL_ENDPOINT_EVENTS:
                        path = "/api/v1/telemetry/events"
                        body: dict[str, Any] = {
                            "events": [entry["payload"] for entry in batch]
                        }
                    elif endpoint == _SPOOL_ENDPOINT_INVENTORY:
                        path = "/api/v1/telemetry/inventory"
                        body = batch[0]["payload"]
                    else:
                        logger.warning("telemetry.unknown_spool_endpoint", endpoint=endpoint)
                        self.spool.remove([entry["queue_id"] for entry in batch])
                        continue

                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.post(
                            f"{self.report_url}{path}",
                            json=body,
                            headers={"Authorization": f"Bearer {self.token}"},
                        )
                    if response.status_code // 100 != 2:
                        logger.warning(
                            "telemetry.upload_failed",
                            status_code=response.status_code,
                        )
                        return
                    self.spool.remove([entry["queue_id"] for entry in batch])
                except Exception as exc:
                    logger.debug("telemetry.upload_deferred", error=str(exc))
                    return

    async def close(self) -> None:
        """尽量完成待上传数据后释放本地资源。"""
        await self.flush()
        self.spool.close()
