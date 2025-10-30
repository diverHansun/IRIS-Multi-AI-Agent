"""Utility functions for virtual filesystem operations."""

from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import Iterator, Literal, Sequence

from langgraph.store.base import Item

from .types import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    EMPTY_CONTENT_WARNING,
    LINE_NUMBER_WIDTH,
    MAX_LINE_LENGTH,
    FileData,
    iso_now,
)

LineFormatStyle = Literal["pipe", "tab"]


def normalize_virtual_path(path: str) -> str:
    """Return a canonical absolute path using forward slashes.

    Virtual filesystem paths don't need security checks since it's isolated from host.
    """
    if not path:
        raise ValueError("Path cannot be empty")

    candidate = path.replace("\\", "/").strip()
    if candidate.startswith("~"):
        raise ValueError("Tilde expansion is not supported inside the virtual filesystem")

    parts = candidate.split("/")
    if any(part == ".." for part in parts):
        raise ValueError("Path traversal is not allowed")

    pure = PurePosixPath("/" + candidate.lstrip("/"))
    normalized = str(pure)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def to_line_iter(content: str | Sequence[str]) -> Iterator[str]:
    """Yield sanitized lines with MAX_LINE_LENGTH truncation applied."""
    if isinstance(content, str):
        lines = content.splitlines()
    else:
        lines = list(content)

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if len(line) > MAX_LINE_LENGTH:
            yield f"{line[:MAX_LINE_LENGTH]}…"
        else:
            yield line


def format_with_line_numbers(
    content: str | Sequence[str],
    *,
    start_line: int = 1,
    style: LineFormatStyle = "pipe",
) -> str:
    """Render content with line numbers similar to `cat -n`."""
    if start_line < 1:
        raise ValueError("start_line must be at least 1")

    formatted_lines: list[str] = []
    line_number = start_line
    for line in to_line_iter(content):
        if style == "pipe":
            formatted_lines.append(f"{line_number}|{line}")
        elif style == "tab":
            formatted_lines.append(f"{str(line_number).rjust(LINE_NUMBER_WIDTH)}\t{line}")
        else:
            raise ValueError(f"Unknown line number style '{style}'")
        line_number += 1
    return "\n".join(formatted_lines)


def string_to_file_data(content: str) -> FileData:
    """Create FileData payload from raw string content.

    No size/line limits for virtual filesystem - it's memory-based and isolated.
    """
    timestamp = iso_now()
    return FileData(content=content.splitlines(), created_at=timestamp, modified_at=timestamp)


def update_file_data(existing: FileData, new_content: str) -> FileData:
    """Return a copy of FileData with updated content and timestamp."""
    updated = FileData(
        content=new_content.splitlines(),
        created_at=existing["created_at"],
        modified_at=iso_now(),
    )
    return updated


def file_data_to_string(file_data: FileData) -> str:
    """Reconstruct file text from FileData."""
    return "\n".join(file_data["content"])


def empty_content_warning(content: str) -> str | None:
    """Return warning string for empty files."""
    if content.strip():
        return None
    return EMPTY_CONTENT_WARNING


def slice_content(
    file_data: FileData,
    *,
    offset: int = DEFAULT_READ_OFFSET,
    limit: int = DEFAULT_READ_LIMIT,
) -> list[str]:
    """Return a subset of lines based on offset and limit."""
    if offset < 0 or limit <= 0:
        raise ValueError("Offset must be >= 0 and limit must be > 0")

    lines = file_data["content"]
    if offset >= len(lines):
        raise ValueError(f"Line offset {offset} exceeds file length ({len(lines)} lines)")

    end_index = min(offset + limit, len(lines))
    return lines[offset:end_index]


def list_directory(paths: Sequence[str], prefix: str | None) -> list[str]:
    """Filter a set of absolute paths using an optional prefix."""
    candidates = list(paths)
    if prefix is None:
        return sorted(candidates)
    normalized = normalize_virtual_path(prefix)
    return sorted(path for path in candidates if path.startswith(normalized))


def store_payload_from_file_data(file_data: FileData) -> dict:
    """Serialize FileData for storage."""
    return {
        "content": list(file_data["content"]),
        "created_at": file_data["created_at"],
        "modified_at": file_data["modified_at"],
    }


def file_data_from_store_item(item: Item) -> FileData:
    """Hydrate FileData from LangGraph store Item."""
    value = getattr(item, "value", None)
    if not isinstance(value, dict):
        raise ValueError("Store item payload must be a mapping")
    try:
        content = value["content"]
        created_at = value["created_at"]
        modified_at = value["modified_at"]
    except KeyError as exc:
        raise ValueError(f"Missing expected field in store payload: {exc}") from exc
    if not isinstance(content, list) or not all(isinstance(line, str) for line in content):
        raise ValueError("Store item content must be a list of strings")
    if not isinstance(created_at, str) or not isinstance(modified_at, str):
        raise ValueError("Store item timestamps must be ISO strings")
    return FileData(content=list(content), created_at=created_at, modified_at=modified_at)
