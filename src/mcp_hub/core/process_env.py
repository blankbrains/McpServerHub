"""Least-privilege environment inheritance for managed MCP processes."""

from __future__ import annotations

import os
from collections.abc import Mapping

_SAFE_ENV_NAMES = {
    "PATH",
    "HOME",
    "USER",
    "USERNAME",
    "LOGNAME",
    "LANG",
    "LANGUAGE",
    "TZ",
    "SHELL",
    "TERM",
    "COLORTERM",
    "TMP",
    "TEMP",
    "TMPDIR",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "PROGRAMDATA",
    "COMPUTERNAME",
    "HOSTNAME",
    "PWD",
    "OLDPWD",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "NODE_PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PYTHONUNBUFFERED",
    "EDITOR",
    "VISUAL",
    "PAGER",
}
_SAFE_ENV_PREFIXES = ("LC_", "XDG_")


def filter_process_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return only the basic runtime environment shared with an MCP subprocess."""
    source = environment if environment is not None else os.environ
    return {
        key: value
        for key, value in source.items()
        if key.upper() in _SAFE_ENV_NAMES
        or key.upper().startswith(_SAFE_ENV_PREFIXES)
    }
