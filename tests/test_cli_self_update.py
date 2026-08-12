"""Tests for explicit CLI/Gateway self-version commands."""

from __future__ import annotations

import json

from click.testing import CliRunner

from mcp_hub import __version__
from mcp_hub.cli import self_update
from mcp_hub.cli.app import cli
from mcp_hub.core.version_policy import STABLE_REF


def test_self_commands_are_registered_without_colliding_with_server_update() -> None:
    result = CliRunner().invoke(cli, ["self", "--help"])

    assert result.exit_code == 0, result.output
    assert "check" in result.output
    assert "upgrade" in result.output
    assert "rollback" in result.output


def test_self_check_uses_bundled_policy_without_network() -> None:
    result = CliRunner().invoke(
        cli,
        ["self", "check", "--gateway-version", "0.2.0", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["policy_source"] == "bundled_policy"
    assert payload["installed_cli_version"] == __version__
    assert payload["data"]["gateway"]["status"] == "upgrade_recommended"


def test_self_check_returns_no_token_when_hub_is_unreachable(monkeypatch) -> None:
    def fail_request(*_args, **_kwargs):
        raise self_update.httpx.ConnectError("offline")

    monkeypatch.setattr(self_update.httpx, "get", fail_request)

    result = CliRunner().invoke(
        cli,
        ["self", "check", "--hub-url", "https://hub.example.test", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "hub_unreachable"
    assert "token" not in result.output.lower()


def test_self_upgrade_dry_run_does_not_write_state_or_run_uv(tmp_path, monkeypatch) -> None:
    def fail_install(_ref: str) -> None:
        raise AssertionError("uv must not run in dry-run mode")

    monkeypatch.setattr(self_update, "_run_uv_install", fail_install)
    state_dir = tmp_path / "state"

    result = CliRunner().invoke(
        cli,
        [
            "self",
            "upgrade",
            "--state-dir",
            str(state_dir),
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["target_ref"] == STABLE_REF
    assert payload["agent_config_changed"] is False
    assert payload["device_token_changed"] is False
    assert not (state_dir / "cli-update-history.json").exists()


def test_self_upgrade_records_history_only_after_success(tmp_path, monkeypatch) -> None:
    installed: list[str] = []
    monkeypatch.setattr(self_update, "_run_uv_install", installed.append)
    state_dir = tmp_path / "state"

    result = CliRunner().invoke(
        cli,
        ["self", "upgrade", "--state-dir", str(state_dir), "--json"],
    )

    assert result.exit_code == 0, result.output
    assert installed == [STABLE_REF]
    history = json.loads((state_dir / "cli-update-history.json").read_text(encoding="utf-8"))
    assert history[0]["previous_version"] == __version__
    assert history[0]["target_ref"] == STABLE_REF


def test_self_rollback_rejects_mutable_ref_and_uses_valid_history(tmp_path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    self_update._append_history(
        state_dir,
        self_update.UpgradeRecord(
            previous_version="0.2.0",
            target_ref=STABLE_REF,
            created_at="2026-08-12T00:00:00+00:00",
        ),
    )
    installed: list[str] = []
    monkeypatch.setattr(self_update, "_run_uv_install", installed.append)

    invalid = CliRunner().invoke(
        cli,
        ["self", "rollback", "--to", "main", "--state-dir", str(state_dir)],
    )
    valid = CliRunner().invoke(
        cli,
        ["self", "rollback", "--state-dir", str(state_dir), "--json"],
    )

    assert invalid.exit_code == 1
    assert "稳定 Git Tag" in invalid.output
    assert valid.exit_code == 0, valid.output
    assert installed == ["v0.2.0"]
