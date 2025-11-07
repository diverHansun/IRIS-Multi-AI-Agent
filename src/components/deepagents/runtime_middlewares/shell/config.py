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


def build_shell_config(config_dict: Dict[str, Any]) -> ShellConfig:
    """
    Build ShellConfig from configuration dictionary.

    Args:
        config_dict: Configuration dictionary

    Returns:
        ShellConfig instance
    """
    workspace_root = config_dict.get("workspace_root", ".")
    if isinstance(workspace_root, str):
        workspace_root = Path(workspace_root).resolve()
    elif not isinstance(workspace_root, Path):
        workspace_root = Path.cwd()

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
