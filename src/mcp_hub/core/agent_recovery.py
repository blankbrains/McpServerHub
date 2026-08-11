"""Migration manifests and conflict-safe Agent configuration recovery."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mcp_hub import __version__
from mcp_hub.agent_types import normalize_agent_type
from mcp_hub.core.agent_config import (
    AgentMigration,
    read_agent_document,
    write_agent_document_with_backup,
)
from mcp_hub.core.gateway_config import GATEWAY_CONFIG_ENV
from mcp_hub.core.telemetry import (
    AGENT_TYPE_ENV,
    STATE_DIR_ENV,
    get_agent_state_dir,
)

MIGRATION_MANIFEST_FILENAME = "migration-manifest.json"
MIGRATION_HISTORY_DIRNAME = "migration-history"
_GATEWAY_NAMES = ("mcp-hub", "mcp-hub-gateway")
_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class MigrationManifest(BaseModel):
    """Privacy-preserving record of one Agent migration."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    migration_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: Literal["active", "disconnected"]
    agent_type: str
    source_config_path: str
    original_backup_path: str
    migration_time: str
    pre_migration_hash: str = Field(pattern=_SHA256_PATTERN)
    post_migration_hash: str = Field(pattern=_SHA256_PATTERN)
    gateway_entry_hash: str = Field(pattern=_SHA256_PATTERN)
    migrated_server_names: list[str]
    retained_server_names: list[str]
    gateway_config_path: str
    cli_version: str
    disconnected_at: str | None = None
    disconnect_backup_path: str | None = None
    restored_file_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)


@dataclass(frozen=True)
class RecoveryConflict:
    """One configuration ownership conflict that prevents automatic recovery."""

    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class RecoveryPreview:
    """Safe, non-sensitive recovery plan derived from current local files."""

    manifest: MigrationManifest
    manifest_path: Path
    source_path: Path
    current_hash: str
    post_hash_matches: bool
    restore_server_names: list[str]
    already_restored_server_names: list[str]
    preserved_server_names: list[str]
    changed_top_level_keys: list[str]
    remove_gateway: bool
    config_changes_required: bool
    already_disconnected: bool
    conflicts: list[RecoveryConflict] = field(default_factory=list)
    repaired_document: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def safe(self) -> bool:
        return not self.conflicts

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.safe,
            "migration_id": self.manifest.migration_id,
            "status": self.manifest.status,
            "agent_type": self.manifest.agent_type,
            "manifest_path": str(self.manifest_path),
            "source_config_path": str(self.source_path),
            "current_hash": self.current_hash,
            "post_hash_matches": self.post_hash_matches,
            "restore_server_names": self.restore_server_names,
            "already_restored_server_names": self.already_restored_server_names,
            "preserved_server_names": self.preserved_server_names,
            "changed_top_level_keys": self.changed_top_level_keys,
            "remove_gateway": self.remove_gateway,
            "config_changes_required": self.config_changes_required,
            "already_disconnected": self.already_disconnected,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }


@dataclass(frozen=True)
class RecoveryResult:
    """Result of one confirmed disconnect or restore operation."""

    preview: RecoveryPreview
    changed: bool
    backup_path: Path | None
    restored_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            **self.preview.to_dict(),
            "success": True,
            "changed": self.changed,
            "backup_path": str(self.backup_path) if self.backup_path else None,
            "restored_hash": self.restored_hash,
        }


def get_migration_manifest_path(
    state_dir: Path | None = None,
    *,
    agent_type: str | None = None,
) -> Path:
    """Return the canonical migration manifest for one local Agent."""
    return (state_dir or get_agent_state_dir(agent_type)) / MIGRATION_MANIFEST_FILENAME


def _history_manifest_path(state_dir: Path, migration_id: str) -> Path:
    return state_dir / MIGRATION_HISTORY_DIRNAME / f"{migration_id}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _gateway_identity_hash(entry: dict[str, Any]) -> str:
    raw_env = entry.get("env")
    env = raw_env if isinstance(raw_env, dict) else {}
    raw_args = entry.get("args")
    args = raw_args if isinstance(raw_args, list) else []
    command = str(entry.get("command") or "").strip()
    identity = {
        "command": Path(command).name.lower(),
        "args": [str(arg) for arg in args],
        "type": str(entry.get("type") or ""),
        "agent_type": str(env.get(AGENT_TYPE_ENV) or ""),
        "state_dir": str(env.get(STATE_DIR_ENV) or ""),
        "gateway_config": str(env.get(GATEWAY_CONFIG_ENV) or ""),
    }
    return _value_hash(identity)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        temp_path.chmod(0o600)
    temp_path.replace(path)


