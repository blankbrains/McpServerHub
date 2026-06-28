"""安全扫描引擎。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from mcp_hub.models.server import SecurityLevel


@dataclass
class ScanResult:
    level: SecurityLevel
    issues: list[str] = None
    network_access: bool = False
    file_access: bool = False
    score: int = 100  # 0-100


class SecurityScanner:
    SUSPICIOUS_PATTERNS = [
        r"base64\.decode",
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"os\.system",
        r"subprocess\.(call|Popen|run)",
        r"requests\.get\(",
        r"urllib\.request",
        r"open\(.*['\"].*\.(env|key|cert)['\"].*\)",
    ]

    async def scan(self, server_data: dict) -> ScanResult:
        """扫描 Server 安全性，返回结果。"""
        issues = []
        network_access = False
        file_access = False
        description = server_data.get("description", "").lower()
        tags = server_data.get("tags", [])

        # Check for network access
        if any(w in description for w in ["web", "api", "http", "search", "network"]):
            network_access = True

        # Check for file access
        if any(w in description for w in ["file", "filesystem", "fs ", "read", "write"]):
            file_access = True

        # Check tags
        if "file_access" in description:
            file_access = True
        if "network_access" in description:
            network_access = True

        # Score
        score = 100
        if file_access:
            score -= 10
        if network_access:
            score -= 10

        # Determine level
        if score >= 90:
            level: SecurityLevel = "verified"
        elif score >= 70:
            level = "reviewed"
        else:
            level = "unreviewed"

        return ScanResult(
            level=level,
            issues=issues,
            network_access=network_access,
            file_access=file_access,
            score=score,
        )
