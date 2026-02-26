"""Command filtering policies for shell middleware."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Pattern


class PolicyViolationError(ValueError):
    """Raised when a command is blocked by the configured security policy."""


@dataclass(frozen=True)
class SecurityPolicy:
    """Pure shell command filtering policy."""

    blocked_commands: frozenset[str] = frozenset()
    blocked_patterns: tuple[Pattern[str], ...] = ()
    unsafe_tokens: tuple[str, ...] = ()
    sensitive_env_keywords: tuple[str, ...] = ()

    def validate(self, command: str) -> None:
        """Validate a command string and raise on policy violations."""
        if not command or not command.strip():
            return

        stripped = command.strip()
        first_token = stripped.split(maxsplit=1)[0].lower()
        if first_token in self.blocked_commands:
            raise PolicyViolationError(
                f"Command '{first_token}' is blocked by security policy."
            )

        for pattern in self.blocked_patterns:
            if pattern.search(command):
                raise PolicyViolationError(
                    f"Command matches a blocked pattern: {pattern.pattern}"
                )

        for token in self.unsafe_tokens:
            if token in command:
                raise PolicyViolationError(
                    f"Command contains unsafe token '{token}'. "
                    "Compound commands and redirections are not allowed."
                )

    def filter_environment(self, env: Mapping[str, str]) -> dict[str, str]:
        """Return a filtered copy of environment variables."""
        if not self.sensitive_env_keywords:
            return dict(env)
        return {
            key: value
            for key, value in env.items()
            if not any(keyword in key.upper() for keyword in self.sensitive_env_keywords)
        }


STRICT_POLICY = SecurityPolicy(
    blocked_commands=frozenset(
        {
            "rm",
            "sudo",
            "poweroff",
            "shutdown",
            "reboot",
            "halt",
            "mkfs",
            "dd",
            "chmod",
            "chown",
            # Windows / PowerShell destructive commands
            "del",
            "erase",
            "rd",
            "rmdir",
            "remove-item",
            "format",
            "diskpart",
        }
    ),
    blocked_patterns=(
        re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
        re.compile(r"rm\s+-rf\s+~", re.IGNORECASE),
        re.compile(r":\s*\(\)\s*{\s*:\s*\|\s*:\s*;\s*}\s*;", re.IGNORECASE),  # fork bomb
        re.compile(r"remove-item\s+.+-recurse.+-force", re.IGNORECASE),
    ),
    unsafe_tokens=(
        "&&",
        "||",
        ">>",
        "<<",
        "$(",
        ";",
        "|",
        ">",
        "<",
        "`",
        "&",
    ),
    sensitive_env_keywords=(
        "API_KEY",
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "PASS",
        "AUTH",
        "PRIVATE_KEY",
    ),
)

PERMISSIVE_POLICY = SecurityPolicy()

