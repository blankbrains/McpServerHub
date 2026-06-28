"""测试全局 fixture — 数据库、CLI、API 客户端。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def temp_dir():
    """临时目录，每次测试后自动清理。"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def cli_runner():
    """Click CLI 测试工具。"""
    return CliRunner()


@pytest.fixture
def seed_data():
    """预置测试数据 — 2 个 Server。"""
    return [
        {
            "id": "@anthropic/web-search",
            "name": "web-search",
            "description": "搜索网页内容",
            "author": "anthropic",
            "categories": json.dumps(["browser"]),
            "rating": 4.8,
            "download_count": 12000,
        },
        {
            "id": "@community/sql-query",
            "name": "sql-query",
            "description": "数据库查询工具",
            "author": "community",
            "categories": json.dumps(["database"]),
            "rating": 4.2,
            "download_count": 8000,
        },
    ]


@pytest.fixture
def test_db_url(temp_dir: Path) -> str:
    """测试用 SQLite 数据库 URL。"""
    db_path = temp_dir / "test.db"
    return f"sqlite+aiosqlite:///{db_path}"
