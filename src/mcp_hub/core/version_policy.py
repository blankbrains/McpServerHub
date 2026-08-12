"""Stable CLI and Gateway release compatibility policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from mcp_hub import __version__

GITHUB_REPOSITORY = "https://github.com/blankbrains/McpServerHub.git"
STABLE_REF = f"v{__version__}"
TEST_REF = "main"
# Version 0.2.0 introduced the authenticated telemetry Gateway contract. Keep
# it supported during the 0.3 release so an updated Hub does not turn healthy
# existing devices into a failed verification solely because they have not
# upgraded yet.
MINIMUM_GATEWAY_VERSION = "0.2.0"
RECOMMENDED_GATEWAY_VERSION = __version__

VersionStatus = Literal[
    "current",
    "upgrade_recommended",
    "upgrade_required",
    "blocked",
    "unknown",
]
_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?$")
_RELEASE_TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class VersionAssessment:
    """Compatibility result for one observed CLI or Gateway version."""

    status: VersionStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status, "message": self.message}


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def install_command(ref: str) -> str:
    """Return a reproducible uv installation command without credentials."""
    return f'uv tool install --force "git+{GITHUB_REPOSITORY}@{ref}"'


def is_release_tag(value: str) -> bool:
    """Return whether a value is a stable, immutable-looking release tag."""
    return bool(_RELEASE_TAG_PATTERN.fullmatch(value.strip()))


def assess_version(version: str) -> VersionAssessment:
    """Classify a client version against the current Hub policy."""
    normalized = version.strip()
    parsed = parse_version(normalized)
    minimum = parse_version(MINIMUM_GATEWAY_VERSION)
    recommended = parse_version(RECOMMENDED_GATEWAY_VERSION)
    if parsed is None or minimum is None or recommended is None:
        return VersionAssessment("unknown", "版本号无法识别，建议运行 mcp-hub self upgrade。")
    if parsed < minimum:
        return VersionAssessment(
            "upgrade_required",
            f"当前版本 {normalized} 低于最低支持版本 {MINIMUM_GATEWAY_VERSION}。",
        )
    if parsed < recommended:
        return VersionAssessment(
            "upgrade_recommended",
            f"当前版本 {normalized} 低于推荐版本 {RECOMMENDED_GATEWAY_VERSION}。",
        )
    if parsed == recommended:
        return VersionAssessment("current", f"当前版本 {normalized} 为推荐版本。")
    return VersionAssessment(
        "unknown",
        (
            f"当前版本 {normalized} 高于此 Hub 已声明的推荐版本 "
            f"{RECOMMENDED_GATEWAY_VERSION}，请运行 mcp-hub self check "
            "确认实际兼容策略。"
        ),
    )


def build_compatibility_payload(
    *,
    cli_version: str = "",
    gateway_version: str = "",
) -> dict[str, Any]:
    """Build the public version policy response."""
    cli_assessment = assess_version(cli_version) if cli_version else None
    gateway_assessment = assess_version(gateway_version) if gateway_version else None
    return {
        "hub_version": __version__,
        "minimum_gateway_version": MINIMUM_GATEWAY_VERSION,
        "recommended_gateway_version": RECOMMENDED_GATEWAY_VERSION,
        "blocked_gateway_versions": [],
        "stable_ref": STABLE_REF,
        "test_ref": TEST_REF,
        "channels": [
            {
                "name": "stable",
                "ref": STABLE_REF,
                "install_command": install_command(STABLE_REF),
                "description": "可重复安装的稳定版本。",
            },
            {
                "name": "test",
                "ref": TEST_REF,
                "install_command": install_command(TEST_REF),
                "description": "跟踪 main，仅用于测试，不保证可重复。",
            },
        ],
        "upgrade_instructions": [
            f"稳定升级：{install_command(STABLE_REF)}",
            f"测试通道：{install_command(TEST_REF)}",
            "升级前记录当前版本；升级失败不会修改 Agent 配置或设备令牌。",
        ],
        "cli": (
            {
                "version": cli_version,
                **cli_assessment.to_dict(),
            }
            if cli_assessment
            else None
        ),
        "gateway": (
            {
                "version": gateway_version,
                **gateway_assessment.to_dict(),
            }
            if gateway_assessment
            else None
        ),
    }


def version_command_for_gateway(gateway_version: str) -> dict[str, str]:
    """Return the status and stable upgrade command for a device row."""
    assessment = assess_version(gateway_version)
    return {
        **assessment.to_dict(),
        "current_version": gateway_version,
        "recommended_version": RECOMMENDED_GATEWAY_VERSION,
        "upgrade_command": install_command(STABLE_REF),
    }
