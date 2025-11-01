"""Utility helpers for the real filesystem middleware."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

LINE_NUMBER_WIDTH = 6
MAX_LINE_LENGTH = 2000
DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 2000
EMPTY_CONTENT_WARNING = "System reminder: File exists but has empty contents"


def format_with_line_numbers(
    lines: Sequence[str],
    *,
    start_line: int = 1,
) -> str:
    """Render text with line numbers using a tab separator."""
    formatted = []
    number = start_line
    for raw in lines:
        text = raw.rstrip("\n")
        if len(text) > MAX_LINE_LENGTH:
            text = f"{text[:MAX_LINE_LENGTH]}..."
        formatted.append(f"{str(number).rjust(LINE_NUMBER_WIDTH)}\t{text}")
        number += 1
    return "\n".join(formatted)


def relative_display_path(path: Path, project_root: Path) -> str:
    """Return a stable string path, preferring project-root-relative form."""
    try:
        relative = path.relative_to(project_root)
        if not str(relative):
            return "."
        return relative.as_posix()
    except ValueError:
        return path.as_posix()


def is_hidden_path(path: Path) -> bool:
    """Return True if any path component should be treated as hidden."""
    return any(part.startswith(".") for part in path.parts)
