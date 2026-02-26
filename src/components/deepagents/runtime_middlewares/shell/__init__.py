"""Shell middleware for persistent shell sessions in agents."""

from .config import SecurityPolicyConfig, ShellConfig, build_shell_config
from .middleware import ShellToolMiddleware
from .security import (
    DirectExecutor,
    DockerExecutor,
    PERMISSIVE_POLICY,
    STRICT_POLICY,
    PolicyViolationError,
    SecurityPolicy,
    ShellExecutor,
)
from .session import PersistentShellSession
from .tool import ShellTool

__all__ = [
    "SecurityPolicyConfig",
    "ShellConfig",
    "build_shell_config",
    "ShellToolMiddleware",
    "PersistentShellSession",
    "ShellTool",
    "SecurityPolicy",
    "PolicyViolationError",
    "STRICT_POLICY",
    "PERMISSIVE_POLICY",
    "ShellExecutor",
    "DirectExecutor",
    "DockerExecutor",
]
