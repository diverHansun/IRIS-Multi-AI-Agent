"""Configuration dataclass for shell middleware."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class ShellConfig:
    """Configuration for persistent shell middleware."""

    enabled: bool = True
    workspace_root: Path = field(default_factory=Path.cwd)
    shell_type: str = "cmd" if os.name == "nt" else "bash"
    command_timeout: float = 30.0
    startup_timeout: float = 10.0
    termination_timeout: float = 5.0
    max_output_lines: int = 100
    max_output_bytes: int = 1048576
    environment: Dict[str, str] = field(default_factory=dict)
    startup_commands: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.command_timeout <= 0:
            raise ValueError("command_timeout must be positive")
        if self.startup_timeout <= 0:
            raise ValueError("startup_timeout must be positive")
        if self.termination_timeout <= 0:
            raise ValueError("termination_timeout must be positive")
        if self.max_output_lines <= 0:
            raise ValueError("max_output_lines must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")

    def get_shell_command(self) -> List[str]:
        """
        Get the shell command for the current platform.

        Returns:
            List of command arguments to start shell
        """
        shell_type = self.shell_type.lower()

        if os.name == "nt":
            if shell_type == "powershell":
                return ["powershell.exe", "-NoLogo", "-NoProfile"]
            return ["cmd.exe", "/Q"]
        return ["/bin/bash", "--norc", "--noprofile"]


def _normalize_project_root(project_root: Path | str | None) -> Path | None:
    """Normalize optional project root input to Path."""
    if project_root is None:
        return None
    return project_root if isinstance(project_root, Path) else Path(project_root)


def _resolve_workspace_root(
    workspace_root: Any,
    project_root: Path | str | None = None,
) -> Path:
    """
    Resolve workspace_root with project-aware semantics.

    Semantics:
    - "auto"/"."/missing -> project_root when available, else Path.cwd()
    - relative path -> resolved relative to project_root when available
    - absolute path -> resolved as-is
    """
    normalized_project_root = _normalize_project_root(project_root)

    if workspace_root in (None, "", "auto", "."):
        return (
            normalized_project_root.resolve()
            if normalized_project_root is not None
            else Path.cwd()
        )

    if isinstance(workspace_root, Path):
        candidate = workspace_root
    elif isinstance(workspace_root, str):
        candidate = Path(workspace_root)
    else:
        return (
            normalized_project_root.resolve()
            if normalized_project_root is not None
            else Path.cwd()
        )

    if not candidate.is_absolute() and normalized_project_root is not None:
        candidate = normalized_project_root / candidate

    return candidate.resolve()


def build_shell_config(
    config_dict: Dict[str, Any],
    project_root: Path | str | None = None,
) -> ShellConfig:
    """
    Build ShellConfig from configuration dictionary.

    Args:
        config_dict: Configuration dictionary
        project_root: Optional project root for resolving "auto" and relative paths

    Returns:
        ShellConfig instance
    """
    workspace_root = _resolve_workspace_root(
        config_dict.get("workspace_root", "auto"),
        project_root=project_root,
    )

    shell_type = config_dict.get("shell_type", "cmd" if os.name == "nt" else "bash")
    environment = config_dict.get("environment", {})
    if not isinstance(environment, dict):
        environment = {}

    startup_commands = config_dict.get("startup_commands", [])
    if not isinstance(startup_commands, list):
        startup_commands = []

    return ShellConfig(
        enabled=bool(config_dict.get("enabled", True)),
        workspace_root=workspace_root,
        shell_type=str(shell_type),
        command_timeout=float(config_dict.get("command_timeout", 30.0)),
        startup_timeout=float(config_dict.get("startup_timeout", 10.0)),
        termination_timeout=float(config_dict.get("termination_timeout", 5.0)),
        max_output_lines=int(config_dict.get("max_output_lines", 100)),
        max_output_bytes=int(config_dict.get("max_output_bytes", 1048576)),
        environment=environment,
        startup_commands=startup_commands,
    )
