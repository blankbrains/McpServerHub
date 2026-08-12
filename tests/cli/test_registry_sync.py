"""CLI behavior tests for official Registry synchronization."""

from __future__ import annotations

from click.testing import CliRunner

from mcp_hub.cli import registry_sync as registry_sync_module


def test_registry_sync_defaults_to_official_source() -> None:
    parameter = next(
        parameter
        for parameter in registry_sync_module.registry_sync.params
        if parameter.name == "source"
    )

    assert parameter.default == "official"


def test_registry_sync_official_dry_run_reports_source_result(monkeypatch) -> None:
    async def sync_from_official_registry(dry_run: bool) -> dict[str, int | str]:
        assert dry_run is True
        return {
            "source": "official_mcp",
            "entries": 2,
            "created": 0,
            "updated": 0,
            "hidden": 0,
        }

    monkeypatch.setattr(
        registry_sync_module,
        "sync_from_official_registry",
        sync_from_official_registry,
    )
    result = CliRunner().invoke(registry_sync_module.registry_sync, ["--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Official Registry previewed: 2" in result.output


async def test_official_registry_sync_prepares_schema_before_writing(monkeypatch) -> None:
    prepared = False

    async def ensure_database_schema() -> None:
        nonlocal prepared
        prepared = True

    async def sync(self, client) -> dict[str, int | str]:
        del self, client
        assert prepared is True
        return {
            "source": "official_mcp",
            "entries": 1,
            "created": 1,
            "updated": 0,
            "hidden": 0,
        }

    monkeypatch.setattr(
        "mcp_hub.db.database.ensure_database_schema",
        ensure_database_schema,
    )
    monkeypatch.setattr(
        "mcp_hub.core.registry_sources.sync.RegistrySourceSynchronizer.sync",
        sync,
    )

    result = await registry_sync_module.sync_from_official_registry(dry_run=False)

    assert result["created"] == 1
    assert prepared is True
