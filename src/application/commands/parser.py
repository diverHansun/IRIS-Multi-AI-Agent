"""
Command parsing helpers migrated from the legacy CLI module.
"""

from __future__ import annotations

from typing import Tuple


def parse_command(query: str) -> Tuple[str, str]:
    """
    Split a command input into the command token and remaining arguments.
    Implementation will be copied from the legacy CLI during migration.
    """
    query = query.strip()
    if not query:
        return "", ""
    parts = query.split(" ", 1)
    command = parts[0].strip()
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def is_command(query: str) -> bool:
    """
    Determine whether the input should be treated as a command.
    """
    return query.strip().startswith("/")


def extract_command_name(command: str) -> str:
    """
    Return the command identifier without the leading slash.
    """
    return command[1:] if command.startswith("/") else command