def _write_manifest(
    manifest: MigrationManifest,
    *,
    state_dir: Path,
) -> Path:
    payload = manifest.model_dump(mode="json")
    history_path = _history_manifest_path(state_dir, manifest.migration_id)
    canonical_path = get_migration_manifest_path(state_dir)
    _write_json_atomic(history_path, payload)
    _write_json_atomic(canonical_path, payload)
    return canonical_path


def load_migration_manifest(path: Path) -> MigrationManifest:
    """Load and validate a migration manifest without exposing config values."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return MigrationManifest.model_validate(raw)
    except FileNotFoundError:
        raise
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"迁移清单无效: {path}") from exc


def ensure_setup_can_create_manifest(
    agent_type: str,
    *,
    source_path: Path,
    state_dir: Path,
) -> None:
    """Prevent a new setup from replacing an active recovery record."""
    manifest_path = get_migration_manifest_path(state_dir)
    if not manifest_path.exists():
        return
    manifest = load_migration_manifest(manifest_path)
    normalized_agent = normalize_agent_type(agent_type)
    if manifest.status == "active":
        raise ValueError(
            "当前状态目录已有未断开的迁移清单，请先运行 "
            f"mcp-hub agent disconnect --agent {normalized_agent}"
        )
    if (
        manifest.agent_type == normalized_agent
        and Path(manifest.source_config_path).absolute() == source_path.absolute()
    ):
        return


def create_migration_manifest(
    migration: AgentMigration,
    *,
    backup_path: Path,
    gateway_config_path: Path,
    state_dir: Path,
) -> MigrationManifest:
    """Persist one manifest after setup has written the Gateway entry."""
    _profile, source_path, migrated_document = read_agent_document(
        migration.profile.agent_type,
        migration.source_path,
    )
    raw_servers = migrated_document.get(migration.profile.server_key)
    if not isinstance(raw_servers, dict):
        raise ValueError("迁移后的 Agent Server 配置不是对象")
    gateway_entry = raw_servers.get("mcp-hub")
    if not isinstance(gateway_entry, dict):
        raise ValueError("迁移后的 Agent 配置缺少 mcp-hub Gateway 入口")

    manifest = MigrationManifest(
        migration_id=uuid.uuid4().hex,
        status="active",
        agent_type=migration.profile.agent_type,
        source_config_path=str(source_path),
        original_backup_path=str(backup_path),
        migration_time=_utc_now(),
        pre_migration_hash=_file_hash(backup_path),
        post_migration_hash=_file_hash(source_path),
        gateway_entry_hash=_gateway_identity_hash(gateway_entry),
        migrated_server_names=[spec.server_id for spec in migration.specs],
        retained_server_names=list(migration.retained_server_names),
        gateway_config_path=str(gateway_config_path),
        cli_version=__version__,
    )
    _write_manifest(manifest, state_dir=state_dir)
    return manifest


def list_migration_manifests(
    state_dir: Path | None = None,
    *,
    agent_type: str | None = None,
) -> list[tuple[Path, MigrationManifest]]:
    """List canonical and historical manifests, newest first, without duplicates."""
    resolved_state_dir = state_dir or get_agent_state_dir(agent_type)
    candidates = [
        get_migration_manifest_path(resolved_state_dir),
        *sorted(
            (resolved_state_dir / MIGRATION_HISTORY_DIRNAME).glob("*.json"),
            reverse=True,
        ),
    ]
    manifests: dict[str, tuple[Path, MigrationManifest]] = {}
    for path in candidates:
        if not path.exists():
            continue
        manifest = load_migration_manifest(path)
        if agent_type is not None and manifest.agent_type != normalize_agent_type(agent_type):
            continue
        existing = manifests.get(manifest.migration_id)
        if existing is None or path.name == MIGRATION_MANIFEST_FILENAME:
            manifests[manifest.migration_id] = (path, manifest)
    return sorted(
        manifests.values(),
        key=lambda item: item[1].migration_time,
        reverse=True,
    )


def _validated_backup_path(manifest: MigrationManifest, source_path: Path) -> Path:
    backup_path = Path(manifest.original_backup_path).expanduser()
    expected_prefix = f"{source_path.name}.mcp-hub-backup-"
    if (
        backup_path.absolute().parent != source_path.absolute().parent
        or not backup_path.name.startswith(expected_prefix)
    ):
        raise ValueError("迁移清单中的备份路径不属于原 Agent 配置")
    if not backup_path.is_file():
        raise FileNotFoundError(f"未找到原配置备份: {backup_path}")
    if _file_hash(backup_path) != manifest.pre_migration_hash:
        raise ValueError("原配置备份哈希与迁移清单不一致")
    return backup_path


def _changed_top_level_keys(
    original: dict[str, Any],
    current: dict[str, Any],
    *,
    server_key: str,
) -> list[str]:
    missing = object()
    keys = (set(original) | set(current)) - {server_key}
    return sorted(
        key
        for key in keys
        if original.get(key, missing) != current.get(key, missing)
    )


def _resolve_recovery_state_dir(
    agent_type: str,
    *,
    state_dir: Path | None,
    manifest_path: Path | None,
) -> Path:
    if state_dir is not None:
        return state_dir
    if manifest_path is not None:
        parent = manifest_path.expanduser().absolute().parent
        return parent.parent if parent.name == MIGRATION_HISTORY_DIRNAME else parent
    return get_agent_state_dir(agent_type)


def prepare_agent_recovery(
    agent_type: str,
    *,
    state_dir: Path | None = None,
    manifest_path: Path | None = None,
) -> RecoveryPreview:
    """Build a conflict-safe restoration plan without modifying local files."""
    normalized_agent = normalize_agent_type(agent_type)
    resolved_state_dir = _resolve_recovery_state_dir(
        normalized_agent,
        state_dir=state_dir,
        manifest_path=manifest_path,
    )
    resolved_manifest_path = manifest_path or get_migration_manifest_path(
        resolved_state_dir
    )
    manifest = load_migration_manifest(resolved_manifest_path)
    if manifest.agent_type != normalized_agent:
        raise ValueError(
            f"迁移清单属于 {manifest.agent_type}，不能用于 {normalized_agent}"
        )

    canonical_path = get_migration_manifest_path(resolved_state_dir)
    if (
        canonical_path.exists()
        and resolved_manifest_path.absolute() != canonical_path.absolute()
    ):
        canonical_manifest = load_migration_manifest(canonical_path)
        if canonical_manifest.migration_id != manifest.migration_id:
            raise ValueError(
                "指定清单不是当前迁移记录，不能自动恢复；"
                "请使用 backups 核对当前清单。"
            )

    source_path = Path(manifest.source_config_path).expanduser()
    profile, _resolved_source, current_document = read_agent_document(
        normalized_agent,
        source_path,
    )
    current_hash = _file_hash(source_path)
    post_hash_matches = current_hash == manifest.post_migration_hash

    if manifest.status == "disconnected":
        return RecoveryPreview(
            manifest=manifest,
            manifest_path=resolved_manifest_path,
            source_path=source_path,
            current_hash=current_hash,
            post_hash_matches=post_hash_matches,
            restore_server_names=[],
            already_restored_server_names=list(manifest.migrated_server_names),
            preserved_server_names=[],
            changed_top_level_keys=[],
            remove_gateway=False,
            config_changes_required=False,
            already_disconnected=True,
        )

    backup_path = _validated_backup_path(manifest, source_path)
    _backup_profile, _backup_source, original_document = read_agent_document(
        normalized_agent,
        backup_path,
    )
    original_servers = original_document.get(profile.server_key)
    current_servers = current_document.get(profile.server_key)
    if not isinstance(original_servers, dict):
        raise ValueError(f"原配置中的 {profile.server_key} 不是对象")
    if not isinstance(current_servers, dict):
        raise ValueError(f"当前配置中的 {profile.server_key} 不是对象")

    conflicts: list[RecoveryConflict] = []
    restore_names: list[str] = []
    already_restored: list[str] = []
    migrated_names = set(manifest.migrated_server_names)
    for server_name in manifest.migrated_server_names:
        if server_name not in original_servers:
            conflicts.append(
                RecoveryConflict(
                    "manifest_server_missing",
                    f"{profile.server_key}.{server_name}",
                    "原配置备份中缺少迁移清单声明的 Server。",
                )
            )
            continue
        if server_name not in current_servers:
            restore_names.append(server_name)
        elif current_servers[server_name] == original_servers[server_name]:
            already_restored.append(server_name)
        else:
            conflicts.append(
                RecoveryConflict(
                    "server_name_conflict",
                    f"{profile.server_key}.{server_name}",
                    "当前配置存在同名但内容不同的 Server，不能自动覆盖。",
                )
            )

    remove_gateway = False
    for gateway_name in _GATEWAY_NAMES:
        gateway_entry = current_servers.get(gateway_name)
        if gateway_entry is None:
            continue
        if (
            gateway_name == "mcp-hub"
            and isinstance(gateway_entry, dict)
            and _gateway_identity_hash(gateway_entry) == manifest.gateway_entry_hash
        ):
            remove_gateway = True
        else:
            conflicts.append(
                RecoveryConflict(
                    "gateway_entry_modified",
                    f"{profile.server_key}.{gateway_name}",
                    "Gateway 入口已被修改或替换，不能确认是否仍属于本次迁移。",
                )
            )

    preserved_names = sorted(
        str(name)
        for name in current_servers
        if str(name) not in migrated_names and str(name) not in _GATEWAY_NAMES
    )
    changed_keys = _changed_top_level_keys(
        original_document,
        current_document,
        server_key=profile.server_key,
    )

    repaired_document: dict[str, Any] | None = None
    config_changes_required = False
    if not conflicts:
        repaired_servers = {
            name: value
            for name, value in current_servers.items()
            if str(name) not in _GATEWAY_NAMES
        }
        for server_name in manifest.migrated_server_names:
            repaired_servers[server_name] = original_servers[server_name]
        repaired_document = {
            **current_document,
            profile.server_key: repaired_servers,
        }
        config_changes_required = repaired_document != current_document

    return RecoveryPreview(
        manifest=manifest,
        manifest_path=resolved_manifest_path,
        source_path=source_path,
        current_hash=current_hash,
        post_hash_matches=post_hash_matches,
        restore_server_names=restore_names,
        already_restored_server_names=already_restored,
        preserved_server_names=preserved_names,
        changed_top_level_keys=changed_keys,
        remove_gateway=remove_gateway,
        config_changes_required=config_changes_required,
        already_disconnected=False,
        conflicts=conflicts,
        repaired_document=repaired_document,
    )


def apply_agent_recovery(
    agent_type: str,
    *,
    state_dir: Path | None = None,
    manifest_path: Path | None = None,
) -> RecoveryResult:
    """Apply a freshly revalidated recovery plan and update its manifest."""
    normalized_agent = normalize_agent_type(agent_type)
    resolved_state_dir = _resolve_recovery_state_dir(
        normalized_agent,
        state_dir=state_dir,
        manifest_path=manifest_path,
    )
    preview = prepare_agent_recovery(
        normalized_agent,
        state_dir=resolved_state_dir,
        manifest_path=manifest_path,
    )
    if preview.conflicts:
        raise ValueError("当前 Agent 配置存在无法自动合并的冲突")
    if preview.already_disconnected:
        return RecoveryResult(
            preview=preview,
            changed=False,
            backup_path=None,
            restored_hash=preview.current_hash,
        )

    backup_path: Path | None = None
    if preview.config_changes_required:
        if preview.repaired_document is None:
            raise ValueError("恢复计划缺少可写入配置")
        if _file_hash(preview.source_path) != preview.current_hash:
            raise ValueError("Agent 配置在恢复校验后发生变化，未写入任何内容")
        profile, _source, _current = read_agent_document(
            normalized_agent,
            preview.source_path,
        )
        backup_path = write_agent_document_with_backup(
            profile,
            preview.source_path,
            preview.repaired_document,
        )

    restored_hash = _file_hash(preview.source_path)
    updated_manifest = preview.manifest.model_copy(
        update={
            "status": "disconnected",
            "disconnected_at": _utc_now(),
            "disconnect_backup_path": str(backup_path) if backup_path else None,
            "restored_file_hash": restored_hash,
        }
    )
    _write_manifest(updated_manifest, state_dir=resolved_state_dir)
    preview.manifest = updated_manifest
    return RecoveryResult(
        preview=preview,
        changed=preview.config_changes_required,
        backup_path=backup_path,
        restored_hash=restored_hash,
    )


def manifest_summary(
    path: Path,
    manifest: MigrationManifest,
) -> dict[str, object]:
    """Return a stable, non-sensitive manifest summary for CLI output."""
    original_backup = Path(manifest.original_backup_path).expanduser()
    disconnect_backup = (
        Path(manifest.disconnect_backup_path).expanduser()
        if manifest.disconnect_backup_path
        else None
    )
    return {
        "migration_id": manifest.migration_id,
        "status": manifest.status,
        "agent_type": manifest.agent_type,
        "migration_time": manifest.migration_time,
        "manifest_path": str(path),
        "source_config_path": manifest.source_config_path,
        "original_backup_path": manifest.original_backup_path,
        "original_backup_exists": original_backup.is_file(),
        "disconnect_backup_path": manifest.disconnect_backup_path,
        "disconnect_backup_exists": bool(
            disconnect_backup and disconnect_backup.is_file()
        ),
        "gateway_config_path": manifest.gateway_config_path,
        "migrated_server_names": list(manifest.migrated_server_names),
        "retained_server_names": list(manifest.retained_server_names),
        "cli_version": manifest.cli_version,
    }
