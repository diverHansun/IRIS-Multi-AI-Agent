"""Utility helpers for the real filesystem middleware."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

LINE_NUMBER_WIDTH = 6
MAX_LINE_LENGTH = 2000
DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 2000
EMPTY_CONTENT_WARNING = "System reminder: File exists but has empty contents"
MAX_DIFF_LINES = 1500
MAX_CAPTURED_OUTPUT = 1_000_000  # bytes


@dataclass(slots=True)
class DiffPreview:
    """Unified diff metadata for approval previews."""

    diff: str | None
    truncated: bool
    added_lines: int
    removed_lines: int


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


def count_lines(text: str) -> int:
    """Return the number of newline-delimited lines in text."""
    if not text:
        return 0
    return len(text.splitlines())


def encode_size(text: str, encoding: str = "utf-8") -> int:
    """Return the number of encoded bytes for text."""
    return len(text.encode(encoding))


def compute_text_diff(
    before: str,
    after: str,
    display_path: str,
    *,
    max_lines: int = MAX_DIFF_LINES,
) -> DiffPreview:
    """Compute diff metadata between text versions."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"{display_path} (before)",
            tofile=f"{display_path} (after)",
            lineterm="",
        )
    )

    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    truncated = False
    rendered_diff: str | None = None
    if diff_lines:
        if max_lines is not None and len(diff_lines) > max_lines:
            truncated = True
            visible = diff_lines[: max_lines - 1]
            visible.append(f"... (diff truncated to {max_lines} lines)")
            rendered_diff = "\n".join(visible)
        else:
            rendered_diff = "\n".join(diff_lines)

    return DiffPreview(diff=rendered_diff, truncated=truncated, added_lines=added, removed_lines=removed)


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
