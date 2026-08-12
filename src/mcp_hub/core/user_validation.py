"""Shared, privacy-minimized contract for the opt-in user validation study."""

from __future__ import annotations

from hashlib import sha256
from typing import Final, Literal

ParticipantRole = Literal["individual_user", "server_publisher", "team_admin"]
ValidationStage = Literal[
    "device_created",
    "setup_started",
    "setup_completed",
    "gateway_first_seen",
    "first_tool_call",
    "verify_failed",
    "verify_succeeded",
    "disconnect_completed",
    "restore_completed",
]
ValidationStageSource = Literal["setup", "verify", "recovery"]

VALIDATION_PARTICIPANT_ROLES: Final[tuple[ParticipantRole, ...]] = (
    "individual_user",
    "server_publisher",
    "team_admin",
)

VALIDATION_STAGES: Final[tuple[ValidationStage, ...]] = (
    "device_created",
    "setup_started",
    "setup_completed",
    "gateway_first_seen",
    "first_tool_call",
    "verify_failed",
    "verify_succeeded",
    "disconnect_completed",
    "restore_completed",
)

VALIDATION_STAGE_SOURCES: Final[
    dict[ValidationStageSource, frozenset[ValidationStage]]
] = {
    "setup": frozenset({"setup_started", "setup_completed"}),
    "verify": frozenset({"verify_failed", "verify_succeeded"}),
    "recovery": frozenset({"disconnect_completed", "restore_completed"}),
}

VALIDATION_STAGE_LABELS: Final[dict[ValidationStage, str]] = {
    "device_created": "创建设备",
    "setup_started": "开始接入",
    "setup_completed": "完成接入配置",
    "gateway_first_seen": "Gateway 首次在线",
    "first_tool_call": "首次工具调用",
    "verify_failed": "验证发现问题",
    "verify_succeeded": "验证通过",
    "disconnect_completed": "安全断开完成",
    "restore_completed": "恢复完成",
}


def validation_stage_id(user_id: str, stage: ValidationStage) -> str:
    """Return a bounded, non-identifying id for one user-level milestone."""
    digest = sha256(user_id.encode("utf-8")).hexdigest()[:32]
    return f"validation:{stage}:{digest}"
