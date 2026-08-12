"""Regression tests for public CLI and Gateway compatibility policy."""

from __future__ import annotations

from mcp_hub import __version__
from mcp_hub.core.version_policy import (
    MINIMUM_GATEWAY_VERSION,
    STABLE_REF,
    assess_version,
    build_compatibility_payload,
    install_command,
    is_release_tag,
    parse_version,
    version_command_for_gateway,
)


def test_version_policy_supports_telemetry_gateway_baseline_and_recommends_release() -> None:
    assert MINIMUM_GATEWAY_VERSION == "0.2.0"
    assert assess_version("0.1.9").status == "upgrade_required"
    assert assess_version("0.2.0").status == "upgrade_recommended"
    assert assess_version("0.3.0").status == "upgrade_recommended"
    assert assess_version(__version__).status == "current"


def test_version_policy_handles_invalid_and_newer_versions_conservatively() -> None:
    assert parse_version("v0.3") == (0, 3, 0)
    assert parse_version("not-a-version") is None
    assert assess_version("not-a-version").status == "unknown"
    assert assess_version("9.0.0").status == "unknown"


def test_version_policy_only_accepts_release_tags_for_rollback() -> None:
    assert is_release_tag("v0.3.1")
    assert not is_release_tag("0.3.0")
    assert not is_release_tag("main")
    assert not is_release_tag("v0.3")


def test_public_payload_and_device_command_never_include_credentials() -> None:
    payload = build_compatibility_payload(
        cli_version="0.2.0",
        gateway_version=__version__,
    )
    device = version_command_for_gateway("0.2.0")

    assert payload["stable_ref"] == STABLE_REF
    assert payload["cli"]["status"] == "upgrade_recommended"
    assert payload["gateway"]["status"] == "current"
    assert device["status"] == "upgrade_recommended"
    assert device["upgrade_command"] == install_command(STABLE_REF)
    assert "token" not in str(payload).lower()
    assert "token" not in str(device).lower()
