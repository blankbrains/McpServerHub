"""MCP Server Hub 集中日志配置 — 基于 structlog 的结构化日志。

使用方式:
    from mcp_hub.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("server.installed", server_id="@org/server", version="2.1.0")
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


def configure_logging(
    level: int = logging.INFO,
    json_format: bool = False,
) -> None:
    """配置 structlog + 标准库日志集成。

    Args:
        level: 日志级别，默认 INFO。
        json_format: 是否输出 JSON 格式（生产环境建议 True）。
    """

    # 共享的预处理器链
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format or os.environ.get("MCP_HUB_LOG_JSON", "").lower() in ("1", "true", "yes"):
        # 生产模式：JSON 输出（兼容日志收集系统）
        renderer = structlog.processors.JSONRenderer()
    elif sys.stdout.isatty():
        # 开发模式：彩色终端输出
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # 管道/文件模式：纯文本
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置标准库日志处理器（structlog → stdlib 桥接）
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # 降低第三方库的日志噪音
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化日志记录器。

    Args:
        name: 日志记录器名称（通常传 __name__）。

    Returns:
        绑定到给定名称的 structlog 日志记录器。

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("server.started", server_id="@org/test", pid=12345)
    """
    return structlog.get_logger(name or "mcp_hub")


# 模块级别默认 logger（用于简单场景）
logger = get_logger("mcp_hub")
