"""安全扫描 API — 评分 + 详情。"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_hub.core.registry import Registry
from mcp_hub.core.security_scanner import SecurityScanner
from mcp_hub.exceptions import ServerNotFoundError

router = APIRouter(tags=["security"])


@router.get("/security/scan/{server_id:path}")
async def scan_server(server_id: str):
    """扫描指定 Server 的安全性。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    scanner = SecurityScanner()
    report = await scanner.scan(server)

    return {
        "success": True,
        "data": {
            "server_id": report.server_id,
            "score": report.score,
            "level": report.level,
            "network_access": report.network_access,
            "file_access": report.file_access,
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "title": f.title,
                    "description": f.description,
                    "score_impact": f.score_impact,
                }
                for f in report.findings
            ],
            "score_breakdown": report.score_breakdown(),
            "scanned_at": report.scanned_at,
        },
    }


@router.post("/security/scan/{server_id:path}/refresh")
async def refresh_scan(server_id: str):
    """强制重新扫描 Server 的安全性。"""
    registry = Registry()
    server = await registry.get_by_id(server_id)
    if not server:
        raise ServerNotFoundError(server_id)

    scanner = SecurityScanner()
    report = await scanner.scan(server)

    return {
        "success": True,
        "data": {
            "server_id": report.server_id,
            "score": report.score,
            "level": report.level,
            "scanned_at": report.scanned_at,
        },
    }
